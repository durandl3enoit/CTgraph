"""Tests de l'interface (plateforme Qt hors écran) : tracé à la souris, accrochage, cotes, glissement, fichiers.

Lancer : .venv\\Scripts\\python -m pytest tests\\test_gui.py
Une variable CTGRAPH_SHOTS=<dossier> enregistre des captures PNG pour contrôle visuel.
"""
from __future__ import annotations

import os
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest  # noqa: E402
from PySide6.QtCore import QPoint, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from ctgraph.esquisse.modele import TypeCote, TypeRelation  # noqa: E402

SHOTS = os.environ.get("CTGRAPH_SHOTS")


@pytest.fixture(scope="module")
def app():
    tmp = tempfile.mkdtemp(prefix="ctgraph_gui_")
    os.environ["CTGRAPH_SETTINGS"] = os.path.join(tmp, "prefs.ini")
    a = QApplication.instance() or QApplication(sys.argv)
    yield a


@pytest.fixture
def fenetre(app):
    from ctgraph.ui.fenetre_principale import FenetrePrincipale
    win = FenetrePrincipale()
    win.resize(1300, 900)
    win.show()
    QTest.qWaitForWindowExposed(win)
    win.vue.tout_voir()
    QTest.qWait(30)
    yield win
    win._modifie = False       # pas de boîte de dialogue à la fermeture
    win.close()
    QTest.qWait(20)


def ecran(win, nom: str) -> None:
    if SHOTS:
        os.makedirs(SHOTS, exist_ok=True)
        win.grab().save(os.path.join(SHOTS, nom + ".png"))


def pos(vue, z: float, x: float) -> QPoint:
    return vue.mapFromScene(z, x)


def clic(vue, z: float, x: float, bouton=Qt.MouseButton.LeftButton, modif=Qt.KeyboardModifier.NoModifier) -> None:
    p = pos(vue, z, x)
    QTest.mouseMove(vue.viewport(), p)
    QTest.mouseClick(vue.viewport(), bouton, modif, p)
    QTest.qWait(10)


def test_tracer_un_rectangle_pose_les_relations_automatiques(fenetre):
    win, vue = fenetre, fenetre.vue
    win.choisir_outil("ligne")
    clic(vue, 0, 0)            # départ sur l'axe, à l'origine
    clic(vue, 0.2, 20)         # presque vertical : relation verticale automatique
    clic(vue, -40, 20.3)       # presque horizontal
    clic(vue, -40.1, 0)        # retour sur l'axe
    clic(vue, 0, 0)            # fermeture sur le premier point (accrochage)
    clic(vue, 0, 0, Qt.MouseButton.RightButton)   # fin de la chaîne
    e = win.esquisse
    assert len(e.points) == 4
    assert len(e.lignes) == 4
    types = sorted(r.type for r in e.relations.values())
    assert types.count(TypeRelation.VERTICAL) == 2
    # une seule horizontale : celle du trait sur l'axe serait redondante avec « sur l'axe », elle est retirée
    assert types.count(TypeRelation.HORIZONTAL) == 1
    assert types.count(TypeRelation.SUR_AXE) == 2
    assert win.resultat.succes
    # le rectangle a bien été redressé par le solveur
    xs = sorted({round(p.x, 6) for p in e.points.values()})
    assert xs[0] == 0.0 and len(xs) == 2
    ecran(win, "rectangle")


def test_cotes_et_modification(fenetre):
    win, vue = fenetre, fenetre.vue
    win.choisir_outil("ligne")
    clic(vue, 0, 0)
    clic(vue, 0, 20)
    clic(vue, -40, 20)
    clic(vue, -40, 0)
    clic(vue, 0, 0)
    clic(vue, 0, 0, Qt.MouseButton.RightButton)
    e = win.esquisse
    win.choisir_outil("selection")
    # fixer l'origine
    p_origine = next(p for p in e.points.values() if abs(p.z) < 1e-6 and abs(p.x) < 1e-6)
    vue.selection = [p_origine.id]
    win.appliquer_relation(TypeRelation.FIXE)
    # cotes posées par le modèle (la boîte de dialogue est contournée)
    haut = next(li for li in e.lignes.values() if all(e.points[p].x > 10 for p in (li.p1, li.p2)))
    assert win._modifier(lambda: e.ajouter_cote(TypeCote.DIAMETRE, (haut.id,), 40.0, (5, 0)))
    assert win._modifier(lambda: e.ajouter_cote(TypeCote.LONGUEUR_Z, (haut.id,), 40.0, (0, 6)))
    assert win.resultat.entierement_contraint, win.resultat.texte()
    diam = next(c for c in e.cotes.values() if c.type == TypeCote.DIAMETRE)
    res = win.solveur.modifier_cote(diam.id, 56.0)
    assert res.succes
    assert max(p.x for p in e.points.values()) == pytest.approx(28.0, abs=1e-6)
    win._appliquer_resultat(res)
    ecran(win, "cotes")
    # annulation : la cote de longueur disparaît
    n = len(e.cotes)
    win.annuler()
    assert len(win.esquisse.cotes) == n - 1


