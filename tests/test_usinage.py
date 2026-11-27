"""Tests de l'usinage : profil extérieur tiré des contours, et trajectoires des trois séquences."""
from __future__ import annotations

import pytest

from ctgraph.montage import Brut, Montage, PriseDePiece
from ctgraph.usinage import Gamme, Sequence, TypeSequence, profil_exterieur, profil_interieur, trajectoire
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


def test_profil_exterieur_d_une_piece_percee():
    """Un contour qui ne touche jamais l'axe est un anneau : seul son dessus est le profil extérieur."""
    # bague Ø 50 × Ø 20, longue de 30, avec un épaulement Ø 40 sur les 10 premiers millimètres
    anneau = [(0.0, 10.0), (-30.0, 10.0), (-30.0, 25.0), (-10.0, 25.0), (-10.0, 20.0), (0.0, 20.0),
              (0.0, 10.0)]
    p = profil_exterieur([anneau])
    assert p and p.points[0][0] == pytest.approx(0.0) and p.points[-1][0] == pytest.approx(-30.0)
    # le profil part du coin de l'alésage sur la face avant — la finition dresse la face depuis là, comme
    # elle le fait depuis l'axe sur une pièce pleine — puis la paroi du trou est écartée
    assert p.points[0] == (0.0, 10.0) and p.points[1] == (0.0, 20.0)
    assert all(x >= 20.0 - 1e-9 for z, x in p.points if z < -1e-9)
    assert p.rayon_maxi == 25.0
    # le coin bas de l'épaulement est gardé, bien qu'il ne porte pas le plus grand rayon de son abscisse
    assert (-10.0, 20.0) in p.points and (-10.0, 25.0) in p.points
    # une finition suit ce bord, et ne descend pas dans le trou
    m = Montage(brut=Brut(diametre=56.0), prise=PriseDePiece(depassement=100.0, surepaisseur_face=2.0))
    s = Sequence(id=1, type=TypeSequence.FINITION, garde=2.0, degagement=1.0)
    t = trajectoire(s, p, m)
    assert t and min(q.x for q in t.mouvements if q.travail and q.z < -1e-9) >= 20.0 - 1e-9
    # le sens est celui de toujours : du bout de la pièce vers le mandrin
    assert [z for z, _ in p.points] == sorted((z for z, _ in p.points), reverse=True)
    # et la paroi du trou, elle, est le profil intérieur : sans les faces de bout
    assert profil_interieur([anneau]).points == [(0.0, 10.0), (-30.0, 10.0)]
    assert not profil_interieur([ARBRE])


