"""Tests du catalogue des porte-plaquettes : cohérence, filtrage, compatibilité VDI 30."""
from __future__ import annotations

import pytest

from ctgraph.outils import CATALOGUE, FAMILLES, MAINS, QUEUE_MAXI, filtrer, par_famille


def test_catalogue_coherent():
    assert len(CATALOGUE) > 60
    # toutes les queues tiennent dans un porte-outil VDI 30
    assert all(0 < pp.queue_mm <= QUEUE_MAXI for pp in CATALOGUE)
    # désignations uniques, familles et mains connues, longueurs et plaquettes renseignées
    designations = [pp.designation for pp in CATALOGUE]
    assert len(set(designations)) == len(designations)
    assert all(pp.famille in FAMILLES for pp in CATALOGUE)
    assert all(pp.main in MAINS.values() for pp in CATALOGUE)
    assert all(pp.longueur > 0 and pp.plaquette and pp.usage and pp.fixation for pp in CATALOGUE)
    # aucune lettre de main oubliée dans un gabarit
    assert not [pp for pp in CATALOGUE if "_" in pp.designation]
    # un outil intérieur annonce l'alésage minimal, qui dépasse sa queue
    interieurs = [pp for pp in CATALOGUE if pp.alesage_mini]
    assert len(interieurs) > 15 and all(pp.alesage_mini > pp.queue_mm for pp in interieurs)
    # chaque famille est pourvue, et les deux mains existent pour les outils courants
    groupes = par_famille()
    assert list(groupes) == list(FAMILLES) and all(groupes[cle] for cle in FAMILLES)
    assert {"SCLCR 2020 K09", "SCLCL 2020 K09"} <= set(designations)
    assert "SDNCN 2020 K11" in designations and "SRDCN 2020 K10" in designations


def test_references_attendues_par_famille():
    noms = {pp.famille: {pp2.designation for pp2 in CATALOGUE if pp2.famille == pp.famille} for pp in CATALOGUE}
    assert {"PCLNR 2020 K12", "MWLNR 2020 K08", "MTJNR 2020 K16"} <= noms["ext_neg"]
    assert {"SDJCR 2020 K11", "SVJCR 2020 K16", "STFCR 2020 K16"} <= noms["ext_pos"]
    assert {"S16Q-SCLCR 09", "S20R-SDUCR 11", "A20R-SCLCR 09"} <= noms["alesage"]
    assert {"SER 2020 K16", "SNR 0016 Q16"} <= noms["filetage"]
    assert {"MGEHR 2020-3", "MGIVR 2016-2"} <= noms["gorge"]
    # la barre la plus grosse tenue en VDI 30 fait Ø 20, la plus petite queue carrée 16 × 16
    barres = [pp for pp in CATALOGUE if pp.queue.startswith("Ø")]
    assert max(pp.queue_mm for pp in barres) == 20.0
    carres = [pp for pp in CATALOGUE if "×" in pp.queue]
    assert min(pp.queue_mm for pp in carres) == 16.0


def test_angle_d_attaque_et_textes():
    scl = next(pp for pp in CATALOGUE if pp.designation == "SCLCR 2020 K09")
    assert scl.attaque == 95.0 and scl.texte_attaque == "95°" and scl.texte_longueur == "125 mm"
    assert scl.main == "droite" and scl.queue == "20 × 20"
    assert "Plaquette CCMT 09T3.." in scl.description() and "ISO 5608" in scl.description()
    ronde = next(pp for pp in CATALOGUE if pp.designation == "SRDCN 2020 K10")
    assert ronde.attaque is None and ronde.texte_attaque == "—"
    barre = next(pp for pp in CATALOGUE if pp.designation == "S16Q-SCLCR 09")
    assert "Alésage minimal 20 mm" in barre.description() and "ISO 6261" in barre.description()
    sdq = next(pp for pp in CATALOGUE if pp.designation == "SDQCR 2020 K11")
    assert sdq.texte_attaque == "107,5°"


def test_filtrage():
    assert len(filtrer("")) == len(CATALOGUE)
    # par désignation, par plaquette, par main, et par mots cumulés
    assert all("cnmg" in pp.plaquette.lower() for pp in filtrer("CNMG"))
    gauches = filtrer("gauche")
    assert gauches and all(pp.main == "gauche" for pp in gauches)
    assert {pp.designation for pp in filtrer("sclc 2020")} == {"SCLCR 2020 K09", "SCLCL 2020 K09",
                                                               "SCLCR 2020 K12", "SCLCL 2020 K12"}
    assert filtrer("tronçonnage") and all(pp.famille == "gorge" for pp in filtrer("tronçonnage"))
    assert filtrer("introuvable zzz") == []
    # le filtre porte aussi sur une sous-liste
    assert filtrer("09", filtrer("S16Q")) == [pp for pp in CATALOGUE
                                              if pp.designation.startswith("S16Q") and "09" in pp.designation]
