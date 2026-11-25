"""Les trajectoires : ce que l'outil parcourt, calculé à chaque fois depuis le profil et le brut.

Une trajectoire est une suite de mouvements dans le plan (z, x) de l'esquisse, **x au rayon**. Chaque
mouvement est soit un déplacement rapide, soit un déplacement en coupe : c'est exactement ce que le
post-processeur traduira en `G0` et `G1` quand viendra le point 5 du périmètre.

Le chemin est celui de la **pointe théorique de l'outil**. Le rayon de bec est corrigé par la commande
numérique (`G41` / `G42` posés sur la finition), comme le font les programmes Go2CAM archivés : on ne
décale donc pas la trajectoire ici.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

from .profil import ProfilTourne
from .sequences import Sequence, TypeSequence


@dataclass(frozen=True)
class Mouvement:
    """Un déplacement vers (z, x). `travail` : en coupe (G1) plutôt qu'en rapide (G0)."""
    z: float
    x: float
    travail: bool = False

    @property
    def diametre(self) -> float:
        return 2.0 * self.x


@dataclass
class Trajectoire:
    """Le chemin d'une séquence, et ce qui a empêché de le calculer le cas échéant."""
    sequence_id: int = 0
    mouvements: List[Mouvement] = None            # type: ignore[assignment]
    message: str = ""

    def __post_init__(self) -> None:
        if self.mouvements is None:
            self.mouvements = []

    def __bool__(self) -> bool:
        return bool(self.mouvements)

    def __len__(self) -> int:
        return len(self.mouvements)

    def longueur_coupe(self) -> float:
        """Longueur parcourue en coupe, en millimètres : de quoi estimer un temps plus tard."""
        total = 0.0
        for a, b in zip(self.mouvements, self.mouvements[1:]):
            if b.travail:
                total += ((b.z - a.z) ** 2 + (b.x - a.x) ** 2) ** 0.5
        return total

    def nb_passes(self) -> int:
        """Nombre de passes en coupe : les entrées en matière après un rapide."""
        nb, precedent_rapide = 0, True
        for m in self.mouvements:
            if m.travail and precedent_rapide:
                nb += 1
            precedent_rapide = not m.travail
        return nb


def _bornes(sequence: Sequence, profil: ProfilTourne, montage) -> Tuple[float, float]:
    """L'étendue en Z à usiner : du bout de la pièce au fond, bornée par la séquence et par les mors."""
    z_debut = sequence.z_debut if sequence.z_debut is not None else profil.z_bout
    z_fin = sequence.z_fin if sequence.z_fin is not None else profil.z_fond
    if montage is not None:
        # on ne descend pas dans les mors : la face des mors est la limite physique
        z_fin = max(z_fin, montage.z_face_mors())
    return z_debut, min(z_fin, z_debut)


def _dressage(sequence: Sequence, profil: ProfilTourne, montage) -> Trajectoire:
    """Dressage de la face avant : passes de la matière vers l'axe, en descendant en Z."""
    if montage is None:
        return Trajectoire(sequence.id, [], "Le dressage demande le montage : il part du bout du brut.")
    z_brut = montage.z_brut_avant()
    z_fini = profil.z_bout if profil else 0.0
    if z_brut <= z_fini + 1e-9:
        return Trajectoire(sequence.id, [], "Rien à dresser : le brut n'avance pas au-delà de la face finie.")
    rayon_depart = montage.rayon_brut() + sequence.degagement
    rayon_fin = montage.rayon_interieur_brut()
    profondeur = max(sequence.profondeur_passe, 0.05)
    reste = z_brut - z_fini - sequence.surepaisseur_face
    nb = max(1, int(reste / profondeur + 0.999)) if reste > 1e-9 else 1

    mouvements: List[Mouvement] = []
    for i in range(1, nb + 1):
        z = max(z_brut - i * profondeur, z_fini + sequence.surepaisseur_face)
        mouvements.append(Mouvement(z + sequence.garde, rayon_depart))
        mouvements.append(Mouvement(z, rayon_depart, travail=True))
        mouvements.append(Mouvement(z, rayon_fin, travail=True))
        mouvements.append(Mouvement(z + sequence.degagement, rayon_fin))
        mouvements.append(Mouvement(z + sequence.garde, rayon_depart))
    return Trajectoire(sequence.id, mouvements)


