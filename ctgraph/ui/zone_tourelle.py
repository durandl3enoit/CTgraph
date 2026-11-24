"""Volet « Tourelle » : la tourelle vue de face, ce qui est monté sur chaque poste, et les corrections.

Trois parties : le disque dessiné, la liste des douze postes, et le formulaire du poste choisi. On y monte
un porte-plaquette et sa plaquette, et on y note le correcteur à appliquer sur la commande numérique.
"""
from __future__ import annotations

import math
from typing import List, Optional

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPalette, QPen
from PySide6.QtWidgets import (QComboBox, QDoubleSpinBox, QFormLayout, QGroupBox, QHBoxLayout, QLabel,
                               QPushButton, QSizePolicy, QSpinBox, QTreeWidget, QTreeWidgetItem,
                               QVBoxLayout, QWidget)

from ..outils import CATALOGUE as OUTILS
from ..plaquettes import CATALOGUE as PLAQUETTES
from ..tourelle import IMPLANTATIONS, NORME, ORIENTATIONS, Tourelle

COLONNES = ["Poste", "Type", "Porte-plaquette", "Plaquette", "Correcteur"]


class VueTourelle(QWidget):
    """Le disque : logements numérotés, postes garnis marqués, poste en travail désigné par une flèche."""

    poste_choisi = Signal(int)

    def __init__(self, tourelle: Tourelle, parent=None):
        super().__init__(parent)
        self.tourelle = tourelle
        self.setMinimumSize(200, 200)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def _echelle(self) -> float:
        marge = 24.0
        cote = min(self.width(), self.height()) - 2 * marge
        return max(cote, 40.0) / max(self.tourelle.diametre, 1.0)

    def _en_pixels(self, x: float, y: float) -> QPointF:
        k = self._echelle()
        return QPointF(self.width() / 2.0 + x * k, self.height() / 2.0 - y * k)

    def _en_mm(self, px: float, py: float):
        k = self._echelle()
        return ((px - self.width() / 2.0) / k, (self.height() / 2.0 - py) / k)

    def paintEvent(self, event) -> None:
        t = self.tourelle
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        pal = self.palette()
        encre = pal.color(QPalette.ColorGroup.Active, QPalette.ColorRole.WindowText)
        fond = pal.color(QPalette.ColorGroup.Active, QPalette.ColorRole.Base)
        choix = QColor(255, 140, 0)
        garni = QColor(46, 160, 67)
        muet = QColor(encre.red(), encre.green(), encre.blue(), 110)
        k = self._echelle()
        p.fillRect(self.rect(), fond)

        centre = self._en_pixels(0.0, 0.0)
        rayon = t.diametre / 2.0 * k
        p.setPen(QPen(encre, 1.6))
        p.setBrush(QBrush(QColor(encre.red(), encre.green(), encre.blue(), 26)))
        p.drawEllipse(centre, rayon, rayon)
        p.setPen(QPen(muet, 1.0, Qt.PenStyle.DashDotLine))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(centre, t.rayon_implantation * k, t.rayon_implantation * k)
        p.setPen(QPen(muet, 1.0))
        p.drawLine(QPointF(centre.x() - 8, centre.y()), QPointF(centre.x() + 8, centre.y()))
        p.drawLine(QPointF(centre.x(), centre.y() - 8), QPointF(centre.x(), centre.y() + 8))

        police = QFont()
        police.setPointSizeF(8.0)
        p.setFont(police)
        r_logement = max(t.diametre_queue / 2.0 * k, 5.0)

        for numero in t.postes():
            poste = t.poste(numero)
            x, y = t.position_poste(numero)
            c = self._en_pixels(x, y)
            actif = numero == t.poste_en_travail
            couleur = choix if actif else (garni if poste.est_garni() else encre)
            norme = max(math.hypot(x, y), 1e-6)
            ux, uy = x / norme, y / norme
            # l'outil : un trait transversal en périphérie, une flèche vers l'axe pour un outil axial
            p.setPen(QPen(couleur, 2.0 if poste.est_garni() else 1.2))
            if poste.implantation == "transversal":
                a = self._en_pixels(x + ux * t.diametre_queue * 0.75 - uy * t.diametre_queue * 0.55,
                                    y + uy * t.diametre_queue * 0.75 + ux * t.diametre_queue * 0.55)
                b = self._en_pixels(x + ux * t.diametre_queue * 0.75 + uy * t.diametre_queue * 0.55,
                                    y + uy * t.diametre_queue * 0.75 - ux * t.diametre_queue * 0.55)
                p.drawLine(a, b)
            else:
                bout = self._en_pixels(x + ux * t.diametre_queue * 1.0, y + uy * t.diametre_queue * 1.0)
                p.drawLine(c, bout)
            p.setPen(QPen(couleur, 2.0 if actif else 1.3))
            p.setBrush(QBrush(QColor(couleur.red(), couleur.green(), couleur.blue(), 70)
                              if poste.est_garni() else fond))
            p.drawEllipse(c, r_logement, r_logement)
            etiquette = self._en_pixels(x - ux * (t.diametre_queue * 0.5 + 11.0 / k),
                                        y - uy * (t.diametre_queue * 0.5 + 11.0 / k))
            p.setPen(QPen(couleur))
            p.drawText(QRectF(etiquette.x() - 13, etiquette.y() - 8, 26, 16),
                       int(Qt.AlignmentFlag.AlignCenter), str(numero))

        # flèche extérieure vers le poste en travail
        x, y = t.position_poste(t.poste_en_travail)
        norme = max(math.hypot(x, y), 1e-6)
        ux, uy = x / norme, y / norme
        pointe = self._en_pixels(x + ux * (t.diametre_queue * 1.4), y + uy * (t.diametre_queue * 1.4))
        talon = self._en_pixels(x + ux * (t.diametre / 2.0 - t.rayon_implantation + t.diametre_queue * 2.6),
                                y + uy * (t.diametre / 2.0 - t.rayon_implantation + t.diametre_queue * 2.6))
        p.setPen(QPen(choix, 1.8))
        p.setBrush(QBrush(choix))
        p.drawLine(talon, pointe)
        dx, dy = pointe.x() - talon.x(), pointe.y() - talon.y()
        n = max(math.hypot(dx, dy), 1e-6)
        dx, dy = dx / n, dy / n
        p.setPen(Qt.PenStyle.NoPen)
        p.drawPolygon([pointe, QPointF(pointe.x() - dx * 8 - dy * 4, pointe.y() - dy * 8 + dx * 4),
                       QPointF(pointe.x() - dx * 8 + dy * 4, pointe.y() - dy * 8 - dx * 4)])
        p.end()

    def mousePressEvent(self, event) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        pos = event.position()
        poste = self.tourelle.poste_le_plus_proche(*self._en_mm(pos.x(), pos.y()))
        if poste != self.tourelle.poste_en_travail:
            self.tourelle.definir_poste(poste)
            self.update()
        self.poste_choisi.emit(poste)


