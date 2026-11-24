"""Tourelle du tour : une tourelle à douze postes VDI 30 (DIN 69880).

Vue de face, la tourelle est un disque percé de `nb_postes` logements répartis régulièrement. Chaque
logement reçoit la queue cylindrique d'un porte-outil VDI : pour la taille 30, un cylindre de Ø 30 mm
denté sur un côté, serré par une crémaillère. C'est cette taille qui borne le catalogue des
porte-plaquettes (`ctgraph.outils`) à une queue de 20 mm.

Repérage retenu : le poste 1 est en haut, la numérotation tourne dans le sens horaire vu de face, et le
poste en travail est celui que l'utilisateur désigne. Le diamètre du disque et le rayon d'implantation
sont des ordres de grandeur, à relever sur le CT200 ; le Ø 30 de la queue, lui, vient de la norme.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Tuple

NORME = "VDI 30 (DIN 69880)"
DIAMETRE_QUEUE = 30.0        # queue cylindrique du porte-outil, fixé par la taille VDI 30


@dataclass
class Tourelle:
    nb_postes: int = 12
    diametre: float = 320.0           # diamètre du disque, à relever
    rayon_implantation: float = 115.0  # du centre à l'axe d'un logement, à relever
    diametre_queue: float = DIAMETRE_QUEUE
    poste_en_travail: int = 1

    def postes(self) -> List[int]:
        return list(range(1, self.nb_postes + 1))

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
                f"Poste en travail : {self.poste_en_travail}.")
