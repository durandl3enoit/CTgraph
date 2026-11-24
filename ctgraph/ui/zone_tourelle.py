"""Volet « Tourelle » : la tourelle du tour vue de face, douze postes VDI 30.

Le disque est dessiné à l'échelle de la zone, chaque logement numéroté. Cliquer un poste le met en
travail ; la flèche extérieure le désigne.
"""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPalette, QPen
from PySide6.QtWidgets import QLabel, QSizePolicy, QVBoxLayout, QWidget

from ..tourelle import NORME, Tourelle


class VueTourelle(QWidget):
    """Le dessin seul : disque, logements numérotés, poste en travail désigné par une flèche."""

    poste_choisi = Signal(int)

    def __init__(self, tourelle: Tourelle, parent=None):
        super().__init__(parent)
        self.tourelle = tourelle
        self.setMinimumSize(180, 180)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    # -- repère : millimètres de la tourelle vers pixels de la zone ------------------------------

    def _echelle(self) -> float:
        marge = 26.0      # place pour les numéros extérieurs et la flèche
        cote = min(self.width(), self.height()) - 2 * marge
        return max(cote, 40.0) / max(self.tourelle.diametre, 1.0)

    def _en_pixels(self, x: float, y: float) -> QPointF:
        k = self._echelle()
        return QPointF(self.width() / 2.0 + x * k, self.height() / 2.0 - y * k)

    def _en_mm(self, px: float, py: float):
        k = self._echelle()
        return ((px - self.width() / 2.0) / k, (self.height() / 2.0 - py) / k)

    # -- dessin -----------------------------------------------------------------------------------

    def paintEvent(self, event) -> None:
        t = self.tourelle
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        pal = self.palette()
        encre = pal.color(QPalette.ColorGroup.Active, QPalette.ColorRole.WindowText)
        fond = pal.color(QPalette.ColorGroup.Active, QPalette.ColorRole.Base)
        choix = QColor(255, 140, 0)                       # même orange que la sélection de l'esquisse
        muet = QColor(encre.red(), encre.green(), encre.blue(), 110)
        k = self._echelle()

        p.fillRect(self.rect(), fond)

        # corps de la tourelle
        centre = self._en_pixels(0.0, 0.0)
        rayon = t.diametre / 2.0 * k
        p.setPen(QPen(encre, 1.6))
        p.setBrush(QBrush(QColor(encre.red(), encre.green(), encre.blue(), 26)))
        p.drawEllipse(centre, rayon, rayon)
        # cercle d'implantation, en trait mixte discret
        mixte = QPen(muet, 1.0, Qt.PenStyle.DashDotLine)
        p.setPen(mixte)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(centre, t.rayon_implantation * k, t.rayon_implantation * k)
        # axe de broche au centre
        p.setPen(QPen(muet, 1.0))
        p.drawLine(QPointF(centre.x() - 8, centre.y()), QPointF(centre.x() + 8, centre.y()))
        p.drawLine(QPointF(centre.x(), centre.y() - 8), QPointF(centre.x(), centre.y() + 8))

        police = QFont()
        police.setPointSizeF(8.5)
        p.setFont(police)
        r_logement = t.diametre_queue / 2.0 * k

        for poste in t.postes():
            x, y = t.position_poste(poste)
            c = self._en_pixels(x, y)
            actif = poste == t.poste_en_travail
            p.setPen(QPen(choix if actif else encre, 2.0 if actif else 1.3))
            p.setBrush(QBrush(QColor(choix.red(), choix.green(), choix.blue(), 60) if actif else fond))
            p.drawEllipse(c, r_logement, r_logement)
            # le méplat denté du VDI, côté extérieur : ce qui tient le porte-outil en rotation
            p.setPen(QPen(choix if actif else muet, 1.2))
            dehors = QPointF(x, y)
            norme = max((dehors.x() ** 2 + dehors.y() ** 2) ** 0.5, 1e-6)
            ux, uy = dehors.x() / norme, dehors.y() / norme
            a = self._en_pixels(x + ux * t.diametre_queue * 0.32 - uy * t.diametre_queue * 0.34,
                                y + uy * t.diametre_queue * 0.32 + ux * t.diametre_queue * 0.34)
            b = self._en_pixels(x + ux * t.diametre_queue * 0.32 + uy * t.diametre_queue * 0.34,
                                y + uy * t.diametre_queue * 0.32 - ux * t.diametre_queue * 0.34)
            p.drawLine(a, b)
            # numéro, posé juste en dehors du logement
            etiquette = self._en_pixels(x * 1.0 + ux * (t.diametre_queue * 0.5 + 9.0 / k),
                                        y * 1.0 + uy * (t.diametre_queue * 0.5 + 9.0 / k))
            p.setPen(QPen(choix if actif else encre))
            p.drawText(QRectF(etiquette.x() - 14, etiquette.y() - 9, 28, 18),
                       int(Qt.AlignmentFlag.AlignCenter), str(poste))

        # flèche extérieure vers le poste en travail
        x, y = t.position_poste(t.poste_en_travail)
        norme = max((x * x + y * y) ** 0.5, 1e-6)
        ux, uy = x / norme, y / norme
        pointe = self._en_pixels(x + ux * (t.diametre_queue * 0.5 + 2.0), y + uy * (t.diametre_queue * 0.5 + 2.0))
        talon = self._en_pixels(x + ux * (t.diametre_queue * 0.5 + 20.0 / k * t.diametre / 320.0 + 10.0),
                                y + uy * (t.diametre_queue * 0.5 + 20.0 / k * t.diametre / 320.0 + 10.0))
        p.setPen(QPen(choix, 1.8))
        p.drawLine(talon, pointe)
        p.setBrush(QBrush(choix))
        p.setPen(Qt.PenStyle.NoPen)
        dx, dy = pointe.x() - talon.x(), pointe.y() - talon.y()
        n = max((dx * dx + dy * dy) ** 0.5, 1e-6)
        dx, dy = dx / n, dy / n
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
    """Le volet : le dessin de la tourelle et la ligne qui dit ce qu'on regarde."""

    poste_choisi = Signal(int)

    def __init__(self, tourelle: Tourelle = None, parent=None):
        super().__init__(parent)
        self.tourelle = tourelle if tourelle is not None else Tourelle()
        self.setMinimumWidth(190)
        v = QVBoxLayout(self)
        v.setContentsMargins(6, 6, 6, 6)
        v.setSpacing(5)
        entete = QLabel(f"{NORME} : {self.tourelle.nb_postes} postes, queue Ø {self.tourelle.diametre_queue:g} mm. "
                        "Cliquez un poste pour le mettre en travail.")
        entete.setWordWrap(True)
        v.addWidget(entete)
        self.vue = VueTourelle(self.tourelle, self)
        self.vue.poste_choisi.connect(self._poste_choisi)
        v.addWidget(self.vue, 1)
        self.lbl_poste = QLabel("")
        self.lbl_poste.setWordWrap(True)
        v.addWidget(self.lbl_poste)
        self._rafraichir()

    def _rafraichir(self) -> None:
        self.lbl_poste.setText(f"Poste en travail : {self.tourelle.poste_en_travail}. "
                               "Diamètre du disque et rayon d'implantation à relever sur le CT200.")

    def _poste_choisi(self, poste: int) -> None:
        self._rafraichir()
        self.poste_choisi.emit(poste)

    def definir_poste(self, poste: int) -> None:
        self.tourelle.definir_poste(poste)
        self.vue.update()
        self._rafraichir()