class ZoneTourelle(QWidget):
    """Le volet : le disque, la liste des postes et le formulaire du poste choisi."""

    poste_choisi = Signal(int)
    tourelle_changee = Signal(object)        # la tourelle entière, à mémoriser

    def __init__(self, tourelle: Optional[Tourelle] = None, parent=None):
        super().__init__(parent)
        self.tourelle = tourelle if tourelle is not None else Tourelle()
        self.setMinimumWidth(350)
        self._blocage = False

        v = QVBoxLayout(self)
        v.setContentsMargins(6, 6, 6, 6)
        v.setSpacing(5)
        entete = QLabel(f"{NORME} : {self.tourelle.nb_postes} postes, queue Ø {self.tourelle.diametre_queue:g} mm. "
                        "La moitié des outils sont montés transversalement en périphérie, l'autre travaille "
                        "dans l'axe. Cliquez un poste.")
        entete.setWordWrap(True)
        v.addWidget(entete)

        self.vue = VueTourelle(self.tourelle, self)
        self.vue.poste_choisi.connect(self._poste_choisi)
        v.addWidget(self.vue, 1)

        self.liste = QTreeWidget()
        self.liste.setColumnCount(len(COLONNES))
        self.liste.setHeaderLabels(COLONNES)
        self.liste.setRootIsDecorated(False)
        self.liste.setUniformRowHeights(True)
        self.liste.setAlternatingRowColors(True)
        self.liste.setMinimumHeight(150)
        self.liste.currentItemChanged.connect(self._ligne_choisie)
        v.addWidget(self.liste)

        self.groupe = QGroupBox("Poste 1")
        f = QFormLayout(self.groupe)
        f.setContentsMargins(8, 6, 8, 6)
        f.setSpacing(4)
        self.implantation = QComboBox()
        for cle, libelle in IMPLANTATIONS.items():
            self.implantation.addItem(libelle.split(" — ")[0], cle)
        self.implantation.setToolTip("\n".join(IMPLANTATIONS.values()))
        self.implantation.currentIndexChanged.connect(self._implantation_changee)
        self.porte_plaquette = QComboBox()
        self.porte_plaquette.currentIndexChanged.connect(self._montage_change)
        self.plaquette = QComboBox()
        self.plaquette.currentIndexChanged.connect(self._montage_change)
        self.correcteur = QSpinBox()
        self.correcteur.setRange(0, 99)
        self.correcteur.setPrefix("D ")
        self.correcteur.setSpecialValueText("non attribué")
        self.corr_x = self._nombre(" mm")
        self.corr_z = self._nombre(" mm")
        self.corr_r = self._nombre(" mm", 0.0, 25.0)
        self.orientation = QComboBox()
        for code, libelle in ORIENTATIONS.items():
            self.orientation.addItem(libelle, code)
        self.orientation.setToolTip("Code d'orientation du nez d'outil.\n"
                                    "Convention à confirmer dans le manuel NUM 750 T.")
        for widget in (self.correcteur, self.corr_x, self.corr_z, self.corr_r):
            widget.valueChanged.connect(self._correcteur_change)
        self.orientation.currentIndexChanged.connect(self._correcteur_change)
        f.addRow("Implantation", self.implantation)
        f.addRow("Porte-plaquette", self.porte_plaquette)
        f.addRow("Plaquette", self.plaquette)
        f.addRow("Correcteur", self.correcteur)
        f.addRow("Correction X", self.corr_x)
        f.addRow("Correction Z", self.corr_z)
        f.addRow("Rayon de bec", self.corr_r)
        f.addRow("Orientation", self.orientation)
        ligne = QHBoxLayout()
        self.btn_vider = QPushButton("Vider le poste")
        self.btn_vider.clicked.connect(self._vider)
        ligne.addStretch(1)
        ligne.addWidget(self.btn_vider)
        f.addRow(ligne)
        v.addWidget(self.groupe)

        self.lbl_etat = QLabel("")
        self.lbl_etat.setWordWrap(True)
        v.addWidget(self.lbl_etat)
        self.rafraichir()

    @staticmethod
    def _nombre(suffixe: str, mini: float = -999.0, maxi: float = 999.0) -> QDoubleSpinBox:
        s = QDoubleSpinBox()
        s.setRange(mini, maxi)
        s.setDecimals(3)
        s.setSuffix(suffixe)
        return s

    # -- remplissage ----------------------------------------------------------------------

    def _outils_compatibles(self, implantation: str) -> List[str]:
        """Les porte-plaquettes que le poste peut recevoir : queue carrée en transversal, cylindrique en axial."""
        cylindrique = implantation == "axial"
        return [pp.designation for pp in OUTILS if pp.queue.startswith("Ø") == cylindrique]

    def rafraichir(self) -> None:
        """Redessine le disque, remplit la liste et le formulaire depuis la tourelle."""
        self._blocage = True
        t = self.tourelle
        self.liste.clear()
        for numero in t.postes():
            poste = t.poste(numero)
            it = QTreeWidgetItem(self.liste, [str(numero), poste.texte_implantation(),
                                              poste.porte_plaquette or "—", poste.plaquette or "—",
                                              poste.correcteur.texte()])
            it.setData(0, Qt.ItemDataRole.UserRole, numero)
            it.setToolTip(0, f"Poste {numero} : {poste.libelle()}\n{IMPLANTATIONS[poste.implantation]}")
            if numero == t.poste_en_travail:
                police = it.font(0)
                police.setBold(True)
                for col in range(len(COLONNES)):
                    it.setFont(col, police)
                self.liste.setCurrentItem(it)
        for col in range(len(COLONNES)):
            self.liste.resizeColumnToContents(col)
        self._remplir_formulaire()
        self._blocage = False
        self.vue.update()
        garnis = len(t.garnis())
        self.lbl_etat.setText(f"{garnis} poste(s) garni(s) sur {t.nb_postes}. Poste en travail : "
                              f"{t.poste_en_travail}. Diamètre du disque et rayon d'implantation à relever.")

    def _remplir_formulaire(self) -> None:
        avant, self._blocage = self._blocage, True
        t = self.tourelle
        poste = t.poste(t.poste_en_travail)
        self.groupe.setTitle(f"Poste {poste.numero} — {poste.libelle()}")
        self.implantation.setCurrentIndex(max(0, self.implantation.findData(poste.implantation)))
        for combo, courant, choix in ((self.porte_plaquette, poste.porte_plaquette,
                                       self._outils_compatibles(poste.implantation)),
                                      (self.plaquette, poste.plaquette,
                                       [pl.designation for pl in PLAQUETTES])):
            combo.clear()
            combo.addItem("—", "")
            for designation in choix:
                combo.addItem(designation, designation)
            if courant and combo.findData(courant) < 0:
                combo.addItem(courant + "  (hors catalogue)", courant)
            combo.setCurrentIndex(max(0, combo.findData(courant)))
        c = poste.correcteur
        self.correcteur.setValue(c.numero)
        self.corr_x.setValue(c.x)
        self.corr_z.setValue(c.z)
        self.corr_r.setValue(c.rayon_bec)
        self.orientation.setCurrentIndex(max(0, self.orientation.findData(c.orientation)))
        self._blocage = avant

    # -- interactions ---------------------------------------------------------------------

    def _poste_choisi(self, numero: int) -> None:
        self.tourelle.definir_poste(numero)
        self.rafraichir()
        self.poste_choisi.emit(numero)

    def _ligne_choisie(self, item: Optional[QTreeWidgetItem], _precedent=None) -> None:
        if self._blocage or item is None:
            return
        numero = item.data(0, Qt.ItemDataRole.UserRole)
        if numero and numero != self.tourelle.poste_en_travail:
            self._poste_choisi(int(numero))

    def _implantation_changee(self) -> None:
        if self._blocage:
            return
        self.tourelle.definir_implantation(self.tourelle.poste_en_travail, self.implantation.currentData())
        self._enregistrer()

    def _montage_change(self) -> None:
        if self._blocage:
            return
        poste = self.tourelle.poste(self.tourelle.poste_en_travail)
        self.tourelle.garnir(poste.numero, self.porte_plaquette.currentData() or "",
                             self.plaquette.currentData() or "")
        # le rayon de bec suit la plaquette montée, tant qu'il n'a pas été corrigé à la main
        pl = next((q for q in PLAQUETTES if q.designation == poste.plaquette), None)
        if pl is not None and not poste.correcteur.rayon_bec:
            poste.correcteur.rayon_bec = pl.rayon_bec
        self._enregistrer()

    def _correcteur_change(self) -> None:
        if self._blocage:
            return
        c = self.tourelle.poste(self.tourelle.poste_en_travail).correcteur
        c.numero = self.correcteur.value()
        c.x, c.z, c.rayon_bec = self.corr_x.value(), self.corr_z.value(), self.corr_r.value()
        c.orientation = int(self.orientation.currentData() or 0)
        self._enregistrer(redessiner=False)

    def _vider(self) -> None:
        self.tourelle.vider(self.tourelle.poste_en_travail)
        self._enregistrer()

    def _enregistrer(self, redessiner: bool = True) -> None:
        if redessiner:
            self.rafraichir()
        else:
            self._rafraichir_ligne()
        self.tourelle_changee.emit(self.tourelle)

    def _rafraichir_ligne(self) -> None:
        """Met à jour la seule ligne du poste courant : évite de reconstruire la liste à chaque chiffre tapé."""
        t = self.tourelle
        poste = t.poste(t.poste_en_travail)
        for i in range(self.liste.topLevelItemCount()):
            it = self.liste.topLevelItem(i)
            if it.data(0, Qt.ItemDataRole.UserRole) == poste.numero:
                it.setText(4, poste.correcteur.texte())
                return

    def definir_poste(self, poste: int) -> None:
        self.tourelle.definir_poste(poste)
        self.rafraichir()

    def definir_tourelle(self, tourelle: Tourelle) -> None:
        self.tourelle = tourelle
        self.vue.tourelle = tourelle
        self.rafraichir()