def test_profil_interieur_et_alesage_epaule():
    """Un alésage épaulé se suit comme un arbre épaulé : même profil, vu du dedans."""
    from ctgraph.usinage.matiere import etats
    # bague : extérieur Ø 40 sur 10 puis Ø 50 ; alésage Ø 20 sur 10 puis Ø 14, de part en part
    bague = [(0.0, 10.0), (0.0, 20.0), (-10.0, 20.0), (-10.0, 25.0), (-30.0, 25.0), (-30.0, 7.0),
             (-10.0, 7.0), (-10.0, 10.0), (0.0, 10.0)]
    ext, inte = profil_exterieur([bague]), profil_interieur([bague])
    assert ext.points == [(0.0, 10.0), (0.0, 20.0), (-10.0, 20.0), (-10.0, 25.0), (-30.0, 25.0)]
    assert inte.points == [(0.0, 10.0), (-10.0, 10.0), (-10.0, 7.0), (-30.0, 7.0)]
    assert profil_interieur([bague[::-1]]).points == inte.points
    # une pièce pleine à alésage borgne : la paroi s'arrête avant le fond plat, où une barre ne va pas
    borgne = [(-40.0, 0.0), (-40.0, 25.0), (0.0, 25.0), (0.0, 10.0), (-10.0, 10.0), (-10.0, 7.0),
              (-25.0, 7.0), (-25.0, 0.0), (-40.0, 0.0)]
    assert profil_interieur([borgne]).points == [(0.0, 10.0), (-10.0, 10.0), (-10.0, 7.0), (-25.0, 7.0)]
    assert profil_exterieur([borgne]).points == [(0.0, 10.0), (0.0, 25.0), (-40.0, 25.0), (-40.0, 0.0)]
    # le profil reconnaît ses propres éléments : c'est ainsi qu'une poignée lâchée sur la paroi dessinée
    # ramène l'alésage au plan
    assert inte.porte([(-10.0, 7.0), (-30.0, 7.0)]) and inte.porte([(-10.0, 10.0), (-10.0, 7.0)])
    assert not inte.porte([(0.0, 20.0), (-10.0, 20.0)]) and not inte.porte([(0.0, 10.0), (0.0, 20.0)])

    m = Montage(brut=Brut(diametre=56.0), prise=PriseDePiece(depassement=40.0, surepaisseur_face=2.0))
    g = Gamme()
    g.ajouter(TypeSequence.DRESSAGE, profondeur_passe=1.0, surepaisseur_face=0.0)
    g.ajouter(TypeSequence.PERCAGE, diametre_outil=10.0, foret="Foret Ø 10", z_fin=-36.0)
    ebauche = g.ajouter(TypeSequence.ALESAGE, profondeur_passe=1.0, surepaisseur=0.3, garde=2.0,
                        degagement=1.0)
    finition = g.ajouter(TypeSequence.FINITION_INTERIEURE, garde=2.0, degagement=1.0)
    # sans diamètre donné, l'alésage se fait au plan : il n'a rien d'autre à déclarer
    assert ebauche.diametre_fond == 0.0 and ebauche.z_fin is None
    assert ebauche.libelle() == "Alésage au plan" and finition.libelle() == "Finition int. au plan"
    suite = etats(g, m, lambda s, e: trajectoire(s, ext, m, e, None, inte))

    def passes(t):
        coupes, passe = [], []
        for a, b in zip(t.mouvements, t.mouvements[1:]):
            if b.travail:
                passe.append((round(b.z, 3), round(b.x, 3)))
            elif passe:
                coupes.append(passe)
                passe = []
        return coupes

    # l'ébauche : du Ø 10 percé au Ø 20 moins la surépaisseur, en épousant la marche. Les deux premières
    # passes courent sur toute la longueur ; les suivantes s'arrêtent **devant l'épaulement**, à la
    # surépaisseur, sans brasser l'air dans le Ø 14 déjà ouvert
    t = trajectoire(ebauche, ext, m, suite[2], None, inte)
    assert not t.message and t.nb_passes() == 5
    p = passes(t)
    assert p[0] == [(0.0, 6.0), (-30.0, 6.0), (-30.0, 5.0)]
    assert p[1] == [(0.0, 7.0), (-9.7, 7.0), (-9.7, 6.7), (-30.0, 6.7), (-30.0, 5.7)]
    assert p[2][:2] == [(0.0, 8.0), (-9.7, 8.0)] and min(z for z, _ in p[2]) == pytest.approx(-9.7)
    assert p[4][:2] == [(0.0, 9.7), (-9.7, 9.7)]
    apres = suite[3]
    assert apres.alesage_a(-5.0) == pytest.approx(9.7) and apres.alesage_a(-20.0) == pytest.approx(6.7)
    assert apres.alesage_a(-9.9) == pytest.approx(6.7)          # la face de l'épaulement garde sa surépaisseur
    # la finition : un seul passage le long de la paroi dessinée, qui dresse la face de l'épaulement
    tf = trajectoire(finition, ext, m, suite[3], None, inte)
    assert not tf.message and tf.nb_passes() == 1
    assert passes(tf)[0] == [(0.0, 10.0), (-10.0, 10.0), (-10.0, 7.0), (-30.0, 7.0), (-30.0, 6.0)]
    assert suite[4].alesage_a(-9.9) == pytest.approx(10.0) and suite[4].alesage_a(-20.0) == pytest.approx(7.0)
    # la cote de profondeur se lit sur le fond que le dessin donne
    assert ebauche.valeur_cote("profondeur", 0.0, -30.0) == pytest.approx(30.0)
    assert ebauche.texte_cote("profondeur", 0.0, -30.0) == "P 30"

    # un alésage borgne au plan : l'ébauche laisse sa surépaisseur sur le fond aussi
    ext_b, int_b = profil_exterieur([borgne]), profil_interieur([borgne])
    mb = Montage(brut=Brut(diametre=56.0), prise=PriseDePiece(depassement=50.0, surepaisseur_face=2.0))
    gb = Gamme()
    gb.ajouter(TypeSequence.DRESSAGE, profondeur_passe=1.0, surepaisseur_face=0.0)
    gb.ajouter(TypeSequence.PERCAGE, diametre_outil=10.0, foret="Foret Ø 10", z_fin=-28.0)
    ab = gb.ajouter(TypeSequence.ALESAGE, profondeur_passe=1.0, surepaisseur=0.3, garde=2.0, degagement=1.0)
    sb = etats(gb, mb, lambda s, e: trajectoire(s, ext_b, mb, e, None, int_b))
    tb = trajectoire(ab, ext_b, mb, sb[2], None, int_b)
    assert tb and min(q.z for q in tb.mouvements if q.travail) == pytest.approx(-24.7)
    # un dégagement intérieur — plus grand derrière plus petit — n'est pas pour la barre : plafonné
    degage = [(0.0, 7.0), (-10.0, 7.0), (-10.0, 10.0), (-20.0, 10.0), (-20.0, 7.0), (-30.0, 7.0),
              (-30.0, 25.0), (0.0, 25.0), (0.0, 7.0)]
    from ctgraph.usinage.trajectoires import paroi_alesage
    s = Sequence(id=1, type=TypeSequence.ALESAGE)
    assert paroi_alesage(s, profil_interieur([degage]), None, 0.0, -30.0) == [(0.0, 7.0), (-30.0, 7.0)]
    # sur une pièce dessinée pleine, l'alésage au plan dit ce qui lui manque
    sans = trajectoire(ebauche, profil_exterieur([ARBRE]), m, None, None, profil_interieur([ARBRE]))
    assert not sans and "n'a pas d'alésage" in sans.message
    # un diamètre donné reprend l'ancien comportement : un cylindre, que l'on place à la main
    cyl = Sequence(id=2, type=TypeSequence.ALESAGE, diametre_fond=16.0, z_fin=-20.0, profondeur_passe=1.0,
                   surepaisseur=0.0, garde=2.0, degagement=1.0)
    tc = trajectoire(cyl, ext, m, suite[2], None, inte)
    assert tc and max(q.x for q in tc.mouvements if q.travail) == pytest.approx(8.0)
    assert min(q.z for q in tc.mouvements if q.travail) == pytest.approx(-20.0)


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
    # et elles s'arrêtent une surépaisseur avant l'épaulement : la finition aura de quoi dresser la face
    passes_profondes = [q for q in coupes if q.x < 25.0]
    assert passes_profondes
    assert max(q.z for q in passes_profondes) == pytest.approx(-30.0 - s.surepaisseur)
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
    # longueur de coupe : l'entrée radiale, le profil sans la face arrière (25 + 30 + 10 + 50), le
    # dégagement. Sans état de matière on suppose le brut entier : l'entrée part donc de son diamètre.
    s.z_fin = None
    assert trajectoire(s, p, m).longueur_coupe() == pytest.approx(29.0 + 115 + s.degagement, abs=0.01)
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


