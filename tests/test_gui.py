"""Tests de l'interface (plateforme Qt hors écran) : tracé, aimantation, sélection, cotes, glissement, élagage, fichiers.

Lancer : .venv\\Scripts\\python -m pytest tests\\test_gui.py
Une variable CTGRAPH_SHOTS=<dossier> enregistre des captures PNG pour contrôle visuel.
"""
from __future__ import annotations

import math
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
    os.environ["CTGRAPH_SANS_3D"] = "1"          # pas d'OpenGL sur la plateforme hors écran
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
    win.act_voir_montage.setChecked(False)     # le montage élargit la vue : les clics simulés perdraient en précision
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
    clic(vue, 0, 0)            # départ sur l'axe, à l'origine : « sur l'axe » et « origine Z »
    clic(vue, 0.2, 20)         # presque vertical : relation verticale automatique
    clic(vue, -40, 20.3)       # presque horizontal
    clic(vue, -40.1, 0)        # retour sur l'axe
    clic(vue, 0, 0)            # fermeture sur le premier point (accrochage)
    QTest.keyClick(vue, Qt.Key.Key_Escape)
    e = win.esquisse
    assert len(e.points) == 4
    assert len(e.lignes) == 4
    types = sorted(r.type for r in e.relations.values())
    # les deux points de la face avant s'accrochent sur Z = 0 : « origine Z » chacun, la verticale automatique
    # devient redondante et disparaît ; de même l'horizontale du trait sur l'axe, redondante avec « sur l'axe »
    assert types.count(TypeRelation.ORIGINE_Z) == 2
    assert types.count(TypeRelation.VERTICAL) == 1
    assert types.count(TypeRelation.HORIZONTAL) == 1
    assert types.count(TypeRelation.SUR_AXE) == 2
    assert win.resultat.succes
    # un rectangle ancré à l'origine n'a plus que ses deux dimensions comme degrés de liberté
    assert win.resultat.dof == 2
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
    assert menu.relations_proposees == []
    clic(vue, -20, 20)
    clic(vue, 0, 10)           # deux lignes perpendiculaires
    menu = win.construire_menu_contextuel()
    textes = [a.text() for a in menu.actions()]
    proposees = menu.relations_proposees
    assert {TypeRelation.PERPENDICULAIRE, TypeRelation.PARALLELE, TypeRelation.EGAL} <= set(proposees)
    assert TypeRelation.HORIZONTAL not in proposees          # pas pour deux lignes
    assert "Coter : Angle" in textes
    assert "Supprimer la sélection" in textes
    # une ligne horizontale : diamètre par rapport à l'axe Z, et longueur Z
    haut = next(li for li in e.lignes.values() if all(e.points[p].x > 10 for p in (li.p1, li.p2)))
    vue.selection = [haut.id]
    menu = win.construire_menu_contextuel()
    textes = [a.text() for a in menu.actions()]
    assert "Coter : Diamètre" in textes and "Coter : Longueur Z" in textes
    assert menu.cotes_proposees == [TypeCote.LONGUEUR_Z, TypeCote.DIAMETRE]
    win._demander_valeur = lambda libelle, unite, defaut, mini: (defaut, True)
    next(a for a in menu.actions() if a.text() == "Coter : Diamètre").trigger()
    c = list(e.cotes.values())[-1]
    assert c.type == TypeCote.DIAMETRE and c.elements == (haut.id,) and c.valeur == pytest.approx(40.0, abs=0.2)
    # une face verticale : position Z et hauteur
    face = next(li for li in e.lignes.values() if all(abs(e.points[p].z) < 1e-6 for p in (li.p1, li.p2)))
    vue.selection = [face.id]
    assert win.construire_menu_contextuel().cotes_proposees == [TypeCote.POSITION_Z, TypeCote.DISTANCE]
    # les relations sont des icônes seules : aucune action textuelle ne porte leur nom
    assert "Perpendiculaire" not in textes
    # une ligne et un point : point sur ligne
    vue.selection = [next(iter(e.lignes)), next(iter(e.points))]
    assert TypeRelation.POINT_SUR_LIGNE in win.construire_menu_contextuel().relations_proposees


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
    glisser(vue, pos(vue, -25, 25), pos(vue, -15, 25))     # trait au-dessus du rectangle : coupe le dépassement haut
    assert len(e.lignes) == n_lignes
    haut = max(e.points[verticale.p1].x, e.points[verticale.p2].x)
    assert haut == pytest.approx(dessus, abs=1e-6)         # raccourcie exactement au côté haut du rectangle
    assert any(r.type == TypeRelation.POINT_SUR_LIGNE for r in e.relations.values())
    assert win.resultat.succes and not win.resultat.conflits
    # un trait au milieu du rectangle : le seul croisement restant est l'axe, la verticale est raccourcie
    # jusqu'à lui (son sommet repose déjà sur le côté haut, ce n'est plus un croisement)
    glisser(vue, pos(vue, -25, 10), pos(vue, -15, 10))
    assert verticale.id in e.lignes and len(e.lignes) == n_lignes
    assert max(e.points[verticale.p1].x, e.points[verticale.p2].x) == pytest.approx(0.0, abs=1e-6)
    ecran(win, "elagage")
    win.annuler()
    e2 = win.esquisse                          # l'annulation recharge le modèle : on relit la ligne par son identifiant
    li = e2.lignes[verticale.id]
    assert max(e2.points[li.p1].x, e2.points[li.p2].x) == pytest.approx(dessus, abs=1e-6)


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
    # un point : diamètre si la cote est posée à côté
    clic(vue, -40, 20)
    clic(vue, -55, 10)
    c = list(e.cotes.values())[-1]
    assert c.type == TypeCote.DIAMETRE and e.genre(c.elements[0]) == "point"
    # le même point, cote posée au-dessus : position Z depuis l'origine de la pièce. Le tracé est parti de
    # l'origine et la longueur est déjà cotée : cette position est redondante, elle devient pilotée.
    clic(vue, -40, 20)
    clic(vue, -30, 36)
    c = list(e.cotes.values())[-1]
    assert c.type == TypeCote.POSITION_Z and c.valeur == pytest.approx(-40.0, abs=0.2)
    assert c.pilotee and e.texte_cote(c).startswith("(Z -")
    # la face arrière (verticale), cote posée au-dessus : position Z aussi
    clic(vue, -40, 10)
    clic(vue, -20, 44)
    c = list(e.cotes.values())[-1]
    assert c.type == TypeCote.POSITION_Z and c.valeur == pytest.approx(-40.0, abs=0.2)
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


