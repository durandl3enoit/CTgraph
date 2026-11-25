"""Volet « Stock d'outils » : les porte-plaquettes montables sur les porte-outils VDI 30 du CT200.

Il liste le catalogue de `ctgraph.outils`, rangé par famille, avec un filtre et une case « en stock » par
référence : le catalogue dit ce qui est montable, les cases disent ce que l'atelier possède (mémorisé dans
les préférences).
"""
from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Set

import math

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPalette, QPen
from PySide6.QtWidgets import (QCheckBox, QHBoxLayout, QLabel, QLineEdit, QSizePolicy, QTreeWidgetItem,
                               QVBoxLayout, QWidget)

from ..icons import icone_plaquette
from ..outils import CATALOGUE, FAMILLES, FORMES_PLAQUETTE, QUEUE_MAXI, PortePlaquette, filtrer
from ..plaquettes import coin_actif, pour_base, rayon_inscrit, sommets_forme
from .transfert import MIME_PORTE_PLAQUETTE, ArbreGlissable
from .volet_lateral import HAUTEUR_DESSIN

COLONNES = ["Désignation", "Plaquette", "Attaque", "Queue", "Fixation"]
ROLE_DESIGNATION = Qt.ItemDataRole.UserRole


def _enveloppe(points: List[tuple]) -> List[tuple]:
    """Enveloppe convexe d'un nuage de points (parcours monotone d'Andrew), dans l'ordre du contour."""
    pts = sorted(set((round(u, 4), round(v, 4)) for u, v in points))
    if len(pts) < 3:
        return pts

    def demi(suite):
        pile = []
        for q in suite:
            while len(pile) >= 2 and ((pile[-1][0] - pile[-2][0]) * (q[1] - pile[-2][1])
                                      - (pile[-1][1] - pile[-2][1]) * (q[0] - pile[-2][0])) <= 0:
                pile.pop()
            pile.append(q)
        return pile[:-1]

    return demi(pts) + demi(reversed(pts))


