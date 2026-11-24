"""Machine, mandrin, contre-pointe, brut et prise de pièce : ce qui entoure le profil.

Repère : celui de la pièce. Z = 0 est la face avant finie (l'origine de l'esquisse), Z négatif vers le mandrin.
La prise de pièce se décrit depuis la face avant des mors : `depassement` est la distance entre cette face et
la face finie, `surepaisseur_face` ce qui dépasse de la face finie avant dressage. L'arrière du brut est donné par
son appui : sur l'épaulement d'un étage des mors ou sur la face du mandrin.

Les mors sont des mors durs étagés et réversibles. Numérotés depuis le bout (étage 1 au bout, le dernier au fond
contre la face du mandrin), chaque étage a une longueur le long de Z et, derrière lui, un épaulement : la marche
radiale vers l'étage suivant. Le mors est le plus épais au fond (`epaisseur_mors`) et s'amincit vers le bout
d'un épaulement par étage.

* Mors normaux : la face étagée regarde l'axe. En serrage extérieur, le brut s'appuie sur l'épaulement derrière
  l'étage qui le serre, ou sur la face du mandrin s'il traverse tous les étages. La face plate, dehors, peut
  serrer un tube par l'intérieur ; l'appui est alors forcément le mandrin.
* Mors retournés : la face étagée regarde dehors. Un tube serré par l'intérieur s'appuie sur l'épaulement derrière
  l'étage qui l'écarte, ou sur la face du mandrin. La face plate, vers l'axe, serre un gros brut par l'extérieur
  avec appui sur le mandrin.

Les dimensions du mandrin marquées « à vérifier » dans le dialogue viennent d'ordres de grandeur, pas de la
fiche constructeur : à relever sur le mandrin.
"""
from __future__ import annotations

import copy
import json
from dataclasses import asdict, dataclass, field, fields
from typing import Any, Dict, List, Tuple

from .esquisse.modele import ErreurEsquisse, Esquisse

FORMAT_PIECE = "ctgraph-piece"
VERSION_PIECE = 1

SERRAGES = ("exterieur", "interieur")


@dataclass
class Machine:
    nom: str = "Cazeneuve CT200"
    commande: str = "NUM 750 T"
    course_z: float = 500.0          # à relever sur la machine
    course_x: float = 200.0          # diamètre maximal usinable, à relever
    broche_max: float = 3000.0       # tr/min, à relever
    changement_outil_z: float = 150.0   # position de changement d'outil, repère pièce, à relever
    changement_outil_x: float = 250.0   # diamètre


@dataclass
class Etage:
    longueur: float = 20.0           # le long de Z
    epaulement: float = 8.0          # marche radiale derrière cet étage (sans objet pour le dernier, au fond)


def _etages_par_defaut() -> List[Etage]:
    return [Etage(20.0, 8.0), Etage(20.0, 8.0), Etage(30.0, 0.0)]     # à vérifier sur les mors 474


PASSAGE_MANDRIN = 42.0   # passage de barre du 210 BH-FC, relevé par l'utilisateur : une caractéristique, pas un réglage


@dataclass
class Mandrin:
    modele: str = "SMW-Autoblok 210 BH-FC"
    reference: str = "210 BH-FC"                   # gravée sur le mandrin, rappelée sur le dessin
    mors_modele: str = "SMW-Autoblok 474"
    mors_reference: str = "12082030 (1/16\"x90°)"  # gravée sur les mors (dentelure 1/16\" × 90°)
    diametre: float = 210.0
    longueur_corps: float = 90.0     # à vérifier
    nb_mors: int = 3
    largeur_mors: float = 30.0       # à vérifier
    epaisseur_mors: float = 40.0     # épaisseur radiale du mors au fond, à vérifier
    etages: List[Etage] = field(default_factory=_etages_par_defaut)   # depuis le bout

    @property
    def alesage(self) -> float:
        """Passage de barre : fixé par le mandrin, affiché mais pas réglable."""
        return PASSAGE_MANDRIN

    def nb_etages(self) -> int:
        return len(self.etages)

    def hauteur_mors(self) -> float:
        """Longueur des mors devant la face du mandrin : la somme des étages."""
        return sum(e.longueur for e in self.etages)

    def epaisseur_etage(self, k: int) -> float:
        """Épaisseur radiale de l'étage k (1 = bout) : celle du fond moins les épaulements qui le séparent du fond."""
        return self.epaisseur_mors - sum(e.epaulement for e in self.etages[k - 1:-1])


@dataclass
class ContrePointe:
    presente: bool = False
    angle: float = 60.0
    diametre: float = 20.0           # diamètre de la pointe à sa base
    longueur: float = 40.0           # longueur de pointe dessinée


