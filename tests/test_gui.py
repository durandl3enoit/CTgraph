"""Tests de l'interface (plateforme Qt hors écran) : tracé, aimantation, sélection, cotes, glissement, élagage, fichiers.

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
    for cle in win.vue.aimants:
        win.cases_aimants[cle].setChecked(True)
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


def glisser(vue, depart: QPoint, arrivee: QPoint, pas: int = 5) -> None:
    QTest.mousePress(vue.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, depart)
    for i in range(1, pas + 1):
        QTest.mouseMove(vue.viewport(), depart + (arrivee - depart) * i / pas)
        QTest.qWait(5)
    QTest.mouseRelease(vue.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, arrivee)
    QTest.qWait(10)


def rectangle(win, largeur: float = 40.0, hauteur: float = 20.0, fermer: bool = True) -> None:
    """Trace un rectangle posé sur l'axe entre z = -largeur et z = 0, puis termine la chaîne (Échap)."""
    vue = win.vue
    win.choisir_outil("ligne")
    clic(vue, 0, 0)
    clic(vue, 0, hauteur)
    clic(vue, -largeur, hauteur)
    clic(vue, -largeur, 0)
    if fermer:
        clic(vue, 0, 0)
    QTest.keyClick(vue, Qt.Key.Key_Escape)
    win.choisir_outil("selection")


def test_tracer_un_rectangle_pose_les_relations_automatiques(fenetre):
    win, vue = fenetre, fenetre.vue
    win.choisir_outil("ligne")
    clic(vue, 0, 0)            # départ sur l'axe, à l'origine
    clic(vue, 0.2, 20)         # presque vertical : relation verticale automatique
    clic(vue, -40, 20.3)       # presque horizontal
    clic(vue, -40.1, 0)        # retour sur l'axe
    clic(vue, 0, 0)            # fermeture sur le premier point (accrochage)
    QTest.keyClick(vue, Qt.Key.Key_Escape)
    e = win.esquisse
    assert len(e.points) == 4
    assert len(e.lignes) == 4
    types = sorted(r.type for r in e.relations.values())
    assert types.count(TypeRelation.VERTICAL) == 2
    # une seule horizontale : celle du trait sur l'axe serait redondante avec « sur l'axe », elle est retirée
    assert types.count(TypeRelation.HORIZONTAL) == 1
    assert types.count(TypeRelation.SUR_AXE) == 2
    assert win.resultat.succes
    xs = sorted({round(p.x, 6) for p in e.points.values()})
    assert xs[0] == 0.0 and len(xs) == 2
    ecran(win, "rectangle")


def test_aimantation_desactivable(fenetre):
    win, vue = fenetre, fenetre.vue
    win.cases_aimants["ortho"].setChecked(False)
    win.cases_aimants["axe"].setChecked(False)
    assert win.vue.aimants["ortho"] is False and win.vue.aimants["axe"] is False
    win.choisir_outil("ligne")
    clic(vue, 0, 0.5)          # près de l'axe mais pas dessus : pas d'accrochage
    clic(vue, 0.3, 20)         # presque vertical : pas de relation
    QTest.keyClick(vue, Qt.Key.Key_Escape)
    e = win.esquisse
    assert not e.relations
    # un clic simulé vise au pixel près : environ 0,1 mm à cette échelle
    zs = sorted(p.z for p in e.points.values())
    assert zs[1] == pytest.approx(0.3, abs=0.1)
    assert min(abs(p.x) for p in e.points.values()) == pytest.approx(0.5, abs=0.1)
    # les réglages sont mémorisés
    assert win.reglages.get_bool("aimant.ortho", True) is False
    win.cases_aimants["ortho"].setChecked(True)
    win.cases_aimants["axe"].setChecked(True)


