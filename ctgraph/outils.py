"""Stock d'outils de l'atelier : les porte-plaquettes montables sur le CT200.

La tourelle reçoit des porte-outils **VDI 30** (DIN 69880). Les porte-outils radiaux y prennent une queue
carrée de 16 × 16 ou 20 × 20, les porte-outils à alésage une queue cylindrique jusqu'à Ø 20 : `QUEUE_MAXI`
borne donc ce catalogue.

Les désignations suivent l'**ISO 5608** pour les outils à queue carrée et l'**ISO 6261** pour les barres
d'alésage. Les outils de gorge, de tronçonnage et de filetage n'ont pas tous de code normalisé : leurs
références sont celles du commerce, signalées comme telles.

Lecture d'un code ISO 5608, par exemple `SDJCR 2020 K11` :

* `S` fixation de la plaquette : S vis, P levier, M bride + goupille, D bride supérieure + goupille, C bride ;
* `D` forme de la plaquette : C losange 80°, D losange 55°, S carré, T triangle, V losange 35°, W trigon 80°, R rond ;
* `J` angle d'attaque : J 93°, L 95°, F 90°, G 91°, N 63°, Q 107,5°, S 45°, B 75°, V 72,5°, D 45° ;
* `C` dépouille de la plaquette : N 0° (négative), C 7°, P 11° (positives) ;
* `R` main : R droite, L gauche, N neutre ;
* `2020` hauteur et largeur de la queue en millimètres ;
* `K` longueur de l'outil : H 100, K 125, M 150 ;
* `11` taille de la plaquette.

Pour une barre `S16Q-SDUCR 11` : `S` queue acier (A avec arrosage intérieur), `16` diamètre de queue,
`Q` longueur (K 125, M 150, Q 180, R 200), puis le code de la tête comme ci-dessus.

Ce catalogue dit ce qu'il est **possible** de monter, pas ce que l'atelier possède : c'est la case
« en stock » de la zone Outils qui le note, atelier par atelier.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from .plaquettes import FORMES_PLAQUETTE, forme_plaquette   # noqa: F401  (réexportés : la forme vient des plaquettes)

QUEUE_MAXI = 20.0        # VDI 30 : queue carrée 20 × 20 ou queue cylindrique Ø 20 au plus

FAMILLES: Dict[str, str] = {
    "ext_neg": "Extérieur — plaquette négative (ébauche)",
    "ext_pos": "Extérieur — plaquette positive (finition)",
    "alesage": "Alésage — barres",
    "filetage": "Filetage",
    "gorge": "Gorge et tronçonnage",
}

MAINS = {"R": "droite", "L": "gauche", "N": "neutre"}


@dataclass(frozen=True)
class PortePlaquette:
    """Un porte-plaquette du catalogue. `attaque` est l'angle d'attaque κr, None s'il n'a pas de sens."""
    designation: str
    famille: str
    plaquette: str
    attaque: Optional[float]
    main: str
    queue: str              # « 20 × 20 » ou « Ø 16 »
    queue_mm: float
    longueur: float
    fixation: str
    norme: str
    usage: str
    alesage_mini: float = 0.0    # barres et outils intérieurs : plus petit alésage praticable
    forme: str = ""              # clé de `FORMES_PLAQUETTE` : la forme de la plaquette, pour l'icône

    @property
    def texte_forme(self) -> str:
        return FORMES_PLAQUETTE.get(self.forme, "")

    @property
    def texte_attaque(self) -> str:
        return "—" if self.attaque is None else f"{self.attaque:g}°".replace(".", ",")

    @property
    def texte_longueur(self) -> str:
        return f"{self.longueur:g} mm"

    def description(self) -> str:
        """Phrase d'infobulle : à quoi sert l'outil et ce qu'il demande."""
        forme = f" ({self.texte_forme.lower()})" if self.texte_forme else ""
        bouts = [self.usage, f"Plaquette {self.plaquette}{forme}", f"Fixation par {self.fixation}",
                 f"Queue {self.queue}, longueur {self.texte_longueur}", self.norme]
        if self.alesage_mini:
            bouts.insert(1, f"Alésage minimal {self.alesage_mini:g} mm")
        return "\n".join(bouts)


