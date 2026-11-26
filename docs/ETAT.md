# CTgraph — état d'avancement

Mis à jour le 26 novembre 2026 (cinquième séance, poste de la semaine).

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
- **Vue 3D** incrustée en haut à droite de l'esquisse (`ctgraph/ui/vue_3d.py`) : révolution des contours fermés,
  orbite, zoom, déplacement, redimensionnable, masquable (touche 3). Première brique du point 3 du périmètre ;
  mandrin, brut et outil sur tourelle restent à ajouter.
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
- **Git** : dépôt local (MinGit portable sur ce poste) relié au dépôt distant privé
  `https://github.com/durandl3enoit/CTgraph` depuis le 24 novembre 2026 ; la branche `main` y est poussée.

- **Séance du 24 novembre** : cotes pilotées, écart entre parallèles, contours fermés remplis, vue 3D lisse,
  icônes sobres et icônes de relations, couple Ø/R, curseurs par outil, menu contextuel à icônes, origine Z et
  position Z, un seul élagage, zone Relations repliable, réglage des cotes à la molette, outils Arrondi et Chanfrein
  avec coin théorique conservé, dessin immobile quand une cote change, menu contextuel avec toutes les cotes
  possibles et Arrondi/Chanfrein sur un coin, cote pilotée posée sans demander de valeur, « égal » entre deux
  cotes, contour fermé par une relation coïncidente, icône de l'application sur la grille. 83 tests.

