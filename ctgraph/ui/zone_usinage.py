"""Volet « Usinage » : la gamme de la pièce, séquence par séquence.

La liste donne l'ordre d'usinage ; le formulaire règle la séquence choisie, dont la trajectoire se
dessine aussitôt sur l'esquisse. Rien n'est figé : la trajectoire se recalcule depuis le profil résolu
à chaque changement de cote, de montage ou de réglage.
"""
from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QCheckBox, QDoubleSpinBox, QFormLayout, QGroupBox, QHBoxLayout, QLabel,
                               QLineEdit, QPushButton, QSpinBox, QTreeWidget, QTreeWidgetItem, QVBoxLayout,
                               QWidget)

from ..usinage import Gamme, Sequence, TypeSequence
from ..usinage.sequences import LIBELLES_SEQUENCE, USAGES_SEQUENCE

COLONNES = ["#", "Opération", "Poste", "Passes", "Coupe"]
ROLE_ID = Qt.ItemDataRole.UserRole


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
                        "trajectoire de celle que vous choisissez se dessine sur l'esquisse.")
        entete.setWordWrap(True)
        v.addWidget(entete)

        ligne = QHBoxLayout()
        ligne.setSpacing(3)
        self.boutons_ajout = {}
        for type_ in TypeSequence:
            b = QPushButton("+ " + LIBELLES_SEQUENCE[type_].split(" ")[0])
            b.setToolTip(USAGES_SEQUENCE[type_])
            b.clicked.connect(lambda _=False, t=type_: self.ajouter(t))
            ligne.addWidget(b)
            self.boutons_ajout[type_] = b
        v.addLayout(ligne)

        self.liste = QTreeWidget()
        self.liste.setColumnCount(len(COLONNES))
        self.liste.setHeaderLabels(COLONNES)
        self.liste.setRootIsDecorated(False)
        self.liste.setUniformRowHeights(True)
        self.liste.setAlternatingRowColors(True)
        self.liste.setMinimumHeight(120)
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
        f = QFormLayout(self.groupe)
        f.setContentsMargins(8, 6, 8, 6)
        f.setSpacing(4)
        self.nom = QLineEdit()
        self.nom.setPlaceholderText("nom libre, sinon le type suffit")
        self.poste = QSpinBox()
        self.poste.setRange(0, 12)
        self.poste.setSpecialValueText("à choisir")
        self.poste.setPrefix("T ")
        self.lbl_outil = QLabel("—")
        self.lbl_outil.setWordWrap(True)
        self.vitesse_coupe = self._nombre(" m/min", 1.0, 1000.0, 0)
        self.vitesse_maxi = self._nombre(" tr/min", 100.0, 10000.0, 0)
        self.avance = self._nombre(" mm/tr", 0.01, 2.0, 3)
        self.arrosage = QCheckBox("Arrosage")
        self.profondeur = self._nombre(" mm", 0.05, 20.0, 2)
        self.surepaisseur = self._nombre(" mm", 0.0, 10.0, 2)
        self.surepaisseur_face = self._nombre(" mm", 0.0, 10.0, 2)
        self.garde = self._nombre(" mm", 0.0, 50.0, 1)
        self.degagement = self._nombre(" mm", 0.0, 50.0, 1)
        self.z_debut = self._etendue("du bout de la pièce")
        self.z_fin = self._etendue("jusqu'au fond usinable")
        f.addRow("Nom", self.nom)
        f.addRow("Poste de tourelle", self.poste)
        f.addRow("Outil monté", self.lbl_outil)
        f.addRow("Vitesse de coupe", self.vitesse_coupe)
        f.addRow("Broche maximale", self.vitesse_maxi)
        f.addRow("Avance", self.avance)
        f.addRow(self.arrosage)
        f.addRow("Profondeur de passe", self.profondeur)
        f.addRow("Surépaisseur au rayon", self.surepaisseur)
        f.addRow("Surépaisseur de face", self.surepaisseur_face)
        f.addRow("Garde d'approche", self.garde)
        f.addRow("Dégagement", self.degagement)
        f.addRow("Z de début", self.z_debut)
        f.addRow("Z de fin", self.z_fin)
        v.addWidget(self.groupe)

        self.lbl_etat = QLabel("")
        self.lbl_etat.setWordWrap(True)
        v.addWidget(self.lbl_etat)

        for widget in (self.vitesse_coupe, self.vitesse_maxi, self.avance, self.profondeur,
                       self.surepaisseur, self.surepaisseur_face, self.garde, self.degagement,
                       self.z_debut, self.z_fin):
            widget.valueChanged.connect(self._reglage_change)
        self.poste.valueChanged.connect(self._reglage_change)
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

    # -- affichage ------------------------------------------------------------------------

    def rafraichir(self) -> None:
        courante = self.sequence_courante()
        self._blocage = True
        self.liste.clear()
        for rang, s in enumerate(self.gamme, start=1):
            traj = self._trajectoire(s)
            passes = str(traj.nb_passes()) if traj else "—"
            coupe = f"{traj.longueur_coupe():.0f} mm" if traj else "—"
            it = QTreeWidgetItem(self.liste, [str(rang), s.libelle(), f"T {s.poste}" if s.poste else "—",
                                              passes, coupe])
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
            self.lbl_etat.setText("Aucune séquence : ajoutez un dressage, une ébauche ou une finition.")
            self._blocage = avant
            return
        self.groupe.setTitle(f"{LIBELLES_SEQUENCE[s.type]} — {s.libelle()}")
        self.nom.setText(s.nom)
        self.poste.setValue(s.poste)
        self.vitesse_coupe.setValue(s.vitesse_coupe)
        self.vitesse_maxi.setValue(s.vitesse_maxi)
        self.avance.setValue(s.avance)
        self.arrosage.setChecked(s.arrosage)
        self.profondeur.setValue(s.profondeur_passe)
        self.surepaisseur.setValue(s.surepaisseur)
        self.surepaisseur_face.setValue(s.surepaisseur_face)
        self.garde.setValue(s.garde)
        self.degagement.setValue(s.degagement)
        self.z_debut.setValue(s.z_debut if s.z_debut is not None else self.z_debut.minimum())
        self.z_fin.setValue(s.z_fin if s.z_fin is not None else self.z_fin.minimum())
        # une finition ne prend pas de passes ni de surépaisseur : elle suit le profil fini
        finition = s.type == TypeSequence.FINITION
        self.profondeur.setEnabled(not finition)
        self.surepaisseur.setEnabled(not finition)
        self.surepaisseur_face.setEnabled(s.type == TypeSequence.DRESSAGE)
        self._blocage = avant
        self._dire_l_outil()
        self._dire_l_etat(s)

    def _dire_l_etat(self, s: Sequence) -> None:
        traj = self._trajectoire(s)
        if traj is None:
            self.lbl_etat.setText("Trajectoire non calculée : il manque le profil ou le montage.")
            return
        if getattr(traj, "message", ""):
            self.lbl_etat.setText(traj.message)
            return
        self.lbl_etat.setText(f"{traj.nb_passes()} passe(s), {traj.longueur_coupe():.0f} mm en coupe à "
                              f"{s.avance:g} mm/tr. Trait plein : en coupe ; pointillé : en rapide.")

    # -- actions --------------------------------------------------------------------------

    def ajouter(self, type_: TypeSequence) -> Sequence:
        valeurs = {"vitesse_coupe": 250.0, "avance": 0.1} if type_ == TypeSequence.FINITION else {}
        s = self.gamme.ajouter(type_, **valeurs)
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
            it.setText(2, f"T {s.poste}" if s.poste else "—")
            it.setText(3, str(traj.nb_passes()) if traj else "—")
            it.setText(4, f"{traj.longueur_coupe():.0f} mm" if traj else "—")
            self._blocage = avant
            return
