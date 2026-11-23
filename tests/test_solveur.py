"""Tests de l'adaptateur PlaneGCS sur des profils de tournage."""
from __future__ import annotations

import math

import pytest

from ctgraph.esquisse.modele import Esquisse, TypeCote, TypeRelation
from ctgraph.esquisse.solveur import AdaptateurSolveur


def arbre_contraint():
    """Arbre épaulé entièrement contraint : positions de départ volontairement approximatives."""
    e = Esquisse()
    p0 = e.ajouter_point(0, 0)
    p1 = e.ajouter_point(0.3, 15.2)
    p2 = e.ajouter_point(-30.1, 15.0)
    p3 = e.ajouter_point(-30.0, 25.3)
    p4 = e.ajouter_point(-80.2, 25.0)
    p5 = e.ajouter_point(-80.0, 0.1)
    face = e.ajouter_ligne(p0.id, p1.id)
    petit = e.ajouter_ligne(p1.id, p2.id)
    epaul = e.ajouter_ligne(p2.id, p3.id)
    grand = e.ajouter_ligne(p3.id, p4.id)
    fond = e.ajouter_ligne(p4.id, p5.id)
    e.ajouter_relation(TypeRelation.FIXE, (p0.id,))
    e.ajouter_relation(TypeRelation.SUR_AXE, (p5.id,))
    e.ajouter_relation(TypeRelation.VERTICAL, (face.id,))
    e.ajouter_relation(TypeRelation.HORIZONTAL, (petit.id,))
    e.ajouter_relation(TypeRelation.VERTICAL, (epaul.id,))
    e.ajouter_relation(TypeRelation.HORIZONTAL, (grand.id,))
    e.ajouter_relation(TypeRelation.VERTICAL, (fond.id,))
    d_petit = e.ajouter_cote(TypeCote.DIAMETRE, (p1.id,), 30.0)
    d_grand = e.ajouter_cote(TypeCote.DIAMETRE, (grand.id,), 50.0)
    l_petit = e.ajouter_cote(TypeCote.LONGUEUR_Z, (petit.id,), 30.0)
    l_total = e.ajouter_cote(TypeCote.LONGUEUR_Z, (p5.id, p0.id), 80.0)
    return e, dict(p0=p0, p1=p1, p2=p2, p3=p3, p4=p4, p5=p5, face=face, petit=petit, epaul=epaul, grand=grand,
                   fond=fond, d_petit=d_petit, d_grand=d_grand, l_petit=l_petit, l_total=l_total)


def test_profil_entierement_contraint():
    e, n = arbre_contraint()
    s = AdaptateurSolveur(e)
    res = s.resoudre()
    assert res.succes and res.entierement_contraint, res
    assert res.dof == 0 and not res.conflits
    assert e.points[n["p1"].id].z == pytest.approx(0.0, abs=1e-6)
    assert 2 * e.points[n["p1"].id].x == pytest.approx(30.0, abs=1e-6)
    assert e.points[n["p2"].id].z == pytest.approx(-30.0, abs=1e-6)
    assert 2 * e.points[n["p3"].id].x == pytest.approx(50.0, abs=1e-6)
    assert e.points[n["p4"].id].z == pytest.approx(-80.0, abs=1e-6)
    assert e.points[n["p5"].id].x == pytest.approx(0.0, abs=1e-6)


def test_modifier_une_cote_recalcule_le_profil():
    e, n = arbre_contraint()
    s = AdaptateurSolveur(e)
    s.resoudre()
    res = s.modifier_cote(n["d_grand"].id, 56.0)
    assert res.succes
    assert 2 * e.points[n["p3"].id].x == pytest.approx(56.0, abs=1e-6)
    assert 2 * e.points[n["p4"].id].x == pytest.approx(56.0, abs=1e-6)
    res = s.modifier_cote(n["l_total"].id, 100.0)
    assert res.succes
    assert e.points[n["p4"].id].z == pytest.approx(-100.0, abs=1e-6)
    assert e.points[n["p5"].id].z == pytest.approx(-100.0, abs=1e-6)


def test_cote_impossible_revient_en_arriere():
    e, n = arbre_contraint()
    s = AdaptateurSolveur(e)
    s.resoudre()
    # longueur totale plus courte que le petit diamètre : p5 devrait passer à droite de p2, ce que
    # la longueur du petit diamètre interdit... non : c'est géométriquement possible. On force un vrai
    # conflit avec une seconde longueur totale différente.
    conflit = e.ajouter_cote(TypeCote.LONGUEUR_Z, (n["p5"].id, n["p0"].id), 90.0)
    s.construire()
    res = s.resoudre()
    assert not res.succes or res.conflits
    assert conflit.id in res.conflits or n["l_total"].id in res.conflits
    # les positions n'ont pas bougé
    assert e.points[n["p4"].id].z == pytest.approx(-80.0, abs=1e-6)


