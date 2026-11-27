"""Le profil tourné : ce que l'outil doit laisser, tiré des contours fermés de l'esquisse.

Un contour fermé de l'esquisse fait le tour de la matière : il monte la face avant, suit le profil
extérieur, redescend la face arrière, puis revient par l'axe — ou, si la pièce est creuse, par la paroi
de l'alésage. Pour l'usinage, on le coupe en deux (`_profils`) : le **profil extérieur**, ce que les
outils de tournage extérieur suivent, et le **profil intérieur**, la paroi de l'alésage que suit la
barre, épaulements compris. Chacun est parcouru du bout de la pièce (le z le plus grand, côté
opérateur) vers le mandrin. Un alésage épaulé se traite ainsi exactement comme un arbre épaulé : même
objet, même méthodes, l'un vu du dessus, l'autre du dedans.

Repère : `z` le long de l'axe, `x` le rayon. Z = 0 est la face avant finie, Z négatif vers le mandrin.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

Point = Tuple[float, float]
TOLERANCE_AXE = 1e-6


def _sur_axe(p: Point) -> bool:
    return abs(p[1]) <= TOLERANCE_AXE


def _sans_fermeture(contour: Sequence[Point]) -> List[Point]:
    pts = [(float(z), float(x)) for z, x in contour]
    if len(pts) > 1 and pts[0] == pts[-1]:
        pts = pts[:-1]
    return pts


def _du_bout_vers_le_mandrin(chaine: List[Point]) -> List[Point]:
    """La chaîne orientée du bout de la pièce vers le mandrin : son premier point est le plus en avant."""
    if len(chaine) >= 2 and chaine[0][0] < chaine[-1][0] - TOLERANCE_AXE:
        return list(reversed(chaine))
    return list(chaine)


def _sommet_haut(pts: List[Point], z_cible: float) -> int:
    """L'indice du point le plus haut parmi ceux posés à cette abscisse : le coin d'une face de bout."""
    candidats = [i for i, (z, _) in enumerate(pts) if abs(z - z_cible) <= 1e-6]
    return max(candidats, key=lambda i: pts[i][1])


def _ouvrir_sur_l_axe(pts: List[Point]) -> List[Point]:
    """Coupe un contour qui touche l'axe au niveau de celui-ci, et rend la chaîne qui n'y est pas.

    Elle va d'un point posé sur l'axe à un autre : le pied de la face arrière d'un côté, de l'autre le
    pied de la face avant — ou le fond d'un alésage borgne, si la pièce en a un.
    """
    n = len(pts)
    sur = [_sur_axe(p) for p in pts]
    if n < 3 or all(sur) or not any(sur):
        return list(pts)
    # on repart juste après le dernier point d'une suite posée sur l'axe
    depart = next(i for i in range(n) if sur[i] and not sur[(i + 1) % n])
    chaine = [pts[depart % n]]
    i = (depart + 1) % n
    while not sur[i]:
        chaine.append(pts[i])
        i = (i + 1) % n
    chaine.append(pts[i])          # le premier point revenu sur l'axe ferme la chaîne
    return chaine


def _bords_anneau(pts: List[Point]) -> Tuple[List[Point], List[Point]]:
    """Les deux bords d'un contour qui ne touche pas l'axe : (extérieur, intérieur avec ses faces de bout).

    Un tel contour est un anneau — la pièce est percée de part en part : la paroi de l'alésage, les deux
    faces de bout, et le bord extérieur. On le coupe au **sommet le plus haut de chaque face de bout** —
    les deux seuls endroits où le bord extérieur rejoint le reste. Des deux chaînes obtenues, celle de
    plus grand rayon moyen est le bord extérieur, l'autre la paroi de l'alésage, faces de bout comprises.
    Les deux sont rendues du bout de la pièce vers le mandrin.

    Couper ailleurs, par exemple sur le critère « ce sommet porte-t-il le plus grand rayon de son
    abscisse », casserait la chaîne à chaque épaulement : le coin bas d'une face d'épaulement est sous
    l'enveloppe, et pourtant il appartient bien au bord extérieur.
    """
    n = len(pts)
    if n < 3:
        return list(pts), []
    a = _sommet_haut(pts, min(z for z, _ in pts))
    b = _sommet_haut(pts, max(z for z, _ in pts))
    if a == b:
        return list(pts), []
    chaines = sorted(([pts[(a + k) % n] for k in range((b - a) % n + 1)],
                      [pts[(b + k) % n] for k in range((a - b) % n + 1)]),
                     key=lambda ch: sum(x for _, x in ch) / len(ch), reverse=True)
    return _du_bout_vers_le_mandrin(chaines[0]), _du_bout_vers_le_mandrin(chaines[1])


def _face_avant(chaine: List[Point]) -> List[Point]:
    """Ce qui longe la face avant au début d'une chaîne orientée du bout vers le mandrin."""
    z_avant = chaine[0][0]
    fin = next((i for i, (z, _) in enumerate(chaine) if abs(z - z_avant) > 1e-6), len(chaine))
    return chaine[:fin]


