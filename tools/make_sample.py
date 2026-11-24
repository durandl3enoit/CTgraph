"""Génère exemples/arbre-epaule.ctg : un arbre épaulé avec congé, entièrement contraint.

Usage : .venv\\Scripts\\python tools\\make_sample.py [dossier]
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ctgraph.esquisse.modele import Esquisse, TypeCote, TypeRelation  # noqa: E402
from ctgraph.esquisse.solveur import AdaptateurSolveur  # noqa: E402


def arbre_epaule() -> Esquisse:
    e = Esquisse()
    p0 = e.ajouter_point(0, 0)          # face avant, sur l'axe
    p1 = e.ajouter_point(0, 14)         # face avant, haut du chanfrein
    p1b = e.ajouter_point(-1, 15)       # fin du chanfrein 1 x 45°
    p2 = e.ajouter_point(-30, 15)       # fin du petit diamètre, début du congé
    c = e.ajouter_point(-30, 18)        # centre du congé R3
    p3 = e.ajouter_point(-33, 18)       # fin du congé, sur l'épaulement
    p4 = e.ajouter_point(-33, 25)       # haut de l'épaulement
    p5 = e.ajouter_point(-80, 25)       # fin du grand diamètre
    p6 = e.ajouter_point(-80, 0)        # retour sur l'axe
    face = e.ajouter_ligne(p0.id, p1.id)
    chanfrein = e.ajouter_ligne(p1.id, p1b.id)
    petit = e.ajouter_ligne(p1b.id, p2.id)
    conge = e.ajouter_arc(c.id, p2.id, p3.id, horaire=True)   # quart de cercle, du bas vers la gauche du centre
    epaul = e.ajouter_ligne(p3.id, p4.id)
    grand = e.ajouter_ligne(p4.id, p5.id)
    fond = e.ajouter_ligne(p5.id, p6.id)
    e.ajouter_relation(TypeRelation.SUR_AXE, (p0.id,))
    e.ajouter_relation(TypeRelation.FIXE, (p0.id,))
    e.ajouter_relation(TypeRelation.SUR_AXE, (p6.id,))
    e.ajouter_relation(TypeRelation.VERTICAL, (face.id,))
    e.ajouter_relation(TypeRelation.HORIZONTAL, (petit.id,))
    e.ajouter_relation(TypeRelation.VERTICAL, (epaul.id,))
    e.ajouter_relation(TypeRelation.HORIZONTAL, (grand.id,))
    e.ajouter_relation(TypeRelation.VERTICAL, (fond.id,))
    e.ajouter_relation(TypeRelation.TANGENT, (petit.id, conge.id))
    e.ajouter_relation(TypeRelation.TANGENT, (epaul.id, conge.id))
    e.ajouter_cote(TypeCote.DIAMETRE, (petit.id,), 30.0, (8.0, 0.0))
    e.ajouter_cote(TypeCote.DIAMETRE, (grand.id,), 50.0, (-40.0, 0.0))
    e.ajouter_cote(TypeCote.LONGUEUR_Z, (p1b.id, p1.id), 1.0, (0.0, 4.0))
    e.ajouter_cote(TypeCote.ANGLE, (chanfrein.id,), 135.0, (3.0, -4.0))
    e.ajouter_cote(TypeCote.LONGUEUR_Z, (p3.id, p0.id), 33.0, (0.0, 12.0))
    e.ajouter_cote(TypeCote.LONGUEUR_Z, (p6.id, p0.id), 80.0, (0.0, -10.0))
    e.ajouter_cote(TypeCote.RAYON, (conge.id,), 3.0, (-4.0, 3.0))
    s = AdaptateurSolveur(e)
    res = s.resoudre()
    if not res.entierement_contraint:
        raise SystemExit(f"exemple mal contraint : {res.texte()} {res.conflits}")
    return e


def main() -> None:
    dossier = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "..", "exemples")
    os.makedirs(dossier, exist_ok=True)
    chemin = os.path.abspath(os.path.join(dossier, "arbre-epaule.ctg"))
    from ctgraph.montage import Brut, Montage, Piece, PriseDePiece
    piece = Piece(arbre_epaule(), Montage(brut=Brut(diametre=56.0), prise=PriseDePiece(depassement=95.0)))
    with open(chemin, "w", encoding="utf-8") as f:
        f.write(piece.to_json())
    print("Écrit :", chemin)


if __name__ == "__main__":
    main()
