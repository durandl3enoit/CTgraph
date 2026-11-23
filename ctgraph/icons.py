"""Icônes dessinées à la volée (aucun fichier image à distribuer) : application et outils d'esquisse."""
from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap, QPolygonF

ROUGE = QColor(225, 60, 50)
BLEU = QColor(60, 140, 230)


def _stylo(couleur: QColor, largeur: float, tirets=None) -> QPen:
    pen = QPen(couleur, largeur)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    if tirets:
        pen.setDashPattern(tirets)
    return pen


def _fabriquer(dessin: Callable[[QPainter], None]) -> QIcon:
    """Icône sur un canevas logique de 24 × 24, rendue en 24, 48 et 96 px."""
    icon = QIcon()
    for taille in (24, 48, 96):
        pm = QPixmap(taille, taille)
        pm.fill(Qt.GlobalColor.transparent)
        p = QPainter(pm)
        p.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing)
        p.scale(taille / 24, taille / 24)
        dessin(p)
        p.end()
        icon.addPixmap(pm)
    return icon


def _point(p: QPainter, x: float, y: float, encre: QColor, fond: QColor, r: float = 2.0) -> None:
    p.setPen(_stylo(encre, 1.0))
    p.setBrush(QBrush(fond))
    p.drawEllipse(QPointF(x, y), r, r)


def icone_selection(encre: QColor, fond: QColor) -> QIcon:
    """Flèche de sélection."""
    def dessin(p: QPainter):
        p.setPen(_stylo(encre, 1.3))
        p.setBrush(QBrush(fond))
        pts = [(6, 3), (6, 19), (10.2, 15.4), (13, 21.5), (15.8, 20.2), (13.2, 14.4), (18.6, 14)]
        p.drawPolygon(QPolygonF([QPointF(*pt) for pt in pts]))
    return _fabriquer(dessin)


def icone_ligne(encre: QColor, fond: QColor) -> QIcon:
    """Demi-profil en lignes brisées avec ses sommets."""
    def dessin(p: QPainter):
        p.setPen(_stylo(encre, 2.0))
        p.setBrush(Qt.BrushStyle.NoBrush)
        pts = [QPointF(3, 20), QPointF(3, 11), QPointF(12, 11), QPointF(12, 5), QPointF(21, 5)]
        p.drawPolyline(QPolygonF(pts))
        for q in pts[1:-1]:
            _point(p, q.x(), q.y(), encre, fond)
        _point(p, 21, 5, encre, BLEU, 2.3)
    return _fabriquer(dessin)


def icone_arc(encre: QColor, fond: QColor) -> QIcon:
    """Arc avec ses trois points : départ, arrivée, point de passage."""
    def dessin(p: QPainter):
        p.setPen(_stylo(encre, 2.0))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawArc(QRectF(4, 4, 16, 16), 0, 180 * 16)
        p.setPen(_stylo(QColor(encre.red(), encre.green(), encre.blue(), 110), 1.0, [2.0, 2.0]))
        p.drawLine(QPointF(4, 12), QPointF(20, 12))
        _point(p, 4, 12, encre, fond)
        _point(p, 20, 12, encre, fond)
        _point(p, 12, 4, encre, BLEU, 2.3)
    return _fabriquer(dessin)


def icone_elaguer(encre: QColor, fond: QColor) -> QIcon:
    """Une ligne traversée par le trait rouge : la partie au-delà disparaît (pointillés)."""
    def dessin(p: QPainter):
        p.setPen(_stylo(encre, 2.0))
        p.drawLine(QPointF(3, 15), QPointF(13, 15))
        p.setPen(_stylo(QColor(encre.red(), encre.green(), encre.blue(), 90), 1.6, [1.5, 2.5]))
        p.drawLine(QPointF(13, 15), QPointF(21, 15))
        p.setPen(_stylo(encre, 2.0))
        p.drawLine(QPointF(13, 4), QPointF(13, 21))
        p.setPen(_stylo(ROUGE, 2.2))
        p.drawPolyline(QPolygonF([QPointF(15, 7), QPointF(18, 11), QPointF(16.5, 15), QPointF(20, 20)]))
    return _fabriquer(dessin)


ICONES_OUTILS = {
    "selection": icone_selection,
    "ligne": icone_ligne,
    "arc": icone_arc,
    "elaguer": icone_elaguer,
}


def icone_outil(nom: str, encre: QColor, fond: QColor) -> QIcon:
    """Icône d'un outil d'esquisse, dans la couleur de texte du thème (lisible en clair comme en sombre)."""
    return ICONES_OUTILS[nom](encre, fond)


def app_pixmap(size: int = 256) -> QPixmap:
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    s = size / 256.0

    # fond : carré arrondi bleu acier
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(QColor(38, 70, 110)))
    p.drawRoundedRect(QRectF(0, 0, size, size), 48 * s, 48 * s)

    # axe de la pièce (tiret-point)
    axe = QPen(QColor(255, 255, 255, 140), 5 * s)
    axe.setStyle(Qt.PenStyle.DashDotLine)
    axe.setCapStyle(Qt.PenCapStyle.FlatCap)
    p.setPen(axe)
    p.drawLine(QPointF(20 * s, 196 * s), QPointF(236 * s, 196 * s))

    # demi-profil : face avant, petit diamètre, épaulement, grand diamètre
    path = QPainterPath()
    path.moveTo(200 * s, 196 * s)
    path.lineTo(200 * s, 130 * s)
    path.lineTo(130 * s, 130 * s)
    path.lineTo(130 * s, 70 * s)
    path.lineTo(48 * s, 70 * s)
    path.lineTo(48 * s, 196 * s)
    p.setBrush(QBrush(QColor(255, 196, 64, 200)))
    p.setPen(QPen(QColor(255, 236, 190), 8 * s, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    p.drawPath(path)

    # sommets : points d'esquisse
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(QColor(255, 255, 255)))
    for z, x in ((200, 130), (130, 130), (130, 70), (48, 70)):
        p.drawEllipse(QPointF(z * s, x * s), 10 * s, 10 * s)
    p.end()
    return pm


def app_icon() -> QIcon:
    icon = QIcon()
    for n in (16, 24, 32, 48, 64, 128, 256):
        icon.addPixmap(app_pixmap(n))
    return icon
