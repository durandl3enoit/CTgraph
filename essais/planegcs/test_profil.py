"""Essai de dérisquage PlaneGCS pour CTgraph (23 novembre 2026).

Ce n'est pas du code de l'application : c'est la preuve que la liaison Python de PlaneGCS
fait ce dont le module d'esquisse a besoin. À lancer dans un environnement virtuel :

    py -3.12 -m venv .venv
    .venv\\Scripts\\pip install planegcs==0.9.6
    .venv\\Scripts\\python essais\\planegcs\\test_profil.py

Demi-profil de tournage dans le plan (Z, X) : un arbre épaulé.
Axe horizontal = Z, axe vertical = rayon (diamètre / 2).

   P4 ─────── P3
   │          │
   │          P2 ───── P1
   │                   │
   P5 ───────────────── P0   (axe de la pièce, rayon 0)

Vérifie : résolution, cotes pilotantes (longueur selon Z, diamètre), diagnostic des degrés
de liberté, modification d'une cote, glissement d'un point avec résolution en continu,
détection d'une sur-contrainte, chronométrage.
"""

import math
import time

from planegcs import Sketch, SolveStatus

s = Sketch()

# Points initiaux (Z, R) approximatifs : le solveur les corrige.
p0 = s.add_fixed_point(0.0, 0.0)        # origine : face avant sur l'axe
p1 = s.add_point(0.0, 15.2)             # face avant, bout du petit diamètre
p2 = s.add_point(-30.1, 15.0)           # épaulement, petit diamètre
p3 = s.add_point(-30.0, 25.3)           # épaulement, grand diamètre
p4 = s.add_point(-80.2, 25.0)           # fin du grand diamètre
p5 = s.add_point(-80.0, 0.1)            # retour sur l'axe

face = s.add_line(p0, p1)
petit = s.add_line(p1, p2)
epaul = s.add_line(p2, p3)
grand = s.add_line(p3, p4)
fond = s.add_line(p4, p5)
axe = s.add_line(p5, p0)

# Relations géométriques
s.vertical(face)
s.horizontal(petit)
s.vertical(epaul)
s.horizontal(grand)
s.vertical(fond)
s.horizontal(axe)

# Cotes pilotantes : chacune est un paramètre fixe que l'on peut relire et modifier
d_petit = s.add_fixed_param(30.0)       # diamètre 30
d_grand = s.add_fixed_param(50.0)       # diamètre 50
l_petit = s.add_fixed_param(30.0)       # longueur Z du petit diamètre
l_total = s.add_fixed_param(80.0)       # longueur totale

# Cote de diamètre : la coordonnée rayon d'un point vaut la moitié du paramètre diamètre
r_petit = s.add_param(15.0)
r_grand = s.add_param(25.0)
s.proportional(r_petit, d_petit, 0.5)   # r = 0,5 × d
s.proportional(r_grand, d_grand, 0.5)
s.coordinate_y(p1, r_petit)
s.coordinate_y(p3, r_grand)

s.p2p_distance(p1, p2, l_petit)          # longueur du petit diamètre
tag_l_total = s.p2p_distance(p0, p5, l_total)  # longueur totale

status = s.solve()
diag = s.diagnose()
print("statut            :", status)
print("degrés de liberté :", diag.dof, "| conflits :", diag.conflicting, "| redondants :", diag.redundant)
for name, pid in (("P0", p0), ("P1", p1), ("P2", p2), ("P3", p3), ("P4", p4), ("P5", p5)):
    z, r = s.get_point(pid)
    print(f"  {name}: Z={z:8.3f}  X(diam)={2*r:8.3f}")

assert status == SolveStatus.Success
assert diag.dof == 0, "le profil devrait être entièrement contraint"
assert abs(2 * s.get_point(p1)[1] - 30.0) < 1e-6
assert abs(s.get_point(p4)[0] + 80.0) < 1e-6

# --- Modification d'une cote : diamètre 50 -> 56 ---
s.set_param(d_grand, 56.0)
status = s.solve()
print("\naprès D grand = 56 :", status, "| P3 diam =", round(2 * s.get_point(p3)[1], 3),
      "| P4 diam =", round(2 * s.get_point(p4)[1], 3))
assert abs(2 * s.get_point(p3)[1] - 56.0) < 1e-6

# --- Glissement d'un point : on relâche la longueur totale et on tire P4 à la souris ---
s.clear_by_tag(tag_l_total)
diag = s.diagnose()
print("\nlongueur totale relâchée, DOF =", diag.dof)
assert diag.dof == 1

t0 = time.perf_counter()
n = 300
for i in range(n):
    z_souris = -80.0 - 20.0 * math.sin(i / n * math.pi)
    # contrainte temporaire : P5 (donc P4) suit la souris en Z
    tag = s.set_p2p_distance(p0, p5, -z_souris)
    st = s.solve()
    s.clear_by_tag(tag)
    assert st == SolveStatus.Success, st
dt = time.perf_counter() - t0
print(f"{n} glissements résolus en {dt*1000:.1f} ms  ({dt/n*1e6:.0f} µs par résolution)")
z4, r4 = s.get_point(p4)
print("P4 final : Z =", round(z4, 3), " diam =", round(2 * r4, 3))

# --- Sur-contrainte volontaire : deux longueurs totales incompatibles ---
s.set_p2p_distance(p0, p5, 80.0)
bad = s.set_p2p_distance(p0, p5, 90.0)
diag = s.diagnose()
print("\nsur-contrainte : conflits =", [(c.type_name, c.entities) for c in diag.conflicting_info])
assert diag.is_over_constrained
s.clear_by_tag(bad)
print("\nOK : tous les tests passent.")
