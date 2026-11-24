"""Volet « Plaquettes » : le catalogue des plaquettes, et le dessin coté de celle que l'on choisit.

Même principe que le stock d'outils : une liste filtrable rangée par famille, une case « en stock » par
référence. En dessous, la plaquette choisie est dessinée de face et de profil, avec les grandeurs qui
servent à choisir : longueur d'arête, cercle inscrit, rayon de bec, épaisseur et angle de dépouille.
"""
from __future__ import annotations

import math
from typing import Dict, Iterable, List, Optional, Set

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPainterPath, QPalette, QPen
from PySide6.QtWidgets import (QCheckBox, QHBoxLayout, QLabel, QLineEdit, QSizePolicy, QTreeWidgetItem,
                               QVBoxLayout, QWidget)

from ..icons import icone_plaquette
from ..plaquettes import CATALOGUE, FAMILLES, FORMES_PLAQUETTE, Plaquette, filtrer, sommets_forme
from .transfert import MIME_PLAQUETTE, ArbreGlissable

COLONNES = ["Désignation", "Dépouille", "Arête", "Épaisseur", "Rayon"]
ROLE_DESIGNATION = Qt.ItemDataRole.UserRole


def _contour_arrondi(sommets, rayon: float) -> QPainterPath:
    """Le contour d'une plaquette avec ses becs arrondis : chaque coin est adouci au rayon donné."""
    path = QPainterPath()
    n = len(sommets)
    if n < 3:
        return path
    for i in range(n):
        a, v, b = sommets[(i - 1) % n], sommets[i], sommets[(i + 1) % n]
        ua = (a[0] - v[0], a[1] - v[1])
        ub = (b[0] - v[0], b[1] - v[1])
        na = max(math.hypot(*ua), 1e-9)
        nb = max(math.hypot(*ub), 1e-9)
        ua, ub = (ua[0] / na, ua[1] / na), (ub[0] / nb, ub[1] / nb)
        cos = max(-1.0, min(1.0, ua[0] * ub[0] + ua[1] * ub[1]))
        demi = math.acos(cos) / 2.0
        recul = min(rayon / max(math.tan(demi), 1e-6), na / 2.0, nb / 2.0)
        p1 = QPointF(v[0] + ua[0] * recul, v[1] + ua[1] * recul)
        p2 = QPointF(v[0] + ub[0] * recul, v[1] + ub[1] * recul)
        if i == 0:
            path.moveTo(p1)
        else:
            path.lineTo(p1)
        path.quadTo(QPointF(*v), p2)      # tangente aux deux arêtes : le bec arrondi
    path.closeSubpath()
    return path


