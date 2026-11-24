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


def test_icones_toutes_dessinables():
    """Chaque outil et chaque relation a une icône qui se dessine sans erreur (hors écran)."""
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtGui import QColor, QGuiApplication
    from PySide6.QtWidgets import QApplication
    from ctgraph.esquisse.modele import TypeRelation
    from ctgraph.icons import ICONES_OUTILS, icone_outil, icone_relation
    app = QApplication.instance() or QGuiApplication([])  # noqa: F841
    encre, fond = QColor(230, 230, 230), QColor(40, 40, 40)
    for nom in ICONES_OUTILS:
        assert not icone_outil(nom, encre, fond).isNull()
    for t in TypeRelation:
        assert not icone_relation(t.value, encre, fond).isNull()


def test_maillages_du_montage():
    from ctgraph.montage import Montage
    from ctgraph.ui.vue_3d import maillage_boite_radiale, maillages_montage
    data, nb = maillage_boite_radiale(-10, 0, 20, 30, 10, 0.0)
    assert nb == 12 * 3
    for i in range(0, len(data), 6):
        assert math.hypot(*data[i + 3:i + 6]) == pytest.approx(1.0, abs=1e-6)
    m = Montage()
    m.contre_pointe.presente = True
    maillages = maillages_montage(m)
    # corps, trois mors de deux blocs (étage et face de serrage), brut translucide, contre-pointe
    assert len(maillages) == 1 + 3 * 2 + 1 + 1
    assert all(nb > 0 for _, nb, _ in maillages)
    assert sum(1 for _, _, c in maillages if c[3] < 1.0) == 1
    # le brut va de la surépaisseur à la prise dans les mors
    brut = maillages[7][0]
    zs = brut[0::6]
    assert min(zs) == pytest.approx(m.z_brut_arriere()) and max(zs) == pytest.approx(m.z_brut_avant())
    # normales sortantes et parcours accordé, pour l'élimination des faces arrière : sur le corps du mandrin,
    # chaque triangle tourne dans le sens de sa normale, et la normale extérieure s'éloigne de l'axe
    corps = maillages[0][0]
    for i in range(0, len(corps), 18):
        p, q, r = (corps[i + k * 6:i + k * 6 + 3] for k in range(3))
        n = corps[i + 3:i + 6]
        g = ((q[1] - p[1]) * (r[2] - p[2]) - (q[2] - p[2]) * (r[1] - p[1]),
             (q[2] - p[2]) * (r[0] - p[0]) - (q[0] - p[0]) * (r[2] - p[2]),
             (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0]))
        assert g[0] * n[0] + g[1] * n[1] + g[2] * n[2] > 0.0
        rayon = math.hypot(p[1], p[2])
        if abs(rayon - m.mandrin.diametre / 2.0) < 1e-6 and abs(n[0]) < 1e-6:
            assert n[1] * p[1] + n[2] * p[2] > 0.0      # surface extérieure : normale vers le dehors


def test_sans_contour_rien():
    data, nb = maillage_revolution([], segments=8)
    assert nb == 0 and len(data) == 0
    centre, rayon = _bornes(data, nb)
    assert rayon == 50.0


def test_anneau_ne_touche_pas_l_axe():
    poly = [(0, 5), (0, 10), (-5, 10), (-5, 5), (0, 5)]
    data, nb = maillage_revolution([poly], segments=12)
    assert nb == 12 * 4 * 2 * 3            # quatre côtés, deux triangles chacun
