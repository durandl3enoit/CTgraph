"""Zone « Stock d'outils » : les porte-plaquettes montables sur les porte-outils VDI 30 du CT200.

Panneau ancré à droite de l'esquisse. Il liste le catalogue de `ctgraph.outils`, rangé par famille, avec
un filtre et une case « en stock » par référence : le catalogue dit ce qui est montable, les cases disent
ce que l'atelier possède (mémorisé dans les préférences).
"""
from __future__ import annotations

from typing import Dict, Iterable, List, Set

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import (QCheckBox, QDockWidget, QHBoxLayout, QLabel, QLineEdit, QTreeWidget,
                               QTreeWidgetItem, QVBoxLayout, QWidget)

from ..icons import icone_plaquette
from ..outils import CATALOGUE, FAMILLES, FORMES_PLAQUETTE, QUEUE_MAXI, PortePlaquette, filtrer

COLONNES = ["Désignation", "Plaquette", "Attaque", "Queue", "Fixation"]
ROLE_DESIGNATION = Qt.ItemDataRole.UserRole


class ZoneOutils(QDockWidget):
    """Le catalogue des porte-plaquettes, filtrable, avec les cases « en stock »."""

    stock_change = Signal(object)        # l'ensemble des désignations cochées

    def __init__(self, parent=None):
        super().__init__("Stock d'outils", parent)
        self.setObjectName("zone_outils")
        self.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)
        self._stock: Set[str] = set()
        self._blocage = False
        # une icône par forme de plaquette, dessinée une fois : le filtre reconstruit la liste à chaque frappe
        pal = self.palette()
        encre = pal.color(QPalette.ColorGroup.Active, QPalette.ColorRole.Text)
        fond = pal.color(QPalette.ColorGroup.Active, QPalette.ColorRole.Base)
        self._icones = {forme: icone_plaquette(forme, encre, fond) for forme in FORMES_PLAQUETTE}

        contenu = QWidget(self)
        v = QVBoxLayout(contenu)
        v.setContentsMargins(6, 6, 6, 6)
        v.setSpacing(5)

        entete = QLabel(f"Porte-plaquettes montables sur porte-outils VDI 30 : queue de {QUEUE_MAXI:g} mm au plus. "
                        "Cochez ce que l'atelier possède.")
        entete.setWordWrap(True)
        v.addWidget(entete)

        ligne = QHBoxLayout()
        self.filtre = QLineEdit()
        self.filtre.setPlaceholderText("Filtrer : désignation, plaquette, usage…")
        self.filtre.setClearButtonEnabled(True)
        self.filtre.textChanged.connect(self._remplir)
        ligne.addWidget(self.filtre, 1)
        self.case_stock = QCheckBox("En stock")
        self.case_stock.setToolTip("N'afficher que les références cochées")
        self.case_stock.toggled.connect(self._remplir)
        ligne.addWidget(self.case_stock)
        v.addLayout(ligne)

        self.arbre = QTreeWidget()
        self.arbre.setColumnCount(len(COLONNES))
        self.arbre.setHeaderLabels(COLONNES)
        self.arbre.setRootIsDecorated(True)
        self.arbre.setIndentation(12)
        self.arbre.setUniformRowHeights(True)
        self.arbre.setAlternatingRowColors(True)
        self.arbre.setIconSize(QSize(18, 18))
        self.arbre.itemChanged.connect(self._case_changee)
        v.addWidget(self.arbre, 1)

        self.lbl_total = QLabel("")
        self.lbl_total.setWordWrap(True)
        v.addWidget(self.lbl_total)

        self.setWidget(contenu)
        self._remplir()

    # -- stock ---------------------------------------------------------------------------

    def stock(self) -> Set[str]:
        return set(self._stock)

    def definir_stock(self, designations: Iterable[str]) -> None:
        """Coche les références possédées (désignations inconnues ignorées : catalogue remanié)."""
        connues = {pp.designation for pp in CATALOGUE}
        self._stock = {str(d) for d in designations if str(d) in connues}
        self._remplir()

    # -- affichage -----------------------------------------------------------------------

    def _visibles(self) -> List[PortePlaquette]:
        liste = filtrer(self.filtre.text())
        if self.case_stock.isChecked():
            liste = [pp for pp in liste if pp.designation in self._stock]
        return liste

    def _remplir(self) -> None:
        self._blocage = True
        self.arbre.clear()
        groupes: Dict[str, List[PortePlaquette]] = {cle: [] for cle in FAMILLES}
        for pp in self._visibles():
            groupes[pp.famille].append(pp)
        for cle, libelle in FAMILLES.items():
            lot = groupes[cle]
            if not lot:
                continue
            parent = QTreeWidgetItem(self.arbre, [f"{libelle}  ({len(lot)})"])
            parent.setFirstColumnSpanned(True)
            parent.setFlags(Qt.ItemFlag.ItemIsEnabled)
            police = parent.font(0)
            police.setBold(True)
            parent.setFont(0, police)
            parent.setExpanded(True)
            for pp in lot:
                it = QTreeWidgetItem(parent, [pp.designation, pp.plaquette, pp.texte_attaque, pp.queue,
                                              pp.fixation])
                it.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
                            | Qt.ItemFlag.ItemIsUserCheckable)
                it.setCheckState(0, Qt.CheckState.Checked if pp.designation in self._stock
                                 else Qt.CheckState.Unchecked)
                it.setData(0, ROLE_DESIGNATION, pp.designation)
                if pp.forme in self._icones:
                    it.setIcon(1, self._icones[pp.forme])     # la forme, juste avant la désignation
                infobulle = pp.description()
                for col in range(len(COLONNES)):
                    it.setToolTip(col, infobulle)
        self._blocage = False
        for col in range(len(COLONNES)):
            self.arbre.resizeColumnToContents(col)
        total, montres = len(CATALOGUE), sum(len(lot) for lot in groupes.values())
        self.lbl_total.setText(f"{montres} référence(s) affichée(s) sur {total} — {len(self._stock)} en stock")

    def _case_changee(self, item: QTreeWidgetItem, colonne: int) -> None:
        if self._blocage or colonne != 0:
            return
        designation = item.data(0, ROLE_DESIGNATION)
        if not designation:
            return
        if item.checkState(0) == Qt.CheckState.Checked:
            self._stock.add(designation)
        else:
            self._stock.discard(designation)
        total = len(CATALOGUE)
        montres = sum(self.arbre.topLevelItem(i).childCount() for i in range(self.arbre.topLevelItemCount()))
        self.lbl_total.setText(f"{montres} référence(s) affichée(s) sur {total} — {len(self._stock)} en stock")
        self.stock_change.emit(self.stock())
