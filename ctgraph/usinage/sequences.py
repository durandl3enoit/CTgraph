"""La gamme d'usinage : une suite ordonnée de séquences attachée à la pièce.

Une **séquence** dit quoi faire, avec quel poste de tourelle et dans quelles conditions de coupe. Elle
ne garde aucune copie du dessin : sa trajectoire se recalcule depuis le profil résolu (voir
`ctgraph.usinage.trajectoires`). Changer une cote change donc la trajectoire, et plus tard le G-code.

Sept types, ceux que montrent les programmes Go2CAM archivés (`docs/reference-go2cam-ct200.md`) :

* **dressage** de la face avant, en passes successives de la matière vers l'axe ;
* **ébauche** paraxiale, passes parallèles à Z qui descendent jusqu'au profil augmenté de la
  surépaisseur de finition ;
* **finition**, qui suit le profil fini en un passage ;
* **gorge**, plongées radiales côte à côte à la largeur de l'outil ;
* **filetage**, passes de plus en plus fines le long du filet ;
* **perçage** dans l'axe, par débourrages successifs ;
* **tronçonnage**, une plongée jusqu'au diamètre demandé ou jusqu'à l'axe.

Les conditions de coupe reprennent ce que la CN attend : vitesse de coupe constante `G96`, limitation
de vitesse de broche `G92`, avance par tour `G95`. Le filetage et le perçage tournent à vitesse de
broche fixe (`G97`) : la vitesse de coupe saisie s'y entend au diamètre travaillé, et c'est le
post-processeur qui fera la conversion.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional, Tuple

from ..forets import nombre
from ..tourelle import nom_poste

# profondeur du filet au rayon, en part du pas, pour un filetage ISO métrique extérieur (H1 = 0,6134 × P)
PROFONDEUR_FILET = 0.6134


class TypeSequence(str, Enum):
    DRESSAGE = "dressage"
    CENTRAGE = "centrage"
    PERCAGE = "percage"
    EBAUCHE = "ebauche"
    ALESAGE = "alesage"
    FINITION = "finition"
    FINITION_INTERIEURE = "finition_interieure"
    GORGE = "gorge"
    FILETAGE = "filetage"
    TRONCONNAGE = "tronconnage"


LIBELLES_SEQUENCE: Dict[TypeSequence, str] = {
    TypeSequence.DRESSAGE: "Dressage de face",
    TypeSequence.CENTRAGE: "Centrage",
    TypeSequence.PERCAGE: "Perçage dans l'axe",
    TypeSequence.EBAUCHE: "Ébauche de chariotage",
    TypeSequence.ALESAGE: "Ébauche d'alésage",
    TypeSequence.FINITION: "Finition extérieure",
    TypeSequence.FINITION_INTERIEURE: "Finition d'alésage",
    TypeSequence.GORGE: "Gorge",
    TypeSequence.FILETAGE: "Filetage",
    TypeSequence.TRONCONNAGE: "Tronçonnage",
}

# le nom court, celui des boutons et des libellés automatiques : « Finition » seul ne suffirait plus à
# distinguer l'extérieur de l'intérieur
NOMS_COURTS: Dict[TypeSequence, str] = {
    TypeSequence.DRESSAGE: "Dressage",
    TypeSequence.CENTRAGE: "Centrage",
    TypeSequence.PERCAGE: "Perçage",
    TypeSequence.EBAUCHE: "Ébauche",
    TypeSequence.ALESAGE: "Alésage",
    TypeSequence.FINITION: "Finition ext.",
    TypeSequence.FINITION_INTERIEURE: "Finition int.",
    TypeSequence.GORGE: "Gorge",
    TypeSequence.FILETAGE: "Filetage",
    TypeSequence.TRONCONNAGE: "Tronçonnage",
}

USAGES_SEQUENCE: Dict[TypeSequence, str] = {
    TypeSequence.DRESSAGE: "Dresse la face avant du brut jusqu'à la face finie, en passes successives "
                           "de la matière vers l'axe.",
    TypeSequence.CENTRAGE: "Pointe l'axe avant le foret, ou perce le centre qui recevra la contre-pointe.",
    TypeSequence.PERCAGE: "Perçage dans l'axe, de la face vers le fond du trou, par débourrages "
                          "successifs.",
    TypeSequence.EBAUCHE: "Passes parallèles à l'axe, du diamètre du brut jusqu'au profil augmenté de "
                          "la surépaisseur laissée à la finition.",
    TypeSequence.ALESAGE: "Ouvre le trou percé jusqu'à la paroi voulue, à la barre, en passes parallèles "
                          "à l'axe, en laissant la surépaisseur de finition.",
    TypeSequence.FINITION: "Suit le profil extérieur fini en un passage, correction de rayon de bec à "
                           "la CN.",
    TypeSequence.FINITION_INTERIEURE: "Suit la paroi de l'alésage en un passage, à la barre. La paroi "
                                      "peut être un cylindre, ou suivre une ligne ou un arc du dessin.",
    TypeSequence.GORGE: "Plongées radiales côte à côte, à la largeur de l'outil, jusqu'au diamètre de "
                        "fond ; autant de plongées qu'il faut pour la largeur demandée.",
    TypeSequence.FILETAGE: "Passes successives le long du filet, de plus en plus fines pour garder la "
                           "section de copeau ; l'avance d'un filetage est son pas.",
    TypeSequence.TRONCONNAGE: "Plongée à la largeur de l'outil jusqu'au diamètre demandé, ou jusqu'à "
                              "l'axe pour détacher la pièce de la barre.",
}

# les réglages qui comptent pour chaque type : l'interface ne montre que ceux-là
CHAMPS_SEQUENCE: Dict[TypeSequence, Tuple[str, ...]] = {
    TypeSequence.DRESSAGE: ("profondeur_passe", "surepaisseur_face", "garde", "degagement"),
    TypeSequence.CENTRAGE: ("foret", "diametre_outil", "garde", "z_debut", "z_fin"),
    TypeSequence.PERCAGE: ("foret", "diametre_outil", "profondeur_passe", "garde", "z_debut", "z_fin"),
    TypeSequence.EBAUCHE: ("profondeur_passe", "surepaisseur", "garde", "degagement", "z_debut", "z_fin"),
    TypeSequence.ALESAGE: ("diametre_fond", "profondeur_passe", "surepaisseur",
                           "garde", "degagement", "z_debut", "z_fin"),
    TypeSequence.FINITION: ("garde", "degagement", "z_debut", "z_fin"),
    TypeSequence.FINITION_INTERIEURE: ("diametre_fond", "garde", "degagement", "z_debut", "z_fin"),
    TypeSequence.GORGE: ("largeur_outil", "largeur", "diametre_fond", "profondeur_passe", "surepaisseur",
                         "garde", "degagement", "z_debut"),
    TypeSequence.FILETAGE: ("interieur", "pas", "hauteur_filet", "profondeur_passe", "garde",
                            "degagement", "z_debut", "z_fin"),
    TypeSequence.TRONCONNAGE: ("largeur_outil", "diametre_fond", "profondeur_passe", "garde",
                               "degagement", "z_debut"),
}

# comment nommer un champ selon le type : ce ne sont pas les mêmes choses d'une opération à l'autre
LIBELLES_CHAMPS: Dict[TypeSequence, Dict[str, str]] = {
    TypeSequence.CENTRAGE: {"foret": "Foret à centrer", "diametre_outil": "Ø du corps",
                            "z_debut": "Z de la face", "z_fin": "Pointe du centre"},
    TypeSequence.PERCAGE: {"z_debut": "Z de la face", "z_fin": "Pointe du foret"},
    TypeSequence.ALESAGE: {"diametre_fond": "Ø à aléser", "z_debut": "Z de la face",
                           "z_fin": "Fond de l'alésage"},
    TypeSequence.FINITION_INTERIEURE: {"diametre_fond": "Ø fini", "z_debut": "Z de la face",
                                       "z_fin": "Fond de l'alésage"},
    TypeSequence.GORGE: {"z_debut": "Z du bord droit"},
    TypeSequence.FILETAGE: {"z_debut": "Début du filet", "z_fin": "Fin du filet"},
    TypeSequence.TRONCONNAGE: {"z_debut": "Z du tronçonnage"},
}

# ce qui change des valeurs par défaut quand on ajoute une séquence de ce type
DEFAUTS_SEQUENCE: Dict[TypeSequence, Dict[str, float]] = {
    TypeSequence.CENTRAGE: {"vitesse_coupe": 30.0, "avance": 0.08, "profondeur_passe": 10.0,
                            "foret": "À centrer 3,15 × 8", "diametre_outil": 8.0, "z_fin": -8.0,
                            "surepaisseur": 0.0},
    TypeSequence.PERCAGE: {"vitesse_coupe": 60.0, "avance": 0.12, "profondeur_passe": 5.0,
                           "foret": "Foret Ø 10", "z_fin": -20.0, "surepaisseur": 0.0},
    TypeSequence.ALESAGE: {"vitesse_coupe": 180.0, "avance": 0.12, "profondeur_passe": 1.0,
                           "diametre_fond": 20.0, "z_fin": -20.0},
    TypeSequence.FINITION_INTERIEURE: {"vitesse_coupe": 220.0, "avance": 0.08, "surepaisseur": 0.0,
                                       "diametre_fond": 20.0, "z_fin": -20.0},
    TypeSequence.FINITION: {"vitesse_coupe": 250.0, "avance": 0.1},
    TypeSequence.GORGE: {"vitesse_coupe": 120.0, "avance": 0.08, "profondeur_passe": 1.5,
                         "surepaisseur": 0.0, "largeur_outil": 3.0, "largeur": 4.0,
                         "diametre_fond": 20.0, "z_debut": -10.0},
    TypeSequence.FILETAGE: {"vitesse_coupe": 100.0, "profondeur_passe": 0.25, "surepaisseur": 0.0,
                            "pas": 1.5, "z_fin": -20.0},
    TypeSequence.TRONCONNAGE: {"vitesse_coupe": 110.0, "avance": 0.08, "profondeur_passe": 2.0,
                               "surepaisseur": 0.0},
}

# les opérations dont la profondeur se cote sur le dessin, et comment la nommer : (intitulé, lettre).
# Elle se compte toujours depuis la surface travaillée, jamais depuis le bout du brut.
LIBELLES_PROFONDEUR: Dict[TypeSequence, Tuple[str, str]] = {
    TypeSequence.CENTRAGE: ("Profondeur du centre", "P"),
    TypeSequence.PERCAGE: ("Profondeur du trou", "P"),
    TypeSequence.ALESAGE: ("Profondeur de l'alésage", "P"),
    TypeSequence.FINITION_INTERIEURE: ("Profondeur de l'alésage", "P"),
    TypeSequence.FILETAGE: ("Longueur du filet", "L"),
}
COTES_PROFONDEUR: Tuple[TypeSequence, ...] = tuple(LIBELLES_PROFONDEUR)

# la famille de porte-plaquettes (`ctgraph.outils`) qui fait cette opération ; vide pour un foret
FAMILLES_OUTIL: Dict[TypeSequence, str] = {
    TypeSequence.DRESSAGE: "ext_neg",
    TypeSequence.CENTRAGE: "",
    TypeSequence.PERCAGE: "",
    TypeSequence.EBAUCHE: "ext_neg",
    TypeSequence.ALESAGE: "alesage",
    TypeSequence.FINITION: "ext_pos",
    TypeSequence.FINITION_INTERIEURE: "alesage",
    TypeSequence.GORGE: "gorge",
    TypeSequence.FILETAGE: "filetage",
    TypeSequence.TRONCONNAGE: "gorge",
}

# La gamme type : l'enchaînement habituel d'une pièce prise en mandrin sur barre, du plus rigide au
# moins rigide. Les opérations qui demandent une cote que le dessin ne donne pas (un trou, une gorge,
# un filet) sont posées **désactivées** : l'ordre est là, il reste à dire si la pièce en a besoin.
# Chacune part tout de même de réglages qui donnent un résultat visible : on coche, on voit, on ajuste.
GAMME_TYPE: Tuple[Tuple[TypeSequence, str, bool, Dict[str, Any]], ...] = (
    (TypeSequence.DRESSAGE, "", True, {}),
    (TypeSequence.CENTRAGE, "", False, {}),
    (TypeSequence.PERCAGE, "", False, {}),
    (TypeSequence.EBAUCHE, "", True, {}),
    (TypeSequence.ALESAGE, "", False, {}),
    # la finition part du trou que l'ébauche a laissé : elle le relève sur la matière, rien à déclarer
    (TypeSequence.FINITION_INTERIEURE, "", False, {}),
    (TypeSequence.FINITION, "", True, {}),
    (TypeSequence.GORGE, "", False, {}),
    (TypeSequence.FILETAGE, "", False, {}),
    (TypeSequence.TRONCONNAGE, "", True, {}),
)


@dataclass
class Sequence:
    """Une opération de la gamme. Les longueurs sont en millimètres, les rayons au rayon (pas au diamètre)."""
    id: int = 0
    type: TypeSequence = TypeSequence.EBAUCHE
    nom: str = ""
    poste: int = 0                   # poste de tourelle ; 0 = pas encore choisi
    active: bool = True

    # conditions de coupe
    vitesse_coupe: float = 150.0     # m/min, vitesse de coupe constante (G96)
    vitesse_maxi: float = 2500.0     # tr/min, limitation de broche (G92)
    avance: float = 0.2              # mm/tour (G95)
    arrosage: bool = True

    # passes
    profondeur_passe: float = 2.0    # profondeur radiale d'une passe d'ébauche, ou axiale en dressage
    surepaisseur: float = 0.3        # ce qu'on laisse au rayon pour la finition
    surepaisseur_face: float = 0.1   # ce qu'on laisse en Z sur la face
    degagement: float = 1.0          # retrait avant le retour rapide
    garde: float = 2.0               # approche en rapide, au-dessus de la matière

    # outil et géométrie propres à certaines opérations
    largeur_outil: float = 3.0       # largeur de l'arête : gorge, tronçonnage
    largeur: float = 0.0             # largeur de la gorge à faire ; 0 = celle de l'outil
    diametre_fond: float = 0.0       # Ø au fond d'une gorge, Ø où s'arrête un tronçonnage (0 = l'axe)
    diametre_outil: float = 10.0     # Ø du foret
    foret: str = ""                  # désignation au catalogue `ctgraph.forets` ; vide = foret ordinaire
    paroi: int = 0                   # alésage : élément d'esquisse que la paroi suit ; 0 = un cylindre
    interieur: bool = False          # l'opération travaille dans l'alésage plutôt que sur l'extérieur
    pas: float = 1.5                 # pas du filet
    hauteur_filet: float = 0.0       # profondeur du filet au rayon ; 0 = PROFONDEUR_FILET × pas

    # étendue ; None = toute la longueur usinable
    z_debut: Optional[float] = None
    z_fin: Optional[float] = None

    def libelle(self) -> str:
        """Le nom montré dans la gamme : celui qu'on a donné, sinon le type **avec sa cote maîtresse**.

        « Perçage Ø 10 » dit tout de suite de quel perçage il s'agit, là où « Perçage dans l'axe » ne
        distingue pas deux lignes voisines.
        """
        if self.nom.strip():
            return self.nom.strip()
        court = NOMS_COURTS[self.type]
        if self.type in (TypeSequence.CENTRAGE, TypeSequence.PERCAGE):
            return f"{court} Ø {nombre(self.diametre_outil)}"
        if self.type in (TypeSequence.ALESAGE, TypeSequence.FINITION_INTERIEURE) \
                and self.diametre_fond > 0:
            return f"{court} Ø {nombre(self.diametre_fond)}"
        if self.type == TypeSequence.GORGE and self.diametre_fond > 0:
            return f"{court} Ø {nombre(self.diametre_fond)} × {nombre(max(self.largeur, self.largeur_outil))}"
        if self.type == TypeSequence.FILETAGE:
            return f"{court}{' int.' if self.interieur else ''} pas {nombre(self.pas)}"
        if self.type == TypeSequence.TRONCONNAGE:
            return f"{court} ép. {nombre(self.largeur_outil)}"
        return LIBELLES_SEQUENCE[self.type]

    def champs(self) -> Tuple[str, ...]:
        """Les réglages qui comptent pour ce type d'opération."""
        return CHAMPS_SEQUENCE.get(self.type, ())

    def libelle_champ(self, cle: str, defaut: str) -> str:
        """L'intitulé d'un réglage pour ce type : « Fond du trou » plutôt que « Z de fin »."""
        return LIBELLES_CHAMPS.get(self.type, {}).get(cle, defaut)

    def vitesse_fixe(self) -> bool:
        """Vrai si l'opération se fait à vitesse de broche fixe (G97) et non à Vc constante (G96)."""
        return self.type in (TypeSequence.FILETAGE, TypeSequence.PERCAGE, TypeSequence.CENTRAGE)

    def dans_l_axe(self) -> bool:
        """Vrai si l'opération travaille dans l'axe : foret, centre, barre d'alésage."""
        return self.type in (TypeSequence.CENTRAGE, TypeSequence.PERCAGE, TypeSequence.ALESAGE)

    def outil_de_percage(self):
        """Le foret de l'opération, avec sa géométrie de pointe. Jamais None : au pire un foret ordinaire."""
        from ..forets import foret as chercher, pour_diametre
        trouve = chercher(self.foret) if self.foret else None
        if trouve is not None and abs(trouve.diametre - self.diametre_outil) < 1e-6:
            return trouve
        return pour_diametre(self.diametre_outil, self.type == TypeSequence.CENTRAGE)

    # -- cotes portées sur le dessin -------------------------------------------------------

    def cotes_dessinees(self) -> Tuple[str, ...]:
        """Les valeurs de la séquence que l'on cote sur l'esquisse, et qu'on y règle."""
        return ("profondeur",) if self.type in COTES_PROFONDEUR else ()

    def z_face(self, montage=None) -> float:
        """L'abscisse d'où part une opération dans l'axe : celle qu'on donne, sinon le bout du brut.

        C'est la borne d'approche de la trajectoire, qui part toujours de la matière brute, jamais après
        elle. La **cote** de profondeur, elle, se compte depuis la surface réellement travaillée : voir
        `valeur_cote`, à qui l'appelant donne cette surface.
        """
        if self.z_debut is not None:
            return self.z_debut
        return montage.z_brut_avant() if montage is not None else 0.0

    def libelle_cote(self, cle: str) -> str:
        if cle != "profondeur":
            raise KeyError(cle)
        return LIBELLES_PROFONDEUR.get(self.type, ("Profondeur", "P"))[0]

    def valeur_cote(self, cle: str, z_surface: float) -> float:
        """La profondeur, comptée depuis la surface travaillée que l'appelant a relevée."""
        if cle != "profondeur":
            raise KeyError(cle)
        return z_surface - (self.z_fin if self.z_fin is not None else z_surface)

    def definir_valeur_cote(self, cle: str, valeur: float, z_surface: float) -> None:
        if cle != "profondeur":
            raise KeyError(cle)
        self.z_fin = z_surface - max(valeur, 0.0)

    def texte_cote(self, cle: str, z_surface: float) -> str:
        lettre = LIBELLES_PROFONDEUR.get(self.type, ("Profondeur", "P"))[1]
        return f"{lettre} {self.valeur_cote(cle, z_surface):g}"

    def profondeur_filet(self) -> float:
        """La profondeur du filet au rayon, celle qui est saisie ou celle du profil ISO métrique."""
        return self.hauteur_filet if self.hauteur_filet > 0 else PROFONDEUR_FILET * self.pas

    def description(self) -> str:
        bouts = [USAGES_SEQUENCE[self.type],
                 f"Poste {nom_poste(self.poste)}" if self.poste else "Poste à choisir"]
        broche = "broche fixe (G97)" if self.vitesse_fixe() else f"maxi {self.vitesse_maxi:g} tr/min"
        avance = f"pas {self.pas:g} mm" if self.type == TypeSequence.FILETAGE \
            else f"avance {self.avance:g} mm/tr"
        bouts.append(f"Vc {self.vitesse_coupe:g} m/min, {broche}, {avance}")
        if self.type in (TypeSequence.FINITION, TypeSequence.FINITION_INTERIEURE):
            bouts.append("Un seul passage, sans surépaisseur")
        elif self.type == TypeSequence.FILETAGE:
            bouts.append(f"Filet de {self.profondeur_filet():g} mm au rayon, passes de "
                         f"{self.profondeur_passe:g} mm à section constante")
        elif self.type in (TypeSequence.GORGE, TypeSequence.TRONCONNAGE):
            bouts.append(f"Outil de {self.largeur_outil:g} mm, plongées de {self.profondeur_passe:g} mm")
        elif self.type == TypeSequence.PERCAGE:
            bouts.append(f"Foret Ø {self.diametre_outil:g}, débourrages de {self.profondeur_passe:g} mm")
        elif self.type == TypeSequence.CENTRAGE:
            bouts.append(f"Foret à centrer Ø {self.diametre_outil:g}")
        elif self.type == TypeSequence.ALESAGE:
            bouts.append(f"Jusqu'au Ø {self.diametre_fond:g}" + (", paroi suivie sur l'esquisse"
                         if self.paroi else "") + f", passes de {self.profondeur_passe:g} mm, "
                         f"surépaisseur {self.surepaisseur:g} mm")
        else:
            bouts.append(f"Passes de {self.profondeur_passe:g} mm, surépaisseur {self.surepaisseur:g} mm")
        bouts.append("Arrosage" if self.arrosage else "Sans arrosage")
        return "\n".join(bouts)


