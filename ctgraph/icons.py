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


def _dessin_selection(encre: QColor, fond: QColor) -> Callable[[QPainter], None]:
    """Flèche pleine."""
    def dessin(p: QPainter):
        p.setPen(_stylo(encre, 1.2))
        p.setBrush(QBrush(encre))
        pts = [(6, 3), (6, 19.5), (10.3, 15.6), (13.2, 21.5), (16, 20.2), (13.2, 14.6), (18.8, 14.4)]
        p.drawPolygon(QPolygonF([QPointF(*pt) for pt in pts]))
    return dessin


def _dessin_ligne(encre: QColor, fond: QColor) -> Callable[[QPainter], None]:
    """Un épaulement : trois segments."""
    def dessin(p: QPainter):
        p.setPen(_stylo(encre, TRAIT))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPolyline(QPolygonF([QPointF(3.5, 17), QPointF(11.5, 17), QPointF(11.5, 7), QPointF(20.5, 7)]))
    return dessin


def _dessin_arc(encre: QColor, fond: QColor) -> Callable[[QPainter], None]:
    """Un demi-cercle."""
    def dessin(p: QPainter):
        p.setPen(_stylo(encre, TRAIT))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawArc(QRectF(4, 6, 16, 16), 0, 180 * 16)
    return dessin


def _dessin_cote(encre: QColor, fond: QColor) -> Callable[[QPainter], None]:
    """Une ligne de cote fléchée aux deux bouts."""
    def dessin(p: QPainter):
        p.setPen(_stylo(encre, 2.0))
        p.drawLine(QPointF(3.5, 12), QPointF(20.5, 12))
        p.drawPolyline(QPolygonF([QPointF(8, 8), QPointF(3.5, 12), QPointF(8, 16)]))
        p.drawPolyline(QPolygonF([QPointF(16, 8), QPointF(20.5, 12), QPointF(16, 16)]))
    return dessin


def _dessin_arrondi(encre: QColor, fond: QColor) -> Callable[[QPainter], None]:
    """Un coin dont l'angle est remplacé par un congé."""
    def dessin(p: QPainter):
        p.setPen(_stylo(encre, TRAIT))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawLine(QPointF(4, 20), QPointF(4, 11))
        p.drawArc(QRectF(4, 4, 14, 14), 90 * 16, 90 * 16)
        p.drawLine(QPointF(11, 4), QPointF(20, 4))
    return dessin


def _dessin_chanfrein(encre: QColor, fond: QColor) -> Callable[[QPainter], None]:
    """Un coin dont l'angle est abattu."""
    def dessin(p: QPainter):
        p.setPen(_stylo(encre, TRAIT))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPolyline(QPolygonF([QPointF(4, 20), QPointF(4, 11), QPointF(11, 4), QPointF(20, 4)]))
    return dessin


def _dessin_elaguer(encre: QColor, fond: QColor) -> Callable[[QPainter], None]:
    """Une ligne barrée d'un trait rouge."""
    def dessin(p: QPainter):
        p.setPen(_stylo(encre, TRAIT))
        p.drawLine(QPointF(3.5, 13), QPointF(20.5, 13))
        p.setPen(_stylo(ROUGE, TRAIT))
        p.drawLine(QPointF(15, 4), QPointF(9, 21))
    return dessin


def _dessins_actions(encre: QColor, fond: QColor):
    def supprimer(p: QPainter):
        p.setPen(_stylo(encre, TRAIT))
        p.drawLine(QPointF(6, 6), QPointF(18, 18))
        p.drawLine(QPointF(6, 18), QPointF(18, 6))

    def deselectionner(p: QPainter):
        p.setPen(_stylo(encre, 1.4, [2.0, 2.0]))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(QRectF(4, 4, 16, 16))
        p.setPen(_stylo(encre, 1.8))
        p.drawLine(QPointF(9, 9), QPointF(15, 15))
        p.drawLine(QPointF(9, 15), QPointF(15, 9))

    def tout_voir(p: QPainter):
        p.setPen(_stylo(encre, 1.8))
        p.setBrush(Qt.BrushStyle.NoBrush)
        for sx, sy in ((1, 1), (-1, 1), (1, -1), (-1, -1)):
            cx, cy = 12 - sx * 8, 12 - sy * 8
            p.drawLine(QPointF(12 - sx * 2.5, 12 - sy * 2.5), QPointF(cx, cy))
            p.drawPolyline(QPolygonF([QPointF(cx + sx * 4, cy), QPointF(cx, cy), QPointF(cx, cy + sy * 4)]))

    def pilotee(p: QPainter):
        p.setPen(_stylo(QColor(encre.red(), encre.green(), encre.blue(), 150), 1.6))
        p.drawLine(QPointF(3.5, 12), QPointF(20.5, 12))
        p.drawPolyline(QPolygonF([QPointF(8, 8), QPointF(3.5, 12), QPointF(8, 16)]))
        p.drawPolyline(QPolygonF([QPointF(16, 8), QPointF(20.5, 12), QPointF(16, 16)]))
        p.setPen(QPen(encre, 1))
        p.setFont(_police(10))
        p.drawText(QRectF(0, 0, 24, 9), Qt.AlignmentFlag.AlignCenter, "( )")

    return {"supprimer": supprimer, "deselectionner": deselectionner, "tout_voir": tout_voir, "pilotee": pilotee}


def icone_action(nom: str, encre: QColor, fond: QColor) -> QIcon:
    """Icône d'une action de menu : supprimer, deselectionner, tout_voir, pilotee."""
    return _fabriquer(_dessins_actions(encre, fond)[nom])


_CURSEURS: dict = {}