def test_glisser_un_point_a_la_souris(fenetre):
    win, vue = fenetre, fenetre.vue
    win.choisir_outil("ligne")
    clic(vue, 0, 0)
    clic(vue, 0, 20)
    clic(vue, -40, 20)
    clic(vue, -40, 0)
    clic(vue, 0, 0, Qt.MouseButton.RightButton)
    e = win.esquisse
    win.choisir_outil("selection")
    coin = next(p for p in e.points.values() if p.z < -30 and p.x > 10)
    depart = pos(vue, coin.z, coin.x)
    arrivee = pos(vue, -60, 20)
    QTest.mousePress(vue.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, depart)
    # mouvement en plusieurs pas, comme une vraie souris
    for i in range(1, 6):
        p = depart + (arrivee - depart) * i / 5
        QTest.mouseMove(vue.viewport(), p)
        QTest.qWait(5)
    QTest.mouseRelease(vue.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, arrivee)
    QTest.qWait(10)
    assert coin.z == pytest.approx(-60.0, abs=0.5)
    assert coin.x == pytest.approx(20.0, abs=0.5)         # la ligne horizontale le retient en x
    assert win.act_annuler.isEnabled()
    win.annuler()
    assert win.esquisse.points[coin.id].z == pytest.approx(-40.0, abs=0.5)


def test_arc_trois_points(fenetre):
    win, vue = fenetre, fenetre.vue
    win.choisir_outil("arc")
    clic(vue, 0, 10)
    clic(vue, -10, 20)
    clic(vue, -2.93, 17.07)   # point à 45° sur le cercle de centre (-10, 10), rayon 10
    e = win.esquisse
    assert len(e.arcs) == 1
    arc = next(iter(e.arcs.values()))
    assert e.rayon(arc.id) == pytest.approx(10.0, abs=0.2)
    c = e.points[arc.centre]
    assert c.z == pytest.approx(-10.0, abs=0.2) and c.x == pytest.approx(10.0, abs=0.2)
    assert arc.horaire is False
    ecran(win, "arc")


def test_enregistrer_et_rouvrir(fenetre, tmp_path):
    win, vue = fenetre, fenetre.vue
    win.choisir_outil("ligne")
    clic(vue, 0, 0)
    clic(vue, 0, 20)
    clic(vue, -40, 20)
    clic(vue, 0, 0, Qt.MouseButton.RightButton)
    chemin = str(tmp_path / "piece.ctg")
    assert win._ecrire(chemin)
    assert not win._modifie
    avant = win.esquisse.to_dict()
    win.nouveau()
    assert win.esquisse.est_vide()
    assert win.ouvrir_fichier(chemin)
    assert win.esquisse.to_dict() == avant
    assert os.path.basename(chemin) in win.windowTitle()


def test_suppression_et_selection(fenetre):
    win, vue = fenetre, fenetre.vue
    win.choisir_outil("ligne")
    clic(vue, 0, 0)
    clic(vue, 0, 20)
    clic(vue, -40, 20)
    clic(vue, 0, 0, Qt.MouseButton.RightButton)
    win.choisir_outil("selection")
    e = win.esquisse
    clic(vue, -20, 20)        # sur la ligne horizontale
    assert len(vue.selection) == 1 and e.genre(vue.selection[0]) == "ligne"
    win.supprimer_selection()
    assert len(e.lignes) == 1
    assert len(e.points) == 2          # le point orphelin a disparu
    clic(vue, 30, 30)                  # dans le vide : désélection
    assert vue.selection == []