def test_alesage_et_centrage():
    from ctgraph.usinage.matiere import EtatMatiere, appliquer
    p = profil_exterieur([ARBRE])
    m = montage_essai()
    # le centrage : une seule descente courte dans l'axe, pas de débourrage
    c = Sequence(id=8, type=TypeSequence.CENTRAGE, diametre_outil=8.0, profondeur_passe=10.0, z_fin=-3.0)
    tc = trajectoire(c, p, m)
    assert tc and tc.nb_passes() == 1 and min(q.z for q in tc.mouvements) == pytest.approx(-3.0)
    assert c.vitesse_fixe() and c.dans_l_axe()
    # l'outil est pris au catalogue des forets à centrer : deux étages, pas un simple cylindre
    c.foret = "À centrer 3,15 × 8"
    assert c.outil_de_percage().a_centrer and c.outil_de_percage().pilote == 3.15
    # enfoncé de 8 mm, le foret a passé son bout guide et son cône mord jusqu'au corps
    c.z_fin = -8.0
    etat = EtatMatiere.depuis_brut(m)
    appliquer(etat, c, trajectoire(c, p, m))
    assert etat.alesage_a(-6.0) == pytest.approx(1.575)       # le bout guide, au petit diamètre
    assert 1.575 < etat.alesage_a(-1.0) < 4.0                 # le cône, en train de s'ouvrir
    assert etat.alesage_a(1.5) == pytest.approx(4.0)          # ouvert jusqu'au corps
    # moins enfoncé, il ne fait que son avant-trou : c'est bien ce que montre le dessin
    c.z_fin = -3.0
    court = EtatMatiere.depuis_brut(m)
    appliquer(court, c, trajectoire(c, p, m))
    assert court.alesage_a(1.5) == pytest.approx(1.575)
    # un diamètre qui ne correspond plus au foret choisi : on retombe sur un foret ordinaire
    c.diametre_outil = 9.0
    assert not c.outil_de_percage().a_centrer and c.outil_de_percage().diametre == 9.0

    # l'alésage : des passes parallèles à l'axe qui ouvrent le trou du Ø 12 au Ø 20 moins la surépaisseur
    s = Sequence(id=9, type=TypeSequence.ALESAGE, diametre_outil=12.0, diametre_fond=20.0,
                 profondeur_passe=1.0, surepaisseur=0.2, garde=2.0, degagement=1.0, z_fin=-45.0)
    t = trajectoire(s, p, m)
    assert t and not t.message
    coupes = [q for q in t.mouvements if q.travail]
    assert max(q.x for q in coupes) == pytest.approx(9.8)      # 20/2 - 0,2
    assert min(q.z for q in coupes) == pytest.approx(-45.0)
    assert t.nb_passes() == 4                                  # de 6 à 9,8 par pas de 1
    # la matière suit : le trou s'ouvre sur la longueur alésée, pas au-delà
    etat = EtatMatiere.depuis_brut(m)
    appliquer(etat, s, t)
    assert etat.alesage_a(-20.0) == pytest.approx(9.8) and etat.alesage_a(-60.0) == 0.0
    # un trou déjà au diamètre, ou sans fond donné : on le dit au lieu de couper
    s.diametre_fond = 12.0
    assert not trajectoire(s, p, m) and "déjà à ce diamètre" in trajectoire(s, p, m).message
    assert trajectoire(Sequence(id=9, type=TypeSequence.ALESAGE), p, m).message


