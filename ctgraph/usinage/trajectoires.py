"""Les trajectoires : ce que l'outil parcourt, calculé à chaque fois depuis le profil et la matière.

Une trajectoire est une suite de mouvements dans le plan (z, x) de l'esquisse, **x au rayon**. Chaque
mouvement est soit un déplacement rapide, soit un déplacement en coupe : c'est exactement ce que le
post-processeur traduira en `G0` et `G1` quand viendra le point 5 du périmètre.

**Un outil enlève ce qui reste après l'opération d'avant.** C'est la règle, rappelée par l'utilisateur le
26 novembre 2026, et c'est pourquoi chaque calcul reçoit l'`EtatMatiere` que la séquence trouve en
arrivant : l'ébauche part du diamètre qui reste et non du brut, l'alésage part du trou déjà percé, et
surtout **aucune approche rapide ne traverse la matière** — on contourne toujours par devant la face
encore présente. Sans état fourni, on retombe sur le brut : c'est l'ancien comportement, prudent.

Le chemin est celui de la **pointe théorique de l'outil**. Le rayon de bec est corrigé par la commande
numérique (`G41` / `G42` posés sur la finition), comme le font les programmes Go2CAM archivés : on ne
décale donc pas la trajectoire ici.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, replace
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


def _face_matiere(etat, montage, defaut: float = 0.0) -> float:
    """L'abscisse devant laquelle il n'y a plus rien : c'est par là qu'un outil arrive sans rien toucher."""
    if etat is not None:
        return etat.z_entree(montage.z_brut_avant() if montage is not None else defaut)
    return montage.z_brut_avant() if montage is not None else defaut


def _dehors(etat, montage, z_a: float, z_b: float) -> float:
    """Le plus grand rayon de matière sur une tranche : au-dessus, l'outil circule librement."""
    if etat is not None:
        rayons = [etat.exterieur[i] for i in etat.tranches(z_a, z_b)]
        if rayons:
            return max(rayons)
    return montage.rayon_brut() if montage is not None else 0.0


def _dedans(etat, montage, z_a: float, z_b: float) -> float:
    """Le plus petit trou déjà ouvert sur une tranche : ce qu'un filet intérieur doit respecter."""
    if etat is not None:
        rayons = [etat.interieur[i] for i in etat.tranches(z_a, z_b)
                  if etat.exterieur[i] - etat.interieur[i] > 1e-9]
        if rayons:
            return min(rayons)
    return montage.rayon_interieur_brut() if montage is not None else 0.0


def _entree_trou(etat, montage, z_face: float, z_fin: float) -> float:
    """Le trou **par lequel la barre entre** : son rayon à la première tranche de matière sous la face.

    C'est de là qu'un alésage part, et non du plus petit rayon de la tranche : ce dernier serait le
    sommet du cône d'un foret, et l'on verrait la barre faire des passes au fond d'un cône où elle ne
    passe pas. La barre bore ce qu'elle peut atteindre, pas davantage.
    """
    if etat is not None:
        for i in reversed(etat.tranches(z_fin, z_face)):
            if etat.exterieur[i] - etat.interieur[i] > 1e-9:
                return etat.interieur[i]
    return montage.rayon_interieur_brut() if montage is not None else 0.0


def _bornes(sequence: Sequence, profil: ProfilTourne, montage) -> Tuple[float, float]:
    """L'étendue en Z à usiner : du bout de la pièce au fond, bornée par la séquence et par les mors."""
    z_debut = sequence.z_debut if sequence.z_debut is not None else profil.z_bout
    z_fin = sequence.z_fin if sequence.z_fin is not None else profil.z_fond
    if montage is not None:
        # on ne descend pas dans les mors : la face des mors est la limite physique
        z_fin = max(z_fin, montage.z_face_mors())
    return z_debut, min(z_fin, z_debut)


