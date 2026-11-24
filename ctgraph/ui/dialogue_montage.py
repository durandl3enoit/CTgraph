"""Dialogue « Machine et montage » : machine, mandrin, brut et prise de pièce, contre-pointe."""
from __future__ import annotations

import copy

from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout,
                               QGroupBox, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QSpinBox, QVBoxLayout)

from ..esquisse.modele import ErreurEsquisse
from ..montage import Montage


def _nombre(valeur: float, mini: float = 0.0, maxi: float = 5000.0, decimales: int = 1, suffixe: str = " mm") -> QDoubleSpinBox:
    s = QDoubleSpinBox()
    s.setRange(mini, maxi)
    s.setDecimals(decimales)
    s.setSuffix(suffixe)
    s.setValue(valeur)
    return s


class DialogueMontage(QDialog):
    def __init__(self, montage: Montage, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Machine et montage")
        self.montage = copy.deepcopy(montage)
        m, md, cp, b, p = (self.montage.machine, self.montage.mandrin, self.montage.contre_pointe,
                           self.montage.brut, self.montage.prise)
        colonnes = QHBoxLayout()

        # Machine
        g = QGroupBox("Machine")
        f = QFormLayout(g)
        self.nom = QLineEdit(m.nom)
        self.commande = QLineEdit(m.commande)
        self.course_z = _nombre(m.course_z)
        self.course_x = _nombre(m.course_x)
        self.broche_max = _nombre(m.broche_max, 0, 20000, 0, " tr/min")
        self.chgt_z = _nombre(m.changement_outil_z, -2000, 2000)
        self.chgt_x = _nombre(m.changement_outil_x, 0, 2000)
        f.addRow("Nom", self.nom)
        f.addRow("Commande", self.commande)
        f.addRow("Course Z (à relever)", self.course_z)
        f.addRow("Ø maximal usinable (à relever)", self.course_x)
        f.addRow("Broche maximale (à relever)", self.broche_max)
        f.addRow("Changement d'outil Z", self.chgt_z)
        f.addRow("Changement d'outil Ø", self.chgt_x)
        gauche = QVBoxLayout()
        gauche.addWidget(g)

        # Mandrin
        g = QGroupBox("Mandrin et mors")
        f = QFormLayout(g)
        self.mandrin_modele = QLineEdit(md.modele)
        self.mors_modele = QLineEdit(md.mors_modele)
        self.mandrin_diametre = _nombre(md.diametre)
        self.longueur_corps = _nombre(md.longueur_corps)
        self.alesage = _nombre(md.alesage)
        self.nb_mors = QSpinBox()
        self.nb_mors.setRange(2, 6)
        self.nb_mors.setValue(md.nb_mors)
        self.hauteur_mors = _nombre(md.hauteur_mors)
        self.largeur_mors = _nombre(md.largeur_mors)
        self.epaisseur_mors = _nombre(md.epaisseur_mors)
        self.etage_mors = _nombre(md.etage_mors)
        f.addRow("Mandrin", self.mandrin_modele)
        f.addRow("Mors", self.mors_modele)
        f.addRow("Ø du mandrin", self.mandrin_diametre)
        f.addRow("Longueur du corps (à vérifier)", self.longueur_corps)
        f.addRow("Passage de barre (à vérifier)", self.alesage)
        f.addRow("Nombre de mors", self.nb_mors)
        f.addRow("Hauteur des mors (à vérifier)", self.hauteur_mors)
        f.addRow("Largeur des mors (à vérifier)", self.largeur_mors)
        f.addRow("Épaisseur radiale des mors", self.epaisseur_mors)
        f.addRow("Étage de butée des mors (à vérifier)", self.etage_mors)
        gauche.addWidget(g)
        gauche.addStretch(1)
        colonnes.addLayout(gauche)

        # Brut et prise de pièce
        droite = QVBoxLayout()
        g = QGroupBox("Brut")
        f = QFormLayout(g)
        self.forme = QComboBox()
        self.forme.addItem("Rond plein", "rond")
        self.forme.addItem("Tube", "tube")
        self.forme.setCurrentIndex(1 if b.forme == "tube" else 0)
        self.brut_diametre = _nombre(b.diametre, 0.1)
        self.brut_interieur = _nombre(b.diametre_interieur)
        self.matiere = QLineEdit(b.matiere)
        f.addRow("Forme", self.forme)
        f.addRow("Ø extérieur", self.brut_diametre)
        f.addRow("Ø intérieur (tube)", self.brut_interieur)
        f.addRow("Matière", self.matiere)
        droite.addWidget(g)

        g = QGroupBox("Prise de pièce")
        f = QFormLayout(g)
        self.serrage = QComboBox()
        self.serrage.addItem("Extérieur (mors autour du brut)", "exterieur")
        self.serrage.addItem("Intérieur (mors dans l'alésage d'un tube)", "interieur")
        self.serrage.setCurrentIndex(1 if p.serrage == "interieur" else 0)
        self.depassement = _nombre(p.depassement)
        self.prise_mors = _nombre(p.prise_mors, 0.1)
        self.surepaisseur = _nombre(p.surepaisseur_face)
        f.addRow("Serrage", self.serrage)
        f.addRow("Dépassement face des mors → face finie", self.depassement)
        f.addRow("Longueur serrée, jusqu'à la butée", self.prise_mors)
        f.addRow("Surépaisseur de la face avant", self.surepaisseur)
        droite.addWidget(g)

        g = QGroupBox("Contre-pointe")
        f = QFormLayout(g)
        self.cp_presente = QCheckBox("Présente")
        self.cp_presente.setChecked(cp.presente)
        self.cp_angle = _nombre(cp.angle, 10, 180, 0, "°")
        self.cp_diametre = _nombre(cp.diametre, 1)
        self.cp_longueur = _nombre(cp.longueur, 1)
        f.addRow(self.cp_presente)
        f.addRow("Angle de la pointe", self.cp_angle)
        f.addRow("Ø de la pointe", self.cp_diametre)
        f.addRow("Longueur dessinée", self.cp_longueur)
        droite.addWidget(g)
        droite.addStretch(1)
        colonnes.addLayout(droite)

        boutons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        boutons.accepted.connect(self.accept)
        boutons.rejected.connect(self.reject)
        disposition = QVBoxLayout(self)
        disposition.addWidget(QLabel("Repère de la pièce : Z = 0 sur la face avant finie, Z négatif vers le mandrin."))
        disposition.addLayout(colonnes)
        disposition.addWidget(boutons)

    def montage_resultat(self) -> Montage:
        """Le montage tel que saisi, validé (lève ErreurEsquisse sinon)."""
        mo = self.montage
        m, md, cp, b, p = mo.machine, mo.mandrin, mo.contre_pointe, mo.brut, mo.prise
        m.nom, m.commande = self.nom.text().strip() or m.nom, self.commande.text().strip() or m.commande
        m.course_z, m.course_x, m.broche_max = self.course_z.value(), self.course_x.value(), self.broche_max.value()
        m.changement_outil_z, m.changement_outil_x = self.chgt_z.value(), self.chgt_x.value()
        md.modele, md.mors_modele = self.mandrin_modele.text().strip(), self.mors_modele.text().strip()
        md.diametre, md.longueur_corps, md.alesage = (self.mandrin_diametre.value(), self.longueur_corps.value(),
                                                     self.alesage.value())
        md.nb_mors = self.nb_mors.value()
        md.hauteur_mors, md.largeur_mors, md.epaisseur_mors = (self.hauteur_mors.value(), self.largeur_mors.value(),
                                                              self.epaisseur_mors.value())
        md.etage_mors = self.etage_mors.value()
        p.serrage = self.serrage.currentData()
        b.forme = self.forme.currentData()
        b.diametre, b.diametre_interieur, b.matiere = (self.brut_diametre.value(), self.brut_interieur.value(),
                                                       self.matiere.text().strip())
        p.depassement, p.prise_mors, p.surepaisseur_face = (self.depassement.value(), self.prise_mors.value(),
                                                            self.surepaisseur.value())
        cp.presente, cp.angle, cp.diametre, cp.longueur = (self.cp_presente.isChecked(), self.cp_angle.value(),
                                                           self.cp_diametre.value(), self.cp_longueur.value())
        mo.verifier()
        return mo

    def accept(self) -> None:
        try:
            self.montage_resultat()
        except ErreurEsquisse as exc:
            QMessageBox.warning(self, "Machine et montage", str(exc))
            return
        super().accept()
