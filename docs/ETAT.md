# CTgraph — état d'avancement

Mis à jour le 23 novembre 2026 (fin de la troisième séance, poste de la semaine).

## Fait

- Périmètre, décisions de conception et **pile technique validée** : Python 3.12, PySide6, `planegcs`,
  `pyserial`, PyInstaller (voir `CLAUDE.md`).
- **Retours du premier essai de l'esquisse, traités** : zoom centré sur le curseur ; outil Élaguer par un trait avec
  quatre modes (`ctgraph/esquisse/elagage.py`, sur une géométrie exacte `geometrie.py`) ; aimantation débrayable
  (horizontal/vertical, 45°, objets proches avec « point sur ligne/arc » et alignements, axe Z) ; sélection cumulative
  par clics et vidée par un clic dans le vide ; menu contextuel du clic droit avec relations et cotes possibles.
  Puis : symboles « -z- » et x barré pour horizontal et vertical, icônes dessinées sur les boutons d'outils,
  clic droit maintenu + molette pour changer d'outil (bulle sous le curseur), clic semi-long + glisser pour élaguer
  depuis n'importe quel outil. Les cinq boutons de cotes sont remplacés par un outil Cote unique qui déduit le type
  de l'élément cliqué et de l'endroit où la cote est posée, avec aperçu sous le curseur. Une cote qui sur-contraint
  devient automatiquement pilotée (grisée, entre parenthèses, mesurée par le solveur), réversible par le menu.
  Les contours fermés sont remplis d'une teinte discrète.
- **Module d'esquisse paramétrique, version 0.1, fonctionnel** :
  - `ctgraph/esquisse/modele.py` : points, lignes, arcs, dix relations, cinq cotes, validation des genres,
    suppression en cascade, mesures, JSON (`.ctg`).
  - `ctgraph/esquisse/solveur.py` : adaptateur PlaneGCS. Résolution, diagnostic (degrés de liberté, conflits,
    redondances), modification de cote avec retour arrière, glissement d'un point en continu (z et x, puis z seul,
    puis x seul), tangence en point commun par angle au point.
  - `ctgraph/ui/` : fenêtre en français, colonne d'outils, vue avec grille, axe, accrochage aux points et à l'axe,
    relations automatiques, outils Ligne et Arc 3 points, sélection, glissement, cotes dessinées avec flèches,
    étiquettes déplaçables, édition par double-clic, symboles des relations, couleurs d'état (vert contraint,
    rouge conflit, jaune redondant), annulation et rétablissement, fichiers récents, préférences.
  - 52 tests (`tests/`) : modèle, géométrie, élagage, solveur, interface hors écran. Tous passent.
  - `build.ps1` produit `dist\CTgraph\CTgraph.exe` (120 Mo avec Qt), vérifié au lancement.
  - `tools/make_sample.py` génère `exemples/arbre-epaule.ctg` (arbre épaulé, chanfrein, congé, entièrement contraint),
    `tools/capture.py` fait une capture en vraie fenêtre.
- **Référence du post-processeur Go2CAM** : neuf programmes ISO réels dans `docs/exemples-cn/`, syntaxe relevée dans
  `docs/reference-go2cam-ct200.md`. Les ébauches sont des trajectoires explicites G0/G1 ; filetage G33, perçage G83.
- **Git** : dépôt local initialisé (MinGit portable sur ce poste). Pas encore de dépôt distant.

## En cours

- Rien d'ouvert : la séance s'est terminée sur un état propre.

## Prochaines étapes

1. **Second essai de l'esquisse** avec les retours traités. Manques connus : pas de cote entre deux lignes parallèles,
   pas de symétrie, pas de miroir, pas de construction (lignes d'aide), pas de prolongement jusqu'à un objet,
   pas de profil intérieur distinct, pas d'export DXF.
2. **Dépôt distant privé** : créer le dépôt (GitHub ou autre), `git remote add origin …`, `git push -u origin main`.
   Sur le poste du week-end : installer Git, cloner, créer `.venv` avec `requirements.txt`.
3. **Installeur** : reprendre `installer/` et `tools/make_installer.ps1` de DXFgraph en remplaçant le nom et
   l'association de fichiers (`.ctg`).
4. **Module suivant à décider** : bibliothèque d'outils (plaquettes, porte-plaquettes, porte-outils, tourelle)
   ou définition machine, brut et prise de pièce. Le post-processeur viendra après les séquences d'usinage.
5. Retrouver le post-processeur Go2CAM et le logiciel RS232 (remis à plus tard par l'utilisateur).
6. Relever sur le tour : grille d'options, version du logiciel CN, taille mémoire, réglages série.

## Questions en attente

- Signification exacte des adresses de `G33` (Q, P, F, S, R, EB, EA) et de `G83` (P, Q, ER) : manuel NUM 750 T.
- Règle du sens de broche (M3 outils à droite, M4 outils à gauche d'après les programmes Go2CAM) : à confirmer.
- Ordre de réalisation des modules restants.
