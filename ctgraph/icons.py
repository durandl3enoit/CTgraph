"""Icônes dessinées à la volée (aucun fichier image à distribuer) : application et outils d'esquisse."""
from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (QBrush, QColor, QFont, QFontMetricsF, QIcon, QPainter, QPainterPath, QPen, QPixmap,
                           QPolygonF)

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


TRAIT = 2.4   # épaisseur commune des icônes d'outils : un seul trait, une seule idée par icône


def icone_selection(encre: QColor, fond: QColor) -> QIcon:
    """Flèche pleine."""
    def dessin(p: QPainter):
        p.setPen(_stylo(encre, 1.2))
        p.setBrush(QBrush(encre))
        pts = [(6, 3), (6, 19.5), (10.3, 15.6), (13.2, 21.5), (16, 20.2), (13.2, 14.6), (18.8, 14.4)]
        p.drawPolygon(QPolygonF([QPointF(*pt) for pt in pts]))
    return _fabriquer(dessin)


def icone_ligne(encre: QColor, fond: QColor) -> QIcon:
    """Un profil en escalier, rien d'autre."""
    def dessin(p: QPainter):
        p.setPen(_stylo(encre, TRAIT))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPolyline(QPolygonF([QPointF(3.5, 20), QPointF(3.5, 11), QPointF(13, 11), QPointF(13, 4.5),
                                  QPointF(20.5, 4.5)]))
    return _fabriquer(dessin)


def icone_arc(encre: QColor, fond: QColor) -> QIcon:
    """Un demi-cercle."""
    def dessin(p: QPainter):
        p.setPen(_stylo(encre, TRAIT))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawArc(QRectF(4, 6, 16, 16), 0, 180 * 16)
    return _fabriquer(dessin)


def icone_cote(encre: QColor, fond: QColor) -> QIcon:
    """Une ligne de cote fléchée aux deux bouts."""
    def dessin(p: QPainter):
        p.setPen(_stylo(encre, 2.0))
        p.drawLine(QPointF(3.5, 12), QPointF(20.5, 12))
        p.drawPolyline(QPolygonF([QPointF(8, 8), QPointF(3.5, 12), QPointF(8, 16)]))
        p.drawPolyline(QPolygonF([QPointF(16, 8), QPointF(20.5, 12), QPointF(16, 16)]))
    return _fabriquer(dessin)


def icone_elaguer(encre: QColor, fond: QColor) -> QIcon:
    """Une ligne barrée d'un trait rouge."""
    def dessin(p: QPainter):
        p.setPen(_stylo(encre, TRAIT))
        p.drawLine(QPointF(3.5, 13), QPointF(20.5, 13))
        p.setPen(_stylo(ROUGE, TRAIT))
        p.drawLine(QPointF(15, 4), QPointF(9, 21))
    return _fabriquer(dessin)


def _police(px: int) -> QFont:
    f = QFont()
    f.setPixelSize(px)
    f.setBold(True)
    return f


def _lettre_centree(p: QPainter, lettre: str, encre: QColor, px: int = 11) -> QRectF:
    """Écrit une lettre centrée sur son encre au milieu du canevas 24 × 24 ; renvoie l'encre occupée."""
    p.setFont(_police(px))
    fm = QFontMetricsF(p.font())
    encre_r = fm.tightBoundingRect(lettre)
    origine = QPointF(12 - (encre_r.x() + encre_r.width() / 2), 12 - (encre_r.y() + encre_r.height() / 2))
    p.setPen(QPen(encre, 1))
    p.drawText(origine, lettre)
    return encre_r.translated(origine)


def _dessins_relations(encre: QColor, fond: QColor):
    R = 2.0

    def horizontal(p):
        r = _lettre_centree(p, "z", encre)
        p.setPen(_stylo(encre, R))
        p.drawLine(QPointF(2.5, 12), QPointF(r.left() - 2, 12))
        p.drawLine(QPointF(r.right() + 2, 12), QPointF(21.5, 12))

    def vertical(p):
        r = _lettre_centree(p, "x", encre)
        p.setPen(_stylo(encre, R))
        p.drawLine(QPointF(12, 2.5), QPointF(12, r.top() - 2))
        p.drawLine(QPointF(12, r.bottom() + 2), QPointF(12, 21.5))

    def coincident(p):
        p.setPen(_stylo(encre, 1.8))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QPointF(12, 12), 7, 7)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(encre))
        p.drawEllipse(QPointF(12, 12), 3, 3)

    def point_sur_ligne(p):
        p.setPen(_stylo(encre, R))
        p.drawLine(QPointF(3, 17), QPointF(21, 7))
        p.setPen(_stylo(encre, 1.2))
        p.setBrush(QBrush(fond))
        p.drawEllipse(QPointF(12, 12), 3.2, 3.2)

    def parallele(p):
        p.setPen(_stylo(encre, R))
        p.drawLine(QPointF(5, 20), QPointF(13, 4))
        p.drawLine(QPointF(11, 20), QPointF(19, 4))

    def perpendiculaire(p):
        p.setPen(_stylo(encre, R))
        p.drawLine(QPointF(5, 19), QPointF(20, 19))
        p.drawLine(QPointF(8, 20), QPointF(8, 4))
        p.setPen(_stylo(encre, 1.2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(QRectF(8, 14, 5, 5))

    def tangent(p):
        p.setPen(_stylo(encre, R))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QPointF(12, 14), 6, 6)
        p.drawLine(QPointF(3, 8), QPointF(21, 8))

    def egal(p):
        p.setPen(_stylo(encre, R))
        p.drawLine(QPointF(5, 9), QPointF(19, 9))
        p.drawLine(QPointF(5, 15), QPointF(19, 15))

    def sur_axe(p):
        p.setPen(_stylo(encre, 1.6, [4.0, 2.0, 1.0, 2.0]))
        p.drawLine(QPointF(2, 16), QPointF(22, 16))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(encre))
        p.drawEllipse(QPointF(12, 16), 3, 3)

    def fixe(p):
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(encre))
        p.drawEllipse(QPointF(12, 8), 3, 3)
        p.setPen(_stylo(encre, R))
        p.drawLine(QPointF(12, 10), QPointF(12, 16))
        p.drawLine(QPointF(5, 16), QPointF(19, 16))
        p.setPen(_stylo(encre, 1.3))
        for x in (6, 10, 14, 18):
            p.drawLine(QPointF(x, 16.5), QPointF(x - 2.5, 20.5))

    return {
        "horizontal": horizontal, "vertical": vertical, "coincident": coincident, "point_sur_ligne": point_sur_ligne,
        "point_sur_arc": point_sur_ligne, "parallele": parallele, "perpendiculaire": perpendiculaire,
        "tangent": tangent, "egal": egal, "sur_axe": sur_axe, "fixe": fixe,
    }


def icone_relation(nom: str, encre: QColor, fond: QColor) -> QIcon:
    """Petite icône d'une relation (clé = valeur de `TypeRelation`), dans la couleur de texte du thème."""
    return _fabriquer(_dessins_relations(encre, fond)[nom])


ICONES_OUTILS = {
    "selection": icone_selection,
    "ligne": icone_ligne,
    "arc": icone_arc,
    "cote": icone_cote,
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