class DessinPlaquette(QWidget):
    """La plaquette choisie, de face et de profil, avec ses cotes."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.plaquette: Optional[Plaquette] = None
        self.setMinimumHeight(185)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def legende(self) -> List[str]:
        """La ligne sous le dessin : ce que les cotes portées ne disent pas déjà."""
        pl = self.plaquette
        if pl is None:
            return []
        ligne = "négative : deux faces utilisables" if pl.depouille < 0.1 else "positive : coupe libre"
        if pl.type_iso in ("A", "G", "M", "N", "T", "W"):
            ligne += f"    type {pl.type_iso}"          # le détail du type est dans l'infobulle de la liste
        if pl.pas:
            ligne += f"    pas {pl.pas}"
        return [ligne]

    def cotes_portees(self) -> List[str]:
        """Les cotes écrites sur les éléments du dessin, dans l'ordre où elles y figurent."""
        pl = self.plaquette
        if pl is None:
            return []
        if pl.famille == "gorge":
            portees = [f"largeur {pl.texte_arete}"]
        elif pl.forme == "R":
            portees = [f"Ø {pl.texte_cercle}"]
        else:
            portees = [f"l {pl.texte_arete}", f"IC {pl.texte_cercle}"]
        return portees + [f"r {pl.texte_rayon}", f"s {pl.texte_epaisseur}", f"α {pl.texte_depouille}"]

    def definir(self, plaquette: Optional[Plaquette]) -> None:
        self.plaquette = plaquette
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
        pl = self.plaquette
        if pl is None:
            p.setPen(QPen(QColor(encre.red(), encre.green(), encre.blue(), 150)))
            p.drawText(self.rect(), int(Qt.AlignmentFlag.AlignCenter),
                       "Choisissez une plaquette pour la voir cotée")
            p.end()
            return

        cote = QColor(110, 170, 255) if fond.lightness() < 128 else QColor(25, 95, 190)
        muet = QColor(encre.red(), encre.green(), encre.blue(), 110)
        # une ligne de titre, les deux vues côte à côte, les cotes en toutes lettres dessous
        legende = self.legende()
        haut_dessins = 17.0
        bas_dessins = self.height() - 4 - 14.0 * len(legende)
        largeur_face = self.width() * 0.55
        hauteur = max(bas_dessins - haut_dessins, 40.0)
        self._dessiner_face(p, pl, QRectF(4, haut_dessins, largeur_face - 8, hauteur), encre, cote, muet)
        self._dessiner_profil(p, pl, QRectF(largeur_face + 4, haut_dessins, self.width() - largeur_face - 8,
                                            hauteur), encre, cote, muet)
        p.setPen(QPen(encre))
        p.drawText(QRectF(4, 1, self.width() - 8, 14), int(Qt.AlignmentFlag.AlignLeft), pl.designation)
        p.setPen(QPen(muet))
        p.drawText(QRectF(4, 1, self.width() - 8, 14), int(Qt.AlignmentFlag.AlignRight), pl.texte_forme)
        p.setPen(QPen(cote))
        for i, ligne in enumerate(legende):
            p.drawText(QRectF(4, bas_dessins + 14.0 * i, self.width() - 8, 14),
                       int(Qt.AlignmentFlag.AlignHCenter), ligne)
        p.end()

    def _dessiner_face(self, p: QPainter, pl: Plaquette, zone: QRectF, encre, cote, muet) -> None:
        """Vue de face : le contour avec ses becs arrondis, le cercle inscrit, le bec marqué « r »."""
        remplissage = QColor(encre.red(), encre.green(), encre.blue(), 40)
        p.save()
        p.translate(zone.center())
        p.setPen(QPen(encre, 1.5))
        p.setBrush(QBrush(remplissage))
        rayon_dessin = min(zone.width(), zone.height()) * 0.42

        if pl.famille == "gorge":
            # barrette de gorge : la largeur de coupe est la grandeur qui compte
            demi = min(rayon_dessin * 0.45, 22.0)
            haut = rayon_dessin
            k = demi * 2.0 / max(pl.arete, 0.1)
            p.drawPath(_contour_arrondi([(-demi, -haut), (demi, -haut), (demi, haut), (-demi, haut)],
                                        min(pl.rayon_bec * k, demi * 0.6)))
            bec = (demi, -haut)
            p.setPen(QPen(cote, 1.1))
            self._coter_horizontal(p, -demi, demi, -haut - 12, f"largeur {pl.texte_arete}")
        elif pl.forme == "R":
            p.drawEllipse(QPointF(0, 0), rayon_dessin, rayon_dessin)
            bec = None
            p.setPen(QPen(cote, 1.1))
            self._coter_horizontal(p, -rayon_dessin, rayon_dessin, -rayon_dessin - 12, f"Ø {pl.texte_cercle}")
        else:
            sommets = sommets_forme(pl.forme, 1.0)
            if not sommets:
                p.restore()
                return
            mm_par_unite = pl.cercle_inscrit / 2.0 / max(_rayon_inscrit(sommets), 1e-6)
            rayon_bec_dessin = pl.rayon_bec / max(mm_par_unite, 1e-6) * rayon_dessin
            points = [(z * rayon_dessin, x * rayon_dessin) for z, x in sommets]
            p.drawPath(_contour_arrondi(points, rayon_bec_dessin))
            r_inscrit = _rayon_inscrit(sommets) * rayon_dessin
            p.setPen(QPen(muet, 1.0, Qt.PenStyle.DashDotLine))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QPointF(0, 0), r_inscrit, r_inscrit)
            # le cercle inscrit porte sa valeur en son centre, l'arête la sienne le long d'un côté
            p.setPen(QPen(muet))
            p.drawText(QRectF(-40, -7, 80, 14), int(Qt.AlignmentFlag.AlignCenter), f"IC {pl.texte_cercle}")
            bec = max(points, key=lambda q: q[1])
            a, b = min(points, key=lambda q: q[0]), min(points, key=lambda q: q[1])
            p.setPen(QPen(cote, 1.2))
            milieu = QPointF((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)
            p.drawLine(QPointF(*a), QPointF(*b))
            p.drawText(QRectF(milieu.x() - 56, milieu.y() - 16, 52, 14),
                       int(Qt.AlignmentFlag.AlignRight), f"l {pl.texte_arete}")

        if bec is not None:
            # le bec, entouré : à cette échelle le rayon est minuscule, on le montre et on l'écrit
            p.setPen(QPen(cote, 1.6))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QPointF(*bec), 6.0, 6.0)
            p.drawText(QRectF(bec[0] + 7, bec[1] - 2, 60, 14), int(Qt.AlignmentFlag.AlignLeft),
                       f"r {pl.texte_rayon}")
        p.restore()

    @staticmethod
    def _coter_horizontal(p: QPainter, x1: float, x2: float, y: float, texte: str) -> None:
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawLine(QPointF(x1, y), QPointF(x2, y))
        for x in (x1, x2):
            p.drawLine(QPointF(x, y - 3), QPointF(x, y + 3))
        p.drawText(QRectF((x1 + x2) / 2 - 50, y - 16, 100, 14), int(Qt.AlignmentFlag.AlignCenter), texte)

    def _dessiner_profil(self, p: QPainter, pl: Plaquette, zone: QRectF, encre, cote, muet) -> None:
        """Vue de profil : l'épaisseur « s » et l'angle de dépouille « α », qui dit si elle se retourne."""
        remplissage = QColor(encre.red(), encre.green(), encre.blue(), 40)
        largeur = min(zone.width() * 0.42, 54.0)
        hauteur = min(zone.height() * 0.44, 48.0)
        cx, cy = zone.center().x() + 4, zone.center().y()
        recul = hauteur * math.tan(math.radians(pl.depouille))
        haut_g, haut_d = cx - largeur / 2, cx + largeur / 2
        p.setPen(QPen(encre, 1.5))
        p.setBrush(QBrush(remplissage))
        p.drawPolygon([QPointF(haut_g, cy - hauteur / 2), QPointF(haut_d, cy - hauteur / 2),
                       QPointF(haut_d - recul, cy + hauteur / 2), QPointF(haut_g + recul, cy + hauteur / 2)])
        # verticale de référence et arc de dépouille
        p.setPen(QPen(muet, 1.0, Qt.PenStyle.DashLine))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawLine(QPointF(haut_d, cy - hauteur / 2), QPointF(haut_d, cy + hauteur / 2 + 8))
        p.setPen(QPen(cote, 1.3))
        if pl.depouille > 0.1:
            p.drawArc(QRectF(haut_d - 14, cy - hauteur / 2 - 14, 28, 28), -90 * 16, -int(pl.depouille * 16))
        p.drawText(QRectF(haut_d + 4, cy - 7, 56, 14), int(Qt.AlignmentFlag.AlignLeft),
                   f"α {pl.texte_depouille}")
        self._coter(p, QPointF(haut_g - 9, cy - hauteur / 2), QPointF(haut_g - 9, cy + hauteur / 2),
                    f"s {pl.texte_epaisseur}", cote)

    @staticmethod
    def _coter(p: QPainter, a: QPointF, b: QPointF, texte: str, couleur) -> None:
        p.setPen(QPen(couleur, 1.1))
        p.drawLine(a, b)
        for q in (a, b):
            p.drawLine(QPointF(q.x() - 3, q.y()), QPointF(q.x() + 3, q.y()))
        p.drawText(QRectF(a.x() - 72, (a.y() + b.y()) / 2 - 7, 68, 14),
                   int(Qt.AlignmentFlag.AlignRight), texte)


