"""Tests du montage : géométrie dérivée, validation, fichier pièce et lecture des anciens fichiers."""
from __future__ import annotations

import pytest

from ctgraph.esquisse.modele import ErreurEsquisse, Esquisse
from ctgraph.montage import Brut, Montage, Piece, PriseDePiece


def test_geometrie_du_montage():
    # appui par défaut : l'épaulement derrière l'étage 1 (bout), long de 20
    m = Montage(brut=Brut(diametre=60.0), prise=PriseDePiece(depassement=100.0, surepaisseur_face=2.0))
    assert m.z_face_mors() == -100.0
    assert m.z_brut_avant() == 2.0
    assert m.z_brut_arriere() == -120.0 and m.profondeur_prise() == 20.0
    assert m.longueur_brut() == 122.0
    assert m.mandrin.hauteur_mors() == 70.0 and m.mandrin.nb_etages() == 3
    assert m.z_fond_mors() == -170.0 and m.z_face_mandrin() == -170.0
    assert m.z_arriere_mandrin() == m.z_fond_mors() - m.mandrin.longueur_corps
    assert m.rayon_brut() == 30.0 and m.rayon_interieur_brut() == 0.0
    m.verifier()
    # appui sur la face du mandrin : le brut traverse les trois étages
    m.definir_appui(0)
    assert m.z_brut_arriere() == -170.0 and m.profondeur_prise() == 70.0 and m.etage_de_serrage() == 3


def test_validation():
    m = Montage()
    m.prise.appui = 3                           # pas d'épaulement derrière le dernier étage : c'est le mandrin
    with pytest.raises(ErreurEsquisse):
        m.verifier()
    m.prise.appui = 1
    m.mandrin.etages[0].longueur = 0.0
    with pytest.raises(ErreurEsquisse):
        m.verifier()
    m.mandrin.etages[0].longueur = 20.0
    m.mandrin.epaisseur_mors = 10.0             # deux épaulements de 8 : plus de matière au bout
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
    p.montage.mandrin.etages[1].epaulement = 6.5
    p.montage.prise.mors_retournes = True
    p.montage.prise.appui = 0
    p2 = Piece.from_json(p.to_json())
    assert p2.to_dict() == p.to_dict()
    assert p2.montage.brut.diametre == 45.0 and p2.montage.contre_pointe.presente
    assert p2.montage.mandrin.etages[1].epaulement == 6.5 and p2.montage.prise.mors_retournes
    # un fichier du montage précédent (mors sans étages, prise par longueur serrée) : valeurs par défaut
    d = p.to_dict()
    d["montage"]["mandrin"] = {"hauteur_mors": 70.0, "etage_mors": 5.0}
    d["montage"]["prise"] = {"depassement": 90.0, "prise_mors": 20.0}
    p3 = Piece.from_dict(d)
    assert p3.montage.mandrin.nb_etages() == 3 and p3.montage.prise.depassement == 90.0
    p3.montage.verifier()
    # un fichier de la version précédente, l'esquisse seule, s'ouvre avec un montage par défaut
    ancien = Piece.from_json(e.to_json())
    assert ancien.esquisse.to_dict() == e.to_dict()
    assert ancien.montage.mandrin.modele.startswith("SMW")
    with pytest.raises(ErreurEsquisse):
        Piece.from_json("[1, 2]")


def test_valeurs_du_brut():
    m = Montage(brut=Brut(diametre=60.0), prise=PriseDePiece(depassement=100.0, surepaisseur_face=2.0))
    assert m.valeur_brut("diametre") == 60.0 and m.valeur_brut("longueur") == 122.0 and m.valeur_brut("marge") == 2.0
    assert m.texte_brut("diametre") == "Ø brut 60" and m.texte_brut("longueur") == "L brut 122"
    m.definir_valeur_brut("longueur", 130.0)
    assert m.prise.depassement == 108.0 and m.longueur_brut() == 130.0
    m.definir_valeur_brut("marge", 3.5)
    assert m.texte_brut("marge") == "marge 3.5" and m.longueur_brut() == 131.5
    with pytest.raises(ErreurEsquisse):
        m.definir_valeur_brut("longueur", 10.0)      # dépassement négatif
    with pytest.raises(ErreurEsquisse):
        m.valeur_brut("autre")