def test_aimantation_45_degres_et_alignement(fenetre):
    win, vue = fenetre, fenetre.vue
    win.choisir_outil("ligne")
    clic(vue, 0, 0)
    clic(vue, -20, 19.4)       # à 44° environ : aligné sur 45°
    QTest.keyClick(vue, Qt.Key.Key_Escape)
    e = win.esquisse
    haut = max(e.points.values(), key=lambda p: p.x)
    assert haut.z == pytest.approx(-20.0, abs=0.1)
    assert haut.x == pytest.approx(-haut.z, abs=1e-9)      # exactement à 45°
    # alignement avec un point existant : même x que le sommet, depuis un départ ni vertical ni à 45°
    win.choisir_outil("ligne")
    clic(vue, -50, 35)
    acc = vue.accrocher(pos(vue, -30, 19.6), vue._debut)
    assert acc.x == pytest.approx(haut.x, abs=1e-9) and acc.guides and acc.auto is None
    QTest.keyClick(vue, Qt.Key.Key_Escape)


def test_accrochage_sur_une_ligne_pose_point_sur_ligne(fenetre):
    win, vue = fenetre, fenetre.vue
    rectangle(win)
    win.choisir_outil("ligne")
    clic(vue, -20, 20)         # milieu du côté haut : point sur ligne
    clic(vue, -20, 30)
    QTest.keyClick(vue, Qt.Key.Key_Escape)
    e = win.esquisse
    assert any(r.type == TypeRelation.POINT_SUR_LIGNE for r in e.relations.values())
    assert win.resultat.succes and not win.resultat.conflits


def test_selection_cumulative_et_vide(fenetre):
    win, vue = fenetre, fenetre.vue
    rectangle(win)
    e = win.esquisse
    clic(vue, -20, 20)         # côté haut
    clic(vue, 0, 10)           # face avant
    assert len(vue.selection) == 2 and all(e.genre(i) == "ligne" for i in vue.selection)
    clic(vue, -20, 20)         # un second clic sur le même élément le retire
    assert len(vue.selection) == 1
    clic(vue, 0, 20)           # un point s'ajoute aussi
    assert len(vue.selection) == 2 and any(e.genre(i) == "point" for i in vue.selection)
    clic(vue, 30, 30)          # dans le vide : tout est désélectionné
    assert vue.selection == []


def test_menu_contextuel_propose_les_relations_possibles(fenetre):
    win, vue = fenetre, fenetre.vue
    rectangle(win)
    e = win.esquisse
    menu = win.construire_menu_contextuel()
    assert any("Sélectionnez" in a.text() for a in menu.actions())
    clic(vue, -20, 20)
    clic(vue, 0, 10)           # deux lignes perpendiculaires
    textes = [a.text() for a in win.construire_menu_contextuel().actions()]
    assert "Perpendiculaire" in textes and "Parallèle" in textes and "Égal" in textes
    assert "Coter la sélection (Angle)" in textes
    assert "Horizontal" not in textes          # pas pour deux lignes
    assert "Supprimer la sélection" in textes
    # une ligne et un point : point sur ligne
    vue.selection = [next(iter(e.lignes)), next(iter(e.points))]
    textes = [a.text() for a in win.construire_menu_contextuel().actions()]
    assert "Point sur ligne" in textes


def test_cotes_et_modification(fenetre):
    win, vue = fenetre, fenetre.vue
    rectangle(win)
    e = win.esquisse
    p_origine = next(p for p in e.points.values() if abs(p.z) < 1e-6 and abs(p.x) < 1e-6)
    vue.selection = [p_origine.id]
    win.appliquer_relation(TypeRelation.FIXE)
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
    n = len(e.cotes)
    win.annuler()
    assert len(win.esquisse.cotes) == n - 1


