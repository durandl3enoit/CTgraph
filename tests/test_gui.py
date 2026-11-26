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
    win.act_zone_atelier.setChecked(False)     # les volets de l'atelier rétrécissent la vue : même raison
    for volet in win.zone_atelier.volets.values():
        volet.definir_deploye(False)           # quel que soit l'état laissé par une autre séance
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


def test_etiquette_d_angle_choisit_le_secteur(fenetre):
    win, vue = fenetre, fenetre.vue
    win.choisir_outil("ligne")
    clic(vue, 0, 0)
    clic(vue, 20, 20)            # ligne à 45°
    QTest.keyClick(vue, Qt.Key.Key_Escape)
    e = win.esquisse
    li = next(iter(e.lignes.values()))
    win._demander_valeur = lambda libelle, unite, defaut, mini: (defaut, True)
    # posée près du départ, côté +Z : 45° ; l'arc est dessiné (pas de simple ligne de rappel)
    win.poser_cote(TypeCote.ANGLE, (li.id,), (6.0 - 10.0, 1.0 - 10.0))     # décalage depuis le milieu (10, 10)
    c = list(e.cotes.values())[-1]
    assert c.secteur == 0 and c.valeur == pytest.approx(45.0, abs=0.5)
    # l'étiquette tirée de l'autre côté de la ligne, vers −Z : le secteur change, la cote lit 135°
    win.deplacer_etiquette(c.id, -12.0, 0.0)
    c = e.cotes[c.id]
    assert c.secteur == 2 and c.valeur == pytest.approx(135.0, abs=0.5)
    assert win.resultat.succes and not win.resultat.conflits
    # la géométrie n'a pas bougé
    a, b = (e.points[i] for i in e.extremites(li.id))
    assert (b.z - a.z, b.x - a.x) == pytest.approx((20.0, 20.0), abs=0.3)


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
    assert set(etiquettes) == {"diametre", "longueur", "marge", "prise"}
    assert etiquettes["diametre"].texte == "Ø brut 60" and etiquettes["marge"].texte == "marge 2"
    assert etiquettes["prise"].texte == "prise 20"
    # régler la prise : le brut n'appuie plus sur rien, il est tenu à cette longueur de la face des mors
    assert win.ajuster_brut("prise", 1, False) == "prise 21"
    assert win.montage.prise.appui == -1 and win.montage.profondeur_prise() == 21.0
    win.definir_appui(1)
    assert win.montage.profondeur_prise() == 20.0
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
    # brut, mors, corps du mandrin, quatre cotes du brut (trait + étiquette), trois inscriptions gravées,
    # cinq plans de référence (trait + nom)
    n_refs = len(win.montage.references())
    assert n_refs == 5
    assert len(vue._items) == 3 + 8 + 3 + 2 * n_refs
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
    assert len(vue._items) == 4 + 8 + 3 + 2 * n_refs
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
    assert set(menu.actions_montage) == {"cotes_mors", "retourner", "exterieur", "interieur", "appui-1", "appui0"}
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


def test_zone_stock_d_outils(fenetre):
    from PySide6.QtWidgets import QTreeWidgetItem
    from ctgraph.outils import CATALOGUE, FAMILLES, FORMES_PLAQUETTE
    win = fenetre
    zone = win.zone_outils
    win.act_zone_atelier.setChecked(True)       # la fixture la masque pour laisser la vue au large
    win.zone_atelier.volets["outils"].definir_deploye(True)
    zone.definir_stock([])                      # pas le stock laissé par une autre séance

    def lignes():
        out = []
        for i in range(zone.arbre.topLevelItemCount()):
            parent = zone.arbre.topLevelItem(i)
            out += [parent.child(j) for j in range(parent.childCount())]
        return out

    def ligne(designation: str) -> QTreeWidgetItem:
        return next(it for it in lignes() if it.text(0) == designation)

    # tout le catalogue est présenté, rangé par famille
    assert zone.arbre.topLevelItemCount() == len(FAMILLES)
    assert len(lignes()) == len(CATALOGUE)
    assert "105" in zone.lbl_total.text() or str(len(CATALOGUE)) in zone.lbl_total.text()
    it = ligne("SCLCR 2020 K09")
    assert [it.text(c) for c in range(5)] == ["SCLCR 2020 K09", "CCMT 09T3..", "95°", "20 × 20", "vis"]
    assert "ISO 5608" in it.toolTip(0)
    # choisir une ligne dessine le porte-plaquette coté
    assert zone.dessin.outil is None
    zone.arbre.setCurrentItem(it)
    QTest.qWait(10)
    assert zone.dessin.outil is not None and zone.dessin.outil.designation == "SCLCR 2020 K09"
    assert zone.dessin.outil.cotes() == [("h × b", "20 × 20"), ("l1", "125"), ("κr", "95°")]
    # une barre d'alésage est cotée par son diamètre de queue et l'alésage où elle passe
    barre = ligne("S16Q-SCLCR 09")
    zone.arbre.setCurrentItem(barre)
    assert zone.dessin.outil.cylindrique
    assert zone.dessin.outil.cotes() == [("d", "Ø 16"), ("l1", "180"), ("κr", "95°"), ("alésage mini", "20")]
    zone.arbre.setCurrentItem(it)
    # la forme de la plaquette est dessinée juste avant sa désignation
    assert not it.icon(1).isNull() and it.icon(0).isNull()
    formes = {it2.icon(1).cacheKey() for it2 in lignes()}
    assert len(formes) == len(FORMES_PLAQUETTE)       # une icône distincte par forme, et toutes présentes
    # le filtre restreint la liste et vide les familles sans réponse
    zone.filtre.setText("barre alésage")
    assert lignes() and all(it.text(0).startswith(("S", "A")) for it in lignes())
    assert zone.arbre.topLevelItemCount() == 1
    zone.filtre.setText("")
    assert len(lignes()) == len(CATALOGUE)
    # cocher une référence la met en stock, et c'est mémorisé
    recu = []
    zone.stock_change.connect(lambda s: recu.append(set(s)))
    ligne("SDJCR 2020 K11").setCheckState(0, Qt.CheckState.Checked)
    ligne("MGEHR 2020-3").setCheckState(0, Qt.CheckState.Checked)
    assert zone.stock() == {"SDJCR 2020 K11", "MGEHR 2020-3"} and recu[-1] == zone.stock()
    assert sorted(win.reglages.get("outils.stock")) == ["MGEHR 2020-3", "SDJCR 2020 K11"]
    # « En stock » n'affiche plus que les références cochées
    zone.case_stock.setChecked(True)
    assert sorted(it.text(0) for it in lignes()) == ["MGEHR 2020-3", "SDJCR 2020 K11"]
    ligne("SDJCR 2020 K11").setCheckState(0, Qt.CheckState.Unchecked)
    assert zone.stock() == {"MGEHR 2020-3"}
    zone.case_stock.setChecked(False)
    # une désignation disparue du catalogue est ignorée au rechargement
    zone.definir_stock(["MGEHR 2020-3", "OUTIL-FANTOME 9999"])
    assert zone.stock() == {"MGEHR 2020-3"}
    # le menu Affichage masque et rouvre l'atelier, et le réglage suit
    assert win.act_zone_atelier.isChecked() and win.zone_atelier.isVisible()
    win.act_zone_atelier.setChecked(False)
    assert not win.zone_atelier.isVisible() and win.reglages.get_bool("atelier.visible", True) is False
    win.act_zone_atelier.setChecked(True)
    assert win.zone_atelier.isVisible() and win.reglages.get_bool("atelier.visible", False) is True
    zone.definir_stock([])