class DessinPorteOutil(QWidget):
    """Le porte-plaquette choisi, vu de dessus et en coupe de queue, avec ses cotes portées sur le dessin."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.outil: Optional[PortePlaquette] = None
        self.setFixedHeight(HAUTEUR_DESSIN)      # même hauteur que le dessin de la plaquette : les deux s'alignent
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def definir(self, outil: Optional[PortePlaquette]) -> None:
        self.outil = outil
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        pal = self.palette()
        encre = pal.color(QPalette.ColorGroup.Active, QPalette.ColorRole.WindowText)
        fond = pal.color(QPalette.ColorGroup.Active, QPalette.ColorRole.Base)
        p.fillRect(self.rect(), fond)
        police = QFont()
        police.setPointSizeF(8.0)
        p.setFont(police)
        pp = self.outil
        if pp is None:
            p.setPen(QPen(QColor(encre.red(), encre.green(), encre.blue(), 150)))
            p.drawText(self.rect(), int(Qt.AlignmentFlag.AlignCenter),
                       "Choisissez un porte-plaquette pour le voir coté")
            p.end()
            return
        cote = QColor(110, 170, 255) if fond.lightness() < 128 else QColor(25, 95, 190)
        muet = QColor(encre.red(), encre.green(), encre.blue(), 110)
        remplissage = QColor(encre.red(), encre.green(), encre.blue(), 40)

        p.setPen(QPen(encre))
        p.drawText(QRectF(4, 1, self.width() - 8, 14), int(Qt.AlignmentFlag.AlignLeft), pp.designation)
        p.setPen(QPen(muet))
        p.drawText(QRectF(4, 1, self.width() - 8, 14), int(Qt.AlignmentFlag.AlignRight),
                   f"plaquette {pp.plaquette}")

        largeur_vue = self.width() * 0.72
        self._dessiner_dessus(p, pp, QRectF(6, 18, largeur_vue - 12, self.height() - 24),
                              encre, cote, muet, remplissage)
        self._dessiner_section(p, pp, QRectF(largeur_vue, 18, self.width() - largeur_vue - 6,
                                             self.height() - 24), encre, cote, muet, remplissage)
        p.end()

    def _dessiner_dessus(self, p, pp, zone, encre, cote, muet, remplissage) -> None:
        """Vue de dessus : la queue, la plaquette assise au bout, l'angle d'attaque.

        Repère local : la pointe de l'outil à l'origine, la queue vers les u positifs, le côté qui coupe
        en v = 0. Un outil à gauche est le miroir d'un outil à droite : on retourne le repère, et la
        pointe passe à droite. C'est ce qui distingue les deux versions d'un coup d'œil.
        """
        marge = 62.0        # place pour l'arête, l'arc d'attaque et sa valeur, devant la pointe
        k = min((zone.width() - marge - 16) / max(pp.longueur, 1.0),
                (zone.height() - 52) / max(pp.queue_mm * 2.0, 1.0))
        k = max(k, 0.2)
        lg, larg = pp.longueur * k, pp.queue_mm * k
        gauche = pp.main == "gauche"
        sens = -1.0 if gauche else 1.0
        x_pointe = zone.right() - marge if gauche else zone.left() + marge
        v_tranchant = larg / 2.0 if pp.main == "neutre" else 0.0
        y_tranchant = zone.top() + 14.0 + v_tranchant

        def ecran(u_px: float, v_px: float) -> QPointF:
            """Du repère local, déjà en pixels, vers la zone : u vers la queue, v vers le dos de l'outil."""
            return QPointF(x_pointe + sens * u_px, y_tranchant - v_tranchant + v_px)

        pointe = ecran(0.0, 0.0)
        # arête principale : elle part de la pointe en faisant l'angle d'attaque avec le sens d'avance
        attaque = pp.attaque if pp.attaque is not None else 90.0
        arete = (-math.cos(math.radians(attaque)), math.sin(math.radians(attaque)))   # repère local, v vers le bas

        # la plaquette, posée : son coin actif sur la pointe, une arête le long de l'arête principale
        plaquette = self._contour_plaquette(pp, k, larg, arete)
        # corps de l'outil : la queue, et la tête qui enveloppe la plaquette. Sur un outil à 45°, la
        # plaquette déborde du profil de la queue : la tête est taillée pour la recevoir.
        queue = [(0.0, 0.0), (lg, 0.0), (lg, larg), (0.0, larg)]
        corps = _enveloppe(queue + [q for q in plaquette if q[0] < lg * 0.5])
        p.setPen(QPen(encre, 1.5))
        p.setBrush(QBrush(remplissage))
        p.drawPolygon([ecran(u, v) for u, v in corps])
        if pp.cylindrique:
            p.setPen(QPen(muet, 1.0, Qt.PenStyle.DashDotLine))
            p.drawLine(ecran(-10.0, larg / 2.0), ecran(lg + 6.0, larg / 2.0))
        p.setPen(QPen(cote, 1.4))
        p.setBrush(QBrush(QColor(cote.red(), cote.green(), cote.blue(), 60)))
        if plaquette:
            p.drawPolygon([ecran(u, v) for u, v in plaquette])

        if pp.attaque is not None:
            longueur_trait = max(larg * 0.75, 16.0)
            p.setPen(QPen(cote, 1.6))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawLine(pointe, QPointF(pointe.x() + sens * arete[0] * longueur_trait,
                                       pointe.y() + arete[1] * longueur_trait))
            p.setPen(QPen(muet, 1.0, Qt.PenStyle.DashLine))
            p.drawLine(pointe, QPointF(pointe.x() - sens * (longueur_trait + 10), pointe.y()))
            p.setPen(QPen(cote, 1.2))
            r_arc = max(larg * 0.5, 13.0)
            depart = 0 if gauche else 180 * 16
            p.drawArc(QRectF(pointe.x() - r_arc, pointe.y() - r_arc, 2 * r_arc, 2 * r_arc),
                      depart, int(sens * attaque * 16))
            p.setPen(QPen(cote))
            x_texte = pointe.x() + 8 if gauche else zone.left()
            p.drawText(QRectF(x_texte, pointe.y() - 18, marge - 8, 14),
                       int(Qt.AlignmentFlag.AlignLeft if gauche else Qt.AlignmentFlag.AlignRight),
                       f"κr {pp.texte_attaque}")

        # alésage minimal d'une barre : le plus petit trou où elle passe
        if pp.alesage_mini:
            r = pp.alesage_mini / 2.0 * k
            centre = ecran(max(larg * 0.4, 6.0) + r, larg / 2.0)
            p.setPen(QPen(muet, 1.0, Qt.PenStyle.DashLine))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(centre, r, r)
            p.setPen(QPen(muet))
            p.drawText(QRectF(centre.x() - 70, centre.y() + r + 2, 140, 14),
                       int(Qt.AlignmentFlag.AlignHCenter), f"alésage mini {pp.nombre(pp.alesage_mini)}")

        # cote de longueur sous le corps
        y_cote = min(ecran(0.0, larg).y() + 22, zone.bottom() - 4)
        self._coter(p, QPointF(ecran(0.0, 0.0).x(), y_cote), QPointF(ecran(lg, 0.0).x(), y_cote),
                    f"l1 {pp.nombre(pp.longueur)}", cote)
        # la main, écrite : c'est elle qui décide du sens de tout le dessin
        p.setPen(QPen(muet))
        p.drawText(QRectF(zone.left(), zone.bottom() - 15, zone.width(), 14),
                   int(Qt.AlignmentFlag.AlignLeft if gauche else Qt.AlignmentFlag.AlignRight),
                   f"outil à {pp.main} — avance vers {'la droite' if gauche else 'la gauche'}")

    @staticmethod
    def _contour_plaquette(pp, k: float, larg: float, arete) -> List[tuple]:
        """Le contour de la plaquette assise dans la tête, en pixels du repère local : son coin actif sur
        la pointe, une de ses arêtes le long de l'arête principale, son corps tourné vers la queue."""
        tailles = pour_base(pp.plaquette)
        cercle = tailles[0].cercle_inscrit if tailles else max(pp.queue_mm * 0.5, 6.0)
        forme = {"filetage": "T", "lame": "S", "gorge": "S"}.get(pp.forme, pp.forme)

        if forme == "R":
            rayon = cercle / 2.0 * k
            n = (-arete[1], arete[0])                       # normale à l'arête, vers l'intérieur
            if n[1] < 0:
                n = (-n[0], -n[1])
            cx, cy = n[0] * rayon, n[1] * rayon
            return [(cx + rayon * math.cos(2 * math.pi * j / 20), cy + rayon * math.sin(2 * math.pi * j / 20))
                    for j in range(20)]

        rayon = cercle / 2.0 / max(rayon_inscrit(forme), 1e-6) * k
        sommets = sommets_forme(forme, rayon)
        if not sommets:
            return []
        i = coin_actif(sommets)
        # des deux arêtes du coin actif, une seule laisse le corps du côté de la queue : c'est celle-là.
        # On mesure de quel côté de l'arête de coupe tombe le centre de la plaquette.
        normale = (arete[1], -arete[0])
        if normale[0] < 0:
            normale = (-normale[0], -normale[1])
        meilleur = None
        for voisin in ((i + 1) % len(sommets), (i - 1) % len(sommets)):
            d = (sommets[voisin][0] - sommets[i][0], sommets[voisin][1] - sommets[i][1])
            rot = math.atan2(arete[1], arete[0]) - math.atan2(d[1], d[0])
            cos, sin = math.cos(rot), math.sin(rot)
            places = [((z - sommets[i][0]) * cos - (x - sommets[i][1]) * sin,
                       (z - sommets[i][0]) * sin + (x - sommets[i][1]) * cos) for z, x in sommets]
            milieu = (sum(u for u, _ in places) / len(places), sum(v for _, v in places) / len(places))
            score = milieu[0] * normale[0] + milieu[1] * normale[1]
            if meilleur is None or score > meilleur[0]:
                meilleur = (score, places)
        return meilleur[1] if meilleur is not None else []

    def _dessiner_section(self, p, pp, zone, encre, cote, muet, remplissage) -> None:
        """Section de la queue : carrée h × b, ou ronde Ø d, avec sa cote."""
        cote_section = min(zone.width() - 18, zone.height() - 34, 58.0)
        cx, cy = zone.center().x(), zone.center().y() - 6
        p.setPen(QPen(encre, 1.5))
        p.setBrush(QBrush(remplissage))
        if pp.cylindrique:
            p.drawEllipse(QPointF(cx, cy), cote_section / 2.0, cote_section / 2.0)
            texte = f"d Ø {pp.nombre(pp.queue_mm)}"
        else:
            p.drawRect(QRectF(cx - cote_section / 2.0, cy - cote_section / 2.0, cote_section, cote_section))
            texte = f"h × b  {pp.nombre(pp.queue_mm)} × {pp.nombre(pp.queue_mm)}"
        p.setPen(QPen(cote))
        p.drawText(QRectF(zone.left(), cy + cote_section / 2.0 + 6, zone.width(), 14),
                   int(Qt.AlignmentFlag.AlignHCenter), texte)
        p.setPen(QPen(muet))
        p.drawText(QRectF(zone.left(), cy + cote_section / 2.0 + 20, zone.width(), 14),
                   int(Qt.AlignmentFlag.AlignHCenter), "section de queue")

    @staticmethod
    def _coter(p, a: QPointF, b: QPointF, texte: str, couleur) -> None:
        p.setPen(QPen(couleur, 1.1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawLine(a, b)
        for q in (a, b):
            p.drawLine(QPointF(q.x(), q.y() - 3), QPointF(q.x(), q.y() + 3))
        p.drawText(QRectF((a.x() + b.x()) / 2 - 50, a.y() - 15, 100, 14),
                   int(Qt.AlignmentFlag.AlignCenter), texte)


class ZoneOutils(QWidget):
    """Le catalogue des porte-plaquettes, filtrable, avec les cases « en stock »."""

    stock_change = Signal(object)        # l'ensemble des désignations cochées

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(510)
        self._stock: Set[str] = set()
        self._blocage = False
        # une icône par forme de plaquette, dessinée une fois : le filtre reconstruit la liste à chaque frappe
        pal = self.palette()
        encre = pal.color(QPalette.ColorGroup.Active, QPalette.ColorRole.Text)
        fond = pal.color(QPalette.ColorGroup.Active, QPalette.ColorRole.Base)
        self._icones = {forme: icone_plaquette(forme, encre, fond) for forme in FORMES_PLAQUETTE}

        v = QVBoxLayout(self)
        v.setContentsMargins(6, 6, 6, 6)
        v.setSpacing(5)

        entete = QLabel(f"Porte-plaquettes montables sur porte-outils VDI 30 : queue de {QUEUE_MAXI:g} mm au plus. "
                        "Cochez ce que l'atelier possède, tirez une ligne sur la tourelle pour l'y monter.")
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

        self.arbre = ArbreGlissable(MIME_PORTE_PLAQUETTE, ROLE_DESIGNATION)
        self.arbre.setToolTip("Tirez une ligne sur la tourelle pour monter l'outil sur un poste.")
        self.arbre.setColumnCount(len(COLONNES))
        self.arbre.setHeaderLabels(COLONNES)
        self.arbre.setRootIsDecorated(True)
        self.arbre.setIndentation(12)
        self.arbre.setUniformRowHeights(True)
        self.arbre.setAlternatingRowColors(True)
        self.arbre.setIconSize(QSize(18, 18))
        self.arbre.itemChanged.connect(self._case_changee)
        self.arbre.currentItemChanged.connect(self._choix_change)
        v.addWidget(self.arbre, 1)

        self.dessin = DessinPorteOutil(self)
        v.addWidget(self.dessin)
        self.lbl_total = QLabel("")
        self.lbl_total.setWordWrap(True)
        v.addWidget(self.lbl_total)
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
                it.setFlags(ArbreGlissable.FLAGS_LIGNE)
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

    def _outil(self, designation: str) -> Optional[PortePlaquette]:
        return next((pp for pp in CATALOGUE if pp.designation == designation), None)

    def _choix_change(self, item: Optional[QTreeWidgetItem], _precedent=None) -> None:
        designation = item.data(0, ROLE_DESIGNATION) if item is not None else None
        self.dessin.definir(self._outil(designation) if designation else None)

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
