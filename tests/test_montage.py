"""Tests du montage : géométrie dérivée, validation, fichier pièce et lecture des anciens fichiers."""
from __future__ import annotations

import pytest

from ctgraph.esquisse.modele import ErreurEsquisse, Esquisse
from ctgraph.montage import Brut, Montage, Piece, PriseDePiece


def test_geometrie_du_montage():
    m = Montage(brut=Brut(diametre=60.0), prise=PriseDePiece(depassement=100.0, prise_mors=20.0, surepaisseur_face=2.0))
    assert m.z_face_mors() == -100.0
    assert m.z_brut_avant() == 2.0
    assert m.z_brut_arriere() == -120.0
    assert m.longueur_brut() == 122.0
    assert m.z_fond_mors() == -100.0 - m.mandrin.hauteur_mors
    assert m.z_arriere_mandrin() == m.z_fond_mors() - m.mandrin.longueur_corps
    assert m.rayon_brut() == 30.0 and m.rayon_interieur_brut() == 0.0
    m.verifier()


def test_validation():
    m = Montage()
    m.prise.prise_mors = 500.0
    with pytest.raises(ErreurEsquisse):
        m.verifier()
    m = Montage(brut=Brut(forme="tube", diametre=60.0, diametre_interieur=70.0))
    with pytest.raises(ErreurEsquisse):
        m.verifier()
    m.brut.diametre_interieur = 40.0
    m.verifier()
    assert m.rayon_interieur_brut() == 20.0


def test_piece_aller_retour_et_ancien_format():
    e = Esquisse()
    a = e.ajouter_point(0, 0)
    b = e.ajouter_point(-10, 15)
    e.ajouter_ligne(a.id, b.id)
    p = Piece(e, Montage(brut=Brut(diametre=45.0)))
    p.montage.contre_pointe.presente = True
    p2 = Piece.from_json(p.to_json())
    assert p2.to_dict() == p.to_dict()
    assert p2.montage.brut.diametre == 45.0 and p2.montage.contre_pointe.presente
    # un fichier de la version précédente, l'esquisse seule, s'ouvre avec un montage par défaut
    ancien = Piece.from_json(e.to_json())
    assert ancien.esquisse.to_dict() == e.to_dict()
    assert ancien.montage.mandrin.modele.startswith("SMW")
    with pytest.raises(ErreurEsquisse):
        Piece.from_json("[1, 2]")


def test_cles_inconnues_ignorees():
    d = Montage().to_dict()
    d["brut"]["inconnue"] = 1
    m = Montage.from_dict(d)
    assert m.brut.diametre == 60.0
