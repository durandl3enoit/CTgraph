"""La gamme d'usinage : une suite ordonnée de séquences attachée à la pièce.

Une **séquence** dit quoi faire, avec quel poste de tourelle et dans quelles conditions de coupe. Elle
ne garde aucune copie du dessin : sa trajectoire se recalcule depuis le profil résolu (voir
`ctgraph.usinage.trajectoires`). Changer une cote change donc la trajectoire, et plus tard le G-code.

Trois types pour commencer, ceux que montrent les programmes Go2CAM archivés
(`docs/reference-go2cam-ct200.md`) :

* **dressage** de la face avant, en passes successives de la matière vers l'axe ;
* **ébauche** paraxiale, passes parallèles à Z qui descendent jusqu'au profil augmenté de la
  surépaisseur de finition ;
* **finition**, qui suit le profil fini en un passage.

Les conditions de coupe reprennent ce que la CN attend : vitesse de coupe constante `G96`, limitation
de vitesse de broche `G92`, avance par tour `G95`.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional


class TypeSequence(str, Enum):
    DRESSAGE = "dressage"
    EBAUCHE = "ebauche"
    FINITION = "finition"


LIBELLES_SEQUENCE: Dict[TypeSequence, str] = {
    TypeSequence.DRESSAGE: "Dressage de face",
    TypeSequence.EBAUCHE: "Ébauche de chariotage",
    TypeSequence.FINITION: "Finition de profil",
}

USAGES_SEQUENCE: Dict[TypeSequence, str] = {
    TypeSequence.DRESSAGE: "Dresse la face avant du brut jusqu'à la face finie, en passes successives "
                           "de la matière vers l'axe.",
    TypeSequence.EBAUCHE: "Passes parallèles à l'axe, du diamètre du brut jusqu'au profil augmenté de "
                          "la surépaisseur laissée à la finition.",
    TypeSequence.FINITION: "Suit le profil fini en un passage, correction de rayon de bec à la CN.",
}


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

    # étendue ; None = toute la longueur usinable
    z_debut: Optional[float] = None
    z_fin: Optional[float] = None

    def libelle(self) -> str:
        return self.nom.strip() or LIBELLES_SEQUENCE[self.type]

    def description(self) -> str:
        bouts = [USAGES_SEQUENCE[self.type],
                 f"Poste {self.poste}" if self.poste else "Poste à choisir",
                 f"Vc {self.vitesse_coupe:g} m/min, maxi {self.vitesse_maxi:g} tr/min, "
                 f"avance {self.avance:g} mm/tr"]
        if self.type == TypeSequence.FINITION:
            bouts.append("Un seul passage, sans surépaisseur")
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
        s = Sequence(id=self._prochain_id, type=TypeSequence(type_), **valeurs)
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