def test_sous_contraint_compte_les_degres_de_liberte():
    e, n = arbre_contraint()
    e.supprimer(n["l_total"].id)
    s = AdaptateurSolveur(e)
    res = s.resoudre()
    assert res.succes and res.dof == 1


def test_glissement_respecte_les_contraintes():
    e, n = arbre_contraint()
    e.supprimer(n["l_total"].id)
    s = AdaptateurSolveur(e)
    s.resoudre()
    # on tire p4 vers z = -95 et vers un x quelconque : z suit, x reste à 25 (diamètre 50)
    assert s.glisser(n["p4"].id, -95.0, 40.0)
    assert e.points[n["p4"].id].z == pytest.approx(-95.0, abs=1e-6)
    assert 2 * e.points[n["p4"].id].x == pytest.approx(50.0, abs=1e-6)
    assert e.points[n["p5"].id].z == pytest.approx(-95.0, abs=1e-6)   # le fond reste vertical
    # un point entièrement contraint ne bouge pas
    assert not s.glisser(n["p1"].id, 10.0, 10.0)
    assert e.points[n["p1"].id].z == pytest.approx(0.0, abs=1e-6)


def test_glissement_rapide():
    import time
    e, n = arbre_contraint()
    e.supprimer(n["l_total"].id)
    s = AdaptateurSolveur(e)
    s.resoudre()
    t0 = time.perf_counter()
    for i in range(200):
        s.glisser(n["p4"].id, -80.0 - 10.0 * math.sin(i / 20.0), 25.0)
    dt = time.perf_counter() - t0
    assert dt < 2.0, f"200 glissements en {dt:.2f} s"


def test_arc_tangent_et_rayon():
    """Congé entre un épaulement vertical et un cylindre horizontal."""
    e = Esquisse()
    p0 = e.ajouter_point(0, 0)
    p1 = e.ajouter_point(0, 10)        # haut de la face
    p2 = e.ajouter_point(-20, 10)      # début du congé, sur le petit diamètre
    c = e.ajouter_point(-20, 15)       # centre du congé (approximatif)
    p3 = e.ajouter_point(-25.2, 15.3)  # fin du congé, sur l'épaulement (approximatif)
    p4 = e.ajouter_point(-25, 30)      # haut de l'épaulement
    face = e.ajouter_ligne(p0.id, p1.id)
    petit = e.ajouter_ligne(p1.id, p2.id)
    arc = e.ajouter_arc(c.id, p2.id, p3.id, horaire=True)   # quart de cercle par le bas-gauche du centre
    epaul = e.ajouter_ligne(p3.id, p4.id)
    e.ajouter_relation(TypeRelation.FIXE, (p0.id,))
    e.ajouter_relation(TypeRelation.VERTICAL, (face.id,))
    e.ajouter_relation(TypeRelation.HORIZONTAL, (petit.id,))
    e.ajouter_relation(TypeRelation.VERTICAL, (epaul.id,))
    e.ajouter_relation(TypeRelation.TANGENT, (petit.id, arc.id))
    e.ajouter_relation(TypeRelation.TANGENT, (epaul.id, arc.id))
    e.ajouter_cote(TypeCote.DIAMETRE, (p1.id,), 20.0)
    e.ajouter_cote(TypeCote.DIAMETRE, (p4.id,), 60.0)
    e.ajouter_cote(TypeCote.LONGUEUR_Z, (p2.id, p1.id), 20.0)
    r = e.ajouter_cote(TypeCote.RAYON, (arc.id,), 5.0)
    s = AdaptateurSolveur(e)
    res = s.resoudre()
    assert res.succes, res
    assert e.rayon(arc.id) == pytest.approx(5.0, abs=1e-6)
    # tangence : le centre est à 5 au-dessus du petit diamètre et 5 à droite de l'épaulement
    assert e.points[c.id].x == pytest.approx(15.0, abs=1e-6)
    assert e.points[c.id].z == pytest.approx(e.points[p3.id].z + 5.0, abs=1e-6)
    assert e.points[p3.id].x == pytest.approx(15.0, abs=1e-6)
    assert e.points[p2.id].z == pytest.approx(-20.0, abs=1e-6)
    # changer le rayon déplace l'épaulement et le centre, pas la cote de longueur
    res = s.modifier_cote(r.id, 8.0)
    assert res.succes
    assert e.rayon(arc.id) == pytest.approx(8.0, abs=1e-6)
    assert e.points[p2.id].z == pytest.approx(-20.0, abs=1e-6)
    assert e.points[c.id].x == pytest.approx(18.0, abs=1e-6)


