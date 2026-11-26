"""La matière qui reste, étape par étape : de quoi voir la pièce se dégager du brut.

Le brut est un solide de révolution : il suffit, pour le décrire, d'une suite de **tranches** le long de
l'axe, chacune portant son rayon intérieur et son rayon extérieur. Une tranche vide (les deux rayons
confondus) est de la matière enlevée. C'est grossier à l'échelle de la tranche, mais c'est exact sur les
formes qu'un tour produit, et cela suffit à montrer où chaque séquence mord.

Chaque type d'opération enlève la matière à sa façon, et seulement la sienne :

* le **dressage** fait avancer la face avant : tout ce qui est devant la passe disparaît ;
* l'**ébauche** et la **finition** rabotent ce qui dépasse au-dessus de leur chemin, tranche par tranche ;
* la **gorge** et le **tronçonnage** creusent sur la largeur de l'outil ;
* le **perçage** ouvre un alésage du diamètre du foret ;
* le **filetage** ne change pas la silhouette : le filet est une rainure hélicoïdale, l'enveloppe reste au
  diamètre nominal.

Ce modèle sert à voir, pas à vérifier : il ne tient pas compte de la forme de l'outil, et ne détecte donc
aucune collision.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List, Optional, Tuple

from .sequences import Gamme, Sequence, TypeSequence
from .trajectoires import Trajectoire

PAS_TRANCHE = 0.25          # mm : finesse du modèle de matière
TOLERANCE = 1e-6

# une bande dessinable : (z gauche, z droite, rayon intérieur, rayon extérieur)
Bande = Tuple[float, float, float, float]


def _bandes(z0: float, pas: float, paires: List[Tuple[float, float]]) -> List[Bande]:
    """Regroupe les tranches voisines de mêmes rayons en rectangles, pour n'en dessiner que quelques-uns."""
    bandes: List[Bande] = []
    debut = 0
    for i in range(len(paires) + 1):
        fini = i == len(paires)
        vide = fini or paires[i][1] - paires[i][0] <= TOLERANCE
        change = fini or vide or (i > debut and paires[i] != paires[debut])
        if change and debut < i and paires[debut][1] - paires[debut][0] > TOLERANCE:
            bandes.append((z0 + debut * pas, z0 + i * pas, paires[debut][0], paires[debut][1]))
        if change:
            debut = i + 1 if vide else i
    return bandes


@dataclass
class EtatMatiere:
    """La matière restante, en demi-profil : une tranche tous les `pas` millimètres."""
    z0: float                        # abscisse du bord gauche de la première tranche
    pas: float
    interieur: List[float]
    exterieur: List[float]

    @classmethod
    def depuis_brut(cls, montage, pas: float = PAS_TRANCHE) -> "EtatMatiere":
        """Le brut tel qu'il est serré : plein ou tube, de l'arrière à la face avant."""
        z_arriere, z_avant = montage.z_brut_arriere(), montage.z_brut_avant()
        nb = max(1, int(round((z_avant - z_arriere) / pas)))
        return cls(z_arriere, pas, [montage.rayon_interieur_brut()] * nb, [montage.rayon_brut()] * nb)

    def copie(self) -> "EtatMatiere":
        return EtatMatiere(self.z0, self.pas, list(self.interieur), list(self.exterieur))

    def __len__(self) -> int:
        return len(self.exterieur)

    def z_milieu(self, i: int) -> float:
        return self.z0 + (i + 0.5) * self.pas

    def tranches(self, z_a: float, z_b: float):
        """Les indices des tranches dont le milieu tombe entre deux abscisses, bornes comprises."""
        bas, haut = (z_a, z_b) if z_a <= z_b else (z_b, z_a)
        debut = max(0, int((bas - self.z0) / self.pas))
        fin = min(len(self), int((haut - self.z0) / self.pas) + 2)
        return [i for i in range(debut, fin) if bas - TOLERANCE <= self.z_milieu(i) <= haut + TOLERANCE]

    def raboter(self, i: int, rayon: float) -> None:
        """Enlève tout ce qui dépasse ce rayon sur la tranche."""
        if rayon < self.exterieur[i]:
            self.exterieur[i] = max(rayon, self.interieur[i])

    def aleser(self, i: int, rayon: float) -> None:
        """Ouvre l'alésage de la tranche jusqu'à ce rayon."""
        if rayon > self.interieur[i]:
            self.interieur[i] = min(rayon, self.exterieur[i])

    def indice(self, z: float) -> int:
        """L'indice de la tranche qui contient cette abscisse, −1 s'il n'y a plus de matière là."""
        i = int((z - self.z0) / self.pas)
        return i if 0 <= i < len(self) else -1

    def rayon_a(self, z: float) -> float:
        """Le rayon extérieur de la matière à cette abscisse ; 0 s'il n'y a plus rien."""
        i = self.indice(z)
        return self.exterieur[i] if i >= 0 else 0.0

    def alesage_a(self, z: float) -> float:
        """Le rayon intérieur de la matière à cette abscisse."""
        i = self.indice(z)
        return self.interieur[i] if i >= 0 else 0.0

    def bandes(self) -> List[Bande]:
        """La matière restante, en rectangles : ce qu'il faut pour la dessiner."""
        return _bandes(self.z0, self.pas, list(zip(self.interieur, self.exterieur)))

    def enlevee_depuis(self, avant: "EtatMatiere") -> List[Bande]:
        """Ce qui a disparu entre un état antérieur et celui-ci : les copeaux de l'étape."""
        if avant.pas != self.pas or abs(avant.z0 - self.z0) > TOLERANCE or len(avant) != len(self):
            return []
        dehors = [(max(self.exterieur[i], avant.interieur[i]), avant.exterieur[i]) for i in range(len(self))]
        dedans = [(avant.interieur[i], min(self.interieur[i], avant.exterieur[i])) for i in range(len(self))]
        return _bandes(self.z0, self.pas, dehors) + _bandes(self.z0, self.pas, dedans)


