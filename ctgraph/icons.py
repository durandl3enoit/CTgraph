"""Icône de l'application, dessinée à la volée : un demi-profil d'arbre épaulé sur son axe."""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap


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