def _dressage(sequence: Sequence, profil: ProfilTourne, montage, etat=None) -> Trajectoire:
    """Dressage de la face avant : passes de la matière vers l'axe, en descendant en Z."""
    if montage is None:
        return Trajectoire(sequence.id, [], "Le dressage demande le montage : il part du bout du brut.")
    z_brut = _face_matiere(etat, montage)
    z_fini = profil.z_bout if profil else 0.0
    if z_brut <= z_fini + 1e-9:
        return Trajectoire(sequence.id, [], "Rien à dresser : la face est déjà en place.")
    rayon_depart = _dehors(etat, montage, z_brut, z_fini) + sequence.degagement
    rayon_fin = _dedans(etat, montage, z_brut, z_fini)
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


def _ebauche(sequence: Sequence, profil: ProfilTourne, montage, etat=None) -> Trajectoire:
    """Ébauche paraxiale : passes parallèles à l'axe, de la matière restante vers le profil + surépaisseur."""
    if not profil:
        return Trajectoire(sequence.id, [], "Pas de profil fermé : rien à ébaucher.")
    if montage is None:
        return Trajectoire(sequence.id, [], "L'ébauche demande le montage : elle part du diamètre du brut.")
    z_debut, z_fin = _bornes(sequence, profil, montage)
    rayon_brut = _dehors(etat, montage, z_debut, z_fin)
    # l'ébauche descend jusqu'au plus petit diamètre de la tranche, pas seulement jusqu'au plus grand
    rayon_vise = profil.rayon_mini(z_debut, z_fin) + sequence.surepaisseur
    if rayon_brut <= rayon_vise + 1e-9:
        return Trajectoire(sequence.id, [], "La matière est déjà au diamètre : rien à ébaucher.")
    profondeur = max(sequence.profondeur_passe, 0.05)
    nb = max(1, int((rayon_brut - rayon_vise) / profondeur + 0.999))
    # on contourne toujours par devant la matière restante : un rapide ne traverse jamais le métal
    z_libre = max(_face_matiere(etat, montage), z_debut)

    mouvements: List[Mouvement] = []
    for i in range(1, nb + 1):
        rayon = max(rayon_brut - i * profondeur, rayon_vise)
        # la passe ne coupe que là où le profil fini, surépaisseur comprise, reste sous elle : un
        # épaulement plus gros devant interdit de partir du bout, on entre après lui
        for z_haut, z_bas in profil.intervalles_sous(rayon - sequence.surepaisseur, z_debut, z_fin):
            # **surépaisseur avant et après l'épaulement** : un bout d'intervalle fermé par la montée du
            # profil s'arrête à distance, pour que la finition ait de quoi dresser la face
            if z_haut < z_debut - 1e-9:
                z_haut -= sequence.surepaisseur
            if z_bas > z_fin + 1e-9:
                z_bas += sequence.surepaisseur
            if z_haut - z_bas <= 1e-9:
                continue
            # et la passe se limite à la matière qui reste : ailleurs elle brasserait de l'air
            tranches = (etat.intervalles_au_dessus(rayon, z_haut, z_bas) if etat is not None
                        else [(z_haut, z_bas)])
            for z_a, z_b in tranches:
                approche = max(z_a, z_libre) + sequence.garde
                mouvements.append(Mouvement(approche, rayon + sequence.degagement))
                mouvements.append(Mouvement(z_a, rayon + sequence.degagement))
                mouvements.append(Mouvement(z_a, rayon, travail=True))
                mouvements.append(Mouvement(z_b, rayon, travail=True))
                mouvements.append(Mouvement(z_b, rayon + sequence.degagement, travail=True))
                mouvements.append(Mouvement(approche, rayon + sequence.degagement))
    if not mouvements:
        return Trajectoire(sequence.id, [], "Aucune passe : la matière et le profil sont au même diamètre.")
    return Trajectoire(sequence.id, mouvements)