def test_outils_arrondi_et_chanfrein(fenetre):
    win, vue = fenetre, fenetre.vue
    rectangle(win)
    e = win.esquisse
    coin = next(p for p in e.points.values() if p.z < -30 and p.x > 10)       # coin arrière haut
    win._demander_valeur = lambda libelle, unite, defaut, mini: (3.0, True)
    win.choisir_outil("arrondi")
    clic(vue, coin.z, coin.x)
    assert e.points[coin.id].construction and len(e.arcs) == 1
    arc = next(iter(e.arcs.values()))
    assert e.rayon(arc.id) == pytest.approx(3.0, abs=1e-6)
    assert sum(1 for r in e.relations.values() if r.type == TypeRelation.TANGENT) == 2
    assert win.resultat.succes and not win.resultat.conflits
    assert win._rayon_arrondi == 3.0                                           # mémorisé pour la prochaine fois
    # chanfrein sur le coin avant haut
    coin2 = next(p for p in e.points.values() if abs(p.z) < 1e-6 and p.x > 10)
    win._demander_valeur = lambda libelle, unite, defaut, mini: (1.5, True)
    win.choisir_outil("chanfrein")
    clic(vue, coin2.z, coin2.x)
    assert e.points[coin2.id].construction
    assert any(c.type == TypeCote.ANGLE for c in e.cotes.values())
    assert any(c.type == TypeCote.DISTANCE and c.valeur == pytest.approx(1.5, abs=1e-6) for c in e.cotes.values())
    assert win.resultat.succes and not win.resultat.conflits
    ecran(win, "coins")
    win.annuler()
    assert not win.esquisse.points[coin2.id].construction


def test_molette_sur_une_etiquette_regle_la_cote(fenetre):
    from PySide6.QtCore import QPointF
    from PySide6.QtGui import QWheelEvent
    from ctgraph.ui.vue_esquisse import ROLE_ID, ROLE_VARIANTE, Etiquette
    win, vue = fenetre, fenetre.vue
    win._demander_valeur = lambda libelle, unite, defaut, mini: (40.0, True)
    rectangle(win)
    e = win.esquisse
    haut = next(li for li in e.lignes.values() if all(e.points[p].x > 10 for p in (li.p1, li.p2)))
    win.poser_cote(TypeCote.DIAMETRE, (haut.id,), (6.0, 0.0))
    diam = list(e.cotes.values())[-1]
    etiquette = next(it for it in vue._items if isinstance(it, Etiquette) and it.data(ROLE_ID) == diam.id
                     and not it.data(ROLE_VARIANTE))
    p = vue.mapFromScene(etiquette.pos())
    QTest.mousePress(vue.viewport(), Qt.MouseButton.RightButton, Qt.KeyboardModifier.NoModifier, p)
    assert vue._droit_cote == (diam.id, None)

    def molette(delta, modif=Qt.KeyboardModifier.NoModifier):
        ev = QWheelEvent(QPointF(p), QPointF(vue.viewport().mapToGlobal(p)), QPoint(0, 0), QPoint(0, delta),
                         Qt.MouseButton.RightButton, modif, Qt.ScrollPhase.NoScrollPhase, False)
        vue.wheelEvent(ev)

    n_annulations = len(win._annuler)
    molette(120)
    molette(120)
    assert diam.valeur == pytest.approx(42.0)
    molette(-120, Qt.KeyboardModifier.ShiftModifier)
    assert diam.valeur == pytest.approx(41.9)
    assert max(pt.x for pt in e.points.values()) == pytest.approx(20.95, abs=1e-6)
    assert vue._bulle_texte is not None and vue._bulle_texte.isVisible() and "41.9" in vue._bulle_texte.text()
    assert vue.outil == "selection"                     # pas de changement d'outil
    # clic droit maintenu + glisser vertical : même réglage, un pas par tranche de pixels, vers le haut = plus
    from PySide6.QtGui import QMouseEvent
    from ctgraph.ui.vue_esquisse import PIXELS_PAR_PAS

    def glisser_droit(dy):
        q = p + QPoint(0, dy)
        ev = QMouseEvent(QMouseEvent.Type.MouseMove, QPointF(q), QPointF(vue.viewport().mapToGlobal(q)),
                         Qt.MouseButton.NoButton, Qt.MouseButton.RightButton, Qt.KeyboardModifier.NoModifier)
        vue.mouseMoveEvent(ev)

    glisser_droit(-3 * PIXELS_PAR_PAS)
    assert diam.valeur == pytest.approx(44.9)
    glisser_droit(-3 * PIXELS_PAR_PAS + 2 * PIXELS_PAR_PAS)     # deux tranches vers le bas
    assert diam.valeur == pytest.approx(42.9)
    assert vue._droit_molette                            # le relâchement n'ouvrira pas le menu
    assert len(win._annuler) == n_annulations           # l'annulation n'est poussée qu'au relâchement
    QTest.mouseRelease(vue.viewport(), Qt.MouseButton.RightButton, Qt.KeyboardModifier.NoModifier, p)
    assert len(win._annuler) == n_annulations + 1
    win.annuler()
    assert win.esquisse.cotes[diam.id].valeur == pytest.approx(40.0)


