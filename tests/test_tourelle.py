"""Tests de la tourelle : répartition des douze postes VDI 30, désignation du poste en travail."""
from __future__ import annotations

import math

import pytest

from ctgraph.tourelle import DIAMETRE_QUEUE, IMPLANTATIONS, NORME, Correcteur, Tourelle


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
    assert t.poste_en_travail == 5 and "Poste en travail : T5" in t.description()
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
    assert len(t.postes_garnis) == 8
    with pytest.raises(ValueError):
        t.definir_poste(9)


def test_implantation_moitie_transversale():
    """La moitié des outils sont montés transversalement en périphérie, l'autre travaille dans l'axe."""
    t = Tourelle()
    implantations = [t.poste(n).implantation for n in t.postes()]
    assert implantations[:4] == ["transversal", "axial", "transversal", "axial"]
    assert implantations.count("transversal") == implantations.count("axial") == 6
    assert set(implantations) <= set(IMPLANTATIONS)
    # la queue attendue découle de l'implantation
    assert t.queue_attendue(1) == "carree" and t.queue_attendue(2) == "cylindrique"
    t.definir_implantation(2, "transversal")
    assert t.queue_attendue(2) == "carree"
    with pytest.raises(ValueError):
        t.definir_implantation(3, "oblique")


def test_garnir_vider_et_correcteur():
    t = Tourelle()
    assert t.garnis() == [] and t.poste(1).libelle() == "libre"
    p = t.garnir(1, "SCLCR 2020 K09", "CCMT 09T308")
    assert p.est_garni() and p.libelle() == "SCLCR 2020 K09 + CCMT 09T308"
    assert t.garnis() == [p] and "1 poste(s) garni(s)" in t.description()
    # un porte-plaquette seul suffit à garnir
    t.garnir(3, "MGEHR 2020-3")
    assert t.poste(3).libelle() == "MGEHR 2020-3"
    # le correcteur : vide tant que rien n'est renseigné
    c = t.poste(1).correcteur
    assert not c.est_renseigne() and c.texte() == "—"
    t.poste(1).correcteur = Correcteur(numero=1, x=-12.345, z=84.5, rayon_bec=0.8, orientation=3)
    texte = t.poste(1).correcteur.texte()
    assert texte.startswith("D1") and "X -12.345" in texte and "R 0.8" in texte and "C3" in texte
    # vider rend le poste libre et efface son correcteur
    t.vider(1)
    assert not t.poste(1).est_garni() and t.poste(1).correcteur.texte() == "—"
    with pytest.raises(ValueError):
        t.poste(13)


def test_aller_retour_json():
    t = Tourelle()
    t.garnir(5, "PCLNR 2020 K12", "CNMG 120408")
    t.definir_implantation(5, "transversal")
    t.poste(5).correcteur = Correcteur(2, 1.5, -3.25, 0.8, 4)
    t.poste(5).commentaire = "outil d'ébauche"
    t.definir_poste(5)
    t2 = Tourelle.from_dict(t.to_dict())
    assert t2.to_dict() == t.to_dict()
    assert t2.poste(5).libelle() == "PCLNR 2020 K12 + CNMG 120408"
    assert t2.poste(5).correcteur.orientation == 4 and t2.poste(5).commentaire == "outil d'ébauche"
    assert t2.poste_en_travail == 5 and len(t2.postes_garnis) == 12
    # un enregistrement incomplet se relit avec les valeurs par défaut
    t3 = Tourelle.from_dict({"postes": [{"numero": 1, "porte_plaquette": "SDJCR 2020 K11"}]})
    assert t3.nb_postes == 12 and len(t3.postes_garnis) == 12
    assert t3.poste(1).porte_plaquette == "SDJCR 2020 K11" and t3.poste(1).correcteur.numero == 0
    assert Tourelle.from_dict({}).nb_postes == 12
