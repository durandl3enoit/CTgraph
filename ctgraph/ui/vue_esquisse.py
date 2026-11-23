"""Vue d'esquisse : tracé à la souris, aimantation, sélection, glissement des points, cotes, élagage.

Coordonnées de scène = coordonnées du modèle : abscisse z, ordonnée x (rayon). La vue est
retournée verticalement (échelle négative en y) pour que le rayon croisse vers le haut.
Les textes et marqueurs de points ignorent la transformation de la vue : ils gardent leur
taille en pixels et ne sont pas retournés.

La vue ne modifie jamais le modèle elle-même : elle appelle le contrôleur (la fenêtre principale)
qui passe par le solveur et l'annulation.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QFontMetricsF, QPainter, QPainterPath, QPen, QPolygonF, QTransform
from PySide6.QtWidgets import (QApplication, QGraphicsEllipseItem, QGraphicsItem, QGraphicsLineItem,
                               QGraphicsPathItem, QGraphicsScene, QGraphicsView, QLabel, QStyleOptionGraphicsItem,
                               QWidget)

from ..esquisse import geometrie as geo
from ..esquisse.elagage import courbe as courbe_de
from ..esquisse.modele import Cote, Esquisse, Relation, TypeCote, TypeRelation

ROLE_GENRE = 0
ROLE_ID = 1

# Symboles dessinés plutôt qu'écrits : horizontal = « -z- », vertical = « x » coupant une barre verticale.
SYMBOLES: Dict[TypeRelation, str] = {
    TypeRelation.HORIZONTAL: "horizontal",
    TypeRelation.VERTICAL: "vertical",
}
GLYPHES: Dict[TypeRelation, str] = {
    TypeRelation.COINCIDENT: "●",
    TypeRelation.HORIZONTAL: "z",
    TypeRelation.VERTICAL: "x",
    TypeRelation.PARALLELE: "∥",
    TypeRelation.PERPENDICULAIRE: "⊥",
    TypeRelation.TANGENT: "T",
    TypeRelation.EGAL: "=",
    TypeRelation.POINT_SUR_LIGNE: "∙/",
    TypeRelation.POINT_SUR_ARC: "∙(",
    TypeRelation.SUR_AXE: "axe",
    TypeRelation.FIXE: "F",
}

TOLERANCE_PX = 9          # rayon d'accrochage et de sélection, en pixels
ANGLE_AUTO_DEG = 4.0      # en deçà, un trait reçoit la relation horizontal ou vertical, ou s'aligne à 45°
AIMANTS_DEFAUT = {"ortho": True, "diag": True, "objets": True, "axe": True}
LIBELLES_AIMANTS = {"ortho": "Horizontal / vertical", "diag": "45°", "objets": "Objets proches", "axe": "Axe Z"}
OUTILS_RAPIDES = ("selection", "ligne", "arc", "elaguer")      # clic droit maintenu + molette
LIBELLES_OUTILS = {"selection": "Sélection", "ligne": "Ligne", "arc": "Arc 3 points", "elaguer": "Élaguer"}
DELAI_GESTE_MS = 350      # clic semi-long : au-delà, glisser élague au lieu de sélectionner ou de tracer
SEUIL_GESTE_PX = 4        # bouger plus que cela avant le délai annule le geste


@dataclass
class Accroche:
    """Résultat de l'aimantation du curseur : une position, et ce à quoi elle est accrochée."""
    z: float
    x: float
    point: Optional[int] = None            # point existant sous le curseur
    sur_axe: bool = False                  # sur l'axe de la pièce (x = 0)
    courbe: Optional[int] = None           # sur une ligne ou un arc existant
    auto: Optional[TypeRelation] = None    # relation à poser d'office sur le trait en cours (horizontal, vertical)
    guides: List[Tuple[Tuple[float, float], Tuple[float, float]]] = field(default_factory=list)


class Etiquette(QGraphicsItem):
    """Texte à taille fixe en pixels avec un fond : symboles de relations et valeurs de cotes.

    `symbole` = "horizontal" dessine « -z- » (un trait de part et d'autre du z),
    "vertical" dessine un x coupant une barre verticale.
    """

    def __init__(self, texte: str, couleur: QColor, fond: QColor, gras: bool = False, symbole: Optional[str] = None,
                 parent=None):
        super().__init__(parent)
        self.texte = texte
        self.couleur = couleur
        self.fond = fond
        self.symbole = symbole
        self.police = QFont()
        self.police.setPointSizeF(9.0)
        self.police.setBold(gras)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True)
        self.setZValue(20)
        fm = QFontMetricsF(self.police)
        w = fm.horizontalAdvance(texte) + 8
        h = fm.height() + 4
        if symbole == "horizontal":
            w += 16
        elif symbole == "vertical":
            h += 12
        self._rect = QRectF(-w / 2, -h / 2, w, h)

    def boundingRect(self) -> QRectF:
        return self._rect.adjusted(-1, -1, 1, 1)

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget = None) -> None:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(self.couleur, 1))
        painter.setBrush(QBrush(self.fond))
        painter.drawRoundedRect(self._rect, 3, 3)
        painter.setFont(self.police)
        fm = QFontMetricsF(self.police)
        painter.drawText(self._rect, Qt.AlignmentFlag.AlignCenter, self.texte)
        trait = QPen(self.couleur, 1.6)
        trait.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(trait)
        if self.symbole == "horizontal":
            demi = fm.horizontalAdvance(self.texte) / 2 + 2
            painter.drawLine(QPointF(self._rect.left() + 3, 0), QPointF(-demi, 0))
            painter.drawLine(QPointF(demi, 0), QPointF(self._rect.right() - 3, 0))
        elif self.symbole == "vertical":
            demi = fm.capHeight() / 2 + 2
            painter.drawLine(QPointF(0, self._rect.top() + 3), QPointF(0, -demi))
            painter.drawLine(QPointF(0, demi), QPointF(0, self._rect.bottom() - 3))


