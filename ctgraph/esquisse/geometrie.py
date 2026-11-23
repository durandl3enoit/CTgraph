"""Géométrie plane exacte sur lignes et arcs : paramètres, intersections, distances. Sans Qt.

Une courbe est décrite par un tuple :
- ("ligne", (z1, x1), (z2, x2))
- ("arc", (cz, cx), rayon, a0, a1) avec a0 et a1 en radians, a1 > a0 pour un arc antihoraire,
  a1 < a0 pour un arc horaire (sens vu dans le plan Z vers la droite, X vers le haut).

Le paramètre t d'une courbe va de 0 (début) à 1 (fin). Hors de [0, 1], le point est sur le prolongement.
"""
from __future__ import annotations

import math
from typing import List, Optional, Tuple

EPS = 1e-9
Point2 = Tuple[float, float]


# -- construction -------------------------------------------------------------------------

def angles_arc(centre: Point2, debut: Point2, fin: Point2, horaire: bool) -> Tuple[float, float]:
    """Angles de début et de fin, la fin décalée de 2π pour respecter le sens de parcours."""
    a0 = math.atan2(debut[1] - centre[1], debut[0] - centre[0])
    a1 = math.atan2(fin[1] - centre[1], fin[0] - centre[0])
    if horaire:
        while a1 >= a0 - EPS:
            a1 -= 2.0 * math.pi
    else:
        while a1 <= a0 + EPS:
            a1 += 2.0 * math.pi
    return a0, a1


def ligne(a: Point2, b: Point2) -> tuple:
    return ("ligne", (float(a[0]), float(a[1])), (float(b[0]), float(b[1])))


def arc(centre: Point2, debut: Point2, fin: Point2, horaire: bool) -> tuple:
    r = math.hypot(debut[0] - centre[0], debut[1] - centre[1])
    a0, a1 = angles_arc(centre, debut, fin, horaire)
    return ("arc", (float(centre[0]), float(centre[1])), r, a0, a1)


# -- paramètres et positions -------------------------------------------------------------

def position(courbe: tuple, t: float) -> Point2:
    if courbe[0] == "ligne":
        (_, a, b) = courbe
        return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
    (_, c, r, a0, a1) = courbe
    ang = a0 + (a1 - a0) * t
    return (c[0] + r * math.cos(ang), c[1] + r * math.sin(ang))


def parametre(courbe: tuple, p: Point2) -> float:
    """Paramètre du point de la courbe le plus proche de p (projection pour une ligne, angle pour un arc)."""
    if courbe[0] == "ligne":
        (_, a, b) = courbe
        dz, dx = b[0] - a[0], b[1] - a[1]
        n2 = dz * dz + dx * dx
        if n2 < EPS * EPS:
            return 0.0
        return ((p[0] - a[0]) * dz + (p[1] - a[1]) * dx) / n2
    (_, c, r, a0, a1) = courbe
    ang = math.atan2(p[1] - c[1], p[0] - c[0])
    balayage = a1 - a0
    if balayage > 0:
        while ang < a0 - EPS:
            ang += 2.0 * math.pi
        while ang >= a0 + 2.0 * math.pi - EPS:
            ang -= 2.0 * math.pi
    else:
        while ang > a0 + EPS:
            ang -= 2.0 * math.pi
        while ang <= a0 - 2.0 * math.pi + EPS:
            ang += 2.0 * math.pi
    t = (ang - a0) / balayage
    # au-delà de l'arc, on rend le paramètre « du côté le plus proche » : > 1 près de la fin, < 0 près du début
    if t > 1.0:
        tour = 2.0 * math.pi / abs(balayage)
        if t - 1.0 > (tour - t):
            t -= tour
    return t


def longueur(courbe: tuple) -> float:
    if courbe[0] == "ligne":
        (_, a, b) = courbe
        return math.hypot(b[0] - a[0], b[1] - a[1])
    (_, _, r, a0, a1) = courbe
    return r * abs(a1 - a0)


def plus_proche(courbe: tuple, p: Point2) -> Tuple[float, float, Point2]:
    """(distance, t, point) : le point de la courbe (bornée) le plus proche de p."""
    t = min(1.0, max(0.0, parametre(courbe, p)))
    q = position(courbe, t)
    return math.hypot(q[0] - p[0], q[1] - p[1]), t, q


