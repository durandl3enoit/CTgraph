"""Plaquettes de coupe : formes, géométrie et catalogue des tailles qui vont dans les porte-plaquettes.

Les désignations suivent l'**ISO 1832**. Pour `CNMG 120408` :

* `C` forme : C losange 80°, D losange 55°, V losange 35°, W trigon 80°, T triangle, S carré, R ronde ;
* `N` dépouille de la plaquette : N 0° (négative, à retourner), B 5°, C 7°, P 11° (positives) ;
* `M` classe de tolérance (M : moyenne, la courante) ;
* `G` type : A trou lisse sans brise-copeaux, G trou et brise-copeaux sur les deux faces, M brise-copeaux
  sur une face, T trou fraisé et brise-copeaux sur une face, N ni trou ni brise-copeaux ;
* `12` longueur d'arête, en code (12 → cercle inscrit 12,7 mm) ;
* `04` épaisseur, en code (04 → 4,76 mm ; T3 → 3,97 mm) ;
* `08` rayon de bec en dixièmes de millimètre (08 → 0,8 mm ; 00 → plaquette ronde).

Une plaquette **négative** (dépouille 0°) a deux faces utilisables et une arête robuste : c'est l'ébauche.
Une plaquette **positive** coupe plus librement et demande moins d'effort : c'est la finition et les pièces
peu rigides. Le rayon de bec tient l'état de surface et la résistance de la pointe : grand pour l'ébauche,
petit pour les angles vifs et les pièces élancées.

Les plaquettes de filetage et de gorge n'entrent pas dans l'ISO 1832 : leurs références sont celles du
commerce, signalées comme telles.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

# Forme de la plaquette : la lettre ISO, ou la nature de l'outil quand il n'y en a pas.
# `icons.icone_plaquette` dessine chacune de ces clés.
FORMES_PLAQUETTE: Dict[str, str] = {
    "C": "Losange 80°",
    "D": "Losange 55°",
    "V": "Losange 35°",
    "W": "Trigon 80°",
    "T": "Triangle 60°",
    "S": "Carré",
    "R": "Ronde",
    "filetage": "Plaquette de filetage",
    "gorge": "Plaquette de gorge",
    "lame": "Lame de tronçonnage",
}

# Angle de pointe des formes polygonales, en degrés : ce que dessinent `sommets_forme` et les icônes.
ANGLES_FORME: Dict[str, float] = {"C": 80.0, "D": 55.0, "V": 35.0, "W": 80.0, "T": 60.0, "S": 90.0}

FAMILLES: Dict[str, str] = {
    "negative": "Négatives — ébauche (dépouille 0°)",
    "positive": "Positives — finition (dépouille 5 à 11°)",
    "filetage": "Filetage",
    "gorge": "Gorge et tronçonnage",
}

TYPES_ISO: Dict[str, str] = {
    "A": "trou lisse, sans brise-copeaux",
    "G": "trou lisse, brise-copeaux deux faces",
    "M": "trou lisse, brise-copeaux une face",
    "N": "ni trou ni brise-copeaux",
    "T": "trou fraisé, brise-copeaux une face",
    "W": "trou fraisé, sans brise-copeaux",
}


def forme_plaquette(plaquette: str) -> str:
    """La clé de forme déduite d'une désignation (« CNMG 1204.. » → « C »). Vide si inconnue."""
    if plaquette.startswith("MGMN"):
        return "gorge"
    if plaquette.startswith("Lame"):
        return "lame"
    if re.match(r"\d+[EI][RL]", plaquette):
        return "filetage"
    lettre = plaquette[:1].upper()
    return lettre if lettre in FORMES_PLAQUETTE and lettre in ANGLES_FORME or lettre == "R" else ""


def sommets_forme(forme: str, rayon: float = 1.0) -> List[Tuple[float, float]]:
    """Le contour d'une forme polygonale dans un cercle de `rayon`, premier sommet en haut, sens horaire
    à l'écran. Vide pour une plaquette ronde ou une forme sans contour polygonal.

    Les losanges (C, D, V) ont leur grande diagonale horizontale, le triangle et le trigon pointent en haut.
    """
    if forme in ("C", "D", "V"):
        # grande diagonale au diamètre du cercle : les trois losanges se comparent d'un coup d'œil
        demi = math.radians(ANGLES_FORME[forme]) / 2.0
        a, b = rayon, rayon * math.tan(demi)
        return [(-a, 0.0), (0.0, -b), (a, 0.0), (0.0, b)]
    if forme in ("T", "S"):
        nb = 3 if forme == "T" else 4
        depart = 90.0 if forme == "T" else 45.0
        return [(rayon * math.cos(math.radians(depart + 360.0 * k / nb)),
                 -rayon * math.sin(math.radians(depart + 360.0 * k / nb))) for k in range(nb)]
    if forme == "W":
        # trois pointes à 80° reliées par des côtés rentrants : entre le triangle et le rond
        pointes = sommets_forme("T", rayon)
        creux = [(rayon * 0.72 * math.cos(math.radians(150.0 + 120.0 * k)),
                  -rayon * 0.72 * math.sin(math.radians(150.0 + 120.0 * k))) for k in range(3)]
        return [coin for paire in zip(pointes, creux) for coin in paire]
    return []