def test_glisser_un_point_a_la_souris(fenetre):
    win, vue = fenetre, fenetre.vue
    rectangle(win, fermer=False)
    e = win.esquisse
    coin = next(p for p in e.points.values() if p.z < -30 and p.x > 10)
    glisser(vue, pos(vue, coin.z, coin.x), pos(vue, -60, 20))
    assert coin.z == pytest.approx(-60.0, abs=0.5)
    assert coin.x == pytest.approx(20.0, abs=0.5)         # la ligne horizontale le retient en x
    assert vue.selection == []                            # un glissement ne sélectionne pas
    assert win.act_annuler.isEnabled()
    win.annuler()
    assert win.esquisse.points[coin.id].z == pytest.approx(-40.0, abs=0.5)


def test_zoom_garde_le_point_sous_le_curseur(fenetre):
    vue = fenetre.vue
    p = pos(vue, -30, 10)
    avant = vue.mapToScene(p)
    vue.zoomer(1.5, p)
    apres = vue.mapToScene(p)
    assert (apres.x(), apres.y()) == pytest.approx((avant.x(), avant.y()), abs=0.05)
    vue.zoomer(1 / 1.5, p)
    apres = vue.mapToScene(p)
    assert (apres.x(), apres.y()) == pytest.approx((avant.x(), avant.y()), abs=0.05)


def test_elaguer_par_un_trait(fenetre):
    win, vue = fenetre, fenetre.vue
    rectangle(win)
    e = win.esquisse
    # une ligne qui traverse le rectangle de part en part, de (-20, -5) à (-20, 30)
    win.choisir_outil("ligne")
    clic(vue, -20, -5)
    clic(vue, -20, 30)
    QTest.keyClick(vue, Qt.Key.Key_Escape)
    verticale = next(li for li in e.lignes.values() if max(e.points[li.p1].x, e.points[li.p2].x) > 25)
    dessus = max(p.x for li in e.lignes.values() if li.id != verticale.id for p in (e.points[li.p1], e.points[li.p2]))
    n_lignes = len(e.lignes)
    win.choisir_outil("elaguer")
    win.combo_elagage.setCurrentIndex(0)                   # jusqu'aux croisements
    glisser(vue, pos(vue, -25, 25), pos(vue, -15, 25))     # trait au-dessus du rectangle : coupe le dépassement haut
    assert len(e.lignes) == n_lignes
    haut = max(e.points[verticale.p1].x, e.points[verticale.p2].x)
    assert haut == pytest.approx(dessus, abs=1e-6)         # raccourcie exactement au côté haut du rectangle
    assert any(r.type == TypeRelation.POINT_SUR_LIGNE for r in e.relations.values())
    assert win.resultat.succes and not win.resultat.conflits
    # mode « tout » : le trait supprime la verticale entière
    win.combo_elagage.setCurrentIndex(3)
    glisser(vue, pos(vue, -25, 10), pos(vue, -15, 10))
    assert verticale.id not in e.lignes
    assert len(e.lignes) == n_lignes - 1
    ecran(win, "elagage")
    win.annuler()
    assert verticale.id in win.esquisse.lignes