- **Module machine et montage, première version** (`ctgraph/montage.py`, `ui/dialogue_montage.py`) : machine, mandrin
  BH-M 210 et mors 474, brut rond ou tube, prise de pièce, contre-pointe ; dialogue *Pièce → Machine et montage*,
  dessin en retrait dans l'esquisse et dans la vue 3D (brut translucide), enregistré avec la pièce (`Piece`).
  Puis : les trois cotes du brut (Ø, longueur, marge en bout) toujours affichées en ambre et éditables par
  double-clic ou clic droit + molette ; **mors durs étagés et réversibles** (étages saisis dans le dialogue :
  longueur et épaulement, mors le plus épais au fond), serrage extérieur ou intérieur, appui du brut sur un
  épaulement ou sur la face du mandrin, réglés directement sur le mors dessiné (double-clic : retourner ; clic
  droit : serrage et appui), en 2D comme en 3D. Boutons de vues typiques sur la 3D : côté, face, biais réglable.
  Réglage des cotes aussi par clic droit + glisser vertical. Références gravées (« 210 BH-FC », mors
  « 12082030 (1/16"x90°) ») inscrites en haut à gauche du mandrin et du mors ; passage de barre 42 mm fixe.
  Clic droit sur la référence du mors : édition en place de toutes ses cotes, le reste grisé jusqu'à validation.
  Survol : l'élément sous le curseur luit en magenta avant le clic. Le glisser du clic droit suit la direction
  de la ligne de cote (horizontale, verticale, diagonale, rayon vers l'extérieur). Les vues 3D cadrent la pièce
  entière. Ligne biaise : longueur vraie (à côté), longueur Z (dessus), longueur X (côté, nouveau type de
  cote), angle (coin). **Références du montage** (face de référence Z = 0 à la marge du bout du brut, face des
  mors, appui, face du mandrin, surfaces du brut) : alignement et cote depuis, par le menu contextuel ou
  l'aimantation. Cotes d'angle en arc de secteur, à la façon de SolidWorks : le secteur mesuré est celui où
  l'étiquette est posée. Brut sans appui : cote « prise » réglable. 133 tests.

- **Stock d'outils, première version** (`ctgraph/outils.py`, `ui/zone_outils.py`) : catalogue des 105
  porte-plaquettes montables sur porte-outils VDI 30 (queue ≤ 20 mm), en cinq familles, désignations ISO 5608
  et ISO 6261. Zone ancrée à droite (touche `O`) : filtre, colonnes désignation / plaquette / attaque / queue /
  fixation, icône de la forme de la plaquette, infobulle d'usage, case « en stock » mémorisée.
- **Atelier : trois volets repliables latéralement** (`ui/zone_atelier.py`, `ui/volet_lateral.py`), ancrés à
  droite, touche `O` : **Tourelle**, **Stock d'outils**, **Plaquettes** (catalogue ISO 1832 de 50 tailles).
  Dans les deux catalogues, l'élément choisi est dessiné coté en dessous, chaque élément géométrique portant
  sa valeur : pour une plaquette l'arête, le cercle inscrit, le rayon de bec, l'épaisseur et la dépouille ;
  pour un porte-plaquette la longueur, la queue, l'angle d'attaque et l'alésage minimal d'une barre.
  Les deux dessins ont la même hauteur et s'alignent ; le bec coté est le coin qui travaille. L'outil est
  couché, queue rectangulaire, plaquette au bout gauche, en bas pour un outil à droite et en haut pour un
  outil à gauche. Seul le stock d'outils est déplié au premier lancement.
- **Tourelle garnie** : douze postes VDI 30 vus de face, implantation transversale en périphérie ou axiale
  (alternées, réglables poste par poste), liste des postes avec le porte-plaquette et la plaquette montés,
  et le correcteur à appliquer (numéro, X, Z, rayon de bec, orientation). Garniture mémorisée avec les
  préférences. **Glisser-déposer** d'un outil ou d'une plaquette depuis les volets voisins, sur le schéma
  comme sur le tableau des postes, avec refus de ce que l'implantation ne tient pas. Point 1 du périmètre
  bien engagé ; restent les porte-outils VDI eux-mêmes et la fiche de réglage. 135 tests.

- **Séquences d'usinage, première version** (point 4 du périmètre) : la pièce porte une **gamme**, suite
  ordonnée de séquences enregistrée dans le `.ctg`. Sept opérations : dressage de face, ébauche paraxiale,
  finition de profil, gorge, filetage, perçage dans l'axe, tronçonnage. Module `ctgraph/usinage/` sans Qt ni
  PlaneGCS : `profil.py` tire le profil tourné des contours fermés et dit où une passe a le droit de couper,
  `sequences.py` porte la gamme et ses réglages (poste, G96/G92/G95, passes, surépaisseurs, largeur d'outil,
  diamètre de fond, pas de filet, étendue en Z), `trajectoires.py` rend des suites de
  `Mouvement(z, x, travail)`, telles quelles traduisibles en G0/G1.
  Volet « Usinage » à gauche de l'atelier : liste ordonnée avec passes et longueur de coupe, un bouton
  d'ajout par type, flèches d'ordre, case d'activation, formulaire de la séquence choisie qui **ne montre
  que les réglages qui comptent pour son type**. Le poste se saisit au numéro ou **en glissant une ligne de
  la tourelle sur la séquence**. **La trajectoire de la séquence choisie se dessine sur l'esquisse** (trait
  plein en coupe, pointillé en rapide) et se recalcule à chaque changement de cote ou de montage : rien
  n'est recopié du dessin. Une passe ne descend jamais dans les mors et la finition laisse la face arrière
  au tronçonnage.
- **Voir la pièce se dégager du brut** : **la liste des opérations est le curseur d'étape**, sa première
  ligne étant le brut. Choisir une ligne montre la pièce après cette opération ; les suivantes se grisent.
  La matière restante est teintée sur le dessin et **ce que l'étape vient d'enlever ressort en orange**
  (`usinage/matiere.py` : le brut en tranches de 0,25 mm, chaque type d'opération enlevant à sa façon).
  L'ordre d'usinage se change aussi en tirant une ligne sur une autre.
  Le modèle de matière sert à voir, pas à vérifier : il ignore la forme de l'outil, donc les collisions.
- **Neuf opérations et la gamme type** : centrage et alésage s'ajoutent aux sept premières, et le bouton
  **Proposer la gamme type** pose l'enchaînement habituel d'une pièce sur barre dans l'ordre (dressage,
  centrage, perçage, ébauche, alésage ×2, finition, gorge, filetage, tronçonnage), postes repris de la
  tourelle par famille d'outil, les opérations à renseigner posées décochées. La **profondeur de perçage**
  est une cote portée sur le dessin, réglable comme celles du brut.
- **Forets** (`ctgraph/forets.py`) : seize forets hélicoïdaux et huit forets à centrer forme A, choisis
  dans un champ de l'opération. Le trou dessiné prend **la forme de l'outil** : fond conique à 135° pour un
  foret, deux étages pour un foret à centrer (bout guide, puis cône à 60°). Le Z de fin est celui de la
  pointe. Dimensions à vérifier sur les forets de l'atelier. Le curseur d'étape se voit à droite de la
  liste, poignée comprise ; boutons et gamme sont fixés en haut du volet. Une opération ajoutée se pose
  juste après l'étape montrée. La matière enlevée est dessinée en polygones suivant le milieu des tranches
  (plus d'escalier sur les cônes) et par-dessus le remplissage du profil (un trou se voit). Les **filetages**
  se dessinent en dents de scie au pas. 159 tests.

## En cours

- Les dimensions du mandrin et de la machine sont des ordres de grandeur : à relever et à saisir dans le dialogue
  (en particulier les étages des mors 474 : longueur et épaulement de chacun, épaisseur radiale au fond, largeur).
- Non prévu encore : brut en barre passant dans le mandrin (pas d'appui, longueur de brut sans objet).
- Usinage, manques connus : pas de profil intérieur dessiné — gorge et alésage se décrivent par leurs cotes,
  ils ne sont pas lus dans l'esquisse ; pas de gorge ni de filetage intérieurs ; pas de deuxième prise ;
  pas de temps estimé ; les conditions de coupe sont saisies à la main, sans table de matières ; l'ébauche
  descend tout droit, sans suivre le profil en fin de passe ; le filetage ne connaît que le pas constant.
  Rien ne vérifie qu'un outil monté sur le poste choisi peut vraiment usiner la trajectoire demandée.

## Prochaines étapes

1. **L'esquisse est utilisable** : les retours de deux essais sont traités. Manques connus : pas de symétrie ni de
   miroir, pas de lignes de construction tracées par l'utilisateur, pas de prolongement jusqu'à un objet,
   pas de profil intérieur distinct, pas d'export DXF, pas de contour passant par un sommet à trois branches.
   Module suivant proposé : **machine, brut et prise de pièce**, puis la bibliothèque d'outils minimale.
2. **Poste du week-end** : installer Git, cloner `https://github.com/durandl3enoit/CTgraph`, créer `.venv`
   avec `requirements.txt`, lancer les tests, puis `build.ps1`.
3. **Installeur** : reprendre `installer/` et `tools/make_installer.ps1` de DXFgraph en remplaçant le nom et
   l'association de fichiers (`.ctg`).
4. **Post-processeur NUM 750 T** (point 5) : traduire la gamme en ISO, trajectoires explicites G0/G1 d'abord,
   cycles en option par séquence. Squelette, changement d'outil, G96/G92/G95, G41/G42 relevés dans
   `docs/reference-go2cam-ct200.md` ; **chaque fonction se vérifie dans le manuel NUM 750 T, jamais de
   mémoire**. Relecture par l'utilisateur obligatoire avant tout envoi à la machine.
5. **Usinage, suite** : profil intérieur dessiné (gorges et alésages lus de l'esquisse), deuxième prise,
   conditions de coupe par matière, temps estimé.
6. Retrouver le post-processeur Go2CAM et le logiciel RS232 (remis à plus tard par l'utilisateur).
7. Relever sur le tour : grille d'options, version du logiciel CN, taille mémoire, réglages série.

## Questions en attente

- Géométrie exacte de la tourelle du CT200 : diamètre du disque, rayon d'implantation, et surtout quels
  postes sont en périphérie et lesquels sur la face. Le logiciel les alterne par défaut, six et six.
- Codes d'orientation du nez d'outil sur NUM 750 T, et comptage de la correction X (au rayon ou au diamètre).
- Signification exacte des adresses de `G33` (Q, P, F, S, R, EB, EA) et de `G83` (P, Q, ER) : manuel NUM 750 T.
- Règle du sens de broche (M3 outils à droite, M4 outils à gauche d'après les programmes Go2CAM) : à confirmer.
- Ordre de réalisation des modules restants.
