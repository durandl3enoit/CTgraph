"""Fenêtre principale : colonne d'outils à gauche, esquisse à droite, menus, fichiers, annulation.

C'est aussi le contrôleur de la vue : toute modification du modèle passe par ici, puis par le
solveur, et est enregistrée dans la pile d'annulation.
"""
from __future__ import annotations

import copy
import json
import os
from typing import Callable, List, Optional, Tuple

from PySide6.QtCore import QByteArray, QSize, Qt
from PySide6.QtGui import QAction, QActionGroup, QCloseEvent, QKeySequence, QPalette
from PySide6.QtWidgets import (QCheckBox, QFileDialog, QGridLayout, QGroupBox, QHBoxLayout, QInputDialog, QLabel,
                               QListWidget, QListWidgetItem, QMainWindow, QMenu, QMessageBox, QPushButton,
                               QScrollArea, QSizePolicy, QToolButton, QVBoxLayout, QWidget, QWidgetAction)

from .. import APP_NAME, __version__
from ..build_info import BUILD_TIME
from ..esquisse import coins, elagage
from ..esquisse.modele import (COTES_SIGNEES, LIBELLES_COTE, LIBELLES_RELATION, ErreurEsquisse, Esquisse, TypeCote,
                               TypeRelation)
from ..esquisse.solveur import AdaptateurSolveur, Resultat
from ..icons import icone_action, icone_outil, icone_relation
from ..log import get as get_log
from ..montage import Montage, Piece
from ..settings import Settings
from ..usinage import Gamme, Sequence, Trajectoire, etats, profil_exterieur, trajectoire
from .dialogue_montage import DialogueMontage
from .vue_esquisse import AIMANTS_DEFAUT, LIBELLES_AIMANTS, Accroche, VueEsquisse
from ..tourelle import Tourelle
from .zone_atelier import ZoneAtelier
from .zone_repliable import ZoneRepliable

FILTRE_FICHIERS = "Esquisse CTgraph (*.ctg);;Tous les fichiers (*)"
MAX_ANNULATION = 200
ORDRE_RELATIONS = [TypeRelation.HORIZONTAL, TypeRelation.VERTICAL, TypeRelation.COINCIDENT,
                   TypeRelation.POINT_SUR_LIGNE, TypeRelation.PARALLELE, TypeRelation.PERPENDICULAIRE,
                   TypeRelation.TANGENT, TypeRelation.EGAL, TypeRelation.SUR_AXE, TypeRelation.ORIGINE_Z,
                   TypeRelation.FIXE]
OUTILS = (("selection", "Sélection", "S"), ("ligne", "Ligne", "L"), ("arc", "Arc 3 points", "A"),
          ("cote", "Cote", "C"), ("arrondi", "Arrondi", "R"), ("chanfrein", "Chanfrein", "H"),
          ("elaguer", "Élaguer", "E"))
PAS_MOLETTE = 1.0          # réglage d'une cote à la molette : 1 mm ou 1° par cran, 0,1 avec Maj