def test_volets_de_l_atelier(fenetre):
    win = fenetre
    win.act_zone_atelier.setChecked(True)
    volets = win.zone_atelier.volets
    # usinage et tourelle à gauche, plaquettes à droite
    assert list(volets) == ["usinage", "tourelle", "outils", "plaquettes"]
    assert volets["usinage"].bandeau_a_gauche and not volets["plaquettes"].bandeau_a_gauche
    # replier un volet le réduit à son bandeau et cache son contenu ; déplier le rend
    outils = volets["outils"]
    outils.definir_deploye(True)
    QTest.qWait(10)
    assert outils.contenu.isVisible() and outils.maximumWidth() > 200
    outils.basculer()
    QTest.qWait(10)
    from ctgraph.ui.volet_lateral import LARGEUR_BANDEAU
    assert not outils.contenu.isVisible() and outils.maximumWidth() == LARGEUR_BANDEAU
    assert win.reglages.get_bool("volet.outils", True) is False      # l'état est mémorisé
    assert not win.actions_volets["outils"].isChecked()              # et le menu suit
    # le menu commande aussi le volet
    win.actions_volets["tourelle"].setChecked(True)
    QTest.qWait(10)
    assert volets["tourelle"].est_deploye() and win.zone_tourelle.isVisible()
    assert win.reglages.get_bool("volet.tourelle", False) is True
    # un clic sur le bandeau bascule
    QTest.mouseClick(volets["tourelle"].bandeau, Qt.MouseButton.LeftButton)
    QTest.qWait(10)
    assert not volets["tourelle"].est_deploye()
    for cle in volets:
        win.actions_volets[cle].setChecked(cle == "outils")


def test_volet_usinage_gamme_et_trajectoires(fenetre, tmp_path):
    from ctgraph.montage import Montage
    from ctgraph.ui.vue_esquisse import ROLE_GENRE
    from ctgraph.usinage import TypeSequence
    win, vue = fenetre, fenetre.vue
    win.definir_montage(Montage())              # pas le montage laissé par un autre test
    rectangle(win, 40.0, 20.0)
    zone = win.zone_usinage
    # le profil d'usinage se tire des contours fermés résolus, jamais d'une copie du dessin
    assert win.profil_usinage().rayon_maxi == pytest.approx(20.0, abs=0.5)   # tracé à la souris
    assert len(zone.gamme) == 0 and zone.sequence_courante() is None
    assert vue.trajectoire is None and "Aucune séquence" in zone.lbl_etat.text()

    # une ébauche ajoutée se choisit d'elle-même, et sa trajectoire se dessine aussitôt
    ebauche = zone.ajouter(TypeSequence.EBAUCHE)
    assert zone.sequence_courante() is ebauche and win._modifie
    assert vue.trajectoire is not None and vue.trajectoire.sequence_id == ebauche.id
    assert any(it.data(ROLE_GENRE) == "trajectoire" for it in vue._items)
    # du brut Ø 60 au Ø 40 plus la surépaisseur, par passes de 2 mm au rayon
    passes = win.trajectoire_de(ebauche).nb_passes()
    assert passes == 5 and zone.liste.topLevelItem(1).text(3) == "5"   # la ligne 0 est le brut
    assert "5 passe(s)" in zone.lbl_etat.text()

    # changer une cote du brut recalcule les trajectoires : rien n'est figé
    win._demander_valeur = lambda libelle, unite, defaut, mini: (80.0, True)
    win.editer_brut("diametre")
    assert win.trajectoire_de(ebauche).nb_passes() > passes
    assert int(zone.liste.topLevelItem(1).text(3)) == win.trajectoire_de(ebauche).nb_passes()

    # le formulaire règle la séquence choisie, et la vue suit
    zone.profondeur.setValue(4.0)
    zone.poste.setValue(11)
    assert ebauche.profondeur_passe == 4.0 and ebauche.poste == 11
    assert zone.liste.topLevelItem(1).text(2) == "T11"
    assert zone.lbl_outil.text().startswith(win.zone_tourelle.tourelle.poste(11).libelle())
    assert vue.trajectoire.sequence_id == ebauche.id

    # une finition ne prend ni passes ni surépaisseur : elle suit le profil fini, et le formulaire
    # ne montre que les réglages qui comptent pour le type choisi
    finition = zone.ajouter(TypeSequence.FINITION)
    assert zone.profondeur.isHidden() and zone.surepaisseur.isHidden()
    assert not zone.garde.isHidden() and not zone.z_fin.isHidden()
    assert win.trajectoire_de(finition).nb_passes() == 1
    assert [s.id for s in win.gamme] == [ebauche.id, finition.id]

    # l'ordre d'usinage se change, et la case décoche une séquence sans la retirer de la gamme
    assert zone.deplacer(-1) and [s.id for s in win.gamme] == [finition.id, ebauche.id]
    zone.liste.topLevelItem(1).setCheckState(0, Qt.CheckState.Unchecked)
    assert not finition.active and len(win.gamme.actives()) == 1

    # la gamme fait partie de la pièce enregistrée
    chemin = tmp_path / "gamme.ctg"
    assert win._ecrire(str(chemin))
    win.nouveau()
    assert len(win.gamme) == 0 and vue.trajectoire is None
    assert win.ouvrir_fichier(str(chemin))
    assert [s.type for s in win.gamme] == [TypeSequence.FINITION, TypeSequence.EBAUCHE]
    assert win.zone_usinage.liste.topLevelItemCount() == 3      # le brut et les deux opérations
    assert not win.gamme.sequences[0].active and win.gamme.sequences[1].poste == 11

    # choisir une ligne montre sa trajectoire ; la supprimer la retire du dessin
    win.zone_usinage.liste.setCurrentItem(win.zone_usinage.liste.topLevelItem(2))
    assert vue.trajectoire.sequence_id == win.gamme.sequences[1].id
    win.zone_usinage.supprimer()
    win.zone_usinage.supprimer()
    assert len(win.gamme) == 0 and vue.trajectoire is None
    assert not any(it.data(ROLE_GENRE) == "trajectoire" for it in vue._items)