def _finition(sequence: Sequence, profil: ProfilTourne, montage, etat=None) -> Trajectoire:
    """Finition : un passage sur le profil fini, de son bout jusqu'au fond demandé.

    La face avant se finit depuis l'axe : elle est libre. La face arrière, elle, ne se descend pas
    jusqu'à l'axe : la pièce y tient encore à la barre, c'est au tronçonnage de la détacher. Le chemin
    s'arrête donc au dernier point du profil avant son retour sur l'axe.

    L'approche se fait **devant la matière restante** : aller se placer sur l'axe au milieu du brut non
    dressé serait une collision en rapide.
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
    z_libre = max(_face_matiere(etat, montage), depart[0]) + sequence.garde
    # on arrive par-dessus la matière, puis on **entre radialement** au point de départ : descendre en Z
    # au rayon du profil labourerait ce qu'un dressage aurait laissé devant
    dessus = max(depart[1], _dehors(etat, montage, depart[0], z_libre)) + sequence.degagement
    mouvements = [Mouvement(z_libre, dessus),
                  Mouvement(depart[0], dessus),
                  Mouvement(depart[0], depart[1], travail=True)]
    mouvements += [Mouvement(z, x, travail=True) for z, x in chemin[1:]]
    mouvements.append(Mouvement(arrivee[0], arrivee[1] + sequence.degagement, travail=True))
    mouvements.append(Mouvement(z_libre, arrivee[1] + sequence.degagement))
    return Trajectoire(sequence.id, mouvements)


def _matiere_sur(profil: ProfilTourne, montage, z_droite: float, largeur: float, etat=None) -> float:
    """Le rayon de matière que l'outil rencontre sur sa largeur, à droite de `z_droite` vers la gauche.

    L'état de la matière fait foi quand on l'a : c'est ce qui reste après les opérations précédentes. À
    défaut, le profil fini donne la hauteur dans la pièce, et le brut règne au-delà de ses bouts.
    """
    if etat is not None:
        return _dehors(etat, montage, z_droite, z_droite - largeur)
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


def _gorge(sequence: Sequence, profil: ProfilTourne, montage, etat=None) -> Trajectoire:
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
    rayon_haut = _matiere_sur(profil, montage, z_droite, largeur, etat)
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


def _tronconnage(sequence: Sequence, profil: ProfilTourne, montage, etat=None) -> Trajectoire:
    """Tronçonnage : une plongée jusqu'au diamètre demandé, ou jusqu'à l'axe pour détacher la pièce."""
    z = sequence.z_debut if sequence.z_debut is not None else (profil.z_fond if profil else None)
    if z is None:
        return Trajectoire(sequence.id, [], "Indiquez le Z où tronçonner.")
    if montage is not None and z - sequence.largeur_outil < montage.z_face_mors() - 1e-9:
        return Trajectoire(sequence.id, [], "Ce Z est dans les mors : le tronçonnage n'y passe pas.")
    rayon_haut = _matiere_sur(profil, montage, z, max(sequence.largeur_outil, 0.1), etat)
    rayon_fin = sequence.diametre_fond / 2.0
    if rayon_haut <= rayon_fin + 1e-9:
        return Trajectoire(sequence.id, [], "Rien à tronçonner : la matière est déjà à ce diamètre.")
    return Trajectoire(sequence.id, _plongee(sequence, z, rayon_haut, rayon_fin))


def _filetage(sequence: Sequence, profil: ProfilTourne, montage, etat=None) -> Trajectoire:
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
    hauteur = sequence.profondeur_filet()
    if sequence.interieur:
        # filet intérieur : la crête est au fond du trou, l'outil ouvre vers l'extérieur
        rayon = _dedans(etat, montage, z_debut, z_fin)
        if rayon <= 1e-9:
            return Trajectoire(sequence.id, [], "Pas de trou à fileter : percez d'abord.")
        sens = 1.0
    else:
        rayon = _rayon_travail(profil, montage, (z_debut + z_fin) / 2.0)
        if rayon <= hauteur + 1e-9:
            return Trajectoire(sequence.id, [],
                               "Le filet est plus profond que la matière : vérifiez le pas.")
        sens = -1.0
    nb = max(1, int(hauteur / max(sequence.profondeur_passe, 0.02) + 0.999))
    degage = rayon - sens * sequence.degagement
    mouvements: List[Mouvement] = []
    for i in range(1, nb + 1):
        # section de copeau constante : la i-ième passe va à la racine de i/n de la hauteur du filet
        fond = rayon + sens * hauteur * math.sqrt(i / nb)
        mouvements.append(Mouvement(z_debut + sequence.garde, degage))
        mouvements.append(Mouvement(z_debut + sequence.garde, fond))
        mouvements.append(Mouvement(z_fin, fond, travail=True))
        mouvements.append(Mouvement(z_fin, degage))
    return Trajectoire(sequence.id, mouvements)


