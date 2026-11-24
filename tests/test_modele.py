"""Tests du modèle d'esquisse : construction, validation, suppression en cascade, sérialisation."""
from __future__ import annotations

import math

import pytest

from ctgraph.esquisse.modele import ErreurEsquisse, Esquisse, TypeCote, TypeRelation


def arbre_epaule() -> Esquisse:
    """Demi-profil d'un arbre épaulé : 6 points, 6 lignes, rien d'autre."""
    e = Esquisse()
    p0 = e.ajouter_point(0, 0)
    p1 = e.ajouter_point(0, 15)
    p2 = e.ajouter_point(-30, 15)
    p3 = e.ajouter_point(-30, 25)
    p4 = e.ajouter_point(-80, 25)
    p5 = e.ajouter_point(-80, 0)
    pts = [p0, p1, p2, p3, p4, p5]
    for a, b in zip(pts, pts[1:] + pts[:1]):
        e.ajouter_ligne(a.id, b.id)
    return e


def test_identifiants_uniques_et_genres():
    e = arbre_epaule()
    ids = list(e.points) + list(e.lignes)
    assert len(ids) == len(set(ids)) == 12
    assert e.genre(1) == "point"
    assert e.genre(7) == "ligne"
    assert e.genre(999) is None


def test_ligne_refuse_point_inconnu_ou_double():
    e = Esquisse()
    p = e.ajouter_point(0, 0)
    with pytest.raises(ErreurEsquisse):
        e.ajouter_ligne(p.id, 42)
    with pytest.raises(ErreurEsquisse):
        e.ajouter_ligne(p.id, p.id)


def test_relation_valide_les_genres():
    e = arbre_epaule()
    ligne = next(iter(e.lignes.values()))
    point = next(iter(e.points.values()))
    e.ajouter_relation(TypeRelation.HORIZONTAL, (ligne.id,))
    e.ajouter_relation(TypeRelation.SUR_AXE, (point.id,))
    with pytest.raises(ErreurEsquisse):
        e.ajouter_relation(TypeRelation.HORIZONTAL, (point.id,))
    with pytest.raises(ErreurEsquisse):
        e.ajouter_relation(TypeRelation.PARALLELE, (ligne.id, ligne.id))
    with pytest.raises(ErreurEsquisse):
        e.ajouter_relation(TypeRelation.TANGENT, (ligne.id, point.id))


def test_relation_symetrique_rangee_dans_l_ordre_canonique():
    e = Esquisse()
    c = e.ajouter_point(0, 0)
    d = e.ajouter_point(10, 0)
    f = e.ajouter_point(0, 10)
    arc = e.ajouter_arc(c.id, d.id, f.id)
    p = e.ajouter_point(20, 0)
    li = e.ajouter_ligne(d.id, p.id)
    r = e.ajouter_relation(TypeRelation.TANGENT, (arc.id, li.id))
    assert r.elements == (li.id, arc.id)
    r2 = e.ajouter_relation(TypeRelation.POINT_SUR_LIGNE, (li.id, f.id))
    assert r2.elements == (f.id, li.id)


def test_cote_prend_la_mesure_actuelle_et_range_les_points():
    e = arbre_epaule()
    p4 = e.points[5]   # (-80, 25)
    p3 = e.points[4]   # (-30, 25)
    c = e.ajouter_cote(TypeCote.LONGUEUR_Z, (p3.id, p4.id))
    assert c.elements == (p4.id, p3.id)      # du plus petit z au plus grand
    assert c.valeur == pytest.approx(50.0)
    d = e.ajouter_cote(TypeCote.DIAMETRE, (p3.id,))
    assert d.valeur == pytest.approx(50.0)
    assert e.texte_cote(d) == "Ø 50"
    with pytest.raises(ErreurEsquisse):
        e.ajouter_cote(TypeCote.DIAMETRE, (p3.id,), -5.0)
    with pytest.raises(ErreurEsquisse):
        e.ajouter_cote(TypeCote.RAYON, (p3.id,))


def test_mesures():
    e = arbre_epaule()
    ligne_face = e.lignes[7]   # p0 -> p1, verticale, longueur 15
    assert e.longueur(ligne_face.id) == pytest.approx(15.0)
    assert e.angle_ligne(ligne_face.id) == pytest.approx(90.0)
    assert e.mesurer(TypeCote.DISTANCE, (ligne_face.id,)) == pytest.approx(15.0)
    ligne_petit = e.lignes[8]  # p1 -> p2, horizontale vers les z négatifs
    assert abs(e.angle_ligne(ligne_petit.id)) == pytest.approx(180.0)
    assert e.mesurer(TypeCote.ANGLE, (ligne_face.id, ligne_petit.id)) == pytest.approx(90.0)
    c = e.ajouter_point(0, 0)
    d = e.ajouter_point(5, 0)
    f = e.ajouter_point(0, 5)
    arc = e.ajouter_arc(c.id, d.id, f.id)
    assert e.rayon(arc.id) == pytest.approx(5.0)