def _sans_les_faces(chaine: List[Point]) -> List[Point]:
    """Une chaîne orientée du bout vers le mandrin, **sans ce qui longe ses faces de bout**.

    C'est ce qu'une barre d'alésage doit suivre : la paroi, du coin d'entrée au fond, épaulements
    compris, mais ni la face avant (c'est le dressage qui la fait) ni le fond plat d'un alésage borgne,
    où une barre ne descend pas jusqu'à l'axe.
    """
    if len(chaine) < 2:
        return []
    z_min = min(z for z, _ in chaine)
    debut = len(_face_avant(chaine))
    fin = next((i for i in range(len(chaine) - 1, -1, -1) if abs(chaine[i][0] - z_min) > 1e-6), -1)
    noyau = chaine[max(debut - 1, 0):fin + 2]
    return noyau if len(noyau) >= 2 else []


def _profils(contour: Sequence[Point]) -> Tuple[List[Point], List[Point]]:
    """Un contour fermé coupé en deux : (profil extérieur, profil intérieur), chacun du bout vers le mandrin.

    Le profil extérieur part du pied de la face avant — l'axe pour une pièce pleine, le coin de l'alésage
    pour une pièce creuse — et va jusqu'au pied de la face arrière : la finition finit ainsi la face avant
    puis suit le profil, et s'arrête avant de redescendre la face arrière. Le profil intérieur est la paroi
    de l'alésage, sans les faces de bout ; vide si la pièce est pleine.

    Pièce percée de part en part : le contour est un anneau, `_bords_anneau` le coupe. Pièce pleine ou à
    alésage borgne : le contour touche l'axe, on l'ouvre là, puis on le coupe au sommet de la face avant,
    le seul point où l'extérieur et l'alésage se touchent. Jusqu'au 26 novembre 2026 l'anneau entier
    passait pour le profil extérieur : la finition descendait dans l'alésage et rabotait toute la pièce.
    """
    pts = _sans_fermeture(contour)
    if len(pts) < 3:
        return pts, []
    sur = [_sur_axe(p) for p in pts]
    if not any(sur):
        exterieur, dedans = _bords_anneau(pts)
        if not dedans:
            return exterieur, []
        face = _face_avant(dedans)                 # du sommet de la face avant au coin de l'alésage
        return list(reversed(face))[:-1] + exterieur, _sans_les_faces(dedans)
    if all(sur):
        return pts, []
    chaine = _ouvrir_sur_l_axe(pts)
    # orientée pour finir au pied de la face arrière : l'autre bout est le pied de la face avant, ou le
    # fond de l'alésage borgne
    if chaine[0][0] < chaine[-1][0] - TOLERANCE_AXE:
        chaine = list(reversed(chaine))
    sommet = _sommet_haut(chaine, max(z for z, _ in chaine))
    exterieur = chaine[max(sommet - 1, 0):]
    interieur = _sans_les_faces(_du_bout_vers_le_mandrin(chaine[:sommet]))
    return exterieur, interieur


