"""Tests de l'arrondi et du chanfrein sur le modèle : géométrie, et les cotes voisines qui ne bougent pas."""
from __future__ import annotations

import pytest

from ctgraph.esquisse.coins import arrondir, chanfreiner
from ctgraph.esquisse.modele import ErreurEsquisse, Esquisse, TypeCote, TypeRelation
from ctgraph.esquisse.solveur import AdaptateurSolveur


def epaulement():
    """Coin à 90° entre un cylindre horizontal (x = 10) et une face verticale (z = -20), entièrement coté."""
    e = Esquisse()
    p0 = e.ajouter_point(0, 10)
    coin = e.ajouter_point(-20, 10)
    p2 = e.ajouter_point(-20, 25)
    cyl = e.ajouter_ligne(p0.id, coin.id)
    face = e.ajouter_ligne(coin.id, p2.id)
    e.ajouter_relation(TypeRelation.ORIGINE_Z, (p0.id,))
    e.ajouter_relation(TypeRelation.HORIZONTAL, (cyl.id,))
    e.ajouter_relation(TypeRelation.VERTICAL, (face.id,))
    longueur = e.ajouter_cote(TypeCote.LONGUEUR_Z, (cyl.id,), 20.0)
    e.ajouter_cote(TypeCote.DIAMETRE, (p0.id,), 20.0)
    e.ajouter_cote(TypeCote.DIAMETRE, (p2.id,), 50.0)
    return e, coin, cyl, face, p0, p2, longueur


def test_arrondi_tangent_au_bon_rayon():
    e, coin, cyl, face, p0, p2, longueur = epaulement()
    arc_id = arrondir(e, coin.id, 3.0)
    arc = e.arcs[arc_id]
    a, b, c = e.points[arc.debut], e.points[arc.fin], e.points[arc.centre]
    assert (a.z, a.x) == pytest.approx((-17.0, 10.0), abs=1e-6)
    assert (b.z, b.x) == pytest.approx((-20.0, 13.0), abs=1e-6)
    assert (c.z, c.x) == pytest.approx((-17.0, 13.0), abs=1e-6)
    assert e.rayon(arc_id) == pytest.approx(3.0)
    assert sum(1 for r in e.relations.values() if r.type == TypeRelation.TANGENT) == 2
    assert any(co.type == TypeCote.RAYON and co.valeur == 3.0 for co in e.cotes.values())


def test_le_coin_theorique_reste_et_porte_les_cotes():
    e, coin, cyl, face, p0, p2, longueur = epaulement()
    arrondir(e, coin.id, 3.0)
    # le sommet est conservé comme point de construction, sur le prolongement des deux lignes
    assert coin.id in e.points and e.points[coin.id].construction
    assert sum(1 for r in e.relations_de(coin.id) if r.type == TypeRelation.POINT_SUR_LIGNE) == 2
    # la longueur du cylindre se lit maintenant entre l'origine et le coin théorique, toujours 20
    assert longueur.id in e.cotes and set(longueur.elements) == {p0.id, coin.id}
    s = AdaptateurSolveur(e)
    res = s.resoudre()
    assert res.succes and res.entierement_contraint, res
    assert (e.points[coin.id].z, e.points[coin.id].x) == pytest.approx((-20.0, 10.0), abs=1e-6)
    # changer le rayon ne déplace ni le coin théorique, ni la face, ni les diamètres
    rayon = next(co for co in e.cotes.values() if co.type == TypeCote.RAYON)
    assert s.modifier_cote(rayon.id, 6.0).succes
    assert (e.points[coin.id].z, e.points[coin.id].x) == pytest.approx((-20.0, 10.0), abs=1e-6)
    assert e.points[p2.id].z == pytest.approx(-20.0, abs=1e-6) and 2 * e.points[p2.id].x == pytest.approx(50.0)
    assert e.points[p0.id].z == pytest.approx(0.0, abs=1e-6)
    arc = next(iter(e.arcs.values()))
    assert (e.points[arc.debut].z, e.points[arc.fin].x) == pytest.approx((-14.0, 16.0), abs=1e-6)
    # et modifier la longueur du cylindre déplace la face et le congé avec elle
    assert s.modifier_cote(longueur.id, 30.0).succes
    assert e.points[coin.id].z == pytest.approx(-30.0, abs=1e-6)
    assert e.points[p2.id].z == pytest.approx(-30.0, abs=1e-6)
    assert e.rayon(arc.id) == pytest.approx(6.0, abs=1e-6)