def _ebauche(sequence: Sequence, profil: ProfilTourne, montage) -> Trajectoire:
    """Ébauche paraxiale : passes parallèles à l'axe, du brut vers le profil plus la surépaisseur."""
    if not profil:
        return Trajectoire(sequence.id, [], "Pas de profil fermé : rien à ébaucher.")
    if montage is None:
        return Trajectoire(sequence.id, [], "L'ébauche demande le montage : elle part du diamètre du brut.")
    z_debut, z_fin = _bornes(sequence, profil, montage)
    rayon_brut = montage.rayon_brut()
    # l'ébauche descend jusqu'au plus petit diamètre de la tranche, pas seulement jusqu'au plus grand
    rayon_vise = profil.rayon_mini(z_debut, z_fin) + sequence.surepaisseur
    if rayon_brut <= rayon_vise + 1e-9:
        return Trajectoire(sequence.id, [], "Le brut est déjà au diamètre : rien à ébaucher.")
    profondeur = max(sequence.profondeur_passe, 0.05)
    nb = max(1, int((rayon_brut - rayon_vise) / profondeur + 0.999))

    mouvements: List[Mouvement] = []
    for i in range(1, nb + 1):
        rayon = max(rayon_brut - i * profondeur, rayon_vise)
        # la passe ne coupe que là où le profil fini, surépaisseur comprise, reste sous elle : un
        # épaulement plus gros devant interdit de partir du bout, on entre après lui
        for z_haut, z_bas in profil.intervalles_sous(rayon - sequence.surepaisseur, z_debut, z_fin):
            mouvements.append(Mouvement(z_haut + sequence.garde, rayon + sequence.degagement))
            mouvements.append(Mouvement(z_haut, rayon + sequence.degagement))
            mouvements.append(Mouvement(z_haut, rayon, travail=True))
            mouvements.append(Mouvement(z_bas, rayon, travail=True))
            mouvements.append(Mouvement(z_bas, rayon + sequence.degagement, travail=True))
            mouvements.append(Mouvement(z_haut + sequence.garde, rayon + sequence.degagement))
    if not mouvements:
        return Trajectoire(sequence.id, [], "Aucune passe : le brut et le profil sont au même diamètre.")
    return Trajectoire(sequence.id, mouvements)


def _finition(sequence: Sequence, profil: ProfilTourne, montage) -> Trajectoire:
    """Finition : un passage sur le profil fini, de son bout jusqu'au fond demandé.

    La face avant se finit depuis l'axe : elle est libre. La face arrière, elle, ne se descend pas
    jusqu'à l'axe : la pièce y tient encore à la barre, c'est au tronçonnage de la détacher. Le chemin
    s'arrête donc au dernier point du profil avant son retour sur l'axe.
    """
    if not profil:
        return Trajectoire(sequence.id, [], "Pas de profil fermé : rien à finir.")
    z_debut, z_fin = _bornes(sequence, profil, montage)
    chemin = profil.entre(z_debut, z_fin)
    while len(chemin) > 2 and abs(chemin[-1][1]) <= 1e-6:
        chemin.pop()
    if len(chemin) < 2:
        return Trajectoire(sequence.id, [], "Le profil n'a rien à finir sur cette étendue.")
    depart, arrivee = chemin[0], chemin[-1]
    mouvements = [Mouvement(depart[0] + sequence.garde, depart[1] + sequence.garde),
                  Mouvement(depart[0] + sequence.garde, depart[1]),
                  Mouvement(depart[0], depart[1], travail=True)]
    mouvements += [Mouvement(z, x, travail=True) for z, x in chemin[1:]]
    mouvements.append(Mouvement(arrivee[0], arrivee[1] + sequence.degagement, travail=True))
    mouvements.append(Mouvement(depart[0] + sequence.garde, arrivee[1] + sequence.degagement))
    return Trajectoire(sequence.id, mouvements)


_CALCULS = {TypeSequence.DRESSAGE: _dressage, TypeSequence.EBAUCHE: _ebauche, TypeSequence.FINITION: _finition}


def trajectoire(sequence: Sequence, profil: ProfilTourne, montage=None) -> Trajectoire:
    """La trajectoire d'une séquence, recalculée depuis le profil résolu et le montage.

    `montage` est un `ctgraph.montage.Montage` : il donne le brut et la face des mors. Sans lui, seules
    les séquences qui n'ont besoin que du profil fini peuvent être calculées.
    """
    calcul = _CALCULS.get(TypeSequence(sequence.type))
    if calcul is None:
        return Trajectoire(sequence.id, [], f"Type de séquence inconnu : {sequence.type}")
    return calcul(sequence, profil, montage)
