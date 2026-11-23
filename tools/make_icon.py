"""Génère assets/ctgraph.ico (icône de l'exécutable) à partir du dessin de icons.py."""
from __future__ import annotations

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from PySide6.QtGui import QGuiApplication, QImage  # noqa: E402

from ctgraph.icons import app_pixmap  # noqa: E402


def main() -> None:
    app = QGuiApplication(sys.argv)  # noqa: F841 - nécessaire pour QPixmap
    out_dir = os.path.join(os.path.dirname(__file__), "..", "assets")
    os.makedirs(out_dir, exist_ok=True)
    ico = os.path.abspath(os.path.join(out_dir, "ctgraph.ico"))
    png = os.path.abspath(os.path.join(out_dir, "ctgraph.png"))
    app_pixmap(256).save(png, "PNG")
    img: QImage = app_pixmap(256).toImage()
    if not img.save(ico, "ICO"):
        raise SystemExit("Écriture de l'icône .ico impossible")
    print("Écrit :", ico)


if __name__ == "__main__":
    main()