def rayon_inscrit(forme: str, rayon: float = 1.0) -> float:
    """Rayon du cercle inscrit d'une forme donnée dans un cercle de `rayon` : la plus courte distance du
    centre à une arête. Pour une forme sans contour polygonal, le rayon lui-même."""
    sommets = sommets_forme(forme, rayon)
    if not sommets:
        return rayon
    court = float("inf")
    for i in range(len(sommets)):
        a, b = sommets[i], sommets[(i + 1) % len(sommets)]
        lg = max(math.hypot(b[0] - a[0], b[1] - a[1]), 1e-9)
        court = min(court, abs(a[0] * b[1] - a[1] * b[0]) / lg)
    return court if court < float("inf") else rayon


def angle_interieur(sommets, i: int) -> float:
    """Angle au sommet `i` du contour, en degrés, non orienté (un creux de trigon donne son supplément)."""
    n = len(sommets)
    v, a, b = sommets[i], sommets[(i - 1) % n], sommets[(i + 1) % n]
    ua = (a[0] - v[0], a[1] - v[1])
    ub = (b[0] - v[0], b[1] - v[1])
    na, nb = max(math.hypot(*ua), 1e-9), max(math.hypot(*ub), 1e-9)
    cos = max(-1.0, min(1.0, (ua[0] * ub[0] + ua[1] * ub[1]) / (na * nb)))
    return math.degrees(math.acos(cos))


def coin_actif(sommets) -> int:
    """Le coin qui travaille : celui dont l'angle est le plus aigu, c'est lui qui porte le rayon de bec.

    Une plaquette en losange a deux coins aigus et deux obtus : seuls les aigus coupent. À égalité (carré,
    triangle, trigon), on retient le plus à gauche, puis le plus haut, pour que le dessin soit stable.
    """
    if not sommets:
        return -1
    angles = [angle_interieur(sommets, i) for i in range(len(sommets))]
    plus_aigu = min(angles)
    candidats = [i for i, a in enumerate(angles) if a <= plus_aigu + 1e-6]
    return min(candidats, key=lambda i: (round(sommets[i][0], 6), round(sommets[i][1], 6)))


@dataclass(frozen=True)
class Plaquette:
    """Une taille de plaquette. `arete` est la longueur d'arête, ou la largeur pour une plaquette de gorge."""
    designation: str
    base: str                # « CNMG 1204 » : relie la plaquette aux porte-plaquettes qui l'acceptent
    forme: str
    famille: str
    depouille: float         # degrés ; 0 = plaquette négative
    tolerance: str
    type_iso: str            # lettre ISO du type (trou, brise-copeaux)
    arete: float             # mm ; largeur de coupe pour une plaquette de gorge
    cercle_inscrit: float    # mm ; diamètre pour une plaquette ronde
    epaisseur: float         # mm
    rayon_bec: float         # mm ; rayon de la plaquette ronde pour la forme R
    usage: str
    pas: str = ""            # plaquettes de filetage : plage de pas praticable

    @staticmethod
    def nombre(valeur: float) -> str:
        """Un nombre à la française : virgule décimale, zéros inutiles enlevés."""
        return f"{valeur:g}".replace(".", ",")

    @property
    def texte_forme(self) -> str:
        return FORMES_PLAQUETTE.get(self.forme, "")

    @property
    def texte_arete(self) -> str:
        return self.nombre(self.arete)

    @property
    def texte_epaisseur(self) -> str:
        return self.nombre(self.epaisseur)

    @property
    def texte_cercle(self) -> str:
        return self.nombre(self.cercle_inscrit)

    @property
    def texte_depouille(self) -> str:
        return f"{self.depouille:g}°"

    @property
    def texte_rayon(self) -> str:
        return self.nombre(self.rayon_bec)

    @property
    def texte_type(self) -> str:
        return TYPES_ISO.get(self.type_iso, "référence du commerce")

    def description(self) -> str:
        bouts = [self.usage, f"{self.texte_forme}, dépouille {self.texte_depouille}"]
        if self.famille == "gorge":
            bouts.append(f"Largeur de coupe {self.texte_arete} mm, rayon de bec {self.texte_rayon} mm")
        elif self.famille == "filetage":
            bouts.append(f"Pas {self.pas}" if self.pas else "Profil de filet")
        else:
            bouts.append(f"Arête {self.texte_arete} mm, cercle inscrit {self.texte_cercle} mm, "
                         f"rayon de bec {self.texte_rayon} mm")
        bouts.append(f"Épaisseur {self.texte_epaisseur} mm")
        if self.type_iso in TYPES_ISO:
            bouts.append(f"Type {self.type_iso} : {self.texte_type}")
        bouts.append("ISO 1832" if self.type_iso in TYPES_ISO else "Référence du commerce (hors ISO)")
        return "\n".join(bouts)


