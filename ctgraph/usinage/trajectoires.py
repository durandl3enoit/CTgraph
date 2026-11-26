"""Les trajectoires : ce que l'outil parcourt, calculé à chaque fois depuis le profil et le brut.

Une trajectoire est une suite de mouvements dans le plan (z, x) de l'esquisse, **x au rayon**. Chaque
mouvement est soit un déplacement rapide, soit un déplacement en coupe : c'est exactement ce que le
post-processeur traduira en `G0` et `G1` quand viendra le point 5 du périmètre.

Le chemin est celui de la **pointe théorique de l'outil**. Le rayon de bec est corrigé par la commande
numérique (`G41` / `G42` posés sur la finition), comme le font les programmes Go2CAM archivés : on ne
décale donc pas la trajectoire ici.
"""
from __future__ import annotations

import math
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


def _matiere_sur(profil: ProfilTourne, montage, z_droite: float, largeur: float) -> float:
    """Le rayon de matière que l'outil rencontre sur sa largeur, à droite de `z_droite` vers la gauche.

    Le profil fini donne la hauteur dans la pièce ; au-delà de ses bouts, c'est le brut qui reste en place.
    """
    rayon_brut = montage.rayon_brut() if montage is not None else 0.0
    if not profil:
        return rayon_brut
    rayon = max(profil.rayon(z_droite - t * largeur) for t in (0.0, 0.5, 1.0))
    if z_droite - largeur < profil.z_fond - 1e-9 or z_droite > profil.z_bout + 1e-9:
        rayon = max(rayon, rayon_brut)          # l'outil mord dans la barre, pas seulement dans la pièce
    return rayon


def _plongee(sequence: Sequence, z: float, rayon_haut: float, rayon_fond: float) -> List[Mouvement]:
    """Une plongée radiale à l'abscisse `z`, par passes de `profondeur_passe` avec débourrage entre elles."""
    approche = rayon_haut + sequence.garde
    retrait = rayon_haut + sequence.degagement
    profondeur = max(sequence.profondeur_passe, 0.05)
    mouvements = [Mouvement(z, approche)]
    rayon = rayon_haut
    while rayon > rayon_fond + 1e-9:
        rayon = max(rayon - profondeur, rayon_fond)
        mouvements.append(Mouvement(z, rayon, travail=True))
        if rayon > rayon_fond + 1e-9:
            mouvements.append(Mouvement(z, rayon + sequence.degagement))   # débourrage
            mouvements.append(Mouvement(z, rayon))                          # retour au fond atteint
    mouvements.append(Mouvement(z, retrait))
    return mouvements


def _gorge(sequence: Sequence, profil: ProfilTourne, montage) -> Trajectoire:
    """Gorge : des plongées côte à côte, à la largeur de l'outil, jusqu'au diamètre de fond."""
    if sequence.z_debut is None or sequence.diametre_fond <= 0.0:
        return Trajectoire(sequence.id, [], "Indiquez le Z du bord droit de la gorge et son diamètre "
                                            "de fond.")
    largeur_outil = max(sequence.largeur_outil, 0.1)
    largeur = max(sequence.largeur, largeur_outil)
    z_droite = sequence.z_debut
    if montage is not None and z_droite - largeur < montage.z_face_mors() - 1e-9:
        return Trajectoire(sequence.id, [], "La gorge entre dans les mors : rapprochez-la de la face.")
    rayon_fond = sequence.diametre_fond / 2.0 + sequence.surepaisseur
    rayon_haut = _matiere_sur(profil, montage, z_droite, largeur)
    if rayon_haut <= rayon_fond + 1e-9:
        return Trajectoire(sequence.id, [], "Rien à creuser : le fond de gorge est déjà au diamètre.")
    # le point piloté est le coin droit de l'outil : il va du bord droit au bord gauche moins la largeur
    course = largeur - largeur_outil
    nb = max(1, int(course / (largeur_outil * 0.8) + 0.999) + (1 if course > 1e-9 else 0))
    mouvements: List[Mouvement] = []
    for i in range(nb):
        z = z_droite - (course * i / (nb - 1) if nb > 1 else 0.0)
        mouvements += _plongee(sequence, z, rayon_haut, rayon_fond)
    return Trajectoire(sequence.id, mouvements)


