"""Élagage : retirer une portion d'une ligne ou d'un arc en gardant le modèle paramétrique cohérent.

Quatre modes, qui ne diffèrent que par les bornes de la portion retirée autour du point traversé :
- « croisement » : jusqu'aux croisements voisins avec les autres objets (sinon jusqu'aux extrémités) ;
- « points » : jusqu'aux points d'esquisse voisins posés sur l'objet (sinon jusqu'aux extrémités) ;
- « extremite » : du point traversé jusqu'à l'extrémité la plus proche ;
- « tout » : l'objet entier.

Quand une borne est un croisement, le nouveau point reçoit la relation « point sur ligne » ou « point sur arc »
avec l'objet croisé : la coupe suit les modifications ultérieures du profil.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Optional, Tuple

from . import geometrie as geo
from .modele import Esquisse, TypeCote, TypeRelation

MODES = ("croisement", "points", "extremite", "tout")
LIBELLES_MODE = {
    "croisement": "Jusqu'aux croisements",
    "points": "Entre deux points",
    "extremite": "Jusqu'à l'extrémité",
    "tout": "Tout l'objet",
}
_TOL_POINT = 1e-6


@dataclass
class Borne:
    t: float
    pos: Tuple[float, float]
    point: Optional[int] = None    # point d'esquisse déjà là
    autre: Optional[int] = None    # objet croisé à cet endroit


def courbe(e: Esquisse, ident: int) -> tuple:
    """Description géométrique d'une ligne ou d'un arc du modèle (voir `geometrie`)."""
    g = e.genre(ident)
    if g == "ligne":
        li = e.lignes[ident]
        a, b = e.points[li.p1], e.points[li.p2]
        return geo.ligne((a.z, a.x), (b.z, b.x))
    if g == "arc":
        a = e.arcs[ident]
        c, d, f = e.points[a.centre], e.points[a.debut], e.points[a.fin]
        return geo.arc((c.z, c.x), (d.z, d.x), (f.z, f.x), a.horaire)
    raise ValueError(f"élément {ident} : ligne ou arc attendu")


def bornes_croisements(e: Esquisse, ident: int) -> List[Borne]:
    c = courbe(e, ident)
    bornes: List[Borne] = []
    for autre in list(e.lignes) + list(e.arcs):
        if autre == ident:
            continue
        for t1, _, p in geo.intersections(c, courbe(e, autre)):
            if _TOL_POINT < t1 < 1.0 - _TOL_POINT:
                bornes.append(Borne(t1, p, None, autre))
    return bornes


def bornes_points(e: Esquisse, ident: int) -> List[Borne]:
    c = courbe(e, ident)
    extremites = set(e.extremites(ident))
    bornes: List[Borne] = []
    for p in e.points.values():
        if p.id in extremites:
            continue
        t = geo.sur_courbe(c, (p.z, p.x))
        if t is not None and _TOL_POINT < t < 1.0 - _TOL_POINT:
            bornes.append(Borne(t, (p.z, p.x), p.id, None))
    return bornes


def _point_pour(e: Esquisse, b: Borne) -> int:
    if b.point is not None:
        return b.point
    if b.autre is not None:
        for pid in e.extremites(b.autre):
            p = e.points[pid]
            if math.hypot(p.z - b.pos[0], p.x - b.pos[1]) < _TOL_POINT:
                return pid        # le croisement tombe sur une extrémité de l'autre objet : on la partage
    p = e.ajouter_point(*b.pos)
    if b.autre is not None:
        typ = TypeRelation.POINT_SUR_LIGNE if e.genre(b.autre) == "ligne" else TypeRelation.POINT_SUR_ARC
        e.ajouter_relation(typ, (p.id, b.autre))
    return p.id


def _est_utilise(e: Esquisse, pid: int) -> bool:
    return bool(e.lignes_du_point(pid) or e.arcs_du_point(pid))


def _nettoyer_apres_raccourci(e: Esquisse, ident: int, ancien: int) -> None:
    """Relations et cotes qui perdent leur sens quand `ident` ne va plus jusqu'au point `ancien`."""
    for r in e.relations_de(ident):
        if r.type == TypeRelation.EGAL:
            e.relations.pop(r.id, None)
        elif r.type == TypeRelation.TANGENT:
            autre = r.elements[0] if r.elements[1] == ident else r.elements[1]
            if ancien in e.extremites(autre):
                e.relations.pop(r.id, None)
    for c in e.cotes_de(ident):
        if c.type in (TypeCote.LONGUEUR_Z, TypeCote.DISTANCE):
            e.cotes.pop(c.id, None)
    if not _est_utilise(e, ancien) and not e.points[ancien].construction:
        e.supprimer(ancien, nettoyer_points=False)