def _ajouter(cat: List[Plaquette], base: str, forme: str, famille: str, depouille: float, tolerance: str,
             type_iso: str, arete: float, cercle: float, epaisseur: float, rayons, usage: str,
             pas: str = "") -> None:
    """Une ligne par rayon de bec : la désignation complète est la base suivie du code du rayon, en
    dixièmes de millimètre. Une plaquette ronde n'a pas de bec à elle : son code est « 00 »."""
    for r in rayons:
        code = "00" if forme == "R" else f"{round(r * 10):02d}"
        cat.append(Plaquette(f"{base}{code}", base, forme, famille, depouille, tolerance, type_iso,
                             arete, cercle, epaisseur, r, usage, pas))


def _construire() -> List[Plaquette]:
    cat: List[Plaquette] = []

    # -- négatives : deux faces, arête robuste, pour l'ébauche --------------------------------------
    _ajouter(cat, "CNMG 1204", "C", "negative", 0.0, "M", "G", 12.9, 12.7, 4.76, (0.4, 0.8, 1.2),
             "Chariotage et dressage d'ébauche : la plaquette la plus courante du tournage.")
    _ajouter(cat, "CNMG 0904", "C", "negative", 0.0, "M", "G", 9.7, 9.525, 4.76, (0.4, 0.8),
             "Même forme en petite taille : alésage et pièces courtes.")
    _ajouter(cat, "DNMG 1504", "D", "negative", 0.0, "M", "G", 15.5, 12.7, 4.76, (0.4, 0.8, 1.2),
             "Ébauche avec dégagement : épaulements et copiage léger.")
    _ajouter(cat, "WNMG 0804", "W", "negative", 0.0, "M", "G", 8.7, 12.7, 4.76, (0.4, 0.8, 1.2),
             "Six arêtes : la plus économique des plaquettes d'ébauche.")
    _ajouter(cat, "TNMG 1604", "T", "negative", 0.0, "M", "G", 16.5, 9.525, 4.76, (0.4, 0.8, 1.2),
             "Trois arêtes, bon dégagement : chariotage et dressage.")
    _ajouter(cat, "SNMG 1204", "S", "negative", 0.0, "M", "G", 12.7, 12.7, 4.76, (0.4, 0.8, 1.2),
             "Quatre arêtes et un angle de pointe droit : grandes profondeurs de passe à 45° ou 75°.")
    _ajouter(cat, "VNMG 1604", "V", "negative", 0.0, "M", "G", 16.6, 9.525, 4.76, (0.4, 0.8),
             "Pointe fine : profilage et formes en négatif.")
    _ajouter(cat, "RNMG 1204", "R", "negative", 0.0, "M", "G", 12.7, 12.7, 4.76, (6.35,),
             "Plaquette ronde : congés, copiage et arête très résistante.")

    # -- positives : coupe libre, finition et pièces peu rigides ------------------------------------
    _ajouter(cat, "CCMT 0602", "C", "positive", 7.0, "M", "T", 6.45, 6.35, 2.38, (0.2, 0.4),
             "Finition des petits diamètres et alésage.")
    _ajouter(cat, "CCMT 09T3", "C", "positive", 7.0, "M", "T", 9.7, 9.525, 3.97, (0.4, 0.8),
             "Finition et semi-finition : la plaquette positive courante du tour.")
    _ajouter(cat, "CCMT 1204", "C", "positive", 7.0, "M", "T", 12.9, 12.7, 4.76, (0.4, 0.8),
             "Finition en grande taille : passes plus fortes.")
    _ajouter(cat, "DCMT 0702", "D", "positive", 7.0, "M", "T", 7.75, 6.35, 2.38, (0.2, 0.4),
             "Finition avec dégagement : fonds d'alésage et épaulements.")
    _ajouter(cat, "DCMT 11T3", "D", "positive", 7.0, "M", "T", 11.6, 9.525, 3.97, (0.4, 0.8),
             "Finition et copiage léger : losange 55° de taille courante.")
    _ajouter(cat, "VBMT 1103", "V", "positive", 5.0, "M", "T", 11.0, 6.35, 3.18, (0.2, 0.4),
             "Profilage intérieur : pointe fine, petite taille.")
    _ajouter(cat, "VBMT 1604", "V", "positive", 5.0, "M", "T", 16.6, 9.525, 4.76, (0.4, 0.8),
             "Profilage et formes : pointe à 35°, le copiage extérieur.")
    _ajouter(cat, "TCMT 1102", "T", "positive", 7.0, "M", "T", 11.0, 6.35, 2.38, (0.2, 0.4),
             "Alésage et dressage de fond en petite taille.")
    _ajouter(cat, "TCMT 16T3", "T", "positive", 7.0, "M", "T", 16.5, 9.525, 3.97, (0.4, 0.8),
             "Dressage et chariotage en triangle positif.")
    _ajouter(cat, "SCMT 1204", "S", "positive", 7.0, "M", "T", 12.7, 12.7, 4.76, (0.4, 0.8),
             "Chariotage, dressage et chanfreins à 45° en positif.")
    _ajouter(cat, "RCMT 10T3", "R", "positive", 7.0, "M", "T", 10.0, 10.0, 3.97, (5.0,),
             "Plaquette ronde positive : congés et formes, surface très propre.")

    # -- filetage : plaquettes couchées, profil du filet --------------------------------------------
    for sens, main in (("ER", "à droite"), ("EL", "à gauche")):
        cat.append(Plaquette(f"16{sens} AG60", f"16{sens}", "filetage", "filetage", 0.0, "", "commerce",
                             16.5, 9.525, 3.97, 0.1,
                             f"Filetage extérieur {main}, profil partiel 60° : un même outil pour tous les pas.",
                             "0,5 à 3 mm"))
    for sens, main in (("IR", "à droite"), ("IL", "à gauche")):
        cat.append(Plaquette(f"16{sens} AG60", f"16{sens}", "filetage", "filetage", 0.0, "", "commerce",
                             16.5, 9.525, 3.97, 0.1,
                             f"Filetage intérieur {main}, profil partiel 60°.", "0,5 à 3 mm"))
    cat.append(Plaquette("11IR AG60", "11IR", "filetage", "filetage", 0.0, "", "commerce", 11.0, 6.35, 2.38, 0.1,
                         "Filetage intérieur des petits alésages, profil partiel 60°.", "0,5 à 1,5 mm"))
    cat.append(Plaquette("16ER 150ISO", "16ER", "filetage", "filetage", 0.0, "", "commerce", 16.5, 9.525, 3.97, 0.108,
                         "Filetage extérieur ISO métrique à profil complet : le sommet du filet est fini "
                         "par la plaquette, un pas par référence.", "1,5 mm"))

    # -- gorge et tronçonnage -----------------------------------------------------------------------
    for largeur, rayon in ((2.0, 0.2), (3.0, 0.2), (4.0, 0.4)):
        cat.append(Plaquette(f"MGMN {int(largeur * 100):03d}-G", f"MGMN {int(largeur * 100):03d}", "gorge",
                             "gorge", 7.0, "", "commerce", largeur, largeur, 5.0, rayon,
                             f"Gorge et tronçonnage, largeur de coupe {largeur:g} mm, deux arêtes."))
    return cat