def test_volet_usinage_curseur_matiere_et_ordre(fenetre):
    from PySide6.QtCore import QPointF
    from PySide6.QtGui import QDropEvent
    from ctgraph.montage import Montage
    from ctgraph.ui.transfert import MIME_SEQUENCE, charger, lire
    from ctgraph.usinage import TypeSequence
    win, vue = fenetre, fenetre.vue
    win.definir_montage(Montage())
    rectangle(win, 40.0, 20.0)
    zone = win.zone_usinage
    dressage = zone.ajouter(TypeSequence.DRESSAGE)
    ebauche = zone.ajouter(TypeSequence.EBAUCHE)

    # la liste est le curseur : une ligne par étape, la première étant le brut
    assert zone.liste.topLevelItemCount() == 3 and zone.liste.topLevelItem(0).text(1) == "Brut"
    assert zone.etape() == 2 and zone.sequence_courante() is ebauche
    zone.liste.setCurrentItem(zone.liste.topLevelItem(1))
    assert zone.etape() == 1 and zone.sequence_courante() is dressage

    # étape 0 : le brut, rien d'enlevé, aucune trajectoire
    zone.definir_etape(0)
    assert zone.sequence_courante() is None and vue.trajectoire is None
    assert "brut" in zone.lbl_etat.text().lower()
    assert vue.matiere and not vue.matiere_enlevee
    assert max(x for poly in vue.matiere for _, x in poly) == pytest.approx(win.montage.rayon_brut())

    # étape 1 : le dressage a emporté la surépaisseur de face, devant Z = 0
    zone.definir_etape(1)
    assert zone.sequence_courante() is dressage and vue.trajectoire is not None
    assert vue.matiere_enlevee and max(z for poly in vue.matiere_enlevee for z, _ in poly) > 0.0
    # les lignes qui suivent l'étape montrée sont grisées, celles d'avant non
    assert zone.liste.topLevelItem(1).foreground(1) != zone.liste.topLevelItem(2).foreground(1)

    # étape 2 : l'ébauche a emporté la matière au diamètre, du brut jusqu'au profil
    zone.definir_etape(2)
    enleve = vue.matiere_enlevee
    assert enleve and max(x for poly in enleve for _, x in poly) == pytest.approx(win.montage.rayon_brut())
    assert min(x for poly in enleve for _, x in poly) < win.montage.rayon_brut()

    # la liste est une source de glisser : une ligne emporte sa séquence
    index = zone.liste.indexFromItem(zone.liste.topLevelItem(2))
    assert zone.liste.dragEnabled()
    type_mime, charge = lire(zone.liste.model().mimeData([index]))
    assert type_mime == MIME_SEQUENCE and charge.startswith(str(ebauche.id))

    def lacher_au_dessus_de(rang: int, sequence) -> bool:
        rect = zone.liste.visualItemRect(zone.liste.topLevelItem(rang))
        point = QPointF(rect.center().x(), rect.top() + 1)
        mime = charger(MIME_SEQUENCE, f"{sequence.id} {sequence.libelle()}")   # à garder vivant
        ev = QDropEvent(point, Qt.DropAction.MoveAction, mime, Qt.MouseButton.LeftButton,
                        Qt.KeyboardModifier.NoModifier)
        assert zone.liste.rang_sous(point.toPoint()) == rang
        zone.liste.dropEvent(ev)
        QTest.qWait(10)        # la liste se reconstruit après la sortie de l'événement
        return ev.isAccepted()

    # lâchée au-dessus de la première opération, l'ébauche passe devant le dressage
    assert lacher_au_dessus_de(1, ebauche)
    assert [s.id for s in win.gamme] == [ebauche.id, dressage.id]
    assert zone.liste.topLevelItem(1).text(1) == ebauche.libelle()
    assert zone.sequence_courante() is ebauche and zone.etape() == 1

    # lâchée là où elle est déjà : rien ne bouge
    assert lacher_au_dessus_de(1, ebauche)
    assert [s.id for s in win.gamme] == [ebauche.id, dressage.id]

    # une opération ajoutée se pose juste après l'étape montrée, pas à la fin
    zone.definir_etape(1)
    gorge = zone.ajouter(TypeSequence.GORGE)
    assert [s.id for s in win.gamme] == [ebauche.id, gorge.id, dressage.id]
    assert zone.sequence_courante() is gorge and zone.etape() == 2
    zone.definir_etape(0)
    tete = zone.ajouter(TypeSequence.CENTRAGE)
    assert [s.id for s in win.gamme][0] == tete.id and zone.etape() == 1

    # gamme vide : il ne reste que la ligne du brut, et le dessin redevient celui de l'esquisse seule
    while zone.supprimer():
        pass
    assert not vue.matiere and not vue.matiere_enlevee
    assert zone.liste.topLevelItemCount() == 1 and zone.etape() == 0


