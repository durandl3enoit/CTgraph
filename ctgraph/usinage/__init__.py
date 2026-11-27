"""Usinage : la gamme, ses séquences et les trajectoires qu'elles produisent.

Le module ne connaît ni Qt ni PlaneGCS. Il reçoit le **profil résolu** de la pièce et le montage, et
rend des trajectoires ; rien n'est recopié du dessin, tout se recalcule quand une cote change. C'est la
règle posée dans `CLAUDE.md` : les séquences référencent le profil, elles n'en gardent pas de copie.
"""
from .matiere import EtatMatiere, etats
from .profil import ProfilTourne, profil_exterieur, profil_interieur
from .sequences import ALESAGES, LIBELLES_SEQUENCE, Gamme, Sequence, TypeSequence
from .trajectoires import Mouvement, Trajectoire, fond_alesage, paroi_alesage, trajectoire

__all__ = ["ProfilTourne", "profil_exterieur", "profil_interieur", "LIBELLES_SEQUENCE", "ALESAGES",
           "Gamme", "Sequence", "TypeSequence", "Mouvement", "Trajectoire", "trajectoire",
           "fond_alesage", "paroi_alesage", "EtatMatiere", "etats"]