CATALOGUE: List[Plaquette] = _construire()


def par_famille() -> Dict[str, List[Plaquette]]:
    groupes: Dict[str, List[Plaquette]] = {cle: [] for cle in FAMILLES}
    for pl in CATALOGUE:
        groupes[pl.famille].append(pl)
    return groupes


def pour_base(base: str) -> List[Plaquette]:
    """Les tailles disponibles pour une base. Accepte la forme notée dans le catalogue des porte-plaquettes :
    « CNMG 1204.. » comme « CNMG 1204 », et « 16ER / 16EL » qui en nomme deux."""
    racines = [m.replace(".", "").strip() for m in base.split("/")]
    racines = [r for r in racines if r]
    return [pl for pl in CATALOGUE if pl.base in racines]


def filtrer(texte: str, catalogue: Optional[List[Plaquette]] = None) -> List[Plaquette]:
    """Les plaquettes dont la désignation, la forme, le type ou l'usage contiennent chaque mot de `texte`."""
    source = CATALOGUE if catalogue is None else catalogue
    mots = [m for m in texte.lower().split() if m]
    if not mots:
        return list(source)
    retenus = []
    for pl in source:
        champs = " ".join((pl.designation, pl.base, pl.texte_forme, pl.usage, pl.texte_type, pl.pas,
                           FAMILLES[pl.famille], pl.texte_depouille, pl.texte_rayon)).lower()
        if all(m in champs for m in mots):
            retenus.append(pl)
    return retenus
