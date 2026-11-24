"""Glisser-déposer entre les volets de l'atelier : un porte-plaquette ou une plaquette vers un poste.

Les listes du stock d'outils et des plaquettes sont des sources : tirer une ligne emporte sa désignation.
Le schéma de la tourelle et le tableau des postes sont des cibles : déposer garnit le poste visé.
"""
from __future__ import annotations

from typing import Callable, Tuple

from PySide6.QtCore import QMimeData, Qt
from PySide6.QtWidgets import QAbstractItemView, QTreeWidget

MIME_PORTE_PLAQUETTE = "application/x-ctgraph-porte-plaquette"
MIME_PLAQUETTE = "application/x-ctgraph-plaquette"
MIMES = (MIME_PORTE_PLAQUETTE, MIME_PLAQUETTE)


def charger(type_mime: str, designation: str) -> QMimeData:
    """Le contenu d'un glisser : la désignation, dans son format propre et en texte simple."""
    m = QMimeData()
    m.setData(type_mime, designation.encode("utf-8"))
    m.setText(designation)
    return m


def lire(mime: QMimeData) -> Tuple[str, str]:
    """(type, désignation) portés par un glisser, ou ("", "") si ce n'en est pas un des nôtres."""
    for type_mime in MIMES:
        if mime is not None and mime.hasFormat(type_mime):
            return type_mime, bytes(mime.data(type_mime)).decode("utf-8")
    return "", ""


class ArbreGlissable(QTreeWidget):
    """Arbre dont on peut tirer une ligne : elle emporte la désignation rangée dans `role`.

    Attention : chaque ligne doit porter `Qt.ItemIsDragEnabled` dans ses drapeaux. Fixer les drapeaux d'un
    `QTreeWidgetItem` remplace les valeurs par défaut, et il est vite oublié ; `FLAGS_LIGNE` le rappelle.
    """

    FLAGS_LIGNE = (Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsUserCheckable
                   | Qt.ItemFlag.ItemIsDragEnabled)

    def __init__(self, type_mime: str, role: int, parent=None):
        super().__init__(parent)
        self.type_mime = type_mime
        self.role = role
        self.setDragEnabled(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragOnly)
        self.setDefaultDropAction(Qt.DropAction.CopyAction)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)

    def mimeTypes(self):
        return [self.type_mime, "text/plain"]

    def mimeData(self, items):
        for it in items:
            designation = it.data(0, self.role)
            if designation:
                return charger(self.type_mime, str(designation))
        return QMimeData()


def accueillir(event, trouver_poste: Callable[[object], int],
               accepte: Callable[[int, str, str], bool]) -> Tuple[int, str, str]:
    """Examine un glisser au-dessus d'une cible : rend (poste, type, désignation) si le dépôt est possible,
    sinon (0, type, désignation). Ne touche pas à l'événement : l'appelant accepte ou laisse passer."""
    type_mime, designation = lire(event.mimeData())
    if not type_mime:
        return 0, "", ""
    poste = trouver_poste(event.position().toPoint())
    if poste and accepte(poste, type_mime, designation):
        return poste, type_mime, designation
    return 0, type_mime, designation
