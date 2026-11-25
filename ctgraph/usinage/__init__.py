"""Usinage : la gamme, ses séquences et les trajectoires qu'elles produisent.

Le module ne connaît ni Qt ni PlaneGCS. Il reçoit le **profil résolu** de la pièce et le montage, et
rend des trajectoires ; rien n'est recopié du dessin, tout se recalcule quand une cote change. C'est la
règle posée dans `CLAUDE.md` : les séquences référencent le profil, elles n'en gardent pas de copie.
"""
from .profil import ProfilTourne, profil_exterieur
from .sequences import LIBELLES_SEQUENCE, Gamme, Sequence, TypeSequence
from .trajectoires import Mouvement, Trajectoire, trajectoire

__all__ = ["ProfilTourne", "profil_exterieur", "LIBELLES_SEQUENCE", "Gamme", "Sequence", "TypeSequence",
           "Mouvement", "Trajectoire", "trajectoire"]
