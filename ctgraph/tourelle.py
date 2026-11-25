"""Tourelle du tour : douze postes VDI 30 (DIN 69880), ce qui y est monté et les corrections à appliquer.

Vue de face, la tourelle est un disque percé de `nb_postes` logements répartis régulièrement. Chaque
logement reçoit la queue cylindrique d'un porte-outil VDI : pour la taille 30, un cylindre de Ø 30 mm
denté sur un côté, serré par une crémaillère. C'est cette taille qui borne le catalogue des
porte-plaquettes (`ctgraph.outils`) à une queue de 20 mm.

**Implantation des postes.** Un porte-outil VDI se monte soit sur la circonférence de la tourelle, soit sur
sa face, selon la tourelle de la machine. Sur le CT200, la moitié des outils sont montés transversalement
en périphérie : ce sont les outils de tournage extérieur, à queue carrée, dont l'arête attaque le diamètre.
L'autre moitié travaille dans l'axe : barres d'alésage, forets, outils de filetage intérieur, à queue
cylindrique. D'où les deux implantations ci-dessous, alternées par défaut, modifiables poste par poste :
le détail exact de la tourelle est à relever sur la machine.

**Corrections.** Chaque poste porte un correcteur : son numéro sur la commande numérique, les corrections
de longueur en X et en Z, le rayon de bec et le code d'orientation du nez d'outil. Les valeurs servent à la
fiche de réglage et au post-processeur. La correspondance exacte des codes d'orientation et la façon dont
la correction X se compte (au rayon ou au diamètre) sont à vérifier dans le manuel NUM 750 T : rien n'est
écrit ici de mémoire.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Tuple

NORME = "VDI 30 (DIN 69880)"
DIAMETRE_QUEUE = 30.0        # queue cylindrique du porte-outil, fixé par la taille VDI 30


def nom_poste(numero: int) -> str:
    """Le nom d'un poste de tourelle : « T1 », « T12 ». C'est ainsi qu'il s'écrit partout, et sur la CN."""
    return f"T{int(numero)}"

IMPLANTATIONS: Dict[str, str] = {
    "transversal": "Transversal, en périphérie — outil de tournage extérieur, queue carrée",
    "axial": "Axial — barre d'alésage, foret, outil intérieur, queue cylindrique",
}

# Code d'orientation du nez d'outil : position du centre de bec par rapport à la pointe théorique.
# Convention à confirmer dans le manuel NUM 750 T avant d'écrire le post-processeur.
ORIENTATIONS: Dict[int, str] = {
    0: "0 — pointe confondue avec le centre de bec",
    1: "1 — centre de bec en X− Z−",
    2: "2 — centre de bec en X− Z+",
    3: "3 — centre de bec en X+ Z+",
    4: "4 — centre de bec en X+ Z−",
    5: "5 — centre de bec en Z−",
    6: "6 — centre de bec en X−",
    7: "7 — centre de bec en Z+",
    8: "8 — centre de bec en X+",
}


@dataclass
class Correcteur:
    """Le correcteur d'un poste : ce que la commande numérique applique quand l'outil est appelé."""
    numero: int = 0              # numéro de correcteur sur la CN ; 0 = pas encore attribué
    x: float = 0.0               # correction de longueur suivant X
    z: float = 0.0               # correction de longueur suivant Z
    rayon_bec: float = 0.0       # rayon de bec de la plaquette, pour la correction de rayon
    orientation: int = 0         # code d'orientation du nez d'outil

    def est_renseigne(self) -> bool:
        return bool(self.numero) or any((self.x, self.z, self.rayon_bec, self.orientation))

    def texte(self) -> str:
        if not self.est_renseigne():
            return "—"
        bouts = [f"D{self.numero}"] if self.numero else []
        bouts += [f"X {self.x:g}", f"Z {self.z:g}"]
        if self.rayon_bec:
            bouts.append(f"R {self.rayon_bec:g}")
        if self.orientation:
            bouts.append(f"C{self.orientation}")
        return "  ".join(bouts)


@dataclass
class Poste:
    """Un poste de la tourelle : son implantation, ce qui y est monté, son correcteur."""
    numero: int
    implantation: str = "transversal"
    porte_plaquette: str = ""    # désignation du catalogue `ctgraph.outils`
    plaquette: str = ""          # désignation du catalogue `ctgraph.plaquettes`
    correcteur: Correcteur = field(default_factory=Correcteur)
    commentaire: str = ""

    def nom(self) -> str:
        return nom_poste(self.numero)

    def est_garni(self) -> bool:
        return bool(self.porte_plaquette or self.plaquette)

    def texte_implantation(self) -> str:
        return "transversal" if self.implantation == "transversal" else "axial"

    def libelle(self) -> str:
        """Ce qui est monté, en une ligne : le porte-plaquette et sa plaquette."""
        if not self.est_garni():
            return "libre"
        if self.porte_plaquette and self.plaquette:
            return f"{self.porte_plaquette} + {self.plaquette}"
        return self.porte_plaquette or self.plaquette


def _postes_par_defaut(nb: int) -> List[Poste]:
    """Postes alternés : les impairs transversaux en périphérie, les pairs axiaux. La moitié de chaque."""
    return [Poste(n, "transversal" if n % 2 else "axial") for n in range(1, nb + 1)]


@dataclass
class Tourelle:
    nb_postes: int = 12
    diametre: float = 320.0            # diamètre du disque, à relever
    rayon_implantation: float = 115.0  # du centre à l'axe d'un logement, à relever
    diametre_queue: float = DIAMETRE_QUEUE
    poste_en_travail: int = 1
    postes_garnis: List[Poste] = field(default_factory=lambda: _postes_par_defaut(12))

    def __post_init__(self) -> None:
        self._ajuster_postes()

    def _ajuster_postes(self) -> None:
        """Garde exactement `nb_postes` postes, numérotés de 1 à n, sans perdre ce qui est garni."""
        connus = {p.numero: p for p in self.postes_garnis}
        defaut = _postes_par_defaut(self.nb_postes)
        self.postes_garnis = [connus.get(p.numero, p) for p in defaut]
        for p in self.postes_garnis:
            if p.implantation not in IMPLANTATIONS:
                p.implantation = "transversal"
        if not 1 <= self.poste_en_travail <= self.nb_postes:
            self.poste_en_travail = 1

    # -- postes ---------------------------------------------------------------------------

    def postes(self) -> List[int]:
        return list(range(1, self.nb_postes + 1))

    def poste(self, numero: int) -> Poste:
        if not 1 <= int(numero) <= self.nb_postes:
            raise ValueError(f"poste hors tourelle : {numero}")
        return self.postes_garnis[int(numero) - 1]

    def garnis(self) -> List[Poste]:
        return [p for p in self.postes_garnis if p.est_garni()]

    def garnir(self, numero: int, porte_plaquette: str = "", plaquette: str = "") -> Poste:
        p = self.poste(numero)
        p.porte_plaquette, p.plaquette = porte_plaquette or "", plaquette or ""
        return p

    def vider(self, numero: int) -> Poste:
        p = self.poste(numero)
        p.porte_plaquette = p.plaquette = p.commentaire = ""
        p.correcteur = Correcteur()
        return p

    def definir_implantation(self, numero: int, implantation: str) -> None:
        if implantation not in IMPLANTATIONS:
            raise ValueError(f"implantation inconnue : {implantation}")
        self.poste(numero).implantation = implantation

    def queue_attendue(self, numero: int) -> str:
        """La queue qu'attend le poste : « carrée » en transversal, « cylindrique » en axial."""
        return "carree" if self.poste(numero).implantation == "transversal" else "cylindrique"

    # -- géométrie ------------------------------------------------------------------------

    def angle_poste(self, poste: int) -> float:
        """Angle du poste en degrés, mesuré depuis le haut, dans le sens horaire vu de face."""
        return 360.0 * ((int(poste) - 1) % max(self.nb_postes, 1)) / max(self.nb_postes, 1)

    def position_poste(self, poste: int) -> Tuple[float, float]:
        """Centre du logement, en millimètres, dans un repère de face : x vers la droite, y vers le haut."""
        a = math.radians(self.angle_poste(poste))
        return (self.rayon_implantation * math.sin(a), self.rayon_implantation * math.cos(a))

    def poste_le_plus_proche(self, x: float, y: float) -> int:
        """Le poste dont le logement est le plus près du point donné (repère de face, en millimètres)."""
        return min(self.postes(), key=lambda n: math.hypot(*(a - b for a, b in
                                                             zip(self.position_poste(n), (x, y)))))

    def definir_poste(self, poste: int) -> None:
        if not 1 <= int(poste) <= self.nb_postes:
            raise ValueError(f"poste hors tourelle : {poste}")
        self.poste_en_travail = int(poste)

    def description(self) -> str:
        return (f"Tourelle {NORME}, {self.nb_postes} postes, queue Ø {self.diametre_queue:g} mm. "
                f"Poste en travail : {nom_poste(self.poste_en_travail)}. "
                f"{len(self.garnis())} poste(s) garni(s).")

    # -- sérialisation ---------------------------------------------------------------------

    def to_dict(self) -> dict:
        return {"nb_postes": self.nb_postes, "diametre": self.diametre,
                "rayon_implantation": self.rayon_implantation, "diametre_queue": self.diametre_queue,
                "poste_en_travail": self.poste_en_travail,
                "postes": [asdict(p) for p in self.postes_garnis]}

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Tourelle":
        d = d or {}
        postes = []
        for q in d.get("postes", []) or []:
            corr = q.get("correcteur") or {}
            postes.append(Poste(int(q.get("numero", len(postes) + 1)),
                                str(q.get("implantation", "transversal")),
                                str(q.get("porte_plaquette", "")), str(q.get("plaquette", "")),
                                Correcteur(int(corr.get("numero", 0)), float(corr.get("x", 0.0)),
                                           float(corr.get("z", 0.0)), float(corr.get("rayon_bec", 0.0)),
                                           int(corr.get("orientation", 0))),
                                str(q.get("commentaire", ""))))
        t = cls(int(d.get("nb_postes", 12)), float(d.get("diametre", 320.0)),
                float(d.get("rayon_implantation", 115.0)), float(d.get("diametre_queue", DIAMETRE_QUEUE)),
                int(d.get("poste_en_travail", 1)), postes or _postes_par_defaut(int(d.get("nb_postes", 12))))
        return t
