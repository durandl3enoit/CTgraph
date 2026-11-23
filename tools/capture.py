"""Ouvre CTgraph sur l'exemple, en vraie fenêtre, et enregistre une capture PNG.

Usage : .venv\\Scripts\\python tools\\capture.py sortie.png [fichier.ctg]
Sert au contrôle visuel pendant le développement (les tests hors écran n'ont pas de polices).
"""
from __future__ import annotations

import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ["CTGRAPH_SETTINGS"] = os.path.join(tempfile.gettempdir(), "ctgraph_capture.ini")

from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from ctgraph.ui.fenetre_principale import FenetrePrincipale  # noqa: E402
from tools.make_sample import arbre_epaule  # noqa: E402


def main() -> None:
    sortie = sys.argv[1] if len(sys.argv) > 1 else "capture.png"
    app = QApplication(sys.argv)
    win = FenetrePrincipale()
    win.resize(1400, 900)
    win.show()
    if len(sys.argv) > 2:
        win.ouvrir_fichier(sys.argv[2])
    else:
        win._charger_json(arbre_epaule().to_json())
        win._appliquer_resultat(win.solveur.resoudre())
        win.vue.tout_voir()

    def capturer():
        win.grab().save(sortie)
        print("Écrit :", os.path.abspath(sortie))
        win._modifie = False
        app.quit()

    QTimer.singleShot(700, capturer)
    app.exec()


if __name__ == "__main__":
    main()
