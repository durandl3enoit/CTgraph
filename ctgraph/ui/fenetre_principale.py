"""Fenêtre principale : colonne d'outils à gauche, esquisse à droite, menus, fichiers, annulation.

C'est aussi le contrôleur de la vue : toute modification du modèle passe par ici, puis par le
solveur, et est enregistrée dans la pile d'annulation.
"""
from __future__ import annotations

import os
from typing import Callable, List, Optional, Tuple

from PySide6.QtCore import QByteArray, QSize, Qt
from PySide6.QtGui import QAction, QActionGroup, QCloseEvent, QKeySequence, QPalette
from PySide6.QtWidgets import (QCheckBox, QFileDialog, QGridLayout, QGroupBox, QHBoxLayout, QInputDialog, QLabel,
                               QListWidget, QListWidgetItem, QMainWindow, QMenu, QMessageBox, QPushButton,
                               QScrollArea, QSizePolicy, QToolButton, QVBoxLayout, QWidget, QWidgetAction)

from .. import APP_NAME, __version__
from ..build_info import BUILD_TIME
from ..esquisse import elagage
from ..esquisse.modele import (LIBELLES_COTE, LIBELLES_RELATION, ErreurEsquisse, Esquisse, TypeCote, TypeRelation)
from ..esquisse.solveur import AdaptateurSolveur, Resultat
from ..icons import icone_action, icone_outil, icone_relation
from ..log import get as get_log
from ..settings import Settings
from .vue_esquisse import AIMANTS_DEFAUT, LIBELLES_AIMANTS, Accroche, VueEsquisse
from .zone_repliable import ZoneRepliable

FILTRE_FICHIERS = "Esquisse CTgraph (*.ctg);;Tous les fichiers (*)"
MAX_ANNULATION = 200
ORDRE_RELATIONS = [TypeRelation.HORIZONTAL, TypeRelation.VERTICAL, TypeRelation.COINCIDENT,
                   TypeRelation.POINT_SUR_LIGNE, TypeRelation.PARALLELE, TypeRelation.PERPENDICULAIRE,
                   TypeRelation.TANGENT, TypeRelation.EGAL, TypeRelation.SUR_AXE, TypeRelation.ORIGINE_Z,
                   TypeRelation.FIXE]
OUTILS = (("selection", "Sélection", "S"), ("ligne", "Ligne", "L"), ("arc", "Arc 3 points", "A"),
          ("cote", "Cote", "C"), ("elaguer", "Élaguer", "E"))


class FenetrePrincipale(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.log = get_log()
        self.reglages = Settings()
        self.premier_lancement = self.reglages.get("geometrie") is None

        self.esquisse = Esquisse()
        self.solveur = AdaptateurSolveur(self.esquisse)
        self.resultat = Resultat(True, "ok", 0)
        self.chemin: Optional[str] = None
        self._modifie = False
        self._annuler: List[str] = []
        self._retablir: List[str] = []
        self._avant_glissement: Optional[str] = None

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
            self.vue3d.setVisible(self.reglages.get_bool("vue3d.visible", True))
            self.vue.vue3d = self.vue3d
            self.vue.placer_superposition()

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

        m_aff = barre.addMenu("&Affichage")
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

    def construire_menu_contextuel(self) -> QMenu:
        """Menu du clic droit : relations et cotes possibles pour la sélection, suppression, outils, vue."""
        menu = QMenu(self)
        sel = list(self.vue.selection)
        possibles = False
        encre, fond = self._encre, self._fond_icone
        menu.relations_proposees = []
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
            deduction = self.vue.deduire_cote(sel)
            if deduction is not None:
                menu.addAction(self.actions_outils["cote"].icon(),
                               f"Coter la sélection ({LIBELLES_COTE[deduction[0]]})", self.coter_selection)
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

    def menu_contextuel(self, pos_globale) -> None:
        self.construire_menu_contextuel().exec(pos_globale)

    def _relation_depuis_menu(self, menu: QMenu, type_: TypeRelation) -> None:
        menu.close()
        self.appliquer_relation(type_)

    # -- état et affichage ---------------------------------------------------------------

    def _appliquer_resultat(self, res: Resultat) -> None:
        self.resultat = res
        self.vue.definir_resultat(res)
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
            it = QListWidgetItem(f"{LIBELLES_RELATION[r.type]} : {cible}")
            it.setData(Qt.ItemDataRole.UserRole, r.id)
            if r.id in conflits:
                it.setForeground(Qt.GlobalColor.red)
            self.liste.addItem(it)
        for c in e.cotes.values():
            cible = ", ".join(f"{e.genre(i)} {i}" for i in c.elements)
            suffixe = " — pilotée" if c.pilotee else ""
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
        c = self.esquisse.cotes.get(cote_id)
        if c is None:
            return
        c.decalage = (c.decalage[0] + dz, c.decalage[1] + dx)
        self._marquer_modifie(True)
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
        if c.pilotee:
            rep = QMessageBox.question(self, libelle, f"Cette cote est pilotée : elle mesure {self.esquisse.texte_cote(c)} "
                                       "et suit la géométrie.\nLa rendre pilotante avec cette valeur ?",
                                       QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                       QMessageBox.StandardButton.No)
            if rep == QMessageBox.StandardButton.Yes:
                self.basculer_pilotee(cote_id)
            return
        unite = "°" if c.type == TypeCote.ANGLE else "mm"
        mini = -360.0 if c.type == TypeCote.ANGLE else (-1e6 if c.type == TypeCote.POSITION_Z else 0.0)
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

    def poser_cote(self, type_: TypeCote, elements: Tuple[int, ...], decalage: Tuple[float, float]) -> None:
        """Demande la valeur, puis ajoute la cote. Appelé par l'outil Cote et par « Coter la sélection »."""
        e = self.esquisse
        sel = tuple(elements)
        try:
            e.verifier_cote(type_, sel)
            mesure = e.mesurer(type_, sel)
        except ErreurEsquisse as exc:
            self.statusBar().showMessage(str(exc), 6000)
            return
        libelle = LIBELLES_COTE[type_]
        unite = "°" if type_ == TypeCote.ANGLE else "mm"
        mini = -360.0 if type_ == TypeCote.ANGLE else (-1e6 if type_ == TypeCote.POSITION_Z else 0.0)
        valeur, ok = self._demander_valeur(libelle, unite, abs(mesure) if mini == 0 else mesure, mini)
        if not ok:
            return
        nouvelle = []

        def action():
            c = e.ajouter_cote(type_, sel, valeur, decalage)
            nouvelle.append(c.id)

        if self._modifier(action):
            if nouvelle and (nouvelle[0] in self.resultat.conflits or nouvelle[0] in self.resultat.redondants
                             or not self.resultat.succes):
                # la cote sur-contraint (conflit ou redondance) ou n'est pas atteignable : elle devient pilotée,
                # grisée, et mesure la géométrie
                e.cotes[nouvelle[0]].pilotee = True
                self._appliquer_resultat(self._resoudre_apres_construction())
                self.statusBar().showMessage(f"{libelle} : la géométrie était déjà déterminée. "
                                             "Cote passée en cote pilotée (grisée, entre parenthèses).", 8000)
            self.vue.selection = []
            self.vue.reconstruire()
            self._selection_changee()

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

    def _charger_json(self, texte: str) -> None:
        self.esquisse = Esquisse.from_json(texte)
        self.solveur = AdaptateurSolveur(self.esquisse)
        self.vue.definir_esquisse(self.esquisse)

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
        self._charger_json(Esquisse().to_json())
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
            self._charger_json(texte)
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
                f.write(self.esquisse.to_json())
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