def _percage(sequence: Sequence, profil: ProfilTourne, montage, etat=None) -> Trajectoire:
    """Perçage dans l'axe : des descentes successives, chacune suivie d'un débourrage complet.

    Sert aussi au centrage, qui n'en est qu'un cas court : une seule descente, pas de débourrage.
    """
    if sequence.z_fin is None:
        return Trajectoire(sequence.id, [], "Indiquez la profondeur du trou : son Z de fond.")
    if sequence.z_debut is not None:
        z_face = sequence.z_debut
    elif etat is not None or montage is not None:
        z_face = _face_matiere(etat, montage)
    else:
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


def _rogner(polyligne: List[Tuple[float, float]], z_haut: float,
            z_bas: float) -> List[Tuple[float, float]]:
    """La polyligne réduite à une tranche, **bouts interpolés**.

    Filtrer les sommets ne suffirait pas : une paroi cylindrique n'a que deux points, et une tranche
    plus courte qu'elle n'en garderait aucun. C'est ce qui faisait disparaître les passes d'alésage.
    """
    haut, bas = max(z_haut, z_bas), min(z_haut, z_bas)
    morceau: List[Tuple[float, float]] = []

    def poser(p: Tuple[float, float]) -> None:
        if not morceau or abs(p[0] - morceau[-1][0]) > 1e-9 or abs(p[1] - morceau[-1][1]) > 1e-9:
            morceau.append(p)

    for (z1, x1), (z2, x2) in zip(polyligne, polyligne[1:]):
        if abs(z2 - z1) <= 1e-12:
            if bas - 1e-9 <= z1 <= haut + 1e-9:
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


def _paroi_visee(sequence: Sequence, paroi, z_face: float, z_fin: float) -> List[Tuple[float, float]]:
    """La paroi à obtenir quand un diamètre est donné, en points (z, rayon) du bord d'entrée vers le fond.

    Sans paroi désignée, c'est un cylindre au diamètre demandé. Avec une ligne ou un arc de l'esquisse
    (`paroi`, une polyligne que l'appelant a résolue), l'alésage **suit cette forme** : un cône, un congé,
    un dégagement. C'est ce qui permet qu'une zone à aléser ne soit pas forcément rectangulaire.
    """
    rayon = sequence.diametre_fond / 2.0
    if not paroi:
        return [(z_face, rayon), (z_fin, rayon)]
    points = sorted(((float(z), float(x)) for z, x in paroi), key=lambda q: -q[0])
    haut, bas = points[0][0], points[-1][0]
    suite: List[Tuple[float, float]] = []
    for z in sorted({z_face, z_fin} | {z for z, _ in points if z_fin <= z <= z_face}, reverse=True):
        if z >= haut:
            suite.append((z, points[0][1]))
        elif z <= bas:
            suite.append((z, points[-1][1]))
        else:
            a = next(i for i in range(len(points) - 1) if points[i][0] >= z >= points[i + 1][0])
            (z1, x1), (z2, x2) = points[a], points[a + 1]
            t = 0.0 if abs(z2 - z1) < 1e-12 else (z - z1) / (z2 - z1)
            suite.append((z, x1 + t * (x2 - x1)))
    return suite


def suit_le_dessin(sequence: Sequence) -> bool:
    """Vrai si l'alésage se fait **au plan** : sans diamètre donné, il suit la paroi dessinée de la pièce."""
    return sequence.diametre_fond <= 0.0