def test_gamme_type_et_cote_de_percage(fenetre):
    from ctgraph.montage import Montage
    from ctgraph.tourelle import Tourelle
    from ctgraph.ui.vue_esquisse import ROLE_GENRE, ROLE_ID, Etiquette
    from ctgraph.usinage import TypeSequence
    win, vue = fenetre, fenetre.vue
    win.definir_montage(Montage())
    rectangle(win, 40.0, 20.0)
    zone = win.zone_usinage
    tourelle = Tourelle()
    tourelle.garnir(3, "SDJCR 2020 K11", "DCMT 11T308")      # extérieur positif : la finition
    tourelle.garnir(11, "PCLNR 2020 K12", "CNMG 120408")     # extérieur négatif : dressage et ébauche
    win.zone_tourelle.definir_tourelle(tourelle)

    # la gamme type pose les neuf étapes dans l'ordre, et affecte les postes que la tourelle porte
    assert zone.proposer_gamme_type(confirmer=False)
    assert [s.type for s in win.gamme][:4] == [TypeSequence.DRESSAGE, TypeSequence.CENTRAGE,
                                               TypeSequence.PERCAGE, TypeSequence.EBAUCHE]
    assert [s.type for s in win.gamme][-1] == TypeSequence.TRONCONNAGE
    assert win.gamme.sequences[0].poste == 11 and win.gamme.sequences[3].poste == 11
    assert next(s for s in win.gamme if s.type == TypeSequence.FINITION).poste == 3
    assert next(s for s in win.gamme if s.type == TypeSequence.PERCAGE).poste == 0   # pas de foret monté
    # elle part sur le brut, et la liste montre toutes ses étapes
    assert zone.etape() == 0 and zone.liste.topLevelItemCount() == len(win.gamme) + 1
    assert zone.liste.minimumHeight() >= len(win.gamme) * zone.liste.sizeHintForRow(0)

    # le curseur d'étape longe la liste : sa poignée est en face de la ligne choisie, et la tirer change
    # l'étape montrée, liste et curseur étant la même chose
    from ctgraph.ui.zone_usinage import CurseurEtape
    assert zone.curseur.width() == CurseurEtape.LARGEUR and zone.curseur.parent() is not None
    y_ligne_2 = zone.curseur._y_de(2)
    zone.curseur._viser(y_ligne_2)
    assert zone.etape() == 2 and zone.curseur._rang_a(y_ligne_2) == 2
    zone.definir_etape(0)

    # le perçage : sa profondeur est une cote portée sur le dessin, et ce qu'il enlève y ressort
    percage = next(s for s in win.gamme if s.type == TypeSequence.PERCAGE)
    percage.active = True
    percage.z_fin = -30.0
    zone._choisir(percage.id)
    win._apres_reglage_sequence()
    # le foret se choisit dans un champ de l'opération, et sa pointe donne la forme du fond
    assert zone.formulaire.labelForField(zone.foret).text() == "Foret"
    assert zone.foret.currentData() == percage.foret == "Foret Ø 10"
    assert not percage.outil_de_percage().a_centrer
    zone.foret.setCurrentIndex(zone.foret.findData("Foret Ø 13"))
    assert percage.foret == "Foret Ø 13" and percage.diametre_outil == 13.0
    creux = max(x for poly in vue.matiere_enlevee for _, x in poly if x < 10.0)
    assert creux == pytest.approx(6.5)                       # le trou est bien au Ø du foret choisi
    cote = next(it for it in vue._items
                if isinstance(it, Etiquette) and it.data(ROLE_GENRE) == "cote_sequence")
    # la profondeur se compte depuis la surface percée — la face dressée, pas le bout du brut
    assert win.surface_travaillee(percage) == pytest.approx(0.0, abs=0.3)
    assert win.montage.z_brut_avant() > 1.0
    assert cote.texte == "P 30" and cote.data(ROLE_ID) == "profondeur"
    assert vue.matiere_enlevee and min(x for poly in vue.matiere_enlevee for _, x in poly) == 0.0

    # la cote se règle comme celles du brut : à la molette, et au double-clic
    assert win.ajuster_valeur_sequence("profondeur", 1, False) == "P 31"
    assert percage.z_fin == pytest.approx(-31.0)
    win._demander_valeur = lambda libelle, unite, defaut, mini: (50.0, True)
    win.editer_valeur_sequence("profondeur")
    assert percage.z_fin == pytest.approx(-50.0) and win._modifie
    # la cote redessinée porte la nouvelle valeur
    assert next(it.texte for it in vue._items
                if isinstance(it, Etiquette) and it.data(ROLE_GENRE) == "cote_sequence") == "P 50"

    while zone.supprimer():
        pass
    win.zone_tourelle.definir_tourelle(Tourelle())


