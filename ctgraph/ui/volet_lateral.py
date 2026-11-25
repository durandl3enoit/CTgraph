"""Volet repliable latéralement : un bandeau vertical cliquable, le contenu replié sur le côté.

Sert aux trois volets de l'atelier (tourelle, stock d'outils, plaquettes), rangés côte à côte : on déplie
celui dont on a besoin, les autres se réduisent à leur bandeau et rendent la place au dessin.
"""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QPainter, QPalette, QPen, QPolygonF
from PySide6.QtWidgets import QHBoxLayout, QSizePolicy, QWidget

LARGEUR_BANDEAU = 32
# hauteur commune des dessins cotés au bas des volets catalogue : les deux zones s'alignent
HAUTEUR_DESSIN = 190
_SANS_LIMITE = 16777215


class _Bandeau(QWidget):
    """Le bandeau vertical : un chevron en haut, puis le titre tourné, lu de haut en bas.

    Même présentation pour les trois volets, quel que soit le côté : le chevron pointe vers la droite
    quand le volet est replié, vers la gauche quand il est déployé.
    """

    clique = Signal()

    def __init__(self, titre: str, volet: "VoletLateral"):
        super().__init__(volet)
        self.titre = titre
        self.volet = volet
        self.setFixedWidth(LARGEUR_BANDEAU)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        self._majuscules = titre.upper()

    def minimumSizeHint(self) -> QSize:
        return QSize(LARGEUR_BANDEAU, self.fontMetrics().horizontalAdvance(self._majuscules) + 48)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        pal = self.palette()
        encre = pal.color(QPalette.ColorGroup.Active, QPalette.ColorRole.ButtonText)
        p.fillRect(self.rect(), pal.color(QPalette.ColorGroup.Active, QPalette.ColorRole.Button))
        p.setPen(QPen(QColor(encre.red(), encre.green(), encre.blue(), 60), 1))
        p.drawLine(self.width() - 1, 0, self.width() - 1, self.height())

        # chevron : vers la droite quand le volet est replié, vers la gauche quand il est déployé
        sens = -1.0 if self.volet.est_deploye() else 1.0
        cx, cy = self.width() / 2.0, 14.0
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(encre))
        p.drawPolygon(QPolygonF([QPointF(cx - 3.5 * sens, cy - 5.0), QPointF(cx + 3.5 * sens, cy),
                                 QPointF(cx - 3.5 * sens, cy + 5.0)]))

        # titre écrit en haut, lu de haut en bas
        p.save()
        p.translate(self.width() / 2.0, 28.0)
        p.rotate(90.0)
        p.setPen(QPen(encre))
        p.drawText(QRectF(0.0, -8.0, max(self.height() - 36.0, 10.0), 16.0),
                   int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), self._majuscules)
        p.restore()
        p.end()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clique.emit()
            event.accept()


class VoletLateral(QWidget):
    """Un contenu et son bandeau : cliquer le bandeau replie ou déplie le volet.

    `bandeau_a_gauche` place le bandeau du côté extérieur : à gauche pour les volets de gauche, à droite
    pour celui de droite, pour que les bandeaux repliés bordent la fenêtre.
    """

    basculee = Signal(bool)

    def __init__(self, titre: str, contenu: QWidget, deploye: bool = True, bandeau_a_gauche: bool = True,
                 parent=None):
        super().__init__(parent)
        self.titre = titre
        self.contenu = contenu
        self.bandeau_a_gauche = bandeau_a_gauche
        self._deploye = True
        self.bandeau = _Bandeau(titre, self)
        self.bandeau.clique.connect(self.basculer)
        self.bandeau.setToolTip(f"{titre} : replier ou déplier le volet")
        h = QHBoxLayout(self)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)
        if bandeau_a_gauche:
            h.addWidget(self.bandeau)
            h.addWidget(contenu, 1)
        else:
            h.addWidget(contenu, 1)
            h.addWidget(self.bandeau)
        self.definir_deploye(deploye)

    def est_deploye(self) -> bool:
        return self._deploye

    def definir_deploye(self, deploye: bool) -> None:
        self._deploye = bool(deploye)
        self.contenu.setVisible(self._deploye)
        if self._deploye:
            self.setMinimumWidth(LARGEUR_BANDEAU + max(self.contenu.minimumWidth(), 120))
            self.setMaximumWidth(_SANS_LIMITE)
            self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        else:
            self.setMinimumWidth(LARGEUR_BANDEAU)
            self.setMaximumWidth(LARGEUR_BANDEAU)
            self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        self.bandeau.update()

    def basculer(self) -> None:
        self.definir_deploye(not self._deploye)
        self.basculee.emit(self._deploye)