def fond_alesage(sequence: Sequence, profil_interieur: Optional[ProfilTourne], montage) -> Optional[float]:
    """Le Z où l'alésage s'arrête : celui qu'on a donné, sinon le fond de l'alésage dessiné — que
    l'alésage soit au plan ou à un diamètre donné, le dessin dit jusqu'où va le trou.

    Borné par la face des mors, comme toute séquence. None s'il manque : pas de fond donné, et une
    pièce dessinée pleine.
    """
    z_fin = sequence.z_fin
    if z_fin is None and profil_interieur:
        z_fin = profil_interieur.z_fond
    if z_fin is not None and montage is not None:
        z_fin = max(z_fin, montage.z_face_mors())
    return z_fin


def paroi_alesage(sequence: Sequence, profil_interieur: Optional[ProfilTourne], paroi,
                  z_face: float, z_fin: float) -> List[Tuple[float, float]]:
    """La paroi que l'alésage doit obtenir, en points (z, rayon) de la face vers le fond, sans surépaisseur.

    Au plan, c'est le profil intérieur de la pièce dessinée, **épaulements compris** : un alésage épaulé
    se suit comme un arbre épaulé. Avec un diamètre donné, c'est un cylindre, ou la ligne ou l'arc de
    l'esquisse désigné. Dans les deux cas, la paroi est ramenée à **ce qu'une barre atteint en entrant
    par la face** : un diamètre plus grand derrière un plus petit — un dégagement intérieur — est
    plafonné au passage qui le précède ; c'est l'affaire d'un outil de gorge intérieure, pas de la barre.
    """
    if suit_le_dessin(sequence):
        brute = profil_interieur.entre(z_face, z_fin) if profil_interieur else []
    else:
        brute = _paroi_visee(sequence, paroi, z_face, z_fin)
    atteignable: List[Tuple[float, float]] = []
    passage = float("inf")
    for z, x in brute:
        passage = min(passage, x)
        atteignable.append((z, passage))
    atteignable = _epurer(atteignable)
    return atteignable if len(atteignable) >= 2 else []


def _avec_surepaisseur(brute: List[Tuple[float, float]], surepaisseur: float,
                       z_face: float) -> List[Tuple[float, float]]:
    """La paroi visée moins la surépaisseur : au rayon partout, et **en Z devant chaque épaulement**.

    La face d'un épaulement garde son épaisseur à finir, comme en ébauche extérieure : la passe qui
    longe le grand diamètre s'arrête à distance de la marche, au lieu d'y dresser la face à vif.
    """
    pts = [(z, max(x - surepaisseur, 0.0)) for z, x in brute]
    if surepaisseur <= 1e-9:
        return pts
    for i in range(len(pts) - 1):
        (z1, x1), (z2, x2) = pts[i], pts[i + 1]
        if abs(z2 - z1) <= 1e-9 and x2 < x1 - 1e-9:          # une marche : le trou se resserre
            borne = pts[i - 1][0] if i > 0 else z_face
            z = min(z1 + surepaisseur, borne)
            pts[i], pts[i + 1] = (z, x1), (z, x2)
    return pts


def _rayon_cible(cible: List[Tuple[float, float]], z: float) -> float:
    """Le rayon de la paroi visée à une abscisse ; sur une marche, le plus grand des deux."""
    rayon = 0.0
    trouve = False
    for (z1, x1), (z2, x2) in zip(cible, cible[1:]):
        haut, bas = max(z1, z2), min(z1, z2)
        if z < bas - 1e-9 or z > haut + 1e-9:
            continue
        valeur = max(x1, x2) if abs(z2 - z1) <= 1e-12 else x1 + (z - z1) / (z2 - z1) * (x2 - x1)
        rayon, trouve = (max(rayon, valeur) if trouve else valeur), True
    if not trouve and cible:
        return cible[0][1] if z > cible[0][0] else cible[-1][1]
    return rayon


