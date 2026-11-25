"""Tests de l'usinage : profil extérieur tiré des contours, et trajectoires des trois séquences."""
from __future__ import annotations

import pytest

from ctgraph.montage import Brut, Montage, PriseDePiece
from ctgraph.usinage import Gamme, Sequence, TypeSequence, profil_exterieur, trajectoire
from ctgraph.usinage.profil import ProfilTourne

# arbre épaulé : Ø 50 de z = 0 à z = -30, puis Ø 30 jusqu'à z = -80, contour fermé par l'axe
ARBRE = [(0.0, 0.0), (0.0, 25.0), (-30.0, 25.0), (-30.0, 15.0), (-80.0, 15.0), (-80.0, 0.0), (0.0, 0.0)]


def montage_essai() -> Montage:
    return Montage(brut=Brut(diametre=56.0), prise=PriseDePiece(depassement=100.0, surepaisseur_face=2.0))


def test_profil_exterieur_ouvre_le_contour_sur_l_axe():
    p = profil_exterieur([ARBRE])
    assert p and p.points[0] == (0.0, 0.0) and p.points[-1] == (-80.0, 0.0)
    assert (0.0, 25.0) in p.points and (-30.0, 15.0) in p.points
    # du bout de la pièce vers le mandrin : z décroissant
    assert p.z_bout == 0.0 and p.z_fond == -80.0 and p.rayon_maxi == 25.0
    assert [z for z, _ in p.points] == sorted((z for z, _ in p.points), reverse=True)
    # un contour donné dans l'autre sens donne le même profil
    assert profil_exterieur([ARBRE[::-1]]).points == p.points
    # le plus grand contour l'emporte
    petit = [(0.0, 0.0), (0.0, 2.0), (-3.0, 2.0), (-3.0, 0.0), (0.0, 0.0)]
    assert profil_exterieur([petit, ARBRE]).points == p.points
    assert not profil_exterieur([])


def test_rayon_du_profil_et_butee_des_passes():
    p = profil_exterieur([ARBRE])
    assert p.rayon(0.0) == 25.0 and p.rayon(-10.0) == 25.0
    assert p.rayon(-30.0) == 25.0                  # l'épaulement : on garde le plus haut
    assert p.rayon(-50.0) == 15.0 and p.rayon(-80.0) == 15.0
    assert p.rayon(5.0) == 0.0                     # hors de la pièce
    # le plus grand z où la matière dépasse un rayon : au rayon 26 le profil ne dépasse nulle part
    assert p.z_matiere(26.0) is None
    assert p.z_matiere(20.0) == pytest.approx(0.0)     # l'épaulement Ø 50 commence dès la face
    # un cône : le croisement tombe au bon endroit
    cone = ProfilTourne([(0.0, 10.0), (-20.0, 20.0)])
    assert cone.z_matiere(15.0) == pytest.approx(-10.0)
    # les tranches où une passe a le droit de couper, et jusqu'où l'ébauche doit descendre
    assert p.intervalles_sous(26.0, 0.0, -80.0) == [(0.0, -80.0)]
    assert p.intervalles_sous(20.0, 0.0, -80.0) == [pytest.approx((-30.0, -80.0))]
    assert p.intervalles_sous(10.0, 0.0, -80.0) == []
    assert p.rayon_mini(0.0, -80.0) == 15.0 and p.rayon_mini(0.0, -20.0) == 25.0


def test_decoupe_du_profil_sur_une_tranche():
    p = profil_exterieur([ARBRE])
    morceau = p.entre(-10.0, -40.0)
    assert morceau[0] == pytest.approx((-10.0, 25.0))
    assert morceau[-1] == pytest.approx((-40.0, 15.0))
    assert (-30.0, 25.0) in [(round(z, 6), round(x, 6)) for z, x in morceau]
    assert (-30.0, 15.0) in [(round(z, 6), round(x, 6)) for z, x in morceau]
    # tranche entière : on retrouve le profil, bornes comprises
    assert p.entre(10.0, -100.0)[0] == pytest.approx((0.0, 0.0))
    # tranche hors pièce : rien
    assert p.entre(50.0, 20.0) == []


def test_dressage():
    p = profil_exterieur([ARBRE])
    m = montage_essai()
    s = Sequence(id=1, type=TypeSequence.DRESSAGE, profondeur_passe=1.0, surepaisseur_face=0.0, garde=2.0)
    t = trajectoire(s, p, m)
    assert t and not t.message
    # le brut avance de 2 mm : deux passes de 1 mm jusqu'à la face finie
    assert t.nb_passes() == 2
    coupes = [q for q in t.mouvements if q.travail]
    assert min(q.z for q in coupes) == pytest.approx(0.0)        # la dernière passe tombe sur Z = 0
    assert max(q.x for q in coupes) == pytest.approx(m.rayon_brut() + s.degagement)
    assert min(q.x for q in coupes) == 0.0                        # on dresse jusqu'à l'axe
    # un tube se dresse jusqu'à son alésage
    m.brut = Brut(forme="tube", diametre=56.0, diametre_interieur=20.0)
    assert min(q.x for q in trajectoire(s, p, m).mouvements if q.travail) == pytest.approx(10.0)
    # sans montage, on le dit
    assert trajectoire(s, p, None).message