def test_glisser_droit_suit_la_ligne_de_cote(fenetre):
    from PySide6.QtCore import QPointF
    from PySide6.QtGui import QMouseEvent
    from ctgraph.ui.vue_esquisse import PIXELS_PAR_PAS, ROLE_ID, ROLE_VARIANTE, Etiquette
    win, vue = fenetre, fenetre.vue
    win._demander_valeur = lambda libelle, unite, defaut, mini: (40.0, True)
    rectangle(win)
    e = win.esquisse
    haut = next(li for li in e.lignes.values() if all(e.points[p].x > 10 for p in (li.p1, li.p2)))
    win.poser_cote(TypeCote.LONGUEUR_Z, (haut.id,), (0.0, 6.0))
    longueur = list(e.cotes.values())[-1]
    assert vue._vecteur_glisser(longueur.id) == pytest.approx((1.0, 0.0))      # ligne de cote horizontale
    etiquette = next(it for it in vue._items if isinstance(it, Etiquette) and it.data(ROLE_ID) == longueur.id
                     and not it.data(ROLE_VARIANTE))
    p = vue.mapFromScene(etiquette.pos())
    QTest.mousePress(vue.viewport(), Qt.MouseButton.RightButton, Qt.KeyboardModifier.NoModifier, p)

    def glisser_droit(dx, dy):
        q = p + QPoint(dx, dy)
        ev = QMouseEvent(QMouseEvent.Type.MouseMove, QPointF(q), QPointF(vue.viewport().mapToGlobal(q)),
                         Qt.MouseButton.NoButton, Qt.MouseButton.RightButton, Qt.KeyboardModifier.NoModifier)
        vue.mouseMoveEvent(ev)

    glisser_droit(0, -3 * PIXELS_PAR_PAS)            # vertical : sans effet sur une cote horizontale
    assert longueur.valeur == pytest.approx(40.0)
    glisser_droit(2 * PIXELS_PAR_PAS, -3 * PIXELS_PAR_PAS)   # vers la droite : plus
    assert longueur.valeur == pytest.approx(42.0)
    glisser_droit(-1 * PIXELS_PAR_PAS, 0)                   # vers la gauche : moins
    assert longueur.valeur == pytest.approx(39.0)
    QTest.mouseRelease(vue.viewport(), Qt.MouseButton.RightButton, Qt.KeyboardModifier.NoModifier, p)
    # un rayon se tire vers l'extérieur de l'arc, en diagonale
    win.choisir_outil("arc")
    clic(vue, -70, 0)
    clic(vue, -50, 20)
    clic(vue, -64, 14)
    arc = list(e.arcs.values())[-1]
    win.choisir_outil("selection")
    win._demander_valeur = lambda libelle, unite, defaut, mini: (20.0, True)
    win.poser_cote(TypeCote.RAYON, (arc.id,), (3.0, 3.0))
    rayon = list(e.cotes.values())[-1]
    sx, sy = vue._vecteur_glisser(rayon.id)
    centre, milieu = e.points[arc.centre], vue._points_arc(arc.id, 2)[1]
    attendu = (milieu[0] - centre.z, -(milieu[1] - centre.x))
    n = math.hypot(*attendu)
    assert (sx, sy) == pytest.approx((attendu[0] / n, attendu[1] / n))
    assert abs(sx) > 0.1 and abs(sy) > 0.1                   # bien en diagonale


def test_cote_de_ligne_biaise(fenetre):
    win, vue = fenetre, fenetre.vue
    win.choisir_outil("ligne")
    clic(vue, 0, 0)
    clic(vue, -30, 20)          # ligne biaise de (0, 0) à (-30, 20)
    QTest.keyClick(vue, Qt.Key.Key_Escape)
    e = win.esquisse
    li = next(iter(e.lignes.values()))
    assert not vue.est_horizontale(li.id) and not vue.est_verticale(li.id)
    # à côté de la ligne, entre ses extrémités : sa longueur vraie, posée parallèlement
    t, els, dec = vue.deduire_cote([li.id], pos(vue, -10, 15))
    assert t == TypeCote.DISTANCE and els == (li.id,)
    # au-dessus de sa boîte : la longueur Z ; à droite : la longueur X ; en diagonale au-delà d'un coin : l'angle
    assert vue.deduire_cote([li.id], pos(vue, -15, 40))[0] == TypeCote.LONGUEUR_Z
    assert vue.deduire_cote([li.id], pos(vue, 20, 10))[0] == TypeCote.LONGUEUR_X
    assert vue.deduire_cote([li.id], pos(vue, 20, 40))[0] == TypeCote.ANGLE
    # la longueur X se pose et se tient : l'écart radial entre les bouts
    win._demander_valeur = lambda libelle, unite, defaut, mini: (25.0, True)
    win.poser_cote(TypeCote.LONGUEUR_X, (li.id,), (6.0, 0.0))
    cx = list(e.cotes.values())[-1]
    assert cx.type == TypeCote.LONGUEUR_X and cx.valeur == 25.0
    a, b = (e.points[i] for i in e.extremites(li.id))
    assert abs(b.x - a.x) == pytest.approx(25.0, abs=1e-6)
    win.annuler()
    e = win.esquisse                                     # l'annulation recharge l'esquisse
    # avec l'outil Cote : clic sur la ligne, puis à côté d'elle ; la valeur demandée est la longueur vraie
    demandes = []

    def demander(libelle, unite, defaut, mini):
        demandes.append((libelle, defaut))
        return 40.0, True

    win._demander_valeur = demander
    win.choisir_outil("cote")
    clic(vue, -15, 10)          # sur la ligne
    clic(vue, -10, 15)          # à côté
    cote = list(e.cotes.values())[-1]
    assert cote.type == TypeCote.DISTANCE and cote.valeur == pytest.approx(40.0)
    assert demandes and demandes[0][1] == pytest.approx(math.hypot(30, 20), abs=0.3)   # tracé à la souris, au pixel
    a, b = (e.points[i] for i in e.extremites(li.id))
    assert math.hypot(b.z - a.z, b.x - a.x) == pytest.approx(40.0, abs=1e-6)