def _alesage(sequence: Sequence, profil: ProfilTourne, montage, etat=None, paroi=None,
             profil_interieur: Optional[ProfilTourne] = None, finition: bool = False) -> Trajectoire:
    """Alésage : la barre ouvre le trou **tel qu'il est** jusqu'à la paroi voulue, passe après passe.

    Le trou de départ n'est pas déclaré : c'est celui que les opérations d'avant ont laissé. La paroi
    visée est celle du dessin — épaulements compris — ou, si un diamètre est donné, un cylindre ou la
    forme d'un élément de l'esquisse. Chaque passe est plafonnée à son rayon et ne court que là où le
    trou est encore plus petit qu'elle : elle épouse donc les marches et ne brasse pas l'air dans ce
    qu'une passe plus fine a déjà ouvert, comme les passes d'une ébauche extérieure. `finition` : un
    seul passage à la paroi, sans surépaisseur.
    """
    au_plan = suit_le_dessin(sequence)
    if au_plan and not profil_interieur:
        return Trajectoire(sequence.id, [], "Le dessin n'a pas d'alésage : dessinez le trou, ou "
                                            "indiquez le diamètre à aléser.")
    z_face = sequence.z_debut if sequence.z_debut is not None else _face_matiere(etat, montage)
    z_fin = fond_alesage(sequence, profil_interieur, montage)
    if z_fin is None:
        return Trajectoire(sequence.id, [], "Indiquez le fond de l'alésage.")
    # un alésage borgne au plan : l'ébauche laisse aussi sa surépaisseur sur le fond
    if au_plan and sequence.z_fin is None and profil and profil_interieur.z_fond > profil.z_fond + 1e-6:
        z_fin += sequence.surepaisseur
    if z_face - z_fin <= 1e-9:
        return Trajectoire(sequence.id, [], "L'alésage n'a pas de profondeur : vérifiez les deux Z.")
    brute = paroi_alesage(sequence, profil_interieur, paroi, z_face, z_fin)
    if len(brute) < 2:
        return Trajectoire(sequence.id, [], "Le dessin n'a pas d'alésage sur cette étendue.")
    cible = _avec_surepaisseur(brute, sequence.surepaisseur, z_face)
    rayon_trou = (_entree_trou(etat, montage, z_face, z_fin) if etat is not None
                  else sequence.diametre_outil / 2.0)
    rayon_vise = max(x for _, x in cible)
    if rayon_vise <= rayon_trou + 1e-9:
        return Trajectoire(sequence.id, [], "Le trou est déjà à ce diamètre : rien à aléser.")
    if finition:
        # un seul passage, qui prend ce que l'ébauche a laissé : au plus ce qu'il trouve à l'entrée
        plafonds = [rayon_vise]
        prise_maxi = max(rayon_vise - rayon_trou, sequence.profondeur_passe)
    else:
        profondeur = max(sequence.profondeur_passe, 0.05)
        nb = max(1, int((rayon_vise - rayon_trou) / profondeur + 0.999))
        plafonds = [min(rayon_trou + i * profondeur, rayon_vise) for i in range(1, nb + 1)]
        prise_maxi = profondeur
    z_libre = max(_face_matiere(etat, montage), z_face) + sequence.garde

    def sous_la_cible(z: float) -> float:
        return _rayon_cible(cible, z)

    # les passes se suivent sur une copie de la matière : chacune sait ce que les précédentes ont ouvert
    travail = etat.copie() if etat is not None else None
    mouvements: List[Mouvement] = []
    for plafond in plafonds:
        # la passe ne court que là où le trou est encore plus petit qu'elle **et** que la paroi visée —
        # le reste est déjà ouvert — et pas là où elle aurait plus que sa profondeur à prendre : un trou
        # bien plus étroit, le cône d'un foret, l'arrête
        tranches = (travail.intervalles_sous_la_paroi(plafond, z_face, z_fin, paroi=sous_la_cible,
                                                      prise_maxi=prise_maxi)
                    if travail is not None else [(z_face, z_fin)])
        for z_a, z_b in tranches:
            chemin = _epurer([(z, min(x, plafond)) for z, x in _rogner(cible, z_a, z_b)])
            if len(chemin) < 2:
                continue
            retrait = max(chemin[-1][1] - sequence.degagement, 0.0)
            mouvements.append(Mouvement(z_libre, chemin[0][1]))
            mouvements += [Mouvement(z, x, travail=True) for z, x in chemin]
            mouvements.append(Mouvement(chemin[-1][0], retrait, travail=True))  # on décolle de la paroi
            mouvements.append(Mouvement(z_libre, retrait))
            if travail is not None:
                ouvrir_alesage(travail, chemin)
    if not mouvements:
        return Trajectoire(sequence.id, [], "Le trou est déjà à ce diamètre : rien à aléser.")
    return Trajectoire(sequence.id, mouvements)