def test_changer_le_rayon_ne_deplace_pas_un_dessin_non_ancre():
    """Sans origine ni point fixe, le dessin peut glisser : changer le rayon ne doit pourtant rien déplacer."""
    e, coin, cyl, face, p0, p2, longueur = epaulement()
    e.supprimer(next(r.id for r in e.relations.values() if r.type == TypeRelation.ORIGINE_Z))
    arrondir(e, coin.id, 3.0)
    s = AdaptateurSolveur(e)
    res = s.resoudre()
    assert res.succes and res.dof == 1
    avant = {pid: (p.z, p.x) for pid, p in e.points.items()}
    rayon = next(co for co in e.cotes.values() if co.type == TypeCote.RAYON)
    assert s.modifier_cote(rayon.id, 7.0).succes
    arc = next(iter(e.arcs.values()))
    for pid, (z, x) in avant.items():
        if pid in (arc.debut, arc.fin, arc.centre):
            continue
        assert (e.points[pid].z, e.points[pid].x) == pytest.approx((z, x), abs=1e-6), pid
    assert e.rayon(arc.id) == pytest.approx(7.0, abs=1e-6)


def test_arrondi_trop_grand_refuse():
    e, coin, *_ = epaulement()
    with pytest.raises(ErreurEsquisse):
        arrondir(e, coin.id, 30.0)
    assert coin.id in e.points and not e.points[coin.id].construction   # rien n'a été modifié


def test_chanfrein_un_par_quarante_cinq():
    e, coin, cyl, face, p0, p2, longueur = epaulement()
    pan_id = chanfreiner(e, coin.id, 1.0)
    pan = e.lignes[pan_id]
    a, b = e.points[pan.p1], e.points[pan.p2]
    assert sorted([(round(a.z, 6), round(a.x, 6)), (round(b.z, 6), round(b.x, 6))]) == [(-20.0, 11.0), (-19.0, 10.0)]
    angle = next(co for co in e.cotes.values() if co.type == TypeCote.ANGLE)
    cote_pan = next(co for co in e.cotes.values() if co.type == TypeCote.DISTANCE)
    assert abs(angle.valeur) % 90.0 == pytest.approx(45.0)
    assert cote_pan.valeur == pytest.approx(1.0) and coin.id in cote_pan.elements
    s = AdaptateurSolveur(e)
    res = s.resoudre()
    assert res.succes and res.entierement_contraint, res
    # un chanfrein de 2,5 : le coin théorique, la face et le cylindre restent en place
    assert s.modifier_cote(cote_pan.id, 2.5).succes
    assert (e.points[coin.id].z, e.points[coin.id].x) == pytest.approx((-20.0, 10.0), abs=1e-6)
    assert e.points[p2.id].z == pytest.approx(-20.0, abs=1e-6)
    assert e.longueur(pan_id) == pytest.approx(2.5 * 2 ** 0.5, abs=1e-6)


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


def test_point_de_construction_survit_au_nettoyage_et_au_fichier():
    e, coin, cyl, face, p0, p2, longueur = epaulement()
    arrondir(e, coin.id, 3.0)
    e2 = Esquisse.from_json(e.to_json())
    assert e2.points[coin.id].construction
    # supprimer un autre élément ne balaie pas le coin théorique avec les orphelins
    rayon = next(co for co in e2.cotes.values() if co.type == TypeCote.RAYON)
    e2.supprimer(rayon.id)
    assert coin.id in e2.points