@dataclass
class ProfilTourne:
    """Le profil extérieur, du bout de la pièce vers le mandrin : z décroissant."""
    points: List[Point]

    def __post_init__(self) -> None:
        if len(self.points) >= 2 and self.points[0][0] < self.points[-1][0]:
            self.points = list(reversed(self.points))

    def __bool__(self) -> bool:
        return len(self.points) >= 2

    @property
    def z_bout(self) -> float:
        """Le z du bout de la pièce : là où l'outil aborde la matière."""
        return max(z for z, _ in self.points) if self.points else 0.0

    @property
    def z_fond(self) -> float:
        """Le z le plus enfoncé vers le mandrin."""
        return min(z for z, _ in self.points) if self.points else 0.0

    @property
    def rayon_maxi(self) -> float:
        return max((x for _, x in self.points), default=0.0)

    def segments(self):
        return zip(self.points, self.points[1:])

    def rayon(self, z: float) -> float:
        """Le rayon fini de la pièce à l'abscisse `z` : le plus grand x du profil à cet endroit.

        Hors de la pièce, 0 : il n'y a pas de matière à laisser.
        """
        plus_grand = 0.0
        for (z1, x1), (z2, x2) in self.segments():
            bas, haut = (z1, z2) if z1 <= z2 else (z2, z1)
            if z < bas - TOLERANCE_AXE or z > haut + TOLERANCE_AXE:
                continue
            if abs(z2 - z1) <= TOLERANCE_AXE:
                plus_grand = max(plus_grand, x1, x2)      # face droite : on prend le plus haut
            else:
                t = (z - z1) / (z2 - z1)
                plus_grand = max(plus_grand, x1 + t * (x2 - x1))
        return plus_grand

    def z_matiere(self, rayon: float) -> Optional[float]:
        """Le plus grand z où le profil fini dépasse `rayon` : une passe paraxiale à ce rayon doit s'y
        arrêter. None si le profil reste partout en dessous, la passe peut aller jusqu'au bout."""
        plus_grand: Optional[float] = None

        def retenir(z: float) -> None:
            nonlocal plus_grand
            plus_grand = z if plus_grand is None else max(plus_grand, z)

        for (z1, x1), (z2, x2) in self.segments():
            dessus1, dessus2 = x1 > rayon + TOLERANCE_AXE, x2 > rayon + TOLERANCE_AXE
            if dessus1:
                retenir(z1)
            if dessus2:
                retenir(z2)
            if dessus1 != dessus2 and abs(x2 - x1) > TOLERANCE_AXE:
                t = (rayon - x1) / (x2 - x1)          # le segment croise le rayon : on prend le passage
                retenir(z1 + t * (z2 - z1))
        return plus_grand

    def _abscisses_remarquables(self, rayon: float) -> List[float]:
        """Les z où le profil change d'allure vis-à-vis d'un rayon : sommets et croisements."""
        zs = [z for z, _ in self.points]
        for (z1, x1), (z2, x2) in self.segments():
            if (x1 - rayon) * (x2 - rayon) < 0 and abs(x2 - x1) > TOLERANCE_AXE:
                zs.append(z1 + (rayon - x1) / (x2 - x1) * (z2 - z1))
        return zs

    def intervalles_sous(self, rayon: float, z_debut: float, z_fin: float) -> List[Tuple[float, float]]:
        """Les tranches (z_haut, z_bas) où le profil fini reste sous `rayon`, dans l'ordre z décroissant.

        C'est là qu'une passe paraxiale à ce rayon a le droit de couper. Une pièce épaulée en donne
        plusieurs : la passe ne peut pas partir du bout si un épaulement plus gros est devant.
        """
        haut, bas = (z_debut, z_fin) if z_debut >= z_fin else (z_fin, z_debut)
        bornes = sorted({z for z in self._abscisses_remarquables(rayon) if bas < z < haut} | {haut, bas},
                        reverse=True)
        tranches: List[Tuple[float, float]] = []
        for a, b in zip(bornes, bornes[1:]):
            if a - b <= TOLERANCE_AXE:
                continue
            if self.rayon((a + b) / 2.0) <= rayon + 1e-9:
                if tranches and abs(tranches[-1][1] - a) <= TOLERANCE_AXE:
                    tranches[-1] = (tranches[-1][0], b)       # on recolle les tranches qui se suivent
                else:
                    tranches.append((a, b))
        return tranches

    def rayon_mini(self, z_debut: float, z_fin: float) -> float:
        """Le plus petit rayon que le profil atteint sur la tranche, faces de bout exceptées.

        C'est jusque-là que l'ébauche doit descendre : le petit diamètre d'un arbre épaulé. On mesure au
        milieu de chaque segment, ce qui laisse de côté les faces droites, où le rayon saute.
        """
        morceau = self.entre(z_debut, z_fin)
        rayons = [self.rayon((a[0] + b[0]) / 2.0) for a, b in zip(morceau, morceau[1:])
                  if abs(b[0] - a[0]) > TOLERANCE_AXE]
        return min(rayons) if rayons else self.rayon_maxi

    def entre(self, z_debut: float, z_fin: float) -> List[Point]:
        """Les points du profil entre deux abscisses, bornes comprises, dans l'ordre du profil.

        Chaque segment est rogné sur la tranche demandée : la chaîne rendue épouse exactement le profil.
        """
        bas, haut = (z_fin, z_debut) if z_fin <= z_debut else (z_debut, z_fin)
        morceau: List[Point] = []

        def poser(p: Point) -> None:
            if not morceau or (abs(p[0] - morceau[-1][0]) > TOLERANCE_AXE
                               or abs(p[1] - morceau[-1][1]) > TOLERANCE_AXE):
                morceau.append(p)

        for (z1, x1), (z2, x2) in self.segments():
            if abs(z2 - z1) <= TOLERANCE_AXE:         # face droite : dedans ou dehors, sans rognage
                if bas - TOLERANCE_AXE <= z1 <= haut + TOLERANCE_AXE:
                    poser((z1, x1))
                    poser((z2, x2))
                continue
            ta, tb = (bas - z1) / (z2 - z1), (haut - z1) / (z2 - z1)
            t0, t1 = max(0.0, min(ta, tb)), min(1.0, max(ta, tb))
            if t0 > t1 + 1e-12:
                continue
            for t in (t0, t1):
                poser((z1 + t * (z2 - z1), x1 + t * (x2 - x1)))
        return morceau

    def porte(self, points: Sequence[Point], tolerance: float = 1e-6) -> bool:
        """Vrai si les deux bouts de cette polyligne sont sur le profil : l'élément d'esquisse qu'elle
        représente en fait partie. Sert à reconnaître qu'une poignée a été lâchée sur la paroi dessinée."""
        pts = list(points)
        if len(pts) < 2 or not self:
            return False
        return all(self._distance(p) <= tolerance for p in (pts[0], pts[-1]))

    def _distance(self, p: Point) -> float:
        """La distance d'un point au profil : au plus près de l'un de ses segments."""
        z, x = p
        plus_courte = float("inf")
        for (z1, x1), (z2, x2) in self.segments():
            dz, dx = z2 - z1, x2 - x1
            longueur2 = dz * dz + dx * dx
            t = 0.0 if longueur2 <= 1e-18 else max(0.0, min(1.0, ((z - z1) * dz + (x - x1) * dx) / longueur2))
            plus_courte = min(plus_courte, ((z - z1 - t * dz) ** 2 + (x - x1 - t * dx) ** 2) ** 0.5)
        return plus_courte


