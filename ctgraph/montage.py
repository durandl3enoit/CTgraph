"""Machine, mandrin, contre-pointe, brut et prise de pièce : ce qui entoure le profil.

Repère : celui de la pièce. Z = 0 est la face avant finie (l'origine de l'esquisse), Z négatif vers le mandrin.
La prise de pièce se décrit depuis la face avant des mors : `depassement` est la distance entre cette face et
la face finie, `prise_mors` la longueur de brut serrée dans les mors, `surepaisseur_face` ce qui dépasse de la
face finie avant dressage. Le brut va donc de Z = +surepaisseur_face à Z = -(depassement + prise_mors).

Les dimensions du mandrin marquées « à vérifier » dans le dialogue viennent d'ordres de grandeur, pas de la
fiche constructeur : à relever sur le mandrin.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, fields
from typing import Any, Dict

from .esquisse.modele import ErreurEsquisse, Esquisse

FORMAT_PIECE = "ctgraph-piece"
VERSION_PIECE = 1


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
class Mandrin:
    modele: str = "SMW-Autoblok BH-M 210"
    mors_modele: str = "SMW-Autoblok 474"
    diametre: float = 210.0
    longueur_corps: float = 90.0     # à vérifier
    alesage: float = 52.0            # passage de barre, à vérifier
    nb_mors: int = 3
    hauteur_mors: float = 70.0       # longueur des mors devant la face du mandrin, à vérifier
    largeur_mors: float = 30.0       # à vérifier
    epaisseur_mors: float = 25.0     # épaisseur radiale au-delà du brut, à vérifier


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
    prise_mors: float = 20.0         # longueur serrée dans les mors
    surepaisseur_face: float = 2.0   # brut au-delà de la face finie


def _depuis_dict(cls, d: Dict[str, Any]):
    """Instancie une dataclass depuis un dict en ignorant les clés inconnues (fichiers plus récents)."""
    noms = {f.name: f.type for f in fields(cls)}
    valeurs = {}
    for nom, valeur in (d or {}).items():
        if nom in noms:
            valeurs[nom] = valeur
    try:
        return cls(**valeurs)
    except TypeError as exc:
        raise ErreurEsquisse(f"{cls.__name__} : {exc}") from exc


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

    def z_fond_mors(self) -> float:
        return self.z_face_mors() - self.mandrin.hauteur_mors

    def z_face_mandrin(self) -> float:
        return self.z_fond_mors()

    def z_arriere_mandrin(self) -> float:
        return self.z_face_mandrin() - self.mandrin.longueur_corps

    def z_brut_avant(self) -> float:
        return self.prise.surepaisseur_face

    def z_brut_arriere(self) -> float:
        return self.z_face_mors() - self.prise.prise_mors

    def longueur_brut(self) -> float:
        return self.z_brut_avant() - self.z_brut_arriere()

    def rayon_brut(self) -> float:
        return self.brut.diametre / 2.0

    def rayon_interieur_brut(self) -> float:
        return self.brut.diametre_interieur / 2.0 if self.brut.forme == "tube" else 0.0

    def verifier(self) -> None:
        """Lève ErreurEsquisse si la prise de pièce n'est pas réalisable."""
        p, m, b = self.prise, self.mandrin, self.brut
        if b.diametre <= 0:
            raise ErreurEsquisse("le diamètre du brut doit être positif")
        if b.forme == "tube" and not 0 < b.diametre_interieur < b.diametre:
            raise ErreurEsquisse("le diamètre intérieur du tube doit être entre 0 et le diamètre extérieur")
        if p.prise_mors <= 0 or p.prise_mors > m.hauteur_mors:
            raise ErreurEsquisse("la prise dans les mors doit être positive et ne pas dépasser la hauteur des mors")
        if p.depassement < 0 or p.surepaisseur_face < 0:
            raise ErreurEsquisse("dépassement et surépaisseur ne peuvent pas être négatifs")
        if b.diametre > m.diametre:
            raise ErreurEsquisse("le brut est plus gros que le mandrin")

    def to_dict(self) -> dict:
        return {
            "machine": asdict(self.machine), "mandrin": asdict(self.mandrin),
            "contre_pointe": asdict(self.contre_pointe), "brut": asdict(self.brut), "prise": asdict(self.prise),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Montage":
        d = d or {}
        return cls(machine=_depuis_dict(Machine, d.get("machine")), mandrin=_depuis_dict(Mandrin, d.get("mandrin")),
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