def _dressage(etat: EtatMatiere, sequence: Sequence, traj: Trajectoire) -> None:
    """La face avance : devant chaque passe radiale, il ne reste rien au-dessus du rayon atteint."""
    for a, b in zip(traj.mouvements, traj.mouvements[1:]):
        if not b.travail or abs(b.z - a.z) > TOLERANCE:
            continue
        bas, haut = min(a.x, b.x), max(a.x, b.x)
        for i in range(len(etat)):
            if etat.z_milieu(i) > b.z + TOLERANCE and haut + TOLERANCE >= etat.exterieur[i]:
                etat.raboter(i, bas)


def _chariotage(etat: EtatMatiere, sequence: Sequence, traj: Trajectoire) -> None:
    """Ébauche et finition : chaque trait de coupe rabote ce qui dépasse au-dessus de lui."""
    for a, b in zip(traj.mouvements, traj.mouvements[1:]):
        if not b.travail or abs(b.z - a.z) <= TOLERANCE:
            continue                      # un mouvement radial ne fait que longer une face
        for i in etat.tranches(a.z, b.z):
            t = (etat.z_milieu(i) - a.z) / (b.z - a.z)
            etat.raboter(i, a.x + t * (b.x - a.x))


def _plongee(etat: EtatMatiere, sequence: Sequence, traj: Trajectoire) -> None:
    """Gorge et tronçonnage : l'outil creuse sur sa largeur, à gauche du point piloté."""
    largeur = max(sequence.largeur_outil, etat.pas)
    for m in traj.mouvements:
        if not m.travail:
            continue
        for i in etat.tranches(m.z - largeur, m.z):
            etat.raboter(i, m.x)


def _percage(etat: EtatMatiere, sequence: Sequence, traj: Trajectoire) -> None:
    """Perçage et centrage : un alésage au diamètre du foret, de la face au fond du trou."""
    coupes = [m for m in traj.mouvements if m.travail]
    if not coupes:
        return
    rayon = sequence.diametre_outil / 2.0
    for i in etat.tranches(min(m.z for m in coupes), max(m.z for m in traj.mouvements)):
        etat.aleser(i, rayon)


def _alesage(etat: EtatMatiere, sequence: Sequence, traj: Trajectoire) -> None:
    """Alésage : chaque passe ouvre le trou à son rayon, sur la longueur qu'elle parcourt."""
    for a, b in zip(traj.mouvements, traj.mouvements[1:]):
        if not b.travail or abs(b.z - a.z) <= TOLERANCE:
            continue                      # un mouvement radial ne fait que décoller de la paroi
        for i in etat.tranches(a.z, b.z):
            etat.aleser(i, max(a.x, b.x))


_ENLEVEMENTS = {TypeSequence.DRESSAGE: _dressage, TypeSequence.EBAUCHE: _chariotage,
                TypeSequence.FINITION: _chariotage, TypeSequence.GORGE: _plongee,
                TypeSequence.TRONCONNAGE: _plongee, TypeSequence.PERCAGE: _percage,
                TypeSequence.CENTRAGE: _percage, TypeSequence.ALESAGE: _alesage}


def appliquer(etat: EtatMatiere, sequence: Sequence, traj: Optional[Trajectoire]) -> EtatMatiere:
    """Enlève de l'état la matière que cette séquence emporte. Rend l'état, modifié sur place."""
    enlever = _ENLEVEMENTS.get(TypeSequence(sequence.type))
    if enlever is not None and traj:
        enlever(etat, sequence, traj)
    return etat


def etats(gamme: Gamme, montage, calcul_trajectoire: Callable[[Sequence], Optional[Trajectoire]],
          pas: float = PAS_TRANCHE) -> List[EtatMatiere]:
    """La matière après chaque étape de la gamme : `etats[0]` est le brut, `etats[k]` l'état après la k-ième.

    Une séquence désactivée ne retire rien, mais garde sa place dans la suite : l'étape k est bien la
    k-ième ligne de la liste.
    """
    if montage is None:
        return []
    suite = [EtatMatiere.depuis_brut(montage, pas)]
    for sequence in gamme:
        etat = suite[-1].copie()
        if sequence.active:
            appliquer(etat, sequence, calcul_trajectoire(sequence))
        suite.append(etat)
    return suite
