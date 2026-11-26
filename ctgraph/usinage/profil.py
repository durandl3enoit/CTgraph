"""Le profil tourné : ce que l'outil doit laisser, tiré des contours fermés de l'esquisse.

Un contour fermé de l'esquisse fait le tour de la matière : il monte la face avant, suit le profil
extérieur, redescend la face arrière, puis revient par l'axe. Pour l'usinage, seule compte la partie
qui n'est pas sur l'axe : c'est le **profil extérieur**, parcouru du bout de la pièce (le z le plus
grand, côté opérateur) vers le mandrin.

Repère : `z` le long de l'axe, `x` le rayon. Z = 0 est la face avant finie, Z négatif vers le mandrin.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

Point = Tuple[float, float]
TOLERANCE_AXE = 1e-6


def _sur_axe(p: Point) -> bool:
    return abs(p[1]) <= TOLERANCE_AXE


def _ouvrir_sur_l_axe(contour: List[Point]) -> List[Point]:
    """Coupe le contour fermé au niveau de l'axe et rend la chaîne qui n'y est pas.

    Le contour est donné fermé (premier point répété à la fin). **S'il ne touche jamais l'axe**, c'est que
    la pièce est percée de part en part : le contour est un anneau, et c'est `_bord_exterieur` qui en tire
    le dessus. Rendre l'anneau entier ferait descendre la finition dans l'alésage et raboter toute la
    pièce — c'est ce qui se produisait jusqu'au 26 novembre 2026.
    """
    pts = list(contour)
    if len(pts) > 1 and pts[0] == pts[-1]:
        pts = pts[:-1]
    n = len(pts)
    if n < 3:
        return pts
    sur = [_sur_axe(p) for p in pts]
    if all(sur):
        return pts
    if not any(sur):
        return _bord_exterieur(contour)
    # on repart juste après le dernier point d'une suite posée sur l'axe
    depart = next(i for i in range(n) if sur[i] and not sur[(i + 1) % n])
    chaine = [pts[depart % n]]
    i = (depart + 1) % n
    while not sur[i]:
        chaine.append(pts[i])
        i = (i + 1) % n
    chaine.append(pts[i])          # le premier point revenu sur l'axe ferme la chaîne
    return chaine


def _bord_exterieur(contour: List[Point]) -> List[Point]:
    """Le dessus d'un contour qui ne touche pas l'axe : le profil extérieur d'une pièce percée.

    Un tel contour est un anneau : la paroi de l'alésage, les deux faces de bout, et le bord extérieur.
    On le coupe au **sommet le plus haut de chaque face de bout** — les deux seuls endroits où le bord
    extérieur rejoint l'alésage — et des deux chaînes obtenues on garde celle de plus grand rayon moyen.

    Couper ailleurs, par exemple sur le critère « ce sommet porte-t-il le plus grand rayon de son
    abscisse », casserait la chaîne à chaque épaulement : le coin bas d'une face d'épaulement est sous
    l'enveloppe, et pourtant il appartient bien au bord extérieur.
    """
    pts = list(contour)
    if len(pts) > 1 and pts[0] == pts[-1]:
        pts = pts[:-1]
    n = len(pts)
    if n < 3:
        return pts
    z_min = min(z for z, _ in pts)
    z_max = max(z for z, _ in pts)

    def sommet_haut(z_cible: float) -> int:
        candidats = [i for i, (z, _) in enumerate(pts) if abs(z - z_cible) <= 1e-6]
        return max(candidats, key=lambda i: pts[i][1])

    a, b = sommet_haut(z_min), sommet_haut(z_max)
    if a == b:
        return pts
    chaines = ([pts[(a + k) % n] for k in range((b - a) % n + 1)],
               [pts[(b + k) % n] for k in range((a - b) % n + 1)])
    return max(chaines, key=lambda ch: sum(x for _, x in ch) / len(ch))


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


def profil_exterieur(contours: Sequence[Sequence[Point]]) -> ProfilTourne:
    """Le profil extérieur de la pièce, tiré des contours fermés de l'esquisse.

    Le plus grand contour l'emporte : c'est la pièce. Les autres (gorges dessinées à part, profils
    intérieurs) viendront quand le module saura les distinguer.
    """
    meilleur: List[Point] = []
    etendue = -1.0
    for contour in contours:
        pts = [(float(z), float(x)) for z, x in contour]
        if len(pts) < 3:
            continue
        large = (max(z for z, _ in pts) - min(z for z, _ in pts)) * max(x for _, x in pts)
        if large > etendue:
            meilleur, etendue = pts, large
    return ProfilTourne(_ouvrir_sur_l_axe(meilleur) if meilleur else [])
