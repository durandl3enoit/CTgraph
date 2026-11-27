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
* le **filetage** ne change pas la silhouette — le filet est une rainure hélicoïdale, l'enveloppe reste au
  diamètre nominal — mais il pose un `Filet`, qui se dessine : sinon rien ne dirait qu'il est fait.

Ce modèle sert à voir, pas à vérifier : il ne tient pas compte de la forme de l'outil, et ne détecte donc
aucune collision.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List, Optional, Tuple

from .sequences import Gamme, Sequence, TypeSequence
from .trajectoires import Trajectoire

# mm : finesse du modèle de matière. C'est la précision du contour dessiné : une face verticale tombe
# quelque part dans sa tranche, et se voit donc penchée de cette largeur-là. 0,05 mm la rend invisible.
PAS_TRANCHE = 0.05
TOLERANCE = 1e-6

# un contour dessinable : le polygone fermé d'une zone de matière, en points (z, rayon)
Contour = List[Tuple[float, float]]


def _sans_points_inutiles(chaine: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
    """Enlève les sommets alignés avec leurs voisins : un cylindre redevient deux points, pas mille.

    C'est ce qui garde les polygones petits malgré des tranches fines, et ce qui rend les droites
    franchement droites au lieu d'une suite de micro-segments.
    """
    garde: List[Tuple[float, float]] = []
    for p in chaine:
        while len(garde) >= 2:
            (z1, x1), (z2, x2) = garde[-2], garde[-1]
            # aire du triangle : nulle si le point du milieu n'apporte rien
            if abs((z2 - z1) * (p[1] - x1) - (x2 - x1) * (p[0] - z1)) > 1e-9:
                break
            garde.pop()
        garde.append(p)
    return garde


def _contours(z0: float, pas: float, paires: List[Tuple[float, float]]) -> List[Contour]:
    """Les zones non vides, en polygones qui passent par le milieu des tranches.

    Relier les milieux plutôt que les bords fait d'un cône une pente franche et non un escalier : c'est
    ce qui rend lisible la pointe d'un foret ou le cône d'un foret à centrer. Une face verticale, elle,
    se retrouve penchée de la largeur d'une tranche : c'est la précision du modèle, et c'est pourquoi
    `PAS_TRANCHE` est fin. Les sommets alignés sont ensuite retirés, pour que les polygones restent
    courts et les droites droites.
    """
    contours: List[Contour] = []
    n = len(paires)
    i = 0
    while i < n:
        if paires[i][1] - paires[i][0] <= TOLERANCE:
            i += 1
            continue
        j = i
        while j < n and paires[j][1] - paires[j][0] > TOLERANCE:
            j += 1
        milieux = [z0 + (k + 0.5) * pas for k in range(i, j)]
        bas = [paires[k][0] for k in range(i, j)]
        haut = [paires[k][1] for k in range(i, j)]
        gauche, droite = z0 + i * pas, z0 + j * pas
        dessous = _sans_points_inutiles([(gauche, bas[0])] + list(zip(milieux, bas))
                                        + [(droite, bas[-1])])
        dessus = _sans_points_inutiles([(droite, haut[-1])] + list(zip(reversed(milieux), reversed(haut)))
                                       + [(gauche, haut[0])])
        contours.append(dessous + dessus)
        i = j
    return contours


@dataclass(frozen=True)
class Filet:
    """Un filetage posé sur la pièce.

    Il ne change pas la silhouette — c'est une rainure hélicoïdale, l'enveloppe reste au diamètre
    nominal — mais il se dessine, sinon rien ne dirait que le filet est fait.
    """
    z_debut: float
    z_fin: float
    rayon: float                     # rayon de crête, le diamètre nominal du filet
    hauteur: float                   # profondeur du filet, au rayon
    pas: float
    interieur: bool = False          # filet taillé dans un alésage : les dents pointent vers l'axe


@dataclass
class EtatMatiere:
    """La matière restante, en demi-profil : une tranche tous les `pas` millimètres."""
    z0: float                        # abscisse du bord gauche de la première tranche
    pas: float
    interieur: List[float]
    exterieur: List[float]
    filets: List[Filet] = None       # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.filets is None:
            self.filets = []

    @classmethod
    def depuis_brut(cls, montage, pas: float = PAS_TRANCHE) -> "EtatMatiere":
        """Le brut tel qu'il est serré : plein ou tube, de l'arrière à la face avant."""
        z_arriere, z_avant = montage.z_brut_arriere(), montage.z_brut_avant()
        nb = max(1, int(round((z_avant - z_arriere) / pas)))
        return cls(z_arriere, pas, [montage.rayon_interieur_brut()] * nb, [montage.rayon_brut()] * nb)

    def copie(self) -> "EtatMatiere":
        return EtatMatiere(self.z0, self.pas, list(self.interieur), list(self.exterieur),
                           list(self.filets))

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

    def intervalles_au_dessus(self, rayon: float, z_a: float, z_b: float) -> List[Tuple[float, float]]:
        """Les tranches où il **reste** de la matière au-dessus de ce rayon, en z décroissant.

        C'est là qu'une passe d'ébauche a quelque chose à couper : partout ailleurs elle brasserait de
        l'air. Ce que les opérations d'avant ont enlevé est donc déduit, quelle que soit la forme.
        """
        haut, bas = max(z_a, z_b), min(z_a, z_b)
        morceaux: List[Tuple[float, float]] = []
        debut = fin = None
        for i in self.tranches(bas, haut):
            if self.exterieur[i] > rayon + TOLERANCE:
                debut = self.z0 + i * self.pas if debut is None else debut
                fin = self.z0 + (i + 1) * self.pas
            elif debut is not None:
                morceaux.append((debut, fin))
                debut = None
        if debut is not None:
            morceaux.append((debut, fin))
        return [(min(f, haut), max(d, bas)) for d, f in reversed(morceaux) if min(f, haut) > max(d, bas)]

    def intervalles_sous_la_paroi(self, rayon: float, z_a: float, z_b: float) -> List[Tuple[float, float]]:
        """Les tranches où le trou est **plus petit** que ce rayon : là qu'une passe d'alésage mord."""
        haut, bas = max(z_a, z_b), min(z_a, z_b)
        morceaux: List[Tuple[float, float]] = []
        debut = fin = None
        for i in self.tranches(bas, haut):
            plein = self.exterieur[i] - self.interieur[i] > TOLERANCE
            if plein and self.interieur[i] < rayon - TOLERANCE:
                debut = self.z0 + i * self.pas if debut is None else debut
                fin = self.z0 + (i + 1) * self.pas
            elif debut is not None:
                morceaux.append((debut, fin))
                debut = None
        if debut is not None:
            morceaux.append((debut, fin))
        return [(min(f, haut), max(d, bas)) for d, f in reversed(morceaux) if min(f, haut) > max(d, bas)]

    def z_entree(self, defaut: float = 0.0) -> float:
        """L'abscisse de la face avant de la matière : la surface qu'un outil axial attaque.

        C'est elle, et non le bout du brut, qui sert de référence aux cotes de profondeur : après un
        dressage, on perce depuis la face dressée.
        """
        for i in range(len(self) - 1, -1, -1):
            if self.exterieur[i] - self.interieur[i] > TOLERANCE:
                return self.z0 + (i + 1) * self.pas
        return defaut

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

    def contours(self) -> List[Contour]:
        """La matière restante, en polygones : ce qu'il faut pour la dessiner."""
        return _contours(self.z0, self.pas, list(zip(self.interieur, self.exterieur)))

    def enlevee_depuis(self, avant: "EtatMatiere") -> List[Contour]:
        """Ce qui a disparu entre un état antérieur et celui-ci : les copeaux de l'étape."""
        if avant.pas != self.pas or abs(avant.z0 - self.z0) > TOLERANCE or len(avant) != len(self):
            return []
        dehors = [(max(self.exterieur[i], avant.interieur[i]), avant.exterieur[i]) for i in range(len(self))]
        dedans = [(avant.interieur[i], min(self.interieur[i], avant.exterieur[i])) for i in range(len(self))]
        return _contours(self.z0, self.pas, dehors) + _contours(self.z0, self.pas, dedans)

    def filets_depuis(self, avant: "EtatMatiere") -> List[Filet]:
        """Les filets que cette étape vient de tailler."""
        return [f for f in self.filets if f not in avant.filets]


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
    """Perçage et centrage : le trou que laisse le foret, **sa pointe comprise**.

    Le `z` le plus bas atteint est celui de la pointe ; le trou ne s'élargit au plein diamètre qu'en
    arrière d'elle, du cône de pointe pour un foret ordinaire, du bout guide puis du cône de centre pour
    un foret à centrer.
    """
    coupes = [m for m in traj.mouvements if m.travail]
    if not coupes:
        return
    outil = sequence.outil_de_percage()
    z_pointe = min(m.z for m in coupes)
    for i in etat.tranches(z_pointe, max(m.z for m in traj.mouvements)):
        etat.aleser(i, outil.rayon_a(etat.z_milieu(i) - z_pointe))


def _alesage(etat: EtatMatiere, sequence: Sequence, traj: Trajectoire) -> None:
    """Alésage : chaque passe ouvre le trou à son rayon, sur la longueur qu'elle parcourt."""
    for a, b in zip(traj.mouvements, traj.mouvements[1:]):
        if not b.travail or abs(b.z - a.z) <= TOLERANCE:
            continue                      # un mouvement radial ne fait que décoller de la paroi
        for i in etat.tranches(a.z, b.z):
            etat.aleser(i, max(a.x, b.x))


def _filetage(etat: EtatMatiere, sequence: Sequence, traj: Trajectoire) -> None:
    """Filetage : **il enlève de la matière**, et pose un filet qui se dessinera.

    Le filet est une rainure hélicoïdale : en toute rigueur l'enveloppe de révolution garde le diamètre
    des crêtes. Mais le creux est bien enlevé, et le montrer vaut mieux que de laisser croire que rien
    n'a été fait. On rabote donc jusqu'au fond de filet — un outil qui repasserait là trouverait, à la
    marge, un peu moins de matière que la réalité.

    L'étendue se lit sur les **segments** de coupe, pas sur leurs points : une passe de filetage est un
    seul mouvement, dont le point d'arrivée est le bout du filet et le départ son entrée, garde comprise.
    """
    segments = [(a, b) for a, b in zip(traj.mouvements, traj.mouvements[1:]) if b.travail]
    if not segments:
        return
    depart, arrivee = segments[0]
    hauteur = sequence.profondeur_filet()
    z_haut = max(depart.z, arrivee.z) - sequence.garde
    z_bas = min(depart.z, arrivee.z)
    if sequence.interieur:
        crete = max(m.x for _, m in segments) - hauteur
        for i in etat.tranches(z_haut, z_bas):
            etat.aleser(i, crete + hauteur)
    else:
        crete = min(m.x for _, m in segments) + hauteur
        for i in etat.tranches(z_haut, z_bas):
            etat.raboter(i, crete - hauteur)
    etat.filets.append(Filet(z_haut, z_bas, crete, hauteur, sequence.pas, sequence.interieur))


_ENLEVEMENTS = {TypeSequence.DRESSAGE: _dressage, TypeSequence.EBAUCHE: _chariotage,
                TypeSequence.FINITION: _chariotage, TypeSequence.GORGE: _plongee,
                TypeSequence.TRONCONNAGE: _plongee, TypeSequence.PERCAGE: _percage,
                TypeSequence.CENTRAGE: _percage, TypeSequence.ALESAGE: _alesage,
                TypeSequence.FINITION_INTERIEURE: _alesage, TypeSequence.FILETAGE: _filetage}


def appliquer(etat: EtatMatiere, sequence: Sequence, traj: Optional[Trajectoire]) -> EtatMatiere:
    """Enlève de l'état la matière que cette séquence emporte. Rend l'état, modifié sur place."""
    enlever = _ENLEVEMENTS.get(TypeSequence(sequence.type))
    if enlever is not None and traj:
        enlever(etat, sequence, traj)
    return etat


def etats(gamme: Gamme, montage,
          calcul_trajectoire: Callable[[Sequence, Optional[EtatMatiere]], Optional[Trajectoire]],
          pas: float = PAS_TRANCHE) -> List[EtatMatiere]:
    """La matière après chaque étape de la gamme : `etats[0]` est le brut, `etats[k]` l'état après la k-ième.

    Le calcul reçoit la matière que la séquence **trouve en arrivant** : un outil enlève ce qui reste
    après l'opération d'avant, et sa trajectoire en dépend.

    Une séquence désactivée ne retire rien, mais garde sa place dans la suite : l'étape k est bien la
    k-ième ligne de la liste.
    """
    if montage is None:
        return []
    suite = [EtatMatiere.depuis_brut(montage, pas)]
    for sequence in gamme:
        avant = suite[-1]
        etat = avant.copie()
        if sequence.active:
            appliquer(etat, sequence, calcul_trajectoire(sequence, avant))
        suite.append(etat)
    return suite
