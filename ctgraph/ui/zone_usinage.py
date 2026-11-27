"""Volet « Usinage » : la gamme de la pièce, séquence par séquence.

La liste donne l'ordre d'usinage ; le formulaire règle la séquence choisie, dont la trajectoire se
dessine aussitôt sur l'esquisse. Rien n'est figé : la trajectoire se recalcule depuis le profil résolu
à chaque changement de cote, de montage ou de réglage.

Chaque type d'opération n'a pas les mêmes réglages : le formulaire ne montre que ceux qui comptent
(`CHAMPS_SEQUENCE`). On affecte un poste de tourelle en tapant son numéro, ou en y glissant la
combinaison montée sur un poste, tirée du volet Tourelle. Les lignes se tirent entre elles pour changer
l'ordre d'usinage.

**La liste est le curseur d'étape.** Sa première ligne est le brut, avant tout usinage ; choisir une
ligne, c'est voir la pièce telle qu'elle est après cette opération, avec en vif ce qu'elle vient
d'enlever. Les lignes qui suivent sont grisées : elles ne sont pas encore passées.
"""
from __future__ import annotations

import math
from typing import Callable, Dict, Optional

from PySide6.QtCore import QPoint, QPointF, Qt, QTimer, Signal
from PySide6.QtGui import QBrush, QColor, QPainter, QPalette, QPen, QPolygonF
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QDoubleSpinBox, QFormLayout,
                               QFrame, QGridLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
                               QMessageBox, QPushButton, QScrollArea, QSpinBox, QTreeWidget,
                               QTreeWidgetItem, QVBoxLayout, QWidget)

from ..forets import forets
from ..tourelle import nom_poste
from ..usinage import ALESAGES, Gamme, Sequence, TypeSequence
from ..usinage.sequences import TEXTES_DIAMETRE_NUL
from ..usinage.sequences import FAMILLES_OUTIL, LIBELLES_SEQUENCE, NOMS_COURTS, USAGES_SEQUENCE
from .transfert import MIME_POSTE, MIME_SEQUENCE, accueillir, charger, lire

COLONNES = ["#", "Opération", "Poste", "Passes", "Coupe"]
ROLE_ID = Qt.ItemDataRole.UserRole
BOUTONS_PAR_RANGEE = 3


