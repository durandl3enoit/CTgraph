"""Tests du catalogue des plaquettes : désignations, géométrie des formes, filtrage, lien avec les outils."""
from __future__ import annotations

import math

import pytest

from ctgraph.plaquettes import (ANGLES_FORME, CATALOGUE, FAMILLES, FORMES_PLAQUETTE, TYPES_ISO, filtrer,
                                forme_plaquette, par_famille, pour_base, sommets_forme)


def test_catalogue_coherent():
    assert len(CATALOGUE) > 40
    designations = [pl.designation for pl in CATALOGUE]
    assert len(set(designations)) == len(designations)
    assert all(pl.famille in FAMILLES for pl in CATALOGUE)
    assert all(pl.forme in FORMES_PLAQUETTE for pl in CATALOGUE)
    assert all(pl.arete > 0 and pl.epaisseur > 0 and pl.rayon_bec > 0 and pl.usage for pl in CATALOGUE)
    groupes = par_famille()
    assert list(groupes) == list(FAMILLES) and all(groupes[cle] for cle in FAMILLES)
    # les négatives ont une dépouille nulle et deux faces, les positives une dépouille ouverte
    assert all(pl.depouille == 0.0 for pl in groupes["negative"])
    assert all(pl.depouille >= 5.0 for pl in groupes["positive"])


def test_designation_iso_1832():
    cnmg = next(pl for pl in CATALOGUE if pl.designation == "CNMG 120408")
    assert cnmg.base == "CNMG 1204" and cnmg.forme == "C" and cnmg.depouille == 0.0
    assert cnmg.arete == 12.9 and cnmg.cercle_inscrit == 12.7 and cnmg.epaisseur == 4.76
    assert cnmg.rayon_bec == 0.8 and cnmg.texte_rayon == "0,8" and cnmg.texte_depouille == "0°"
    assert cnmg.type_iso == "G" and cnmg.texte_type == TYPES_ISO["G"]
    assert "ISO 1832" in cnmg.description() and "Arête 12,9 mm" in cnmg.description()
    assert cnmg.texte_arete == "12,9" and cnmg.texte_epaisseur == "4,76" and cnmg.texte_cercle == "12,7"
    # le code du rayon de bec est bien deux chiffres en dixièmes
    assert {pl.designation for pl in pour_base("CNMG 1204")} == {"CNMG 120404", "CNMG 120408", "CNMG 120412"}
    # une plaquette positive de finition
    ccmt = next(pl for pl in CATALOGUE if pl.designation == "CCMT 09T304")
    assert ccmt.depouille == 7.0 and ccmt.epaisseur == 3.97 and ccmt.type_iso == "T"
    # la base relie la plaquette au porte-plaquette, dont le catalogue note « CCMT 09T3.. »
    assert pour_base("CCMT 09T3..") == pour_base("CCMT 09T3")


def test_chaque_porte_plaquette_trouve_ses_plaquettes():
    """Toute plaquette nommée par un porte-plaquette existe au catalogue : le porte-lame fait exception,
    il reçoit une lame et non une plaquette."""
    from ctgraph.outils import CATALOGUE as OUTILS
    manquantes = {pp.plaquette for pp in OUTILS if not pour_base(pp.plaquette) and pp.forme != "lame"}
    assert manquantes == set(), manquantes
    # un porte-plaquette de filetage nomme ses deux mains : les deux se retrouvent
    assert {pl.designation for pl in pour_base("16ER / 16EL")} == {"16ER AG60", "16EL AG60", "16ER 150ISO"}


def test_formes_geometriques():
    assert forme_plaquette("WNMG 0804..") == "W" and forme_plaquette("MGMN 300") == "gorge"
    # losanges : l'angle de pointe se retrouve sur le contour
    for forme in ("C", "D", "V"):
        s = sommets_forme(forme)
        assert len(s) == 4
        gauche, haut, droite = s[0], s[1], s[2]
        u = (haut[0] - gauche[0], haut[1] - gauche[1])
        w = (s[3][0] - gauche[0], s[3][1] - gauche[1])
        cos = (u[0] * w[0] + u[1] * w[1]) / (math.hypot(*u) * math.hypot(*w))
        assert math.degrees(math.acos(cos)) == pytest.approx(ANGLES_FORME[forme], abs=1e-6)
        assert math.hypot(*droite) == pytest.approx(1.0)       # inscrit dans le cercle de rayon 1
    assert len(sommets_forme("T")) == 3 and len(sommets_forme("S")) == 4
    assert len(sommets_forme("W")) == 6                        # trois pointes et trois creux
    assert sommets_forme("R") == [] and sommets_forme("gorge") == []
    # le triangle pointe en haut (x négatif vers le haut dans le repère écran du dessin)
    assert sommets_forme("T")[0] == pytest.approx((0.0, -1.0), abs=1e-9)
    # le carré est à plat
    assert sorted(round(abs(z), 6) for z, _ in sommets_forme("S")) == [pytest.approx(0.70710678, abs=1e-6)] * 4


def test_filtrage():
    assert len(filtrer("")) == len(CATALOGUE)
    assert all(pl.forme == "C" for pl in filtrer("losange 80"))
    assert {pl.designation for pl in filtrer("CNMG 1204")} == {"CNMG 120404", "CNMG 120408", "CNMG 120412"}
    assert filtrer("filetage") and all(pl.famille == "filetage" for pl in filtrer("filetage"))
    assert filtrer("zzz introuvable") == []
    assert filtrer("08", filtrer("CNMG")) == [pl for pl in CATALOGUE if pl.designation.endswith("08")
                                              and pl.designation.startswith("CNMG")]