def test_gamme_type_dans_l_ordre():
    from ctgraph.usinage.sequences import FAMILLES_OUTIL
    g = Gamme().remplir_type()
    assert [s.type for s in g] == [TypeSequence.DRESSAGE, TypeSequence.CENTRAGE, TypeSequence.PERCAGE,
                                   TypeSequence.EBAUCHE, TypeSequence.ALESAGE,
                                   TypeSequence.FINITION_INTERIEURE, TypeSequence.FINITION,
                                   TypeSequence.GORGE, TypeSequence.FILETAGE, TypeSequence.TRONCONNAGE]
    # les opérations qui marchent sans autre renseignement sont cochées, les autres attendent leurs cotes
    assert [s.type for s in g.actives()] == [TypeSequence.DRESSAGE, TypeSequence.EBAUCHE,
                                             TypeSequence.FINITION, TypeSequence.TRONCONNAGE]
    # l'intérieur a ses deux opérations, distinctes de la finition extérieure ; elles se font au plan
    assert [s.libelle() for s in g][4:7] == ["Alésage au plan", "Finition int. au plan", "Finition extérieure"]
    # chaque opération sait quelle famille d'outil la fait, sauf celles qui vont au foret
    assert FAMILLES_OUTIL[TypeSequence.FINITION] == "ext_pos" and FAMILLES_OUTIL[TypeSequence.PERCAGE] == ""
    assert set(FAMILLES_OUTIL) == set(TypeSequence)