def sur_courbe(courbe: tuple, p: Point2, tol: float = 1e-6) -> Optional[float]:
    """Paramètre de p s'il est sur la courbe (bornes comprises), sinon None."""
    d, t, _ = plus_proche(courbe, p)
    return t if d <= tol else None


# -- intersections ------------------------------------------------------------------------

def _inter_lignes(l1: tuple, l2: tuple) -> List[Tuple[float, float, Point2]]:
    (_, a, b), (_, c, d) = l1, l2
    r = (b[0] - a[0], b[1] - a[1])
    s = (d[0] - c[0], d[1] - c[1])
    den = r[0] * s[1] - r[1] * s[0]
    if abs(den) < EPS:
        return []        # parallèles ou confondues : pas de point unique
    qp = (c[0] - a[0], c[1] - a[1])
    t = (qp[0] * s[1] - qp[1] * s[0]) / den
    u = (qp[0] * r[1] - qp[1] * r[0]) / den
    return [(t, u, (a[0] + r[0] * t, a[1] + r[1] * t))]


def _inter_ligne_arc(li: tuple, ar: tuple) -> List[Tuple[float, float, Point2]]:
    (_, a, b) = li
    (_, c, r, _, _) = ar
    dz, dx = b[0] - a[0], b[1] - a[1]
    fz, fx = a[0] - c[0], a[1] - c[1]
    qa = dz * dz + dx * dx
    if qa < EPS * EPS:
        return []
    qb = 2.0 * (fz * dz + fx * dx)
    qc = fz * fz + fx * fx - r * r
    disc = qb * qb - 4.0 * qa * qc
    if disc < -EPS:
        return []
    disc = max(disc, 0.0)
    racine = math.sqrt(disc)
    ts = [(-qb - racine) / (2.0 * qa)] if racine < EPS else [(-qb - racine) / (2.0 * qa), (-qb + racine) / (2.0 * qa)]
    out = []
    for t in ts:
        p = (a[0] + dz * t, a[1] + dx * t)
        out.append((t, parametre(ar, p), p))
    return out


def _inter_arcs(a1: tuple, a2: tuple) -> List[Tuple[float, float, Point2]]:
    (_, c1, r1, _, _), (_, c2, r2, _, _) = a1, a2
    dz, dx = c2[0] - c1[0], c2[1] - c1[1]
    d = math.hypot(dz, dx)
    if d < EPS or d > r1 + r2 + EPS or d < abs(r1 - r2) - EPS:
        return []
    a = (r1 * r1 - r2 * r2 + d * d) / (2.0 * d)
    h2 = r1 * r1 - a * a
    h = math.sqrt(max(h2, 0.0))
    mz, mx = c1[0] + a * dz / d, c1[1] + a * dx / d
    pts = [(mz, mx)] if h < EPS else [(mz - h * dx / d, mx + h * dz / d), (mz + h * dx / d, mx - h * dz / d)]
    return [(parametre(a1, p), parametre(a2, p), p) for p in pts]


def intersections(c1: tuple, c2: tuple, bornes: bool = True, tol: float = 1e-9) -> List[Tuple[float, float, Point2]]:
    """Intersections de deux courbes : liste de (t1, t2, point). Avec `bornes`, seulement sur les courbes
    elles-mêmes (t dans [0, 1] à `tol` près), sinon sur leurs prolongements."""
    if c1[0] == "ligne" and c2[0] == "ligne":
        res = _inter_lignes(c1, c2)
    elif c1[0] == "ligne":
        res = _inter_ligne_arc(c1, c2)
    elif c2[0] == "ligne":
        res = [(t2, t1, p) for (t1, t2, p) in _inter_ligne_arc(c2, c1)]
    else:
        res = _inter_arcs(c1, c2)
    if bornes:
        res = [(t1, t2, p) for (t1, t2, p) in res if -tol <= t1 <= 1.0 + tol and -tol <= t2 <= 1.0 + tol]
    return res


def polyligne_croise(points: List[Point2], courbe: tuple) -> Optional[Tuple[float, Point2]]:
    """Premier croisement d'une polyligne (le trait de la souris) avec une courbe : (t sur la courbe, point)."""
    for a, b in zip(points, points[1:]):
        if math.hypot(b[0] - a[0], b[1] - a[1]) < EPS:
            continue
        hits = intersections(ligne(a, b), courbe)
        if hits:
            hits.sort(key=lambda h: h[0])
            return hits[0][1], hits[0][2]
    return None