def test_outil_cote_deduit_le_type(fenetre):
    win, vue = fenetre, fenetre.vue
    win._demander_valeur = lambda libelle, unite, defaut, mini: (defaut, True)   # pas de boîte de dialogue
    rectangle(win)
    e = win.esquisse
    haut = next(li for li in e.lignes.values() if all(e.points[p].x > 10 for p in (li.p1, li.p2)))
    face = next(li for li in e.lignes.values() if all(abs(e.points[p].z) < 1e-6 for p in (li.p1, li.p2)))
    fond = next(li for li in e.lignes.values() if all(e.points[p].z < -30 for p in (li.p1, li.p2)))
    win.choisir_outil("cote")
    # ligne horizontale, cote posée au-dessus : longueur Z
    clic(vue, -20, 20)
    assert vue._cote_elements == [haut.id]
    clic(vue, -20, 30)
    c = list(e.cotes.values())[-1]
    assert c.type == TypeCote.LONGUEUR_Z and c.elements == (haut.id,) and c.valeur == pytest.approx(40.0, abs=0.2)
    assert c.decalage[1] == pytest.approx(10.0, abs=0.2)
    # la même ligne, cote posée à côté : diamètre
    clic(vue, -20, 20)
    clic(vue, 15, 10)
    c = list(e.cotes.values())[-1]
    assert c.type == TypeCote.DIAMETRE and c.valeur == pytest.approx(40.0, abs=0.2)
    # un point : diamètre
    clic(vue, -40, 20)
    clic(vue, -55, 10)
    c = list(e.cotes.values())[-1]
    assert c.type == TypeCote.DIAMETRE and e.genre(c.elements[0]) == "point"
    # deux faces verticales : longueur Z entre elles
    clic(vue, 0, 10)
    clic(vue, -40, 10)
    assert vue._cote_elements == [face.id, fond.id]
    clic(vue, -20, -8)
    c = list(e.cotes.values())[-1]
    assert c.type == TypeCote.LONGUEUR_Z and c.valeur == pytest.approx(40.0, abs=0.2)
    assert all(e.genre(i) == "point" for i in c.elements)
    # deux lignes perpendiculaires : angle
    clic(vue, 0, 10)
    clic(vue, -20, 20)
    clic(vue, -5, 15)
    c = list(e.cotes.values())[-1]
    assert c.type == TypeCote.ANGLE and abs(c.valeur) == pytest.approx(90.0, abs=0.5)
    # un arc : rayon
    win.choisir_outil("arc")
    clic(vue, 20, 10)
    clic(vue, 30, 20)
    clic(vue, 27.07, 12.93)
    win.choisir_outil("cote")
    arc = next(iter(e.arcs.values()))
    clic(vue, 27.07, 12.93)
    assert vue._cote_elements == [arc.id]
    clic(vue, 40, 30)
    c = list(e.cotes.values())[-1]
    assert c.type == TypeCote.RAYON and c.valeur == pytest.approx(10.0, abs=0.3)
    # deux lignes horizontales : écart (profondeur de gorge)
    win.choisir_outil("ligne")
    clic(vue, -30, 35)
    clic(vue, -10, 35)
    QTest.keyClick(vue, Qt.Key.Key_Escape)
    win.choisir_outil("cote")
    clic(vue, -20, 20)
    assert vue._cote_elements == [haut.id]
    clic(vue, -25, 35)
    assert len(vue._cote_elements) == 2
    clic(vue, -28, 27)
    c = list(e.cotes.values())[-1]
    assert c.type == TypeCote.ECART and c.valeur == pytest.approx(15.0, abs=0.3)
    assert win.resultat.succes
    # Échap abandonne une cote commencée
    clic(vue, -20, 20)
    QTest.keyClick(vue, Qt.Key.Key_Escape)
    assert vue._cote_elements == []
    ecran(win, "outil_cote")


def test_contour_ferme_detecte(fenetre):
    win, vue = fenetre, fenetre.vue
    win.choisir_outil("ligne")
    clic(vue, 10, 30)                   # chaîne ouverte, loin de l'axe : rien
    clic(vue, 30, 30)
    clic(vue, 30, 40)
    QTest.keyClick(vue, Qt.Key.Key_Escape)
    assert vue.contours_fermes() == []
    rectangle(win, fermer=False)        # trois côtés dont les bouts touchent l'axe : fermé par l'axe
    contours = vue.contours_fermes()
    assert len(contours) == 1 and len(contours[0]) == 3
    win.choisir_outil("ligne")
    clic(vue, -40, 0)
    clic(vue, 0, 0)                     # referme sur l'origine
    QTest.keyClick(vue, Qt.Key.Key_Escape)
    contours = vue.contours_fermes()
    assert len(contours) == 1 and len(contours[0]) == 4
    # un arc remplace un côté : le contour reste fermé
    e = win.esquisse
    haut = next(li for li in e.lignes.values()
                if all(e.points[p].x > 10 and e.points[p].z <= 1e-6 for p in (li.p1, li.p2)))
    p1, p2 = haut.p1, haut.p2
    avant = e.to_dict()

    def action_ratee():
        e.supprimer(haut.id)
        e.ajouter_ligne(p1, 9999)          # échoue après avoir modifié le modèle

    assert not win._modifier(action_ratee)
    assert win.esquisse.to_dict() == avant     # le modèle est restauré tel quel
    e = win.esquisse

    def action():
        c = e.ajouter_point(-20, 20)
        e.ajouter_arc(c.id, p1, p2, horaire=e.points[p1].z > e.points[p2].z)
        e.supprimer(haut.id)

    assert win._modifier(action)
    contours = vue.contours_fermes()
    assert len(contours) == 1 and any(e.genre(i) == "arc" for i, _ in contours[0])
    ecran(win, "contour_ferme")