def test_ecart_entre_deux_lignes_paralleles():
    e, n = arbre_contraint()
    AdaptateurSolveur(e).resoudre()
    # écart entre le petit et le grand diamètre : (50 - 30) / 2 = 10, mesuré
    assert e.mesurer(TypeCote.ECART, (n["petit"].id, n["grand"].id)) == pytest.approx(10.0, abs=1e-6)
    # on remplace le grand diamètre par un écart de 12 : le grand diamètre devient 54
    e.supprimer(n["d_grand"].id)
    e.ajouter_cote(TypeCote.ECART, (n["petit"].id, n["grand"].id), 12.0)
    s = AdaptateurSolveur(e)
    res = s.resoudre()
    assert res.succes and res.dof == 0 and not res.conflits, res
    assert 2 * e.points[n["p3"].id].x == pytest.approx(54.0, abs=1e-6)


def test_cote_pilotee_mesure_sans_contraindre():
    e, n = arbre_contraint()
    # une seconde longueur totale, pilotée : elle ne sur-contraint pas et prend la mesure
    c = e.ajouter_cote(TypeCote.LONGUEUR_Z, (n["p5"].id, n["p0"].id), 12.0)
    c.pilotee = True
    d = e.ajouter_cote(TypeCote.DIAMETRE, (n["p4"].id,), 1.0)
    d.pilotee = True
    s = AdaptateurSolveur(e)
    res = s.resoudre()
    assert res.succes and res.dof == 0 and not res.conflits and not res.redondants, res
    assert c.valeur == pytest.approx(80.0, abs=1e-6)
    assert d.valeur == pytest.approx(50.0, abs=1e-6)
    assert e.texte_cote(c) == "(80)"
    # elle suit les modifications des cotes pilotantes
    assert s.modifier_cote(n["l_total"].id, 95.0).succes
    assert c.valeur == pytest.approx(95.0, abs=1e-6)
    assert s.modifier_cote(n["d_grand"].id, 44.0).succes
    assert d.valeur == pytest.approx(44.0, abs=1e-6)
    # on ne règle pas une cote pilotée
    assert not s.modifier_cote(c.id, 10.0).succes
    assert c.valeur == pytest.approx(95.0, abs=1e-6)


def test_relations_diverses():
    e = Esquisse()
    a = e.ajouter_point(0, 0)
    b = e.ajouter_point(10, 0.5)
    c = e.ajouter_point(10.2, 8)
    d = e.ajouter_point(0.3, 7.9)
    l1 = e.ajouter_ligne(a.id, b.id)
    l2 = e.ajouter_ligne(b.id, c.id)
    l3 = e.ajouter_ligne(c.id, d.id)
    l4 = e.ajouter_ligne(d.id, a.id)
    e.ajouter_relation(TypeRelation.FIXE, (a.id,))
    e.ajouter_relation(TypeRelation.HORIZONTAL, (l1.id,))
    e.ajouter_relation(TypeRelation.PERPENDICULAIRE, (l1.id, l2.id))
    e.ajouter_relation(TypeRelation.PARALLELE, (l1.id, l3.id))
    e.ajouter_relation(TypeRelation.PARALLELE, (l2.id, l4.id))
    e.ajouter_relation(TypeRelation.EGAL, (l1.id, l2.id))
    e.ajouter_cote(TypeCote.DISTANCE, (l1.id,), 10.0)
    s = AdaptateurSolveur(e)
    res = s.resoudre()
    assert res.succes and res.dof == 0, res
    # un carré de 10
    assert e.points[c.id].z == pytest.approx(10.0, abs=1e-6)
    assert e.points[c.id].x == pytest.approx(10.0, abs=1e-6)
    assert e.points[d.id].z == pytest.approx(0.0, abs=1e-6)
    # angle de 45° imposé à la diagonale
    diag = e.ajouter_ligne(a.id, c.id)
    e.ajouter_cote(TypeCote.ANGLE, (diag.id,), 45.0)
    s.construire()
    res = s.resoudre()
    assert res.succes and res.redondants, res   # la diagonale d'un carré fait déjà 45° : redondant
    m = e.ajouter_point(5, 0.2)
    e.ajouter_relation(TypeRelation.POINT_SUR_LIGNE, (m.id, l1.id))
    e.ajouter_relation(TypeRelation.COINCIDENT, (m.id, b.id))
    s.construire()
    res = s.resoudre()
    assert res.succes
    assert e.points[m.id].z == pytest.approx(10.0, abs=1e-6)
    assert e.points[m.id].x == pytest.approx(0.0, abs=1e-6)