@dataclass
class Brut:
    forme: str = "rond"              # "rond" (plein) ou "tube"
    diametre: float = 60.0
    diametre_interieur: float = 0.0  # tube seulement
    matiere: str = "acier"


@dataclass
class PriseDePiece:
    depassement: float = 100.0       # face avant des mors -> face finie (Z = 0)
    surepaisseur_face: float = 2.0   # brut au-delà de la face finie
    serrage: str = "exterieur"       # "exterieur" : les mors serrent le brut par l'extérieur ;
                                     # "interieur" : ils s'écartent dans l'alésage d'un tube
    mors_retournes: bool = False     # face étagée vers l'axe (False) ou vers l'extérieur (True)
    appui: int = 1                   # 0 : face du mandrin ; k : épaulement derrière l'étage k (depuis le bout)


def _depuis_dict(cls, d: Dict[str, Any]):
    """Instancie une dataclass depuis un dict en ignorant les clés inconnues (fichiers plus récents ou anciens)."""
    noms = {f.name: f.type for f in fields(cls)}
    valeurs = {}
    for nom, valeur in (d or {}).items():
        if nom in noms:
            valeurs[nom] = valeur
    try:
        return cls(**valeurs)
    except TypeError as exc:
        raise ErreurEsquisse(f"{cls.__name__} : {exc}") from exc


def _mandrin_depuis_dict(d: Dict[str, Any]) -> Mandrin:
    m = _depuis_dict(Mandrin, d)
    m.etages = [e if isinstance(e, Etage) else _depuis_dict(Etage, e) for e in (m.etages or [])] or _etages_par_defaut()
    return m


