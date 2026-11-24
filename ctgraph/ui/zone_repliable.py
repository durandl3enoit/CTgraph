"""Zone de la colonne d'outils que l'on déploie ou replie d'un clic sur son titre."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QSizePolicy, QToolButton, QVBoxLayout, QWidget


class ZoneRepliable(QFrame):
    basculee = Signal(bool)

    def __init__(self, titre: str, contenu: QWidget, deployee: bool = False, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.contenu = contenu
        self.bouton = QToolButton(self)
        self.bouton.setText(titre)
        self.bouton.setCheckable(True)
        self.bouton.setChecked(deployee)
        self.bouton.setAutoRaise(True)
        self.bouton.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.bouton.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.bouton.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.bouton.setStyleSheet("QToolButton { font-weight: bold; text-align: left; padding: 2px 4px; }")
        self.bouton.toggled.connect(self._basculer)
        disposition = QVBoxLayout(self)
        disposition.setContentsMargins(2, 2, 2, 2)
        disposition.setSpacing(2)
        disposition.addWidget(self.bouton)
        disposition.addWidget(contenu)
        self._basculer(deployee)

    def est_deployee(self) -> bool:
        return self.bouton.isChecked()

    def deployer(self, etat: bool) -> None:
        self.bouton.setChecked(etat)

    def _basculer(self, deployee: bool) -> None:
        self.bouton.setArrowType(Qt.ArrowType.DownArrow if deployee else Qt.ArrowType.RightArrow)
        self.contenu.setVisible(deployee)
        self.basculee.emit(deployee)