def test_ebauche_paraxiale():
    p = profil_exterieur([ARBRE])
    m = montage_essai()
    s = Sequence(id=2, type=TypeSequence.EBAUCHE, profondeur_passe=2.0, surepaisseur=0.5, degagement=1.0)
    t = trajectoire(s, p, m)
    assert t and not t.message
    # l'ébauche descend du rayon 28 (brut) jusqu'au petit diamètre plus la surépaisseur : 15,5
    coupes = [q for q in t.mouvements if q.travail]
    assert min(q.x for q in coupes) == pytest.approx(15.5)
    assert max(q.x for q in coupes) <= 28.0 + s.degagement + 1e-9
    # la première passe, au-dessus du Ø 50, court sur toute la longueur
    assert min(q.z for q in coupes) == pytest.approx(-80.0)
    # les passes plus profondes que le Ø 50 n'entrent qu'après l'épaulement, jamais dans le fini
    for a, b in zip(t.mouvements, t.mouvements[1:]):
        if b.travail and abs(b.x - a.x) < 1e-9:                   # une passe paraxiale
            assert b.x + 1e-9 >= p.rayon_mini(max(a.z, b.z), min(a.z, b.z)) + s.surepaisseur
    passes_profondes = [q for q in coupes if q.x < 25.0]
    assert passes_profondes and max(q.z for q in passes_profondes) == pytest.approx(-30.0)
    # brut au diamètre du plus gros : il reste l'épaulement à dégager
    m.brut = Brut(diametre=50.0)
    assert trajectoire(s, p, m)
    # brut au plus petit diamètre : plus rien à faire, et on le dit
    m.brut = Brut(diametre=30.0)
    assert not trajectoire(s, p, m) and trajectoire(s, p, m).message


def test_finition_suit_le_profil():
    p = profil_exterieur([ARBRE])
    m = montage_essai()
    s = Sequence(id=3, type=TypeSequence.FINITION, garde=2.0, degagement=1.0)
    t = trajectoire(s, p, m)
    assert t and not t.message and t.nb_passes() == 1
    coupes = [(round(q.z, 6), round(q.x, 6)) for q in t.mouvements if q.travail]
    # le chemin passe par les sommets du profil, dans l'ordre, du bout vers le mandrin
    for sommet in ((0.0, 0.0), (0.0, 25.0), (-30.0, 25.0), (-30.0, 15.0)):
        assert sommet in coupes
    # la face avant se finit depuis l'axe, la face arrière non : la pièce y tient encore à la barre
    assert (-80.0, 15.0) in coupes and (-80.0, 0.0) not in coupes
    # la finition s'arrête à la face des mors, jamais dedans
    s.z_fin = -500.0
    assert min(q.z for q in trajectoire(s, p, m).mouvements) >= m.z_face_mors() - 1e-6
    # longueur de coupe : l'approche, le profil sans la face arrière (25 + 30 + 10 + 50), le dégagement
    s.z_fin = None
    assert trajectoire(s, p, m).longueur_coupe() == pytest.approx(s.garde + 115 + s.degagement, abs=0.01)
    # une étendue réduite ne finit que la tranche demandée
    s.z_debut, s.z_fin = -10.0, -40.0
    court = trajectoire(s, p, m)
    assert max(q.z for q in court.mouvements if q.travail) == pytest.approx(-10.0)
    assert min(q.z for q in court.mouvements if q.travail) == pytest.approx(-40.0)


def test_gamme_ordonnee_et_enregistree():
    g = Gamme()
    a = g.ajouter(TypeSequence.DRESSAGE, poste=1)
    b = g.ajouter(TypeSequence.EBAUCHE, poste=11)
    c = g.ajouter(TypeSequence.FINITION, poste=5, nom="Finition Ø 30")
    assert [s.id for s in g] == [a.id, b.id, c.id] and len(g) == 3
    assert c.libelle() == "Finition Ø 30" and a.libelle() == "Dressage de face"
    assert "Poste 11" in b.description()
    # l'ordre se change, et on ne sort pas des bornes
    assert g.deplacer(c.id, -1) and [s.id for s in g] == [a.id, c.id, b.id]
    assert not g.deplacer(a.id, -1) and not g.deplacer(b.id, 1)
    assert not g.deplacer(999, 1)
    # une séquence désactivée reste dans la gamme mais sort des actives
    b.active = False
    assert len(g.actives()) == 2 and g.sequence(b.id) is b
    # aller-retour JSON
    g2 = Gamme.from_dict(g.to_dict())
    assert g2.to_dict() == g.to_dict()
    assert [s.type for s in g2] == [s.type for s in g]
    assert g2.sequence(c.id).nom == "Finition Ø 30" and not g2.sequence(b.id).active
    # un nouvel ajout ne réutilise pas un identifiant
    assert g2.ajouter(TypeSequence.EBAUCHE).id not in [s.id for s in g]
    assert g.supprimer(a.id) and not g.supprimer(a.id) and len(g) == 2
    assert Gamme.from_dict(None).to_dict() == Gamme().to_dict()