def _raccourcir(e: Esquisse, ident: int, nouveau: int, cote: str) -> None:
    g = e.genre(ident)
    el = e.element(ident)
    if g == "ligne":
        ancien = el.p1 if cote == "debut" else el.p2
        if cote == "debut":
            el.p1 = nouveau
        else:
            el.p2 = nouveau
    else:
        ancien = el.debut if cote == "debut" else el.fin
        if cote == "debut":
            el.debut = nouveau
        else:
            el.fin = nouveau
    # une relation « point sur » du nouveau point avec l'objet raccourci n'a plus de sens : il en est l'extrémité
    for r in e.relations_de(nouveau):
        if r.type in (TypeRelation.POINT_SUR_LIGNE, TypeRelation.POINT_SUR_ARC) and ident in r.elements:
            e.relations.pop(r.id, None)
    _nettoyer_apres_raccourci(e, ident, ancien)


def _scinder(e: Esquisse, ident: int, pa: int, pb: int) -> Tuple[int, int]:
    """Remplace `ident` par deux morceaux : du début à `pa`, et de `pb` à la fin."""
    g = e.genre(ident)
    el = e.element(ident)
    c = courbe(e, ident)
    if g == "ligne":
        m1 = e.ajouter_ligne(el.p1, pa)
        m2 = e.ajouter_ligne(pb, el.p2)
        debut_id, fin_id = el.p1, el.p2
    else:
        m1 = e.ajouter_arc(el.centre, el.debut, pa, el.horaire)
        m2 = e.ajouter_arc(el.centre, pb, el.fin, el.horaire)
        e.ajouter_relation(TypeRelation.EGAL, (m1.id, m2.id))     # même centre et même rayon : même cercle
        debut_id, fin_id = el.debut, el.fin
    ta = geo.parametre(c, (e.points[pa].z, e.points[pa].x))

    for r in list(e.relations_de(ident)):
        autres = tuple(x for x in r.elements if x != ident)
        if r.type in (TypeRelation.HORIZONTAL, TypeRelation.VERTICAL, TypeRelation.PARALLELE,
                      TypeRelation.PERPENDICULAIRE) or (r.type == TypeRelation.EGAL and g == "arc"):
            for m in (m1, m2):
                e.ajouter_relation(r.type, tuple(m.id if x == ident else x for x in r.elements))
        elif r.type == TypeRelation.TANGENT:
            autre = autres[0]
            ext = set(e.extremites(autre))
            if debut_id in ext:
                e.ajouter_relation(r.type, (m1.id, autre))
            elif fin_id in ext:
                e.ajouter_relation(r.type, (m2.id, autre))
        elif r.type in (TypeRelation.POINT_SUR_LIGNE, TypeRelation.POINT_SUR_ARC):
            pid = autres[0]
            if pid in (pa, pb):
                continue
            p = e.points[pid]
            t = geo.parametre(c, (p.z, p.x))
            if t < ta:
                e.ajouter_relation(r.type, (pid, m1.id))
            else:
                e.ajouter_relation(r.type, (pid, m2.id))
        e.relations.pop(r.id, None)

    for co in list(e.cotes_de(ident)):
        if co.type in (TypeCote.ANGLE, TypeCote.DIAMETRE, TypeCote.RAYON):
            e.ajouter_cote(co.type, tuple(m1.id if x == ident else x for x in co.elements), co.valeur, co.decalage)
        e.cotes.pop(co.id, None)

    getattr(e, g + "s").pop(ident, None)
    return m1.id, m2.id


def elaguer(e: Esquisse, ident: int, t0: float, mode: str) -> None:
    """Retire la portion de `ident` qui entoure le paramètre `t0`, selon `mode`."""
    if mode not in MODES:
        raise ValueError(f"mode d'élagage inconnu : {mode}")
    if e.genre(ident) not in ("ligne", "arc"):
        return
    if mode == "tout":
        e.supprimer(ident)
        return
    c = courbe(e, ident)
    t0 = min(1.0, max(0.0, t0))
    if mode == "extremite":
        p = e.ajouter_point(*geo.position(c, t0))
        _raccourcir(e, ident, p.id, "debut" if t0 < 0.5 else "fin")
        return
    bornes = bornes_croisements(e, ident) if mode == "croisement" else bornes_points(e, ident)
    avant = [b for b in bornes if b.t <= t0]
    apres = [b for b in bornes if b.t > t0]
    ba = max(avant, key=lambda b: b.t) if avant else None
    bb = min(apres, key=lambda b: b.t) if apres else None
    if ba is None and bb is None:
        e.supprimer(ident)
    elif ba is None:
        _raccourcir(e, ident, _point_pour(e, bb), "debut")
    elif bb is None:
        _raccourcir(e, ident, _point_pour(e, ba), "fin")
    else:
        pa, pb = _point_pour(e, ba), _point_pour(e, bb)
        if pa == pb:
            return
        _scinder(e, ident, pa, pb)
