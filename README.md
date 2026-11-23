# CTgraph

Logiciel de FAO pour le tour **Cazeneuve CT200** à commande numérique **NUM 750 T** (deux axes, X et Z).
Il ira du dessin de la pièce jusqu'à l'envoi du programme ISO à la machine.

État actuel : **module d'esquisse paramétrique** (version 0.1). Les autres modules (bibliothèque d'outils,
vue 3D, séquences d'usinage, post-processeur, liaison RS232) viendront ensuite. Voir `docs/ETAT.md`.

## L'esquisse

Une pièce est un **demi-profil** dans le plan (Z, X) : Z le long de l'axe de la pièce, X le rayon.
L'axe est tracé en tiret-point ; les diamètres se lisent directement dans les cotes « Ø ».

* **Changer d'outil** : les boutons à icônes de la colonne, les touches `S`, `L`, `A`, `E`, ou **clic droit
  maintenu + molette** sur le dessin : le nom de l'outil s'affiche sous le curseur.
* **Clic semi-long puis glisser** (environ un tiers de seconde sans bouger) : quel que soit l'outil, le glisser
  qui suit est un trait d'élagage ; l'outil d'avant revient au relâchement.
* **Symboles des relations** : « -z- » pour horizontal (le long de l'axe Z), un x coupant une barre verticale
  pour vertical, puis ∥, ⊥, T, =, ●, axe, F.
* **Colonne de gauche** : les outils (Sélection, Ligne, Arc 3 points, Cote, Élaguer et son mode), les relations
  (horizontal, vertical, coïncident, point sur ligne ou sur arc, parallèle, perpendiculaire, tangent, égal, sur l'axe,
  fixe), l'état du solveur avec la liste des relations et des cotes, l'affichage et l'aimantation.
* **Cote** (`C`) : un seul outil, le type se déduit. Cliquez un point : diamètre. Un arc : rayon. Une ligne, puis
  l'endroit où poser la cote : au-dessus ou au-dessous, c'est la longueur Z ; à côté, c'est le diamètre d'une ligne
  horizontale, l'angle d'une ligne inclinée, la hauteur d'une ligne verticale. Deux lignes : angle entre elles,
  longueur Z entre deux faces verticales, ou écart entre deux lignes parallèles (profondeur de gorge), que l'on
  glisse le long de la première. Deux points : longueur Z. La cote suit le curseur en aperçu, le clic la pose
  et demande sa valeur, proposée à la mesure actuelle. `Ctrl+K` ou le menu du clic droit cotent la sélection.
  Une cote qui sur-contraindrait l'esquisse devient aussitôt une **cote pilotée** : grisée, entre parenthèses,
  elle mesure la géométrie et la suit. Le menu du clic droit, ou un double-clic, la rend pilotante quand
  c'est possible, et inversement.
* **À droite** : le dessin. Molette pour zoomer autour du curseur, bouton du milieu pour déplacer la vue, `F` pour tout voir.
* **Ligne** (`L`) : cliquez le départ puis chaque sommet ; la chaîne continue jusqu'au clic droit ou `Échap`.
* **Arc 3 points** (`A`) : départ, arrivée, puis un point par où passe l'arc.
* **Élaguer** (`E`) : tirez un trait au travers des lignes ou des arcs à couper. Le mode, dans la zone Outils, dit ce
  qui est retiré autour du point traversé : *jusqu'aux croisements* avec les autres objets, *entre deux points*
  d'esquisse posés sur l'objet, *jusqu'à l'extrémité* la plus proche, ou *tout l'objet*. Les nouveaux points de coupe
  reçoivent « point sur ligne » ou « point sur arc » avec l'objet croisé : la coupe suit les modifications du profil.
* **Aimantation** (zone Affichage, chaque case se désactive) : *horizontal / vertical* pose la relation d'office sur
  un trait presque droit ; *45°* aligne le trait sur la diagonale ; *objets proches* accroche aux points (cercle),
  aux lignes et aux arcs (croix, avec la relation « point sur ») et aux alignements avec les points existants
  (pointillés) ; *axe Z* accroche à l'axe de la pièce (croix) et pose « sur l'axe ».
* **Sélection** (`S`) : les clics successifs s'ajoutent à la sélection, un second clic sur un élément le retire,
  un clic dans le vide vide la sélection. Tirez un point pour le faire glisser : le solveur recalcule tout le profil
  en continu en respectant relations et cotes. Tirez une valeur de cote pour déplacer son étiquette ; double-cliquez-la
  pour changer sa valeur. `Suppr` supprime la sélection.
* **Clic droit** : menu contextuel avec les relations et cotes possibles pour la sélection, la suppression, les outils
  et « Tout voir ». Pendant un tracé, le clic droit termine la chaîne.
* **Relations** : sélectionnez les éléments concernés puis cliquez le bouton (ou le menu du clic droit).
  Une relation ou une cote en conflit est affichée en rouge, une relation redondante en jaune.
* **État** : « sous-contraint » avec le nombre de degrés de liberté, « entièrement contraint » (profil en vert),
  ou « sur-contraint » avec les relations en cause. Un contour fermé se remplit d'une teinte discrète.
* **Vue 3D** (en haut à droite, touche `3` pour la masquer) : la pièce obtenue par révolution des contours fermés,
  mise à jour en continu. Bouton gauche : orbite. Molette : zoom. Bouton du milieu : déplacement. Double-clic ou
  `Ctrl+3` : recadrer. Le coin inférieur gauche la redimensionne.
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
et l'exemple `exemples\arbre-epaule.ctg`, inscrit la date de compilation dans `ctgraph\build_info.py` le temps
de la compilation (visible dans *Aide → À propos*) et produit `dist\CTgraph\`.

Contrôle visuel : `.venv\Scripts\python tools\capture.py captures\fenetre.png` ouvre la fenêtre sur l'exemple
et enregistre une capture.

## Organisation du code

```
ctgraph/
  main.py                  point d'entrée, QApplication
  esquisse/modele.py       points, lignes, arcs, relations, cotes ; validation ; JSON. Ne connaît pas le solveur.
  esquisse/geometrie.py    géométrie exacte : paramètres, intersections ligne/arc, point le plus proche
  esquisse/elagage.py      élagage : raccourcir ou scinder une ligne ou un arc en gardant les relations cohérentes
  esquisse/solveur.py      adaptateur PlaneGCS : traduction du modèle, résolution, glissement, diagnostic
  ui/vue_esquisse.py       QGraphicsView : tracé, aimantation, sélection, élagage, dessin des cotes et des symboles
  ui/fenetre_principale.py fenêtre, menus, menu contextuel, fichiers, annulation ; contrôleur de la vue
tests/                     modèle, géométrie, élagage, solveur, interface (plateforme Qt hors écran)
tools/                     icône, exemple, capture
docs/                      état d'avancement, décisions, référence NUM 750 T observée dans les programmes Go2CAM
```

## Licences des composants

* **PlaneGCS** (solveur de contraintes de FreeCAD) via le paquet Python `planegcs`, LGPL 2.1 ou ultérieure,
  lié dynamiquement.
* **Qt 6** via PySide6, LGPL 3.
* **pyserial** (liaison RS232, à venir), licence BSD.