def test_suppression_en_cascade():
    e = arbre_epaule()
    li = e.lignes[8]            # p1 -> p2
    e.ajouter_relation(TypeRelation.HORIZONTAL, (li.id,))
    e.ajouter_cote(TypeCote.LONGUEUR_Z, (li.id,))
    e.supprimer(li.id)
    assert li.id not in e.lignes
    assert not e.relations and not e.cotes
    # p1 et p2 tiennent encore à d'autres lignes : ils restent
    assert 2 in e.points and 3 in e.points
    # supprimer un point retire ses lignes puis les points devenus orphelins
    e.supprimer(2)
    assert 2 not in e.points and 7 not in e.lignes
    assert 1 in e.points            # p0 tient encore à la ligne de l'axe


def test_points_orphelins_apres_suppression_de_ligne_isolee():
    e = Esquisse()
    a = e.ajouter_point(0, 0)
    b = e.ajouter_point(10, 0)
    li = e.ajouter_ligne(a.id, b.id)
    e.supprimer(li.id)
    assert e.est_vide()


def test_serialisation_aller_retour():
    e = arbre_epaule()
    li = e.lignes[8]
    e.ajouter_relation(TypeRelation.HORIZONTAL, (li.id,))
    e.ajouter_relation(TypeRelation.FIXE, (1,))
    c = e.ajouter_cote(TypeCote.DIAMETRE, (4,), 50.0, (3.0, -1.5))
    c.pilotee = True
    texte = e.to_json()
    e2 = Esquisse.from_json(texte)
    assert e2.to_dict() == e.to_dict()
    assert e2.cotes[c.id].decalage == (3.0, -1.5)
    assert e2.cotes[c.id].pilotee is True and e2.texte_cote(e2.cotes[c.id]) == "(Ø 50)"
    # les identifiants continuent après le plus grand existant
    p = e2.ajouter_point(1, 1)
    assert p.id > max(list(e.points) + list(e.lignes) + list(e.relations) + list(e.cotes))


def test_fichier_etranger_refuse():
    with pytest.raises(ErreurEsquisse):
        Esquisse.from_json('{"format": "autre"}')
    with pytest.raises(ErreurEsquisse):
        Esquisse.from_json("pas du json")
    with pytest.raises(ErreurEsquisse):
        Esquisse.from_dict({"format": "ctgraph-esquisse", "version": 1,
                            "points": [], "lignes": [{"id": 1, "p1": 5, "p2": 6}]})


def test_verifier_cote():
    e = arbre_epaule()
    e.verifier_cote(TypeCote.LONGUEUR_Z, (7,))
    with pytest.raises(ErreurEsquisse):
        e.verifier_cote(TypeCote.RAYON, (7,))


def test_longueur_x_et_references_du_montage():
    from ctgraph.esquisse.modele import Reference
    e = Esquisse()
    a = e.ajouter_point(0, 10)
    b = e.ajouter_point(-30, 25)
    li = e.ajouter_ligne(a.id, b.id)
    # longueur X : l'écart radial, rangé du plus petit x au plus grand, jamais négatif
    assert e.mesurer(TypeCote.LONGUEUR_X, (li.id,)) == 15.0
    c = e.ajouter_cote(TypeCote.LONGUEUR_X, (b.id, a.id))
    assert c.elements == (a.id, b.id) and c.valeur == 15.0
    with pytest.raises(ErreurEsquisse):
        e.ajouter_cote(TypeCote.LONGUEUR_X, (li.id,), -3.0)
    # les références du montage : inconnues tant que le contrôleur ne les a pas posées
    with pytest.raises(ErreurEsquisse):
        e.ajouter_relation(TypeRelation.SUR_REFERENCE, (a.id,), reference="face_mors")
    with pytest.raises(ErreurEsquisse):
        e.mesurer(TypeCote.DEPUIS_REFERENCE, (a.id,), "face_mors")
    e.references = {"face_mors": Reference("face_mors", "z", -95.0, "Face avant des mors", "mors"),
                    "brut_ext": Reference("brut_ext", "x", 28.0, "Surface du brut", "brut")}
    r = e.ajouter_relation(TypeRelation.SUR_REFERENCE, (li.id,), reference="face_mors")
    assert r.reference == "face_mors"
    # écart signé depuis le plan, selon son axe
    assert e.mesurer(TypeCote.DEPUIS_REFERENCE, (b.id,), "face_mors") == 65.0
    assert e.mesurer(TypeCote.DEPUIS_REFERENCE, (a.id,), "brut_ext") == -18.0
    c = e.ajouter_cote(TypeCote.DEPUIS_REFERENCE, (a.id,), reference="brut_ext")
    assert c.valeur == -18.0 and e.texte_cote(c) == "brut -18"
    with pytest.raises(ErreurEsquisse):
        e.ajouter_cote(TypeCote.DEPUIS_REFERENCE, (a.id,))          # la référence manque
    # la référence voyage dans le fichier ; une cote ordinaire n'en garde pas
    e2 = Esquisse.from_json(e.to_json())
    assert e2.relations[r.id].reference == "face_mors" and e2.cotes[c.id].reference == "brut_ext"
    assert "reference" not in e.to_dict()["cotes"][0]


def test_copier_est_independant():
    e = arbre_epaule()
    e2 = e.copier()
    e2.points[1].z = 99.0
    assert e.points[1].z == 0.0
    assert math.isclose(e2.points[1].z, 99.0)