def test_cote_surcontrainte_devient_pilotee(fenetre):
    win, vue = fenetre, fenetre.vue
    win._demander_valeur = lambda libelle, unite, defaut, mini: (defaut, True)
    rectangle(win)
    e = win.esquisse
    origine = next(p for p in e.points.values() if abs(p.z) < 1e-6 and abs(p.x) < 1e-6)
    vue.selection = [origine.id]
    win.appliquer_relation(TypeRelation.FIXE)
    haut = next(li for li in e.lignes.values() if all(e.points[p].x > 10 for p in (li.p1, li.p2)))
    face = next(li for li in e.lignes.values() if all(abs(e.points[p].z) < 1e-6 for p in (li.p1, li.p2)))
    fond = next(li for li in e.lignes.values() if all(e.points[p].z < -30 for p in (li.p1, li.p2)))
    win.poser_cote(TypeCote.LONGUEUR_Z, (haut.id,), (0.0, 8.0))
    win.poser_cote(TypeCote.DIAMETRE, (haut.id,), (6.0, 0.0))
    assert win.resultat.entierement_contraint
    # une troisième cote, redondante avec la longueur : elle devient pilotée au lieu de sur-contraindre
    win.poser_cote(TypeCote.LONGUEUR_Z, (face.p1, fond.p1), (0.0, -8.0))
    c = list(e.cotes.values())[-1]
    assert c.pilotee and c.valeur == pytest.approx(40.0, abs=0.2)
    assert win.resultat.entierement_contraint and not win.resultat.conflits
    assert e.texte_cote(c).startswith("(")
    # elle suit la cote pilotante
    longueur = next(co for co in e.cotes.values() if co.type == TypeCote.LONGUEUR_Z and not co.pilotee)
    win._appliquer_resultat(win.solveur.modifier_cote(longueur.id, 55.0))
    assert c.valeur == pytest.approx(55.0, abs=1e-6)
    # la rendre pilotante est refusé tant que l'autre longueur existe
    assert not win.basculer_pilotee(c.id)
    assert c.pilotee
    # une fois l'autre longueur supprimée, elle peut piloter
    vue.selection = [longueur.id]
    win.supprimer_selection()
    assert win.basculer_pilotee(c.id)
    assert not c.pilotee and win.resultat.entierement_contraint
    ecran(win, "cote_pilotee")