def test_cote_de_profondeur_depuis_la_surface_travaillee():
    from ctgraph.usinage.matiere import EtatMatiere, appliquer
    m = montage_essai()
    s = Sequence(id=10, type=TypeSequence.PERCAGE, diametre_outil=12.0, z_fin=-45.0)
    assert s.cotes_dessinees() == ("profondeur",)
    # la trajectoire approche depuis le bout du brut : jamais après la matière
    assert s.z_face(m) == pytest.approx(m.z_brut_avant())
    # la cote, elle, se compte depuis la surface qu'on relève et qu'on lui donne
    assert s.valeur_cote("profondeur", 0.0) == pytest.approx(45.0)
    assert s.texte_cote("profondeur", 0.0) == "P 45"
    assert s.valeur_cote("profondeur", 2.0) == pytest.approx(47.0)
    # la régler déplace le fond du trou, pas la surface
    s.definir_valeur_cote("profondeur", 30.0, 0.0)
    assert s.z_fin == pytest.approx(-30.0)
    s.definir_valeur_cote("profondeur", -5.0, 0.0)        # jamais de profondeur négative
    assert s.z_fin == pytest.approx(0.0)
    # la surface se lit sur la matière : le brut d'abord, la face dressée ensuite
    brut = EtatMatiere.depuis_brut(m)
    assert brut.z_entree() == pytest.approx(m.z_brut_avant(), abs=brut.pas)
    dresse = brut.copie()
    appliquer(dresse, Sequence(id=1, type=TypeSequence.DRESSAGE, surepaisseur_face=0.0),
              trajectoire(Sequence(id=1, type=TypeSequence.DRESSAGE, surepaisseur_face=0.0), None, m))
    assert dresse.z_entree() == pytest.approx(0.0, abs=brut.pas)
    # chaque opération en profondeur nomme la sienne
    assert s.libelle_cote("profondeur") == "Profondeur du trou"
    filetage = Sequence(id=12, type=TypeSequence.FILETAGE, z_fin=-20.0)
    assert filetage.cotes_dessinees() == ("profondeur",)
    assert filetage.libelle_cote("profondeur") == "Longueur du filet"
    assert filetage.texte_cote("profondeur", 0.0) == "L 20"
    assert Sequence(id=13, type=TypeSequence.ALESAGE).cotes_dessinees() == ("profondeur",)
    # une opération qui ne se cote pas sur le dessin n'en propose aucune
    assert Sequence(id=11, type=TypeSequence.EBAUCHE).cotes_dessinees() == ()