def ouvrir_alesage(etat, chemin: List[Tuple[float, float]]) -> None:
    """Ouvre la matière le long d'un chemin de coupe (z, rayon) : chaque tranche traversée est alésée au
    rayon du chemin à son abscisse — interpolé sur une pente, pour qu'un cône alésé soit un cône.

    `etat` est un `EtatMatiere` ; la fonction vit ici, et non dans `matiere`, parce que l'alésage s'en
    sert pour suivre ses propres passes (`matiere` importe ce module, pas l'inverse).
    """
    for (z1, x1), (z2, x2) in zip(chemin, chemin[1:]):
        if abs(z2 - z1) <= 1e-9:
            continue                      # un mouvement radial ne fait que décoller de la paroi
        for i in etat.tranches(z1, z2):
            t = (etat.z_milieu(i) - z1) / (z2 - z1)
            etat.aleser(i, x1 + t * (x2 - x1))


def _epurer(chemin: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
    """La polyligne sans ses points répétés ni ses points alignés : plafonner une marche en fait naître,
    et chacun ferait un bloc de plus dans le programme."""
    propre: List[Tuple[float, float]] = []
    for p in chemin:
        if propre and abs(p[0] - propre[-1][0]) <= 1e-9 and abs(p[1] - propre[-1][1]) <= 1e-9:
            continue
        if len(propre) >= 2:
            (z0, x0), (z1, x1) = propre[-2], propre[-1]
            if abs((z1 - z0) * (p[1] - x0) - (x1 - x0) * (p[0] - z0)) <= 1e-9 \
                    and (z1 - z0) * (p[0] - z1) + (x1 - x0) * (p[1] - x1) >= 0.0:
                propre[-1] = p                # même direction : le point du milieu ne sert à rien
                continue
        propre.append(p)
    return propre


def _finition_interieure(sequence: Sequence, profil: ProfilTourne, montage, etat=None, paroi=None,
                         profil_interieur: Optional[ProfilTourne] = None) -> Trajectoire:
    """Finition d'alésage : un seul passage le long de la paroi, comme la finition extérieure en suit le profil."""
    traj = _alesage(replace(sequence, surepaisseur=0.0), profil, montage, etat, paroi, profil_interieur,
                    finition=True)
    return Trajectoire(sequence.id, traj.mouvements, traj.message)


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
            TypeSequence.FINITION_INTERIEURE: _finition_interieure,
            TypeSequence.TRONCONNAGE: _tronconnage}


def trajectoire(sequence: Sequence, profil: ProfilTourne, montage=None, etat=None, paroi=None,
                profil_interieur: Optional[ProfilTourne] = None) -> Trajectoire:
    """La trajectoire d'une séquence, recalculée depuis le profil résolu, le montage et la matière.

    `montage` est un `ctgraph.montage.Montage` : il donne le brut et la face des mors. `etat` est
    l'`EtatMatiere` que la séquence trouve en arrivant — ce que les opérations d'avant ont laissé ; sans
    lui, on raisonne sur le brut. `paroi` est la polyligne (z, rayon) qu'un alésage à diamètre donné doit
    suivre, résolue par l'appelant depuis l'élément d'esquisse désigné ; `profil_interieur` est la paroi
    de l'alésage dessiné (`profil.profil_interieur`), que suit un alésage au plan.
    """
    calcul = _CALCULS.get(TypeSequence(sequence.type))
    if calcul is None:
        return Trajectoire(sequence.id, [], f"Type de séquence inconnu : {sequence.type}")
    if calcul in (_alesage, _finition_interieure):
        return calcul(sequence, profil, montage, etat, paroi, profil_interieur)
    return calcul(sequence, profil, montage, etat)