def test_references_du_montage_alignement_et_cote(fenetre):
    from ctgraph.montage import Montage
    from ctgraph.esquisse.modele import Esquisse
    win, vue = fenetre, fenetre.vue
    win.definir_montage(Montage())
    win.act_voir_montage.setChecked(True)
    rectangle(win)
    e = win.esquisse
    assert set(e.references) == {"face_reference", "face_mors", "appui_mors", "face_mandrin", "brut_ext"}
    assert e.references["face_reference"].valeur == 0.0 and "à 2 du bout du brut" in e.references["face_reference"].libelle
    # un point sélectionné : le menu propose de l'aligner sur chaque référence, ou d'en coter l'écart
    coin = next(p for p in e.points.values() if p.z < -10 and p.x > 10)
    vue.selection = [coin.id]
    menu = win.construire_menu_contextuel()
    assert menu.references_proposees == [r.nom for r in win.montage.references()]
    # cote depuis la face du mandrin : l'écart signé, qui règle la position du coin arrière (libre en Z)
    win._demander_valeur = lambda libelle, unite, defaut, mini: (130.0, True)
    win.coter_depuis_reference("face_mandrin")
    cote = list(e.cotes.values())[-1]
    assert cote.type == TypeCote.DEPUIS_REFERENCE and cote.reference == "face_mandrin" and cote.valeur == 130.0
    assert not cote.pilotee and e.points[coin.id].z == pytest.approx(win.montage.z_face_mandrin() + 130.0)
    assert e.texte_cote(cote) == "mandrin 130"
    # la référence s'enregistre et se relit
    e2 = Esquisse.from_json(e.to_json())
    assert e2.cotes[cote.id].reference == "face_mandrin"
    win.annuler()
    e = win.esquisse                                     # l'annulation recharge l'esquisse
    # alignement sur la face des mors : le point y va, et suit le montage quand il change
    vue.selection = [coin.id]
    win.aligner_sur_reference("face_mors")
    assert any(r.type == TypeRelation.SUR_REFERENCE and r.reference == "face_mors" for r in e.relations.values())
    assert e.points[coin.id].z == pytest.approx(win.montage.z_face_mors())
    m = Montage()
    m.prise.depassement = 130.0
    win.definir_montage(m)
    assert e.points[coin.id].z == pytest.approx(-130.0)
    assert any(r.reference == "face_mors" for r in Esquisse.from_json(e.to_json()).relations.values())
    # une face verticale ne vise que les plans Z, une ligne horizontale que les surfaces du brut
    verticale = next(li for li in e.lignes.values() if vue.est_verticale(li.id))
    horizontale = next(li for li in e.lignes.values() if vue.est_horizontale(li.id))
    assert all(r.axe == "z" for r in win.references_pour([verticale.id]))
    assert [r.nom for r in win.references_pour([horizontale.id])] == ["brut_ext"]
    # aimantation : un tracé qui finit sur la face des mors y est accroché, avec la relation
    acc = vue.accrocher(pos(vue, win.montage.z_face_mors() + 0.3, 40.0))
    assert acc.reference == "face_mors" and acc.z == pytest.approx(win.montage.z_face_mors())
    win.act_voir_montage.setChecked(False)


def test_curseur_suit_l_outil(fenetre):
    win, vue = fenetre, fenetre.vue
    win.choisir_outil("selection")
    assert vue.viewport().cursor().shape() == Qt.CursorShape.ArrowCursor
    for outil in ("ligne", "arc", "cote", "arrondi", "chanfrein", "elaguer"):
        win.choisir_outil(outil)
        assert vue.viewport().cursor().shape() == Qt.CursorShape.BitmapCursor
    win.choisir_outil("selection")


def test_menu_contextuel_a_des_icones(fenetre):
    win, vue = fenetre, fenetre.vue
    rectangle(win)
    clic(vue, -20, 20)
    clic(vue, 0, 10)
    from PySide6.QtWidgets import QWidgetAction
    menu = win.construire_menu_contextuel()
    actions = [a for a in menu.actions() if not a.isSeparator() and a.isEnabled() and not isinstance(a, QWidgetAction)]
    assert actions and all(not a.icon().isNull() for a in actions)
    assert menu.relations_proposees