def _ajouter(cat: List[PortePlaquette], gabarit: str, famille: str, plaquette: str, attaque: Optional[float],
             queue_mm: float, longueur: float, fixation: str, norme: str, usage: str,
             mains: str = "RL", cylindrique: bool = False, alesage_mini: float = 0.0) -> None:
    """Ajoute une référence, une ligne par main : le gabarit porte « _ » à la place de la lettre de main."""
    queue = f"Ø {queue_mm:g}" if cylindrique else f"{queue_mm:g} × {queue_mm:g}"
    forme = forme_plaquette(plaquette)
    for lettre in mains:
        cat.append(PortePlaquette(gabarit.replace("_", lettre), famille, plaquette, attaque, MAINS[lettre],
                                  queue, queue_mm, longueur, fixation, norme, usage, alesage_mini, forme))


def _construire() -> List[PortePlaquette]:
    cat: List[PortePlaquette] = []
    iso5608, iso6261, commerce = "ISO 5608", "ISO 6261", "Référence du commerce (hors ISO)"

    # -- extérieur, plaquettes négatives : ébauche et chariotage lourd -----------------------------
    ebauche = "Ébauche et chariotage, plaquette négative à deux faces."
    _ajouter(cat, "PCLN_ 2020 K12", "ext_neg", "CNMG 1204..", 95.0, 20, 125, "levier", iso5608,
             ebauche + " Losange 80°, l'outil à tout faire de l'ébauche.")
    _ajouter(cat, "MCLN_ 2020 K12", "ext_neg", "CNMG 1204..", 95.0, 20, 125, "bride + goupille", iso5608,
             ebauche + " Même tête que le PCLN, bridage plus simple à entretenir.")
    _ajouter(cat, "DCLN_ 2020 K12", "ext_neg", "CNMG 1204..", 95.0, 20, 125, "bride dessus",
             iso5608, ebauche + " Bride dessus : copeau bien dégagé.")
    _ajouter(cat, "PDJN_ 2020 K15", "ext_neg", "DNMG 1504..", 93.0, 20, 125, "levier", iso5608,
             ebauche + " Losange 55° : dégagement pour les épaulements et le copiage léger.")
    _ajouter(cat, "MDJN_ 2020 K15", "ext_neg", "DNMG 1504..", 93.0, 20, 125, "bride + goupille", iso5608,
             ebauche + " Losange 55°, bridage simple.")
    _ajouter(cat, "MWLN_ 2020 K08", "ext_neg", "WNMG 0804..", 95.0, 20, 125, "bride + goupille", iso5608,
             ebauche + " Trigon 80° : six arêtes, le plus économique à l'arête.")
    _ajouter(cat, "DWLN_ 2020 K08", "ext_neg", "WNMG 0804..", 95.0, 20, 125, "bride dessus",
             iso5608, ebauche + " Trigon 80°, bride dessus.")
    _ajouter(cat, "MTJN_ 2020 K16", "ext_neg", "TNMG 1604..", 93.0, 20, 125, "bride + goupille", iso5608,
             ebauche + " Triangle : trois arêtes, dégagement correct.")
    _ajouter(cat, "PTFN_ 2020 K16", "ext_neg", "TNMG 1604..", 90.0, 20, 125, "levier", iso5608,
             "Dressage de face en négatif, triangle à 90°.")
    _ajouter(cat, "PTGN_ 2020 K16", "ext_neg", "TNMG 1604..", 91.0, 20, 125, "levier", iso5608,
             "Chariotage et dressage, triangle à 91°.")
    _ajouter(cat, "MSSN_ 2020 K12", "ext_neg", "SNMG 1204..", 45.0, 20, 125, "bride + goupille", iso5608,
             "Chariotage et dressage à 45°, chanfreins : plaquette carrée, quatre arêtes, arête très robuste.")
    _ajouter(cat, "MSKN_ 2020 K12", "ext_neg", "SNMG 1204..", 75.0, 20, 125, "bride + goupille", iso5608,
             "Chariotage à 75° en plaquette carrée : grande profondeur de passe.")
    _ajouter(cat, "MVJN_ 2020 K16", "ext_neg", "VNMG 1604..", 93.0, 20, 125, "bride + goupille", iso5608,
             "Profilage en négatif : losange 35°, pointe fine pour les formes.")
    _ajouter(cat, "CRDNN 2020 K12", "ext_neg", "RNMG 1204..", None, 20, 125, "bride", iso5608,
             "Plaquette ronde : congés, formes et copiage, arête très résistante.", mains="N")

    # -- extérieur, plaquettes positives : finition et formes ---------------------------------------
    _ajouter(cat, "SCLC_ 2020 K09", "ext_pos", "CCMT 09T3..", 95.0, 20, 125, "vis", iso5608,
             "Finition et semi-finition, l'outil extérieur courant du tour.")
    _ajouter(cat, "SCLC_ 1616 H09", "ext_pos", "CCMT 09T3..", 95.0, 16, 100, "vis", iso5608,
             "Même outil en queue 16 × 16, pour les porte-outils VDI 30 de petite section.")
    _ajouter(cat, "SCLC_ 2020 K12", "ext_pos", "CCMT 1204..", 95.0, 20, 125, "vis", iso5608,
             "Finition en plaquette 12 : passes plus fortes qu'en 09.")
    _ajouter(cat, "SDJC_ 2020 K11", "ext_pos", "DCMT 11T3..", 93.0, 20, 125, "vis", iso5608,
             "Finition et copiage léger : losange 55°, bon dégagement dans les épaulements.")
    _ajouter(cat, "SDJC_ 1616 H11", "ext_pos", "DCMT 11T3..", 93.0, 16, 100, "vis", iso5608,
             "Même outil en queue 16 × 16.")
    _ajouter(cat, "SDNCN 2020 K11", "ext_pos", "DCMT 11T3..", 62.5, 20, 125, "vis", iso5608,
             "Losange 55° monté neutre à 62,5° : travail dans les deux sens.", mains="N")
    _ajouter(cat, "SDQC_ 2020 K11", "ext_pos", "DCMT 11T3..", 107.5, 20, 125, "vis", iso5608,
             "Dressage en tirant et reprise d'arrière : attaque à 107,5°.")
    _ajouter(cat, "SVJC_ 2020 K16", "ext_pos", "VBMT 1604..", 93.0, 20, 125, "vis", iso5608,
             "Profilage et formes : losange 35°, pointe fine, copiage.")
    _ajouter(cat, "SVJC_ 1616 H16", "ext_pos", "VBMT 1604..", 93.0, 16, 100, "vis", iso5608,
             "Même outil de profilage en queue 16 × 16.")
    _ajouter(cat, "SVVCN 2020 K16", "ext_pos", "VBMT 1604..", 72.5, 20, 125, "vis", iso5608,
             "Profilage symétrique à 72,5° : formes attaquées des deux côtés.", mains="N")
    _ajouter(cat, "STFC_ 2020 K16", "ext_pos", "TCMT 16T3..", 90.0, 20, 125, "vis", iso5608,
             "Dressage de face en positif, triangle à 90°.")
    _ajouter(cat, "STGC_ 2020 K16", "ext_pos", "TCMT 16T3..", 91.0, 20, 125, "vis", iso5608,
             "Chariotage et dressage en triangle positif.")
    _ajouter(cat, "SSSC_ 2020 K12", "ext_pos", "SCMT 1204..", 45.0, 20, 125, "vis", iso5608,
             "Chariotage, dressage et chanfreins à 45° : plaquette carrée positive.")
    _ajouter(cat, "SSBC_ 2020 K12", "ext_pos", "SCMT 1204..", 75.0, 20, 125, "vis", iso5608,
             "Chariotage à 75° en plaquette carrée positive.")
    _ajouter(cat, "SRDCN 2020 K10", "ext_pos", "RCMT 10T3..", None, 20, 125, "vis", iso5608,
             "Plaquette ronde positive : congés et formes, surface très propre.", mains="N")

    # -- barres d'alésage ---------------------------------------------------------------------------
    _ajouter(cat, "S10K-SCLC_ 06", "alesage", "CCMT 0602..", 95.0, 10, 125, "vis", iso6261,
             "Alésage des petits diamètres.", cylindrique=True, alesage_mini=13.0)
    _ajouter(cat, "S12M-SCLC_ 06", "alesage", "CCMT 0602..", 95.0, 12, 150, "vis", iso6261,
             "Alésage courant des petits diamètres.", cylindrique=True, alesage_mini=15.0)
    _ajouter(cat, "S12M-SDUC_ 07", "alesage", "DCMT 0702..", 93.0, 12, 150, "vis", iso6261,
             "Alésage avec dégagement : fonds d'alésage et épaulements.", cylindrique=True, alesage_mini=16.0)
    _ajouter(cat, "S16Q-SCLC_ 09", "alesage", "CCMT 09T3..", 95.0, 16, 180, "vis", iso6261,
             "Barre d'alésage courante.", cylindrique=True, alesage_mini=20.0)
    _ajouter(cat, "S16Q-SDUC_ 07", "alesage", "DCMT 0702..", 93.0, 16, 180, "vis", iso6261,
             "Alésage avec dégagement, plaquette 07.", cylindrique=True, alesage_mini=20.0)
    _ajouter(cat, "S16Q-SDUC_ 11", "alesage", "DCMT 11T3..", 93.0, 16, 180, "vis", iso6261,
             "Alésage avec dégagement, plaquette 11 : passes plus fortes.", cylindrique=True, alesage_mini=22.0)
    _ajouter(cat, "S16Q-STFC_ 11", "alesage", "TCMT 1102..", 90.0, 16, 180, "vis", iso6261,
             "Alésage et dressage de fond à 90°.", cylindrique=True, alesage_mini=20.0)
    _ajouter(cat, "S16Q-SVUC_ 11", "alesage", "VBMT 1103..", 93.0, 16, 180, "vis", iso6261,
             "Profilage intérieur : losange 35°.", cylindrique=True, alesage_mini=20.0)
    _ajouter(cat, "S20R-SCLC_ 09", "alesage", "CCMT 09T3..", 95.0, 20, 200, "vis", iso6261,
             "Barre d'alésage de la plus grosse section tenue en VDI 30.", cylindrique=True, alesage_mini=25.0)
    _ajouter(cat, "S20R-SDUC_ 11", "alesage", "DCMT 11T3..", 93.0, 20, 200, "vis", iso6261,
             "Alésage avec dégagement en Ø 20.", cylindrique=True, alesage_mini=25.0)
    _ajouter(cat, "S20R-STFC_ 16", "alesage", "TCMT 16T3..", 90.0, 20, 200, "vis", iso6261,
             "Alésage et dressage de fond en Ø 20.", cylindrique=True, alesage_mini=25.0)
    _ajouter(cat, "S20R-SVUC_ 16", "alesage", "VBMT 1604..", 93.0, 20, 200, "vis", iso6261,
             "Profilage intérieur en Ø 20.", cylindrique=True, alesage_mini=25.0)
    _ajouter(cat, "S20R-MCLN_ 09", "alesage", "CNMG 0904..", 95.0, 20, 200, "bride + goupille", iso6261,
             "Alésage en plaquette négative : ébauche intérieure.", cylindrique=True, alesage_mini=25.0)
    _ajouter(cat, "S20R-PCLN_ 09", "alesage", "CNMG 0904..", 95.0, 20, 200, "levier", iso6261,
             "Alésage en plaquette négative, serrage par levier.", cylindrique=True, alesage_mini=25.0)
    _ajouter(cat, "A16Q-SCLC_ 09", "alesage", "CCMT 09T3..", 95.0, 16, 180, "vis", iso6261,
             "Barre à arrosage intérieur : évacuation du copeau dans les alésages profonds.",
             cylindrique=True, alesage_mini=20.0)
    _ajouter(cat, "A20R-SCLC_ 09", "alesage", "CCMT 09T3..", 95.0, 20, 200, "vis", iso6261,
             "Barre Ø 20 à arrosage intérieur.", cylindrique=True, alesage_mini=25.0)

    # -- filetage -------------------------------------------------------------------------------------
    _ajouter(cat, "SE_ 1616 H16", "filetage", "16ER / 16EL", None, 16, 100, "bride", commerce,
             "Filetage extérieur, plaquette couchée 16 : du pas 0,5 au pas 3.")
    _ajouter(cat, "SE_ 2020 K16", "filetage", "16ER / 16EL", None, 20, 125, "bride", commerce,
             "Filetage extérieur en queue 20 × 20.")
    _ajouter(cat, "SN_ 0012 M11", "filetage", "11IR / 11IL", None, 12, 150, "bride", commerce,
             "Filetage intérieur des petits alésages.", cylindrique=True, alesage_mini=16.0)
    _ajouter(cat, "SN_ 0016 Q16", "filetage", "16IR / 16IL", None, 16, 180, "bride", commerce,
             "Filetage intérieur, barre Ø 16.", cylindrique=True, alesage_mini=20.0)
    _ajouter(cat, "SN_ 0020 R16", "filetage", "16IR / 16IL", None, 20, 200, "bride", commerce,
             "Filetage intérieur, barre Ø 20.", cylindrique=True, alesage_mini=25.0)

    # -- gorge et tronçonnage ---------------------------------------------------------------------------
    _ajouter(cat, "MGEH_ 1616-2", "gorge", "MGMN 200", None, 16, 100, "vis", commerce,
             "Gorge extérieure et tronçonnage, largeur 2 mm, queue 16 × 16.")
    _ajouter(cat, "MGEH_ 2020-2", "gorge", "MGMN 200", None, 20, 125, "vis", commerce,
             "Gorge extérieure et tronçonnage, largeur 2 mm.")
    _ajouter(cat, "MGEH_ 2020-3", "gorge", "MGMN 300", None, 20, 125, "vis", commerce,
             "Gorge extérieure et tronçonnage, largeur 3 mm : plus de profondeur.")
    _ajouter(cat, "MGIV_ 2016-2", "gorge", "MGMN 200", None, 20, 160, "vis", commerce,
             "Gorge intérieure, barre Ø 20, largeur 2 mm.", cylindrique=True, alesage_mini=22.0)
    _ajouter(cat, "Porte-lame 2026", "gorge", "Lame 26 mm (GTN / ZQMX)", None, 20, 125, "bride", commerce,
             "Porte-lame de tronçonnage, queue 20 × 20, lame de 26 mm de hauteur : tronçonnage des gros "
             "diamètres et gorges profondes. La main est celle de la lame, pas du porte-lame.", mains="N")
    return cat


CATALOGUE: List[PortePlaquette] = _construire()


def par_famille() -> Dict[str, List[PortePlaquette]]:
    """Le catalogue rangé par famille, dans l'ordre de `FAMILLES`."""
    groupes: Dict[str, List[PortePlaquette]] = {cle: [] for cle in FAMILLES}
    for pp in CATALOGUE:
        groupes[pp.famille].append(pp)
    return groupes


def filtrer(texte: str, catalogue: Optional[List[PortePlaquette]] = None) -> List[PortePlaquette]:
    """Les porte-plaquettes dont la désignation, la plaquette, la queue ou l'usage contiennent chaque mot
    de `texte` (sans tenir compte de la casse ni des accents absents)."""
    source = CATALOGUE if catalogue is None else catalogue
    mots = [m for m in texte.lower().split() if m]
    if not mots:
        return list(source)
    retenus = []
    for pp in source:
        champs = " ".join((pp.designation, pp.plaquette, pp.queue, pp.usage, pp.main, pp.fixation,
                           FAMILLES[pp.famille], pp.texte_attaque, pp.texte_forme)).lower()
        if all(m in champs for m in mots):
            retenus.append(pp)
    return retenus
