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


def test_normales_lisses_sur_le_cylindre_et_nettes_aux_epaulements():
    poly = [(0, 0), (0, 10), (-20, 10), (-20, 0), (0, 0)]
    data, nb = maillage_revolution([poly], segments=16)
    for i in range(0, len(data), 6):
        z, y, x3, nz, ny, nx3 = data[i:i + 6]
        r = math.hypot(y, x3)
        if abs(r - 10.0) < 1e-6 and -20 < z < 0:
            pass
        if abs(r - 10.0) < 1e-6 and abs(nz) < 1e-6:
            # sommet du cylindre : la normale est radiale et alignée sur la position, pas sur la facette
            assert (ny, nx3) == pytest.approx((y / r, x3 / r), abs=1e-6)
        if abs(r) < 1e-6:
            # sur l'axe : normale axiale (face avant ou arrière), l'angle droit n'est pas lissé
            assert abs(nz) == pytest.approx(1.0, abs=1e-6)


def test_arc_echantillonne_est_lisse():
    from ctgraph.ui.vue_3d import _normales_profil
    # un quart de cercle en 8 segments : angle entre voisins 11°, sous le pli de 30°
    arc = [(10 * math.cos(math.radians(90 - 11.25 * k)) - 10, 10 * math.sin(math.radians(90 - 11.25 * k)))
           for k in range(9)]
    segs = _normales_profil(arc, 30.0)
    assert len(segs) == 8
    for (p, q, n_debut, n_fin) in segs:
        assert n_debut != n_fin                  # lissées avec les voisins, donc différentes aux deux bouts
        assert math.hypot(*n_debut) == pytest.approx(1.0) and math.hypot(*n_fin) == pytest.approx(1.0)
    # la fin d'un segment et le début du suivant partagent la même normale : pas de couture
    for s1, s2 in zip(segs, segs[1:]):
        assert s1[3] == pytest.approx(s2[2])


def test_sans_contour_rien():
    data, nb = maillage_revolution([], segments=8)
    assert nb == 0 and len(data) == 0
    centre, rayon = _bornes(data, nb)
    assert rayon == 50.0


def test_anneau_ne_touche_pas_l_axe():
    poly = [(0, 5), (0, 10), (-5, 10), (-5, 5), (0, 5)]
    data, nb = maillage_revolution([poly], segments=12)
    assert nb == 12 * 4 * 2 * 3            # quatre côtés, deux triangles chacun
