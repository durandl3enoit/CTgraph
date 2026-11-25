"""Volet « Usinage » : la gamme de la pièce, séquence par séquence.

La liste donne l'ordre d'usinage ; le formulaire règle la séquence choisie, dont la trajectoire se
dessine aussitôt sur l'esquisse. Rien n'est figé : la trajectoire se recalcule depuis le profil résolu
à chaque changement de cote, de montage ou de réglage.

Chaque type d'opération n'a pas les mêmes réglages : le formulaire ne montre que ceux qui comptent
(`CHAMPS_SEQUENCE`). On affecte un poste de tourelle en tapant son numéro, ou en y glissant la
combinaison montée sur un poste, tirée du volet Tourelle.
"""
from __future__ import annotations

from typing import Callable, Dict, Optional

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QDoubleSpinBox, QFormLayout, QGridLayout,
                               QGroupBox, QHBoxLayout, QLabel, QLineEdit, QPushButton, QSpinBox,
                               QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget)

from ..tourelle import nom_poste
from ..usinage import Gamme, Sequence, TypeSequence
from ..usinage.sequences import LIBELLES_SEQUENCE, LIBELLES_Z, USAGES_SEQUENCE
from .transfert import MIME_POSTE, accueillir

COLONNES = ["#", "Opération", "Poste", "Passes", "Coupe"]
ROLE_ID = Qt.ItemDataRole.UserRole
BOUTONS_PAR_RANGEE = 4


class ListeSequences(QTreeWidget):
    """La liste de la gamme. On peut y déposer un poste de tourelle : la séquence visée le prend."""

    depot = Signal(int, int)                 # identifiant de séquence, numéro de poste

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.viewport().setAcceptDrops(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DropOnly)
        self.accepte_depot = lambda sequence_id, poste: False

    def sequence_sous(self, point) -> int:
        it = self.itemAt(point)
        return int(it.data(0, ROLE_ID) or 0) if it is not None else 0

    def _survoler(self, event) -> None:
        # la liste se reconstruit en affectant le poste : on ne touche pas à la sélection pendant le survol
        sequence_id, _, _ = accueillir(event, self.sequence_sous, self._accepte)
        if sequence_id:
            event.acceptProposedAction()
        else:
            event.ignore()

    def _accepte(self, sequence_id: int, type_mime: str, charge: str) -> bool:
        return type_mime == MIME_POSTE and self.accepte_depot(sequence_id, _numero_poste(charge))

    def dragEnterEvent(self, event) -> None:
        self._survoler(event)

    def dragMoveEvent(self, event) -> None:
        self._survoler(event)

    def dropEvent(self, event) -> None:
        sequence_id, _, charge = accueillir(event, self.sequence_sous, self._accepte)
        if not sequence_id:
            event.ignore()
            return
        event.acceptProposedAction()
        poste = _numero_poste(charge)
        QTimer.singleShot(0, lambda: self.depot.emit(sequence_id, poste))


def _numero_poste(charge: str) -> int:
    """Le numéro porté par un glisser de poste : « T7 » ou « T7 PCLNR 2020 K12 + CNMG 120408 »."""
    tete = (charge or "").strip().split(" ")[0].lstrip("Tt")
    return int(tete) if tete.isdigit() else 0


