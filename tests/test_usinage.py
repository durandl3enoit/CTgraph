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


def test_gorge_plongees_cote_a_cote():
    p = profil_exterieur([ARBRE])
    m = montage_essai()
    s = Sequence(id=4, type=TypeSequence.GORGE, largeur_outil=3.0, largeur=8.0, diametre_fond=20.0,
                 profondeur_passe=2.0, surepaisseur=0.0, garde=2.0, degagement=1.0, z_debut=-10.0)
    t = trajectoire(s, p, m)
    assert t and not t.message
    coupes = [q for q in t.mouvements if q.travail]
    # la gorge se creuse dans le Ø 50 : du rayon 25 au rayon 10
    assert max(q.x for q in coupes) < 25.0 and min(q.x for q in coupes) == pytest.approx(10.0)
    # le coin droit de l'outil balaie du bord droit au bord gauche plus la largeur de l'outil
    zs = sorted({round(q.z, 6) for q in coupes})
    assert zs[-1] == pytest.approx(-10.0) and zs[0] == pytest.approx(-15.0)
    assert all(a - b <= s.largeur_outil * 0.8 + 1e-9 for a, b in zip(zs[1:], zs))   # pas de pont oublié
    # chaque plongée descend par passes : 25 -> 10 à 2 mm, soit huit entrées en matière par position
    assert t.nb_passes() == 8 * len(zs)
    # une gorge sans fond donné, ou plus profonde que la matière, le dit au lieu de couper
    assert trajectoire(Sequence(id=4, type=TypeSequence.GORGE, z_debut=-10.0), p, m).message
    s.diametre_fond = 60.0
    assert not trajectoire(s, p, m) and "déjà au diamètre" in trajectoire(s, p, m).message


def test_tronconnage_derriere_la_piece():
    p = profil_exterieur([ARBRE])
    m = montage_essai()
    s = Sequence(id=5, type=TypeSequence.TRONCONNAGE, largeur_outil=3.0, profondeur_passe=5.0,
                 surepaisseur=0.0, garde=2.0, degagement=1.0)
    t = trajectoire(s, p, m)
    assert t and not t.message
    coupes = [q for q in t.mouvements if q.travail]
    # sans Z donné, on tronçonne au fond de la pièce, et l'outil mord dans la barre : rayon du brut
    assert {round(q.z, 6) for q in coupes} == {-80.0}
    assert max(q.x for q in coupes) < m.rayon_brut() and min(q.x for q in coupes) == 0.0
    # jusqu'à un diamètre, pour laisser la pièce tenir
    s.diametre_fond = 10.0
    assert min(q.x for q in trajectoire(s, p, m).mouvements if q.travail) == pytest.approx(5.0)
    # dans les mors, on refuse
    s.z_debut = m.z_face_mors() - 1.0
    assert not trajectoire(s, p, m) and "mors" in trajectoire(s, p, m).message


def test_filetage_passes_de_plus_en_plus_fines():
    p = profil_exterieur([ARBRE])
    m = montage_essai()
    s = Sequence(id=6, type=TypeSequence.FILETAGE, pas=2.0, profondeur_passe=0.3, garde=2.0,
                 degagement=1.0, z_debut=-35.0, z_fin=-70.0)
    t = trajectoire(s, p, m)
    assert t and not t.message
    # le filet se taille sur le Ø 30 ; sa profondeur suit le profil ISO métrique
    hauteur = s.profondeur_filet()
    assert hauteur == pytest.approx(0.6134 * 2.0)
    fonds = sorted({round(q.x, 6) for q in t.mouvements if q.travail})
    assert t.nb_passes() == len(fonds) == 5
    assert fonds[0] == pytest.approx(15.0 - hauteur)       # la dernière passe tombe au fond du filet
    assert fonds[-1] < 15.0
    # les passes se resserrent : la première est la plus grosse
    ecarts = [b - a for a, b in zip(fonds, fonds[1:])]
    assert all(a <= b + 1e-9 for a, b in zip(ecarts, ecarts[1:]))
    # chaque passe court sur toute la longueur du filet
    assert min(q.z for q in t.mouvements if q.travail) == pytest.approx(-70.0)
    # sans Z de fin ni pas, on le dit
    assert trajectoire(Sequence(id=6, type=TypeSequence.FILETAGE), p, m).message
    assert trajectoire(Sequence(id=6, type=TypeSequence.FILETAGE, pas=0.0, z_fin=-70.0), p, m).message


def test_percage_dans_l_axe_avec_debourrage():
    p = profil_exterieur([ARBRE])
    m = montage_essai()
    s = Sequence(id=7, type=TypeSequence.PERCAGE, diametre_outil=12.0, profondeur_passe=10.0,
                 garde=2.0, z_fin=-45.0)
    t = trajectoire(s, p, m)
    assert t and not t.message
    coupes = [q for q in t.mouvements if q.travail]
    assert all(q.x == 0.0 for q in t.mouvements)                 # tout se passe sur l'axe
    # du bout du brut (z = 2) au fond du trou, par tranches de 10 mm : cinq descentes
    assert t.nb_passes() == 5 and min(q.z for q in coupes) == pytest.approx(-45.0)
    # entre deux descentes, l'outil ressort complètement
    assert max(q.z for q in t.mouvements) == pytest.approx(m.z_brut_avant() + s.garde)
    # sans fond donné, on le dit
    assert trajectoire(Sequence(id=7, type=TypeSequence.PERCAGE), p, m).message


def test_gamme_ordonnee_et_enregistree():
    g = Gamme()
    a = g.ajouter(TypeSequence.DRESSAGE, poste=1)
    b = g.ajouter(TypeSequence.EBAUCHE, poste=11)
    c = g.ajouter(TypeSequence.FINITION, poste=5, nom="Finition Ø 30")
    assert [s.id for s in g] == [a.id, b.id, c.id] and len(g) == 3
    assert c.libelle() == "Finition Ø 30" and a.libelle() == "Dressage de face"
    assert "Poste T11" in b.description()
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