@dataclass
class Montage:
    machine: Machine = field(default_factory=Machine)
    mandrin: Mandrin = field(default_factory=Mandrin)
    contre_pointe: ContrePointe = field(default_factory=ContrePointe)
    brut: Brut = field(default_factory=Brut)
    prise: PriseDePiece = field(default_factory=PriseDePiece)

    # -- géométrie dérivée, repère pièce ----------------------------------------------

    def z_face_mors(self) -> float:
        return -self.prise.depassement

    def z_face_mandrin(self) -> float:
        return self.z_face_mors() - self.mandrin.hauteur_mors()

    def z_fond_mors(self) -> float:
        return self.z_face_mandrin()

    def z_arriere_mandrin(self) -> float:
        return self.z_face_mandrin() - self.mandrin.longueur_corps

    def z_fond_etage(self, k: int) -> float:
        """L'arrière de l'étage k (1 = bout) ; k = 0 est la face des mors."""
        return self.z_face_mors() - sum(e.longueur for e in self.mandrin.etages[:k])

    def z_appui(self) -> float:
        """Où s'appuie l'arrière du brut : face du mandrin ou épaulement derrière l'étage `appui`."""
        return self.z_face_mandrin() if self.prise.appui <= 0 else self.z_fond_etage(self.prise.appui)

    def z_brut_avant(self) -> float:
        return self.prise.surepaisseur_face

    def z_brut_arriere(self) -> float:
        return self.z_appui()

    def profondeur_prise(self) -> float:
        """Longueur de brut engagée dans les mors, de leur face à l'appui."""
        return self.z_face_mors() - self.z_appui()

    def longueur_brut(self) -> float:
        return self.z_brut_avant() - self.z_brut_arriere()

    def rayon_brut(self) -> float:
        return self.brut.diametre / 2.0

    def rayon_interieur_brut(self) -> float:
        return self.brut.diametre_interieur / 2.0 if self.brut.forme == "tube" else 0.0

    def rayon_contact(self) -> float:
        """Le rayon du brut touché par les mors : extérieur, ou l'alésage du tube."""
        return self.rayon_interieur_brut() if self.prise.serrage == "interieur" else self.rayon_brut()

    def face_etagee_en_contact(self) -> bool:
        """Mors normaux en serrage extérieur, ou retournés en serrage intérieur : c'est la face étagée qui serre."""
        return self.prise.mors_retournes == (self.prise.serrage == "interieur")

    def etage_de_serrage(self) -> int:
        """L'étage qui touche le brut (1 = bout) : celui de l'appui, ou le fond quand le brut va jusqu'au mandrin."""
        n = self.mandrin.nb_etages()
        if self.face_etagee_en_contact() and 1 <= self.prise.appui <= n:
            return self.prise.appui
        return n

    def blocs_mors(self) -> List[Tuple[float, float, float, float]]:
        """Les blocs (z1, z2, r1, r2) d'un mors, un par étage depuis le bout. Le mors est placé radialement pour que
        la face qui serre touche le brut ; la face plate est dehors (mors normaux) ou vers l'axe (retournés)."""
        md, p = self.mandrin, self.prise
        n = md.nb_etages()
        k = self.etage_de_serrage()
        rc = self.rayon_contact()
        ek = md.epaisseur_etage(k)
        if not p.mors_retournes:
            plat = rc + ek if self.face_etagee_en_contact() else rc       # rayon de la face plate, dehors
            return [(self.z_fond_etage(i), self.z_fond_etage(i - 1), max(plat - md.epaisseur_etage(i), 0.0), plat)
                    for i in range(1, n + 1)]
        plat = max(rc - ek, 0.0) if self.face_etagee_en_contact() else rc    # face plate, vers l'axe
        return [(self.z_fond_etage(i), self.z_fond_etage(i - 1), plat, plat + md.epaisseur_etage(i))
                for i in range(1, n + 1)]

    def profil_mors(self) -> List[Tuple[float, float]]:
        """Le contour (z, r) d'un mors dans le plan de l'esquisse : la face plate, puis l'escalier des étages."""
        blocs = self.blocs_mors()
        if not blocs:
            return []
        plat = blocs[0][3] if not self.prise.mors_retournes else blocs[0][2]
        pts = [(self.z_face_mandrin(), plat), (self.z_face_mors(), plat)]
        for (z1, z2, r1, r2) in blocs:
            marche = r1 if not self.prise.mors_retournes else r2
            pts += [(z2, marche), (z1, marche)]
        return pts

    # -- prise de pièce : réglages faits directement sur le mors ----------------------------

    def _modifier(self, modification) -> None:
        """Applique `modification` puis vérifie ; si la prise n'est pas réalisable, brut et prise reviennent
        à leur état d'avant et l'erreur est relevée."""
        brut, prise = copy.deepcopy(self.brut), copy.deepcopy(self.prise)
        try:
            modification()
            self.verifier()
        except ErreurEsquisse:
            self.brut, self.prise = brut, prise
            raise

    def _ajuster_appui(self) -> None:
        """Après un retournement ou un changement de serrage : l'appui reste s'il est réalisable, sinon le premier
        qui l'est, la face du mandrin d'abord puis les épaulements depuis le bout (un tube serré par l'intérieur
        n'accepte souvent que les étages minces du bout)."""
        actuel = self.prise.appui
        for appui in [actuel] + [a for a, _ in self.appuis_possibles() if a != actuel]:
            self.prise.appui = appui
            try:
                self.verifier()
                return
            except ErreurEsquisse:
                continue
        self.prise.appui = 0

    def retourner_mors(self) -> None:
        """Retourne les mors : la face étagée passe vers l'extérieur, ou revient vers l'axe."""
        def faire():
            self.prise.mors_retournes = not self.prise.mors_retournes
            self._ajuster_appui()
        self._modifier(faire)

    def definir_serrage(self, serrage: str) -> None:
        def faire():
            self.prise.serrage = serrage
            self._ajuster_appui()
        self._modifier(faire)

    def definir_appui(self, appui: int) -> None:
        def faire():
            self.prise.appui = int(appui)
        self._modifier(faire)

    def appuis_possibles(self) -> List[Tuple[int, str]]:
        """(valeur, libellé) des appuis : la face du mandrin, puis chaque épaulement si la face étagée serre."""
        out = [(0, "Face du mandrin")]
        if self.face_etagee_en_contact():
            out += [(k, f"Épaulement de l'étage {k}") for k in range(1, self.mandrin.nb_etages())]
        return out

    def description_prise(self) -> str:
        p = self.prise
        mors = "mors retournés" if p.mors_retournes else "mors normaux"
        serrage = "serrage intérieur" if p.serrage == "interieur" else "serrage extérieur"
        appui = "appui sur la face du mandrin" if p.appui <= 0 else f"appui sur l'épaulement de l'étage {p.appui}"
        return f"{mors}, {serrage} par l'étage {self.etage_de_serrage()}, {appui}"

    # -- les trois valeurs du brut affichées et éditables dans l'esquisse ----------------------

    CLES_BRUT = ("diametre", "longueur", "marge")
    LIBELLES_BRUT = {"diametre": "Diamètre du brut", "longueur": "Longueur du brut",
                     "marge": "Marge en bout (face brute → face finie)"}

    def valeur_brut(self, cle: str) -> float:
        if cle == "diametre":
            return self.brut.diametre
        if cle == "longueur":
            return self.longueur_brut()
        if cle == "marge":
            return self.prise.surepaisseur_face
        raise ErreurEsquisse(f"valeur de brut inconnue : {cle}")

    def definir_valeur_brut(self, cle: str, valeur: float) -> None:
        """Change une des trois valeurs. La longueur se répartit sur le dépassement : la prise dans les mors et
        la marge en bout ne bougent pas, c'est la pièce qui avance ou recule dans le brut."""
        if cle not in self.CLES_BRUT:
            raise ErreurEsquisse(f"valeur de brut inconnue : {cle}")

        def faire():
            if cle == "diametre":
                self.brut.diametre = float(valeur)
            elif cle == "longueur":
                self.prise.depassement = float(valeur) - self.profondeur_prise() - self.prise.surepaisseur_face
            else:
                self.prise.surepaisseur_face = float(valeur)
        self._modifier(faire)

    def texte_brut(self, cle: str) -> str:
        v = self.valeur_brut(cle)
        texte = f"{v:.2f}".rstrip("0").rstrip(".")
        return {"diametre": "Ø brut ", "longueur": "L brut ", "marge": "marge "}[cle] + texte

    def verifier(self) -> None:
        """Lève ErreurEsquisse si le mors ou la prise de pièce ne sont pas réalisables."""
        p, m, b = self.prise, self.mandrin, self.brut
        if not m.etages:
            raise ErreurEsquisse("le mors doit avoir au moins un étage")
        if any(e.longueur <= 0 for e in m.etages) or any(e.epaulement < 0 for e in m.etages):
            raise ErreurEsquisse("chaque étage a une longueur positive et un épaulement nul ou positif")
        if m.epaisseur_etage(1) <= 0:
            raise ErreurEsquisse("les épaulements mangent toute l'épaisseur du mors : le bout n'a plus de matière")
        if b.diametre <= 0:
            raise ErreurEsquisse("le diamètre du brut doit être positif")
        if b.forme == "tube" and not 0 < b.diametre_interieur < b.diametre:
            raise ErreurEsquisse("le diamètre intérieur du tube doit être entre 0 et le diamètre extérieur")
        if p.depassement < 0 or p.surepaisseur_face < 0:
            raise ErreurEsquisse("dépassement et surépaisseur ne peuvent pas être négatifs")
        if b.diametre > m.diametre:
            raise ErreurEsquisse("le brut est plus gros que le mandrin")
        if p.serrage not in SERRAGES:
            raise ErreurEsquisse("serrage : « exterieur » ou « interieur »")
        if p.serrage == "interieur" and b.forme != "tube":
            raise ErreurEsquisse("le serrage intérieur demande un brut en tube")
        if not 0 <= p.appui < m.nb_etages():
            raise ErreurEsquisse("l'appui est la face du mandrin (0) ou l'épaulement derrière un étage avant le fond")
        if p.appui >= 1 and not self.face_etagee_en_contact():
            raise ErreurEsquisse("la face plate des mors serre le brut : l'appui ne peut être que la face du mandrin")
        if p.serrage == "interieur":
            k = self.etage_de_serrage()
            if self.rayon_contact() - m.epaisseur_etage(k) < 0:
                raise ErreurEsquisse(f"les mors ne tiennent pas dans l'alésage du tube (étage {k} trop épais)")

    def to_dict(self) -> dict:
        return {
            "machine": asdict(self.machine), "mandrin": asdict(self.mandrin),
            "contre_pointe": asdict(self.contre_pointe), "brut": asdict(self.brut), "prise": asdict(self.prise),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Montage":
        d = d or {}
        return cls(machine=_depuis_dict(Machine, d.get("machine")), mandrin=_mandrin_depuis_dict(d.get("mandrin")),
                   contre_pointe=_depuis_dict(ContrePointe, d.get("contre_pointe")),
                   brut=_depuis_dict(Brut, d.get("brut")), prise=_depuis_dict(PriseDePiece, d.get("prise")))


@dataclass
class Piece:
    """Le document enregistré : l'esquisse et son montage."""
    esquisse: Esquisse = field(default_factory=Esquisse)
    montage: Montage = field(default_factory=Montage)

    def to_dict(self) -> dict:
        return {"format": FORMAT_PIECE, "version": VERSION_PIECE,
                "esquisse": self.esquisse.to_dict(), "montage": self.montage.to_dict()}

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=1)

    @classmethod
    def from_dict(cls, d: dict) -> "Piece":
        if not isinstance(d, dict):
            raise ErreurEsquisse("ce fichier n'est pas une pièce CTgraph")
        if d.get("format") == FORMAT_PIECE:
            if int(d.get("version", 0)) > VERSION_PIECE:
                raise ErreurEsquisse("pièce enregistrée par une version plus récente de CTgraph")
            return cls(Esquisse.from_dict(d.get("esquisse") or {}), Montage.from_dict(d.get("montage")))
        # ancien format : l'esquisse seule
        return cls(Esquisse.from_dict(d), Montage())

    @classmethod
    def from_json(cls, texte: str) -> "Piece":
        try:
            d = json.loads(texte)
        except ValueError as exc:
            raise ErreurEsquisse(f"fichier illisible : {exc}") from exc
        return cls.from_dict(d)