def test_menu_contextuel_propose_arrondi_et_chanfrein_sur_un_coin(fenetre):
    win, vue = fenetre, fenetre.vue
    rectangle(win)
    e = win.esquisse
    coin = next(p for p in e.points.values() if p.z < -30 and p.x > 10)
    haut = next(li for li in e.lignes.values() if all(e.points[p].x > 10 for p in (li.p1, li.p2)))
    fond = next(li for li in e.lignes.values() if all(e.points[p].z < -30 for p in (li.p1, li.p2)))
    face = next(li for li in e.lignes.values() if all(abs(e.points[p].z) < 1e-6 for p in (li.p1, li.p2)))
    # un coin sélectionné
    vue.selection = [coin.id]
    menu = win.construire_menu_contextuel()
    textes = [a.text() for a in menu.actions()]
    assert menu.coin_propose == coin.id and "Arrondi…" in textes and "Chanfrein…" in textes
    # deux lignes concourantes
    vue.selection = [haut.id, fond.id]
    assert win.construire_menu_contextuel().coin_propose == coin.id
    # deux lignes qui ne se touchent pas : rien
    vue.selection = [face.id, fond.id]
    menu = win.construire_menu_contextuel()
    assert menu.coin_propose is None and "Arrondi…" not in [a.text() for a in menu.actions()]
    # depuis le menu, l'arrondi s'applique au coin
    vue.selection = [coin.id]
    win._demander_valeur = lambda libelle, unite, defaut, mini: (2.0, True)
    next(a for a in win.construire_menu_contextuel().actions() if a.text() == "Arrondi…").trigger()
    assert e.points[coin.id].construction and len(e.arcs) == 1


def test_zone_relations_repliee_par_defaut(fenetre):
    win = fenetre
    assert not win.zone_relations.est_deployee()
    assert not win.boutons_relations[TypeRelation.HORIZONTAL].isVisibleTo(win)
    win.zone_relations.deployer(True)
    assert win.boutons_relations[TypeRelation.HORIZONTAL].isVisibleTo(win)
    assert win.reglages.get_bool("relations.deployee", False) is True
    win.zone_relations.deployer(False)


def test_outil_cote_deplace_une_cote(fenetre):
    win, vue = fenetre, fenetre.vue
    win._demander_valeur = lambda libelle, unite, defaut, mini: (defaut, True)
    rectangle(win)
    e = win.esquisse
    haut = next(li for li in e.lignes.values() if all(e.points[p].x > 10 for p in (li.p1, li.p2)))
    win.poser_cote(TypeCote.LONGUEUR_Z, (haut.id,), (0.0, 8.0))
    c = list(e.cotes.values())[-1]
    win.choisir_outil("cote")
    depart = pos(vue, -20, 28)                 # l'étiquette « 40 » est au-dessus de la ligne, à x = 20 + 8
    arrivee = pos(vue, -10, 34)
    glisser(vue, depart, arrivee)
    assert c.decalage[0] == pytest.approx(10.0, abs=0.3) and c.decalage[1] == pytest.approx(14.0, abs=0.3)
    assert vue._cote_elements == []            # déplacer une cote n'en commence pas une nouvelle
    assert len(e.cotes) == 1


def test_egal_entre_deux_cotes_depuis_l_interface(fenetre):
    from ctgraph.ui.vue_esquisse import Etiquette
    win, vue = fenetre, fenetre.vue
    win._demander_valeur = lambda libelle, unite, defaut, mini: (defaut, True)
    rectangle(win)
    e = win.esquisse
    coin_arriere = next(p for p in e.points.values() if p.z < -30 and p.x > 10)
    coin_avant = next(p for p in e.points.values() if abs(p.z) < 1e-6 and p.x > 10)
    win._demander_valeur = lambda libelle, unite, defaut, mini: (3.0, True)
    win.choisir_outil("arrondi")
    clic(vue, coin_arriere.z, coin_arriere.x)
    win._demander_valeur = lambda libelle, unite, defaut, mini: (5.0, True)
    clic(vue, coin_avant.z, coin_avant.x)
    rayons = [c for c in e.cotes.values() if c.type == TypeCote.RAYON]
    assert len(rayons) == 2 and sorted(c.valeur for c in rayons) == [3.0, 5.0]
    # les deux cotes de rayon sélectionnées : « égal » est proposé, et la seconde suit la première
    vue.selection = [rayons[0].id, rayons[1].id]
    assert TypeRelation.EGAL in win.construire_menu_contextuel().relations_proposees
    win.appliquer_relation(TypeRelation.EGAL)
    assert rayons[1].valeur == pytest.approx(rayons[0].valeur)
    assert win.resultat.succes and not win.resultat.conflits
    assert e.cote_maitresse(rayons[1].id) == rayons[0].id
    assert any(isinstance(it, Etiquette) and it.texte == "=" for it in vue._items)   # symbole sur l'étiquette
    # régler la première par la molette entraîne la seconde
    assert win.ajuster_cote(rayons[0].id, 1, None, False)
    assert rayons[1].valeur == pytest.approx(rayons[0].valeur)
    assert win.ajuster_cote(rayons[1].id, 1, None, False) is None     # la suiveuse ne se règle pas


def test_diametre_accompagne_de_son_rayon(fenetre):
    from ctgraph.ui.vue_esquisse import ROLE_ID, ROLE_VARIANTE, Etiquette
    win, vue = fenetre, fenetre.vue
    rectangle(win)
    e = win.esquisse
    haut = next(li for li in e.lignes.values() if all(e.points[p].x > 10 for p in (li.p1, li.p2)))
    win._demander_valeur = lambda libelle, unite, defaut, mini: (40.0, True)
    win.poser_cote(TypeCote.DIAMETRE, (haut.id,), (6.0, 0.0))
    diam = list(e.cotes.values())[-1]
    etiquettes = [it for it in vue._items if isinstance(it, Etiquette) and it.data(ROLE_ID) == diam.id]
    assert sorted(it.texte for it in etiquettes) == ["R 20", "Ø 40"]
    rayon = next(it for it in etiquettes if it.data(ROLE_VARIANTE) == "rayon")
    assert rayon.texte == "R 20"
    # éditer par le rayon : 28 donne un diamètre de 56
    demandes = []

    def demander(libelle, unite, defaut, mini):
        demandes.append((libelle, defaut))
        return (28.0, True)

    win._demander_valeur = demander
    win.editer_cote(diam.id, "rayon")
    assert demandes[-1] == ("Rayon", 20.0)
    assert diam.valeur == pytest.approx(56.0)
    assert max(p.x for p in e.points.values()) == pytest.approx(28.0, abs=1e-6)
    # éditer par le diamètre : 50
    win._demander_valeur = lambda libelle, unite, defaut, mini: (50.0, True)
    win.editer_cote(diam.id)
    assert diam.valeur == pytest.approx(50.0)
    assert e.texte_rayon(diam) == "R 25"


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


