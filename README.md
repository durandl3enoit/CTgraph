# CTgraph

Logiciel de FAO pour le tour **Cazeneuve CT200** à commande numérique **NUM 750 T** (deux axes, X et Z).
Il ira du dessin de la pièce jusqu'à l'envoi du programme ISO à la machine.

État actuel : **module d'esquisse paramétrique** (version 0.1). Les autres modules (bibliothèque d'outils,
vue 3D, séquences d'usinage, post-processeur, liaison RS232) viendront ensuite. Voir `docs/ETAT.md`.

## L'esquisse

Une pièce est un **demi-profil** dans le plan (Z, X) : Z le long de l'axe de la pièce, X le rayon.
L'axe est tracé en tiret-point ; les diamètres se lisent directement dans les cotes « Ø ».

* **Colonne de gauche** : les outils de tracé (Sélection, Ligne, Arc 3 points), les relations
  (horizontal, vertical, coïncident, point sur ligne, parallèle, perpendiculaire, tangent, égal, sur l'axe, fixe),
  les cotes (longueur Z, diamètre, rayon, angle, distance), l'état du solveur avec la liste des relations
  et des cotes, et l'affichage.
* **À droite** : le dessin. Molette pour zoomer, bouton du milieu pour déplacer la vue, `F` pour tout voir.
* **Ligne** (`L`) : cliquez le départ puis chaque sommet ; la chaîne continue jusqu'au clic droit ou `Échap`.
  Le curseur s'accroche aux points existants (cercle) et à l'axe de la pièce (croix). Un trait presque
  horizontal ou vertical reçoit la relation correspondante d'office ; un point posé sur l'axe reçoit « sur l'axe ».
* **Arc 3 points** (`A`) : départ, arrivée, puis un point par où passe l'arc.
* **Sélection** (`S`) : clic sur un élément, `Ctrl` + clic pour en ajouter. Tirez un point pour le faire glisser :
  le solveur recalcule tout le profil en continu en respectant relations et cotes. Tirez une valeur de cote pour
  déplacer son étiquette ; double-cliquez-la pour changer sa valeur. `Suppr` supprime la sélection.
* **Relations et cotes** : sélectionnez les éléments concernés puis cliquez le bouton. La cote propose la mesure
  actuelle. Une relation ou une cote en conflit est affichée en rouge, une relation redondante en jaune.
* **État** : « sous-contraint » avec le nombre de degrés de liberté, « entièrement contraint » (profil en vert),
  ou « sur-contraint » avec les relations en cause.
* **Fichiers** : les esquisses sont enregistrées en `.ctg` (JSON lisible). `Ctrl+Z` / `Ctrl+Y` annulent et rétablissent.

## Lancer

* **Depuis les sources** : `.venv\Scripts\python.exe run.py [fichier.ctg]`.
* **Version compilée** : `dist\CTgraph\CTgraph.exe` (dossier autonome, à copier en entier).

## Installer l'environnement de développement

```
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m pytest tests
```

Fabrication de l'exécutable : `powershell -ExecutionPolicy Bypass -File build.ps1`. Le script génère l'icône
et l'exemple `exemples\arbre-epaule.ctg`, inscrit la date de compilation dans `ctgraph\build_info.py`
(visible dans *Aide → À propos*) et produit `dist\CTgraph\`.

Contrôle visuel : `.venv\Scripts\python tools\capture.py captures\fenetre.png` ouvre la fenêtre sur l'exemple
et enregistre une capture.

## Organisation du code

```
ctgraph/
  main.py                 point d'entrée, QApplication
  esquisse/modele.py      points, lignes, arcs, relations, cotes ; validation ; JSON. Ne connaît pas le solveur.
  esquisse/solveur.py     adaptateur PlaneGCS : traduction du modèle, résolution, glissement, diagnostic
  ui/vue_esquisse.py      QGraphicsView : tracé, accrochage, sélection, dessin des cotes et des symboles
  ui/fenetre_principale.py fenêtre, menus, fichiers, annulation ; contrôleur de la vue
tests/                    modèle, solveur, interface (plateforme Qt hors écran)
tools/                    icône, exemple, capture
docs/                     état d'avancement, décisions, référence NUM 750 T observée dans les programmes Go2CAM
```

## Licences des composants

* **PlaneGCS** (solveur de contraintes de FreeCAD) via le paquet Python `planegcs`, LGPL 2.1 ou ultérieure,
  lié dynamiquement.
* **Qt 6** via PySide6, LGPL 3.
* **pyserial** (liaison RS232, à venir), licence BSD.
