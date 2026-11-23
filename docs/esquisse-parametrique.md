# CTgraph — Esquisse paramétrique

Rédigé le 20 novembre 2026. Copie du document tenu sur claude.ai :
https://claude.ai/artifact/LM2RqR4eRD2w8yh1dHoZCn

## Décision

Le module d'esquisse de CTgraph sera paramétrique, et le solveur retenu est **PlaneGCS**, celui de l'atelier d'esquisse de FreeCAD. Sa licence permet de garder CTgraph fermé, contrairement à celle de SolveSpace.

PlaneGCS est purement 2D, ce qui correspond exactement à un profil de tournage.

## Licences vérifiées

| Brique | Licence | Conséquence pour CTgraph |
| --- | --- | --- |
| [SolveSpace](https://github.com/noreng/solvespace) | GPL v3 | Obligerait à publier CTgraph sous GPL s'il est distribué, sauf licence commerciale négociée avec les développeurs |
| [PlaneGCS](https://pypi.org/project/planegcs/) | LGPL 2.1 ou ultérieure | Code de CTgraph non ouvert, à condition que le composant reste remplaçable (liaison dynamique en DLL) |
| [Open CASCADE](https://wiki.freecad.org/Third_Party_Libraries), pour le STEP plus tard | LGPL 2.1 depuis la version 6.7 | Même régime que PlaneGCS |

PlaneGCS ne demande qu'Eigen et Boost pour se compiler. Les obligations de la LGPL sont décrites sur la [page Licence de FreeCAD](https://wiki.freecad.org/Licence).

Une extraction en bibliothèque autonome existe sur GitHub ([libplanegcs](https://www.github.com/marcuswu/libplanegcs)), ce qui évite de découper le solveur dans les sources de FreeCAD. Son état de maintenance n'a pas été vérifié.

## Architecture en trois couches

1. **Modèle d'esquisse** : points, lignes, arcs, relations et cotes. C'est ce qui est enregistré dans le fichier de la pièce.
2. **Adaptateur solveur** : il traduit le modèle pour PlaneGCS, lance la résolution et récupère les positions. Lui seul connaît PlaneGCS, ce qui permet d'en changer.
3. **Interface** : tracé à la souris, glisser des points avec résolution en continu, édition des cotes par double-clic.

## Jeu de contraintes pour le tournage

- **Relations** : coïncident, horizontal, vertical, parallèle, perpendiculaire, tangent, égal, point sur ligne.
- **Cotes** : longueur selon Z, diamètre (distance à l'axe doublée), rayon d'arc, angle.
- **Automatismes** : les accrochages pendant le tracé posent les relations d'office. Un trait tiré à l'horizontale reçoit la relation « horizontal ».
- **Diagnostic** : le solveur fournit les degrés de liberté restants et les contraintes en conflit, d'où le code couleur habituel (sous-contraint, entièrement contraint, sur-contraint).

## Conséquence pour le reste du logiciel

Les séquences d'usinage doivent référencer le profil résolu et non en garder une copie. Modifier un diamètre dans l'esquisse recalcule alors les trajectoires et le G-code.

Cette liaison se décide maintenant, dans le modèle de données, car elle est pénible à ajouter après coup.

## Première étape

Le module d'esquisse devient le plus gros morceau de CTgraph. Un prototype minimal le dérisque :

- [ ] Compiler PlaneGCS dans une application C++ de test
- [ ] Tracer un rectangle à la souris
- [ ] Poser une cote modifiable
- [ ] Faire glisser un point avec résolution en continu

Si cela tourne en quelques jours, le reste est surtout du travail d'interface.