def _depuis_dict(cls, d: Dict[str, Any]):
    noms = {f.name for f in fields(cls)}
    return cls(**{k: v for k, v in (d or {}).items() if k in noms})


@dataclass
class Gamme:
    """La suite des séquences, dans l'ordre d'usinage."""
    sequences: List[Sequence] = field(default_factory=list)
    _prochain_id: int = 1

    def __iter__(self):
        return iter(self.sequences)

    def __len__(self) -> int:
        return len(self.sequences)

    def actives(self) -> List[Sequence]:
        return [s for s in self.sequences if s.active]

    def sequence(self, ident: int) -> Optional[Sequence]:
        return next((s for s in self.sequences if s.id == ident), None)

    def ajouter(self, type_: TypeSequence, **valeurs) -> Sequence:
        """Ajoute une séquence en fin de gamme, avec les réglages habituels de son type."""
        type_ = TypeSequence(type_)
        reglages = dict(DEFAUTS_SEQUENCE.get(type_, {}))
        reglages.update(valeurs)
        s = Sequence(id=self._prochain_id, type=type_, **reglages)
        self._prochain_id += 1
        self.sequences.append(s)
        return s

    def supprimer(self, ident: int) -> bool:
        avant = len(self.sequences)
        self.sequences = [s for s in self.sequences if s.id != ident]
        return len(self.sequences) != avant

    def deplacer(self, ident: int, pas: int) -> bool:
        """Monte ou descend une séquence dans l'ordre d'usinage. Vrai si elle a bougé."""
        rangs = [s.id for s in self.sequences]
        if ident not in rangs:
            return False
        i = rangs.index(ident)
        j = min(max(i + pas, 0), len(self.sequences) - 1)
        if i == j:
            return False
        self.sequences.insert(j, self.sequences.pop(i))
        return True

    def remplir_type(self) -> "Gamme":
        """Pose la gamme type : les dix lignes de l'enchaînement habituel, dans l'ordre, à la suite."""
        for type_, nom, active, reglages in GAMME_TYPE:
            s = self.ajouter(type_, nom=nom, **reglages)
            s.active = active
        return self

    def deplacer_a(self, ident: int, rang: int) -> bool:
        """Pose la séquence au rang donné, compté avant le retrait. Vrai si elle a bougé."""
        rangs = [s.id for s in self.sequences]
        if ident not in rangs:
            return False
        i = rangs.index(ident)
        rang = min(max(int(rang), 0), len(self.sequences))
        if rang in (i, i + 1):
            return False                     # lâchée là où elle était déjà
        s = self.sequences.pop(i)
        self.sequences.insert(rang - 1 if rang > i else rang, s)
        return True

    def to_dict(self) -> dict:
        return {"prochain_id": self._prochain_id,
                "sequences": [{**asdict(s), "type": s.type.value} for s in self.sequences]}

    @classmethod
    def from_dict(cls, d: Optional[Dict[str, Any]]) -> "Gamme":
        d = d or {}
        gamme = cls()
        for q in d.get("sequences", []) or []:
            q = dict(q)
            q["type"] = TypeSequence(q.get("type", TypeSequence.EBAUCHE.value))
            gamme.sequences.append(_depuis_dict(Sequence, q))
        ids: Iterable[int] = [s.id for s in gamme.sequences]
        gamme._prochain_id = max([int(d.get("prochain_id", 1))] + [i + 1 for i in ids])
        return gamme
