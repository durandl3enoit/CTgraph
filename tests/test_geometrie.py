"""Tests de la géométrie exacte : paramètres, intersections, polyligne."""
from __future__ import annotations

import math

import pytest

from ctgraph.esquisse import geometrie as geo


def test_ligne_parametre_et_position():
    li = geo.ligne((0, 0), (10, 0))
    assert geo.parametre(li, (2.5, 3.0)) == pytest.approx(0.25)
    assert geo.position(li, 0.25) == pytest.approx((2.5, 0.0))
    assert geo.longueur(li) == pytest.approx(10.0)
    d, t, p = geo.plus_proche(li, (12.0, 1.0))
    assert t == 1.0 and p == pytest.approx((10.0, 0.0)) and d == pytest.approx(math.hypot(2, 1))
    assert geo.sur_courbe(li, (5.0, 0.0)) == pytest.approx(0.5)
    assert geo.sur_courbe(li, (5.0, 0.1)) is None


def test_arc_sens_et_parametre():
    # quart de cercle antihoraire de (10,0) à (0,10) autour de l'origine
    a = geo.arc((0, 0), (10, 0), (0, 10), horaire=False)
    assert a[3] == pytest.approx(0.0) and a[4] == pytest.approx(math.pi / 2)
    assert geo.position(a, 0.5) == pytest.approx((10 * math.cos(math.pi / 4), 10 * math.sin(math.pi / 4)))
    assert geo.parametre(a, (0, 10)) == pytest.approx(1.0)
    assert geo.parametre(a, (-10, 0)) == pytest.approx(2.0)      # au-delà de la fin
    assert geo.parametre(a, (0, -10)) == pytest.approx(-1.0)     # avant le début
    # le même arc en horaire fait le grand tour
    h = geo.arc((0, 0), (10, 0), (0, 10), horaire=True)
    assert h[4] == pytest.approx(-3 * math.pi / 2)
    assert geo.longueur(h) == pytest.approx(10 * 3 * math.pi / 2)
    assert geo.parametre(h, (-10, 0)) == pytest.approx(2 / 3)


def test_intersection_lignes():
    l1 = geo.ligne((0, 0), (10, 10))
    l2 = geo.ligne((0, 10), (10, 0))
    hits = geo.intersections(l1, l2)
    assert len(hits) == 1
    t1, t2, p = hits[0]
    assert (t1, t2) == pytest.approx((0.5, 0.5)) and p == pytest.approx((5.0, 5.0))
    # segments qui ne se touchent pas, mais dont les prolongements se croisent
    l3 = geo.ligne((20, 0), (20, 1))
    assert geo.intersections(l1, l3) == []
    assert len(geo.intersections(l1, l3, bornes=False)) == 1
    # parallèles
    assert geo.intersections(l1, geo.ligne((0, 1), (10, 11))) == []


def test_intersection_ligne_arc():
    a = geo.arc((0, 0), (10, 0), (-10, 0), horaire=False)     # demi-cercle supérieur
    verticale = geo.ligne((0, -20), (0, 20))
    hits = geo.intersections(verticale, a)
    assert len(hits) == 1
    assert hits[0][2] == pytest.approx((0.0, 10.0)) and hits[0][1] == pytest.approx(0.5)
    horizontale = geo.ligne((-20, 5), (20, 5))
    hits = sorted(geo.intersections(horizontale, a), key=lambda h: h[0])
    assert len(hits) == 2
    assert hits[0][2][0] == pytest.approx(-math.sqrt(75)) and hits[1][2][0] == pytest.approx(math.sqrt(75))
    # tangente : un seul point
    tangente = geo.ligne((-20, 10), (20, 10))
    hits = geo.intersections(tangente, a)
    assert len(hits) == 1 and hits[0][2] == pytest.approx((0.0, 10.0))
    # en dessous : le demi-cercle inférieur n'existe pas
    assert geo.intersections(geo.ligne((-20, -5), (20, -5)), a) == []


def test_intersection_arcs():
    a1 = geo.arc((0, 0), (10, 0), (-10, 0), horaire=False)
    a2 = geo.arc((10, 0), (20, 0), (0, 0), horaire=False)
    hits = geo.intersections(a1, a2)
    assert len(hits) == 1
    assert hits[0][2] == pytest.approx((5.0, math.sqrt(75)))
    # cercles concentriques : rien
    assert geo.intersections(a1, geo.arc((0, 0), (5, 0), (-5, 0), False)) == []


def test_polyligne_croise():
    li = geo.ligne((0, 0), (10, 0))
    trait = [(2, -3), (3, 3), (8, 3), (9, -3)]
    res = geo.polyligne_croise(trait, li)
    assert res is not None
    t, p = res
    assert t == pytest.approx(0.25) and p == pytest.approx((2.5, 0.0))
    assert geo.polyligne_croise([(0, 5), (10, 5)], li) is None