def test_matiere_etape_par_etape():
    from ctgraph.usinage.matiere import EtatMatiere, etats
    p = profil_exterieur([ARBRE])
    m = montage_essai()
    g = Gamme()
    dressage = g.ajouter(TypeSequence.DRESSAGE, profondeur_passe=1.0, surepaisseur_face=0.0)
    ebauche = g.ajouter(TypeSequence.EBAUCHE, profondeur_passe=2.0, surepaisseur=0.5, degagement=1.0)
    percage = g.ajouter(TypeSequence.PERCAGE, diametre_outil=12.0, z_fin=-45.0)
    filetage = g.ajouter(TypeSequence.FILETAGE, pas=2.0, z_debut=-35.0, z_fin=-70.0)
    suite = etats(g, m, lambda s, e: trajectoire(s, p, m, e))
    assert len(suite) == len(g) + 1

    # le brut : plein, au diamètre, de l'arrière jusqu'à la surépaisseur de face
    brut = suite[0]
    assert set(brut.exterieur) == {m.rayon_brut()} and set(brut.interieur) == {0.0}
    assert brut.rayon_a(1.0) == m.rayon_brut() and brut.rayon_a(-50.0) == m.rayon_brut()

    # le dressage fait avancer la face : il ne reste plus rien devant Z = 0
    apres_dressage = suite[1]
    assert apres_dressage.rayon_a(1.0) == 0.0 and apres_dressage.rayon_a(-1.0) == m.rayon_brut()

    # l'ébauche rabote : au Ø 50 elle s'arrête à la passe qui y a droit, au Ø 30 elle descend au fini + 0,5
    apres_ebauche = suite[2]
    assert apres_ebauche.rayon_a(-10.0) == pytest.approx(26.0)
    assert apres_ebauche.rayon_a(-50.0) == pytest.approx(15.5)
    assert apres_ebauche.rayon_a(-90.0) == m.rayon_brut()        # au-delà de la pièce, rien n'est touché

    # le perçage ouvre un alésage de la face au fond du trou, pas au-delà, et sa pointe est un cône
    apres_percage = suite[3]
    assert apres_percage.alesage_a(-20.0) == pytest.approx(6.0)
    assert apres_percage.alesage_a(-60.0) == 0.0
    pointe = percage.outil_de_percage().hauteur_pointe()
    assert pointe == pytest.approx(2.485, abs=0.01)
    assert apres_percage.alesage_a(-45.0 + pointe / 2.0) == pytest.approx(3.0, abs=0.4)
    assert apres_percage.alesage_a(-45.0 + pointe + 1.0) == pytest.approx(6.0)

    # le filetage enlève de la matière : il descend jusqu'au fond du filet, sur sa longueur
    hauteur = filetage.profondeur_filet()
    assert suite[4].rayon_a(-50.0) == pytest.approx(15.0 - hauteur)
    assert suite[4].rayon_a(-20.0) == apres_percage.rayon_a(-20.0)      # hors du filet, rien ne bouge
    # et il pose un filet, qui se dessine, et que l'étape signale comme neuf
    assert len(suite[4].filets) == 1 and not apres_percage.filets
    filet = suite[4].filets[0]
    assert filet.pas == 2.0 and filet.rayon == pytest.approx(15.0)
    assert filet.hauteur == pytest.approx(filetage.profondeur_filet())
    assert suite[4].filets_depuis(suite[3]) == [filet] and not suite[3].filets_depuis(suite[2])

    # ce que chaque étape a enlevé, pour le mettre en évidence : des polygones (z, rayon)
    copeaux = apres_ebauche.enlevee_depuis(apres_dressage)
    rayons = [x for poly in copeaux for _, x in poly]
    assert copeaux and max(rayons) == pytest.approx(m.rayon_brut())
    assert min(rayons) == pytest.approx(15.5)
    # le filetage aussi laisse des copeaux : le creux du filet, sur toute sa longueur
    filet_enleve = suite[4].enlevee_depuis(suite[3])
    assert filet_enleve and min(x for poly in filet_enleve for _, x in poly) == pytest.approx(15.0 - hauteur)
    # un contour suit le milieu des tranches : un cône y devient une pente, pas un escalier
    assert all(len(poly) >= 4 for poly in copeaux)
    trou = suite[3].enlevee_depuis(suite[2])
    penchants = [(a, b) for poly in trou for a, b in zip(poly, poly[1:])
                 if abs(a[0] - b[0]) > 1e-9 and abs(a[1] - b[1]) > 1e-9]
    assert penchants, "la pointe du foret doit être une pente, pas une marche d'escalier"

    # une séquence désactivée n'enlève rien, mais garde son rang dans la suite
    ebauche.active = False
    sans = etats(g, m, lambda s, e: trajectoire(s, p, m, e))
    assert len(sans) == len(suite) and sans[2].exterieur == sans[1].exterieur
    ebauche.active = True
    assert [dressage.id, ebauche.id, percage.id, filetage.id] == [s.id for s in g]
    assert etats(g, None, lambda s, e: None) == []


def test_ordre_de_la_gamme_par_rang():
    g = Gamme()
    a, b, c, d = (g.ajouter(TypeSequence.EBAUCHE) for _ in range(4))
    # le rang est celui du dépôt, compté avant le retrait de la séquence déplacée
    assert g.deplacer_a(a.id, 3) and [s.id for s in g] == [b.id, c.id, a.id, d.id]
    assert g.deplacer_a(d.id, 0) and [s.id for s in g] == [d.id, b.id, c.id, a.id]
    # lâchée là où elle est déjà : rien ne bouge
    assert not g.deplacer_a(b.id, 1) and not g.deplacer_a(b.id, 2)
    assert not g.deplacer_a(999, 0)
    # un rang hors bornes se ramène aux bouts
    assert g.deplacer_a(d.id, 99) and [s.id for s in g][-1] == d.id


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
