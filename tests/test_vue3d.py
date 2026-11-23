"""Tests du maillage de révolution (sans OpenGL)."""
from __future__ import annotations

import math

import pytest

from ctgraph.ui.vue_3d import _bornes, maillage_revolution


def test_cylindre_ferme_par_l_axe():
    # rectangle posé sur l'axe : face, cylindre, face arrière, retour sur l'axe
    poly = [(0, 0), (0, 10), (-20, 10), (-20, 0), (0, 0)]
    data, nb = maillage_revolution([poly], segments=8)
    # par facette : 1 triangle sur chaque face (l'autre est dégénéré sur l'axe), 2 sur le cylindre, rien sur l'axe
    assert nb == 8 * (1 + 2 + 1) * 3
    assert len(data) == nb * 6
    # normales unitaires
    for i in range(0, len(data), 6):
        n = data[i + 3:i + 6]
        assert math.hypot(*n) == pytest.approx(1.0, abs=1e-5)
    # un sommet du cylindre a un rayon de 10 et sa normale est radiale
    rayons = {round(math.hypot(data[i + 1], data[i + 2]), 6) for i in range(0, len(data), 6)}
    assert rayons == {0.0, 10.0}
    centre, rayon = _bornes(data, nb)
    assert (centre.x(), centre.y(), centre.z()) == pytest.approx((-10.0, 0.0, 0.0), abs=1e-5)
    assert rayon == pytest.approx(10.0, abs=1e-5)


def test_sans_contour_rien():
    data, nb = maillage_revolution([], segments=8)
    assert nb == 0 and len(data) == 0
    centre, rayon = _bornes(data, nb)
    assert rayon == 50.0


def test_anneau_ne_touche_pas_l_axe():
    poly = [(0, 5), (0, 10), (-5, 10), (-5, 5), (0, 5)]
    data, nb = maillage_revolution([poly], segments=12)
    assert nb == 12 * 4 * 2 * 3            # quatre côtés, deux triangles chacun