def test_contour_ferme_par_une_relation_coincidente(fenetre):
    win, vue = fenetre, fenetre.vue
    win.cases_aimants["objets"].setChecked(False)      # le dernier point ne doit pas s'accrocher au premier
    win.choisir_outil("ligne")
    clic(vue, 10, 10)
    clic(vue, 30, 10)
    clic(vue, 30, 30)
    clic(vue, 10, 30)
    clic(vue, 10, 14)                                  # revient près du départ, sans le rejoindre
    QTest.keyClick(vue, Qt.Key.Key_Escape)
    win.cases_aimants["objets"].setChecked(True)
    e = win.esquisse
    assert len(e.points) == 5 and vue.contours_fermes() == []
    depart = next(p for p in e.points.values() if abs(p.z - 10) < 0.2 and abs(p.x - 10) < 0.2)
    arrivee = next(p for p in e.points.values() if abs(p.z - 10) < 0.2 and abs(p.x - 14) < 0.2)
    vue.selection = [depart.id, arrivee.id]
    win.appliquer_relation(TypeRelation.COINCIDENT)
    assert win.resultat.succes and not win.resultat.conflits
    assert (e.points[arrivee.id].z, e.points[arrivee.id].x) == pytest.approx((e.points[depart.id].z, e.points[depart.id].x), abs=1e-6)
    contours = vue.contours_fermes()
    assert len(contours) == 1 and len(contours[0]) == 4


def test_cote_surcontrainte_devient_pilotee_sans_demander_de_valeur(fenetre):
    win, vue = fenetre, fenetre.vue
    demandes = []

    def demander(libelle, unite, defaut, mini):
        demandes.append(libelle)
        return (defaut, True)

    win._demander_valeur = demander
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
    assert demandes == ["Longueur Z", "Diamètre"]
    # une troisième cote, redondante avec la longueur : elle devient pilotée, et aucune valeur n'est demandée
    win.poser_cote(TypeCote.LONGUEUR_Z, (face.p1, fond.p1), (0.0, -8.0))
    c = list(e.cotes.values())[-1]
    assert c.pilotee and c.valeur == pytest.approx(40.0, abs=0.2)
    assert demandes == ["Longueur Z", "Diamètre"]
    # abandonner la saisie ne pose pas de cote : sur une ligne libre, la cote piloterait, la valeur est demandée
    win.choisir_outil("ligne")
    clic(vue, 20, 30)
    clic(vue, 40, 42)
    QTest.keyClick(vue, Qt.Key.Key_Escape)
    libre = next(li for li in e.lignes.values() if e.points[li.p1].z > 10)
    n_cotes = len(e.cotes)
    win._demander_valeur = lambda libelle, unite, defaut, mini: (defaut, False)
    win.poser_cote(TypeCote.DISTANCE, (libre.id,), (0.0, 6.0))
    assert len(win.esquisse.cotes) == n_cotes
    win.vue.selection = [libre.id]
    win.supprimer_selection()                   # la ligne libre repart : l'esquisse redevient entièrement contrainte
    e = win.esquisse
    c = e.cotes[c.id]
    win._demander_valeur = demander
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
    assert vue._bulle is not None and vue._bulle.isVisible() and vue._bulle.courant == "ligne"
    assert vue._bulle.ordre()[3] == "ligne"            # l'outil actif est au milieu de la bande de sept
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
    win.montage.brut.diametre = 48.0
    win.definir_montage(win.montage)
    chemin = str(tmp_path / "piece.ctg")
    assert win._ecrire(chemin)
    assert not win._modifie
    avant = win.esquisse.to_dict()
    win.nouveau()
    assert win.esquisse.est_vide()
    assert win.ouvrir_fichier(chemin)
    assert win.esquisse.to_dict() == avant
    assert win.montage.brut.diametre == 48.0 and win.vue.montage is win.montage
    assert os.path.basename(chemin) in win.windowTitle()
    # un fichier de l'ancien format, l'esquisse seule, s'ouvre encore
    ancien = str(tmp_path / "ancien.ctg")
    with open(ancien, "w", encoding="utf-8") as f:
        f.write(win.esquisse.to_json())
    assert win.ouvrir_fichier(ancien)
    assert win.esquisse.to_dict() == avant