class ListeSequences(QTreeWidget):
    """La liste de la gamme, source et cible de glissers.

    On y dépose un poste de tourelle, et la séquence visée le prend. On y tire une ligne sur une autre,
    et l'ordre d'usinage change : le trait qui suit le curseur dit où la séquence va se poser.
    """

    depot = Signal(int, int)                 # identifiant de séquence, numéro de poste
    reordonne = Signal(int, int)             # identifiant de séquence, rang visé

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.viewport().setAcceptDrops(True)
        self.setDragEnabled(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.accepte_depot = lambda sequence_id, poste: False
        self._rang_cible = -1                # trait d'insertion pendant un glisser de réordonnancement

    # -- glisser une ligne pour changer l'ordre ---------------------------------------------

    def mimeTypes(self):
        return [MIME_SEQUENCE, MIME_POSTE, "text/plain"]

    def mimeData(self, items):
        for it in items:
            ident = int(it.data(0, ROLE_ID) or 0)
            if ident:
                return charger(MIME_SEQUENCE, f"{ident} {it.text(1)}")
        return charger(MIME_SEQUENCE, "")

    def rang_sous(self, point) -> int:
        """Le rang où une ligne lâchée ici viendrait se poser : avant ou après celle qu'on survole.

        Compté dans la liste, où la ligne 0 est le brut : le rang dans la gamme vaut un de moins.
        """
        it = self.itemAt(point)
        if it is None:
            return self.topLevelItemCount()
        rect = self.visualItemRect(it)
        return max(1, self.indexOfTopLevelItem(it) + (1 if point.y() > rect.center().y() else 0))

    def _y_du_rang(self, rang: int) -> int:
        if not self.topLevelItemCount():
            return 0
        if rang >= self.topLevelItemCount():
            return self.visualItemRect(self.topLevelItem(self.topLevelItemCount() - 1)).bottom()
        return self.visualItemRect(self.topLevelItem(max(rang, 0))).top()

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        if self._rang_cible < 0:
            return
        p = QPainter(self.viewport())
        y = self._y_du_rang(self._rang_cible)
        p.setPen(QPen(self.palette().color(QPalette.ColorRole.Highlight), 2))
        p.drawLine(0, y, self.viewport().width(), y)
        p.end()

    # -- accueil d'un glisser ----------------------------------------------------------------

    def sequence_sous(self, point) -> int:
        it = self.itemAt(point)
        return int(it.data(0, ROLE_ID) or 0) if it is not None else 0

    def _accepte(self, sequence_id: int, type_mime: str, charge: str) -> bool:
        return type_mime == MIME_POSTE and self.accepte_depot(sequence_id, _numero_poste(charge))

    def _marquer(self, rang: int) -> None:
        if rang != self._rang_cible:
            self._rang_cible = rang
            self.viewport().update()

    def _survoler(self, event) -> None:
        type_mime, charge = lire(event.mimeData())
        if type_mime == MIME_SEQUENCE:
            self._marquer(self.rang_sous(event.position().toPoint()))
            event.acceptProposedAction()
            return
        # la liste se reconstruit en affectant le poste : on ne touche pas à la sélection pendant le survol
        sequence_id, _, _ = accueillir(event, self.sequence_sous, self._accepte)
        if sequence_id:
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragEnterEvent(self, event) -> None:
        self._survoler(event)

    def dragMoveEvent(self, event) -> None:
        self._survoler(event)

    def dragLeaveEvent(self, event) -> None:
        self._marquer(-1)

    def dropEvent(self, event) -> None:
        type_mime, charge = lire(event.mimeData())
        if type_mime == MIME_SEQUENCE:
            rang = self.rang_sous(event.position().toPoint())
            self._marquer(-1)
            ident = _numero_tete(charge)
            if not ident:
                event.ignore()
                return
            event.acceptProposedAction()
            # la liste se reconstruit en se réordonnant : on le fait après la sortie de l'événement
            QTimer.singleShot(0, lambda: self.reordonne.emit(ident, rang))
            return
        sequence_id, _, charge = accueillir(event, self.sequence_sous, self._accepte)
        if not sequence_id:
            event.ignore()
            return
        event.acceptProposedAction()
        poste = _numero_poste(charge)
        QTimer.singleShot(0, lambda: self.depot.emit(sequence_id, poste))


class CurseurEtape(QWidget):
    """Le curseur d'étape, à droite de la liste : un trait et une poignée que l'on fait glisser.

    Il n'a pas d'état propre : la poignée se pose en face de la ligne choisie, et la tirer change la
    ligne. La liste et le curseur sont donc toujours d'accord, par construction.
    """

    LARGEUR = 18

    def __init__(self, liste: QTreeWidget, parent=None):
        super().__init__(parent)
        self.liste = liste
        self.setFixedWidth(self.LARGEUR)
        self.setCursor(Qt.CursorShape.SizeVerCursor)
        self.setToolTip("Curseur d'étape : tirez la poignée pour voir la pièce à chaque opération.")

    def _y_de(self, rang: int) -> int:
        """Le milieu de la ligne de ce rang, en coordonnées du curseur."""
        nb = self.liste.topLevelItemCount()
        if not nb:
            return self.height() // 2
        it = self.liste.topLevelItem(min(max(rang, 0), nb - 1))
        rect = self.liste.visualItemRect(it)
        return rect.center().y() + self.liste.viewport().mapTo(self.liste, QPoint(0, 0)).y()

    def _rang_a(self, y: int) -> int:
        """Le rang de la ligne la plus proche de cette hauteur."""
        nb = self.liste.topLevelItemCount()
        if not nb:
            return 0
        return min(range(nb), key=lambda i: abs(self._y_de(i) - y))

    def paintEvent(self, event) -> None:
        nb = self.liste.topLevelItemCount()
        if not nb:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pal = self.palette()
        encre = pal.color(QPalette.ColorGroup.Active, QPalette.ColorRole.WindowText)
        trait = QColor(encre.red(), encre.green(), encre.blue(), 90)
        vif = pal.color(QPalette.ColorGroup.Active, QPalette.ColorRole.Highlight)
        x = self.width() / 2.0
        haut, bas = self._y_de(0), self._y_de(nb - 1)
        p.setPen(QPen(trait, 2))
        p.drawLine(int(x), haut, int(x), bas)
        # un repère par étape, pour que les crans se voient
        p.setPen(QPen(trait, 1))
        for i in range(nb):
            y = self._y_de(i)
            p.drawLine(int(x - 3), y, int(x + 3), y)
        # la poignée, en face de la ligne choisie
        courant = self.liste.indexOfTopLevelItem(self.liste.currentItem())
        if courant >= 0:
            y = self._y_de(courant)
            p.setPen(QPen(vif, 1.4))
            p.setBrush(QBrush(vif))
            # la poignée pointe vers la liste : elle désigne la ligne où l'on en est
            p.drawPolygon(QPolygonF([QPointF(x + 6.0, y - 5.0), QPointF(x - 6.0, y),
                                     QPointF(x + 6.0, y + 5.0)]))
        p.end()

    def _viser(self, y: int) -> None:
        rang = self._rang_a(y)
        if rang != self.liste.indexOfTopLevelItem(self.liste.currentItem()):
            self.liste.setCurrentItem(self.liste.topLevelItem(rang))
        self.update()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._viser(int(event.position().y()))

    def mouseMoveEvent(self, event) -> None:
        if event.buttons() & Qt.MouseButton.LeftButton:
            self._viser(int(event.position().y()))

    def wheelEvent(self, event) -> None:
        pas = -1 if event.angleDelta().y() > 0 else 1
        courant = self.liste.indexOfTopLevelItem(self.liste.currentItem())
        self._viser(self._y_de(max(courant, 0) + pas))
        event.accept()


def _numero_tete(charge: str) -> int:
    """Le nombre en tête d'une charge de glisser, zéro s'il n'y en a pas."""
    tete = (charge or "").strip().split(" ")[0].lstrip("Tt")
    return int(tete) if tete.isdigit() else 0


def _numero_poste(charge: str) -> int:
    """Le numéro porté par un glisser de poste : « T7 » ou « T7 PCLNR 2020 K12 + CNMG 120408 »."""
    return _numero_tete(charge)


class BoiteDemi(QDoubleSpinBox):
    """Une boîte de nombre dont les flèches et la molette vont de demi en demi-millimètre.

    Les forets vont par entiers et demis : d'une valeur libre tapée à la main (un 6,8 de taraudage), un
    cran de molette ramène d'abord sur le demi voisin, puis avance par demis. Seule la saisie reste libre.
    """

    def stepBy(self, pas: int) -> None:
        courant = self.value()
        cale = round(courant * 2.0) / 2.0
        if abs(cale - courant) > 1e-9:
            # on était entre deux crans : on rejoint celui qui est dans le sens du geste
            cale = (math.floor(courant * 2.0) if pas < 0 else math.ceil(courant * 2.0)) / 2.0
            pas = pas + 1 if pas < 0 else pas - 1
        self.setValue(cale + 0.5 * pas)


class ZoneUsinage(QWidget):
    """La gamme : liste ordonnée, boutons d'ordre, et le réglage de la séquence choisie.

    **Les boutons et la gamme sont fixés en haut du volet** : ils restent sous la main quelle que soit la
    longueur du formulaire, qui défile seul en dessous.
    """

    gamme_changee = Signal()                 # la gamme a changé : à enregistrer et à redessiner
    sequence_choisie = Signal(int)           # identifiant de la séquence à montrer sur l'esquisse
    etape_changee = Signal(int)              # rang de l'étape à montrer : 0 = le brut, k = après la k-ième

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(360)
        self.gamme = Gamme()
        self.tourelle = None                 # garniture de la machine : dit ce que porte le poste choisi
        self._blocage = False
        self._trajectoire: Callable[[Sequence], object] = lambda s: None

        v = QVBoxLayout(self)
        v.setContentsMargins(6, 6, 6, 6)
        v.setSpacing(5)
        entete = QLabel("Gamme d'usinage de la pièce : les séquences s'exécutent dans cet ordre. Choisir "
                        "une ligne montre la pièce après cette opération, et la trajectoire qui l'a faite ; "
                        "glissez-y un poste de la tourelle pour l'y affecter.")
        entete.setWordWrap(True)
        v.addWidget(entete)

        grille = QGridLayout()
        grille.setSpacing(3)
        self.boutons_ajout: Dict[TypeSequence, QPushButton] = {}
        for i, type_ in enumerate(TypeSequence):
            b = QPushButton("+ " + NOMS_COURTS[type_])
            b.setToolTip(USAGES_SEQUENCE[type_])
            b.clicked.connect(lambda _=False, t=type_: self.ajouter(t))
            grille.addWidget(b, i // BOUTONS_PAR_RANGEE, i % BOUTONS_PAR_RANGEE)
            self.boutons_ajout[type_] = b
        self.btn_gamme_type = QPushButton("Proposer la gamme type")
        self.btn_gamme_type.setToolTip(
            "Pose l'enchaînement habituel d'une pièce sur barre, dans l'ordre : dressage, centrage, "
            "perçage, ébauche, alésage, finition, gorge, filetage, tronçonnage.\n"
            "Les opérations qui demandent une cote que le dessin ne donne pas sont posées décochées.")
        self.btn_gamme_type.clicked.connect(self.proposer_gamme_type)
        grille.addWidget(self.btn_gamme_type, (len(TypeSequence) - 1) // BOUTONS_PAR_RANGEE + 1, 0,
                         1, BOUTONS_PAR_RANGEE)
        v.addLayout(grille)

        self.liste = ListeSequences()
        self.liste.setColumnCount(len(COLONNES))
        self.liste.setHeaderLabels(COLONNES)
        self.liste.setRootIsDecorated(False)
        self.liste.setUniformRowHeights(True)
        self.liste.setAlternatingRowColors(True)
        self.liste.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.liste.accepte_depot = self.accepte_poste
        self.liste.depot.connect(self.affecter_poste)
        self.liste.reordonne.connect(self.reordonner)
        self.liste.currentItemChanged.connect(self._ligne_choisie)
        self.liste.itemChanged.connect(self._case_changee)
        # le curseur d'étape longe la liste, à sa droite : un trait, un cran par étape, une poignée
        self.curseur = CurseurEtape(self.liste)
        rangee = QHBoxLayout()
        rangee.setSpacing(2)
        rangee.addWidget(self.liste, 1)
        rangee.addWidget(self.curseur)
        v.addLayout(rangee)

        ordre = QHBoxLayout()
        ordre.setSpacing(3)
        self.btn_monter = self._bouton(ordre, "▲", "Monter la séquence dans l'ordre d'usinage",
                                       lambda: self.deplacer(-1))
        self.btn_descendre = self._bouton(ordre, "▼", "Descendre la séquence dans l'ordre d'usinage",
                                          lambda: self.deplacer(1))
        self.btn_supprimer = self._bouton(ordre, "Supprimer", "Retirer la séquence de la gamme",
                                          self.supprimer)
        ordre.addStretch(1)
        v.addLayout(ordre)

        self.groupe = QGroupBox("Séquence")
        self.formulaire = QFormLayout(self.groupe)
        self.formulaire.setContentsMargins(8, 6, 8, 6)
        self.formulaire.setSpacing(4)
        self.nom = QLineEdit()
        self.nom.setPlaceholderText("nom libre, sinon le type suffit")
        self.poste = QSpinBox()
        self.poste.setRange(0, 12)
        self.poste.setSpecialValueText("à choisir")
        self.poste.setPrefix("T")
        self.poste.setToolTip("Numéro de poste, ou glissez une ligne du volet Tourelle sur la séquence.")
        self.lbl_outil = QLabel("—")
        self.lbl_outil.setWordWrap(True)
        self.vitesse_coupe = self._nombre(" m/min", 1.0, 1000.0, 0)
        self.vitesse_maxi = self._nombre(" tr/min", 100.0, 10000.0, 0)
        self.avance = self._nombre(" mm/tr", 0.01, 2.0, 3)
        self.arrosage = QCheckBox("Arrosage")
        self.interieur = QCheckBox("dans l'alésage")
        self.interieur.setToolTip("L'opération travaille à l'intérieur : on peut aussi déplacer sa zone "
                                  "à la poignée centrale, du contour extérieur vers le trou.")
        self.interieur.toggled.connect(self._reglage_change)
        self.largeur_outil = self._nombre(" mm", 0.5, 20.0, 2)
        self.largeur = self._nombre(" mm", 0.0, 200.0, 2)
        self.largeur.setSpecialValueText("largeur de l'outil")
        self.diametre_fond = self._nombre(" mm", 0.0, 500.0, 2)
        self.diametre_fond.setSpecialValueText("jusqu'à l'axe")
        self.diametre_outil = BoiteDemi()
        self.diametre_outil.setRange(0.5, 100.0)
        self.diametre_outil.setDecimals(2)
        self.diametre_outil.setSuffix(" mm")
        self.diametre_outil.setSingleStep(0.5)
        self.foret = QComboBox()
        self.foret.setToolTip("Le foret monté : sa pointe donne la forme du trou, pas seulement son Ø.")
        self.foret.currentIndexChanged.connect(self._foret_change)
        self.pas = self._nombre(" mm", 0.2, 12.0, 2)
        self.hauteur_filet = self._nombre(" mm", 0.0, 20.0, 3)
        self.hauteur_filet.setSpecialValueText("profil ISO métrique")
        self.profondeur = self._nombre(" mm", 0.05, 20.0, 2)
        self.profondeur.setSingleStep(0.1)              # un dixième par cran de molette
        self.surepaisseur = self._nombre(" mm", 0.0, 10.0, 2)
        self.surepaisseur_face = self._nombre(" mm", 0.0, 10.0, 2)
        self.garde = self._nombre(" mm", 0.0, 50.0, 1)
        self.degagement = self._nombre(" mm", 0.0, 50.0, 1)
        self.z_debut = self._etendue("du bout de la pièce")
        self.z_fin = self._etendue("jusqu'au fond usinable")
        # (clé du champ, intitulé) ; la clé est celle de CHAMPS_SEQUENCE, qui dit quand le montrer
        self.champs: Dict[str, QWidget] = {}
        self.intitules: Dict[str, str] = {}
        for cle, intitule, widget in (
                ("", "Nom", self.nom),
                ("", "Poste de tourelle", self.poste),
                ("", "Outil monté", self.lbl_outil),
                ("", "Vitesse de coupe", self.vitesse_coupe),
                ("vitesse_maxi", "Broche maximale", self.vitesse_maxi),
                ("avance", "Avance", self.avance),
                ("", "", self.arrosage),
                ("interieur", "Côté usiné", self.interieur),
                ("largeur_outil", "Largeur de l'outil", self.largeur_outil),
                ("largeur", "Largeur de la gorge", self.largeur),
                ("diametre_fond", "Ø au fond", self.diametre_fond),
                ("foret", "Foret", self.foret),
                ("diametre_outil", "Ø du foret", self.diametre_outil),
                ("pas", "Pas du filet", self.pas),
                ("hauteur_filet", "Profondeur du filet", self.hauteur_filet),
                ("profondeur_passe", "Profondeur de passe", self.profondeur),
                ("surepaisseur", "Surépaisseur au rayon", self.surepaisseur),
                ("surepaisseur_face", "Surépaisseur de face", self.surepaisseur_face),
                ("garde", "Garde d'approche", self.garde),
                ("degagement", "Dégagement", self.degagement),
                ("z_debut", "Z de début", self.z_debut),
                ("z_fin", "Z de fin", self.z_fin)):
            if intitule:
                self.formulaire.addRow(intitule, widget)
            else:
                self.formulaire.addRow(widget)
            if cle:
                self.champs[cle] = widget
                self.intitules[cle] = intitule

        self.lbl_etat = QLabel("")
        self.lbl_etat.setWordWrap(True)

        # seul le réglage de la séquence défile : les boutons et la gamme restent en haut
        bas = QWidget()
        vbas = QVBoxLayout(bas)
        vbas.setContentsMargins(0, 0, 0, 0)
        vbas.setSpacing(5)
        vbas.addWidget(self.groupe)
        vbas.addWidget(self.lbl_etat)
        vbas.addStretch(1)
        self.defilement = QScrollArea()
        self.defilement.setWidgetResizable(True)
        self.defilement.setFrameShape(QFrame.Shape.NoFrame)
        self.defilement.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.defilement.setWidget(bas)
        v.addWidget(self.defilement, 1)

        for widget in (self.vitesse_coupe, self.vitesse_maxi, self.avance, self.largeur_outil,
                       self.largeur, self.diametre_fond, self.diametre_outil, self.pas,
                       self.hauteur_filet, self.profondeur, self.surepaisseur, self.surepaisseur_face,
                       self.garde, self.degagement, self.z_debut, self.z_fin, self.poste):
            widget.valueChanged.connect(self._reglage_change)
        self.arrosage.toggled.connect(self._reglage_change)
        self.nom.editingFinished.connect(self._reglage_change)
        self.rafraichir()

    @staticmethod
    def _bouton(rangee: QHBoxLayout, texte: str, aide: str, action: Callable[[], None]) -> QPushButton:
        b = QPushButton(texte)
        b.setToolTip(aide)
        if len(texte) == 1:
            b.setFixedWidth(30)
        b.clicked.connect(action)
        rangee.addWidget(b)
        return b

    @staticmethod
    def _nombre(suffixe: str, mini: float, maxi: float, decimales: int) -> QDoubleSpinBox:
        s = QDoubleSpinBox()
        s.setRange(mini, maxi)
        s.setDecimals(decimales)
        s.setSuffix(suffixe)
        return s

    def _etendue(self, texte_libre: str) -> QDoubleSpinBox:
        """Une borne en Z : la valeur la plus basse veut dire « automatique »."""
        s = QDoubleSpinBox()
        s.setRange(-1000.0, 1000.0)
        s.setDecimals(2)
        s.setSuffix(" mm")
        s.setSpecialValueText(texte_libre)
        return s

    # -- liaison avec le reste ------------------------------------------------------------

    def definir_gamme(self, gamme: Gamme, calcul_trajectoire: Callable[[Sequence], object]) -> None:
        """Change la gamme montrée et la façon d'en calculer les trajectoires."""
        self.gamme = gamme
        self._trajectoire = calcul_trajectoire
        self.rafraichir()

    def definir_tourelle(self, tourelle) -> None:
        """La garniture courante : le formulaire dit alors ce que porte le poste choisi."""
        self.tourelle = tourelle
        if tourelle is not None:
            self.poste.setRange(0, int(getattr(tourelle, "nb_postes", 12)))
        self._dire_l_outil()

    def _dire_l_outil(self) -> None:
        """Ce que porte le poste de la séquence choisie, relu de la tourelle de l'atelier."""
        numero = self.poste.value()
        if self.tourelle is None or not numero:
            self.lbl_outil.setText("—" if numero else "poste à choisir")
            return
        try:
            poste = self.tourelle.poste(numero)
        except ValueError:
            self.lbl_outil.setText("hors tourelle")
            return
        self.lbl_outil.setText(f"{poste.libelle()} ({poste.texte_implantation()})")

    def sequence_courante(self) -> Optional[Sequence]:
        it = self.liste.currentItem()
        return self.gamme.sequence(int(it.data(0, ROLE_ID))) if it is not None else None

    # -- dépôt d'un poste de tourelle ------------------------------------------------------

    def accepte_poste(self, sequence_id: int, poste: int) -> bool:
        """Une séquence de la gamme accepte tout poste existant de la tourelle."""
        if not poste or self.gamme.sequence(sequence_id) is None:
            return False
        if self.tourelle is None:
            return True
        return 1 <= poste <= int(getattr(self.tourelle, "nb_postes", 12))

    def affecter_poste(self, sequence_id: int, poste: int) -> bool:
        """Donne ce poste à la séquence : c'est ce que fait un dépôt venu du volet Tourelle."""
        if not self.accepte_poste(sequence_id, poste):
            return False
        s = self.gamme.sequence(sequence_id)
        s.poste = poste
        self._choisir(s.id)
        self._mettre_a_jour_ligne(s)
        self._remplir_formulaire()
        self.gamme_changee.emit()
        return True

    def reordonner(self, sequence_id: int, rang_liste: int) -> bool:
        """Pose la séquence à ce rang : c'est ce que fait un glisser d'une ligne sur une autre.

        Le rang est celui de la liste, où la ligne 0 est le brut ; dans la gamme, c'est un de moins.
        """
        if not self.gamme.deplacer_a(sequence_id, max(rang_liste - 1, 0)):
            return False
        self.rafraichir()
        self._choisir(sequence_id)
        self.gamme_changee.emit()
        return True

    # -- la liste est le curseur d'étape -----------------------------------------------------

    def etape(self) -> int:
        """Le rang de l'étape montrée : 0 pour le brut, k pour l'état après la k-ième opération.

        C'est le rang de la ligne choisie : la liste et le curseur ne font qu'un.
        """
        it = self.liste.currentItem()
        return self.liste.indexOfTopLevelItem(it) if it is not None else 0

    def definir_etape(self, rang: int) -> None:
        """Choisit la ligne de cette étape ; 0 montre le brut, avant tout usinage."""
        rang = min(max(rang, 0), self.liste.topLevelItemCount() - 1)
        if rang >= 0 and rang != self.etape():
            self.liste.setCurrentItem(self.liste.topLevelItem(rang))

    def _marquer_etape(self) -> None:
        """Les lignes qui suivent l'étape montrée se grisent : la liste se lit comme un curseur."""
        avant, self._blocage = self._blocage, True
        courante = self.etape()
        pal = self.palette()
        vif = pal.color(QPalette.ColorGroup.Active, QPalette.ColorRole.WindowText)
        muet = QColor(vif.red(), vif.green(), vif.blue(), 110)
        for i in range(self.liste.topLevelItemCount()):
            it = self.liste.topLevelItem(i)
            couleur = vif if i <= courante else muet
            for col in range(len(COLONNES)):
                it.setForeground(col, couleur)
        self._blocage = avant
        self.curseur.update()

    # -- affichage ------------------------------------------------------------------------

    def rafraichir(self) -> None:
        courante = self.sequence_courante()
        etape_avant = self.etape()
        self._blocage = True
        self.liste.clear()
        # première ligne : le brut, avant tout usinage. C'est l'étape 0 du curseur.
        brut = QTreeWidgetItem(self.liste, ["0", "Brut", "—", "—", "—"])
        brut.setData(0, ROLE_ID, 0)
        brut.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
        brut.setToolTip(0, "La pièce avant usinage : le brut tel qu'il est serré dans les mors.")
        for rang, s in enumerate(self.gamme, start=1):
            traj = self._trajectoire(s)
            passes = str(traj.nb_passes()) if traj else "—"
            coupe = f"{traj.longueur_coupe():.0f} mm" if traj else "—"
            it = QTreeWidgetItem(self.liste, [str(rang), s.libelle(),
                                              nom_poste(s.poste) if s.poste else "—", passes, coupe])
            it.setData(0, ROLE_ID, s.id)
            it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            it.setCheckState(0, Qt.CheckState.Checked if s.active else Qt.CheckState.Unchecked)
            message = getattr(traj, "message", "") if traj is not None else ""
            it.setToolTip(0, s.description() + (f"\n\n{message}" if message else ""))
            if courante is not None and s.id == courante.id:
                self.liste.setCurrentItem(it)
        if self.liste.currentItem() is None:
            # la séquence montrée a disparu : on reste au même rang, sinon on montre le brut
            self.liste.setCurrentItem(self.liste.topLevelItem(
                min(max(etape_avant, 0), self.liste.topLevelItemCount() - 1)))
        for col in range(len(COLONNES)):
            self.liste.resizeColumnToContents(col)
        self._ajuster_hauteur()
        self._blocage = False
        self._marquer_etape()
        self._remplir_formulaire()

    def _ajuster_hauteur(self) -> None:
        """La liste montre toutes ses étapes d'un coup : on ne défile pas dans la gamme."""
        nb = self.liste.topLevelItemCount()
        ligne = self.liste.sizeHintForRow(0) if nb else 20
        hauteur = (self.liste.header().sizeHint().height() + max(nb, 4) * ligne
                   + 2 * self.liste.frameWidth() + 2)
        self.liste.setMinimumHeight(hauteur)
        self.liste.setMaximumHeight(hauteur)

    def _remplir_formulaire(self) -> None:
        s = self.sequence_courante()
        avant, self._blocage = self._blocage, True
        # sur la ligne du brut, pas de réglage à montrer : le formulaire s'efface plutôt que de se griser
        self.groupe.setVisible(s is not None)
        if s is None:
            self.groupe.setTitle("Séquence")
            self.lbl_etat.setText("Le brut, avant usinage. Choisissez une ligne pour voir la pièce après "
                                  "cette opération." if len(self.gamme) else
                                  "Aucune séquence : ajoutez une opération, ou proposez la gamme type.")
            self._blocage = avant
            return
        self.groupe.setTitle(f"{LIBELLES_SEQUENCE[s.type]} — {s.libelle()}")
        self.nom.setText(s.nom)
        self.poste.setValue(s.poste)
        self.vitesse_coupe.setValue(s.vitesse_coupe)
        self.vitesse_maxi.setValue(s.vitesse_maxi)
        self.avance.setValue(s.avance)
        self.arrosage.setChecked(s.arrosage)
        self.interieur.setChecked(s.interieur)
        self.largeur_outil.setValue(s.largeur_outil)
        self.largeur.setValue(s.largeur)
        self.diametre_fond.setValue(s.diametre_fond)
        self.diametre_outil.setValue(s.diametre_outil)
        self._remplir_forets(s)
        self.pas.setValue(s.pas)
        self.hauteur_filet.setValue(s.hauteur_filet)
        self.profondeur.setValue(s.profondeur_passe)
        self.surepaisseur.setValue(s.surepaisseur)
        self.surepaisseur_face.setValue(s.surepaisseur_face)
        self.garde.setValue(s.garde)
        self.degagement.setValue(s.degagement)
        self.z_debut.setValue(s.z_debut if s.z_debut is not None else self.z_debut.minimum())
        self.z_fin.setValue(s.z_fin if s.z_fin is not None else self.z_fin.minimum())
        self._adapter_au_type(s)
        self._blocage = avant
        self._dire_l_outil()
        self._dire_l_etat(s)

    def _remplir_forets(self, s: Sequence) -> None:
        """Le choix de foret, selon le type : forets à centrer pour un centrage, hélicoïdaux sinon."""
        if "foret" not in s.champs():
            return
        avant, self._blocage = self._blocage, True
        self.foret.clear()
        self.foret.addItem("— (Ø libre, pointe à 135°)", "")
        for f in forets(a_centrer=s.type == TypeSequence.CENTRAGE):
            self.foret.addItem(f.designation, f.designation)
            self.foret.setItemData(self.foret.count() - 1, f.description(),
                                   Qt.ItemDataRole.ToolTipRole)
        self.foret.setCurrentIndex(max(0, self.foret.findData(s.foret)))
        self._blocage = avant

    def _foret_change(self) -> None:
        """Choisir un foret fixe son diamètre : un foret a le sien, on ne le règle pas à part."""
        if self._blocage:
            return
        s = self.sequence_courante()
        designation = self.foret.currentData() or ""
        if s is None:
            return
        from ..forets import foret as chercher
        choisi = chercher(designation)
        avant, self._blocage = self._blocage, True
        if choisi is not None:
            self.diametre_outil.setValue(choisi.diametre)
        self._blocage = avant
        self._reglage_change()

    def _adapter_au_type(self, s: Sequence) -> None:
        """Ne montre que les réglages qui comptent pour ce type, et les nomme pour ce qu'ils y sont."""
        attendus = s.champs()
        for cle, widget in self.champs.items():
            if cle not in ("vitesse_maxi", "avance"):
                self.formulaire.setRowVisible(widget, cle in attendus)
            etiquette = self.formulaire.labelForField(widget)
            if etiquette is not None:
                etiquette.setText(s.libelle_champ(cle, self.intitules[cle]))
        # la broche est fixe en filetage, en perçage et en centrage ; un filetage avance de son pas
        self.formulaire.setRowVisible(self.vitesse_maxi, not s.vitesse_fixe())
        self.formulaire.setRowVisible(self.avance, s.type != TypeSequence.FILETAGE)
        # un Ø au fond nul ne veut pas dire la même chose partout : l'axe pour une gorge, le dessin
        # pour un alésage, qui suit alors la paroi dessinée jusqu'au fond du trou
        self.diametre_fond.setSpecialValueText(TEXTES_DIAMETRE_NUL.get(s.type, "jusqu'à l'axe"))
        self.z_fin.setSpecialValueText("fond de l'alésage dessiné" if s.type in ALESAGES
                                       else "jusqu'au fond usinable")

    def _dire_l_etat(self, s: Sequence) -> None:
        traj = self._trajectoire(s)
        if traj is None:
            self.lbl_etat.setText("Trajectoire non calculée : il manque le profil ou le montage.")
            return
        if getattr(traj, "message", ""):
            self.lbl_etat.setText(traj.message)
            return
        allure = f"pas {s.pas:g} mm" if s.type == TypeSequence.FILETAGE else f"{s.avance:g} mm/tr"
        self.lbl_etat.setText(f"{traj.nb_passes()} passe(s), {traj.longueur_coupe():.0f} mm en coupe à "
                              f"{allure}. Trait plein : en coupe ; pointillé : en rapide.")

    # -- actions --------------------------------------------------------------------------

    def ajouter(self, type_: TypeSequence) -> Sequence:
        """Ajoute une opération **juste après l'étape montrée**, et la choisit : on construit la gamme
        de proche en proche, sans avoir à remonter chaque ajout depuis la fin."""
        s = self.gamme.ajouter(type_)
        self.gamme.deplacer_a(s.id, self.etape())
        self.rafraichir()
        self._choisir(s.id)
        self.gamme_changee.emit()
        return s

    def proposer_gamme_type(self, confirmer: bool = True) -> bool:
        """Pose l'enchaînement habituel, dans l'ordre, et affecte les postes que la tourelle porte déjà."""
        if len(self.gamme) and confirmer:
            rep = QMessageBox.question(self, "Gamme type",
                                       "Remplacer la gamme actuelle par l'enchaînement type ?",
                                       QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                                       QMessageBox.StandardButton.Cancel)
            if rep != QMessageBox.StandardButton.Yes:
                return False
        self.gamme.sequences.clear()
        self.gamme.remplir_type()
        for s in self.gamme:
            s.poste = self._poste_pour(s)
        self.rafraichir()
        self.definir_etape(0)
        self.gamme_changee.emit()
        return True

    def _poste_pour(self, sequence: Sequence) -> int:
        """Le premier poste garni d'un outil de la bonne famille, 0 si la tourelle n'en porte pas."""
        famille = FAMILLES_OUTIL.get(sequence.type, "")
        if not famille or self.tourelle is None:
            return 0
        from ..outils import CATALOGUE as OUTILS
        designations = {pp.designation for pp in OUTILS if pp.famille == famille}
        for poste in self.tourelle.garnis():
            if poste.porte_plaquette in designations:
                return poste.numero
        return 0

    def supprimer(self) -> bool:
        s = self.sequence_courante()
        if s is None or not self.gamme.supprimer(s.id):
            return False
        self.rafraichir()
        self.gamme_changee.emit()
        suivante = self.sequence_courante()
        self.sequence_choisie.emit(suivante.id if suivante is not None else 0)
        return True

    def deplacer(self, pas: int) -> bool:
        """Monte ou descend la séquence choisie dans l'ordre d'usinage."""
        s = self.sequence_courante()
        if s is None or not self.gamme.deplacer(s.id, pas):
            return False
        self.rafraichir()
        self._choisir(s.id)
        self.gamme_changee.emit()
        return True

    def _choisir(self, ident: int) -> None:
        for i in range(self.liste.topLevelItemCount()):
            it = self.liste.topLevelItem(i)
            if int(it.data(0, ROLE_ID)) == ident:
                self.liste.setCurrentItem(it)
                return

    def _ligne_choisie(self, item: Optional[QTreeWidgetItem], _precedent=None) -> None:
        if self._blocage:
            return
        self._remplir_formulaire()
        # choisir une ligne, c'est choisir l'étape : le dessin montre la pièce à ce moment-là
        self._marquer_etape()
        self.sequence_choisie.emit(int(item.data(0, ROLE_ID)) if item is not None else 0)
        self.etape_changee.emit(self.liste.indexOfTopLevelItem(item) if item is not None else 0)

    def _case_changee(self, item: QTreeWidgetItem, colonne: int) -> None:
        if self._blocage or colonne != 0:
            return
        s = self.gamme.sequence(int(item.data(0, ROLE_ID)))
        if s is None:
            return
        s.active = item.checkState(0) == Qt.CheckState.Checked
        self.gamme_changee.emit()

    def _reglage_change(self) -> None:
        if self._blocage:
            return
        s = self.sequence_courante()
        if s is None:
            return
        s.nom = self.nom.text().strip()
        s.poste = self.poste.value()
        s.vitesse_coupe, s.vitesse_maxi, s.avance = (self.vitesse_coupe.value(), self.vitesse_maxi.value(),
                                                     self.avance.value())
        s.arrosage = self.arrosage.isChecked()
        s.interieur = self.interieur.isChecked()
        s.largeur_outil, s.largeur = self.largeur_outil.value(), self.largeur.value()
        s.diametre_fond, s.diametre_outil = self.diametre_fond.value(), self.diametre_outil.value()
        # régler le Ø à la main détache le foret choisi : c'est alors un foret ordinaire de ce Ø
        s.foret = self.foret.currentData() or ""
        if s.foret and abs(s.outil_de_percage().diametre - s.diametre_outil) > 1e-6:
            s.foret = ""
        s.pas, s.hauteur_filet = self.pas.value(), self.hauteur_filet.value()
        s.profondeur_passe, s.surepaisseur = self.profondeur.value(), self.surepaisseur.value()
        s.surepaisseur_face = self.surepaisseur_face.value()
        s.garde, s.degagement = self.garde.value(), self.degagement.value()
        s.z_debut = None if self.z_debut.value() <= self.z_debut.minimum() else self.z_debut.value()
        s.z_fin = None if self.z_fin.value() <= self.z_fin.minimum() else self.z_fin.value()
        self._mettre_a_jour_ligne(s)
        self._dire_l_outil()
        self._dire_l_etat(s)
        self.gamme_changee.emit()

    def _mettre_a_jour_ligne(self, s: Sequence) -> None:
        traj = self._trajectoire(s)
        for i in range(self.liste.topLevelItemCount()):
            it = self.liste.topLevelItem(i)
            if int(it.data(0, ROLE_ID)) != s.id:
                continue
            avant, self._blocage = self._blocage, True
            it.setText(1, s.libelle())
            it.setText(2, nom_poste(s.poste) if s.poste else "—")
            it.setText(3, str(traj.nb_passes()) if traj else "—")
            it.setText(4, f"{traj.longueur_coupe():.0f} mm" if traj else "—")
            it.setToolTip(0, s.description() + (f"\n\n{traj.message}" if getattr(traj, "message", "") else ""))
            self._blocage = avant
            return