def test_alesage_attrape_a_la_souris(fenetre):
    from ctgraph.montage import Montage
    from ctgraph.ui.vue_esquisse import ROLE_GENRE, ROLE_ID
    from ctgraph.usinage import TypeSequence
    win, vue = fenetre, fenetre.vue
    win.definir_montage(Montage())
    rectangle(win, 40.0, 20.0)
    zone = win.zone_usinage
    alesage = zone.ajouter(TypeSequence.ALESAGE)
    assert alesage.libelle() == "Alésage Ø 20"        # la cote maîtresse est dans le nom

    # la zone à aléser porte ses prises : trois arêtes, deux coins, et son corps
    poignees = {it.data(ROLE_ID) for it in vue._items if it.data(ROLE_GENRE) == "poignee_alesage"}
    assert poignees == {"face", "fond", "paroi", "coin_face", "coin_fond", "corps"}
    # sans dressage avant lui, l'alésage part du bout du brut : c'est la matière qu'il trouve
    assert vue.alesage_montre() == (pytest.approx(win.montage.z_brut_avant(), abs=0.3), -20.0, 5.0, 10.0)

    # pousser la paroi change le diamètre ; pousser le fond change la profondeur
    assert win.deplacer_alesage("paroi", -10.0, 12.5)
    assert alesage.diametre_fond == pytest.approx(25.0)
    assert win.deplacer_alesage("fond", -32.0, 0.0)
    assert alesage.z_fin == pytest.approx(-32.0)
    # un coin pousse les deux à la fois
    assert win.deplacer_alesage("coin_fond", -40.0, 7.0)
    assert alesage.z_fin == pytest.approx(-40.0) and alesage.diametre_fond == pytest.approx(14.0)
    # jamais plus petit que le trou de départ, ni retourné
    assert win.deplacer_alesage("paroi", 0.0, 1.0)
    assert alesage.diametre_fond > alesage.diametre_outil
    face_avant = alesage.z_debut if alesage.z_debut is not None else win.surface_travaillee(alesage)
    assert win.deplacer_alesage("fond", face_avant + 50.0, 0.0)
    assert alesage.z_fin < face_avant

    # le corps déplace la zone entière le long de l'axe, sans changer sa longueur
    alesage.z_debut, alesage.z_fin, alesage.diametre_fond = -5.0, -35.0, 20.0
    assert win.deplacer_alesage("corps", -12.0, 0.0, ancre=(-10.0, 0.0))
    assert (alesage.z_debut, alesage.z_fin) == (pytest.approx(-7.0), pytest.approx(-37.0))

    # une séquence qui n'est pas un alésage n'offre aucune prise
    zone.ajouter(TypeSequence.EBAUCHE)
    assert vue.alesage_montre() is None
    assert not any(it.data(ROLE_GENRE) == "poignee_alesage" for it in vue._items)
    assert not win.deplacer_alesage("paroi", 0.0, 5.0)

    while zone.supprimer():
        pass


def test_volet_usinage_un_formulaire_par_type(fenetre):
    from ctgraph.usinage import TypeSequence
    from ctgraph.usinage.sequences import CHAMPS_SEQUENCE, LIBELLES_CHAMPS
    win = fenetre
    zone = win.zone_usinage
    assert set(zone.boutons_ajout) == set(TypeSequence)        # un bouton d'ajout par opération
    for type_ in TypeSequence:
        s = zone.ajouter(type_)
        attendus = set(CHAMPS_SEQUENCE[type_])
        montres = {cle for cle, widget in zone.champs.items()
                   if not widget.isHidden() and cle not in ("vitesse_maxi", "avance")}
        assert montres == attendus, type_
        # filetage, perçage et centrage tournent à broche fixe : pas de limitation de broche à régler,
        # et l'avance d'un filetage est son pas
        assert zone.vitesse_maxi.isHidden() == s.vitesse_fixe()
        assert zone.avance.isHidden() == (type_ == TypeSequence.FILETAGE)
        # chaque type nomme ses champs pour ce qu'ils y sont : « Fond du trou », pas « Z de fin »
        for cle, intitule in LIBELLES_CHAMPS.get(type_, {}).items():
            assert zone.formulaire.labelForField(zone.champs[cle]).text() == intitule
    for s in list(win.gamme.sequences):
        win.gamme.supprimer(s.id)
    zone.rafraichir()


def test_zone_tourelle(fenetre):
    from PySide6.QtCore import QPoint
    win = fenetre
    win.act_zone_atelier.setChecked(True)
    win.actions_volets["tourelle"].setChecked(True)
    QTest.qWait(20)
    zone = win.zone_tourelle
    from ctgraph.tourelle import Tourelle
    zone.definir_tourelle(Tourelle())          # pas la garniture laissée par une autre séance
    t = zone.tourelle
    assert t.nb_postes == 12 and t.diametre_queue == 30.0
    # la moitié des postes sont transversaux en périphérie, l'autre moitié axiale, alternés
    assert [t.poste(n).implantation for n in (1, 2, 3, 4)] == ["transversal", "axial"] * 2
    assert sum(1 for n in t.postes() if t.poste(n).implantation == "transversal") == 6
    zone.definir_poste(1)
    assert "Poste en travail : T1" in zone.lbl_etat.text()
    # cliquer sur le logement du poste 4 (à 90°, donc à droite) le met en travail
    x, y = t.position_poste(4)
    cible = zone.vue._en_pixels(x, y)
    QTest.mouseClick(zone.vue, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
                     QPoint(int(cible.x()), int(cible.y())))
    QTest.qWait(10)
    assert t.poste_en_travail == 4 and "Poste en travail : T4" in zone.lbl_etat.text()
    # la liste montre les douze postes, le poste en travail en gras et sélectionné
    assert zone.liste.topLevelItemCount() == 12
    assert zone.liste.currentItem().text(0) == "T4" and zone.liste.currentItem().font(0).bold()
    # et elle est assez haute pour les montrer tous : pas de défilement dans la liste
    assert zone.liste.minimumHeight() >= 12 * zone.liste.sizeHintForRow(0)
    assert zone.liste.verticalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    assert zone.widgetResizable()          # c'est le volet entier qui défile, pas la liste
    win.actions_volets["tourelle"].setChecked(False)