def test_cotes_du_brut_affichees_et_editables(fenetre):
    from ctgraph.montage import Montage
    from ctgraph.ui.vue_esquisse import ROLE_GENRE, ROLE_ID, Etiquette
    win, vue = fenetre, fenetre.vue
    win.definir_montage(Montage())                  # pas le dernier montage mémorisé par un autre test
    win.act_voir_montage.setChecked(True)
    etiquettes = {it.data(ROLE_ID): it for it in vue._items if isinstance(it, Etiquette) and it.data(ROLE_GENRE) == "brut"}
    assert set(etiquettes) == {"diametre", "longueur", "marge"}
    assert etiquettes["diametre"].texte == "Ø brut 60" and etiquettes["marge"].texte == "marge 2"
    assert etiquettes["longueur"].texte == f"L brut {win.montage.longueur_brut():g}"
    # double-clic : la valeur est demandée et appliquée
    win._demander_valeur = lambda libelle, unite, defaut, mini: (70.0, True)
    win.editer_brut("diametre")
    assert win.montage.brut.diametre == 70.0
    # la longueur du brut se répartit sur le dépassement, marge et prise inchangées
    avant = (win.montage.profondeur_prise(), win.montage.prise.surepaisseur_face)
    win._demander_valeur = lambda libelle, unite, defaut, mini: (150.0, True)
    win.editer_brut("longueur")
    assert win.montage.longueur_brut() == pytest.approx(150.0)
    assert (win.montage.profondeur_prise(), win.montage.prise.surepaisseur_face) == avant
    # molette : un pas, un dixième avec Maj ; une valeur impossible est refusée sans rien changer
    assert win.ajuster_brut("marge", 1, False) == "marge 3"
    assert win.ajuster_brut("marge", -1, True) == "marge 2.9"
    assert win.montage.longueur_brut() == pytest.approx(150.9)      # la marge fait partie de la longueur du brut
    assert win.ajuster_brut("longueur", -1, False) == "L brut 149.9"
    depassement = win.montage.prise.depassement
    win._demander_valeur = lambda libelle, unite, defaut, mini: (5.0, True)
    win.editer_brut("longueur")                      # plus court que la prise + marge : refusé
    assert win.montage.prise.depassement == depassement
    # les cotes du brut ne se sélectionnent pas
    et = etiquettes["diametre"]
    clic(vue, et.pos().x(), et.pos().y())
    assert vue.selection == []
    win.act_voir_montage.setChecked(False)


def test_dialogue_montage_et_dessin(fenetre):
    from ctgraph.ui.dialogue_montage import DialogueMontage
    win, vue = fenetre, fenetre.vue
    n_sans = len(vue._items)                   # montage masqué par la fixture : esquisse vide, rien à dessiner
    assert not win.vue.montage_visible and n_sans == 0
    win.act_voir_montage.setChecked(True)
    # brut, mors, corps du mandrin, trois cotes du brut (trait + étiquette), trois inscriptions gravées,
    # cinq plans de référence (trait + nom)
    n_refs = len(win.montage.references())
    assert n_refs == 5
    assert len(vue._items) == 3 + 6 + 3 + 2 * n_refs
    dlg = DialogueMontage(win.montage, win)
    dlg.brut_diametre.setValue(70.0)
    dlg.depassement.setValue(120.0)
    dlg.cp_presente.setChecked(True)
    m = dlg.montage_resultat()
    assert m.brut.diametre == 70.0 and m.prise.depassement == 120.0 and m.contre_pointe.presente
    assert m.mandrin.mors_modele == "SMW-Autoblok 474" and m.mandrin.reference == "210 BH-FC"
    assert "42" in dlg.alesage.text()                   # passage de barre affiché, pas réglable
    # les références gravées sont inscrites sur le dessin du montage
    from ctgraph.ui.vue_esquisse import Inscription
    textes = {it.texte for it in vue._items if isinstance(it, Inscription)}
    assert textes >= {"210 BH-FC", "passage Ø 42", "12082030 (1/16\"x90°)", "mors", "mandrin", "réf", "appui", "brut"}
    win.definir_montage(m)
    assert win.montage.z_face_mors() == -120.0 and win._modifie
    # le brut, les mors, le corps du mandrin et la contre-pointe sont dessinés, plus les cotes, inscriptions et plans
    assert len(vue._items) == 4 + 6 + 3 + 2 * n_refs
    win.act_voir_montage.setChecked(False)
    assert not vue.montage_visible and len(vue._items) == 0
    # les étages se saisissent dans le dialogue : deux étages de 25 et 45, un seul épaulement
    assert dlg.nb_etages.value() == 3 and not dlg.lignes_etages[2][1].isEnabled()
    dlg.nb_etages.setValue(2)
    assert dlg.lignes_etages[1][0].isEnabled() and not dlg.lignes_etages[2][0].isEnabled()
    dlg.lignes_etages[0][0].setValue(25.0)
    dlg.lignes_etages[1][0].setValue(45.0)
    m = dlg.montage_resultat()
    assert [(e.longueur, e.epaulement) for e in m.mandrin.etages] == [(25.0, 8.0), (45.0, 0.0)]
    assert m.mandrin.hauteur_mors() == 70.0
    # une prise de pièce impossible est refusée : serrage intérieur d'un rond plein
    dlg.serrage.setCurrentIndex(1)
    from ctgraph.esquisse.modele import ErreurEsquisse
    with pytest.raises(ErreurEsquisse):
        dlg.montage_resultat()


def test_reglages_directement_sur_le_mors(fenetre):
    from ctgraph.montage import Montage
    from ctgraph.ui.vue_esquisse import ROLE_GENRE
    win, vue = fenetre, fenetre.vue
    win.definir_montage(Montage())
    win.act_voir_montage.setChecked(True)
    mors = next(it for it in vue._items if it.data(ROLE_GENRE) == "mors")
    # le mors se voit sous le curseur, mais ne se sélectionne pas
    centre = mors.boundingRect().center()
    assert vue.element_sous(vue.mapFromScene(centre)) == ("mors", 0)
    clic(vue, centre.x(), centre.y())
    assert vue.selection == []
    # double-clic : les mors se retournent, l'appui passe sur la face du mandrin
    assert win.retourner_mors()
    assert win.montage.prise.mors_retournes and win.montage.prise.appui == 0
    assert win.montage.z_brut_arriere() == win.montage.z_face_mandrin()
    # le menu du clic droit sur le mors : retournement, serrage, appuis possibles
    menu = win.construire_menu_contextuel(montage="mors")
    assert menu.actions_montage["retourner"].isChecked()
    assert not menu.actions_montage["interieur"].isEnabled()         # pas de tube
    assert set(menu.actions_montage) == {"cotes_mors", "retourner", "exterieur", "interieur", "appui0"}
    assert win.retourner_mors()
    menu = win.construire_menu_contextuel(montage="mors")
    assert {"appui0", "appui1", "appui2"} <= set(menu.actions_montage)
    assert win.definir_appui(2) and win.montage.profondeur_prise() == 40.0
    assert not win.definir_appui(3)                                  # pas d'épaulement derrière le fond
    assert win.montage.prise.appui == 2
    # le serrage intérieur demande un tube
    assert not win.definir_serrage("interieur")
    win.act_voir_montage.setChecked(False)


