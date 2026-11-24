"""Arrondi et chanfrein d'un coin : le sommet commun à deux lignes reçoit un congé ou un pan.

Le sommet lui-même ne disparaît pas : il devient un point de construction, le coin théorique, tenu sur le
prolongement des deux lignes. Les cotes qui s'y rattachaient, et les cotes de longueur des deux lignes,
continuent de s'y référer : changer le rayon ou la longueur du pan ne déplace que le congé ou le pan,
jamais les cotes importantes autour (longueurs, diamètres, positions).

L'arrondi reçoit ses deux tangences et sa cote de rayon. Le chanfrein reçoit sa longueur depuis le coin
théorique et son angle, à lire « 1 × 45° ».
"""
from __future__ import annotations

import math
from typing import Tuple

from . import geometrie as geo
from .elagage import _raccourcir
from .modele import ErreurEsquisse, Esquisse, TypeCote, TypeRelation


def _coin(e: Esquisse, point_id: int):
    """Les deux lignes qui se rejoignent en `point_id`, leurs autres extrémités et les vecteurs unitaires."""
    if e.genre(point_id) != "point":
        raise ErreurEsquisse("cliquez un sommet entre deux lignes")
    lignes = e.lignes_du_point(point_id)
    if len(lignes) != 2 or e.arcs_du_point(point_id):
        raise ErreurEsquisse("le sommet doit relier exactement deux lignes")
    p = e.points[point_id]
    autres = []
    for li in lignes:
        q = e.points[li.p2 if li.p1 == point_id else li.p1]
        dz, dx = q.z - p.z, q.x - p.x
        lg = math.hypot(dz, dx)
        if lg < 1e-9:
            raise ErreurEsquisse("une des lignes est de longueur nulle")
        autres.append((q, (dz / lg, dx / lg), lg))
    (q1, u1, lg1), (q2, u2, lg2) = autres
    cos_theta = max(-1.0, min(1.0, u1[0] * u2[0] + u1[1] * u2[1]))
    theta = math.acos(cos_theta)
    if theta < math.radians(1.0) or theta > math.radians(179.0):
        raise ErreurEsquisse("les deux lignes sont presque alignées : pas de coin à traiter")
    return p, lignes, (q1, u1, lg1), (q2, u2, lg2), theta


def _poser_points(e: Esquisse, p, lignes, u1, u2, t: float, lg1: float, lg2: float) -> Tuple[int, int]:
    """Raccourcit les deux lignes jusqu'aux nouveaux points A et B ; le coin devient point de construction."""
    if t >= lg1 - 1e-6 or t >= lg2 - 1e-6:
        raise ErreurEsquisse("valeur trop grande pour les lignes de ce coin")
    pid = p.id
    # les cotes de longueur portées par les lignes passent sur (autre extrémité, coin) : elles gardent leur sens
    for li in lignes:
        q = li.p2 if li.p1 == pid else li.p1
        for co in e.cotes_de(li.id):
            if co.type in (TypeCote.LONGUEUR_Z, TypeCote.DISTANCE) and co.elements == (li.id,):
                a, b = e.points[q], e.points[pid]
                co.elements = (q, pid) if a.z <= b.z else (pid, q)
    p.construction = True
    a = e.ajouter_point(p.z + u1[0] * t, p.x + u1[1] * t)
    b = e.ajouter_point(p.z + u2[0] * t, p.x + u2[1] * t)
    _raccourcir(e, lignes[0].id, a.id, "debut" if lignes[0].p1 == pid else "fin")
    _raccourcir(e, lignes[1].id, b.id, "debut" if lignes[1].p1 == pid else "fin")
    # le coin théorique reste sur le prolongement des deux lignes
    e.ajouter_relation(TypeRelation.POINT_SUR_LIGNE, (pid, lignes[0].id))
    e.ajouter_relation(TypeRelation.POINT_SUR_LIGNE, (pid, lignes[1].id))
    return a.id, b.id


def arrondir(e: Esquisse, point_id: int, rayon: float, decalage=(0.0, 0.0)) -> int:
    """Pose un congé de rayon `rayon`, tangent aux deux lignes du coin. Renvoie l'identifiant de l'arc."""
    if rayon <= 0:
        raise ErreurEsquisse("le rayon doit être positif")
    p, lignes, (q1, u1, lg1), (q2, u2, lg2), theta = _coin(e, point_id)
    t = rayon / math.tan(theta / 2.0)                       # distance du coin aux points de tangence
    bis = (u1[0] + u2[0], u1[1] + u2[1])
    n = math.hypot(*bis)
    bis = (bis[0] / n, bis[1] / n)
    d_centre = rayon / math.sin(theta / 2.0)
    centre = (p.z + bis[0] * d_centre, p.x + bis[1] * d_centre)
    milieu = (centre[0] - bis[0] * rayon, centre[1] - bis[1] * rayon)     # point de l'arc le plus proche du coin
    a_id, b_id = _poser_points(e, p, lignes, u1, u2, t, lg1, lg2)
    a, b = e.points[a_id], e.points[b_id]
    res = geo.arc_par_trois_points((a.z, a.x), (b.z, b.x), milieu)
    horaire = res[1] if res is not None else False
    c = e.ajouter_point(*centre)
    arc = e.ajouter_arc(c.id, a_id, b_id, horaire)
    e.ajouter_relation(TypeRelation.TANGENT, (lignes[0].id, arc.id))
    e.ajouter_relation(TypeRelation.TANGENT, (lignes[1].id, arc.id))
    e.ajouter_cote(TypeCote.RAYON, (arc.id,), rayon, decalage)
    return arc.id


def chanfreiner(e: Esquisse, point_id: int, distance: float, decalage=(0.0, 0.0)) -> int:
    """Pose un pan dont les côtés mesurent `distance` depuis le coin théorique. Renvoie la ligne."""
    if distance <= 0:
        raise ErreurEsquisse("la longueur du chanfrein doit être positive")
    p, lignes, (q1, u1, lg1), (q2, u2, lg2), theta = _coin(e, point_id)
    a_id, b_id = _poser_points(e, p, lignes, u1, u2, distance, lg1, lg2)
    pan = e.ajouter_ligne(a_id, b_id)
    # lecture « longueur × angle » : longueur du côté depuis le coin théorique, angle du pan
    e.ajouter_cote(TypeCote.DISTANCE, (point_id, a_id), distance, (0.0, decalage[1]))
    e.ajouter_cote(TypeCote.ANGLE, (pan.id,), None, decalage)
    return pan.id
