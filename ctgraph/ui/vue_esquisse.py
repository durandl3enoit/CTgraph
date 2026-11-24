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
from ..icons import curseur_outil, icone_outil

ROLE_GENRE = 0
ROLE_ID = 1
ROLE_VARIANTE = 2        # sur une étiquette de cote : "rayon" pour la seconde étiquette d'un diamètre

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
    TypeRelation.ORIGINE_Z: "z0",
    TypeRelation.FIXE: "F",
}

TOLERANCE_PX = 9          # rayon d'accrochage et de sélection, en pixels
ANGLE_AUTO_DEG = 4.0      # en deçà, un trait reçoit la relation horizontal ou vertical, ou s'aligne à 45°
AIMANTS_DEFAUT = {"ortho": True, "diag": True, "objets": True, "axe": True}
LIBELLES_AIMANTS = {"ortho": "Horizontal / vertical", "diag": "45°", "objets": "Objets proches", "axe": "Axe Z"}
OUTILS_RAPIDES = ("selection", "ligne", "arc", "cote", "arrondi", "chanfrein", "elaguer")   # clic droit + molette
LIBELLES_OUTILS = {"selection": "Sélection", "ligne": "Ligne", "arc": "Arc 3 points", "cote": "Cote",
                   "arrondi": "Arrondi", "chanfrein": "Chanfrein", "elaguer": "Élaguer"}
DELAI_GESTE_MS = 350      # clic semi-long : au-delà, glisser élague au lieu de sélectionner ou de tracer
SEUIL_GESTE_PX = 4        # bouger plus que cela avant le délai annule le geste


@dataclass
class Accroche:
    """Résultat de l'aimantation du curseur : une position, et ce à quoi elle est accrochée."""
    z: float
    x: float
    point: Optional[int] = None            # point existant sous le curseur
    sur_axe: bool = False                  # sur l'axe de la pièce (x = 0)
    sur_origine: bool = False              # sur la face d'origine (z = 0) : pose la relation « origine Z »
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
        if not self.symbole:
            painter.drawText(self._rect, Qt.AlignmentFlag.AlignCenter, self.texte)
            return
        # La lettre est centrée sur son encre réelle (pas sur la hauteur de police) : le z tombe à mi-hauteur
        # des tirets, le x à mi-largeur de la barre.
        fm = QFontMetricsF(self.police)
        encre = fm.tightBoundingRect(self.texte)
        origine = QPointF(-(encre.x() + encre.width() / 2), -(encre.y() + encre.height() / 2))
        painter.drawText(origine, self.texte)
        trait = QPen(self.couleur, 1.6)
        trait.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(trait)
        if self.symbole == "horizontal":
            demi = encre.width() / 2 + 2.5
            painter.drawLine(QPointF(self._rect.left() + 3, 0), QPointF(-demi, 0))
            painter.drawLine(QPointF(demi, 0), QPointF(self._rect.right() - 3, 0))
        else:
            demi = encre.height() / 2 + 2.5
            painter.drawLine(QPointF(0, self._rect.top() + 3), QPointF(0, -demi))
            painter.drawLine(QPointF(0, demi), QPointF(0, self._rect.bottom() - 3))


class BulleOutils(QWidget):
    """Bande d'icônes affichée sous le curseur pendant le cycle d'outils à la molette.

    Les outils sont rangés en anneau et la bande tourne pour garder l'outil actif au centre, en plus gros,
    avec son nom dessous : la molette fait défiler les icônes.
    """

    PAS = 38

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.courant = "selection"
        encre, fond = QColor(240, 240, 240), QColor(40, 40, 40)
        self._icones = {nom: icone_outil(nom, encre, fond) for nom in OUTILS_RAPIDES}
        self.resize(self.PAS * len(OUTILS_RAPIDES) + 16, 72)
        self.hide()

    def montrer(self, outil: str, pos: QPoint) -> None:
        self.courant = outil if outil in OUTILS_RAPIDES else "selection"
        self.move(pos)
        self.show()
        self.raise_()
        self.update()

    def ordre(self) -> List[str]:
        """Les outils tournés pour que l'outil actif soit au milieu."""
        n = len(OUTILS_RAPIDES)
        i = OUTILS_RAPIDES.index(self.courant)
        decal = i - n // 2
        return [OUTILS_RAPIDES[(k + decal) % n] for k in range(n)]

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor(40, 40, 40, 225)))
        p.drawRoundedRect(self.rect(), 6, 6)
        milieu = len(OUTILS_RAPIDES) // 2
        for k, nom in enumerate(self.ordre()):
            cx = 8 + self.PAS * k + self.PAS // 2
            if k == milieu:
                p.setBrush(QBrush(QColor(90, 160, 220, 110)))
                p.drawEllipse(QPointF(cx, 26), 17, 17)
                taille = 28
            else:
                taille = 20
            pm = self._icones[nom].pixmap(taille, taille)
            p.drawPixmap(int(cx - taille / 2), int(26 - taille / 2), pm)
        p.setPen(QPen(QColor(255, 255, 255)))
        police = QFont()
        police.setBold(True)
        p.setFont(police)
        p.drawText(QRectF(0, 48, self.width(), 20), Qt.AlignmentFlag.AlignCenter, LIBELLES_OUTILS[self.courant])
        p.end()


