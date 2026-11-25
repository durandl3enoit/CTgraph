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
        """Vue de dessus, l'outil couché à l'horizontale, la queue toujours rectangulaire.

        La plaquette est au bout gauche dans tous les cas ; c'est sa position en hauteur qui dit la main :
        **en bas pour un outil à droite**, débordant vers le bas et vers la gauche, **en haut pour un
        outil à gauche**, débordant vers le haut et vers la gauche.
        """
        marge_g, marge_d = 62.0, 14.0      # place devant la pointe pour l'arc d'attaque et sa valeur
        hauteur_utile = zone.height() - 42
        k = min((zone.width() - marge_g - marge_d) / max(pp.longueur, 1.0),
                hauteur_utile / max(pp.queue_mm * 2.3, 1.0))
        k = max(k, 0.2)
        lg, larg = pp.longueur * k, pp.queue_mm * k
        gauche = pp.main == "gauche"
        cote_v = 1.0 if gauche else -1.0   # le corps de la plaquette s'enfonce vers le bas (gauche) ou le haut (droite)
        cote_dessus = not gauche and pp.main != "neutre"   # la cote de longueur va à l'opposé de la plaquette
        x0 = zone.left() + marge_g
        y_milieu = zone.top() + zone.height() * 0.52
        y_haut, y_bas = y_milieu - larg / 2.0, y_milieu + larg / 2.0
        # le coin de la queue où s'appuie la plaquette : en bas à gauche à droite, en haut à gauche à gauche
        ancre = QPointF(x0, y_haut if gauche else y_bas)
        if pp.main == "neutre":
            ancre = QPointF(x0, y_milieu)

        # la queue : un rectangle, toujours
        p.setPen(QPen(encre, 1.5))
        p.setBrush(QBrush(remplissage))
        p.drawRect(QRectF(x0, y_haut, lg, larg))
        if pp.cylindrique:
            p.setPen(QPen(muet, 1.0, Qt.PenStyle.DashDotLine))
            p.drawLine(QPointF(x0 - 12, y_milieu), QPointF(x0 + lg + 6, y_milieu))

        # arête principale : depuis la pointe, à l'angle d'attaque du sens d'avance (vers la gauche)
        attaque = pp.attaque if pp.attaque is not None else 90.0
        voulue = (-math.cos(math.radians(attaque)), cote_v * math.sin(math.radians(attaque)))
        plaquette, pointe_locale, arete = self._contour_plaquette(pp, k, voulue, cote_v,
                                                                  pp.main == "neutre")
        # la plaquette déborde largement de la queue : son centre est posé sur le coin
        plaquette = [(ancre.x() + u, ancre.y() + v) for u, v in plaquette]
        pointe = QPointF(ancre.x() + pointe_locale[0], ancre.y() + pointe_locale[1])
        p.setPen(QPen(cote, 1.4))
        p.setBrush(QBrush(QColor(cote.red(), cote.green(), cote.blue(), 60)))
        if plaquette:
            p.drawPolygon([QPointF(u, v) for u, v in plaquette])

        if pp.attaque is not None:
            trait = max(larg * 0.6, 15.0)
            p.setPen(QPen(cote, 1.6))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawLine(pointe, QPointF(pointe.x() + arete[0] * trait, pointe.y() + arete[1] * trait))
            p.setPen(QPen(muet, 1.0, Qt.PenStyle.DashLine))
            p.drawLine(pointe, QPointF(pointe.x() - trait - 12, pointe.y()))
            p.setPen(QPen(cote, 1.2))
            r_arc = max(larg * 0.42, 12.0)
            # l'arc va du sens d'avance (180° dans le repère de Qt, y vers le haut) jusqu'à l'arête
            # elle-même, par le plus court chemin : il se pose donc du bon côté, quelle que soit la main
            angle_arete = math.degrees(math.atan2(-arete[1], arete[0]))
            balayage = (angle_arete - 180.0 + 180.0) % 360.0 - 180.0
            p.drawArc(QRectF(pointe.x() - r_arc, pointe.y() - r_arc, 2 * r_arc, 2 * r_arc),
                      180 * 16, int(balayage * 16))
            p.setPen(QPen(cote))
            y_texte = pointe.y() + 3 if balayage > 0 else pointe.y() - 18
            p.drawText(QRectF(zone.left(), y_texte, marge_g - 6, 14),
                       int(Qt.AlignmentFlag.AlignRight), f"κr {pp.texte_attaque}")

        # alésage minimal d'une barre : le plus petit trou où elle passe
        if pp.alesage_mini:
            r = pp.alesage_mini / 2.0 * k
            centre = QPointF(x0 + max(larg * 0.4, 6.0) + r, y_milieu)
            p.setPen(QPen(muet, 1.0, Qt.PenStyle.DashLine))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(centre, r, r)
            p.setPen(QPen(muet))
            y_alesage = y_bas + 4 if cote_dessus else y_haut - 17
            p.drawText(QRectF(zone.left(), y_alesage, zone.width() - 4, 14),
                       int(Qt.AlignmentFlag.AlignRight), f"alésage mini {pp.nombre(pp.alesage_mini)}")

        # cote de longueur du côté opposé à la plaquette : c'est là qu'il reste de la place
        y_cote = max(y_haut - 22, zone.top() + 18) if cote_dessus else min(y_bas + 22, zone.bottom() - 32)
        self._coter(p, QPointF(x0, y_cote), QPointF(x0 + lg, y_cote), f"l1 {pp.nombre(pp.longueur)}", cote,
                    texte_dessous=not cote_dessus)
        if pp.main == "neutre":
            legende = "outil neutre — pointe en avant, dans l'axe"
        else:
            legende = f"outil à {pp.main} — plaquette en {'haut' if gauche else 'bas'} à gauche"
        p.setPen(QPen(muet))
        p.drawText(QRectF(zone.left(), zone.bottom() - 15, zone.width(), 14),
                   int(Qt.AlignmentFlag.AlignHCenter), legende)

    @staticmethod
    def _contour_plaquette(pp, k: float, voulue, cote_v: float, neutre: bool = False):
        """(contour, pointe, arête) de la plaquette, en pixels relatifs au coin de queue où elle s'appuie.

        Le coin actif est en avant, une arête suit l'arête principale, le corps rentre dans la queue (vers
        le haut pour un outil à droite, vers le bas pour un outil à gauche). Le contour est centré sur le
        coin : la plaquette déborde largement. **Sur un outil neutre, c'est la bissectrice du coin qui
        pointe droit devant** : la pointe fine darde vers l'extérieur, symétriquement.
        """
        tailles = pour_base(pp.plaquette)
        cercle = tailles[0].cercle_inscrit if tailles else max(pp.queue_mm * 0.5, 6.0)
        forme = {"filetage": "T", "lame": "S", "gorge": "S"}.get(pp.forme, pp.forme)

        if forme == "R":
            rayon = cercle / 2.0 * k
            points = [(rayon * math.cos(2 * math.pi * j / 20), rayon * math.sin(2 * math.pi * j / 20))
                      for j in range(20)]
            return points, (-rayon * 0.7, cote_v * rayon * 0.7), voulue

        rayon = cercle / 2.0 / max(rayon_inscrit(forme), 1e-6) * k
        sommets = sommets_forme(forme, rayon)
        if not sommets:
            return [], (0.0, 0.0), voulue
        i = coin_actif(sommets)
        voisins = ((i + 1) % len(sommets), (i - 1) % len(sommets))

        def tourner(rot):
            cos, sin = math.cos(rot), math.sin(rot)
            return [((z - sommets[i][0]) * cos - (x - sommets[i][1]) * sin,
                     (z - sommets[i][0]) * sin + (x - sommets[i][1]) * cos) for z, x in sommets]

        if neutre:
            # bissectrice du coin actif, dirigée vers l'extérieur de la plaquette, amenée sur −u
            bras = []
            for v in voisins:
                d = (sommets[v][0] - sommets[i][0], sommets[v][1] - sommets[i][1])
                n = max(math.hypot(*d), 1e-9)
                bras.append((d[0] / n, d[1] / n))
            dehors = (-(bras[0][0] + bras[1][0]), -(bras[0][1] + bras[1][1]))
            rot = math.pi - math.atan2(dehors[1], dehors[0])
            places = tourner(rot)
            d = (places[voisins[0]][0], places[voisins[0]][1])
            arete = (d[0] / max(math.hypot(*d), 1e-9), d[1] / max(math.hypot(*d), 1e-9))
        else:
            # des deux arêtes du coin actif, une seule laisse le corps du bon côté : vers la queue, et
            # vers le dos de l'outil. On regarde de quel côté tombe le centre de la plaquette.
            dedans = (1.0, -cote_v)
            meilleur = None
            for v in voisins:
                d = (sommets[v][0] - sommets[i][0], sommets[v][1] - sommets[i][1])
                candidat = tourner(math.atan2(voulue[1], voulue[0]) - math.atan2(d[1], d[0]))
                centre = (sum(u for u, _ in candidat) / len(candidat),
                          sum(w for _, w in candidat) / len(candidat))
                score = centre[0] * dedans[0] + centre[1] * dedans[1]
                if meilleur is None or score > meilleur[0]:
                    meilleur = (score, candidat)
            places, arete = meilleur[1], voulue

        milieu = (sum(u for u, _ in places) / len(places), sum(v for _, v in places) / len(places))
        # on pose le centre de la plaquette sur le coin de la queue : la pointe passe dehors
        points = [(u - milieu[0], v - milieu[1]) for u, v in places]
        return points, (-milieu[0], -milieu[1]), arete

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
    def _coter(p, a: QPointF, b: QPointF, texte: str, couleur, texte_dessous: bool = False) -> None:
        p.setPen(QPen(couleur, 1.1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawLine(a, b)
        for q in (a, b):
            p.drawLine(QPointF(q.x(), q.y() - 3), QPointF(q.x(), q.y() + 3))
        p.drawText(QRectF((a.x() + b.x()) / 2 - 50, a.y() + (3 if texte_dessous else -16), 100, 14),
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
