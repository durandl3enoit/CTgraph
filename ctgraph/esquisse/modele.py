"""Modèle d'esquisse : points, lignes, arcs, relations et cotes. C'est ce qui est enregistré.

Repère : le demi-profil est dans le plan (Z, X). `z` est l'abscisse le long de l'axe de la pièce,
`x` est la distance à l'axe, c'est-à-dire le rayon. Les cotes de diamètre valent 2 × x.

Ce module ne connaît pas le solveur : il décrit, valide et sérialise. L'adaptateur `solveur.py`
le traduit pour PlaneGCS.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Iterable, List, Optional, Tuple

FORMAT = "ctgraph-esquisse"
VERSION_FORMAT = 1


class TypeRelation(str, Enum):
    COINCIDENT = "coincident"            # (point, point)
    HORIZONTAL = "horizontal"            # (ligne) ou (point, point) : même x
    VERTICAL = "vertical"                # (ligne) ou (point, point) : même z
    PARALLELE = "parallele"              # (ligne, ligne)
    PERPENDICULAIRE = "perpendiculaire"  # (ligne, ligne)
    TANGENT = "tangent"                  # (ligne, arc) ou (arc, arc)
    EGAL = "egal"                        # (ligne, ligne) longueurs ou (arc, arc) rayons
    POINT_SUR_LIGNE = "point_sur_ligne"  # (point, ligne)
    POINT_SUR_ARC = "point_sur_arc"      # (point, arc)
    SUR_AXE = "sur_axe"                  # (point) : x = 0
    ORIGINE_Z = "origine_z"              # (point) : z = 0, la face d'origine de la pièce
    FIXE = "fixe"                        # (point) : z et x figés


class TypeCote(str, Enum):
    LONGUEUR_Z = "longueur_z"  # (point, point) ou (ligne) : écart selon Z
    DIAMETRE = "diametre"      # (point) ou (ligne) : 2 × x
    RAYON = "rayon"            # (arc)
    ANGLE = "angle"            # (ligne) par rapport à l'axe Z, ou (ligne, ligne) ; en degrés
    DISTANCE = "distance"      # (point, point) ou (ligne) : distance vraie
    ECART = "ecart"            # (ligne, ligne) parallèles : distance perpendiculaire (profondeur de gorge…)
    POSITION_Z = "position_z"  # (point) ou (ligne) : coordonnée z depuis l'origine de la pièce, signée


LIBELLES_RELATION: Dict[TypeRelation, str] = {
    TypeRelation.COINCIDENT: "Coïncident",
    TypeRelation.HORIZONTAL: "Horizontal",
    TypeRelation.VERTICAL: "Vertical",
    TypeRelation.PARALLELE: "Parallèle",
    TypeRelation.PERPENDICULAIRE: "Perpendiculaire",
    TypeRelation.TANGENT: "Tangent",
    TypeRelation.EGAL: "Égal",
    TypeRelation.POINT_SUR_LIGNE: "Point sur ligne",
    TypeRelation.POINT_SUR_ARC: "Point sur arc",
    TypeRelation.SUR_AXE: "Sur l'axe",
    TypeRelation.ORIGINE_Z: "Origine Z",
    TypeRelation.FIXE: "Fixe",
}

LIBELLES_COTE: Dict[TypeCote, str] = {
    TypeCote.LONGUEUR_Z: "Longueur Z",
    TypeCote.DIAMETRE: "Diamètre",
    TypeCote.RAYON: "Rayon",
    TypeCote.ANGLE: "Angle",
    TypeCote.DISTANCE: "Distance",
    TypeCote.ECART: "Écart",
    TypeCote.POSITION_Z: "Position Z",
}

# Formes acceptées : suites de genres d'éléments, dans l'ordre donné.
_FORMES_RELATION: Dict[TypeRelation, List[Tuple[str, ...]]] = {
    TypeRelation.COINCIDENT: [("point", "point")],
    TypeRelation.HORIZONTAL: [("ligne",), ("point", "point")],
    TypeRelation.VERTICAL: [("ligne",), ("point", "point")],
    TypeRelation.PARALLELE: [("ligne", "ligne")],
    TypeRelation.PERPENDICULAIRE: [("ligne", "ligne")],
    TypeRelation.TANGENT: [("ligne", "arc"), ("arc", "ligne"), ("arc", "arc")],
    TypeRelation.EGAL: [("ligne", "ligne"), ("arc", "arc"), ("cote", "cote")],   # deux cotes : la seconde suit la première
    TypeRelation.POINT_SUR_LIGNE: [("point", "ligne"), ("ligne", "point")],
    TypeRelation.POINT_SUR_ARC: [("point", "arc"), ("arc", "point")],
    TypeRelation.SUR_AXE: [("point",)],
    TypeRelation.ORIGINE_Z: [("point",)],
    TypeRelation.FIXE: [("point",)],
}

_FORMES_COTE: Dict[TypeCote, List[Tuple[str, ...]]] = {
    TypeCote.LONGUEUR_Z: [("point", "point"), ("ligne",)],
    TypeCote.DIAMETRE: [("point",), ("ligne",)],
    TypeCote.RAYON: [("arc",)],
    TypeCote.ANGLE: [("ligne",), ("ligne", "ligne")],
    TypeCote.DISTANCE: [("point", "point"), ("ligne",)],
    TypeCote.ECART: [("ligne", "ligne")],
    TypeCote.POSITION_Z: [("point",), ("ligne",)],
}


class ErreurEsquisse(ValueError):
    """Opération impossible sur le modèle (élément inconnu, genres incompatibles…)."""


@dataclass
class Point:
    id: int
    z: float
    x: float
    construction: bool = False   # point de construction : le sommet théorique d'un arrondi ou d'un chanfrein,
                                 # hors profil, conservé pour que les cotes voisines gardent leur sens


@dataclass
class Ligne:
    id: int
    p1: int
    p2: int


@dataclass
class Arc:
    """Arc de cercle du point `debut` au point `fin` autour de `centre`.

    `horaire` est le sens de parcours vu dans le plan (Z vers la droite, X vers le haut).
    """
    id: int
    centre: int
    debut: int
    fin: int
    horaire: bool = False


@dataclass
class Relation:
    id: int
    type: TypeRelation
    elements: Tuple[int, ...]


@dataclass
class Cote:
    id: int
    type: TypeCote
    elements: Tuple[int, ...]
    valeur: float
    decalage: Tuple[float, float] = (0.0, 0.0)   # position de l'étiquette par rapport à son point d'ancrage
    pilotee: bool = False                        # cote pilotée : mesurée par le solveur, elle n'impose rien


class Esquisse:
    """Le dessin d'un demi-profil : géométrie, relations, cotes. Identifiants entiers uniques."""

    def __init__(self) -> None:
        self.points: Dict[int, Point] = {}
        self.lignes: Dict[int, Ligne] = {}
        self.arcs: Dict[int, Arc] = {}
        self.relations: Dict[int, Relation] = {}
        self.cotes: Dict[int, Cote] = {}
        self._prochain_id = 1

    # -- identifiants et genres ------------------------------------------------------

    def _nouvel_id(self) -> int:
        i = self._prochain_id
        self._prochain_id += 1
        return i

    def genre(self, ident: int) -> Optional[str]:
        if ident in self.points:
            return "point"
        if ident in self.lignes:
            return "ligne"
        if ident in self.arcs:
            return "arc"
        if ident in self.relations:
            return "relation"
        if ident in self.cotes:
            return "cote"
        return None

    def _exiger(self, ident: int, genre: str):
        if self.genre(ident) != genre:
            raise ErreurEsquisse(f"élément {ident} : {genre} attendu, {self.genre(ident) or 'inconnu'} trouvé")
        return getattr(self, genre + "s")[ident]

    def _verifier_forme(self, formes: List[Tuple[str, ...]], elements: Tuple[int, ...], libelle: str) -> None:
        genres = tuple(self.genre(e) or "inconnu" for e in elements)
        if genres not in formes:
            attendu = " ou ".join("(" + ", ".join(f) + ")" for f in formes)
            raise ErreurEsquisse(f"{libelle} : éléments {genres} refusés, attendu {attendu}")
        if len(set(elements)) != len(elements):
            raise ErreurEsquisse(f"{libelle} : le même élément est donné deux fois")

    # -- ajout -----------------------------------------------------------------------

    def ajouter_point(self, z: float, x: float) -> Point:
        p = Point(self._nouvel_id(), float(z), float(x))
        self.points[p.id] = p
        return p

    def ajouter_ligne(self, p1: int, p2: int) -> Ligne:
        self._exiger(p1, "point")
        self._exiger(p2, "point")
        if p1 == p2:
            raise ErreurEsquisse("une ligne demande deux points distincts")
        li = Ligne(self._nouvel_id(), p1, p2)
        self.lignes[li.id] = li
        return li

    def ajouter_arc(self, centre: int, debut: int, fin: int, horaire: bool = False) -> Arc:
        for p in (centre, debut, fin):
            self._exiger(p, "point")
        if len({centre, debut, fin}) != 3:
            raise ErreurEsquisse("un arc demande trois points distincts")
        a = Arc(self._nouvel_id(), centre, debut, fin, bool(horaire))
        self.arcs[a.id] = a
        return a

    def ajouter_relation(self, type_: TypeRelation, elements: Iterable[int]) -> Relation:
        type_ = TypeRelation(type_)
        elements = tuple(int(e) for e in elements)
        self._verifier_forme(_FORMES_RELATION[type_], elements, LIBELLES_RELATION[type_])
        # Formes symétriques : on range dans l'ordre canonique (point avant ligne, ligne avant arc).
        if type_ in (TypeRelation.TANGENT, TypeRelation.POINT_SUR_LIGNE, TypeRelation.POINT_SUR_ARC):
            ordre = {"point": 0, "ligne": 1, "arc": 2}
            elements = tuple(sorted(elements, key=lambda e: ordre[self.genre(e)]))
        if type_ == TypeRelation.EGAL and self.genre(elements[0]) == "cote":
            self._verifier_egalite_cotes(elements[0], elements[1])
        r = Relation(self._nouvel_id(), type_, elements)
        self.relations[r.id] = r
        return r

    def _verifier_egalite_cotes(self, maitre: int, suiveuse: int) -> None:
        a, b = self.cotes[maitre], self.cotes[suiveuse]
        if a.type != b.type:
            raise ErreurEsquisse(f"Égal : deux cotes de même type attendues ({LIBELLES_COTE[a.type]} et "
                                 f"{LIBELLES_COTE[b.type]})")
        if self.cote_maitresse(suiveuse) is not None:
            raise ErreurEsquisse("Égal : cette cote suit déjà une autre cote")
        if self.cote_maitresse(maitre) == suiveuse:
            raise ErreurEsquisse("Égal : ces deux cotes se suivraient l'une l'autre")

    def cote_maitresse(self, cote_id: int) -> Optional[int]:
        """La cote dont `cote_id` prend la valeur par une relation « égal », sinon None."""
        for r in self.relations.values():
            if r.type == TypeRelation.EGAL and len(r.elements) == 2 and r.elements[1] == cote_id \
                    and self.genre(r.elements[0]) == "cote":
                return r.elements[0]
        return None

    def relation_possible(self, type_: TypeRelation, elements: Iterable[int]) -> bool:
        """Vrai si ces éléments peuvent porter une relation de ce type (sans l'ajouter)."""
        elements = tuple(int(e) for e in elements)
        try:
            self._verifier_forme(_FORMES_RELATION[TypeRelation(type_)], elements, "")
            if TypeRelation(type_) == TypeRelation.EGAL and self.genre(elements[0]) == "cote":
                self._verifier_egalite_cotes(elements[0], elements[1])
        except ErreurEsquisse:
            return False
        return True

    def cote_possible(self, type_: TypeCote, elements: Iterable[int]) -> bool:
        try:
            self.verifier_cote(type_, tuple(int(e) for e in elements))
        except ErreurEsquisse:
            return False
        return True

    def ajouter_cote(self, type_: TypeCote, elements: Iterable[int], valeur: Optional[float] = None,
                     decalage: Tuple[float, float] = (0.0, 0.0)) -> Cote:
        """Ajoute une cote. Sans `valeur`, la cote prend la mesure actuelle."""
        type_ = TypeCote(type_)
        elements = tuple(int(e) for e in elements)
        self._verifier_forme(_FORMES_COTE[type_], elements, LIBELLES_COTE[type_])
        if valeur is None:
            valeur = self.mesurer(type_, elements)
        valeur = float(valeur)
        if type_ in (TypeCote.LONGUEUR_Z, TypeCote.DISTANCE) and len(elements) == 2:
            # ordre canonique : du plus petit z au plus grand, la valeur est positive
            a, b = (self.points[e] for e in elements)
            if a.z > b.z:
                elements = (elements[1], elements[0])
            valeur = abs(valeur)
        if type_ in (TypeCote.DIAMETRE, TypeCote.RAYON, TypeCote.DISTANCE, TypeCote.LONGUEUR_Z, TypeCote.ECART) \
                and valeur < 0:
            raise ErreurEsquisse(f"{LIBELLES_COTE[type_]} : valeur négative refusée")
        c = Cote(self._nouvel_id(), type_, elements, valeur, (float(decalage[0]), float(decalage[1])))
        self.cotes[c.id] = c
        return c

    # -- accès -----------------------------------------------------------------------

    def element(self, ident: int):
        g = self.genre(ident)
        if g is None:
            raise ErreurEsquisse(f"élément {ident} inconnu")
        return getattr(self, g + "s")[ident]

    def extremites(self, ident: int) -> Tuple[int, int]:
        """Les deux points d'une ligne, ou début et fin d'un arc."""
        g = self.genre(ident)
        if g == "ligne":
            li = self.lignes[ident]
            return li.p1, li.p2
        if g == "arc":
            a = self.arcs[ident]
            return a.debut, a.fin
        raise ErreurEsquisse(f"élément {ident} : ligne ou arc attendu")

    def lignes_du_point(self, pid: int) -> List[Ligne]:
        return [li for li in self.lignes.values() if pid in (li.p1, li.p2)]

    def arcs_du_point(self, pid: int) -> List[Arc]:
        return [a for a in self.arcs.values() if pid in (a.centre, a.debut, a.fin)]

    def relations_de(self, ident: int) -> List[Relation]:
        return [r for r in self.relations.values() if ident in r.elements]

    def cotes_de(self, ident: int) -> List[Cote]:
        return [c for c in self.cotes.values() if ident in c.elements]

    def points_orphelins(self) -> List[int]:
        """Points qui ne tiennent à aucune ligne ni aucun arc, points de construction exceptés."""
        utilises = set()
        for li in self.lignes.values():
            utilises.update((li.p1, li.p2))
        for a in self.arcs.values():
            utilises.update((a.centre, a.debut, a.fin))
        return [pid for pid, p in self.points.items() if pid not in utilises and not p.construction]

    def est_vide(self) -> bool:
        return not (self.points or self.lignes or self.arcs)

    # -- suppression -----------------------------------------------------------------

    def supprimer(self, ident: int, nettoyer_points: bool = True) -> None:
        """Supprime un élément et tout ce qui en dépend. Les points devenus orphelins partent aussi."""
        g = self.genre(ident)
        if g is None:
            return
        if g in ("relation", "cote"):
            getattr(self, g + "s").pop(ident, None)
            return
        if g == "point":
            for li in self.lignes_du_point(ident):
                self.supprimer(li.id, nettoyer_points=False)
            for a in self.arcs_du_point(ident):
                self.supprimer(a.id, nettoyer_points=False)
        for r in self.relations_de(ident):
            self.relations.pop(r.id, None)
        for c in self.cotes_de(ident):
            self.cotes.pop(c.id, None)
        getattr(self, g + "s").pop(ident, None)
        if nettoyer_points:
            for pid in self.points_orphelins():
                self.supprimer(pid, nettoyer_points=False)

    # -- mesures ---------------------------------------------------------------------

    def _points_de(self, elements: Tuple[int, ...]) -> Tuple[Point, Point]:
        if len(elements) == 1:
            a, b = self.extremites(elements[0])
            return self.points[a], self.points[b]
        return self.points[elements[0]], self.points[elements[1]]

    def longueur(self, ligne_id: int) -> float:
        a, b = self._points_de((ligne_id,))
        return math.hypot(b.z - a.z, b.x - a.x)

    def rayon(self, arc_id: int) -> float:
        a = self.arcs[arc_id]
        c, d = self.points[a.centre], self.points[a.debut]
        return math.hypot(d.z - c.z, d.x - c.x)

    def point_reference(self, ident: int) -> int:
        """Le point que vise une cote posée sur un point ou sur une ligne (son premier point)."""
        return ident if self.genre(ident) == "point" else self.lignes[ident].p1

    def ecart(self, l1: int, l2: int) -> float:
        """Distance du premier point de `l1` à la droite portant `l2` (écart entre deux lignes parallèles)."""
        a = self.points[self.lignes[l1].p1]
        c, d = (self.points[i] for i in self.extremites(l2))
        vz, vx = d.z - c.z, d.x - c.x
        n = math.hypot(vz, vx) or 1.0
        return abs((a.z - c.z) * vx - (a.x - c.x) * vz) / n

    def angle_ligne(self, ligne_id: int) -> float:
        """Angle en degrés de la ligne (p1 vers p2) par rapport à l'axe Z, dans ]-180, 180]."""
        a, b = self._points_de((ligne_id,))
        return math.degrees(math.atan2(b.x - a.x, b.z - a.z))

    def verifier_cote(self, type_: TypeCote, elements: Tuple[int, ...]) -> None:
        """Lève ErreurEsquisse si ces éléments ne peuvent pas porter une cote de ce type."""
        type_ = TypeCote(type_)
        self._verifier_forme(_FORMES_COTE[type_], tuple(int(e) for e in elements), LIBELLES_COTE[type_])

    def mesurer(self, type_: TypeCote, elements: Tuple[int, ...]) -> float:
        """Valeur actuelle de la grandeur qu'une cote de ce type imposerait."""
        type_ = TypeCote(type_)
        self.verifier_cote(type_, elements)
        if type_ == TypeCote.LONGUEUR_Z:
            a, b = self._points_de(elements)
            return abs(b.z - a.z)
        if type_ == TypeCote.DISTANCE:
            a, b = self._points_de(elements)
            return math.hypot(b.z - a.z, b.x - a.x)
        if type_ == TypeCote.DIAMETRE:
            e = elements[0]
            p = self.points[e] if self.genre(e) == "point" else self.points[self.lignes[e].p1]
            return 2.0 * p.x
        if type_ == TypeCote.RAYON:
            return self.rayon(elements[0])
        if type_ == TypeCote.ECART:
            return self.ecart(elements[0], elements[1])
        if type_ == TypeCote.POSITION_Z:
            return self.points[self.point_reference(elements[0])].z
        if type_ == TypeCote.ANGLE:
            if len(elements) == 1:
                return self.angle_ligne(elements[0])
            a1 = self.angle_ligne(elements[0])
            a2 = self.angle_ligne(elements[1])
            d = (a2 - a1) % 360.0
            return d if d <= 180.0 else d - 360.0
        raise ErreurEsquisse(f"type de cote inconnu : {type_}")

    @staticmethod
    def _formater(valeur: float, decimales: int) -> str:
        v = f"{valeur:.{decimales}f}".rstrip("0").rstrip(".") if decimales else f"{valeur:.0f}"
        return "0" if v == "-0" else v

    def texte_cote(self, cote: Cote, decimales: int = 2) -> str:
        v = self._formater(cote.valeur, decimales)
        if cote.type == TypeCote.DIAMETRE:
            texte = "Ø " + v
        elif cote.type == TypeCote.RAYON:
            texte = "R " + v
        elif cote.type == TypeCote.ANGLE:
            texte = v + "°"
        elif cote.type == TypeCote.POSITION_Z:
            texte = "Z " + v                     # coordonnée signée, comme sur la commande numérique
        else:
            texte = v
        return f"({texte})" if cote.pilotee else texte   # convention du dessin : une cote mesurée entre parenthèses

    def texte_rayon(self, cote: Cote, decimales: int = 2) -> str:
        """Le rayon qui accompagne une cote de diamètre : la même grandeur, lue depuis l'axe."""
        texte = "R " + self._formater(cote.valeur / 2.0, decimales + 1)
        return f"({texte})" if cote.pilotee else texte

    # -- sérialisation ---------------------------------------------------------------

    def to_dict(self) -> dict:
        return {
            "format": FORMAT,
            "version": VERSION_FORMAT,
            "prochain_id": self._prochain_id,
            "points": [{"id": p.id, "z": p.z, "x": p.x, "construction": p.construction} for p in self.points.values()],
            "lignes": [{"id": li.id, "p1": li.p1, "p2": li.p2} for li in self.lignes.values()],
            "arcs": [{"id": a.id, "centre": a.centre, "debut": a.debut, "fin": a.fin, "horaire": a.horaire}
                     for a in self.arcs.values()],
            "relations": [{"id": r.id, "type": r.type.value, "elements": list(r.elements)}
                          for r in self.relations.values()],
            "cotes": [{"id": c.id, "type": c.type.value, "elements": list(c.elements), "valeur": c.valeur,
                       "decalage": list(c.decalage), "pilotee": c.pilotee} for c in self.cotes.values()],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Esquisse":
        if d.get("format") != FORMAT:
            raise ErreurEsquisse("ce fichier n'est pas une esquisse CTgraph")
        if int(d.get("version", 0)) > VERSION_FORMAT:
            raise ErreurEsquisse("esquisse enregistrée par une version plus récente de CTgraph")
        e = cls()
        for p in d.get("points", []):
            e.points[int(p["id"])] = Point(int(p["id"]), float(p["z"]), float(p["x"]), bool(p.get("construction", False)))
        for li in d.get("lignes", []):
            e.lignes[int(li["id"])] = Ligne(int(li["id"]), int(li["p1"]), int(li["p2"]))
        for a in d.get("arcs", []):
            e.arcs[int(a["id"])] = Arc(int(a["id"]), int(a["centre"]), int(a["debut"]), int(a["fin"]),
                                       bool(a.get("horaire", False)))
        for r in d.get("relations", []):
            e.relations[int(r["id"])] = Relation(int(r["id"]), TypeRelation(r["type"]),
                                                 tuple(int(x) for x in r["elements"]))
        for c in d.get("cotes", []):
            dec = c.get("decalage") or [0.0, 0.0]
            e.cotes[int(c["id"])] = Cote(int(c["id"]), TypeCote(c["type"]), tuple(int(x) for x in c["elements"]),
                                         float(c["valeur"]), (float(dec[0]), float(dec[1])),
                                         bool(c.get("pilotee", False)))
        ids = list(e.points) + list(e.lignes) + list(e.arcs) + list(e.relations) + list(e.cotes)
        e._prochain_id = max([int(d.get("prochain_id", 1))] + [i + 1 for i in ids])
        e._verifier_coherence()
        return e

    def _verifier_coherence(self) -> None:
        for li in self.lignes.values():
            for p in (li.p1, li.p2):
                if p not in self.points:
                    raise ErreurEsquisse(f"ligne {li.id} : point {p} inconnu")
        for a in self.arcs.values():
            for p in (a.centre, a.debut, a.fin):
                if p not in self.points:
                    raise ErreurEsquisse(f"arc {a.id} : point {p} inconnu")
        for r in self.relations.values():
            self._verifier_forme(_FORMES_RELATION[r.type], r.elements, LIBELLES_RELATION[r.type])
        for c in self.cotes.values():
            self._verifier_forme(_FORMES_COTE[c.type], c.elements, LIBELLES_COTE[c.type])

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=1)

    @classmethod
    def from_json(cls, texte: str) -> "Esquisse":
        try:
            d = json.loads(texte)
        except ValueError as exc:
            raise ErreurEsquisse(f"fichier illisible : {exc}") from exc
        if not isinstance(d, dict):
            raise ErreurEsquisse("ce fichier n'est pas une esquisse CTgraph")
        return cls.from_dict(d)

    def copier(self) -> "Esquisse":
        return Esquisse.from_dict(self.to_dict())