class ZoneUsinage(QWidget):
    """La gamme : liste ordonnée, boutons d'ordre, et le réglage de la séquence choisie."""

    gamme_changee = Signal()                 # la gamme a changé : à enregistrer et à redessiner
    sequence_choisie = Signal(int)           # identifiant de la séquence à montrer sur l'esquisse

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
        entete = QLabel("Gamme d'usinage de la pièce : les séquences s'exécutent dans cet ordre. La "
                        "trajectoire de celle que vous choisissez se dessine sur l'esquisse ; glissez-y "
                        "un poste de la tourelle pour l'y affecter.")
        entete.setWordWrap(True)
        v.addWidget(entete)

        grille = QGridLayout()
        grille.setSpacing(3)
        self.boutons_ajout: Dict[TypeSequence, QPushButton] = {}
        for i, type_ in enumerate(TypeSequence):
            b = QPushButton("+ " + LIBELLES_SEQUENCE[type_].split(" ")[0])
            b.setToolTip(USAGES_SEQUENCE[type_])
            b.clicked.connect(lambda _=False, t=type_: self.ajouter(t))
            grille.addWidget(b, i // BOUTONS_PAR_RANGEE, i % BOUTONS_PAR_RANGEE)
            self.boutons_ajout[type_] = b
        v.addLayout(grille)

        self.liste = ListeSequences()
        self.liste.setColumnCount(len(COLONNES))
        self.liste.setHeaderLabels(COLONNES)
        self.liste.setRootIsDecorated(False)
        self.liste.setUniformRowHeights(True)
        self.liste.setAlternatingRowColors(True)
        self.liste.setMinimumHeight(120)
        self.liste.accepte_depot = self.accepte_poste
        self.liste.depot.connect(self.affecter_poste)
        self.liste.currentItemChanged.connect(self._ligne_choisie)
        self.liste.itemChanged.connect(self._case_changee)
        v.addWidget(self.liste, 1)

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
        self.largeur_outil = self._nombre(" mm", 0.5, 20.0, 2)
        self.largeur = self._nombre(" mm", 0.0, 200.0, 2)
        self.largeur.setSpecialValueText("largeur de l'outil")
        self.diametre_fond = self._nombre(" mm", 0.0, 500.0, 2)
        self.diametre_fond.setSpecialValueText("jusqu'à l'axe")
        self.diametre_outil = self._nombre(" mm", 0.5, 100.0, 2)
        self.pas = self._nombre(" mm", 0.2, 12.0, 2)
        self.hauteur_filet = self._nombre(" mm", 0.0, 20.0, 3)
        self.hauteur_filet.setSpecialValueText("profil ISO métrique")
        self.profondeur = self._nombre(" mm", 0.05, 20.0, 2)
        self.surepaisseur = self._nombre(" mm", 0.0, 10.0, 2)
        self.surepaisseur_face = self._nombre(" mm", 0.0, 10.0, 2)
        self.garde = self._nombre(" mm", 0.0, 50.0, 1)
        self.degagement = self._nombre(" mm", 0.0, 50.0, 1)
        self.z_debut = self._etendue("du bout de la pièce")
        self.z_fin = self._etendue("jusqu'au fond usinable")
        # (clé du champ, intitulé) ; la clé est celle de CHAMPS_SEQUENCE, qui dit quand le montrer
        self.champs: Dict[str, QWidget] = {}
        for cle, intitule, widget in (
                ("", "Nom", self.nom),
                ("", "Poste de tourelle", self.poste),
                ("", "Outil monté", self.lbl_outil),
                ("", "Vitesse de coupe", self.vitesse_coupe),
                ("vitesse_maxi", "Broche maximale", self.vitesse_maxi),
                ("avance", "Avance", self.avance),
                ("", "", self.arrosage),
                ("largeur_outil", "Largeur de l'outil", self.largeur_outil),
                ("largeur", "Largeur de la gorge", self.largeur),
                ("diametre_fond", "Ø au fond", self.diametre_fond),
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
        v.addWidget(self.groupe)

        self.lbl_etat = QLabel("")
        self.lbl_etat.setWordWrap(True)
        v.addWidget(self.lbl_etat)

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

    # -- affichage ------------------------------------------------------------------------

    def rafraichir(self) -> None:
        courante = self.sequence_courante()
        self._blocage = True
        self.liste.clear()
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
        if self.liste.currentItem() is None and self.liste.topLevelItemCount():
            self.liste.setCurrentItem(self.liste.topLevelItem(0))
        for col in range(len(COLONNES)):
            self.liste.resizeColumnToContents(col)
        self._blocage = False
        self._remplir_formulaire()

    def _remplir_formulaire(self) -> None:
        s = self.sequence_courante()
        avant, self._blocage = self._blocage, True
        self.groupe.setEnabled(s is not None)
        if s is None:
            self.groupe.setTitle("Séquence")
            self.lbl_etat.setText("Aucune séquence : ajoutez une opération avec les boutons du haut.")
            self._blocage = avant
            return
        self.groupe.setTitle(f"{LIBELLES_SEQUENCE[s.type]} — {s.libelle()}")
        self.nom.setText(s.nom)
        self.poste.setValue(s.poste)
        self.vitesse_coupe.setValue(s.vitesse_coupe)
        self.vitesse_maxi.setValue(s.vitesse_maxi)
        self.avance.setValue(s.avance)
        self.arrosage.setChecked(s.arrosage)
        self.largeur_outil.setValue(s.largeur_outil)
        self.largeur.setValue(s.largeur)
        self.diametre_fond.setValue(s.diametre_fond)
        self.diametre_outil.setValue(s.diametre_outil)
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

    def _adapter_au_type(self, s: Sequence) -> None:
        """Ne montre que les réglages qui comptent pour ce type, et nomme les bornes en Z pour ce qu'elles sont."""
        attendus = s.champs()
        for cle, widget in self.champs.items():
            if cle not in ("vitesse_maxi", "avance"):
                self.formulaire.setRowVisible(widget, cle in attendus)
        # la broche est fixe en filetage et en perçage, et un filetage avance de son pas
        self.formulaire.setRowVisible(self.vitesse_maxi, not s.vitesse_fixe())
        self.formulaire.setRowVisible(self.avance, s.type != TypeSequence.FILETAGE)
        debut, fin = LIBELLES_Z.get(s.type, ("Z de début", "Z de fin"))
        for widget, texte in ((self.z_debut, debut), (self.z_fin, fin)):
            etiquette = self.formulaire.labelForField(widget)
            if etiquette is not None and texte:
                etiquette.setText(texte)

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
        s = self.gamme.ajouter(type_)
        self.rafraichir()
        self._choisir(s.id)
        self.gamme_changee.emit()
        return s

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
        self.sequence_choisie.emit(int(item.data(0, ROLE_ID)) if item is not None else 0)

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
        s.largeur_outil, s.largeur = self.largeur_outil.value(), self.largeur.value()
        s.diametre_fond, s.diametre_outil = self.diametre_fond.value(), self.diametre_outil.value()
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
