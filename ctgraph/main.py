"""Point d'entrée : `python run.py [fichier.ctg]`."""
from __future__ import annotations

import os
import sys


def main(argv=None) -> int:
    argv = list(sys.argv if argv is None else argv)
    path = next((a for a in argv[1:] if a.lower().endswith(".ctg")), None)
    if path:
        path = os.path.abspath(path)

    # Icône et regroupement corrects dans la barre des tâches Windows.
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("CTgraph.CTgraph")
        except Exception:
            pass

    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication

    from . import APP_NAME
    from .icons import app_icon
    from .log import get as get_log, setup as setup_log

    app = QApplication(argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(APP_NAME)
    app.setWindowIcon(app_icon())
    setup_log()
    log = get_log()

    from .ui.fenetre_principale import FenetrePrincipale

    win = FenetrePrincipale()
    if win.premier_lancement:
        win.showMaximized()
    else:
        win.show()
    if path:
        QTimer.singleShot(0, lambda: win.ouvrir_fichier(path))
    log.info("démarrage (%s)", path or "sans fichier")
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