def _tronconnage(sequence: Sequence, profil: ProfilTourne, montage) -> Trajectoire:
    """Tronçonnage : une plongée jusqu'au diamètre demandé, ou jusqu'à l'axe pour détacher la pièce."""
    z = sequence.z_debut if sequence.z_debut is not None else (profil.z_fond if profil else None)
    if z is None:
        return Trajectoire(sequence.id, [], "Indiquez le Z où tronçonner.")
    if montage is not None and z - sequence.largeur_outil < montage.z_face_mors() - 1e-9:
        return Trajectoire(sequence.id, [], "Ce Z est dans les mors : le tronçonnage n'y passe pas.")
    rayon_haut = _matiere_sur(profil, montage, z, max(sequence.largeur_outil, 0.1))
    rayon_fin = sequence.diametre_fond / 2.0
    if rayon_haut <= rayon_fin + 1e-9:
        return Trajectoire(sequence.id, [], "Rien à tronçonner : la matière est déjà à ce diamètre.")
    return Trajectoire(sequence.id, _plongee(sequence, z, rayon_haut, rayon_fin))


def _filetage(sequence: Sequence, profil: ProfilTourne, montage) -> Trajectoire:
    """Filetage : des passes le long du filet, de plus en plus fines pour garder la section de copeau."""
    if sequence.z_fin is None:
        return Trajectoire(sequence.id, [], "Indiquez le Z de fin du filet.")
    if sequence.pas <= 0.0:
        return Trajectoire(sequence.id, [], "Indiquez le pas du filet.")
    z_debut = sequence.z_debut if sequence.z_debut is not None else (profil.z_bout if profil else 0.0)
    z_fin = sequence.z_fin
    if montage is not None:
        z_fin = max(z_fin, montage.z_face_mors())
    if z_debut - z_fin <= 1e-9:
        return Trajectoire(sequence.id, [], "Le filet n'a pas de longueur : vérifiez les deux Z.")
    rayon = _rayon_travail(profil, montage, (z_debut + z_fin) / 2.0)
    hauteur = sequence.profondeur_filet()
    if rayon <= hauteur + 1e-9:
        return Trajectoire(sequence.id, [], "Le filet est plus profond que la matière : vérifiez le pas.")
    nb = max(1, int(hauteur / max(sequence.profondeur_passe, 0.02) + 0.999))
    degage = rayon + sequence.degagement
    mouvements: List[Mouvement] = []
    for i in range(1, nb + 1):
        # section de copeau constante : la i-ième passe descend à la racine de i/n de la hauteur du filet
        fond = rayon - hauteur * math.sqrt(i / nb)
        mouvements.append(Mouvement(z_debut + sequence.garde, degage))
        mouvements.append(Mouvement(z_debut + sequence.garde, fond))
        mouvements.append(Mouvement(z_fin, fond, travail=True))
        mouvements.append(Mouvement(z_fin, degage))
    return Trajectoire(sequence.id, mouvements)


