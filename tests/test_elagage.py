"""Tests de l'élagage sur le modèle : raccourcir, scinder, modes, arcs, cohérence des relations."""
from __future__ import annotations

import pytest

from ctgraph.esquisse.elagage import bornes_croisements, bornes_points, courbe, elaguer
from ctgraph.esquisse.modele import Esquisse, TypeCote, TypeRelation
from ctgraph.esquisse.solveur import AdaptateurSolveur


def croix():
    """Deux lignes qui se croisent en (5, 5) : horizontale de (0,5) à (10,5), verticale de (5,0) à (5,10)."""
    e = Esquisse()
    a = e.ajouter_point(0, 5)
    b = e.ajouter_point(10, 5)
    c = e.ajouter_point(5, 0)
    d = e.ajouter_point(5, 10)
    h = e.ajouter_ligne(a.id, b.id)
    v = e.ajouter_ligne(c.id, d.id)
    e.ajouter_relation(TypeRelation.HORIZONTAL, (h.id,))
    e.ajouter_relation(TypeRelation.VERTICAL, (v.id,))
    return e, h, v


def test_bornes_croisements():
    e, h, v = croix()
    b = bornes_croisements(e, h.id)
    assert len(b) == 1 and b[0].t == pytest.approx(0.5) and b[0].autre == v.id


def test_raccourcir_jusqu_au_croisement():
    e, h, v = croix()
    elaguer(e, h.id, 0.8, "croisement")          # on traverse la partie droite : elle disparaît
    assert h.id in e.lignes
    p2 = e.points[e.lignes[h.id].p2]
    assert (p2.z, p2.x) == pytest.approx((5.0, 5.0))
    assert any(r.type == TypeRelation.POINT_SUR_LIGNE and v.id in r.elements for r in e.relations_de(p2.id))
    assert any(r.type == TypeRelation.HORIZONTAL for r in e.relations_de(h.id))   # la relation reste
    assert len(e.points) == 4                                                       # l'ancien bout a disparu
    # le solveur accepte le résultat
    res = AdaptateurSolveur(e).resoudre()
    assert res.succes and not res.conflits


def test_scinder_entre_deux_croisements():
    e = Esquisse()
    a = e.ajouter_point(0, 5)
    b = e.ajouter_point(20, 5)
    h = e.ajouter_ligne(a.id, b.id)
    e.ajouter_relation(TypeRelation.HORIZONTAL, (h.id,))
    e.ajouter_cote(TypeCote.LONGUEUR_Z, (h.id,), 20.0)
    for z in (5, 15):
        c = e.ajouter_point(z, 0)
        d = e.ajouter_point(z, 10)
        e.ajouter_ligne(c.id, d.id)
    elaguer(e, h.id, 0.5, "croisement")
    assert h.id not in e.lignes
    morceaux = [li for li in e.lignes.values() if abs(e.points[li.p1].x - 5) < 1e-9 and abs(e.points[li.p2].x - 5) < 1e-9]
    assert len(morceaux) == 2
    zs = sorted((e.points[li.p1].z, e.points[li.p2].z) for li in morceaux)
    assert zs == [pytest.approx((0.0, 5.0)), pytest.approx((15.0, 20.0))]
    assert all(any(r.type == TypeRelation.HORIZONTAL for r in e.relations_de(li.id)) for li in morceaux)
    assert not e.cotes          # la longueur n'a plus de sens
    res = AdaptateurSolveur(e).resoudre()
    assert res.succes and not res.conflits


def test_sans_croisement_supprime_tout():
    e = Esquisse()
    a = e.ajouter_point(0, 0)
    b = e.ajouter_point(10, 0)
    e.ajouter_ligne(a.id, b.id)
    elaguer(e, 3, 0.3, "croisement")
    assert e.est_vide()


def test_mode_extremite_coupe_au_trait():
    e, h, v = croix()
    elaguer(e, h.id, 0.3, "extremite")
    p1 = e.points[e.lignes[h.id].p1]
    assert (p1.z, p1.x) == pytest.approx((3.0, 5.0))
    assert not e.relations_de(p1.id)       # point libre
    assert len(e.points) == 4


def test_mode_points():
    e, h, v = croix()
    m = e.ajouter_point(7, 5)
    e.ajouter_relation(TypeRelation.POINT_SUR_LIGNE, (m.id, h.id))
    assert [b.point for b in bornes_points(e, h.id)] == [m.id]
    elaguer(e, h.id, 0.9, "points")        # entre le point m et l'extrémité droite
    p2 = e.points[e.lignes[h.id].p2]
    assert p2.id == m.id
    assert not any(r.type == TypeRelation.POINT_SUR_LIGNE for r in e.relations_de(m.id))


def test_mode_tout():
    e, h, v = croix()
    elaguer(e, v.id, 0.5, "tout")
    assert v.id not in e.lignes and len(e.points) == 2


def test_arc_scinde_garde_le_cercle():
    e = Esquisse()
    c = e.ajouter_point(0, 0)
    d = e.ajouter_point(10, 0)
    f = e.ajouter_point(-10, 0)
    arc = e.ajouter_arc(c.id, d.id, f.id, horaire=False)       # demi-cercle supérieur
    e.ajouter_cote(TypeCote.RAYON, (arc.id,), 10.0)
    for z in (-5, 5):
        a = e.ajouter_point(z, -1)
        b = e.ajouter_point(z, 12)
        e.ajouter_ligne(a.id, b.id)
    elaguer(e, arc.id, 0.5, "croisement")
    assert arc.id not in e.arcs and len(e.arcs) == 2
    a1, a2 = e.arcs.values()
    assert a1.centre == a2.centre == c.id
    assert any(r.type == TypeRelation.EGAL and set(r.elements) == {a1.id, a2.id} for r in e.relations.values())
    assert sum(1 for co in e.cotes.values() if co.type == TypeCote.RAYON) == 1
    res = AdaptateurSolveur(e).resoudre()
    assert res.succes and not res.conflits
    for a in (a1, a2):
        assert e.rayon(a.id) == pytest.approx(10.0, abs=1e-6)


def test_tangence_suit_le_bon_morceau():
    """Une ligne tangente à un arc à son extrémité : après scission de la ligne, la tangence reste sur le morceau collé à l'arc."""
    e = Esquisse()
    p0 = e.ajouter_point(0, 10)
    p1 = e.ajouter_point(-20, 10)
    c = e.ajouter_point(-20, 15)
    p2 = e.ajouter_point(-25, 15)
    li = e.ajouter_ligne(p0.id, p1.id)
    arc = e.ajouter_arc(c.id, p1.id, p2.id, horaire=True)
    e.ajouter_relation(TypeRelation.TANGENT, (li.id, arc.id))
    for z in (-5, -12):
        a = e.ajouter_point(z, 0)
        b = e.ajouter_point(z, 20)
        e.ajouter_ligne(a.id, b.id)
    elaguer(e, li.id, 0.4, "croisement")
    tangentes = [r for r in e.relations.values() if r.type == TypeRelation.TANGENT]
    assert len(tangentes) == 1
    morceau = e.lignes[tangentes[0].elements[0]]
    assert p1.id in (morceau.p1, morceau.p2)


def test_courbe_refuse_un_point():
    e = Esquisse()
    p = e.ajouter_point(0, 0)
    with pytest.raises(ValueError):
        courbe(e, p.id)
