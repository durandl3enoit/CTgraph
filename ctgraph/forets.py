r"""Forets et forets à centrer : ce qu'ils laissent comme trou.

Un foret ne perce pas un trou à fond plat. Sa pointe est un cône, et un foret à centrer a deux étages :
un petit bout cylindrique qui guide, puis un cône qui ouvre le centre au diamètre du corps. Pour voir
l'enlèvement de matière tel qu'il est, il faut donc connaître la forme de l'outil, pas seulement son
diamètre.

Chaque foret se décrit ici par son **profil mesuré depuis la pointe** : `rayon_a(t)` donne le rayon du
trou à la distance `t` en arrière de la pointe. Le modèle de matière n'a besoin que de cela.

```
foret hélicoïdal                     foret à centrer, forme A (DIN 333)
         |<--- D --->|                        |<------ D ------>|
    _____|___________|_____             ______|_________________|______
         \           /                        \               /          cône à 60°
          \   2θ    /   pointe à 135°          \____   ____/
           \       /                            | d |              bout cylindrique qui guide
            \     /                              \ /               pointe à 118°
             \   /                                V
              \ /
               V
```

Les dimensions sont celles des séries courantes. **À vérifier sur les forets de l'atelier** : l'angle de
pointe en particulier dépend de l'affûtage (118° sur un foret HSS ordinaire, 135° sur un foret à âme
amincie ou carbure, qui est ce que l'utilisateur emploie).
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Optional

ANGLE_POINTE = 135.0            # pointe d'un foret hélicoïdal, angle au sommet
ANGLE_POINTE_PILOTE = 118.0     # pointe du bout guide d'un foret à centrer
ANGLE_CENTRE = 60.0             # cône d'un foret à centrer forme A : reçoit une pointe de tour à 60°


def _hauteur_cone(rayon: float, angle_sommet: float) -> float:
    """Hauteur du cône de pointe qui atteint ce rayon, pour un angle au sommet donné."""
    demi = math.radians(max(min(angle_sommet, 179.0), 1.0) / 2.0)
    return rayon / math.tan(demi)


@dataclass(frozen=True)
class Foret:
    """Un foret du stock. `pilote` non nul : c'est un foret à centrer, à deux étages."""
    designation: str
    diametre: float                  # diamètre du corps, celui du trou percé
    angle_pointe: float = ANGLE_POINTE
    pilote: float = 0.0              # foret à centrer : diamètre du bout guide
    longueur_pilote: float = 0.0     # longueur de ce bout cylindrique
    angle_centre: float = ANGLE_CENTRE

    @property
    def a_centrer(self) -> bool:
        return self.pilote > 0.0

    @property
    def rayon(self) -> float:
        return self.diametre / 2.0

    def hauteur_pointe(self) -> float:
        """Longueur du cône de pointe : ce que le foret descend avant de percer son plein diamètre."""
        if self.a_centrer:
            return _hauteur_cone(self.pilote / 2.0, self.angle_pointe)
        return _hauteur_cone(self.rayon, self.angle_pointe)

    def longueur_utile(self) -> float:
        """De la pointe au plein diamètre du corps : au-delà, le trou ne s'élargit plus."""
        if not self.a_centrer:
            return self.hauteur_pointe()
        return (self.hauteur_pointe() + self.longueur_pilote
                + _hauteur_cone(self.rayon - self.pilote / 2.0, self.angle_centre))

    def rayon_a(self, t: float) -> float:
        """Le rayon du trou à la distance `t` en arrière de la pointe. Zéro devant la pointe."""
        if t <= 0.0:
            return 0.0
        pointe = self.hauteur_pointe()
        if not self.a_centrer:
            return min(self.rayon, t / max(pointe, 1e-9) * self.rayon)
        rayon_pilote = self.pilote / 2.0
        if t <= pointe:
            return t / max(pointe, 1e-9) * rayon_pilote
        if t <= pointe + self.longueur_pilote:
            return rayon_pilote
        monte = _hauteur_cone(self.rayon - rayon_pilote, self.angle_centre)
        reste = t - pointe - self.longueur_pilote
        if reste >= monte:
            return self.rayon
        return rayon_pilote + reste / max(monte, 1e-9) * (self.rayon - rayon_pilote)

    def profil(self, z_pointe: float, z_face: float, pas: float = 0.25) -> List[tuple]:
        """Le trou laissé entre la pointe et la face, en points (z, rayon), du fond vers la face."""
        points = []
        z = z_pointe
        while z <= z_face + 1e-9:
            points.append((z, self.rayon_a(z - z_pointe)))
            z += pas
        return points

    def description(self) -> str:
        if self.a_centrer:
            return (f"Foret à centrer Ø {nombre(self.pilote)} × Ø {nombre(self.diametre)}, cône à "
                    f"{nombre(self.angle_centre)}°, pointe à {nombre(self.angle_pointe)}°")
        return f"Foret hélicoïdal Ø {nombre(self.diametre)}, pointe à {nombre(self.angle_pointe)}°"


def nombre(valeur: float) -> str:
    """Un nombre à la française : virgule décimale, pas de zéro inutile."""
    return f"{valeur:g}".replace(".", ",")


def _catalogue() -> List[Foret]:
    """Les forets courants de l'atelier. À compléter avec ce qui est réellement en tiroir."""
    cat: List[Foret] = []
    # forets hélicoïdaux : la série métrique usuelle, plus les Ø de perçage avant taraudage
    for d in (3.0, 4.0, 5.0, 6.0, 6.8, 8.0, 8.5, 10.0, 10.2, 11.0, 12.0, 13.0, 14.0, 16.0, 18.0, 20.0):
        cat.append(Foret(f"Foret Ø {nombre(d)}", d))
    # forets à centrer forme A (DIN 333) : bout guide d, corps D, cône à 60°
    for pilote, corps in ((1.0, 3.15), (1.6, 4.0), (2.0, 5.0), (2.5, 6.3), (3.15, 8.0), (4.0, 10.0),
                          (5.0, 12.5), (6.3, 16.0)):
        cat.append(Foret(f"À centrer {nombre(pilote)} × {nombre(corps)}", corps, ANGLE_POINTE_PILOTE,
                         pilote, round(pilote * 1.3, 2)))
    return cat


CATALOGUE: List[Foret] = _catalogue()


def foret(designation: str) -> Optional[Foret]:
    """Le foret de ce nom, ou None s'il n'est pas au catalogue."""
    return next((f for f in CATALOGUE if f.designation == designation), None)


def forets(a_centrer: bool) -> List[Foret]:
    """Les forets à centrer, ou les forets hélicoïdaux."""
    return [f for f in CATALOGUE if f.a_centrer == a_centrer]


def pour_diametre(diametre: float, a_centrer: bool = False) -> Foret:
    """Le foret du catalogue à ce diamètre, sinon un foret ordinaire de ce diamètre."""
    exact = next((f for f in forets(a_centrer) if abs(f.diametre - diametre) < 1e-6), None)
    return exact if exact is not None else Foret(f"Foret Ø {nombre(diametre)}", max(diametre, 0.1))