def test_garnir_un_poste_et_ses_corrections(fenetre):
    from ctgraph.tourelle import Tourelle
    win = fenetre
    win.act_zone_atelier.setChecked(True)
    win.actions_volets["tourelle"].setChecked(True)
    QTest.qWait(20)
    zone = win.zone_tourelle
    zone.definir_tourelle(Tourelle())
    t = zone.tourelle
    # poste 1, transversal : le choix des porte-plaquettes se borne aux queues carrées
    zone.definir_poste(1)
    choix = [zone.porte_plaquette.itemData(i) for i in range(zone.porte_plaquette.count())]
    assert "SCLCR 2020 K09" in choix and "S16Q-SCLCR 09" not in choix
    zone.porte_plaquette.setCurrentIndex(zone.porte_plaquette.findData("SCLCR 2020 K09"))
    zone.plaquette.setCurrentIndex(zone.plaquette.findData("CCMT 09T308"))
    poste = t.poste(1)
    assert poste.est_garni() and poste.libelle() == "SCLCR 2020 K09 + CCMT 09T308"
    assert poste.correcteur.rayon_bec == 0.8          # le rayon de bec suit la plaquette montée
    # les corrections se saisissent et se lisent dans la liste
    zone.correcteur.setValue(1)
    zone.corr_x.setValue(-12.345)
    zone.corr_z.setValue(84.5)
    zone.orientation.setCurrentIndex(zone.orientation.findData(3))
    c = poste.correcteur
    assert (c.numero, c.x, c.z, c.orientation) == (1, -12.345, 84.5, 3)
    assert "D1" in c.texte() and "X -12.345" in c.texte() and "C3" in c.texte()
    ligne = next(zone.liste.topLevelItem(i) for i in range(12) if zone.liste.topLevelItem(i).text(0) == "T1")
    assert ligne.text(2) == "SCLCR 2020 K09" and ligne.text(3) == "CCMT 09T308" and "D1" in ligne.text(4)
    # un poste axial n'accepte que les queues cylindriques
    zone.definir_poste(2)
    assert t.poste(2).implantation == "axial"
    choix = [zone.porte_plaquette.itemData(i) for i in range(zone.porte_plaquette.count())]
    assert "S16Q-SCLCR 09" in choix and "SCLCR 2020 K09" not in choix
    # changer l'implantation d'un poste change ce qu'il peut recevoir
    zone.implantation.setCurrentIndex(zone.implantation.findData("transversal"))
    assert t.poste(2).implantation == "transversal"
    assert "SCLCR 2020 K09" in [zone.porte_plaquette.itemData(i) for i in range(zone.porte_plaquette.count())]
    # la garniture est mémorisée et se relit
    import json
    relu = Tourelle.from_dict(json.loads(str(win.reglages.get("tourelle"))))
    assert relu.poste(1).porte_plaquette == "SCLCR 2020 K09" and relu.poste(1).correcteur.numero == 1
    assert relu.poste(2).implantation == "transversal"
    # vider rend le poste libre
    zone.definir_poste(1)
    zone._vider()
    assert not t.poste(1).est_garni() and t.poste(1).libelle() == "libre"
    assert t.poste(1).correcteur.texte() == "—"
    zone.definir_tourelle(Tourelle())
    win.actions_volets["tourelle"].setChecked(False)


def test_zone_plaquettes(fenetre):
    from ctgraph.plaquettes import CATALOGUE, FAMILLES
    win = fenetre
    win.act_zone_atelier.setChecked(True)
    win.actions_volets["plaquettes"].setChecked(True)
    QTest.qWait(20)
    zone = win.zone_plaquettes
    zone.definir_stock([])

    def lignes():
        out = []
        for i in range(zone.arbre.topLevelItemCount()):
            parent = zone.arbre.topLevelItem(i)
            out += [parent.child(j) for j in range(parent.childCount())]
        return out

    assert zone.arbre.topLevelItemCount() == len(FAMILLES) and len(lignes()) == len(CATALOGUE)
    it = next(x for x in lignes() if x.text(0) == "CNMG 120408")
    assert [it.text(c) for c in range(5)] == ["CNMG 120408", "0°", "12,9", "4,76", "0,8"]
    assert not it.icon(0).isNull() and "ISO 1832" in it.toolTip(0)
    # choisir une ligne dessine la plaquette cotée
    assert zone.dessin.plaquette is None
    zone.arbre.setCurrentItem(it)
    QTest.qWait(10)
    assert zone.dessin.plaquette is not None and zone.dessin.plaquette.designation == "CNMG 120408"
    # les cotes sont portées sur les éléments du dessin, avec les valeurs de la plaquette choisie
    assert zone.dessin.cotes_portees() == ["l 12,9", "IC 12,7", "r 0,8", "s 4,76", "α 0°"]
    assert "deux faces utilisables" in zone.dessin.legende()[0]
    # une plaquette ronde est cotée par son diamètre, une barrette de gorge par sa largeur
    zone.arbre.setCurrentItem(next(x for x in lignes() if x.text(0) == "RCMT 10T300"))
    assert zone.dessin.cotes_portees()[:2] == ["Ø 10", "r 5"]
    zone.arbre.setCurrentItem(next(x for x in lignes() if x.text(0) == "MGMN 300-G"))
    assert zone.dessin.cotes_portees()[:2] == ["largeur 3", "r 0,2"]
    zone.arbre.setCurrentItem(it)
    # le filtre et la case « en stock » marchent comme dans le stock d'outils
    zone.filtre.setText("ronde")
    assert lignes() and all("RNMG" in x.text(0) or "RCMT" in x.text(0) for x in lignes())
    zone.filtre.setText("")
    it = next(x for x in lignes() if x.text(0) == "CCMT 09T304")
    it.setCheckState(0, Qt.CheckState.Checked)
    assert zone.stock() == {"CCMT 09T304"}
    assert win.reglages.get("plaquettes.stock") == ["CCMT 09T304"]
    zone.case_stock.setChecked(True)
    assert [x.text(0) for x in lignes()] == ["CCMT 09T304"]
    zone.case_stock.setChecked(False)
    zone.definir_stock([])
    win.actions_volets["plaquettes"].setChecked(False)