def curseur_outil(nom: str, encre: QColor, fond: QColor):
    """Curseur propre à un outil : une petite croix au point chaud, le symbole de l'outil en bas à droite.

    La sélection garde la flèche habituelle. Dessiné net en HiDPI (facteur 2), mis en cache.
    """
    from PySide6.QtGui import QCursor
    if nom == "selection":
        return QCursor(Qt.CursorShape.ArrowCursor)
    cle = (nom, encre.rgb(), fond.rgb())
    if cle in _CURSEURS:
        return _CURSEURS[cle]
    taille, facteur = 32, 2
    pm = QPixmap(taille * facteur, taille * facteur)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing)
    p.scale(facteur, facteur)
    # croix au point chaud (8, 8), avec un halo de la couleur du fond pour rester visible partout
    for couleur, largeur in ((fond, 3.2), (encre, 1.4)):
        p.setPen(_stylo(couleur, largeur))
        p.drawLine(QPointF(1, 8), QPointF(15, 8))
        p.drawLine(QPointF(8, 1), QPointF(8, 15))
    # symbole de l'outil, réduit, en bas à droite
    p.save()
    p.translate(13, 13)
    p.scale(0.75, 0.75)
    ICONES_OUTILS[nom](encre, fond)(p)
    p.restore()
    p.end()
    pm.setDevicePixelRatio(facteur)
    cur = QCursor(pm, 8, 8)
    _CURSEURS[cle] = cur
    return cur


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

    def origine_z(p):
        p.setPen(_stylo(encre, 1.6, [1.0, 2.0]))
        p.drawLine(QPointF(12, 2), QPointF(12, 22))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(encre))
        p.drawEllipse(QPointF(12, 12), 3, 3)

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

    def sur_reference(p):
        # un plan du montage (trait mixte, comme les traits du montage) et le point qui s'y pose
        p.setPen(_stylo(encre, 1.6, [4.0, 2.0, 1.0, 2.0]))
        p.drawLine(QPointF(8, 2), QPointF(8, 22))
        p.setPen(_stylo(encre, R))
        p.drawLine(QPointF(8, 12), QPointF(16, 12))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(encre))
        p.drawEllipse(QPointF(17, 12), 3, 3)

    return {
        "horizontal": horizontal, "vertical": vertical, "coincident": coincident, "point_sur_ligne": point_sur_ligne,
        "point_sur_arc": point_sur_ligne, "parallele": parallele, "perpendiculaire": perpendiculaire,
        "tangent": tangent, "egal": egal, "sur_axe": sur_axe, "origine_z": origine_z, "fixe": fixe,
        "sur_reference": sur_reference,
    }


def icone_relation(nom: str, encre: QColor, fond: QColor) -> QIcon:
    """Petite icône d'une relation (clé = valeur de `TypeRelation`), dans la couleur de texte du thème."""
    return _fabriquer(_dessins_relations(encre, fond)[nom])


ICONES_OUTILS = {
    "selection": _dessin_selection,
    "ligne": _dessin_ligne,
    "arc": _dessin_arc,
    "cote": _dessin_cote,
    "arrondi": _dessin_arrondi,
    "chanfrein": _dessin_chanfrein,
    "elaguer": _dessin_elaguer,
}


def icone_outil(nom: str, encre: QColor, fond: QColor) -> QIcon:
    """Icône d'un outil d'esquisse, dans la couleur de texte du thème (lisible en clair comme en sombre)."""
    return _fabriquer(ICONES_OUTILS[nom](encre, fond))


def app_pixmap(size: int = 256) -> QPixmap:
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    s = size / 256.0

    # fond : la zone de dessin, sombre, avec sa grille
    coin = QPainterPath()
    coin.addRoundedRect(QRectF(0, 0, size, size), 44 * s, 44 * s)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(QColor(34, 36, 40)))
    p.drawPath(coin)
    p.setClipPath(coin)
    grille = QPen(QColor(255, 255, 255, 38), max(1.0, 2 * s))
    p.setPen(grille)
    pas = 32 * s
    for i in range(1, 8):
        p.drawLine(QPointF(i * pas, 0), QPointF(i * pas, size))
        p.drawLine(QPointF(0, i * pas), QPointF(size, i * pas))

    # axe de la pièce (tiret-point) et face d'origine (pointillés)
    axe = QPen(QColor(255, 255, 255, 150), 5 * s)
    axe.setStyle(Qt.PenStyle.DashDotLine)
    axe.setCapStyle(Qt.PenCapStyle.FlatCap)
    p.setPen(axe)
    p.drawLine(QPointF(0, 192 * s), QPointF(size, 192 * s))
    origine = QPen(QColor(255, 255, 255, 90), 3 * s, Qt.PenStyle.DotLine)
    p.setPen(origine)
    p.drawLine(QPointF(208 * s, 0), QPointF(208 * s, size))

    # demi-profil entièrement contraint, en vert, avec son remplissage discret
    path = QPainterPath()
    path.moveTo(208 * s, 192 * s)
    path.lineTo(208 * s, 128 * s)
    path.lineTo(128 * s, 128 * s)
    path.lineTo(128 * s, 64 * s)
    path.lineTo(44 * s, 64 * s)
    path.lineTo(44 * s, 192 * s)
    path.closeSubpath()
    p.setBrush(QBrush(QColor(46, 160, 67, 60)))
    p.setPen(QPen(QColor(70, 200, 95), 9 * s, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    p.drawPath(path)

    # sommets : points d'esquisse
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(QColor(255, 255, 255)))
    for z, x in ((208, 128), (128, 128), (128, 64), (44, 64)):
        p.drawEllipse(QPointF(z * s, x * s), 10 * s, 10 * s)
    p.end()
    return pm


def app_icon() -> QIcon:
    icon = QIcon()
    for n in (16, 24, 32, 48, 64, 128, 256):
        icon.addPixmap(app_pixmap(n))
    return icon