def _rayon_inscrit(sommets) -> float:
    """Rayon du cercle inscrit d'un contour centré sur l'origine : la plus courte distance du centre à
    une arête (produit vectoriel des deux sommets, divisé par la longueur de l'arête)."""
    n = len(sommets)
    court = float("inf")
    for i in range(n):
        a, b = sommets[i], sommets[(i + 1) % n]
        lg = max(math.hypot(b[0] - a[0], b[1] - a[1]), 1e-9)
        court = min(court, abs(a[0] * b[1] - a[1] * b[0]) / lg)
    return court if court < float("inf") else 1.0


class ZonePlaquettes(QWidget):
    """Le volet : catalogue filtrable, cases « en stock », et le dessin coté de la plaquette choisie."""

    stock_change = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(380)
        self._stock: Set[str] = set()
        self._blocage = False
        pal = self.palette()
        encre = pal.color(QPalette.ColorGroup.Active, QPalette.ColorRole.Text)
        fond = pal.color(QPalette.ColorGroup.Active, QPalette.ColorRole.Base)
        self._icones = {forme: icone_plaquette(forme, encre, fond) for forme in FORMES_PLAQUETTE}

        v = QVBoxLayout(self)
        v.setContentsMargins(6, 6, 6, 6)
        v.setSpacing(5)
        entete = QLabel("Plaquettes ISO 1832 qui garnissent les porte-plaquettes du stock. Cochez ce que "
                        "l'atelier possède, tirez une ligne sur la tourelle pour l'y monter.")
        entete.setWordWrap(True)
        v.addWidget(entete)

        ligne = QHBoxLayout()
        self.filtre = QLineEdit()
        self.filtre.setPlaceholderText("Filtrer : désignation, forme, usage…")
        self.filtre.setClearButtonEnabled(True)
        self.filtre.textChanged.connect(self._remplir)
        ligne.addWidget(self.filtre, 1)
        self.case_stock = QCheckBox("En stock")
        self.case_stock.setToolTip("N'afficher que les références cochées")
        self.case_stock.toggled.connect(self._remplir)
        ligne.addWidget(self.case_stock)
        v.addLayout(ligne)

        self.arbre = ArbreGlissable(MIME_PLAQUETTE, ROLE_DESIGNATION)
        self.arbre.setToolTip("Tirez une ligne sur la tourelle pour monter la plaquette sur un poste.")
        self.arbre.setColumnCount(len(COLONNES))
        self.arbre.setHeaderLabels(COLONNES)
        self.arbre.setIndentation(12)
        self.arbre.setUniformRowHeights(True)
        self.arbre.setAlternatingRowColors(True)
        self.arbre.setIconSize(QSize(18, 18))
        self.arbre.itemChanged.connect(self._case_changee)
        self.arbre.currentItemChanged.connect(self._choix_change)
        v.addWidget(self.arbre, 1)

        self.dessin = DessinPlaquette(self)
        v.addWidget(self.dessin)
        self.lbl_total = QLabel("")
        self.lbl_total.setWordWrap(True)
        v.addWidget(self.lbl_total)
        self._remplir()

    # -- stock ---------------------------------------------------------------------------

    def stock(self) -> Set[str]:
        return set(self._stock)

    def definir_stock(self, designations: Iterable[str]) -> None:
        connues = {pl.designation for pl in CATALOGUE}
        self._stock = {str(d) for d in designations if str(d) in connues}
        self._remplir()

    # -- affichage -----------------------------------------------------------------------

    def _visibles(self) -> List[Plaquette]:
        liste = filtrer(self.filtre.text())
        if self.case_stock.isChecked():
            liste = [pl for pl in liste if pl.designation in self._stock]
        return liste

    def _remplir(self) -> None:
        self._blocage = True
        self.arbre.clear()
        groupes: Dict[str, List[Plaquette]] = {cle: [] for cle in FAMILLES}
        for pl in self._visibles():
            groupes[pl.famille].append(pl)
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
            for pl in lot:
                it = QTreeWidgetItem(parent, [pl.designation, pl.texte_depouille, pl.texte_arete,
                                              pl.texte_epaisseur, pl.texte_rayon])
                it.setFlags(ArbreGlissable.FLAGS_LIGNE)
                it.setCheckState(0, Qt.CheckState.Checked if pl.designation in self._stock
                                 else Qt.CheckState.Unchecked)
                it.setData(0, ROLE_DESIGNATION, pl.designation)
                if pl.forme in self._icones:
                    it.setIcon(0, self._icones[pl.forme])
                infobulle = pl.description()
                for col in range(len(COLONNES)):
                    it.setToolTip(col, infobulle)
        self._blocage = False
        for col in range(len(COLONNES)):
            self.arbre.resizeColumnToContents(col)
        self._compter()

    def _compter(self) -> None:
        montres = sum(self.arbre.topLevelItem(i).childCount() for i in range(self.arbre.topLevelItemCount()))
        self.lbl_total.setText(f"{montres} référence(s) affichée(s) sur {len(CATALOGUE)} — "
                               f"{len(self._stock)} en stock")

    def _plaquette(self, designation: str) -> Optional[Plaquette]:
        return next((pl for pl in CATALOGUE if pl.designation == designation), None)

    def _choix_change(self, item: Optional[QTreeWidgetItem], _precedent=None) -> None:
        designation = item.data(0, ROLE_DESIGNATION) if item is not None else None
        self.dessin.definir(self._plaquette(designation) if designation else None)

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
        self._compter()
        self.stock_change.emit(self.stock())
