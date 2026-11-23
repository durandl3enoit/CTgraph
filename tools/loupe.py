"""Agrandit des zones d'une capture pour contrôler les détails (symboles, flèches).

Usage : .venv\\Scripts\\python tools\\loupe.py capture.png sortie.png x,y[,x,y...]
Chaque zone de 64 × 44 px autour de (x, y) est agrandie 5 fois et placée côte à côte.
"""
from __future__ import annotations

import sys

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QGuiApplication, QImage, QPainter


def main() -> None:
    app = QGuiApplication(sys.argv)  # noqa: F841
    source, sortie = sys.argv[1], sys.argv[2]
    coords = [int(v) for v in sys.argv[3].split(",")]
    centres = list(zip(coords[0::2], coords[1::2]))
    img = QImage(source)
    largeur, hauteur, facteur = 64, 44, 5
    out = QImage(len(centres) * largeur * facteur, hauteur * facteur, QImage.Format.Format_ARGB32)
    out.fill(Qt.GlobalColor.white)
    p = QPainter(out)
    for i, (x, y) in enumerate(centres):
        zone = img.copy(QRect(x - largeur // 2, y - hauteur // 2, largeur, hauteur))
        zone = zone.scaled(largeur * facteur, hauteur * facteur, Qt.AspectRatioMode.IgnoreAspectRatio,
                           Qt.TransformationMode.FastTransformation)
        p.drawImage(i * largeur * facteur, 0, zone)
    p.end()
    out.save(sortie)
    print("Écrit :", sortie)


if __name__ == "__main__":
    main()
