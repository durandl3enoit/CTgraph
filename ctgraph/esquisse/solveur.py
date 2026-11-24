"""Adaptateur du solveur : seule partie du code qui connaît PlaneGCS.

Il traduit une `Esquisse` en système PlaneGCS, lance la résolution et réécrit les positions dans
le modèle. Le système est reconstruit à chaque changement de structure (ajout ou suppression) ;
les modifications de cotes et les glissements de points réutilisent le système en place.

Correspondance des axes : PlaneGCS travaille en (x, y). On lui donne x = z du modèle et y = x du modèle
(le rayon). « Horizontal » au sens du modèle (parallèle à l'axe de la pièce) est donc horizontal
pour PlaneGCS aussi.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from planegcs import Sketch, SolveStatus

from .modele import COTES_SIGNEES, Cote, Esquisse, Relation, TypeCote, TypeRelation

_OK = (SolveStatus.Success, SolveStatus.Converged)


@dataclass
class Resultat:
    succes: bool
    statut: str                                  # "ok", "approche", "echec" ou "invalide"
    dof: int = -1                                # degrés de liberté restants, -1 si inconnu
    conflits: List[int] = field(default_factory=list)    # relations ou cotes en conflit (identifiants du modèle)
    redondants: List[int] = field(default_factory=list)  # relations ou cotes redondantes

    @property
    def sur_contraint(self) -> bool:
        return bool(self.conflits)

    @property
    def entierement_contraint(self) -> bool:
        return self.succes and self.dof == 0 and not self.conflits

    def texte(self) -> str:
        if self.conflits:
            n = len(self.conflits)
            return f"Sur-contraint : {n} relation{'s' if n > 1 else ''} en conflit"
        if not self.succes:
            return "Résolution impossible"
        if self.dof == 0:
            return "Entièrement contraint"
        if self.dof > 0:
            return f"Sous-contraint : {self.dof} degré{'s' if self.dof > 1 else ''} de liberté"
        return "Résolu"


def _statut_texte(statut: SolveStatus) -> str:
    if statut == SolveStatus.Success:
        return "ok"
    if statut == SolveStatus.Converged:
        return "approche"
    if statut == SolveStatus.SuccessfulSolutionInvalid:
        return "invalide"
    return "echec"


class AdaptateurSolveur:
    """Traduit le modèle pour PlaneGCS et maintient la correspondance des identifiants."""

    def __init__(self, esquisse: Esquisse) -> None:
        self.esquisse = esquisse
        self.construire()

    # -- construction ----------------------------------------------------------------

    def construire(self) -> None:
        """(Re)construit le système complet à partir du modèle."""
        e = self.esquisse
        s = Sketch()
        self._s = s
        self._pts: Dict[int, int] = {}
        self._params_pts: Dict[int, Tuple[int, int]] = {}
        self._lignes: Dict[int, int] = {}
        self._arcs: Dict[int, int] = {}
        self._params_cotes: Dict[int, int] = {}
        self._tags: Dict[int, int] = {}      # étiquette PlaneGCS -> identifiant de relation ou de cote
        self._params: List[int] = []         # paramètres libres, pour instantané et restauration
        self.erreurs: Dict[int, str] = {}    # identifiant -> message, si la traduction a échoué

        for p in e.points.values():
            pz = s.add_param(p.z)
            px = s.add_param(p.x)
            self._pts[p.id] = s.add_point_from_params(pz, px)
            self._params_pts[p.id] = (pz, px)
            self._params += [pz, px]

        for li in e.lignes.values():
            self._lignes[li.id] = s.add_line(self._pts[li.p1], self._pts[li.p2])

        for a in e.arcs.values():
            c, d, f = (e.points[i] for i in (a.centre, a.debut, a.fin))
            rayon = max(math.hypot(d.z - c.z, d.x - c.x), 1e-6)
            a0 = math.atan2(d.x - c.x, d.z - c.z)
            a1 = math.atan2(f.x - c.x, f.z - c.z)
            if a.horaire:
                while a1 >= a0:
                    a1 -= 2.0 * math.pi
            else:
                while a1 <= a0:
                    a1 += 2.0 * math.pi
            pr, pa0, pa1 = s.add_param(rayon), s.add_param(a0), s.add_param(a1)
            self._params += [pr, pa0, pa1]
            self._arcs[a.id] = s.add_arc(self._pts[a.centre], self._pts[a.debut], self._pts[a.fin], pr, pa0, pa1)

        # Ordre : relations, puis cotes, puis les « égal » entre cotes (qui ont besoin des paramètres des cotes).
        # PlaneGCS signale comme redondante la contrainte arrivée en dernier : une cote nouvelle doit donc
        # passer après les relations pour être celle que l'on désigne.
        self._liees = {c for c in e.cotes if e.cote_maitresse(c) is not None}
        entre_cotes = [r for r in e.relations.values()
                       if r.type == TypeRelation.EGAL and e.genre(r.elements[0]) == "cote"]
        for r in e.relations.values():
            if r in entre_cotes:
                continue
            try:
                for t in self._traduire_relation(r):
                    self._tags[int(t)] = r.id
            except Exception as exc:  # relation intraduisible : signalée comme conflit
                self.erreurs[r.id] = str(exc)

        for c in e.cotes.values():
            try:
                self._tags[int(self._traduire_cote(c))] = c.id
            except Exception as exc:
                self.erreurs[c.id] = str(exc)

        for r in entre_cotes:
            try:
                for t in self._traduire_relation(r):
                    self._tags[int(t)] = r.id
            except Exception as exc:
                self.erreurs[r.id] = str(exc)

        # paramètres réutilisés par le glissement (évite d'en allouer à chaque mouvement de souris)
        self._glisse_z = s.add_fixed_param(0.0)
        self._glisse_x = s.add_fixed_param(0.0)

    def _traduire_relation(self, r: Relation) -> list:
        s, e, els = self._s, self.esquisse, r.elements
        genres = [e.genre(i) for i in els]
        T = TypeRelation
        if r.type == T.COINCIDENT:
            return [s.coincident(self._pts[els[0]], self._pts[els[1]])]
        if r.type == T.HORIZONTAL:
            if genres == ["ligne"]:
                return [s.horizontal(self._lignes[els[0]])]
            return [s.horizontal_points(self._pts[els[0]], self._pts[els[1]])]
        if r.type == T.VERTICAL:
            if genres == ["ligne"]:
                return [s.vertical(self._lignes[els[0]])]
            return [s.vertical_points(self._pts[els[0]], self._pts[els[1]])]
        if r.type == T.PARALLELE:
            return [s.parallel(self._lignes[els[0]], self._lignes[els[1]])]
        if r.type == T.PERPENDICULAIRE:
            return [s.perpendicular(self._lignes[els[0]], self._lignes[els[1]])]
        if r.type == T.TANGENT:
            courbes = [self._lignes[i] if e.genre(i) == "ligne" else self._arcs[i] for i in els]
            commun = set(e.extremites(els[0])) & set(e.extremites(els[1]))
            if commun:
                # Tangence en un point commun : l'angle entre les deux courbes en ce point vaut 0 ou π.
                # La contrainte générique (distance centre-droite = rayon) y a une racine double et
                # converge mal ; l'angle au point est la méthode de FreeCAD.
                pt = self._pts[sorted(commun)[0]]
                angle = s.calculate_angle_via_point(courbes[0], courbes[1], pt)
                angle = round(angle / math.pi) * math.pi
                return [s.set_angle_via_point(courbes[0], courbes[1], pt, angle)]
            if genres == ["ligne", "arc"]:
                return [s.tangent_line_arc(courbes[0], courbes[1])]
            return [s.tangent_arc_arc(courbes[0], courbes[1])]
        if r.type == T.EGAL:
            if genres == ["ligne", "ligne"]:
                return [s.equal_length(self._lignes[els[0]], self._lignes[els[1]])]
            if genres == ["cote", "cote"]:
                # la seconde cote prend la valeur de la première : son paramètre, laissé libre, lui est égalé
                return [s.equal(self._params_cotes[els[0]], self._params_cotes[els[1]])]
            return [s.equal_radius_aa(self._arcs[els[0]], self._arcs[els[1]])]
        if r.type == T.POINT_SUR_LIGNE:
            return [s.point_on_line(self._pts[els[0]], self._lignes[els[1]])]
        if r.type == T.POINT_SUR_ARC:
            return [s.point_on_arc(self._pts[els[0]], self._arcs[els[1]])]
        if r.type == T.SUR_AXE:
            return [s.coordinate_y(self._pts[els[0]], s.add_fixed_param(0.0))]
        if r.type == T.ORIGINE_Z:
            return [s.coordinate_x(self._pts[els[0]], s.add_fixed_param(0.0))]
        if r.type == T.FIXE:
            p = e.points[els[0]]
            types = {rr.type for rr in e.relations_de(p.id)}
            tags = []
            # ne figer que ce que « sur l'axe » et « origine Z » ne tiennent pas déjà, sinon redondance
            if T.ORIGINE_Z not in types:
                tags.append(s.coordinate_x(self._pts[p.id], s.add_fixed_param(p.z)))
            if T.SUR_AXE not in types:
                tags.append(s.coordinate_y(self._pts[p.id], s.add_fixed_param(p.x)))
            return tags
        if r.type == T.SUR_REFERENCE:
            # sur un plan du montage : coordonnée figée à la valeur de la référence, pour le point ou les deux
            # points de la ligne (qui devient de fait verticale ou horizontale)
            ref = e.reference_de(r.reference)
            pts = [els[0]] if genres == ["point"] else list(e.extremites(els[0]))
            figer = s.coordinate_x if ref.axe == "z" else s.coordinate_y
            return [figer(self._pts[p], s.add_fixed_param(ref.valeur)) for p in pts]
        raise ValueError(f"relation inconnue : {r.type}")

    def _points_cote(self, els: Tuple[int, ...], axe: int = 0) -> Tuple[int, int]:
        """Les deux points d'une cote (point, point) ou (ligne), rangés par z croissant (axe 0) ou x (axe 1)."""
        if len(els) == 1:
            a, b = self.esquisse.extremites(els[0])
        else:
            a, b = els
        pa, pb = self.esquisse.points[a], self.esquisse.points[b]
        va, vb = (pa.z, pb.z) if axe == 0 else (pa.x, pb.x)
        return (a, b) if va <= vb else (b, a)

    @staticmethod
    def _valeur_param(c: Cote) -> float:
        if c.type == TypeCote.DIAMETRE:
            return c.valeur / 2.0
        if c.type == TypeCote.ANGLE:
            return math.radians(c.valeur)
        return c.valeur

    @staticmethod
    def _valeur_depuis_param(c: Cote, v: float) -> float:
        if c.type == TypeCote.DIAMETRE:
            return 2.0 * v
        if c.type == TypeCote.ANGLE:
            return math.degrees(v)
        return v

    def _traduire_cote(self, c: Cote):
        """Une cote pilotante fixe son paramètre ; une cote pilotée le laisse libre et le solveur le mesure.
        Une cote qui en suit une autre (« égal ») pilote la géométrie avec un paramètre libre, égalé à l'autre."""
        s, e, els = self._s, self.esquisse, c.elements
        pilote = not c.pilotee
        param = s.add_param(self._valeur_param(c), fixed=pilote and c.id not in self._liees)
        self._params_cotes[c.id] = param
        if c.type == TypeCote.LONGUEUR_Z:
            a, b = self._points_cote(els)
            return s.difference(self._params_pts[a][0], self._params_pts[b][0], param, driving=pilote)  # z(b) - z(a)
        if c.type == TypeCote.DISTANCE:
            a, b = self._points_cote(els)
            return s.p2p_distance(self._pts[a], self._pts[b], param, driving=pilote)
        if c.type == TypeCote.DIAMETRE:
            pid = els[0] if e.genre(els[0]) == "point" else e.lignes[els[0]].p1
            return s.coordinate_y(self._pts[pid], param, driving=pilote)
        if c.type == TypeCote.RAYON:
            return s.arc_radius(self._arcs[els[0]], param, driving=pilote)
        if c.type == TypeCote.ECART:
            return s.p2l_distance(self._pts[e.lignes[els[0]].p1], self._lignes[els[1]], param, driving=pilote)
        if c.type == TypeCote.POSITION_Z:
            return s.coordinate_x(self._pts[e.point_reference(els[0])], param, driving=pilote)
        if c.type == TypeCote.LONGUEUR_X:
            a, b = self._points_cote(els, axe=1)
            return s.difference(self._params_pts[a][1], self._params_pts[b][1], param, driving=pilote)  # x(b) - x(a)
        if c.type == TypeCote.DEPUIS_REFERENCE:
            # coordonnée du point moins la valeur de la référence : écart signé, comme la position Z
            ref = e.reference_de(c.reference)
            pid = e.point_reference(els[0])
            coord = self._params_pts[pid][0 if ref.axe == "z" else 1]
            return s.difference(s.add_fixed_param(ref.valeur), coord, param, driving=pilote)
        if c.type == TypeCote.ANGLE:
            if len(els) == 1:
                li = e.lignes[els[0]]
                return s.p2p_angle(self._pts[li.p1], self._pts[li.p2], param, driving=pilote)
            return s.l2l_angle(self._lignes[els[0]], self._lignes[els[1]], param, driving=pilote)
        raise ValueError(f"cote inconnue : {c.type}")

    # -- résolution ------------------------------------------------------------------

    def _instantane(self) -> List[float]:
        return [self._s.get_param(p) for p in self._params]

    def _restaurer(self, valeurs: List[float]) -> None:
        for p, v in zip(self._params, valeurs):
            self._s.set_param(p, v)

    def _ecrire_positions(self) -> None:
        for pid, sid in self._pts.items():
            z, x = self._s.get_point(sid)
            p = self.esquisse.points[pid]
            p.z, p.x = float(z), float(x)
        for cid, param in self._params_cotes.items():
            c = self.esquisse.cotes.get(cid)
            if c is not None and (c.pilotee or cid in self._liees):
                c.valeur = self._valeur_depuis_param(c, float(self._s.get_param(param)))
                if c.type not in COTES_SIGNEES:
                    c.valeur = abs(c.valeur)

    def resoudre(self, diagnostiquer: bool = True) -> Resultat:
        """Résout le système. En cas d'échec, les positions précédentes sont conservées."""
        avant = self._instantane()
        statut = self._s.solve()
        res = Resultat(statut in _OK, _statut_texte(statut))
        if res.succes:
            self._ecrire_positions()
        else:
            self._restaurer(avant)
        if diagnostiquer:
            self.diagnostiquer(res)
        return res

    def diagnostiquer(self, res: Resultat) -> Resultat:
        """Complète `res` avec les degrés de liberté et les relations en conflit ou redondantes."""
        try:
            d = self._s.diagnose()
        except Exception:
            return res
        res.dof = int(d.dof)
        res.conflits = sorted({self._tags[int(t)] for t in d.conflicting if int(t) in self._tags})
        redondants = list(d.redundant) + list(getattr(d, "partially_redundant", []))
        res.redondants = sorted({self._tags[int(t)] for t in redondants if int(t) in self._tags})
        for ident in self.erreurs:
            if ident not in res.conflits:
                res.conflits.append(ident)
        return res

    def modifier_cote(self, cote_id: int, valeur: float) -> Resultat:
        """Change la valeur d'une cote et résout. Revient à l'ancienne valeur en cas d'échec.

        Le reste du dessin ne doit pas se déplacer : si le solveur a répondu par une translation d'ensemble,
        ce qu'il fait volontiers quand rien n'ancre l'esquisse, elle est annulée (voir `_compenser_derive`).
        """
        c = self.esquisse.cotes[cote_id]
        if c.pilotee:
            return Resultat(False, "pilotee")      # une cote pilotée se lit, elle ne se règle pas
        if cote_id in self._liees:
            return Resultat(False, "liee")         # elle suit une autre cote : c'est celle-là qu'on règle
        ancienne = c.valeur
        c.valeur = float(valeur)
        positions = {pid: (p.z, p.x) for pid, p in self.esquisse.points.items()}
        param = self._params_cotes.get(cote_id)
        if param is None:
            self.construire()
            res = self.resoudre(diagnostiquer=False)
        else:
            self._s.set_param(param, self._valeur_param(c))
            res = self.resoudre(diagnostiquer=False)
        if not res.succes:
            c.valeur = ancienne
            if param is not None:
                self._s.set_param(param, self._valeur_param(c))
        else:
            self._compenser_derive(self._points_de_cote(c), positions)
        return self.diagnostiquer(res)

    def _points_de_cote(self, c: Cote) -> set:
        """Les points qu'une cote fait légitimement bouger : ses éléments, centre d'arc compris."""
        e = self.esquisse
        pts = set()
        for ident in c.elements:
            g = e.genre(ident)
            if g == "point":
                pts.add(ident)
            elif g == "ligne":
                pts.update(e.extremites(ident))
            elif g == "arc":
                a = e.arcs[ident]
                pts.update((a.debut, a.fin, a.centre))
        return pts

    def _compenser_derive(self, exclus: set, avant: Dict[int, Tuple[float, float]]) -> None:
        """Annule la translation d'ensemble choisie par le solveur quand l'esquisse n'est pas ancrée.

        On mesure le déplacement médian des points étrangers à la cote modifiée. S'il n'est pas nul, tout
        le dessin est ramené d'autant et le système est résolu à nouveau : sans référence absolue, cette
        position est une solution et tout reste en place ; avec une référence absolue, le solveur revient
        de lui-même à la bonne position.
        """
        deltas = [(p.z - avant[pid][0], p.x - avant[pid][1])
                  for pid, p in self.esquisse.points.items() if pid not in exclus and pid in avant]
        if not deltas:
            return
        dzs = sorted(d[0] for d in deltas)
        dxs = sorted(d[1] for d in deltas)
        dz, dx = dzs[len(dzs) // 2], dxs[len(dxs) // 2]
        if abs(dz) < 1e-9 and abs(dx) < 1e-9:
            return
        instantane = self._instantane()
        for pz, px in self._params_pts.values():
            self._s.set_param(pz, self._s.get_param(pz) - dz)
            self._s.set_param(px, self._s.get_param(px) - dx)
        if self._s.solve() in _OK:
            self._ecrire_positions()
        else:
            self._restaurer(instantane)
            self._ecrire_positions()

    def glisser(self, point_id: int, z: float, x: float) -> bool:
        """Amène un point vers (z, x) en respectant les contraintes. Vrai si quelque chose a bougé.

        Essaie d'imposer les deux coordonnées, puis z seul, puis x seul : un point qui glisse
        sur une ligne horizontale suit la souris en z et garde son x.
        """
        s = self._s
        pid = self._pts[point_id]
        avant = self._instantane()
        s.set_param(self._glisse_z, float(z))
        s.set_param(self._glisse_x, float(x))
        for mode in ("zx", "z", "x"):
            tags = []
            if "z" in mode:
                tags.append(s.coordinate_x(pid, self._glisse_z))
            if "x" in mode:
                tags.append(s.coordinate_y(pid, self._glisse_x))
            statut = s.solve()
            for t in tags:
                s.clear_by_tag(t)
            if statut in _OK:
                self._ecrire_positions()
                return True
            self._restaurer(avant)
        return False