class FenetrePrincipale(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.log = get_log()
        self.reglages = Settings()
        self.premier_lancement = self.reglages.get("geometrie") is None

        self.esquisse = Esquisse()
        self.montage = self._montage_par_defaut()
        self.gamme = Gamme()
        self._profil_usinage = None          # profil tourné, recalculé après chaque résolution
        self._etats_matiere = None           # matière restante après chaque étape de la gamme
        self._synchroniser_references()
        self.solveur = AdaptateurSolveur(self.esquisse)
        self.resultat = Resultat(True, "ok", 0)
        self.chemin: Optional[str] = None
        self._modifie = False
        self._annuler: List[str] = []
        self._retablir: List[str] = []
        self._avant_glissement: Optional[str] = None
        self._avant_ajustement: Optional[str] = None     # réglage d'une cote à la molette : une seule annulation
        self._montage_avant_mors: Optional[Montage] = None   # montage d'avant l'édition des cotes du mors
        self._rayon_arrondi = 2.0
        self._longueur_chanfrein = 1.0

        self._construire_interface()
        self._construire_menus()
        self._restaurer_geometrie()
        self._rafraichir_titre()
        self._appliquer_resultat(self.resultat)
        self.choisir_outil("selection")

    # -- interface -----------------------------------------------------------------------

    def _construire_interface(self) -> None:
        central = QWidget()
        disposition = QHBoxLayout(central)
        disposition.setContentsMargins(0, 0, 0, 0)
        disposition.setSpacing(0)

        self.vue = VueEsquisse(self)
        self.vue.montage = self.montage
        self.vue.montage_visible = self.reglages.get_bool("montage.visible", True)
        self.vue.coordonnees.connect(self._afficher_coordonnees)
        self.vue.message.connect(self._afficher_aide)
        self.vue.selection_changee.connect(self._selection_changee)
        for cle in AIMANTS_DEFAUT:
            self.vue.aimants[cle] = self.reglages.get_bool("aimant." + cle, AIMANTS_DEFAUT[cle])
        self.vue.mode_elagage = "croisement"      # un seul élagage : jusqu'aux croisements voisins

        # vue 3D incrustée en haut à droite (CTGRAPH_SANS_3D=1 la désactive : tests hors écran sans OpenGL)
        self.vue3d = None
        if not os.environ.get("CTGRAPH_SANS_3D"):
            from .vue_3d import TAILLE_DEFAUT, Incrustation3D
            self.vue3d = Incrustation3D(self.vue)
            taille = str(self.reglages.get("vue3d.taille", "") or "")
            try:
                w, h = (int(v) for v in taille.split(","))
                self.vue3d.resize(max(w, 100), max(h, 80))
            except ValueError:
                self.vue3d.resize(TAILLE_DEFAUT)
            self.vue3d.taille_changee.connect(lambda s: self.reglages.set("vue3d.taille", f"{s.width()},{s.height()}"))
            biais = str(self.reglages.get("vue3d.biais", "") or "")
            if biais:
                try:
                    lacet, tangage = (float(v) for v in biais.split(","))
                    self.vue3d.definir_biais(lacet, tangage)
                except ValueError:
                    pass
            self.vue3d.biais_change.connect(lambda l, t: self.reglages.set("vue3d.biais", f"{l:g},{t:g}"))
            self.vue3d.setVisible(self.reglages.get_bool("vue3d.visible", True))
            self.vue.vue3d = self.vue3d
            self.vue.placer_superposition()
            self._pousser_montage_3d()

        colonne = QWidget()
        colonne.setFixedWidth(240)
        vbox = QVBoxLayout(colonne)
        vbox.setContentsMargins(6, 6, 6, 6)
        vbox.setSpacing(8)

        # Outils de tracé
        g_outils = QGroupBox("Outils")
        grille = QGridLayout(g_outils)
        self.groupe_outils = QActionGroup(self)
        self.actions_outils = {}
        pal = self.palette()
        encre = pal.color(QPalette.ColorGroup.Active, QPalette.ColorRole.ButtonText)
        fond_icone = pal.color(QPalette.ColorGroup.Active, QPalette.ColorRole.Button)
        self._encre, self._fond_icone = encre, fond_icone
        for i, (cle, libelle, touche) in enumerate(OUTILS):
            act = QAction(icone_outil(cle, encre, fond_icone), libelle, self, checkable=True)
            act.setShortcut(QKeySequence(touche))
            act.setData(cle)
            act.triggered.connect(lambda _=False, c=cle: self.choisir_outil(c))
            self.groupe_outils.addAction(act)
            self.actions_outils[cle] = act
            bouton = QToolButton()
            bouton.setDefaultAction(act)
            bouton.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
            bouton.setIconSize(QSize(30, 30))
            bouton.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            bouton.setMinimumHeight(56)
            bouton.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            grille.addWidget(bouton, i // 2, i % 2)
        vbox.addWidget(g_outils)

        # Relations : zone repliable, repliée par défaut (le menu du clic droit les propose aussi)
        contenu_rel = QWidget()
        grille = QGridLayout(contenu_rel)
        grille.setContentsMargins(4, 0, 4, 4)
        grille.setSpacing(4)
        self.boutons_relations = {}
        for i, t in enumerate(ORDRE_RELATIONS):
            b = QPushButton(icone_relation(t.value, encre, fond_icone), LIBELLES_RELATION[t])
            b.setIconSize(QSize(16, 16))
            b.setStyleSheet("text-align: left; padding-left: 3px; padding-right: 2px;")
            b.clicked.connect(lambda _=False, tt=t: self.appliquer_relation(tt))
            grille.addWidget(b, i // 2, i % 2)
            self.boutons_relations[t] = b
        self.zone_relations = ZoneRepliable("Relations", contenu_rel, self.reglages.get_bool("relations.deployee", False))
        self.zone_relations.basculee.connect(lambda etat: self.reglages.set("relations.deployee", etat))
        vbox.addWidget(self.zone_relations)

        # État et liste des relations et cotes
        g_etat = QGroupBox("État")
        v = QVBoxLayout(g_etat)
        self.lbl_etat = QLabel("")
        self.lbl_etat.setWordWrap(True)
        v.addWidget(self.lbl_etat)
        self.liste = QListWidget()
        self.liste.setToolTip("Relations et cotes de l'esquisse. Cliquer sélectionne, Suppr supprime.")
        self.liste.itemSelectionChanged.connect(self._liste_selectionnee)
        # la liste prend la hauteur qui reste, sans en réclamer : les groupes du dessous restent visibles
        self.liste.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Ignored)
        self.liste.setMinimumHeight(70)
        v.addWidget(self.liste, 1)
        vbox.addWidget(g_etat, 1)

        # Affichage et aimantation
        g_aff = QGroupBox("Affichage")
        v = QVBoxLayout(g_aff)
        h = QHBoxLayout()
        b = QPushButton("Tout voir")
        b.clicked.connect(self.vue.tout_voir)
        h.addWidget(b)
        self.case_grille = QCheckBox("Grille")
        self.case_grille.setChecked(self.reglages.get_bool("grille", True))
        self.case_grille.toggled.connect(self._basculer_grille)
        h.addWidget(self.case_grille)
        v.addLayout(h)
        v.addWidget(QLabel("Aimantation :"))
        grille = QGridLayout()
        grille.setSpacing(2)
        self.cases_aimants = {}
        for i, cle in enumerate(AIMANTS_DEFAUT):
            case = QCheckBox(LIBELLES_AIMANTS[cle])
            case.setChecked(self.vue.aimants[cle])
            case.toggled.connect(lambda actif, c=cle: self._basculer_aimant(c, actif))
            grille.addWidget(case, i // 2, i % 2)
            self.cases_aimants[cle] = case
        v.addLayout(grille)
        vbox.addWidget(g_aff)

        defilement = QScrollArea()
        defilement.setWidgetResizable(True)
        defilement.setWidget(colonne)
        defilement.setFixedWidth(256)
        defilement.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        disposition.addWidget(defilement)
        disposition.addWidget(self.vue, 1)
        self.setCentralWidget(central)

        # Atelier : usinage, tourelle, stock d'outils et plaquettes, en volets repliables ancrés à droite
        self.zone_atelier = ZoneAtelier(self)
        self.zone_usinage = self.zone_atelier.usinage
        self.zone_tourelle = self.zone_atelier.tourelle
        self.zone_outils = self.zone_atelier.outils
        self.zone_plaquettes = self.zone_atelier.plaquettes
        for cle, volet in self.zone_atelier.volets.items():
            volet.definir_deploye(self.reglages.get_bool("volet." + cle, cle == "outils"))
            volet.basculee.connect(lambda etat, c=cle: self._volet_bascule(c, etat))
        for cle, zone in (("outils", self.zone_outils), ("plaquettes", self.zone_plaquettes)):
            stock = self.reglages.get(cle + ".stock", []) or []
            zone.definir_stock([stock] if isinstance(stock, str) else stock)
            zone.stock_change.connect(lambda s, c=cle: self.reglages.set(c + ".stock", sorted(s)))
        # garniture de la tourelle : propre à la machine, mémorisée avec les préférences
        garniture = str(self.reglages.get("tourelle", "") or "")
        if garniture:
            try:
                self.zone_tourelle.definir_tourelle(Tourelle.from_dict(json.loads(garniture)))
            except (ValueError, TypeError):
                pass
        self.zone_tourelle.tourelle_changee.connect(
            lambda t: self.reglages.set("tourelle", json.dumps(t.to_dict(), ensure_ascii=False)))
        # la gamme appartient à la pièce ; la garniture de la tourelle dit ce que porte chaque poste
        self.zone_tourelle.tourelle_changee.connect(self.zone_usinage.definir_tourelle)
        self.zone_usinage.definir_tourelle(self.zone_tourelle.tourelle)
        self.zone_usinage.definir_gamme(self.gamme, self.trajectoire_de)
        self.zone_usinage.gamme_changee.connect(self._gamme_changee)
        self.zone_usinage.sequence_choisie.connect(self._sequence_choisie)
        self.zone_usinage.etape_changee.connect(self._etape_choisie)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.zone_atelier)
        self.resizeDocks([self.zone_atelier], [self.zone_atelier.largeur_souhaitee()], Qt.Orientation.Horizontal)
        self.zone_atelier.setVisible(self.reglages.get_bool("atelier.visible", True))
        self.zone_atelier.visibilityChanged.connect(self._zone_atelier_visible)

        barre = self.statusBar()
        self.lbl_aide = QLabel("")
        barre.addWidget(self.lbl_aide, 1)
        self.lbl_coord = QLabel("Z = —    Ø = —")
        self.lbl_coord.setMinimumWidth(220)
        barre.addPermanentWidget(self.lbl_coord)
        self.lbl_solveur = QLabel("")
        self.lbl_solveur.setMinimumWidth(240)
        barre.addPermanentWidget(self.lbl_solveur)
        self.vue.grille_visible = self.case_grille.isChecked()

    def _construire_menus(self) -> None:
        barre = self.menuBar()

        m_fichier = barre.addMenu("&Fichier")
        self.act_nouveau = self._action(m_fichier, "&Nouveau", QKeySequence.StandardKey.New, self.nouveau)
        self.act_ouvrir = self._action(m_fichier, "&Ouvrir…", QKeySequence.StandardKey.Open, self.ouvrir)
        self.menu_recents = m_fichier.addMenu("Fichiers &récents")
        self.menu_recents.aboutToShow.connect(self._remplir_recents)
        m_fichier.addSeparator()
        self.act_enregistrer = self._action(m_fichier, "&Enregistrer", QKeySequence.StandardKey.Save, self.enregistrer)
        self.act_enregistrer_sous = self._action(m_fichier, "Enregistrer &sous…", QKeySequence.StandardKey.SaveAs,
                                                 self.enregistrer_sous)
        m_fichier.addSeparator()
        self._action(m_fichier, "&Quitter", QKeySequence.StandardKey.Quit, self.close)

        m_edition = barre.addMenu("&Édition")
        self.act_annuler = self._action(m_edition, "&Annuler", QKeySequence.StandardKey.Undo, self.annuler)
        self.act_retablir = self._action(m_edition, "&Rétablir", QKeySequence.StandardKey.Redo, self.retablir)
        m_edition.addSeparator()
        self.act_supprimer = self._action(m_edition, "&Supprimer", QKeySequence.StandardKey.Delete,
                                          self.supprimer_selection)
        self.act_supprimer.setIcon(icone_action("supprimer", self._encre, self._fond_icone))
        self.act_deselectionner = self._action(m_edition, "Tout &désélectionner", QKeySequence("Ctrl+D"),
                                               self.vue.deselectionner)
        self.act_deselectionner.setIcon(icone_action("deselectionner", self._encre, self._fond_icone))

        m_esquisse = barre.addMenu("E&squisse")
        for act in self.actions_outils.values():
            m_esquisse.addAction(act)
        m_esquisse.addSeparator()
        m_rel = m_esquisse.addMenu("&Relations")
        for t, b in self.boutons_relations.items():
            self._action(m_rel, LIBELLES_RELATION[t], None, b.click).setIcon(b.icon())
        self.act_coter = self._action(m_esquisse, "&Coter la sélection", QKeySequence("Ctrl+K"), self.coter_selection)
        self.act_coter.setIcon(self.actions_outils["cote"].icon())

        m_piece = barre.addMenu("&Pièce")
        self.act_montage = self._action(m_piece, "&Machine et montage…", QKeySequence("Ctrl+M"), self.regler_montage)

        m_aff = barre.addMenu("&Affichage")
        self.act_voir_montage = QAction("&Montage (mandrin, brut)", self, checkable=True)
        self.act_voir_montage.setShortcut(QKeySequence("M"))
        self.act_voir_montage.setChecked(self.vue.montage_visible)
        self.act_voir_montage.toggled.connect(self._basculer_montage)
        m_aff.addAction(self.act_voir_montage)
        self.act_tout_voir = self._action(m_aff, "&Tout voir", QKeySequence("F"), self.vue.tout_voir)
        self.act_tout_voir.setIcon(icone_action("tout_voir", self._encre, self._fond_icone))
        self._action(m_aff, "Zoom &avant", QKeySequence.StandardKey.ZoomIn, lambda: self.vue.zoomer(1.25))
        self._action(m_aff, "Zoom a&rrière", QKeySequence.StandardKey.ZoomOut, lambda: self.vue.zoomer(0.8))
        self.act_grille = self._action(m_aff, "&Grille", QKeySequence("G"), self.case_grille.toggle)
        self.act_vue3d = QAction("Vue &3D", self, checkable=True)
        self.act_vue3d.setShortcut(QKeySequence("3"))
        self.act_vue3d.setChecked(self.vue3d is not None and self.vue3d.isVisibleTo(self.vue))
        self.act_vue3d.setEnabled(self.vue3d is not None)
        self.act_vue3d.toggled.connect(self._basculer_vue3d)
        m_aff.addAction(self.act_vue3d)
        self._action(m_aff, "Recadrer la vue 3&D", QKeySequence("Ctrl+3"),
                     lambda: self.vue3d.recadrer() if self.vue3d is not None else None)
        m_aff.addSeparator()
        self.act_zone_atelier = QAction("&Atelier (tourelle, outils, plaquettes)", self, checkable=True)
        self.act_zone_atelier.setShortcut(QKeySequence("O"))
        self.act_zone_atelier.setChecked(self.reglages.get_bool("atelier.visible", True))
        self.act_zone_atelier.toggled.connect(self._basculer_zone_atelier)
        m_aff.addAction(self.act_zone_atelier)
        self.actions_volets = {}
        for cle, volet in self.zone_atelier.volets.items():
            act = QAction(f"Volet « {volet.titre} »", self, checkable=True)
            act.setChecked(volet.est_deploye())
            act.toggled.connect(lambda etat, c=cle: self._regler_volet(c, etat))
            volet.basculee.connect(act.setChecked)
            m_aff.addAction(act)
            self.actions_volets[cle] = act

        m_aide = barre.addMenu("&Aide")
        self._action(m_aide, "À &propos de CTgraph", None, self.a_propos)
        self._rafraichir_annulation()

    def _action(self, menu, texte: str, raccourci, slot: Callable) -> QAction:
        act = QAction(texte, self)
        if raccourci is not None:
            act.setShortcut(raccourci)
        act.triggered.connect(slot)
        menu.addAction(act)
        return act

    def construire_menu_contextuel(self, montage: Optional[str] = None) -> QMenu:
        """Menu du clic droit : relations et cotes possibles pour la sélection, suppression, outils, vue.
        Sur le mors ou une cote du brut (`montage`), d'abord les réglages de la prise de pièce."""
        menu = QMenu(self)
        sel = list(self.vue.selection)
        possibles = False
        encre, fond = self._encre, self._fond_icone
        menu.relations_proposees = []
        menu.coin_propose = None
        menu.cotes_proposees = []
        menu.actions_montage = {}
        if self.vue.mode_mors:
            # pendant l'édition des cotes du mors, le menu ne sert qu'à conclure
            menu.addAction("Valider les cotes du mors\tEntrée", self.valider_edition_mors)
            menu.addAction("Abandonner les modifications\tÉchap", self.annuler_edition_mors)
            menu.actions_montage["valider"] = menu.actions()[0]
            return menu
        if montage is not None:
            if montage in ("mors", "reference_mors"):
                act = menu.addAction("Modifier les cotes du mors…", self.commencer_edition_mors)
                menu.actions_montage["cotes_mors"] = act
                menu.addSeparator()
            self._menu_prise_de_piece(menu)
            return menu
        if sel:
            types = [t for t in ORDRE_RELATIONS if self.esquisse.relation_possible(t, sel) or (
                t == TypeRelation.POINT_SUR_LIGNE and self.esquisse.relation_possible(TypeRelation.POINT_SUR_ARC, sel))]
            if types:
                # les relations possibles, en rangée d'icônes seules (le nom en infobulle)
                rangee = QWidget(menu)
                h = QHBoxLayout(rangee)
                h.setContentsMargins(8, 3, 8, 3)
                h.setSpacing(2)
                for t in types:
                    b = QToolButton(rangee)
                    b.setIcon(icone_relation(t.value, encre, fond))
                    b.setIconSize(QSize(22, 22))
                    b.setAutoRaise(True)
                    b.setToolTip(LIBELLES_RELATION[t])
                    b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
                    b.clicked.connect(lambda _=False, tt=t, m=menu: self._relation_depuis_menu(m, tt))
                    h.addWidget(b)
                h.addStretch(1)
                action = QWidgetAction(menu)
                action.setDefaultWidget(rangee)
                menu.addAction(action)
                menu.relations_proposees = types
                possibles = True
                menu.addSeparator()
            cotes = self.vue.cotes_possibles(sel)
            menu.cotes_proposees = [t for t, _, _ in cotes]
            for t, els, dec in cotes:
                menu.addAction(self.actions_outils["cote"].icon(), f"Coter : {LIBELLES_COTE[t]}",
                               lambda tt=t, ee=els, dd=dec: self.poser_cote(tt, ee, dd))
                possibles = True
            # les plans du montage : s'y aligner (relation) ou en partir (cote), pour un point ou une face
            cibles = self.references_pour(sel)
            menu.references_proposees = [r.nom for r in cibles]
            if cibles:
                m_al = menu.addMenu(icone_relation("sur_reference", encre, fond), "Aligner sur une référence")
                m_co = menu.addMenu(self.actions_outils["cote"].icon(), "Coter depuis une référence")
                for ref in cibles:
                    m_al.addAction(ref.libelle, lambda n=ref.nom: self.aligner_sur_reference(n))
                    m_co.addAction(ref.libelle, lambda n=ref.nom: self.coter_depuis_reference(n))
                possibles = True
            coin = self.coin_depuis_selection(sel)
            menu.coin_propose = coin
            if coin is not None:
                menu.addAction(self.actions_outils["arrondi"].icon(), "Arrondi…", lambda pid=coin: self.arrondir(pid))
                menu.addAction(self.actions_outils["chanfrein"].icon(), "Chanfrein…",
                               lambda pid=coin: self.chanfreiner(pid))
                possibles = True
            cotes_sel = [self.esquisse.cotes[i] for i in sel if i in self.esquisse.cotes]
            for co in cotes_sel:
                texte = "Rendre la cote pilotante" if co.pilotee else "Rendre la cote pilotée (mesurée)"
                icone = self.actions_outils["cote"].icon() if co.pilotee else icone_action("pilotee", encre, fond)
                menu.addAction(icone, f"{texte} : {self.esquisse.texte_cote(co)}",
                               lambda cid=co.id: self.basculer_pilotee(cid))
                possibles = True
            if not possibles:
                act = menu.addAction("Aucune relation ni cote pour cette sélection")
                act.setEnabled(False)
            menu.addSeparator()
            menu.addAction(self.act_supprimer.icon(), "Supprimer la sélection", self.supprimer_selection)
            menu.addAction(self.act_deselectionner.icon(), "Tout désélectionner", self.vue.deselectionner)
        else:
            act = menu.addAction("Sélectionnez des éléments pour poser une relation ou une cote")
            act.setEnabled(False)
        menu.addSeparator()
        m_outils = menu.addMenu(self.actions_outils[self.vue.outil].icon(), "Outils")
        for act in self.actions_outils.values():
            m_outils.addAction(act)
        menu.addAction(self.act_tout_voir.icon(), "Tout voir", self.vue.tout_voir)
        return menu

    def references_pour(self, sel) -> list:
        """Les références du montage qu'une sélection peut viser : toutes pour un point ; les plans Z pour une
        face verticale, les surfaces de révolution pour une ligne horizontale."""
        e = self.esquisse
        if len(sel) != 1 or not e.references:
            return []
        genre = e.genre(sel[0])
        refs = list(e.references.values())
        if genre == "point":
            return refs
        if genre == "ligne":
            if self.vue.est_verticale(sel[0]):
                return [r for r in refs if r.axe == "z"]
            if self.vue.est_horizontale(sel[0]):
                return [r for r in refs if r.axe == "x"]
        return []

    def aligner_sur_reference(self, nom: str) -> None:
        """Relation « sur une référence » entre la sélection (point ou face) et un plan du montage."""
        sel = list(self.vue.selection)
        e = self.esquisse
        if nom not in e.references or not sel:
            return
        nouvelle = []

        def action():
            nouvelle.append(e.ajouter_relation(TypeRelation.SUR_REFERENCE, sel, reference=nom).id)

        if self._modifier(action, f"Aligné sur : {e.references[nom].libelle}."):
            if nouvelle and nouvelle[0] in self.resultat.conflits:
                self.statusBar().showMessage(f"{e.references[nom].libelle} : alignement en conflit avec le reste. "
                                             "Annulez (Ctrl+Z) ou supprimez-le.", 8000)
            self.vue.selection = []
            self.vue.reconstruire()
            self._selection_changee()

    def coter_depuis_reference(self, nom: str) -> None:
        """Cote de l'écart signé entre la sélection (point ou face) et un plan du montage."""
        sel = tuple(self.vue.selection)
        if nom not in self.esquisse.references or not sel:
            return
        decalage = self.vue.decalage_par_defaut(TypeCote.DEPUIS_REFERENCE, sel)
        self.poser_cote(TypeCote.DEPUIS_REFERENCE, sel, decalage, reference=nom)

    def coin_depuis_selection(self, sel) -> Optional[int]:
        """Le sommet à arrondir ou chanfreiner : un point entre deux lignes, ou deux lignes concourantes."""
        e = self.esquisse
        genres = [e.genre(i) for i in sel]
        if genres == ["point"]:
            pid = sel[0]
        elif sorted(genres) == ["ligne", "ligne"]:
            l1, l2 = (e.lignes[i] for i in sel)
            commun = {l1.p1, l1.p2} & {l2.p1, l2.p2}
            if len(commun) != 1:
                return None
            pid = commun.pop()
        else:
            return None
        if e.points[pid].construction or len(e.lignes_du_point(pid)) != 2 or e.arcs_du_point(pid):
            return None
        return pid

    def _menu_prise_de_piece(self, menu: QMenu) -> None:
        """Les réglages faits directement sur le mors : retournement, serrage, appui du brut."""
        m, p = self.montage, self.montage.prise
        titre = menu.addAction(f"Mors {m.mandrin.mors_modele}")
        titre.setEnabled(False)
        act = menu.addAction("Retourner les mors", self.retourner_mors)
        act.setCheckable(True)
        act.setChecked(p.mors_retournes)
        menu.actions_montage["retourner"] = act
        menu.addSeparator()
        for serrage, libelle in (("exterieur", "Serrage extérieur"), ("interieur", "Serrage intérieur (tube)")):
            act = menu.addAction(libelle, lambda s=serrage: self.definir_serrage(s))
            act.setCheckable(True)
            act.setChecked(p.serrage == serrage)
            if serrage == "interieur" and m.brut.forme != "tube":
                act.setEnabled(False)
                act.setToolTip("Demande un brut en tube (Machine et montage…)")
            menu.actions_montage[serrage] = act
        menu.addSeparator()
        titre = menu.addAction("Appui du brut")
        titre.setEnabled(False)
        for valeur, libelle in m.appuis_possibles():
            act = menu.addAction(libelle, lambda v=valeur: self.definir_appui(v))
            act.setCheckable(True)
            act.setChecked(p.appui == valeur)
            menu.actions_montage[f"appui{valeur}"] = act
        menu.addSeparator()
        menu.addAction("Machine et montage…", self.regler_montage)

    def menu_contextuel(self, pos_globale, montage: Optional[str] = None) -> None:
        self.construire_menu_contextuel(montage).exec(pos_globale)

    def _relation_depuis_menu(self, menu: QMenu, type_: TypeRelation) -> None:
        menu.close()
        self.appliquer_relation(type_)

    # -- état et affichage ---------------------------------------------------------------

    def _appliquer_resultat(self, res: Resultat) -> None:
        self.resultat = res
        self.vue.definir_resultat(res)
        # le profil a bougé : les trajectoires se recalculent avant que la vue ne se redessine
        self._rafraichir_usinage(False)
        self.vue.reconstruire()
        texte = res.texte()
        if res.sur_contraint:
            couleur = "#e63c32"
        elif res.entierement_contraint:
            couleur = "#2ea043"
        else:
            couleur = ""
        style = f"color: {couleur}; font-weight: bold;" if couleur else ""
        self.lbl_etat.setStyleSheet(style)
        self.lbl_etat.setText(texte)
        self.lbl_solveur.setStyleSheet(style)
        self.lbl_solveur.setText(texte)
        self._remplir_liste()

    def _remplir_liste(self) -> None:
        self.liste.blockSignals(True)
        self.liste.clear()
        e = self.esquisse
        conflits = set(self.resultat.conflits)
        for r in e.relations.values():
            cible = ", ".join(f"{e.genre(i)} {i}" for i in r.elements)
            if r.reference:
                ref = e.references.get(r.reference)
                cible += f" — {ref.libelle if ref is not None else r.reference}"
            it = QListWidgetItem(f"{LIBELLES_RELATION[r.type]} : {cible}")
            it.setData(Qt.ItemDataRole.UserRole, r.id)
            if r.id in conflits:
                it.setForeground(Qt.GlobalColor.red)
            self.liste.addItem(it)
        for c in e.cotes.values():
            cible = ", ".join(f"{e.genre(i)} {i}" for i in c.elements)
            suffixe = " — pilotée" if c.pilotee else (" — égale à une autre cote" if e.cote_maitresse(c.id) else "")
            valeur = e.texte_cote(c) + (f" ({e.texte_rayon(c)})" if c.type == TypeCote.DIAMETRE else "")
            it = QListWidgetItem(f"{LIBELLES_COTE[c.type]} {valeur} : {cible}{suffixe}")
            it.setData(Qt.ItemDataRole.UserRole, c.id)
            if c.id in conflits:
                it.setForeground(Qt.GlobalColor.red)
            elif c.pilotee:
                it.setForeground(Qt.GlobalColor.gray)
            self.liste.addItem(it)
        for i in range(self.liste.count()):
            it = self.liste.item(i)
            it.setSelected(it.data(Qt.ItemDataRole.UserRole) in self.vue.selection)
        self.liste.blockSignals(False)

    def _liste_selectionnee(self) -> None:
        ids = [it.data(Qt.ItemDataRole.UserRole) for it in self.liste.selectedItems()]
        if ids:
            self.vue.selection = ids
            self.vue.reconstruire()
            self.act_supprimer.setEnabled(True)

    def _selection_changee(self) -> None:
        self.act_supprimer.setEnabled(bool(self.vue.selection))
        self._remplir_liste()

    def _afficher_coordonnees(self, z: float, x: float) -> None:
        self.lbl_coord.setText(f"Z = {z:.2f}    Ø = {2 * x:.2f}   (X = {x:.2f})")

    def _afficher_aide(self, texte: str) -> None:
        self.lbl_aide.setText(texte)

    def _basculer_grille(self, actif: bool) -> None:
        self.vue.grille_visible = actif
        self.reglages.set("grille", actif)
        self.vue.viewport().update()

    # -- machine et montage -------------------------------------------------------------------

    def _montage_par_defaut(self) -> Montage:
        """Le dernier montage utilisé, mémorisé dans les préférences, sinon les valeurs du CT200."""
        brut = self.reglages.get("montage.defaut", "")
        if brut:
            try:
                return Montage.from_dict(json.loads(str(brut)))
            except (ValueError, ErreurEsquisse):
                pass
        return Montage()

    def _pousser_montage_3d(self) -> None:
        if self.vue3d is None:
            return
        from .vue_3d import maillages_montage
        self.vue3d.definir_montage(maillages_montage(self.montage) if self.vue.montage_visible else [])

    def definir_montage(self, montage: Montage) -> None:
        self.montage = montage
        self.vue.montage = montage
        self.reglages.set("montage.defaut", json.dumps(montage.to_dict(), ensure_ascii=False))
        self._marquer_modifie(True)
        # les références du montage ont pu bouger : ce qui s'y aligne ou s'y cote suit
        self._synchroniser_references()
        if any(r.reference for r in self.esquisse.relations.values()) \
                or any(c.reference for c in self.esquisse.cotes.values()):
            self._appliquer_resultat(self._resoudre_apres_construction())
        else:
            # le brut et la face des mors entrent dans les trajectoires : elles se recalculent aussi
            self._rafraichir_usinage()
        self._pousser_montage_3d()

    def editer_valeur_montage(self, cle: str) -> None:
        """Double-clic sur une cote du brut (diamètre, longueur, marge) ou du mors (étages, épaisseur)."""
        try:
            libelle, defaut = self.montage.libelle(cle), self.montage.valeur(cle)
        except ErreurEsquisse:
            return
        valeur, ok = self._demander_valeur(libelle, "mm", defaut, 0.0)
        if not ok:
            return
        nouveau = copy.deepcopy(self.montage)
        try:
            nouveau.definir_valeur(cle, valeur)
        except ErreurEsquisse as exc:
            self.statusBar().showMessage(str(exc), 6000)
            return
        self.definir_montage(nouveau)

    def ajuster_valeur_montage(self, cle: str, sens: int, fin: bool) -> Optional[str]:
        """Molette ou glisser sur une cote du brut ou du mors : un pas par cran (0,1 avec Maj)."""
        pas = PAS_MOLETTE / 10.0 if fin else PAS_MOLETTE
        nouveau = copy.deepcopy(self.montage)
        try:
            nouveau.definir_valeur(cle, max(0.0, self.montage.valeur(cle) + sens * pas))
        except ErreurEsquisse as exc:
            self.statusBar().showMessage(str(exc), 4000)
            return None
        self.definir_montage(nouveau)
        return nouveau.texte(cle)

    def editer_brut(self, cle: str) -> None:
        self.editer_valeur_montage(cle)

    def ajuster_brut(self, cle: str, sens: int, fin: bool) -> Optional[str]:
        return self.ajuster_valeur_montage(cle, sens, fin)

    # -- usinage : la gamme de la pièce et ses trajectoires ------------------------------------

    def profil_usinage(self):
        """Le profil tourné de la pièce, tiré des contours fermés résolus.

        Il est recalculé après chaque résolution, jamais recopié : c'est la règle posée pour les
        séquences d'usinage, qui référencent le profil et ne gardent rien du dessin.
        """
        if self._profil_usinage is None:
            self._profil_usinage = profil_exterieur(self.vue.polylignes_contours())
        return self._profil_usinage

    def trajectoire_de(self, sequence: Sequence) -> Trajectoire:
        """La trajectoire d'une séquence, calculée depuis le profil résolu et le montage courant."""
        return trajectoire(sequence, self.profil_usinage(), self.montage)

    def _rafraichir_usinage(self, redessiner: bool = True) -> None:
        """Après une résolution ou un changement de montage : profil, passes et trajectoire montrée."""
        self._profil_usinage = None
        self._etats_matiere = None
        self.zone_usinage.rafraichir()
        self._pousser_trajectoire(redessiner)

    def _pousser_trajectoire(self, redessiner: bool = True) -> None:
        """Dessine sur l'esquisse la trajectoire de la séquence choisie et la matière à cette étape."""
        sequence = self.zone_usinage.sequence_courante()
        self.vue.sequence = sequence
        self.vue.trajectoire = self.trajectoire_de(sequence) if sequence is not None else None
        self._pousser_matiere()
        if redessiner:
            self.vue.reconstruire()

    def editer_valeur_sequence(self, cle: str) -> None:
        """Double-clic sur une cote de la séquence montrée : la profondeur d'un perçage, par exemple."""
        s = self.zone_usinage.sequence_courante()
        if s is None or cle not in s.cotes_dessinees():
            return
        valeur, ok = self._demander_valeur(s.libelle_cote(cle), "mm", s.valeur_cote(cle, self.montage), 0.0)
        if ok:
            s.definir_valeur_cote(cle, valeur, self.montage)
            self._apres_reglage_sequence()

    def ajuster_valeur_sequence(self, cle: str, sens: int, fin: bool) -> Optional[str]:
        """Molette ou glisser sur une cote de la séquence : un pas par cran, un dixième avec Maj."""
        s = self.zone_usinage.sequence_courante()
        if s is None or cle not in s.cotes_dessinees():
            return None
        pas = PAS_MOLETTE / 10.0 if fin else PAS_MOLETTE
        s.definir_valeur_cote(cle, max(0.0, s.valeur_cote(cle, self.montage) + sens * pas), self.montage)
        self._apres_reglage_sequence()
        return s.texte_cote(cle, self.montage)

    def _apres_reglage_sequence(self) -> None:
        """Une cote de séquence a changé : passes, longueur de coupe, trajectoire et matière suivent."""
        self._etats_matiere = None
        self.zone_usinage.rafraichir()
        self._marquer_modifie(True)
        self._pousser_trajectoire()

    def _pousser_matiere(self) -> None:
        """La matière qui reste après l'étape choisie, et en vif ce que cette étape vient d'enlever."""
        if self._etats_matiere is None:
            self._etats_matiere = etats(self.gamme, self.montage, self.trajectoire_de)
        suite = self._etats_matiere
        if len(suite) < 2:                   # pas de gamme : le dessin reste celui de l'esquisse seule
            self.vue.matiere = self.vue.matiere_enlevee = []
            self.vue.filets = self.vue.filets_neufs = []
            return
        k = min(max(self.zone_usinage.etape(), 0), len(suite) - 1)
        self.vue.matiere = suite[k].contours()
        self.vue.matiere_enlevee = suite[k].enlevee_depuis(suite[k - 1]) if k else []
        self.vue.filets = list(suite[k].filets)
        self.vue.filets_neufs = suite[k].filets_depuis(suite[k - 1]) if k else []

    def _gamme_changee(self) -> None:
        self._marquer_modifie(True)
        self._etats_matiere = None           # l'ordre ou les réglages ont changé : la matière aussi
        self._pousser_trajectoire()

    def _sequence_choisie(self, _ident: int) -> None:
        self._pousser_trajectoire()

    def _etape_choisie(self, _rang: int) -> None:
        self._pousser_trajectoire()

    # -- cotes du mors : édition en place, le reste grisé jusqu'à validation ----------------------

    def commencer_edition_mors(self) -> None:
        """Depuis le menu de la référence du mors : ses cotes s'affichent et se règlent, le reste se grise."""
        if self.vue.mode_mors:
            return
        self._montage_avant_mors = copy.deepcopy(self.montage)
        self.vue.mode_mors = True
        self.vue.reconstruire()
        self.statusBar().showMessage("Cotes du mors : L longueur d'un étage, h épaulement derrière lui, E épaisseur "
                                     "au fond. Double-clic ou clic droit + molette. Entrée valide, Échap annule.")

    def valider_edition_mors(self) -> None:
        if not self.vue.mode_mors:
            return
        self._montage_avant_mors = None
        self.vue.mode_mors = False
        self.vue.reconstruire()
        self.statusBar().showMessage("Cotes du mors validées.", 4000)

    def annuler_edition_mors(self) -> None:
        if not self.vue.mode_mors:
            return
        avant, self._montage_avant_mors = self._montage_avant_mors, None
        self.vue.mode_mors = False
        if avant is not None:
            self.definir_montage(avant)
        else:
            self.vue.reconstruire()
        self.statusBar().showMessage("Cotes du mors : modifications abandonnées.", 4000)

    def _modifier_prise(self, action) -> bool:
        """Applique `action` à une copie du montage ; refusée avec son message si la prise n'est pas réalisable."""
        nouveau = copy.deepcopy(self.montage)
        try:
            action(nouveau)
        except ErreurEsquisse as exc:
            self.statusBar().showMessage(str(exc), 6000)
            return False
        self.definir_montage(nouveau)
        self.statusBar().showMessage(nouveau.description_prise().capitalize() + ".", 6000)
        return True

    def retourner_mors(self) -> bool:
        """Double-clic sur le mors : face étagée vers l'axe ou vers l'extérieur."""
        return self._modifier_prise(lambda mo: mo.retourner_mors())

    def definir_serrage(self, serrage: str) -> bool:
        return self._modifier_prise(lambda mo: mo.definir_serrage(serrage))

    def definir_appui(self, appui: int) -> bool:
        return self._modifier_prise(lambda mo: mo.definir_appui(appui))

    def regler_montage(self) -> None:
        dlg = DialogueMontage(self.montage, self)
        if dlg.exec() == DialogueMontage.DialogCode.Accepted:
            self.definir_montage(dlg.montage_resultat())
            self.statusBar().showMessage("Machine et montage mis à jour.", 4000)

    def _basculer_montage(self, actif: bool) -> None:
        self.vue.montage_visible = actif
        self.reglages.set("montage.visible", actif)
        self.vue.reconstruire()
        self._pousser_montage_3d()

    def _basculer_zone_atelier(self, actif: bool) -> None:
        self.zone_atelier.setVisible(actif)
        self.reglages.set("atelier.visible", actif)

    def _zone_atelier_visible(self, visible: bool) -> None:
        """La zone masquée ou rouverte : le menu suit (et le réglage avec lui). Tant que la fenêtre n'est
        pas affichée, Qt annonce la zone masquée : on n'en tient pas compte."""
        if not self.isVisible() or self.isMinimized() or not hasattr(self, "act_zone_atelier"):
            return
        self.act_zone_atelier.setChecked(visible)

    def _regler_volet(self, cle: str, deploye: bool) -> None:
        """Le volet commandé depuis le menu : même effet qu'un clic sur son bandeau."""
        volet = self.zone_atelier.volets[cle]
        if volet.est_deploye() != deploye:
            volet.definir_deploye(deploye)
        self._volet_bascule(cle, deploye)

    def _volet_bascule(self, cle: str, deploye: bool) -> None:
        """Un volet replié ou déplié : on mémorise, et la zone reprend la largeur qu'il lui faut."""
        self.reglages.set("volet." + cle, deploye)
        if self.zone_atelier.isVisible():
            self.resizeDocks([self.zone_atelier], [self.zone_atelier.largeur_souhaitee()],
                             Qt.Orientation.Horizontal)

    def _basculer_vue3d(self, actif: bool) -> None:
        if self.vue3d is None:
            return
        self.vue3d.setVisible(actif)
        if actif:
            self.vue.placer_superposition()
        self.reglages.set("vue3d.visible", actif)

    def _basculer_aimant(self, cle: str, actif: bool) -> None:
        self.vue.aimants[cle] = actif
        self.reglages.set("aimant." + cle, actif)

    def choisir_outil(self, outil: str) -> None:
        if outil not in self.actions_outils:
            return
        self.vue.definir_outil(outil)
        self.actions_outils[outil].setChecked(True)

    def _rafraichir_titre(self) -> None:
        nom = os.path.basename(self.chemin) if self.chemin else "Sans titre"
        self.setWindowTitle(f"{APP_NAME} — {nom}{' *' if self._modifie else ''}")

    def _marquer_modifie(self, etat: bool = True) -> None:
        self._modifie = etat
        self._rafraichir_titre()

    # -- modifications du modèle (contrôleur) -------------------------------------------------

    def _resoudre_apres_construction(self) -> Resultat:
        self.solveur.construire()
        return self.solveur.resoudre()

    def _modifier(self, action: Callable[[], object], message: str = "") -> bool:
        """Applique une modification de structure : annulation, reconstruction, résolution, affichage."""
        avant = self.esquisse.to_json()
        try:
            action()
        except ErreurEsquisse as exc:
            self.statusBar().showMessage(str(exc), 6000)
            self._charger_json(avant)          # l'action a pu modifier le modèle avant d'échouer : on le restaure
            self._appliquer_resultat(self.solveur.resoudre())
            return False
        res = self._resoudre_apres_construction()
        self._pousser_annulation(avant)
        self._appliquer_resultat(res)
        if message:
            self.statusBar().showMessage(message, 4000)
        return True

    def _pousser_annulation(self, avant: str) -> None:
        self._annuler.append(avant)
        del self._annuler[:-MAX_ANNULATION]
        self._retablir.clear()
        self._marquer_modifie(True)
        self._rafraichir_annulation()

    def _rafraichir_annulation(self) -> None:
        self.act_annuler.setEnabled(bool(self._annuler))
        self.act_retablir.setEnabled(bool(self._retablir))

    def _point_depuis_accroche(self, acc: Accroche) -> int:
        e = self.esquisse
        if acc.point is not None and acc.point in e.points:
            return acc.point
        p = e.ajouter_point(acc.z, acc.x)
        if acc.courbe is not None and e.genre(acc.courbe) in ("ligne", "arc"):
            typ = TypeRelation.POINT_SUR_LIGNE if e.genre(acc.courbe) == "ligne" else TypeRelation.POINT_SUR_ARC
            e.ajouter_relation(typ, (p.id, acc.courbe))
        else:
            if acc.sur_axe:
                e.ajouter_relation(TypeRelation.SUR_AXE, (p.id,))
            if acc.sur_origine:
                e.ajouter_relation(TypeRelation.ORIGINE_Z, (p.id,))
            if acc.reference and acc.reference in e.references:
                e.ajouter_relation(TypeRelation.SUR_REFERENCE, (p.id,), reference=acc.reference)
        return p.id

    def ajouter_ligne(self, debut: Accroche, fin: Accroche, auto: Optional[TypeRelation] = None) -> Optional[int]:
        """Ajoute une ligne entre deux accrochages. Renvoie l'identifiant du point d'arrivée."""
        e = self.esquisse
        avant = e.to_json()
        try:
            p1 = self._point_depuis_accroche(debut)
            p2 = self._point_depuis_accroche(fin)
            if p1 == p2:
                return None
            li = e.ajouter_ligne(p1, p2)
            rel = e.ajouter_relation(auto, (li.id,)) if auto else None
        except ErreurEsquisse as exc:
            self.statusBar().showMessage(str(exc), 6000)
            self._charger_json(avant)
            return None
        res = self._resoudre_apres_construction()
        if rel is not None and (not res.succes or rel.id in res.conflits or rel.id in res.redondants):
            e.supprimer(rel.id)           # la relation automatique gêne ou n'apporte rien : on la retire
            res = self._resoudre_apres_construction()
        self._pousser_annulation(avant)
        self._appliquer_resultat(res)
        return p2

    def ajouter_arc(self, debut: Accroche, fin: Accroche, centre: Tuple[float, float], horaire: bool) -> None:
        e = self.esquisse

        def action():
            p1 = self._point_depuis_accroche(debut)
            p2 = self._point_depuis_accroche(fin)
            c = e.ajouter_point(*centre)
            e.ajouter_arc(c.id, p1, p2, horaire)

        self._modifier(action)

    def elaguer(self, coups: List[Tuple[int, float]], mode: str) -> None:
        """Applique l'élagage à chaque (élément, paramètre) traversé par le trait."""
        if not coups:
            self.statusBar().showMessage("Élaguer : le trait n'a traversé aucune ligne ni aucun arc.", 4000)
            return
        e = self.esquisse

        def action():
            for ident, t in coups:
                if e.genre(ident) in ("ligne", "arc"):
                    elagage.elaguer(e, ident, t, mode)

        self.vue.selection = []
        self._modifier(action)
        self._selection_changee()

    def debut_glissement(self) -> None:
        self._avant_glissement = self.esquisse.to_json()

    def glisser(self, point_id: int, z: float, x: float) -> None:
        if self.solveur.glisser(point_id, z, x):
            self.vue.reconstruire()

    def fin_glissement(self) -> None:
        if self._avant_glissement is None:
            return
        apres = self.esquisse.to_json()
        if apres != self._avant_glissement:
            self._pousser_annulation(self._avant_glissement)
        self._avant_glissement = None
        res = self.solveur.diagnostiquer(Resultat(True, "ok"))
        self._appliquer_resultat(res)

    def deplacer_etiquette(self, cote_id: int, dz: float, dx: float) -> None:
        e = self.esquisse
        c = e.cotes.get(cote_id)
        if c is None:
            return
        c.decalage = (c.decalage[0] + dz, c.decalage[1] + dx)
        self._marquer_modifie(True)
        if c.type == TypeCote.ANGLE:
            # l'étiquette passée dans un autre secteur : la cote mesure désormais celui-là (le supplément, ou
            # l'angle depuis l'autre bout), sans que la géométrie bouge
            ancre = e.ancre_angle(c.elements)
            secteur = e.secteur_angle(c.elements, (ancre[0] + c.decalage[0], ancre[1] + c.decalage[1]))
            if secteur != c.secteur:
                c.secteur = secteur
                c.valeur = e.angle_secteur(c.elements, secteur)
                self._appliquer_resultat(self._resoudre_apres_construction())
                return
        self.vue.reconstruire()

    def editer_cote(self, cote_id: int, variante: str = "valeur") -> None:
        """Change la valeur d'une cote. Pour un diamètre, `variante` = "rayon" édite le rayon équivalent."""
        c = self.esquisse.cotes.get(cote_id)
        if c is None:
            return
        libelle = LIBELLES_COTE[c.type]
        facteur = 1.0
        if c.type == TypeCote.DIAMETRE and variante == "rayon":
            libelle, facteur = "Rayon", 2.0
        maitresse = self.esquisse.cote_maitresse(cote_id)
        if maitresse is not None:
            self.statusBar().showMessage(f"Cette cote suit la cote {self.esquisse.texte_cote(self.esquisse.cotes[maitresse])} "
                                         "par une relation « égal » : réglez celle-là, ou supprimez la relation.", 8000)
            return
        if c.pilotee:
            rep = QMessageBox.question(self, libelle, f"Cette cote est pilotée : elle mesure {self.esquisse.texte_cote(c)} "
                                       "et suit la géométrie.\nLa rendre pilotante avec cette valeur ?",
                                       QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                       QMessageBox.StandardButton.No)
            if rep == QMessageBox.StandardButton.Yes:
                self.basculer_pilotee(cote_id)
            return
        unite = "°" if c.type == TypeCote.ANGLE else "mm"
        mini = -360.0 if c.type == TypeCote.ANGLE else (-1e6 if c.type in COTES_SIGNEES else 0.0)
        saisie, ok = self._demander_valeur(libelle, unite, c.valeur / facteur, mini)
        valeur = saisie * facteur
        if not ok or abs(valeur - c.valeur) < 1e-12:
            return
        avant = self.esquisse.to_json()
        res = self.solveur.modifier_cote(cote_id, valeur)
        if not res.succes:
            self.statusBar().showMessage(f"Impossible d'appliquer {libelle} = {valeur:g} : "
                                         "la géométrie ne peut pas suivre. Valeur conservée.", 8000)
            self._appliquer_resultat(res)
            return
        self._pousser_annulation(avant)
        self._appliquer_resultat(res)

    def appliquer_relation(self, type_: TypeRelation) -> None:
        sel = list(self.vue.selection)
        if not sel:
            self.statusBar().showMessage("Sélectionnez d'abord les éléments concernés.", 5000)
            return
        e = self.esquisse
        if type_ == TypeRelation.POINT_SUR_LIGNE and not e.relation_possible(type_, sel) \
                and e.relation_possible(TypeRelation.POINT_SUR_ARC, sel):
            type_ = TypeRelation.POINT_SUR_ARC
        nouvelle = []

        def action():
            r = e.ajouter_relation(type_, sel)
            nouvelle.append(r.id)

        if self._modifier(action):
            if nouvelle and nouvelle[0] in self.resultat.conflits:
                self.statusBar().showMessage(f"{LIBELLES_RELATION[type_]} : relation en conflit avec les autres. "
                                             "Annulez (Ctrl+Z) ou supprimez-la.", 8000)
            else:
                self.vue.selection = []
                self.vue.reconstruire()
                self._selection_changee()

    def _demander_valeur(self, libelle: str, unite: str, defaut: float, mini: float) -> Tuple[float, bool]:
        """Boîte de saisie d'une valeur de cote. Isolée pour pouvoir être remplacée dans les tests."""
        return QInputDialog.getDouble(self, libelle, f"{libelle} ({unite}) :", defaut, mini, 1e6, 3)

    def coter_selection(self) -> None:
        """Pose la cote déduite de la sélection courante, au placement par défaut."""
        sel = tuple(self.vue.selection)
        if not sel:
            self.statusBar().showMessage("Sélectionnez d'abord les éléments à coter, ou prenez l'outil Cote.", 5000)
            return
        deduction = self.vue.deduire_cote(sel)
        if deduction is None:
            self.statusBar().showMessage("Pas de cote pour cette sélection.", 5000)
            return
        self.poser_cote(*deduction)

    def poser_cote(self, type_: TypeCote, elements: Tuple[int, ...], decalage: Tuple[float, float],
                   reference: str = "") -> None:
        """Ajoute la cote à la mesure actuelle ; si elle sur-contraint, elle devient pilotée sans rien demander ;
        sinon la valeur est demandée. Appelé par l'outil Cote, par « Coter : … » et « Coter depuis … »."""
        e = self.esquisse
        sel = tuple(elements)
        secteur = 0
        try:
            e.verifier_cote(type_, sel)
            if type_ == TypeCote.ANGLE:
                # le secteur mesuré est celui où l'étiquette est posée, comme dans une esquisse de CAO
                ancre = e.ancre_angle(sel)
                secteur = e.secteur_angle(sel, (ancre[0] + decalage[0], ancre[1] + decalage[1]))
            mesure = e.mesurer(type_, sel, reference, secteur)
        except ErreurEsquisse as exc:
            self.statusBar().showMessage(str(exc), 6000)
            return
        libelle = LIBELLES_COTE[type_]
        if reference and reference in e.references:
            libelle = f"Écart depuis : {e.references[reference].libelle}"
        avant = e.to_json()
        try:
            c = e.ajouter_cote(type_, sel, mesure, decalage, reference, secteur)
        except ErreurEsquisse as exc:
            self.statusBar().showMessage(str(exc), 6000)
            return
        res = self._resoudre_apres_construction()
        if c.id in res.conflits or c.id in res.redondants or not res.succes:
            # la géométrie est déjà déterminée : cote pilotée, grisée, qui mesure ; sa valeur ne se demande pas
            c.pilotee = True
            res = self._resoudre_apres_construction()
            self._pousser_annulation(avant)
            self._appliquer_resultat(res)
            self.statusBar().showMessage(f"{libelle} : la géométrie était déjà déterminée. "
                                         "Cote posée en cote pilotée (grisée, entre parenthèses).", 8000)
        else:
            unite = "°" if type_ == TypeCote.ANGLE else "mm"
            mini = -360.0 if type_ == TypeCote.ANGLE else (-1e6 if type_ in COTES_SIGNEES else 0.0)
            valeur, ok = self._demander_valeur(libelle, unite, abs(mesure) if mini == 0 else mesure, mini)
            if not ok:
                self._charger_json(avant)                      # abandon : la cote n'est pas posée
                self._appliquer_resultat(self.solveur.resoudre())
                return
            if abs(valeur - c.valeur) > 1e-12:
                res2 = self.solveur.modifier_cote(c.id, valeur)
                if res2.succes:
                    res = res2
                else:
                    self.statusBar().showMessage(f"{libelle} = {valeur:g} : la géométrie ne peut pas suivre, "
                                                 f"cote posée à {c.valeur:g}.", 8000)
            self._pousser_annulation(avant)
            self._appliquer_resultat(res)
        self.vue.selection = []
        self.vue.reconstruire()
        self._selection_changee()

    def ajuster_cote(self, cote_id: int, sens: int, variante: Optional[str], fin: bool) -> Optional[str]:
        """Molette sur une étiquette : la cote monte ou descend d'un pas. Renvoie le texte à afficher, ou None."""
        c = self.esquisse.cotes.get(cote_id)
        if c is None:
            return None
        if c.pilotee:
            self.statusBar().showMessage("Cote pilotée : elle mesure, elle ne se règle pas.", 4000)
            return None
        if self.esquisse.cote_maitresse(cote_id) is not None:
            self.statusBar().showMessage("Cette cote en suit une autre par « égal » : réglez celle-là.", 4000)
            return None
        pas = PAS_MOLETTE / 10.0 if fin else PAS_MOLETTE
        if c.type == TypeCote.DIAMETRE and variante == "rayon":
            pas *= 2.0                                   # un pas de rayon vaut deux pas de diamètre
        valeur = c.valeur + sens * pas
        if c.type not in COTES_SIGNEES:
            valeur = max(0.0, valeur)
        if abs(valeur - c.valeur) < 1e-12:
            return self.esquisse.texte_cote(c)
        if self._avant_ajustement is None:
            self._avant_ajustement = self.esquisse.to_json()
        res = self.solveur.modifier_cote(cote_id, valeur)
        self._appliquer_resultat(res)
        if not res.succes:
            self.statusBar().showMessage("La géométrie ne peut pas suivre cette valeur.", 4000)
        self._marquer_modifie(True)
        return self.esquisse.texte_rayon(c) if (c.type == TypeCote.DIAMETRE and variante == "rayon") \
            else self.esquisse.texte_cote(c)

    def fin_ajustement(self) -> None:
        """Relâchement du bouton droit : le réglage à la molette devient une seule étape d'annulation."""
        if self._avant_ajustement is not None:
            if self._avant_ajustement != self.esquisse.to_json():
                self._pousser_annulation(self._avant_ajustement)
            self._avant_ajustement = None

    def arrondir(self, point_id: int) -> None:
        valeur, ok = self._demander_valeur("Rayon de l'arrondi", "mm", self._rayon_arrondi, 0.001)
        if not ok:
            return
        self._rayon_arrondi = valeur
        decalage = self.vue.decalage_par_defaut(TypeCote.RAYON, ())
        self._modifier(lambda: coins.arrondir(self.esquisse, point_id, valeur, decalage))

    def chanfreiner(self, point_id: int) -> None:
        valeur, ok = self._demander_valeur("Longueur du chanfrein", "mm", self._longueur_chanfrein, 0.001)
        if not ok:
            return
        self._longueur_chanfrein = valeur
        decalage = self.vue.decalage_par_defaut(TypeCote.ANGLE, ())
        self._modifier(lambda: coins.chanfreiner(self.esquisse, point_id, valeur, decalage))

    def basculer_pilotee(self, cote_id: int) -> bool:
        """Passe une cote de pilotante à pilotée ou l'inverse. Une cote qui sur-contraindrait reste pilotée."""
        c = self.esquisse.cotes.get(cote_id)
        if c is None:
            return False
        avant = self.esquisse.to_json()
        c.pilotee = not c.pilotee
        res = self._resoudre_apres_construction()
        if not c.pilotee and (not res.succes or c.id in res.conflits or c.id in res.redondants):
            c.pilotee = True
            self._appliquer_resultat(self._resoudre_apres_construction())
            self.statusBar().showMessage("Cette cote sur-contraindrait l'esquisse : elle reste pilotée. "
                                         "Supprimez d'abord une autre contrainte.", 8000)
            return False
        self._pousser_annulation(avant)
        self._appliquer_resultat(res)
        return True

    def supprimer_selection(self) -> None:
        sel = list(self.vue.selection)
        if not sel:
            return

        def action():
            for ident in sel:
                self.esquisse.supprimer(ident)

        self.vue.selection = []
        self._modifier(action)
        self._selection_changee()

    # -- annulation ------------------------------------------------------------------------

    def _synchroniser_references(self) -> None:
        """Les plans du montage (face des mors, du mandrin…) que l'esquisse peut viser, relus du montage courant."""
        montage = getattr(self, "montage", None)
        if montage is not None:
            self.esquisse.references = {r.nom: r for r in montage.references()}

    def _charger_json(self, texte: str) -> None:
        """Recharge l'esquisse seule (annulation) ; le montage ne fait pas partie de la pile d'annulation."""
        self.esquisse = Esquisse.from_json(texte)
        self._synchroniser_references()
        self.solveur = AdaptateurSolveur(self.esquisse)
        self.vue.definir_esquisse(self.esquisse)

    def _charger_piece(self, texte: str) -> None:
        piece = Piece.from_json(texte)
        self.esquisse = piece.esquisse
        self.montage = piece.montage
        self.gamme = piece.gamme
        self._synchroniser_references()
        self.solveur = AdaptateurSolveur(self.esquisse)
        self.vue.montage = self.montage
        self.vue.definir_esquisse(self.esquisse)
        self.vue.trajectoire = self.vue.sequence = None
        self.vue.matiere = self.vue.matiere_enlevee = []
        self.vue.filets = self.vue.filets_neufs = []
        self._profil_usinage = self._etats_matiere = None
        self.zone_usinage.definir_gamme(self.gamme, self.trajectoire_de)
        self._pousser_montage_3d()

    def annuler(self) -> None:
        if not self._annuler:
            return
        self._retablir.append(self.esquisse.to_json())
        self._charger_json(self._annuler.pop())
        self._appliquer_resultat(self.solveur.resoudre())
        self._marquer_modifie(True)
        self._rafraichir_annulation()

    def retablir(self) -> None:
        if not self._retablir:
            return
        self._annuler.append(self.esquisse.to_json())
        self._charger_json(self._retablir.pop())
        self._appliquer_resultat(self.solveur.resoudre())
        self._marquer_modifie(True)
        self._rafraichir_annulation()

    # -- fichiers ----------------------------------------------------------------------------

    def _confirmer_abandon(self) -> bool:
        if not self._modifie:
            return True
        rep = QMessageBox.question(self, APP_NAME, "L'esquisse a été modifiée. Enregistrer avant de continuer ?",
                                   QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard |
                                   QMessageBox.StandardButton.Cancel, QMessageBox.StandardButton.Save)
        if rep == QMessageBox.StandardButton.Cancel:
            return False
        if rep == QMessageBox.StandardButton.Save:
            return self.enregistrer()
        return True

    def nouveau(self) -> None:
        if not self._confirmer_abandon():
            return
        self._charger_piece(Piece(Esquisse(), self._montage_par_defaut()).to_json())
        self.chemin = None
        self._annuler.clear()
        self._retablir.clear()
        self._marquer_modifie(False)
        self._rafraichir_annulation()
        self._appliquer_resultat(self.solveur.resoudre())
        self.vue.tout_voir()

    def ouvrir(self) -> None:
        if not self._confirmer_abandon():
            return
        dossier = self.reglages.get("dernierDossier", "") or ""
        chemin, _ = QFileDialog.getOpenFileName(self, "Ouvrir une esquisse", dossier, FILTRE_FICHIERS)
        if chemin:
            self.ouvrir_fichier(chemin)

    def ouvrir_fichier(self, chemin: str) -> bool:
        try:
            with open(chemin, "r", encoding="utf-8") as f:
                texte = f.read()
            self._charger_piece(texte)
        except (OSError, ErreurEsquisse) as exc:
            QMessageBox.warning(self, APP_NAME, f"Impossible d'ouvrir le fichier :\n{chemin}\n\n{exc}")
            self.reglages.remove_recent(chemin)
            return False
        self.chemin = chemin
        self.reglages.add_recent(chemin)
        self.reglages.set("dernierDossier", os.path.dirname(chemin))
        self._annuler.clear()
        self._retablir.clear()
        self._marquer_modifie(False)
        self._rafraichir_annulation()
        self._appliquer_resultat(self.solveur.resoudre())
        self.vue.tout_voir()
        self.log.info("ouverture %s", chemin)
        return True

    def enregistrer(self) -> bool:
        if not self.chemin:
            return self.enregistrer_sous()
        return self._ecrire(self.chemin)

    def enregistrer_sous(self) -> bool:
        dossier = self.chemin or self.reglages.get("dernierDossier", "") or ""
        chemin, _ = QFileDialog.getSaveFileName(self, "Enregistrer l'esquisse", dossier, FILTRE_FICHIERS)
        if not chemin:
            return False
        if not chemin.lower().endswith(".ctg"):
            chemin += ".ctg"
        return self._ecrire(chemin)

    def _ecrire(self, chemin: str) -> bool:
        try:
            tmp = chemin + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                f.write(Piece(self.esquisse, self.montage, self.gamme).to_json())
            os.replace(tmp, chemin)
        except OSError as exc:
            QMessageBox.warning(self, APP_NAME, f"Enregistrement impossible :\n{chemin}\n\n{exc}")
            return False
        self.chemin = chemin
        self.reglages.add_recent(chemin)
        self.reglages.set("dernierDossier", os.path.dirname(chemin))
        self._marquer_modifie(False)
        self.statusBar().showMessage(f"Enregistré : {chemin}", 4000)
        self.log.info("enregistrement %s", chemin)
        return True

    def _remplir_recents(self) -> None:
        self.menu_recents.clear()
        fichiers = self.reglages.recent_files()
        if not fichiers:
            act = self.menu_recents.addAction("(aucun)")
            act.setEnabled(False)
            return
        for chemin in fichiers:
            act = self.menu_recents.addAction(chemin)
            act.triggered.connect(lambda _=False, c=chemin: self._ouvrir_recent(c))

    def _ouvrir_recent(self, chemin: str) -> None:
        if self._confirmer_abandon():
            self.ouvrir_fichier(chemin)

    # -- divers ------------------------------------------------------------------------------

    def a_propos(self) -> None:
        compile_ = f"compilé le {BUILD_TIME}" if BUILD_TIME else "exécuté depuis les sources"
        QMessageBox.about(self, f"À propos de {APP_NAME}",
                          f"<b>{APP_NAME} {__version__}</b><br>{compile_}<br><br>"
                          "FAO pour le tour Cazeneuve CT200 à commande NUM 750 T.<br><br>"
                          "Solveur de contraintes : PlaneGCS (FreeCAD), LGPL 2.1 ou ultérieure, "
                          "lié dynamiquement.<br>Interface : Qt 6 via PySide6, LGPL 3.")

    def _restaurer_geometrie(self) -> None:
        geo = self.reglages.get("geometrie")
        if geo is not None:
            try:
                self.restoreGeometry(QByteArray(geo))
            except Exception:
                pass
        else:
            self.resize(1280, 820)

    def closeEvent(self, event: QCloseEvent) -> None:
        if not self._confirmer_abandon():
            event.ignore()
            return
        self.reglages.set("geometrie", self.saveGeometry())
        self.reglages.sync()
        event.accept()