def test_glisser_deposer_sur_la_tourelle(fenetre):
    from PySide6.QtCore import QPointF
    from PySide6.QtGui import QDropEvent
    from ctgraph.tourelle import Tourelle
    from ctgraph.ui.transfert import MIME_PLAQUETTE, MIME_PORTE_PLAQUETTE, charger, lire
    from ctgraph.ui.vue_esquisse import ROLE_GENRE  # noqa: F401
    win = fenetre
    win.act_zone_atelier.setChecked(True)
    for cle in win.zone_atelier.volets:
        win.actions_volets[cle].setChecked(True)
    QTest.qWait(20)
    zone = win.zone_tourelle
    zone.definir_tourelle(Tourelle())
    t = zone.tourelle

    def ligne(arbre, designation):
        for i in range(arbre.topLevelItemCount()):
            parent = arbre.topLevelItem(i)
            for j in range(parent.childCount()):
                if parent.child(j).text(0) == designation:
                    return parent.child(j)
        raise AssertionError(designation)

    # une ligne du stock d'outils emporte sa désignation ; celle des plaquettes aussi, dans son format.
    # On passe par le modèle, comme Qt le fait pendant un vrai glisser : les drapeaux de la ligne comptent.
    for arbre, designation, attendu in ((win.zone_outils.arbre, "SCLCR 2020 K09", MIME_PORTE_PLAQUETTE),
                                        (win.zone_plaquettes.arbre, "CCMT 09T308", MIME_PLAQUETTE)):
        it = ligne(arbre, designation)
        assert arbre.dragEnabled()
        assert it.flags() & Qt.ItemFlag.ItemIsDragEnabled      # sans ce drapeau, rien ne se tire
        index = arbre.indexFromItem(it)
        assert arbre.model().flags(index) & Qt.ItemFlag.ItemIsDragEnabled
        assert lire(arbre.model().mimeData([index])) == (attendu, designation)
        assert lire(arbre.mimeData([it])) == (attendu, designation)

    # ce que chaque poste accepte : les plaquettes partout, les outils selon l'implantation
    assert zone.accepte_depot(1, MIME_PORTE_PLAQUETTE, "SCLCR 2020 K09")        # poste 1 transversal
    assert not zone.accepte_depot(1, MIME_PORTE_PLAQUETTE, "S16Q-SCLCR 09")     # queue cylindrique
    assert zone.accepte_depot(2, MIME_PORTE_PLAQUETTE, "S16Q-SCLCR 09")         # poste 2 axial
    assert not zone.accepte_depot(2, MIME_PORTE_PLAQUETTE, "SCLCR 2020 K09")
    assert zone.accepte_depot(1, MIME_PLAQUETTE, "CCMT 09T308")
    assert not zone.accepte_depot(0, MIME_PLAQUETTE, "CCMT 09T308")
    assert not zone.accepte_depot(1, MIME_PLAQUETTE, "PLAQUETTE INCONNUE")

    def deposer(cible, point, type_mime, designation):
        m = charger(type_mime, designation)
        ev = QDropEvent(QPointF(point), Qt.DropAction.CopyAction, m, Qt.MouseButton.LeftButton,
                        Qt.KeyboardModifier.NoModifier)
        cible.dropEvent(ev)
        QTest.qWait(10)        # le tableau garnit après la sortie de l'événement
        return ev.isAccepted()

    def survol(cible, point, type_mime, designation):
        from PySide6.QtGui import QDragMoveEvent
        m = charger(type_mime, designation)
        ev = QDragMoveEvent(QPointF(point), Qt.DropAction.CopyAction, m, Qt.MouseButton.LeftButton,
                            Qt.KeyboardModifier.NoModifier)
        cible.dragMoveEvent(ev)
        return ev.isAccepted()

    # dépôt sur le schéma : le logement du poste 3 (transversal)
    x, y = t.position_poste(3)
    cible = zone.vue._en_pixels(x, y)
    # le survol dit si le dépôt est possible, et entoure le poste visé
    assert survol(zone.vue, cible, MIME_PORTE_PLAQUETTE, "SDJCR 2020 K11")
    assert zone.vue._survol == 3
    assert not survol(zone.vue, cible, MIME_PORTE_PLAQUETTE, "S16Q-SCLCR 09")
    assert zone.vue._survol == 0
    assert deposer(zone.vue, cible, MIME_PORTE_PLAQUETTE, "SDJCR 2020 K11")
    assert t.poste(3).porte_plaquette == "SDJCR 2020 K11" and t.poste_en_travail == 3
    # la plaquette se dépose sur le même poste sans effacer le porte-plaquette
    assert deposer(zone.vue, cible, MIME_PLAQUETTE, "DCMT 11T308")
    assert t.poste(3).libelle() == "SDJCR 2020 K11 + DCMT 11T308"
    assert t.poste(3).correcteur.rayon_bec == 0.8          # le rayon de bec suit la plaquette
    # un outil à queue cylindrique sur un poste transversal : refusé, rien ne change
    assert not deposer(zone.vue, cible, MIME_PORTE_PLAQUETTE, "S16Q-SCLCR 09")
    assert t.poste(3).porte_plaquette == "SDJCR 2020 K11"

    # dépôt sur le tableau des postes : la ligne du poste 4, axial
    zone.rafraichir()
    item = next(zone.liste.topLevelItem(i) for i in range(12) if zone.liste.topLevelItem(i).text(0) == "T4")
    rect = zone.liste.visualItemRect(item)
    assert deposer(zone.liste, rect.center(), MIME_PORTE_PLAQUETTE, "S20R-SDUCR 11")
    assert t.poste(4).porte_plaquette == "S20R-SDUCR 11" and t.poste_en_travail == 4
    assert not deposer(zone.liste, rect.center(), MIME_PORTE_PLAQUETTE, "SCLCR 2020 K09")
    assert t.poste(4).porte_plaquette == "S20R-SDUCR 11"
    # un glisser étranger n'est pas accueilli
    from PySide6.QtCore import QMimeData
    etranger = QMimeData()
    etranger.setText("bonjour")
    ev = QDropEvent(QPointF(rect.center()), Qt.DropAction.CopyAction, etranger, Qt.MouseButton.LeftButton,
                    Qt.KeyboardModifier.NoModifier)
    zone.liste.dropEvent(ev)
    assert not ev.isAccepted()

    zone.definir_tourelle(Tourelle())
    for cle in win.zone_atelier.volets:
        win.actions_volets[cle].setChecked(cle == "outils")