def test_edition_des_cotes_du_mors(fenetre):
    from ctgraph.montage import Montage
    from ctgraph.ui.vue_esquisse import ROLE_GENRE, Etiquette, Inscription
    win, vue = fenetre, fenetre.vue
    rectangle(win)
    win.definir_montage(Montage())
    win.act_voir_montage.setChecked(True)
    ref = next(it for it in vue._items if isinstance(it, Inscription) and it.data(ROLE_GENRE) == "reference_mors")
    centre = ref.boundingRect().center()                 # en pixels : l'inscription ignore la transformation
    sous_ref = vue.mapFromScene(ref.pos()) + QPoint(int(centre.x()), int(centre.y()))
    assert vue.element_sous(sous_ref) == ("reference_mors", 0)
    # le menu de la référence du mors propose d'en modifier les cotes
    menu = win.construire_menu_contextuel(montage="reference_mors")
    assert "cotes_mors" in menu.actions_montage
    assert not any(isinstance(it, Etiquette) and it.data(ROLE_GENRE) == "cote_mors" for it in vue._items)
    win.commencer_edition_mors()
    assert vue.mode_mors and vue._bandeau_mors is not None and vue._bandeau_mors.isVisible()
    cotes = {it.data(1): it for it in vue._items if isinstance(it, Etiquette) and it.data(ROLE_GENRE) == "cote_mors"}
    assert set(cotes) == set(win.montage.cles_mors()) and cotes["mors.epaisseur"].texte == "E 40"
    # le mors et ses cotes restent vifs, tout le reste est grisé
    assert all(it.opacity() == 1.0 for it in vue._items_mors)
    assert all(it.opacity() < 1.0 for it in vue._items if it.data(ROLE_GENRE) == "ligne")
    # pendant l'édition, un clic sur l'esquisse ne sélectionne rien, et le menu ne sert qu'à conclure
    clic(vue, -20, 20)
    assert vue.selection == []
    assert "valider" in win.construire_menu_contextuel().actions_montage
    # réglage par la molette et par la boîte de saisie
    assert win.ajuster_valeur_montage("mors.epaisseur", 1, False) == "E 41"
    win._demander_valeur = lambda libelle, unite, defaut, mini: (25.0, True)
    win.editer_valeur_montage("mors.etage1.longueur")
    assert win.montage.mandrin.etages[0].longueur == 25.0 and win.montage.mandrin.epaisseur_mors == 41.0
    # Échap : tout revient comme avant
    QTest.keyClick(vue, Qt.Key.Key_Escape)
    assert not vue.mode_mors and not vue._bandeau_mors.isVisible()
    assert win.montage.mandrin.etages[0].longueur == 20.0 and win.montage.mandrin.epaisseur_mors == 40.0
    # Entrée : les réglages restent
    win.commencer_edition_mors()
    assert win.ajuster_valeur_montage("mors.etage1.epaulement", 1, False) == "h1 9"
    QTest.keyClick(vue, Qt.Key.Key_Return)
    assert not vue.mode_mors and win.montage.mandrin.etages[0].epaulement == 9.0
    assert all(it.opacity() == 1.0 for it in vue._items)
    win.act_voir_montage.setChecked(False)


def test_survol_fait_luire_l_element(fenetre):
    from PySide6.QtWidgets import QGraphicsLineItem
    from ctgraph.ui.vue_esquisse import ROLE_GENRE, ROLE_ID
    win, vue = fenetre, fenetre.vue
    rectangle(win)
    e = win.esquisse
    haut = next(li for li in e.lignes.values() if all(e.points[p].x > 10 for p in (li.p1, li.p2)))
    item = next(it for it in vue._items if isinstance(it, QGraphicsLineItem) and it.data(ROLE_ID) == haut.id)
    couleur_avant = item.pen().color()
    lueur = vue._couleurs()["lueur"]
    from PySide6.QtCore import QPointF
    from PySide6.QtGui import QMouseEvent

    def survoler(z, x):
        q = pos(vue, z, x)
        ev = QMouseEvent(QMouseEvent.Type.MouseMove, QPointF(q), QPointF(vue.viewport().mapToGlobal(q)),
                         Qt.MouseButton.NoButton, Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier)
        vue.mouseMoveEvent(ev)

    survoler(-20, 20)                                       # sur la ligne du haut
    assert vue._survol == ("ligne", haut.id) and item.pen().color() == lueur and item.pen().widthF() > 2
    survoler(-20, 60)                                       # dans le vide : l'aspect revient
    assert vue._survol is None and item.pen().color() == couleur_avant
    # un élément sélectionné garde la couleur de sélection
    clic(vue, -20, 20)
    assert haut.id in vue.selection
    item = next(it for it in vue._items if isinstance(it, QGraphicsLineItem) and it.data(ROLE_ID) == haut.id)
    survoler(-20, 60)
    survoler(-20, 20)
    assert item.pen().color() == vue._couleurs()["selection"]
    assert item.data(ROLE_GENRE) == "ligne"


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
