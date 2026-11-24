"""Tests de la tourelle : répartition des douze postes VDI 30, désignation du poste en travail."""
from __future__ import annotations

import math

import pytest

from ctgraph.tourelle import DIAMETRE_QUEUE, NORME, Tourelle


def test_douze_postes_vdi_30():
    t = Tourelle()
    assert t.nb_postes == 12 and t.diametre_queue == DIAMETRE_QUEUE == 30.0
    assert "VDI 30" in NORME and t.postes() == list(range(1, 13))
    # un poste tous les 30°, le 1 en haut, la numérotation dans le sens horaire vu de face
    assert [t.angle_poste(n) for n in (1, 2, 4, 7, 12)] == [0.0, 30.0, 90.0, 180.0, 330.0]
    assert t.position_poste(1) == pytest.approx((0.0, t.rayon_implantation), abs=1e-9)
    assert t.position_poste(4) == pytest.approx((t.rayon_implantation, 0.0), abs=1e-9)
    assert t.position_poste(7) == pytest.approx((0.0, -t.rayon_implantation), abs=1e-9)
    # tous les logements sont sur le cercle d'implantation, dans le disque
    for n in t.postes():
        assert math.hypot(*t.position_poste(n)) == pytest.approx(t.rayon_implantation)
        assert t.rayon_implantation + t.diametre_queue / 2 < t.diametre / 2


def test_poste_en_travail():
    t = Tourelle()
    assert t.poste_en_travail == 1
    t.definir_poste(5)
    assert t.poste_en_travail == 5 and "Poste en travail : 5" in t.description()
    for mauvais in (0, 13, -1):
        with pytest.raises(ValueError):
            t.definir_poste(mauvais)
    assert t.poste_en_travail == 5          # refusé sans rien changer


def test_poste_le_plus_proche():
    t = Tourelle()
    for n in t.postes():
        x, y = t.position_poste(n)
        assert t.poste_le_plus_proche(x, y) == n
        assert t.poste_le_plus_proche(x * 1.08, y * 1.08) == n     # un peu en dehors du logement
    assert t.poste_le_plus_proche(0.0, 0.0) in t.postes()          # au centre : un poste quand même


def test_tourelle_a_un_autre_nombre_de_postes():
    t = Tourelle(nb_postes=8)
    assert t.postes() == list(range(1, 9)) and t.angle_poste(3) == 90.0
    with pytest.raises(ValueError):
        t.definir_poste(9)