def _percage(sequence: Sequence, profil: ProfilTourne, montage) -> Trajectoire:
    """Perçage dans l'axe : des descentes successives, chacune suivie d'un débourrage complet.

    Sert aussi au centrage, qui n'en est qu'un cas court : une seule descente, pas de débourrage.
    """
    if sequence.z_fin is None:
        return Trajectoire(sequence.id, [], "Indiquez la profondeur du trou : son Z de fond.")
    z_face = sequence.z_face(montage if montage is not None else None)
    if sequence.z_debut is None and montage is None:
        z_face = profil.z_bout if profil else 0.0
    if z_face - sequence.z_fin <= 1e-9:
        return Trajectoire(sequence.id, [], "Le trou n'a pas de profondeur : vérifiez les deux Z.")
    pas = max(sequence.profondeur_passe, 0.1)
    approche = z_face + sequence.garde
    mouvements = [Mouvement(approche, 0.0)]
    z = z_face
    while z > sequence.z_fin + 1e-9:
        z = max(z - pas, sequence.z_fin)
        mouvements.append(Mouvement(z, 0.0, travail=True))
        if z > sequence.z_fin + 1e-9:
            mouvements.append(Mouvement(approche, 0.0))                       # débourrage complet
            mouvements.append(Mouvement(min(z + sequence.garde, approche), 0.0))
    mouvements.append(Mouvement(approche, 0.0))
    return Trajectoire(sequence.id, mouvements)


def _alesage(sequence: Sequence, profil: ProfilTourne, montage) -> Trajectoire:
    """Alésage : la barre reprend le trou percé, en passes parallèles à l'axe qui l'ouvrent peu à peu."""
    if sequence.z_fin is None or sequence.diametre_fond <= 0.0:
        return Trajectoire(sequence.id, [], "Indiquez le diamètre à aléser et le fond de l'alésage.")
    z_face = sequence.z_face(montage)
    z_fin = sequence.z_fin
    if z_face - z_fin <= 1e-9:
        return Trajectoire(sequence.id, [], "L'alésage n'a pas de profondeur : vérifiez les deux Z.")
    rayon_trou = sequence.diametre_outil / 2.0
    rayon_vise = sequence.diametre_fond / 2.0 - sequence.surepaisseur
    if rayon_vise <= rayon_trou + 1e-9:
        return Trajectoire(sequence.id, [], "Le trou est déjà à ce diamètre : rien à aléser.")
    profondeur = max(sequence.profondeur_passe, 0.05)
    nb = max(1, int((rayon_vise - rayon_trou) / profondeur + 0.999))

    mouvements: List[Mouvement] = []
    for i in range(1, nb + 1):
        rayon = min(rayon_trou + i * profondeur, rayon_vise)
        retrait = max(rayon - sequence.degagement, 0.0)
        mouvements.append(Mouvement(z_face + sequence.garde, rayon))
        mouvements.append(Mouvement(z_face, rayon, travail=True))
        mouvements.append(Mouvement(z_fin, rayon, travail=True))
        mouvements.append(Mouvement(z_fin, retrait, travail=True))      # on décolle de la paroi
        mouvements.append(Mouvement(z_face + sequence.garde, retrait))
    return Trajectoire(sequence.id, mouvements)


def _rayon_travail(profil: ProfilTourne, montage, z: float) -> float:
    """Le rayon de la matière à une abscisse : le profil s'il y est, sinon le brut."""
    rayon = profil.rayon(z) if profil else 0.0
    if rayon <= 0.0 and montage is not None:
        rayon = montage.rayon_brut()
    return rayon


_CALCULS = {TypeSequence.DRESSAGE: _dressage, TypeSequence.EBAUCHE: _ebauche,
            TypeSequence.FINITION: _finition, TypeSequence.GORGE: _gorge,
            TypeSequence.FILETAGE: _filetage, TypeSequence.PERCAGE: _percage,
            TypeSequence.CENTRAGE: _percage, TypeSequence.ALESAGE: _alesage,
            TypeSequence.TRONCONNAGE: _tronconnage}


def trajectoire(sequence: Sequence, profil: ProfilTourne, montage=None) -> Trajectoire:
    """La trajectoire d'une séquence, recalculée depuis le profil résolu et le montage.

    `montage` est un `ctgraph.montage.Montage` : il donne le brut et la face des mors. Sans lui, seules
    les séquences qui n'ont besoin que du profil fini peuvent être calculées.
    """
    calcul = _CALCULS.get(TypeSequence(sequence.type))
    if calcul is None:
        return Trajectoire(sequence.id, [], f"Type de séquence inconnu : {sequence.type}")
    return calcul(sequence, profil, montage)
