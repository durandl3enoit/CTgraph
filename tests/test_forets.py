"""Tests des forets : la forme du trou qu'ils laissent, pointe comprise."""
from __future__ import annotations

import math

import pytest

from ctgraph.forets import (ANGLE_CENTRE, ANGLE_POINTE, CATALOGUE, Foret, foret, forets, nombre,
                            pour_diametre)


def test_foret_helicoidal_pointe_conique():
    f = Foret("Foret Ø 12", 12.0)
    assert not f.a_centrer and f.rayon == 6.0 and f.angle_pointe == ANGLE_POINTE
    # la pointe à 135° : la hauteur du cône est le rayon divisé par la tangente du demi-angle
    assert f.hauteur_pointe() == pytest.approx(6.0 / math.tan(math.radians(67.5)))
    assert f.hauteur_pointe() == pytest.approx(2.485, abs=0.001)
    h = f.hauteur_pointe()
    assert f.rayon_a(-1.0) == 0.0 and f.rayon_a(0.0) == 0.0
    assert f.rayon_a(h / 2.0) == pytest.approx(3.0)        # à mi-pointe, mi-diamètre
    assert f.rayon_a(h) == pytest.approx(6.0)
    assert f.rayon_a(50.0) == 6.0                          # au-delà, le trou ne s'élargit plus
    assert f.longueur_utile() == pytest.approx(h)
    # un foret à pointe plus obtuse creuse moins loin pour le même diamètre
    assert Foret("x", 12.0, 118.0).hauteur_pointe() > h


def test_foret_a_centrer_a_deux_etages():
    f = foret("À centrer 3,15 × 8")
    assert f is not None and f.a_centrer
    assert f.pilote == 3.15 and f.diametre == 8.0 and f.angle_centre == ANGLE_CENTRE
    pointe = f.hauteur_pointe()
    assert pointe == pytest.approx(1.575 / math.tan(math.radians(59.0)), abs=1e-6)
    # le bout guide : un cône court, puis un cylindre au petit diamètre
    assert f.rayon_a(pointe / 2.0) == pytest.approx(1.575 / 2.0)
    assert f.rayon_a(pointe) == pytest.approx(1.575)
    assert f.rayon_a(pointe + f.longueur_pilote / 2.0) == pytest.approx(1.575)
    # puis le cône à 60° qui ouvre le centre jusqu'au corps
    monte = (4.0 - 1.575) / math.tan(math.radians(30.0))
    assert f.rayon_a(pointe + f.longueur_pilote + monte / 2.0) == pytest.approx((1.575 + 4.0) / 2.0)
    assert f.rayon_a(pointe + f.longueur_pilote + monte) == pytest.approx(4.0)
    assert f.rayon_a(100.0) == 4.0
    assert f.longueur_utile() == pytest.approx(pointe + f.longueur_pilote + monte)
    # le profil rendu va du fond vers la face, en rayons croissants
    profil = f.profil(-5.0, 0.0)
    assert profil[0] == (-5.0, 0.0) and profil[-1][0] == pytest.approx(0.0, abs=0.25)
    assert all(b >= a - 1e-9 for (_, a), (_, b) in zip(profil, profil[1:]))


def test_catalogue_des_forets():
    assert len(forets(a_centrer=False)) == 16 and len(forets(a_centrer=True)) == 8
    assert len(CATALOGUE) == 24
    assert foret("Foret Ø 10").diametre == 10.0 and foret("Foret Ø 6,8").diametre == 6.8
    assert foret("inconnu") is None
    # un diamètre hors catalogue donne tout de même un foret ordinaire, pour que rien ne bloque
    libre = pour_diametre(7.5)
    assert libre.diametre == 7.5 and not libre.a_centrer and libre.designation == "Foret Ø 7,5"
    assert pour_diametre(10.0).designation == "Foret Ø 10"
    assert pour_diametre(8.0, a_centrer=True).a_centrer
    # nombres à la française, comme partout ailleurs
    assert nombre(3.15) == "3,15" and nombre(10.0) == "10"
    assert "pointe à 135°" in foret("Foret Ø 10").description()
    assert "cône à 60°" in foret("À centrer 3,15 × 8").description()