def _contour_principal(contours: Sequence[Sequence[Point]]) -> List[Point]:
    """Le plus grand contour fermé : c'est la pièce. Les autres (gorges dessinées à part) viendront
    quand le module saura les distinguer."""
    meilleur: List[Point] = []
    etendue = -1.0
    for contour in contours:
        pts = [(float(z), float(x)) for z, x in contour]
        if len(pts) < 3:
            continue
        large = (max(z for z, _ in pts) - min(z for z, _ in pts)) * max(x for _, x in pts)
        if large > etendue:
            meilleur, etendue = pts, large
    return meilleur


def profil_exterieur(contours: Sequence[Sequence[Point]]) -> ProfilTourne:
    """Le profil extérieur de la pièce, tiré des contours fermés de l'esquisse : ce que suivent les
    outils de tournage extérieur, de la face avant au fond."""
    principal = _contour_principal(contours)
    return ProfilTourne(_profils(principal)[0] if principal else [])


def profil_interieur(contours: Sequence[Sequence[Point]]) -> ProfilTourne:
    """Le profil intérieur de la pièce : la paroi de l'alésage dessiné, épaulements compris, du coin
    d'entrée au fond. Vide (faux) si la pièce est pleine : il n'y a alors rien à aléser au plan."""
    principal = _contour_principal(contours)
    return ProfilTourne(_profils(principal)[1] if principal else [])