def test_glisser_un_poste_vers_une_sequence(fenetre):
    from PySide6.QtCore import QMimeData, QPointF
    from PySide6.QtGui import QDragMoveEvent, QDropEvent
    from ctgraph.tourelle import Tourelle
    from ctgraph.ui.transfert import MIME_POSTE, charger_poste, lire
    from ctgraph.ui.zone_usinage import ROLE_ID as ROLE_ID_SEQUENCE
    from ctgraph.usinage import TypeSequence
    win = fenetre
    win.act_zone_atelier.setChecked(True)
    for cle in win.zone_atelier.volets:
        win.actions_volets[cle].setChecked(True)
    QTest.qWait(20)
    tourelle = Tourelle()
    tourelle.garnir(3, "SDJCR 2020 K11", "DCMT 11T308")
    win.zone_tourelle.definir_tourelle(tourelle)
    usinage = win.zone_usinage
    ebauche = usinage.ajouter(TypeSequence.EBAUCHE)
    finition = usinage.ajouter(TypeSequence.FINITION)

    # une ligne du tableau des postes emporte son numéro et la combinaison montée
    liste = win.zone_tourelle.liste
    it = next(liste.topLevelItem(i) for i in range(liste.topLevelItemCount())
              if liste.topLevelItem(i).data(0, Qt.ItemDataRole.UserRole) == 3)
    assert liste.dragEnabled() and it.flags() & Qt.ItemFlag.ItemIsDragEnabled
    type_mime, charge = lire(liste.model().mimeData([liste.indexFromItem(it)]))
    assert type_mime == MIME_POSTE and charge == "T3 SDJCR 2020 K11 + DCMT 11T308"

    def point_de(sequence):
        rect = usinage.liste.visualItemRect(next(
            usinage.liste.topLevelItem(i) for i in range(usinage.liste.topLevelItemCount())
            if usinage.liste.topLevelItem(i).data(0, ROLE_ID_SEQUENCE) == sequence.id))
        return QPointF(rect.center())

    def deposer(point, mime):
        ev = QDropEvent(point, Qt.DropAction.CopyAction, mime, Qt.MouseButton.LeftButton,
                        Qt.KeyboardModifier.NoModifier)
        usinage.liste.dropEvent(ev)
        QTest.qWait(10)        # la ligne se met à jour après la sortie de l'événement
        return ev.isAccepted()

    # déposer le poste sur la finition le lui donne, et ne touche pas à l'autre séquence
    assert deposer(point_de(finition), charger_poste(3, tourelle.poste(3).libelle()))
    assert finition.poste == 3 and ebauche.poste == 0
    assert usinage.sequence_courante() is finition and win._modifie
    assert usinage.lbl_outil.text().startswith("SDJCR 2020 K11 + DCMT 11T308")
    # le survol dit si le dépôt est possible : sur une ligne oui, dans le vide non
    def survol(point, mime):
        ev = QDragMoveEvent(point, Qt.DropAction.CopyAction, mime, Qt.MouseButton.LeftButton,
                            Qt.KeyboardModifier.NoModifier)
        usinage.liste.dragMoveEvent(ev)
        return ev.isAccepted()

    poste_7 = charger_poste(7, tourelle.poste(7).libelle())
    assert survol(point_de(ebauche), poste_7)
    # la ligne du brut n'est pas une opération : elle ne prend pas de poste
    brut = QPointF(usinage.liste.visualItemRect(usinage.liste.topLevelItem(0)).center())
    assert not survol(brut, poste_7)
    assert not deposer(point_de(ebauche), QMimeData())        # un glisser étranger n'est pas accueilli
    assert ebauche.poste == 0
    # un poste hors tourelle est refusé
    assert not usinage.affecter_poste(ebauche.id, 99) and ebauche.poste == 0
    assert usinage.affecter_poste(ebauche.id, 7) and ebauche.poste == 7

    for s in list(win.gamme.sequences):
        win.gamme.supprimer(s.id)
    usinage.rafraichir()
    win.zone_tourelle.definir_tourelle(Tourelle())
    for cle in win.zone_atelier.volets:
        win.actions_volets[cle].setChecked(cle == "outils")


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