def test_mors_etages_normaux_serrage_exterieur():
    # étages depuis le bout : 20 (épaulement 8), 20 (épaulement 8), 30 au fond ; épaisseur au fond 40
    m = Montage(brut=Brut(diametre=60.0), prise=PriseDePiece(depassement=100.0))
    assert [m.mandrin.epaisseur_etage(k) for k in (1, 2, 3)] == [24.0, 32.0, 40.0]
    # appui sur l'épaulement derrière l'étage 1 : l'étage 1 serre au rayon 30, la face plate est à 30 + 24
    assert m.blocs_mors() == [(-120.0, -100.0, 30.0, 54.0), (-140.0, -120.0, 22.0, 54.0), (-170.0, -140.0, 14.0, 54.0)]
    assert m.profil_mors() == [(-170.0, 54.0), (-100.0, 54.0), (-100.0, 30.0), (-120.0, 30.0), (-120.0, 22.0),
                               (-140.0, 22.0), (-140.0, 14.0), (-170.0, 14.0)]
    # appui sur l'épaulement derrière l'étage 2
    m.definir_appui(2)
    assert m.z_brut_arriere() == -140.0 and m.etage_de_serrage() == 2
    assert m.blocs_mors()[1] == (-140.0, -120.0, 30.0, 62.0) and m.blocs_mors()[0][2] == 38.0
    # appui sur la face du mandrin : le fond serre au rayon 30
    m.definir_appui(0)
    assert m.blocs_mors() == [(-120.0, -100.0, 46.0, 70.0), (-140.0, -120.0, 38.0, 70.0), (-170.0, -140.0, 30.0, 70.0)]
    assert "face du mandrin" in m.description_prise() and "étage 3" in m.description_prise()


def test_mors_retournes_et_serrage_interieur():
    m = Montage(brut=Brut(forme="tube", diametre=80.0, diametre_interieur=60.0), prise=PriseDePiece(depassement=100.0))
    # retournés en serrage extérieur : la face plate, vers l'axe, serre au rayon 40 ; l'appui passe au mandrin
    m.retourner_mors()
    assert m.prise.mors_retournes and m.prise.appui == 0 and not m.face_etagee_en_contact()
    assert m.blocs_mors() == [(-120.0, -100.0, 40.0, 64.0), (-140.0, -120.0, 40.0, 72.0), (-170.0, -140.0, 40.0, 80.0)]
    assert m.profil_mors()[:3] == [(-170.0, 40.0), (-100.0, 40.0), (-100.0, 64.0)]
    with pytest.raises(ErreurEsquisse):
        m.definir_appui(1)                     # la face plate serre : pas d'épaulement contre le brut
    # serrage intérieur : la face étagée écarte le tube par son alésage (rayon 30). Le fond (40 d'épaisseur) ne
    # tient pas dans Ø 60 : l'appui passe de lui-même sur l'épaulement derrière l'étage 1 (24 d'épaisseur)
    m.definir_serrage("interieur")
    assert m.prise.appui == 1
    assert m.face_etagee_en_contact() and m.etage_de_serrage() == 1 and m.z_brut_arriere() == -120.0
    assert m.blocs_mors() == [(-120.0, -100.0, 6.0, 30.0), (-140.0, -120.0, 6.0, 38.0), (-170.0, -140.0, 6.0, 46.0)]
    assert m.appuis_possibles() == [(0, "Face du mandrin"), (1, "Épaulement de l'étage 1"), (2, "Épaulement de l'étage 2")]
    # mors normaux en serrage intérieur : la face plate dehors, le fond (40 d'épaisseur) ne tient pas dans Ø 60 ;
    # refusé, et rien ne change
    with pytest.raises(ErreurEsquisse):
        m.retourner_mors()
    assert m.prise.mors_retournes and m.prise.appui == 1
    m.brut.diametre_interieur = 100.0
    m.brut.diametre = 120.0
    m.retourner_mors()
    assert not m.prise.mors_retournes and m.prise.appui == 0
    assert m.blocs_mors()[2] == (-170.0, -140.0, 10.0, 50.0)
    # le serrage intérieur demande un tube
    m.brut.forme = "rond"
    with pytest.raises(ErreurEsquisse):
        m.verifier()
    assert m.appuis_possibles() == [(0, "Face du mandrin")]


def test_cles_inconnues_ignorees():
    d = Montage().to_dict()
    d["brut"]["inconnue"] = 1
    m = Montage.from_dict(d)
    assert m.brut.diametre == 60.0


def test_references_et_passage_du_mandrin():
    from ctgraph.montage import PASSAGE_MANDRIN
    m = Montage()
    assert m.mandrin.reference == "210 BH-FC" and m.mandrin.mors_reference.startswith("12082030")
    # le passage de barre est une caractéristique du mandrin : ni réglable, ni enregistré, ni relu d'un fichier
    assert m.mandrin.alesage == PASSAGE_MANDRIN == 42.0
    d = m.to_dict()
    assert "alesage" not in d["mandrin"]
    d["mandrin"]["alesage"] = 52.0
    assert Montage.from_dict(d).mandrin.alesage == 42.0