class VueEsquisse(QGraphicsView):
    coordonnees = Signal(float, float)       # (z, x) sous le curseur
    message = Signal(str)                    # aide contextuelle pour la barre d'état
    selection_changee = Signal()

    OUTILS = ("selection", "ligne", "arc", "cote", "arrondi", "chanfrein", "elaguer")

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
        self.vue3d = None                 # incrustation 3D en haut à droite, posée par la fenêtre
        self.montage = None               # mandrin, brut, contre-pointe : dessinés en arrière-plan du profil
        self.montage_visible = True

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
        self._cote_elements: List[int] = []             # éléments cliqués avec l'outil Cote, avant la pose
        self._apercu: List[QGraphicsItem] = []
        self._glisse_point: Optional[int] = None
        self._glisse_cote: Optional[int] = None
        self._glisse_dernier: Optional[QPointF] = None
        self._glisse_actif = False
        self._pan_dernier = None
        self._items: List[QGraphicsItem] = []
        self._pos_cotes: Dict[int, Tuple[float, float]] = {}

        # clic semi-long + glisser : élagage, quel que soit l'outil
        self._press_pos: Optional[QPoint] = None
        self._geste = False
        self._outil_avant: Optional[str] = None
        self._timer_geste = QTimer(self)
        self._timer_geste.setSingleShot(True)
        self._timer_geste.timeout.connect(self._declencher_geste)

        # clic droit maintenu + molette : changement d'outil (bande d'icônes), ou réglage d'une cote si le
        # bouton a été enfoncé sur son étiquette
        self._droit_molette = False
        self._droit_cote: Optional[Tuple[int, Optional[str]]] = None
        self._bulle: Optional[BulleOutils] = None
        self._bulle_texte: Optional[QLabel] = None
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
        zs = [p.z for p in e.points.values()]
        xs = [p.x for p in e.points.values()] + [0.0]
        if self.montage is not None and self.montage_visible:
            zs += [self.montage.z_brut_arriere(), self.montage.z_brut_avant()]
            xs += [max(self.montage.rayon_brut(), max(b[3] for b in self.montage.blocs_mors()))]
        if zs:
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
            "pilotee": QColor(150, 150, 150) if sombre else QColor(135, 135, 135),
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

        if self.montage is not None and self.montage_visible:
            self._dessiner_montage(c)

        # contours fermés : un remplissage discret valide que le profil se referme, et la vue 3D les révolutionne
        contours = self.contours_fermes()
        for chaine in contours:
            it = QGraphicsPathItem(self._chemin_contour(chaine))
            it.setPen(QPen(Qt.PenStyle.NoPen))
            it.setBrush(QBrush(QColor(couleur_geom.red(), couleur_geom.green(), couleur_geom.blue(), 30)))
            it.setZValue(1)
            self._scene.addItem(it)
            self._items.append(it)
        if self.vue3d is not None:
            self.vue3d.definir_contours([self._polyligne_contour(ch) for ch in contours])

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
            if p.construction:
                it = self._croix(p, c["relation"], p.id in sel, c, diagonale=True)   # coin théorique, hors profil
            elif p.id in centres and p.id not in extremites:
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

        # cotes avant les symboles de relations : une relation « égal » entre cotes s'ancre sur leurs étiquettes
        self._pos_cotes: Dict[int, Tuple[float, float]] = {}
        for co in e.cotes.values():
            if co.pilotee:
                couleur = c["pilotee"]
            else:
                couleur = c["conflit"] if co.id in conflits else (c["redondant"] if co.id in redondants else c["cote"])
            if co.id in sel:
                couleur = c["selection"]
            self._dessiner_cote(co, couleur, c)

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

        self._dessiner_apercu()

    def _dessiner_montage(self, c: Dict[str, QColor]) -> None:
        """Brut en pointillés, mors hachurés, face du mandrin, contre-pointe : au-dessus de l'axe, en retrait."""
        m = self.montage
        muet = QColor(c["texte"].red(), c["texte"].green(), c["texte"].blue(), 90)
        stylo = QPen(muet, 1, Qt.PenStyle.DashLine)
        stylo.setCosmetic(True)
        plein = QPen(muet, 1)
        plein.setCosmetic(True)

        def ajouter(it: QGraphicsItem, z: float = 0.5) -> None:
            it.setZValue(z)
            self._scene.addItem(it)
            self._items.append(it)

        # brut
        rb, rbi = m.rayon_brut(), m.rayon_interieur_brut()
        z1, z2 = m.z_brut_arriere(), m.z_brut_avant()
        rect = QGraphicsPathItem(self._rect_path(z1, rbi, z2, rb))
        rect.setPen(stylo)
        rect.setBrush(QBrush(QColor(200, 170, 90, 22)))
        ajouter(rect)
        # mors étagé : l'étage de butée au fond, la face de serrage devant (hachurés)
        zf = m.z_fond_mors()
        path = QPainterPath()
        for (bz1, bz2, br1, br2) in m.blocs_mors():
            if br2 - br1 > 1e-6 and bz2 - bz1 > 1e-6:
                path.addRect(QRectF(bz1, br1, bz2 - bz1, br2 - br1))
        mors = QGraphicsPathItem(path)
        mors.setPen(plein)
        mors.setBrush(QBrush(muet, Qt.BrushStyle.BDiagPattern))
        ajouter(mors)
        # corps du mandrin : de l'alésage au diamètre extérieur, derrière les mors
        za = m.z_arriere_mandrin()
        corps = QGraphicsPathItem(self._rect_path(za, m.mandrin.alesage / 2.0, zf, m.mandrin.diametre / 2.0))
        corps.setPen(plein)
        corps.setBrush(QBrush(QColor(muet.red(), muet.green(), muet.blue(), 30)))
        ajouter(corps)
        # les trois valeurs du brut, toujours affichées et éditables : Ø, longueur, marge en bout
        d = self.px_en_mm(30)
        ambre = QColor(205, 175, 95)
        zl = z2 + d
        self._dessiner_cote_brut("diametre", [(zl, 0.0), (zl, rb)], [((z2, rb), (zl + self.px_en_mm(4), rb))],
                                 (zl, rb / 2.0), ambre, c, fleches=((zl, rb, (0.0, 1.0)), (zl, 0.0, (0.0, -1.0))))
        xl = max(rb, max(b[3] for b in m.blocs_mors())) + d
        self._dessiner_cote_brut("longueur", [(z1, xl), (z2, xl)],
                                 [((z1, rb), (z1, xl + self.px_en_mm(4))), ((z2, rb), (z2, xl + self.px_en_mm(4)))],
                                 ((z1 + z2) / 2.0, xl), ambre, c,
                                 fleches=((z1, xl, (-1.0, 0.0)), (z2, xl, (1.0, 0.0))))
        xm = -d * 0.7
        self._dessiner_cote_brut("marge", [(0.0, xm), (z2, xm)],
                                 [((0.0, 0.0), (0.0, xm - self.px_en_mm(4))), ((z2, 0.0), (z2, xm - self.px_en_mm(4)))],
                                 (z2 / 2.0 + self.px_en_mm(26), xm), ambre, c,
                                 fleches=((0.0, xm, (-1.0, 0.0)), (z2, xm, (1.0, 0.0))) if z2 > 1e-9 else ())
        # contre-pointe
        cp = m.contre_pointe
        if cp.presente:
            demi = cp.diametre / 2.0
            lg_cone = demi / math.tan(math.radians(cp.angle / 2.0))
            path = QPainterPath()
            path.moveTo(z2, 0.0)
            path.lineTo(z2 + lg_cone, demi)
            path.lineTo(z2 + max(cp.longueur, lg_cone + 1.0), demi)
            path.lineTo(z2 + max(cp.longueur, lg_cone + 1.0), 0.0)
            path.closeSubpath()
            pointe = QGraphicsPathItem(path)
            pointe.setPen(plein)
            pointe.setBrush(QBrush(muet, Qt.BrushStyle.FDiagPattern))
            ajouter(pointe)

    def _dessiner_cote_brut(self, cle: str, ligne, attaches, pos, couleur: QColor, c: Dict[str, QColor],
                            fleches=()) -> None:
        """Une cote du brut : ligne de cote, lignes d'attache, flèches, étiquette éditable (genre « brut »)."""
        path = QPainterPath()
        (a, b) = ligne
        path.moveTo(*a)
        path.lineTo(*b)
        for (p, q) in attaches:
            path.moveTo(*p)
            path.lineTo(*q)
        for (z, x, direction) in fleches:
            self._fleche(path, (z, x), direction)
        it = QGraphicsPathItem(path)
        pen = QPen(couleur, 1)
        pen.setCosmetic(True)
        it.setPen(pen)
        it.setZValue(2)
        self._scene.addItem(it)
        self._items.append(it)
        et = Etiquette(self.montage.texte_brut(cle), couleur, c["fond"], gras=False)
        et.setPos(*pos)
        et.setData(ROLE_GENRE, "brut")
        et.setData(ROLE_ID, cle)
        self._scene.addItem(et)
        self._items.append(et)

    @staticmethod
    def _rect_path(z1: float, x1: float, z2: float, x2: float) -> QPainterPath:
        path = QPainterPath()
        path.addRect(QRectF(min(z1, z2), min(x1, x2), abs(z2 - z1), abs(x2 - x1)))
        return path

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

    def _croix(self, p, couleur: QColor, selectionne: bool, c: Dict[str, QColor],
               diagonale: bool = False) -> QGraphicsPathItem:
        path = QPainterPath()
        if diagonale:
            path.moveTo(-4, -4)
            path.lineTo(4, 4)
            path.moveTo(-4, 4)
            path.lineTo(4, -4)
        else:
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

    def contours_fermes(self) -> List[List[Tuple[int, bool]]]:
        """Chaînes fermées de lignes et d'arcs, chaque sommet reliant exactement deux éléments.

        Chaque chaîne est une liste de (élément, parcouru à l'envers). Les boucles passant par un sommet
        à trois branches ou plus ne sont pas reconnues : il faudra un vrai parcours de faces plus tard.
        """
        e = self.esquisse
        elements = list(e.lignes) + list(e.arcs)

        # deux points liés par « coïncident » comptent pour un seul sommet
        parent: Dict[int, int] = {pid: pid for pid in e.points}

        def trouver(pid: int) -> int:
            while parent[pid] != pid:
                parent[pid] = parent[parent[pid]]
                pid = parent[pid]
            return pid

        for r in e.relations.values():
            if r.type == TypeRelation.COINCIDENT and all(p in parent for p in r.elements):
                a, b = trouver(r.elements[0]), trouver(r.elements[1])
                if a != b:
                    parent[b] = a

        def extremites(ident: int) -> Tuple[int, int]:
            a, b = e.extremites(ident)
            return trouver(a), trouver(b)

        incidences: Dict[int, List[int]] = {}
        for ident in elements:
            for p in extremites(ident):
                incidences.setdefault(p, []).append(ident)

        def avancer(courant: int, inverse: bool, chaine: List[Tuple[int, bool]], vus: set) -> Optional[int]:
            """Prolonge la chaîne depuis la sortie de `courant` tant que les sommets relient deux éléments.
            Renvoie le point d'arrêt, ou None si la chaîne se referme sur son premier élément."""
            while True:
                a, b = extremites(courant)
                fin = a if inverse else b
                autour = incidences.get(fin, [])
                if len(autour) != 2:
                    return fin
                suivant = autour[0] if autour[1] == courant else autour[1]
                if suivant == chaine[0][0]:
                    return None
                if suivant in vus:
                    return fin
                na, nb = extremites(suivant)
                inverse = (nb == fin)
                chaine.append((suivant, inverse))
                vus.add(suivant)
                courant = suivant

        def sur_axe(pid: int) -> bool:
            return abs(e.points[pid].x) < 1e-9

        vus: set = set()
        contours = []
        for depart in elements:
            if depart in vus:
                continue
            avant: List[Tuple[int, bool]] = [(depart, False)]
            vus.add(depart)
            fin_avant = avancer(depart, False, avant, vus)
            if fin_avant is None:
                chaine = avant                                   # refermée sur elle-même
            else:
                arriere: List[Tuple[int, bool]] = [(depart, True)]
                fin_arriere = avancer(depart, True, arriere, vus)
                chaine = [(i, not inv) for i, inv in reversed(arriere[1:])] + avant
                # un profil dont les deux bouts touchent l'axe est fermé par l'axe de révolution
                if fin_arriere is None or not (sur_axe(fin_avant) and sur_axe(fin_arriere)) or fin_avant == fin_arriere:
                    continue
                if all(sur_axe(p) for i, _ in chaine for p in extremites(i)):
                    continue                                     # tout est sur l'axe : pas de surface
            if len(chaine) >= 3 or any(e.genre(i) == "arc" for i, _ in chaine) or fin_avant is not None:
                contours.append(chaine)
        return contours

    def _polyligne_contour(self, chaine: List[Tuple[int, bool]]) -> List[Tuple[float, float]]:
        """Points (z, x) d'un contour fermé, dans l'ordre de parcours, le premier répété à la fin."""
        e = self.esquisse
        poly: List[Tuple[float, float]] = []
        for ident, inverse in chaine:
            if e.genre(ident) == "ligne":
                a, b = (e.points[i] for i in e.extremites(ident))
                pts = [(a.z, a.x), (b.z, b.x)]
            else:
                pts = self._points_arc(ident, 32)
            if inverse:
                pts = pts[::-1]
            poly.extend(pts if not poly else pts[1:])
        if poly and poly[0] != poly[-1]:
            poly.append(poly[0])
        return poly

    def _chemin_contour(self, chaine: List[Tuple[int, bool]]) -> QPainterPath:
        path = QPainterPath()
        poly = self._polyligne_contour(chaine)
        if poly:
            path.moveTo(*poly[0])
            for q in poly[1:]:
                path.lineTo(*q)
            path.closeSubpath()
        return path

    def placer_superposition(self) -> None:
        """Garde la vue 3D ancrée en haut à droite de l'esquisse."""
        if self.vue3d is None:
            return
        marge = 10
        w = min(self.vue3d.width(), max(self.width() - 2 * marge, 1))
        h = min(self.vue3d.height(), max(self.height() - 2 * marge, 1))
        if (w, h) != (self.vue3d.width(), self.vue3d.height()):
            self.vue3d.resize(w, h)
        self.vue3d.move(self.width() - w - marge, marge)
        self.vue3d.raise_()

    def _milieu(self, ident: int) -> Tuple[float, float]:
        e = self.esquisse
        g = e.genre(ident)
        if g == "point":
            p = e.points[ident]
            return p.z, p.x
        if g == "cote":
            return self._pos_cotes.get(ident, (0.0, 0.0))
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
            elif g == "cote":
                ancres.append((ident, mz + decal * 1.6, mx))           # à droite de l'étiquette
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

    def _dessiner_cote(self, co: Cote, couleur: QColor, c: Dict[str, QColor], apercu: bool = False) -> None:
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
        elif co.type == TypeCote.POSITION_Z:
            # de la face d'origine (z = 0) au point visé, sur une horizontale au-dessus du point ou de la face
            el = co.elements[0]
            p = e.points[e.point_reference(el)]
            if e.genre(el) == "ligne":
                a, b = (e.points[i] for i in e.extremites(el))
                base_x = max(a.x, b.x)
            else:
                base_x = p.x
            xl = base_x + dx
            path.moveTo(p.z, base_x)
            path.lineTo(p.z, xl + math.copysign(ext, dx or 1.0))
            path.moveTo(0.0, xl - ext)
            path.lineTo(0.0, xl + ext)
            path.moveTo(0.0, xl)
            path.lineTo(p.z, xl)
            if abs(p.z) > 1e-9:
                self._fleche(path, (0.0, xl), (-p.z, 0.0))
                self._fleche(path, (p.z, xl), (p.z, 0.0))
            pos = (p.z / 2 + dz, xl)
        elif co.type == TypeCote.ECART:
            # segment perpendiculaire entre les deux lignes, glissé le long de la première selon le décalage
            l1, l2 = (e.lignes[i] for i in co.elements)
            a, b = e.points[l1.p1], e.points[l1.p2]
            uz, ux = b.z - a.z, b.x - a.x
            n = math.hypot(uz, ux) or 1.0
            uz, ux = uz / n, ux / n
            glisse = dz * uz + dx * ux
            az, ax = (a.z + b.z) / 2 + uz * glisse, (a.x + b.x) / 2 + ux * glisse
            c1, c2 = e.points[l2.p1], e.points[l2.p2]
            t = geo.parametre(geo.ligne((c1.z, c1.x), (c2.z, c2.x)), (az, ax))
            bz, bx = geo.position(geo.ligne((c1.z, c1.x), (c2.z, c2.x)), t)
            path.moveTo(az, ax)
            path.lineTo(bz, bx)
            if math.hypot(bz - az, bx - ax) > 1e-9:
                self._fleche(path, (az, ax), (az - bz, ax - bx))
                self._fleche(path, (bz, bx), (bz - az, bx - ax))
            pos = ((az + bz) / 2, (ax + bx) / 2)
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
        pen = QPen(couleur, 1, Qt.PenStyle.DashLine if apercu else Qt.PenStyle.SolidLine)
        pen.setCosmetic(True)
        it.setPen(pen)
        if not apercu:
            self._pos_cotes[co.id] = pos
        etiquettes = [(Etiquette(texte, couleur, c["fond"], gras=True), pos, None)]
        if co.type == TypeCote.DIAMETRE:
            # le rayon accompagne le diamètre : même grandeur lue depuis l'axe, éditable aussi
            et_r = Etiquette(e.texte_rayon(co), couleur, c["fond"], gras=False)
            etiquettes.append((et_r, (pos[0], pos[1] - self.px_en_mm(19)), "rayon"))
        if apercu:
            self._ajouter_apercu(it, 3)
        else:
            it.setZValue(3)
            self._enregistrer(it, "cote", co.id)
        for et, position, variante in etiquettes:
            et.setPos(*position)
            if apercu:
                self._ajouter_apercu(et, 20)
            else:
                self._enregistrer(et, "cote", co.id)
                if variante:
                    et.setData(ROLE_VARIANTE, variante)

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
        if self.outil == "cote" and self._cote_elements:
            self._apercu_cote(curseur, c)
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
            elif curseur.sur_axe or curseur.sur_origine:
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
                    acc = Accroche(proche[1][0], proche[1][1], None, abs(proche[1][1]) < 1e-9, courbe=proche[0])

        if acc.point is None and acc.courbe is None:
            if self.aimants["axe"] and abs(acc.x) <= tol:
                acc.x = 0.0
            if self.aimants["axe"] and abs(acc.z) <= tol:
                acc.z = 0.0                      # face d'origine de la pièce
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
        acc.sur_origine = acc.point is None and acc.courbe is None and self.aimants["axe"] and abs(acc.z) < 1e-9
        return acc

    def etiquette_sous(self, pos) -> Optional[Tuple[str, int]]:
        """(genre, identifiant) de l'étiquette de cote exactement sous le curseur, sinon None."""
        for it in self.items(pos):
            if isinstance(it, Etiquette) and it.data(ROLE_GENRE) == "cote":
                return it.data(ROLE_GENRE), it.data(ROLE_ID)
        return None

    def element_sous(self, pos, genres=None) -> Optional[Tuple[str, int]]:
        """(genre, identifiant) de l'élément sous le curseur, les points d'abord.

        `genres` restreint la recherche, par exemple à la géométrie seule pour ignorer les étiquettes de cotes.
        Les textes (symboles de relations, valeurs de cotes) ne répondent qu'à un clic exactement dessus.
        """
        t = TOLERANCE_PX
        for it in self.items(pos):
            if isinstance(it, Etiquette) and it.data(ROLE_GENRE) and (genres is None or it.data(ROLE_GENRE) in genres):
                return it.data(ROLE_GENRE), it.data(ROLE_ID)
        rect = QRect(pos.x() - t, pos.y() - t, 2 * t + 1, 2 * t + 1)
        candidats = [(it.data(ROLE_GENRE), it.data(ROLE_ID)) for it in self.items(rect)
                     if it.data(ROLE_GENRE) and not isinstance(it, Etiquette)
                     and (genres is None or it.data(ROLE_GENRE) in genres)]
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
        self.appliquer_curseur()

    def appliquer_curseur(self) -> None:
        """Le curseur dit quel outil est actif : flèche en sélection, croix et symbole de l'outil sinon."""
        c = self._couleurs()
        self.viewport().setCursor(curseur_outil(self.outil, c["texte"], c["fond"]))

    def annuler_outil(self) -> None:
        """Interrompt le tracé en cours (ligne enchaînée, arc, trait d'élagage) sans changer d'outil."""
        self._debut = None
        self._arc_fin = None
        self._trait = []
        self._cote_elements = []
        self._timer_geste.stop()
        self._dessiner_apercu(None)
        self._aide()

    def en_cours(self) -> bool:
        return self._debut is not None or bool(self._trait) or bool(self._cote_elements)

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
        self.message.emit("Élaguer : tirez le trait au travers des objets à couper, puis relâchez.")
        self._dessiner_apercu(None)

    def _terminer_geste(self) -> None:
        trait = self._trait
        self._trait = []
        self._geste = False
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
            self._bulle = BulleOutils(self.viewport())
        self._bulle.montrer(self.outil, pos + QPoint(14, 14))
        self._timer_bulle.start(1100)

    def _cacher_bulle(self) -> None:
        if self._bulle is not None:
            self._bulle.hide()
        if self._bulle_texte is not None:
            self._bulle_texte.hide()

    def _montrer_texte(self, texte: str, pos) -> None:
        """Petite bulle de texte sous le curseur (valeur d'une cote en cours de réglage)."""
        if self._bulle_texte is None:
            self._bulle_texte = QLabel(self.viewport())
            self._bulle_texte.setStyleSheet("background: rgba(40, 40, 40, 225); color: white; padding: 3px 8px; "
                                            "border-radius: 4px; font-weight: 600;")
            self._bulle_texte.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._bulle_texte.setText(texte)
        self._bulle_texte.adjustSize()
        self._bulle_texte.move(pos + QPoint(14, 14))
        self._bulle_texte.show()
        self._bulle_texte.raise_()
        self._timer_bulle.start(1100)

    def etiquette_et_variante(self, pos) -> Optional[Tuple[int, Optional[str]]]:
        """(cote, variante) de l'étiquette sous le curseur : variante « rayon » pour le R d'un diamètre,
        ou (clé, "brut") pour une cote du brut."""
        for it in self.items(pos):
            if isinstance(it, Etiquette) and it.data(ROLE_GENRE) == "cote":
                return it.data(ROLE_ID), it.data(ROLE_VARIANTE) or None
            if isinstance(it, Etiquette) and it.data(ROLE_GENRE) == "brut":
                return it.data(ROLE_ID), "brut"
        return None

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
        elif self.outil == "arrondi":
            self.message.emit("Arrondi : cliquez le sommet entre deux lignes, puis donnez le rayon.")
        elif self.outil == "chanfrein":
            self.message.emit("Chanfrein : cliquez le sommet entre deux lignes, puis donnez la longueur du pan.")
        elif self.outil == "cote":
            if not self._cote_elements:
                self.message.emit("Cote : cliquez un point (diamètre), un arc (rayon), une ligne, ou deux éléments.")
            else:
                self.message.emit("Cote : cliquez où la poser. Le type suit l'endroit : au-dessus = longueur Z, "
                                  "à côté = diamètre ou angle. Un second élément : angle ou longueur entre deux faces.")
        else:
            self.message.emit("Sélection : les clics s'ajoutent, clic dans le vide pour tout désélectionner. "
                              "Tirez un point, double-cliquez une cote. Clic semi-long + glisser : élaguer. "
                              "Clic droit + molette : outil.")

    # -- souris ------------------------------------------------------------------------

    def mousePressEvent(self, event) -> None:
        pos = event.position().toPoint()
        if event.button() == Qt.MouseButton.MiddleButton:
            self._pan_dernier = pos
            self.viewport().setCursor(Qt.CursorShape.ClosedHandCursor)
            return
        if event.button() == Qt.MouseButton.RightButton:
            self._droit_molette = False        # l'action du clic droit est décidée au relâchement
            self._droit_cote = self.etiquette_et_variante(pos)   # sur une étiquette : la molette règle la cote
            return
        if event.button() != Qt.MouseButton.LeftButton:
            return
        self._press_pos = pos
        self._geste = False
        if self.outil == "selection":
            self._presser_selection(pos)
        elif self.outil == "cote" and not self._cote_elements and (el := self.etiquette_sous(pos)) is not None:
            # l'outil Cote déplace aussi les cotes posées : prise de leur étiquette (pas de leurs traits)
            self._glisse_cote = el[1]
            self._glisse_dernier = self.mapToScene(pos)
            self._glisse_actif = False
        elif self.outil in ("ligne", "arc", "cote", "arrondi", "chanfrein"):
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
        if genre == "brut":
            return                              # les cotes du brut ne se sélectionnent pas : double-clic ou molette
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

    # -- outil Cote : le type se déduit des éléments cliqués et de l'endroit où l'on pose la cote ----------

    def est_horizontale(self, ligne_id: int) -> bool:
        e = self.esquisse
        if any(r.type == TypeRelation.HORIZONTAL for r in e.relations_de(ligne_id)):
            return True
        a, b = (e.points[i] for i in e.extremites(ligne_id))
        return abs(a.x - b.x) < 1e-6

    def est_verticale(self, ligne_id: int) -> bool:
        e = self.esquisse
        if any(r.type == TypeRelation.VERTICAL for r in e.relations_de(ligne_id)):
            return True
        a, b = (e.points[i] for i in e.extremites(ligne_id))
        return abs(a.z - b.z) < 1e-6

    def _decalage_normal(self, a, b, z: float, x: float) -> Tuple[float, float]:
        """Décalage d'une cote de distance : projection du curseur sur la normale (même convention que le dessin)."""
        vz, vx = b.z - a.z, b.x - a.x
        n = math.hypot(vz, vx) or 1.0
        nz, nx = -vx / n, vz / n
        if nx < 0:
            nz, nx = -nz, -nx
        mz, mx = (a.z + b.z) / 2, (a.x + b.x) / 2
        return (0.0, (z - mz) * nz + (x - mx) * nx)

    def deduire_cote(self, elements, pos=None) -> Optional[Tuple[TypeCote, Tuple[int, ...], Tuple[float, float]]]:
        """(type, éléments, décalage) de la cote que poseraient ces éléments, le curseur en `pos`.

        Sans `pos`, placement par défaut. None si la combinaison n'a pas de cote.
        """
        e = self.esquisse
        elements = tuple(elements)
        genres = [e.genre(i) for i in elements]
        if pos is None:
            z = x = None
        else:
            z, x = self.position_scene(pos)
        d = self.px_en_mm(34)

        if genres == ["arc"]:
            mz, mx = self._points_arc(elements[0], 2)[1]
            dec = (d * 0.6, d * 0.6) if z is None else (z - mz, x - mx)
            return TypeCote.RAYON, elements, dec
        if genres == ["point"]:
            p = e.points[elements[0]]
            # à côté du point : diamètre ; au-dessus ou au-dessous : position Z depuis l'origine de la pièce
            if abs(p.x) < 1e-9 or (z is not None and abs(x - p.x) >= abs(z - p.z)):
                dec = (0.0, d) if z is None else (z - p.z / 2, x - p.x)
                return TypeCote.POSITION_Z, elements, dec
            dec = (d, 0.0) if z is None else (z - p.z, x - p.x / 2)
            return TypeCote.DIAMETRE, elements, dec
        if genres == ["ligne"]:
            li = e.lignes[elements[0]]
            a, b = e.points[li.p1], e.points[li.p2]
            horizontale, verticale = self.est_horizontale(li.id), self.est_verticale(li.id)
            if z is None:
                famille = "dessus"
                dz_hors = dx_hors = 0.0
            else:
                zmin, zmax = sorted((a.z, b.z))
                xmin, xmax = sorted((a.x, b.x))
                dz_hors = max(0.0, zmin - z, z - zmax)
                dx_hors = max(0.0, xmin - x, x - xmax)
                famille = "cote" if (verticale or dz_hors > dx_hors) else "dessus"
            if verticale:
                # une face : posée au-dessus ou au-dessous, sa position Z depuis l'origine ; à côté, sa hauteur
                if z is None or dx_hors > 0.0:
                    haut = max(a.x, b.x)
                    dec = (0.0, d) if z is None else (z - a.z / 2, x - haut)
                    return TypeCote.POSITION_Z, elements, dec
                return TypeCote.DISTANCE, elements, self._decalage_normal(a, b, z, x)
            if famille == "dessus":
                dec = (0.0, d) if z is None else (z - (a.z + b.z) / 2, x - max(a.x, b.x))
                return TypeCote.LONGUEUR_Z, elements, dec
            if horizontale:
                dec = (d, 0.0) if z is None else (z - a.z, x - a.x / 2)
                return TypeCote.DIAMETRE, elements, dec
            mz, mx = (a.z + b.z) / 2, (a.x + b.x) / 2
            dec = (d * 0.6, d * 0.6) if z is None else (z - mz, x - mx)
            return TypeCote.ANGLE, elements, dec
        if genres == ["ligne", "ligne"]:
            l1, l2 = (e.lignes[i] for i in elements)
            if self.est_verticale(l1.id) and self.est_verticale(l2.id):
                p, q = e.points[l1.p1], e.points[l2.p1]
                if abs(p.z - q.z) < 1e-9:
                    return None
                pts = (l1.p1, l2.p1)
                dec = (0.0, d) if z is None else (z - (p.z + q.z) / 2, x - max(p.x, q.x))
                return TypeCote.LONGUEUR_Z, pts, dec
            a1 = e.angle_ligne(l1.id) % 180.0
            a2 = e.angle_ligne(l2.id) % 180.0
            paralleles = (self.est_horizontale(l1.id) and self.est_horizontale(l2.id)) \
                or abs(a1 - a2) < 1e-6 or abs(abs(a1 - a2) - 180.0) < 1e-6
            if paralleles:
                # écart entre deux lignes parallèles (profondeur de gorge, épaulement…), glissé le long de la première
                m = self._milieu(l1.id)
                dec = (0.0, 0.0) if z is None else (z - m[0], x - m[1])
                return TypeCote.ECART, elements, dec
            commun = {l1.p1, l1.p2} & {l2.p1, l2.p2}
            if commun:
                p = e.points[commun.pop()]
                mz, mx = p.z, p.x
            else:
                m1, m2 = self._milieu(l1.id), self._milieu(l2.id)
                mz, mx = (m1[0] + m2[0]) / 2, (m1[1] + m2[1]) / 2
            dec = (d * 0.6, d * 0.6) if z is None else (z - mz, x - mx)
            return TypeCote.ANGLE, elements, dec
        if genres == ["point", "point"]:
            p, q = (e.points[i] for i in elements)
            if abs(p.z - q.z) < 1e-9:
                dec = (0.0, d) if z is None else self._decalage_normal(p, q, z, x)
                return TypeCote.DISTANCE, elements, dec
            dec = (0.0, d) if z is None else (z - (p.z + q.z) / 2, x - max(p.x, q.x))
            return TypeCote.LONGUEUR_Z, elements, dec
        return None

    def cotes_possibles(self, elements) -> List[Tuple[TypeCote, Tuple[int, ...], Tuple[float, float]]]:
        """Toutes les cotes que ces éléments peuvent porter, la déduction par défaut en premier (menu contextuel)."""
        e = self.esquisse
        elements = tuple(elements)
        genres = [e.genre(i) for i in elements]
        d = self.px_en_mm(34)
        candidats: List[Tuple[TypeCote, Tuple[int, ...], Tuple[float, float]]] = []
        defaut = self.deduire_cote(elements)
        if defaut is not None:
            candidats.append(defaut)
        if genres == ["ligne"]:
            li = e.lignes[elements[0]]
            a, b = e.points[li.p1], e.points[li.p2]
            if self.est_horizontale(li.id):
                candidats.append((TypeCote.DIAMETRE, elements, (d, 0.0)))       # diamètre par rapport à l'axe Z
                candidats.append((TypeCote.LONGUEUR_Z, elements, (0.0, d)))
            elif self.est_verticale(li.id):
                candidats.append((TypeCote.POSITION_Z, elements, (0.0, d)))
                candidats.append((TypeCote.DISTANCE, elements, (0.0, d)))
            else:
                candidats.append((TypeCote.LONGUEUR_Z, elements, (0.0, d)))
                candidats.append((TypeCote.ANGLE, elements, (d * 0.6, d * 0.6)))
                candidats.append((TypeCote.DISTANCE, elements, (0.0, d)))
        elif genres == ["point"]:
            p = e.points[elements[0]]
            if abs(p.x) > 1e-9:
                candidats.append((TypeCote.DIAMETRE, elements, (d, 0.0)))
            candidats.append((TypeCote.POSITION_Z, elements, (0.0, d)))
        elif genres == ["point", "point"]:
            candidats.append((TypeCote.LONGUEUR_Z, elements, (0.0, d)))
            candidats.append((TypeCote.DISTANCE, elements, (0.0, d)))
        vus = set()
        uniques = []
        for t, els, dec in candidats:
            if t not in vus and e.cote_possible(t, els):
                vus.add(t)
                uniques.append((t, els, dec))
        return uniques

    def _presser_cote(self, pos) -> None:
        # la géométrie seule : une étiquette de cote déjà posée ne doit pas cacher la ligne que l'on vise
        el = self.element_sous(pos, genres=("point", "ligne", "arc"))
        if el is not None and el[1] not in self._cote_elements:
            if len(self._cote_elements) >= 2:
                self.message.emit("Cote : deux éléments au plus. Cliquez où poser la cote, ou Échap.")
                return
            candidats = self._cote_elements + [el[1]]
            if len(candidats) == 2 and self.deduire_cote(candidats, pos) is None:
                self.message.emit("Cote : pas de cote entre ces deux éléments. Cliquez où poser la cote du premier.")
                return
            self._cote_elements = candidats
            self._aide()
            self._dessiner_apercu(Accroche(*self.position_scene(pos)))
            return
        if not self._cote_elements:
            return
        deduction = self.deduire_cote(self._cote_elements, pos)
        if deduction is None:
            self.message.emit("Cote : combinaison sans cote. Échap pour recommencer.")
            return
        type_, elements, decalage = deduction
        self._cote_elements = []
        self._dessiner_apercu(None)
        self.controleur.poser_cote(type_, elements, decalage)
        self._aide()

    def _presser_coin(self, pos) -> None:
        """Arrondi ou chanfrein : le clic désigne le sommet, la fenêtre demande la valeur et modifie le modèle."""
        el = self.element_sous(pos, genres=("point",))
        if el is None:
            self.message.emit("Cliquez un sommet entre deux lignes.")
            return
        if self.outil == "arrondi":
            self.controleur.arrondir(el[1])
        else:
            self.controleur.chanfreiner(el[1])
        self._aide()

    def _apercu_cote(self, curseur: Optional[Accroche], c: Dict[str, QColor]) -> None:
        e = self.esquisse
        surbrillance = QPen(QColor(c["selection"].red(), c["selection"].green(), c["selection"].blue(), 120), 7)
        surbrillance.setCosmetic(True)
        surbrillance.setCapStyle(Qt.PenCapStyle.RoundCap)
        for ident in self._cote_elements:
            g = e.genre(ident)
            if g == "ligne":
                a, b = (e.points[i] for i in e.extremites(ident))
                it = QGraphicsLineItem(a.z, a.x, b.z, b.x)
            elif g == "arc":
                path = QPainterPath()
                pts = self._points_arc(ident, 48)
                path.moveTo(*pts[0])
                for z, x in pts[1:]:
                    path.lineTo(z, x)
                it = QGraphicsPathItem(path)
            elif g == "point":
                p = e.points[ident]
                it = QGraphicsEllipseItem(-6, -6, 12, 12)
                it.setPos(p.z, p.x)
                it.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True)
            else:
                continue
            it.setPen(surbrillance)
            self._ajouter_apercu(it, 2)
        if curseur is None:
            return
        pos = self.mapFromScene(QPointF(curseur.z, curseur.x))
        deduction = self.deduire_cote(self._cote_elements, pos)
        if deduction is None:
            return
        type_, elements, decalage = deduction
        try:
            valeur = e.mesurer(type_, elements)
        except Exception:
            return
        provisoire = Cote(-1, type_, elements, valeur, decalage)
        self._dessiner_cote(provisoire, c["cote"], c, apercu=True)

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
        elif self.outil == "cote":
            self._dessiner_apercu(Accroche(z, x))

    def mouseReleaseEvent(self, event) -> None:
        pos = event.position().toPoint()
        if event.button() == Qt.MouseButton.MiddleButton:
            self._pan_dernier = None
            self.appliquer_curseur()
            return
        if event.button() == Qt.MouseButton.RightButton:
            self._droit_cote = None
            self.controleur.fin_ajustement()
            if self._droit_molette:
                self._droit_molette = False     # la molette a servi (outil ou cote) : pas de menu
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
        etiquette_prise = self._glisse_cote is not None
        if self.outil == "ligne" and not self._a_bouge(pos):
            self._presser_ligne(pos)
        elif self.outil == "arc" and not self._a_bouge(pos):
            self._presser_arc(pos)
        elif self.outil == "cote" and not etiquette_prise and not self._a_bouge(pos):
            self._presser_cote(pos)
        elif self.outil in ("arrondi", "chanfrein") and not self._a_bouge(pos):
            self._presser_coin(pos)
        self._press_pos = None
        if self._glisse_point is not None:
            if self._glisse_actif:
                self.controleur.fin_glissement()
            else:
                self.selectionner(self._glisse_point, ajouter=True)
            self._glisse_point = None
            self._glisse_actif = False
        if self._glisse_cote is not None:
            if not self._glisse_actif and self.outil == "selection":
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
        if event.button() != Qt.MouseButton.LeftButton or self.outil not in ("selection", "cote"):
            return
        pos = event.position().toPoint()
        el = self.element_sous(pos)
        if el is not None and el[0] == "brut":
            self.controleur.editer_brut(el[1])
            return
        if el is not None and el[0] == "cote":
            self._glisse_cote = None
            variante = next((it.data(ROLE_VARIANTE) for it in self.items(pos)
                             if isinstance(it, Etiquette) and it.data(ROLE_ID) == el[1] and it.data(ROLE_VARIANTE)), None)
            self.controleur.editer_cote(el[1], variante or "valeur")

    def wheelEvent(self, event) -> None:
        delta = event.angleDelta().y()
        if delta == 0:
            return
        if event.buttons() & Qt.MouseButton.RightButton:
            self._droit_molette = True
            pos = event.position().toPoint()
            if self._droit_cote is not None:
                # clic droit maintenu sur une étiquette de cote + molette : la valeur monte ou descend
                cote_id, variante = self._droit_cote
                fin = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
                if variante == "brut":
                    texte = self.controleur.ajuster_brut(cote_id, 1 if delta > 0 else -1, fin)
                else:
                    texte = self.controleur.ajuster_cote(cote_id, 1 if delta > 0 else -1, variante, fin)
                if texte:
                    self._montrer_texte(texte, pos)
            else:
                # sinon, cycle des outils : Sélection -> Ligne -> Arc -> Cote -> Arrondi -> Chanfrein -> Élaguer
                self.cycler_outil(1 if delta < 0 else -1, pos)
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
        self.placer_superposition()
        self.reconstruire()