def test_clic_semi_long_puis_glisser_elague(fenetre):
    win, vue = fenetre, fenetre.vue
    rectangle(win)
    e = win.esquisse
    win.choisir_outil("ligne")
    clic(vue, -20, -5)
    clic(vue, -20, 30)
    QTest.keyClick(vue, Qt.Key.Key_Escape)
    win.choisir_outil("selection")
    verticale = next(li for li in e.lignes.values() if max(e.points[li.p1].x, e.points[li.p2].x) > 25)
    dessus = max(p.x for li in e.lignes.values() if li.id != verticale.id for p in (e.points[li.p1], e.points[li.p2]))
    win.combo_elagage.setCurrentIndex(0)
    depart, arrivee = pos(vue, -25, 25), pos(vue, -15, 25)
    QTest.mousePress(vue.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, depart)
    QTest.qWait(500)                                   # clic semi-long : l'outil Élaguer se sélectionne
    assert vue.outil == "elaguer" and win.actions_outils["elaguer"].isChecked()
    for i in range(1, 6):
        QTest.mouseMove(vue.viewport(), depart + (arrivee - depart) * i / 5)
        QTest.qWait(5)
    QTest.mouseRelease(vue.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, arrivee)
    QTest.qWait(10)
    haut = max(e.points[verticale.p1].x, e.points[verticale.p2].x)
    assert haut == pytest.approx(dessus, abs=1e-6)
    assert vue.outil == "selection"                    # l'outil d'avant revient après le geste
    # un clic bref dans le vide reste une désélection, sans élagage
    n = len(e.lignes)
    clic(vue, 30, 30)
    assert len(e.lignes) == n and vue.outil == "selection"


def test_clic_droit_molette_change_d_outil(fenetre):
    from PySide6.QtCore import QPointF
    from PySide6.QtGui import QWheelEvent
    win, vue = fenetre, fenetre.vue
    p = pos(vue, -20, 10)
    QTest.mousePress(vue.viewport(), Qt.MouseButton.RightButton, Qt.KeyboardModifier.NoModifier, p)

    def molette(delta):
        ev = QWheelEvent(QPointF(p), QPointF(vue.viewport().mapToGlobal(p)), QPoint(0, 0), QPoint(0, delta),
                         Qt.MouseButton.RightButton, Qt.KeyboardModifier.NoModifier, Qt.ScrollPhase.NoScrollPhase,
                         False)
        vue.wheelEvent(ev)

    echelle = vue.echelle()
    molette(-120)
    assert vue.outil == "ligne" and win.actions_outils["ligne"].isChecked()
    molette(-120)
    assert vue.outil == "arc"
    molette(120)
    assert vue.outil == "ligne"
    assert vue.echelle() == pytest.approx(echelle)     # pas de zoom pendant le cycle
    assert vue._bulle is not None and vue._bulle.isVisible() and vue._bulle.text() == "Ligne"
    assert vue._droit_molette                          # le relâchement n'ouvrira pas le menu
    win.choisir_outil("selection")


def test_symboles_horizontal_vertical(fenetre):
    from ctgraph.ui.vue_esquisse import Etiquette
    win, vue = fenetre, fenetre.vue
    rectangle(win)
    symboles = {it.symbole for it in vue._items if isinstance(it, Etiquette)}
    assert {"horizontal", "vertical"} <= symboles
    textes = {it.texte for it in vue._items if isinstance(it, Etiquette) and it.symbole}
    assert textes == {"z", "x"}


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
    rectangle(win, fermer=False)
    chemin = str(tmp_path / "piece.ctg")
    assert win._ecrire(chemin)
    assert not win._modifie
    avant = win.esquisse.to_dict()
    win.nouveau()
    assert win.esquisse.est_vide()
    assert win.ouvrir_fichier(chemin)
    assert win.esquisse.to_dict() == avant
    assert os.path.basename(chemin) in win.windowTitle()


def test_suppression(fenetre):
    win, vue = fenetre, fenetre.vue
    win.choisir_outil("ligne")
    clic(vue, 0, 0)
    clic(vue, 0, 20)
    clic(vue, -40, 20)
    QTest.keyClick(vue, Qt.Key.Key_Escape)
    win.choisir_outil("selection")
    e = win.esquisse
    clic(vue, -20, 20)        # sur la ligne horizontale
    assert len(vue.selection) == 1 and e.genre(vue.selection[0]) == "ligne"
    win.supprimer_selection()
    assert len(e.lignes) == 1
    assert len(e.points) == 2          # le point orphelin a disparu
