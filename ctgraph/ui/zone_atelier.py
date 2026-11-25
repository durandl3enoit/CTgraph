"""Zone « Atelier » : des volets repliables latéralement, côte à côte à droite de l'esquisse.

De gauche à droite : l'**usinage** (la gamme de la pièce), la **tourelle** du tour vue de face, le **stock
d'outils** (porte-plaquettes montables en VDI 30) et les **plaquettes** qui les garnissent. Chaque volet se
replie sur son bandeau vertical : on déplie celui dont on a besoin, les autres rendent la place au dessin.
"""
from __future__ import annotations

from typing import Dict

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDockWidget, QHBoxLayout, QWidget

from .volet_lateral import VoletLateral
from .zone_outils import ZoneOutils
from .zone_plaquettes import ZonePlaquettes
from .zone_tourelle import ZoneTourelle
from .zone_usinage import ZoneUsinage


class ZoneAtelier(QDockWidget):
    """Le conteneur des volets. Pas de barre de titre : les bandeaux des volets en tiennent lieu."""

    def __init__(self, parent=None):
        super().__init__("Atelier", parent)
        self.setObjectName("zone_atelier")
        self.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)
        self.setFeatures(QDockWidget.DockWidgetFeature.NoDockWidgetFeatures)
        self.setTitleBarWidget(QWidget(self))     # les bandeaux verticaux remplacent la barre de titre

        self.usinage = ZoneUsinage()
        self.tourelle = ZoneTourelle()
        self.outils = ZoneOutils()
        self.plaquettes = ZonePlaquettes()

        self.volets: Dict[str, VoletLateral] = {
            "usinage": VoletLateral("Usinage", self.usinage, False, bandeau_a_gauche=True),
            "tourelle": VoletLateral("Tourelle", self.tourelle, False, bandeau_a_gauche=True),
            "outils": VoletLateral("Stock d'outils", self.outils, True, bandeau_a_gauche=True),
            "plaquettes": VoletLateral("Plaquettes", self.plaquettes, False, bandeau_a_gauche=False),
        }

        contenu = QWidget(self)
        h = QHBoxLayout(contenu)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)
        for volet in self.volets.values():
            h.addWidget(volet, 1)
        # quand les trois volets sont repliés, la place qui reste va ici : les bandeaux restent collés
        h.addStretch(0)
        self.setWidget(contenu)

    def largeur_souhaitee(self) -> int:
        """Largeur qui laisse voir les volets dépliés sans écraser les autres."""
        return sum(v.minimumWidth() if v.est_deploye() else v.maximumWidth() for v in self.volets.values()) + 8