class VueEsquisse(QGraphicsView):
    coordonnees = Signal(float, float)       # (z, x) sous le curseur
    message = Signal(str)                    # aide contextuelle pour la barre d'état
    selection_changee = Signal()

    OUTILS = ("selection", "ligne", "arc", "elaguer")

    def __init__(self, controleur, parent=None):
        super().__init__(parent)
        self.controleur = controleur
        self.esquisse: Esquisse = controleur.esquisse
        self.resultat = None
        self.selection: List[int] = []
        self.outil = "selection"
        self.grille_visible = True
        self.aimants: Dict[str, bool] = dict(AIMANTS_DEFAUT)
        self.mode_elagage = "croisement"

        self._scene = QGraphicsScene(self)
        self._scene.setSceneRect(-1e5, -1e5, 2e5, 2e5)
        self.setScene(self._scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.NoAnchor)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setTransform(QTransform().scale(4.0, -4.0))
        self.centerOn(-40.0, 20.0)

        # état des outils
        self._debut: Optional[Accroche] = None          # premier point d'une ligne ou d'un arc
        self._arc_fin: Optional[Accroche] = None        # deuxième point d'un arc
        self._trait: List[Tuple[float, float]] = []     # trait d'élagage en cours
        self._apercu: List[QGraphicsItem] = []
        self._glisse_point: Optional[int] = None
        self._glisse_cote: Optional[int] = None
        self._glisse_dernier: Optional[QPointF] = None
        self._glisse_actif = False
        self._pan_dernier = None
        self._items: List[QGraphicsItem] = []

        # clic semi-long + glisser : élagage, quel que soit l'outil
        self._press_pos: Optional[QPoint] = None
        self._geste = False
        self._outil_avant: Optional[str] = None
        self._timer_geste = QTimer(self)
        self._timer_geste.setSingleShot(True)
        self._timer_geste.timeout.connect(self._declencher_geste)

        # clic droit maintenu + molette : changement d'outil, avec le nom affiché sous le curseur
        self._droit_molette = False
        self._bulle: Optional[QLabel] = None
        self._timer_bulle = QTimer(self)
        self._timer_bulle.setSingleShot(True)
        self._timer_bulle.timeout.connect(self._cacher_bulle)

        self.reconstruire()

    # -- repère et échelle -----------------------------------------------------------

    def echelle(self) -> float:
        """Pixels par millimètre."""
        return abs(self.transform().m11())

    def px_en_mm(self, px: float) -> float:
        return px / max(self.echelle(), 1e-9)

    def position_scene(self, pos) -> Tuple[float, float]:
        p = self.mapToScene(pos)
        return p.x(), p.y()

    def definir_esquisse(self, esquisse: Esquisse) -> None:
        self.esquisse = esquisse
        self.selection = [i for i in self.selection if esquisse.genre(i) is not None]
        self.annuler_outil()
        self.reconstruire()

    def definir_resultat(self, resultat) -> None:
        self.resultat = resultat

    def tout_voir(self) -> None:
        e = self.esquisse
        if e.points:
            zs = [p.z for p in e.points.values()]
            xs = [p.x for p in e.points.values()] + [0.0]
            rect = QRectF(min(zs), min(xs), max(max(zs) - min(zs), 1e-3), max(max(xs) - min(xs), 1e-3))
        else:
            rect = QRectF(-120.0, -10.0, 140.0, 70.0)
        marge = 0.15
        rect.adjust(-rect.width() * marge - 5, -rect.height() * marge - 5,
                    rect.width() * marge + 5, rect.height() * marge + 5)
        vp = self.viewport().rect()
        if vp.width() < 10 or vp.height() < 10:
            return
        s = min(vp.width() / rect.width(), vp.height() / rect.height())
        s = max(0.05, min(s, 500.0))
        self.setTransform(QTransform().scale(s, -s))
        self.centerOn(rect.center())
        self.reconstruire()

    def zoomer(self, facteur: float, pos=None) -> None:
        """Zoom en gardant fixe le point de la scène situé sous `pos` (le centre de la vue à défaut)."""
        s = self.echelle() * facteur
        if s < 0.05 or s > 500.0:
            return
        if pos is None:
            pos = self.viewport().rect().center()
        avant = self.mapToScene(pos)
        self.scale(facteur, facteur)
        apres = self.mapToScene(pos)
        self.translate(apres.x() - avant.x(), apres.y() - avant.y())
        self.reconstruire()

    # -- couleurs --------------------------------------------------------------------

    def _couleurs(self) -> Dict[str, QColor]:
        pal = self.palette()
        texte = pal.color(pal.ColorGroup.Active, pal.ColorRole.WindowText)
        fond = pal.color(pal.ColorGroup.Active, pal.ColorRole.Base)
        sombre = fond.lightness() < 128
        return {
            "texte": texte,
            "fond": fond,
            "geometrie": QColor(46, 160, 67) if (self.resultat is not None and self.resultat.entierement_contraint) else texte,
            "selection": QColor(255, 140, 0),
            "survol": pal.color(pal.ColorRole.Highlight),
            "cote": QColor(110, 170, 255) if sombre else QColor(25, 95, 190),
            "relation": QColor(170, 170, 170) if sombre else QColor(100, 100, 100),
            "conflit": QColor(230, 60, 50),
            "redondant": QColor(220, 160, 0),
            "axe": QColor(texte.red(), texte.green(), texte.blue(), 120),
            "grille": QColor(texte.red(), texte.green(), texte.blue(), 28),
            "centre": QColor(texte.red(), texte.green(), texte.blue(), 160),
            "guide": QColor(90, 180, 255, 160) if sombre else QColor(0, 110, 220, 160),
            "elagage": QColor(230, 60, 50),
        }

    # -- fond : grille et axe ----------------------------------------------------------

    def drawBackground(self, painter: QPainter, rect: QRectF) -> None:
        super().drawBackground(painter, rect)
        c = self._couleurs()
        painter.fillRect(rect, c["fond"])
        if self.grille_visible:
            pas = self._pas_grille()
            painter.setPen(QPen(c["grille"], 0))
            z = math.floor(rect.left() / pas) * pas
            while z <= rect.right():
                painter.drawLine(QPointF(z, rect.top()), QPointF(z, rect.bottom()))
                z += pas
            x = math.floor(rect.top() / pas) * pas
            while x <= rect.bottom():
                painter.drawLine(QPointF(rect.left(), x), QPointF(rect.right(), x))
                x += pas
        painter.setPen(QPen(c["axe"], 0, Qt.PenStyle.DashDotLine))
        painter.drawLine(QPointF(rect.left(), 0.0), QPointF(rect.right(), 0.0))
        painter.setPen(QPen(c["axe"], 0, Qt.PenStyle.DotLine))
        painter.drawLine(QPointF(0.0, rect.top()), QPointF(0.0, rect.bottom()))

    def _pas_grille(self) -> float:
        """Pas de grille en mm pour des carreaux d'au moins 28 px."""
        mini = self.px_en_mm(28)
        for pas in (0.1, 0.2, 0.5, 1, 2, 5, 10, 20, 50, 100, 200, 500, 1000):
            if pas >= mini:
                return float(pas)
        return 1000.0

    # -- reconstruction des éléments graphiques -----------------------------------------

    def reconstruire(self) -> None:
        """Redessine tout à partir du modèle (simple et sûr : les esquisses restent petites)."""
        for it in self._items:
            self._scene.removeItem(it)
        self._items = []
        e, c = self.esquisse, self._couleurs()
        conflits = set(self.resultat.conflits) if self.resultat is not None else set()
        redondants = set(self.resultat.redondants) if self.resultat is not None else set()
        sel = set(self.selection)
        couleur_geom = c["geometrie"]

        for li in e.lignes.values():
            a, b = e.points[li.p1], e.points[li.p2]
            it = QGraphicsLineItem(a.z, a.x, b.z, b.x)
            it.setPen(self._stylo(li.id in sel, couleur_geom, c))
            it.setZValue(5)
            self._enregistrer(it, "ligne", li.id)

        for a in e.arcs.values():
            path = QPainterPath()
            pts = self._points_arc(a.id, 48)
            path.moveTo(*pts[0])
            for z, x in pts[1:]:
                path.lineTo(z, x)
            it = QGraphicsPathItem(path)
            it.setPen(self._stylo(a.id in sel, couleur_geom, c))
            it.setZValue(5)
            self._enregistrer(it, "arc", a.id)

        centres = {a.centre for a in e.arcs.values()}
        extremites = set()
        for li in e.lignes.values():
            extremites.update((li.p1, li.p2))
        for a in e.arcs.values():
            extremites.update((a.debut, a.fin))
        for p in e.points.values():
            if p.id in centres and p.id not in extremites:
                it = self._croix(p, c["centre"], p.id in sel, c)
            else:
                r = 4.5 if p.id in sel else 3.5
                it = QGraphicsEllipseItem(-r, -r, 2 * r, 2 * r)
                it.setPos(p.z, p.x)
                it.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True)
                it.setPen(QPen(c["fond"], 1))
                it.setBrush(QBrush(c["selection"] if p.id in sel else couleur_geom))
            it.setZValue(10)
            self._enregistrer(it, "point", p.id)

        occupation: Dict[int, int] = {}
        for r in e.relations.values():
            couleur = c["conflit"] if r.id in conflits else (c["redondant"] if r.id in redondants else c["relation"])
            if r.id in sel:
                couleur = c["selection"]
            for ident, dz, dx in self._ancres_relation(r):
                n = occupation.get(ident, 0)
                occupation[ident] = n + 1
                et = Etiquette(GLYPHES[r.type], couleur, c["fond"], gras=r.id in sel, symbole=SYMBOLES.get(r.type))
                et.setPos(dz, dx)
                et.moveBy(self.px_en_mm(22) * (n % 3), self.px_en_mm(16) * (n // 3))
                self._enregistrer(et, "relation", r.id)

        for co in e.cotes.values():
            couleur = c["conflit"] if co.id in conflits else (c["redondant"] if co.id in redondants else c["cote"])
            if co.id in sel:
                couleur = c["selection"]
            self._dessiner_cote(co, couleur, c)

        self._dessiner_apercu()

    def _enregistrer(self, it: QGraphicsItem, genre: str, ident: int) -> None:
        it.setData(ROLE_GENRE, genre)
        it.setData(ROLE_ID, ident)
        self._scene.addItem(it)
        self._items.append(it)

    def _stylo(self, selectionne: bool, couleur: QColor, c: Dict[str, QColor]) -> QPen:
        pen = QPen(c["selection"] if selectionne else couleur, 3 if selectionne else 2)
        pen.setCosmetic(True)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        return pen

    def _croix(self, p, couleur: QColor, selectionne: bool, c: Dict[str, QColor]) -> QGraphicsPathItem:
        path = QPainterPath()
        path.moveTo(-5, 0)
        path.lineTo(5, 0)
        path.moveTo(0, -5)
        path.lineTo(0, 5)
        it = QGraphicsPathItem(path)
        it.setPos(p.z, p.x)
        it.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True)
        it.setPen(QPen(c["selection"] if selectionne else couleur, 1.5))
        return it

    def _points_arc(self, arc_id: int, n: int) -> List[Tuple[float, float]]:
        e = self.esquisse
        a = e.arcs[arc_id]
        d, f = e.points[a.debut], e.points[a.fin]
        cb = courbe_de(e, arc_id)
        pts = [geo.position(cb, i / n) for i in range(n + 1)]
        pts[0] = (d.z, d.x)
        pts[-1] = (f.z, f.x)
        return pts

    def _milieu(self, ident: int) -> Tuple[float, float]:
        e = self.esquisse
        g = e.genre(ident)
        if g == "point":
            p = e.points[ident]
            return p.z, p.x
        if g == "arc":
            return self._points_arc(ident, 2)[1]
        a, b = (e.points[i] for i in e.extremites(ident))
        return (a.z + b.z) / 2, (a.x + b.x) / 2

    def _ancres_relation(self, r: Relation) -> List[Tuple[int, float, float]]:
        """Où poser le symbole : (élément, z, x) ; un symbole par élément concerné."""
        e = self.esquisse
        decal = self.px_en_mm(14)
        ancres = []
        for ident in r.elements:
            g = e.genre(ident)
            mz, mx = self._milieu(ident)
            if g == "point":
                ancres.append((ident, mz + decal * 0.8, mx + decal * 0.8))
            elif g == "ligne":
                a, b = (e.points[i] for i in e.extremites(ident))
                dz, dx = b.z - a.z, b.x - a.x
                n = math.hypot(dz, dx) or 1.0
                nz, nx = -dx / n, dz / n
                if nx < 0:
                    nz, nx = -nz, -nx
                ancres.append((ident, mz + nz * decal, mx + nx * decal))
            else:
                ancres.append((ident, mz, mx + decal))
            if r.type in (TypeRelation.COINCIDENT, TypeRelation.POINT_SUR_LIGNE, TypeRelation.POINT_SUR_ARC,
                          TypeRelation.TANGENT):
                break
        return ancres

    # -- cotes -------------------------------------------------------------------------

    def decalage_par_defaut(self, type_: TypeCote, elements: Tuple[int, ...]) -> Tuple[float, float]:
        d = self.px_en_mm(34)
        if type_ == TypeCote.LONGUEUR_Z:
            return (0.0, d)
        if type_ == TypeCote.DIAMETRE:
            return (d, 0.0)
        if type_ == TypeCote.DISTANCE:
            return (0.0, d)
        return (d * 0.6, d * 0.6)

    def _fleche(self, path: QPainterPath, pointe: Tuple[float, float], direction: Tuple[float, float]) -> None:
        lg = self.px_en_mm(9)
        dz, dx = direction
        n = math.hypot(dz, dx) or 1.0
        dz, dx = dz / n, dx / n
        pz, px = pointe
        bz, bx = pz - dz * lg, px - dx * lg
        wz, wx = -dx * lg * 0.35, dz * lg * 0.35
        path.moveTo(pz, px)
        path.lineTo(bz + wz, bx + wx)
        path.moveTo(pz, px)
        path.lineTo(bz - wz, bx - wx)

    def _dessiner_cote(self, co: Cote, couleur: QColor, c: Dict[str, QColor]) -> None:
        e = self.esquisse
        path = QPainterPath()
        dz, dx = co.decalage
        texte = e.texte_cote(co)
        ext = self.px_en_mm(4)
        if co.type in (TypeCote.LONGUEUR_Z, TypeCote.DISTANCE):
            if len(co.elements) == 1:
                a, b = (e.points[i] for i in e.extremites(co.elements[0]))
            else:
                a, b = (e.points[i] for i in co.elements)
            if co.type == TypeCote.LONGUEUR_Z:
                xl = max(a.x, b.x) + dx
                path.moveTo(a.z, a.x)
                path.lineTo(a.z, xl + math.copysign(ext, dx or 1.0))
                path.moveTo(b.z, b.x)
                path.lineTo(b.z, xl + math.copysign(ext, dx or 1.0))
                path.moveTo(a.z, xl)
                path.lineTo(b.z, xl)
                self._fleche(path, (a.z, xl), (a.z - b.z, 0.0))
                self._fleche(path, (b.z, xl), (b.z - a.z, 0.0))
                pos = ((a.z + b.z) / 2 + dz, xl)
            else:
                vz, vx = b.z - a.z, b.x - a.x
                n = math.hypot(vz, vx) or 1.0
                nz, nx = -vx / n, vz / n
                if nx < 0:
                    nz, nx = -nz, -nx
                az, ax = a.z + nz * dx, a.x + nx * dx
                bz, bx = b.z + nz * dx, b.x + nx * dx
                path.moveTo(a.z, a.x)
                path.lineTo(az + nz * ext, ax + nx * ext)
                path.moveTo(b.z, b.x)
                path.lineTo(bz + nz * ext, bx + nx * ext)
                path.moveTo(az, ax)
                path.lineTo(bz, bx)
                self._fleche(path, (az, ax), (-vz, -vx))
                self._fleche(path, (bz, bx), (vz, vx))
                pos = ((az + bz) / 2, (ax + bx) / 2)
        elif co.type == TypeCote.DIAMETRE:
            el = co.elements[0]
            p = e.points[el] if e.genre(el) == "point" else e.points[e.lignes[el].p1]
            zl = p.z + dz
            path.moveTo(p.z, p.x)
            path.lineTo(zl + math.copysign(ext, dz or 1.0), p.x)
            path.moveTo(zl, 0.0)
            path.lineTo(zl, p.x)
            self._fleche(path, (zl, p.x), (0.0, 1.0))
            path.moveTo(zl - ext, 0.0)
            path.lineTo(zl + ext, 0.0)
            pos = (zl, p.x / 2 + dx)
        elif co.type == TypeCote.RAYON:
            a = e.arcs[co.elements[0]]
            ce = e.points[a.centre]
            mz, mx = self._points_arc(a.id, 2)[1]
            path.moveTo(ce.z, ce.x)
            path.lineTo(mz, mx)
            self._fleche(path, (mz, mx), (mz - ce.z, mx - ce.x))
            pos = (mz + dz, mx + dx)
        else:  # angle
            if len(co.elements) == 1:
                mz, mx = self._milieu(co.elements[0])
            else:
                l1, l2 = (e.lignes[i] for i in co.elements)
                commun = {l1.p1, l1.p2} & {l2.p1, l2.p2}
                if commun:
                    p = e.points[commun.pop()]
                    mz, mx = p.z, p.x
                else:
                    m1, m2 = self._milieu(l1.id), self._milieu(l2.id)
                    mz, mx = (m1[0] + m2[0]) / 2, (m1[1] + m2[1]) / 2
            path.moveTo(mz, mx)
            path.lineTo(mz + dz, mx + dx)
            pos = (mz + dz, mx + dx)
        it = QGraphicsPathItem(path)
        pen = QPen(couleur, 1)
        pen.setCosmetic(True)
        it.setPen(pen)
        it.setZValue(3)
        self._enregistrer(it, "cote", co.id)
        et = Etiquette(texte, couleur, c["fond"], gras=True)
        et.setPos(*pos)
        self._enregistrer(et, "cote", co.id)

    # -- aperçu pendant le tracé ---------------------------------------------------------

    def _ajouter_apercu(self, it: QGraphicsItem, z: int = 4) -> None:
        it.setZValue(z)
        self._scene.addItem(it)
        self._apercu.append(it)

    def _dessiner_apercu(self, curseur: Optional[Accroche] = None) -> None:
        for it in self._apercu:
            self._scene.removeItem(it)
        self._apercu = []
        c = self._couleurs()
        if self._trait:
            poly = QPolygonF([QPointF(z, x) for z, x in self._trait])
            path = QPainterPath()
            path.addPolygon(poly)
            it = QGraphicsPathItem(path)
            pen = QPen(c["elagage"], 2)
            pen.setCosmetic(True)
            it.setPen(pen)
            self._ajouter_apercu(it, 25)
        if curseur is None:
            return
        pen = QPen(c["survol"], 1, Qt.PenStyle.DashLine)
        pen.setCosmetic(True)
        guide = QPen(c["guide"], 1, Qt.PenStyle.DotLine)
        guide.setCosmetic(True)
        for (a, b) in curseur.guides:
            it = QGraphicsLineItem(a[0], a[1], b[0], b[1])
            it.setPen(guide)
            self._ajouter_apercu(it)
        if self.outil == "ligne" and self._debut is not None:
            it = QGraphicsLineItem(self._debut.z, self._debut.x, curseur.z, curseur.x)
            it.setPen(pen)
            self._ajouter_apercu(it)
        elif self.outil == "arc" and self._debut is not None:
            if self._arc_fin is None:
                it = QGraphicsLineItem(self._debut.z, self._debut.x, curseur.z, curseur.x)
                it.setPen(pen)
                self._ajouter_apercu(it)
            else:
                arc = self._arc_par_trois_points((self._debut.z, self._debut.x), (self._arc_fin.z, self._arc_fin.x),
                                                 (curseur.z, curseur.x))
                if arc is not None:
                    (cz, cx), horaire = arc
                    cb = geo.arc((cz, cx), (self._debut.z, self._debut.x), (self._arc_fin.z, self._arc_fin.x), horaire)
                    path = QPainterPath()
                    pts = [geo.position(cb, i / 48) for i in range(49)]
                    path.moveTo(*pts[0])
                    for z, x in pts[1:]:
                        path.lineTo(z, x)
                    it = QGraphicsPathItem(path)
                    it.setPen(pen)
                    self._ajouter_apercu(it)
        if self.outil in ("ligne", "arc"):
            taille = 6
            path = QPainterPath()
            if curseur.point is not None:
                path.addEllipse(-taille, -taille, 2 * taille, 2 * taille)
            elif curseur.courbe is not None:
                path.moveTo(-taille, -taille)
                path.lineTo(taille, taille)
                path.moveTo(-taille, taille)
                path.lineTo(taille, -taille)
            elif curseur.sur_axe:
                path.moveTo(-taille, 0)
                path.lineTo(taille, 0)
                path.moveTo(0, -taille)
                path.lineTo(0, taille)
            else:
                path.addRect(-taille + 1, -taille + 1, 2 * taille - 2, 2 * taille - 2)
            it = QGraphicsPathItem(path)
            it.setPos(curseur.z, curseur.x)
            it.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True)
            it.setPen(QPen(c["survol"], 1.5))
            self._ajouter_apercu(it, 30)

    @staticmethod
    def _arc_par_trois_points(a, b, m):
        """Centre et sens d'un arc allant de a à b en passant par m. None si les points sont alignés."""
        ax, ay = a
        bx, by = b
        mx, my = m
        d = 2 * (ax * (by - my) + bx * (my - ay) + mx * (ay - by))
        if abs(d) < 1e-9:
            return None
        ux = ((ax * ax + ay * ay) * (by - my) + (bx * bx + by * by) * (my - ay) + (mx * mx + my * my) * (ay - by)) / d
        uy = ((ax * ax + ay * ay) * (mx - bx) + (bx * bx + by * by) * (ax - mx) + (mx * mx + my * my) * (bx - ax)) / d
        aa = math.atan2(ay - uy, ax - ux)
        ab = math.atan2(by - uy, bx - ux)
        am = math.atan2(my - uy, mx - ux)
        balayage_b = (ab - aa) % (2 * math.pi)
        balayage_m = (am - aa) % (2 * math.pi)
        horaire = balayage_m > balayage_b
        return (ux, uy), horaire

    # -- aimantation et sélection ---------------------------------------------------------

    def accrocher(self, pos, depuis: Optional[Accroche] = None) -> Accroche:
        """Position du curseur aimantée selon les réglages : objets proches, axe, alignements,
        puis horizontal / vertical / 45° par rapport au point de départ `depuis`."""
        z, x = self.position_scene(pos)
        tol = self.px_en_mm(TOLERANCE_PX)
        e = self.esquisse
        acc = Accroche(z, x)

        if self.aimants["objets"]:
            meilleur, dist = None, tol
            for p in e.points.values():
                d = math.hypot(p.z - z, p.x - x)
                if d <= dist:
                    meilleur, dist = p, d
            if meilleur is not None:
                acc = Accroche(meilleur.z, meilleur.x, meilleur.id, abs(meilleur.x) < 1e-9)
            else:
                proche, dist = None, tol
                for ident in list(e.lignes) + list(e.arcs):
                    d, _, q = geo.plus_proche(courbe_de(e, ident), (z, x))
                    if d <= dist:
                        proche, dist = (ident, q), d
                if proche is not None:
                    acc = Accroche(proche[1][0], proche[1][1], None, abs(proche[1][1]) < 1e-9, proche[0])

        if acc.point is None and acc.courbe is None:
            if self.aimants["axe"] and abs(acc.x) <= tol:
                acc.x = 0.0
            if self.aimants["objets"]:
                for p in e.points.values():
                    if depuis is not None and p.id == depuis.point:
                        continue
                    if abs(p.z - acc.z) <= tol:
                        acc.z = p.z
                        acc.guides.append(((p.z, p.x), (p.z, acc.x)))
                        break
                for p in e.points.values():
                    if depuis is not None and p.id == depuis.point:
                        continue
                    if abs(acc.x) > 1e-9 and abs(p.x - acc.x) <= tol:
                        acc.x = p.x
                        acc.guides.append(((p.z, p.x), (acc.z, p.x)))
                        break

        if depuis is not None:
            dz, dx = acc.z - depuis.z, acc.x - depuis.x
            if math.hypot(dz, dx) > 1e-9:
                angle = math.degrees(math.atan2(abs(dx), abs(dz)))
                libre = acc.point is None and acc.courbe is None
                if self.aimants["ortho"] and angle < ANGLE_AUTO_DEG:
                    acc.auto = TypeRelation.HORIZONTAL
                    if libre:
                        acc.x = depuis.x
                        acc.guides = []
                elif self.aimants["ortho"] and angle > 90.0 - ANGLE_AUTO_DEG:
                    acc.auto = TypeRelation.VERTICAL
                    if libre:
                        acc.z = depuis.z
                        acc.guides = []
                elif self.aimants["diag"] and libre and abs(angle - 45.0) < ANGLE_AUTO_DEG:
                    acc.x = depuis.x + math.copysign(abs(dz), dx)
                    acc.guides = [((depuis.z, depuis.x), (acc.z, acc.x))]
        acc.sur_axe = abs(acc.x) < 1e-9 if acc.point is None else abs(e.points[acc.point].x) < 1e-9
        return acc

    def element_sous(self, pos) -> Optional[Tuple[str, int]]:
        """(genre, identifiant) de l'élément sous le curseur, les points d'abord."""
        t = TOLERANCE_PX
        for it in self.items(pos):
            if isinstance(it, Etiquette) and it.data(ROLE_GENRE):
                return it.data(ROLE_GENRE), it.data(ROLE_ID)
        rect = QRect(pos.x() - t, pos.y() - t, 2 * t + 1, 2 * t + 1)
        candidats = [(it.data(ROLE_GENRE), it.data(ROLE_ID)) for it in self.items(rect)
                     if it.data(ROLE_GENRE) and not isinstance(it, Etiquette)]
        if not candidats:
            return None
        ordre = {"point": 0, "arc": 1, "ligne": 2, "cote": 3, "relation": 4}
        candidats.sort(key=lambda gi: ordre.get(gi[0], 9))
        return candidats[0]

    def selectionner(self, ident: Optional[int], ajouter: bool = False) -> None:
        """Clic sur un élément : l'ajoute à la sélection, ou l'en retire s'il y était. Sans élément : vide tout."""
        if ident is None:
            self.selection = []
        elif ajouter:
            if ident in self.selection:
                self.selection.remove(ident)
            else:
                self.selection.append(ident)
        else:
            self.selection = [ident]
        self.reconstruire()
        self.selection_changee.emit()

    def deselectionner(self) -> None:
        if self.selection:
            self.selection = []
            self.reconstruire()
            self.selection_changee.emit()

    # -- outils --------------------------------------------------------------------------

    def definir_outil(self, outil: str) -> None:
        if outil not in self.OUTILS:
            return
        self.outil = outil
        self.annuler_outil()

    def annuler_outil(self) -> None:
        """Interrompt le tracé en cours (ligne enchaînée, arc, trait d'élagage) sans changer d'outil."""
        self._debut = None
        self._arc_fin = None
        self._trait = []
        self._timer_geste.stop()
        self._dessiner_apercu(None)
        self._aide()

    def en_cours(self) -> bool:
        return self._debut is not None or bool(self._trait)

    # -- geste d'élagage et cycle d'outils -------------------------------------------------

    def _declencher_geste(self) -> None:
        """Le bouton gauche est resté enfoncé sans bouger : le glisser qui suit sera un trait d'élagage."""
        if self._press_pos is None or not (QApplication.mouseButtons() & Qt.MouseButton.LeftButton):
            return
        self._geste = True
        self._outil_avant = self.outil
        depart = self.position_scene(self._press_pos)
        if self.outil != "elaguer":
            self.controleur.choisir_outil("elaguer")
        self._trait = [depart]
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.message.emit("Élaguer : tirez le trait au travers des objets à couper, puis relâchez.")
        self._dessiner_apercu(None)

    def _terminer_geste(self) -> None:
        trait = self._trait
        self._trait = []
        self._geste = False
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self._dessiner_apercu(None)
        if len(trait) >= 2:
            self.controleur.elaguer(self.croisements_du_trait(trait), self.mode_elagage)
        if self._outil_avant is not None and self._outil_avant != self.outil:
            self.controleur.choisir_outil(self._outil_avant)
        self._outil_avant = None

    def _a_bouge(self, pos) -> bool:
        return self._press_pos is not None and (pos - self._press_pos).manhattanLength() > SEUIL_GESTE_PX

    def cycler_outil(self, sens: int, pos=None) -> None:
        """Passe à l'outil suivant (sens > 0) ou précédent dans l'ordre Sélection, Ligne, Arc, Élaguer."""
        courant = self.outil if self.outil in OUTILS_RAPIDES else "selection"
        i = (OUTILS_RAPIDES.index(courant) + (1 if sens > 0 else -1)) % len(OUTILS_RAPIDES)
        nouveau = OUTILS_RAPIDES[i]
        self.controleur.choisir_outil(nouveau)
        if pos is not None:
            self._montrer_bulle(LIBELLES_OUTILS[nouveau], pos)

    def _montrer_bulle(self, texte: str, pos) -> None:
        if self._bulle is None:
            self._bulle = QLabel(self.viewport())
            self._bulle.setStyleSheet("background: rgba(40, 40, 40, 215); color: white; padding: 3px 8px; "
                                      "border-radius: 4px; font-weight: 600;")
        self._bulle.setText(texte)
        self._bulle.adjustSize()
        self._bulle.move(pos + QPoint(14, 14))
        self._bulle.show()
        self._timer_bulle.start(900)

    def _cacher_bulle(self) -> None:
        if self._bulle is not None:
            self._bulle.hide()

    def _aide(self) -> None:
        if self.outil == "ligne":
            self.message.emit("Ligne : cliquez le départ, puis chaque sommet. Clic droit ou Échap pour finir."
                              if self._debut is None else
                              "Ligne : cliquez le sommet suivant. Clic droit ou Échap pour finir la chaîne.")
        elif self.outil == "arc":
            if self._debut is None:
                self.message.emit("Arc : cliquez le point de départ.")
            elif self._arc_fin is None:
                self.message.emit("Arc : cliquez le point d'arrivée.")
            else:
                self.message.emit("Arc : cliquez un point par où passe l'arc.")
        elif self.outil == "elaguer":
            self.message.emit("Élaguer : tirez un trait au travers des lignes ou des arcs à couper.")
        else:
            self.message.emit("Sélection : les clics s'ajoutent, clic dans le vide pour tout désélectionner. "
                              "Tirez un point, double-cliquez une cote. Clic semi-long + glisser : élaguer. "
                              "Clic droit + molette : outil.")

    # -- souris ------------------------------------------------------------------------

    def mousePressEvent(self, event) -> None:
        pos = event.position().toPoint()
        if event.button() == Qt.MouseButton.MiddleButton:
            self._pan_dernier = pos
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            return
        if event.button() == Qt.MouseButton.RightButton:
            self._droit_molette = False        # l'action du clic droit est décidée au relâchement
            return
        if event.button() != Qt.MouseButton.LeftButton:
            return
        self._press_pos = pos
        self._geste = False
        if self.outil == "selection":
            self._presser_selection(pos)
        elif self.outil in ("ligne", "arc"):
            if not self.en_cours():
                self._timer_geste.start(DELAI_GESTE_MS)
        elif self.outil == "elaguer":
            self._trait = [self.position_scene(pos)]
            self._dessiner_apercu(None)

    def _presser_selection(self, pos) -> None:
        el = self.element_sous(pos)
        if el is None:
            self.selectionner(None)
            self._timer_geste.start(DELAI_GESTE_MS)
            return
        genre, ident = el
        if genre == "point":
            self._glisse_point = ident          # sélection ou glissement : tranché au relâchement
            self._glisse_actif = False
            return
        if genre == "cote":
            self._glisse_cote = ident
            self._glisse_dernier = self.mapToScene(pos)
            self._glisse_actif = False
            return
        self.selectionner(ident, ajouter=True)
        if genre in ("ligne", "arc"):
            self._timer_geste.start(DELAI_GESTE_MS)

    def _presser_ligne(self, pos) -> None:
        if self._debut is None:
            self._debut = self.accrocher(pos)
            self._aide()
            return
        acc = self.accrocher(pos, self._debut)
        if acc.point is not None and acc.point == self._debut.point:
            return
        if math.hypot(acc.z - self._debut.z, acc.x - self._debut.x) < 1e-9:
            return
        fin = self.controleur.ajouter_ligne(self._debut, acc, acc.auto)
        if fin is None:
            return
        p = self.esquisse.points.get(fin)
        self._debut = Accroche(p.z, p.x, fin, abs(p.x) < 1e-9) if p is not None else None
        self._aide()

    def _presser_arc(self, pos) -> None:
        if self._debut is None:
            self._debut = self.accrocher(pos)
        elif self._arc_fin is None:
            acc = self.accrocher(pos)
            if acc.point is not None and acc.point == self._debut.point:
                return
            self._arc_fin = acc
        else:
            z, x = self.position_scene(pos)
            arc = self._arc_par_trois_points((self._debut.z, self._debut.x), (self._arc_fin.z, self._arc_fin.x), (z, x))
            if arc is None:
                self.message.emit("Arc : les trois points sont alignés, choisissez un autre point de passage.")
                return
            (cz, cx), horaire = arc
            self.controleur.ajouter_arc(self._debut, self._arc_fin, (cz, cx), horaire)
            self._debut = None
            self._arc_fin = None
            self._dessiner_apercu(None)
        self._aide()

    def mouseMoveEvent(self, event) -> None:
        pos = event.position().toPoint()
        z, x = self.position_scene(pos)
        self.coordonnees.emit(z, x)
        if self._pan_dernier is not None:
            delta = pos - self._pan_dernier
            self._pan_dernier = pos
            self.translate(delta.x() / self.echelle(), -delta.y() / self.echelle())
            return
        gauche = bool(event.buttons() & Qt.MouseButton.LeftButton)
        if self._geste and gauche:
            self._trait.append((z, x))
            self._dessiner_apercu(None)
            return
        if gauche and self._timer_geste.isActive() and self._a_bouge(pos):
            self._timer_geste.stop()           # on a bougé trop tôt : ce n'est pas un clic semi-long
        if self._glisse_point is not None and gauche:
            if not self._glisse_actif:
                self._glisse_actif = True
                self.controleur.debut_glissement()
            acc = self.accrocher(pos)
            cible_z, cible_x = acc.z, acc.x
            if acc.point == self._glisse_point:
                cible_z, cible_x = z, x
            self.controleur.glisser(self._glisse_point, cible_z, cible_x)
            return
        if self._glisse_cote is not None and gauche:
            p = self.mapToScene(pos)
            d = p - self._glisse_dernier
            self._glisse_dernier = p
            self._glisse_actif = True
            self.controleur.deplacer_etiquette(self._glisse_cote, d.x(), d.y())
            return
        if self.outil == "elaguer" and self._trait and gauche:
            self._trait.append((z, x))
            self._dessiner_apercu(None)
            return
        if self.outil in ("ligne", "arc"):
            depuis = self._debut if (self.outil == "ligne" and self._debut is not None) else None
            self._dessiner_apercu(self.accrocher(pos, depuis))

    def mouseReleaseEvent(self, event) -> None:
        pos = event.position().toPoint()
        if event.button() == Qt.MouseButton.MiddleButton:
            self._pan_dernier = None
            self.setCursor(Qt.CursorShape.ArrowCursor)
            return
        if event.button() == Qt.MouseButton.RightButton:
            if self._droit_molette:
                self._droit_molette = False     # la molette a servi à changer d'outil : pas de menu
                return
            if self.en_cours():
                self.annuler_outil()
                return
            el = self.element_sous(pos)
            if el is not None and el[1] not in self.selection:
                self.selectionner(el[1], ajouter=True)
            self.controleur.menu_contextuel(event.globalPosition().toPoint())
            return
        if event.button() != Qt.MouseButton.LeftButton:
            return
        self._timer_geste.stop()
        if self._geste:
            self._terminer_geste()
            self._press_pos = None
            return
        if self.outil == "ligne" and not self._a_bouge(pos):
            self._presser_ligne(pos)
        elif self.outil == "arc" and not self._a_bouge(pos):
            self._presser_arc(pos)
        self._press_pos = None
        if self._glisse_point is not None:
            if self._glisse_actif:
                self.controleur.fin_glissement()
            else:
                self.selectionner(self._glisse_point, ajouter=True)
            self._glisse_point = None
            self._glisse_actif = False
        if self._glisse_cote is not None:
            if not self._glisse_actif:
                self.selectionner(self._glisse_cote, ajouter=True)
            self._glisse_cote = None
            self._glisse_dernier = None
            self._glisse_actif = False
        if self.outil == "elaguer" and self._trait:
            trait = self._trait
            self._trait = []
            self._dessiner_apercu(None)
            if len(trait) >= 2:
                self.controleur.elaguer(self.croisements_du_trait(trait), self.mode_elagage)

    def croisements_du_trait(self, trait: List[Tuple[float, float]]) -> List[Tuple[int, float]]:
        """Pour chaque ligne ou arc traversé par le trait : (identifiant, paramètre du premier croisement)."""
        e = self.esquisse
        coups = []
        for ident in list(e.lignes) + list(e.arcs):
            res = geo.polyligne_croise(trait, courbe_de(e, ident))
            if res is not None:
                coups.append((ident, res[0]))
        return coups

    def mouseDoubleClickEvent(self, event) -> None:
        if event.button() != Qt.MouseButton.LeftButton or self.outil != "selection":
            return
        el = self.element_sous(event.position().toPoint())
        if el is not None and el[0] == "cote":
            self._glisse_cote = None
            self.controleur.editer_cote(el[1])

    def wheelEvent(self, event) -> None:
        delta = event.angleDelta().y()
        if delta == 0:
            return
        if event.buttons() & Qt.MouseButton.RightButton:
            # clic droit maintenu + molette : Sélection -> Ligne -> Arc -> Élaguer
            self._droit_molette = True
            self.cycler_outil(1 if delta < 0 else -1, event.position().toPoint())
            event.accept()
            return
        self.zoomer(1.15 ** (delta / 120.0), event.position().toPoint())

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape:
            if self.en_cours():
                self.annuler_outil()
            else:
                self.deselectionner()
            return
        super().keyPressEvent(event)

    def leaveEvent(self, event) -> None:
        self._dessiner_apercu(None)
        super().leaveEvent(event)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.reconstruire()
