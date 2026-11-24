"""Tests de l'arrondi et du chanfrein sur le modèle."""
from __future__ import annotations

import math

import pytest

from ctgraph.esquisse.coins import arrondir, chanfreiner
from ctgraph.esquisse.modele import ErreurEsquisse, Esquisse, TypeCote, TypeRelation
from ctgraph.esquisse.solveur import AdaptateurSolveur


def epaulement():
    """Coin à 90° entre un cylindre horizontal (y = 10) et une face verticale (z = -20), ancré."""
    e = Esquisse()
    p0 = e.ajouter_point(0, 10)
    coin = e.ajouter_point(-20, 10)
    p2 = e.ajouter_point(-20, 25)
    cyl = e.ajouter_ligne(p0.id, coin.id)
    face = e.ajouter_ligne(coin.id, p2.id)
    e.ajouter_relation(TypeRelation.FIXE, (p0.id,))
    e.ajouter_relation(TypeRelation.HORIZONTAL, (cyl.id,))
    e.ajouter_relation(TypeRelation.VERTICAL, (face.id,))
    e.ajouter_cote(TypeCote.LONGUEUR_Z, (cyl.id,), 20.0)        # sera retirée : la ligne raccourcie n'a plus ce sens
    e.ajouter_cote(TypeCote.DIAMETRE, (p2.id,), 50.0)
    e.ajouter_cote(TypeCote.POSITION_Z, (face.id,), -20.0)
    return e, coin, cyl, face, p0, p2


def test_arrondi_tangent_au_bon_rayon():
    e, coin, cyl, face, p0, p2 = epaulement()
    arc_id = arrondir(e, coin.id, 3.0)
    assert coin.id not in e.points
    arc = e.arcs[arc_id]
    a, b, c = e.points[arc.debut], e.points[arc.fin], e.points[arc.centre]
    # points de tangence à 3 mm du coin, centre à (-17, 13)
    assert (a.z, a.x) == pytest.approx((-17.0, 10.0), abs=1e-6)
    assert (b.z, b.x) == pytest.approx((-20.0, 13.0), abs=1e-6)
    assert (c.z, c.x) == pytest.approx((-17.0, 13.0), abs=1e-6)
    assert e.rayon(arc_id) == pytest.approx(3.0)
    assert sum(1 for r in e.relations.values() if r.type == TypeRelation.TANGENT) == 2
    assert any(co.type == TypeCote.RAYON and co.valeur == 3.0 for co in e.cotes.values())
    assert not any(co.type == TypeCote.LONGUEUR_Z for co in e.cotes.values())   # la longueur du cylindre est partie
    # le solveur accepte et la position Z de la face tient toujours
    res = AdaptateurSolveur(e).resoudre()
    assert res.succes and not res.conflits, res
    assert e.points[face.p2].z == pytest.approx(-20.0, abs=1e-6)
    # le congé est bien dans le coin : son milieu est entre le cylindre et la face, pas à l'extérieur
    arc_c = e.points[arc.centre]
    assert arc_c.z > -20.0 and arc_c.x > 10.0


def test_arrondi_trop_grand_refuse():
    e, coin, *_ = epaulement()
    with pytest.raises(ErreurEsquisse):
        arrondir(e, coin.id, 30.0)
    assert coin.id in e.points            # rien n'a été modifié


def test_chanfrein_un_par_quarante_cinq():
    e, coin, cyl, face, p0, p2 = epaulement()
    pan_id = chanfreiner(e, coin.id, 1.0)
    pan = e.lignes[pan_id]
    a, b = e.points[pan.p1], e.points[pan.p2]
    assert sorted([(round(a.z, 6), round(a.x, 6)), (round(b.z, 6), round(b.x, 6))]) == [(-20.0, 11.0), (-19.0, 10.0)]
    angle = next(co for co in e.cotes.values() if co.type == TypeCote.ANGLE)
    longueur = next(co for co in e.cotes.values() if co.type == TypeCote.LONGUEUR_Z)
    assert abs(angle.valeur) % 90.0 == pytest.approx(45.0)
    assert longueur.valeur == pytest.approx(1.0)
    res = AdaptateurSolveur(e).resoudre()
    assert res.succes and not res.conflits, res


def test_coin_invalide():
    e = Esquisse()
    a = e.ajouter_point(0, 0)
    b = e.ajouter_point(10, 0)
    e.ajouter_ligne(a.id, b.id)
    with pytest.raises(ErreurEsquisse):
        arrondir(e, b.id, 1.0)            # une seule ligne au sommet
    c = e.ajouter_point(20, 0)
    e.ajouter_ligne(b.id, c.id)
    with pytest.raises(ErreurEsquisse):
        chanfreiner(e, b.id, 1.0)         # deux lignes alignées
