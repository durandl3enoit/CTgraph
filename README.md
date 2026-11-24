# CTgraph

Logiciel de FAO pour le tour **Cazeneuve CT200** à commande numérique **NUM 750 T** (deux axes, X et Z).
Il ira du dessin de la pièce jusqu'à l'envoi du programme ISO à la machine.

État actuel : **module d'esquisse paramétrique** (version 0.1). Les autres modules (bibliothèque d'outils,
vue 3D, séquences d'usinage, post-processeur, liaison RS232) viendront ensuite. Voir `docs/ETAT.md`.

## L'esquisse

Une pièce est un **demi-profil** dans le plan (Z, X) : Z le long de l'axe de la pièce, X le rayon.
L'axe est tracé en tiret-point ; les diamètres se lisent directement dans les cotes « Ø ».

* **Changer d'outil** : les boutons à icônes de la colonne, les touches `S`, `L`, `A`, `C`, `R`, `H`, `E`, ou **clic droit
  maintenu + molette** sur le dessin : une bande d'icônes défile sous le curseur, l'outil actif au milieu avec
  son nom. Le curseur porte le symbole
  de l'outil actif, avec une petite croix au point de visée.
* **Clic semi-long puis glisser** (environ un tiers de seconde sans bouger) : quel que soit l'outil, le glisser
  qui suit est un trait d'élagage ; l'outil d'avant revient au relâchement.
* **Symboles des relations** : « -z- » pour horizontal (le long de l'axe Z), un x coupant une barre verticale
  pour vertical, puis ∥, ⊥, T, =, ●, axe, F.
* **Colonne de gauche** : les outils (Sélection, Ligne, Arc 3 points, Cote, Arrondi, Chanfrein, Élaguer), la zone
  Relations, repliée
  par défaut (horizontal, vertical, coïncident, point sur ligne ou sur arc, parallèle, perpendiculaire, tangent,
  égal, sur l'axe, origine Z, fixe), l'état du solveur avec la liste des relations et des cotes, l'affichage et
  l'aimantation.
* **Cote** (`C`) : un seul outil, le type se déduit. Cliquez un point : diamètre si la cote est posée à côté,
  position Z depuis l'origine de la pièce si elle est posée au-dessus. Un arc : rayon. Une ligne, puis
  l'endroit où poser la cote : au-dessus ou au-dessous, c'est la longueur Z ; à côté, c'est le diamètre d'une ligne
  horizontale. Une **ligne inclinée** se cote selon l'endroit : à côté d'elle, entre ses extrémités, sa longueur
  vraie, dessinée parallèle ; au-dessus ou au-dessous, sa longueur Z ; à droite ou à gauche, sa longueur X
  (l'écart radial entre ses bouts) ; en diagonale au-delà d'un coin, son angle. Deux points se cotent de même.
  Une face verticale : sa position Z si la cote est posée au-dessus, sa hauteur si elle est posée à côté.
  Une **cote d'angle** se dessine comme dans une esquisse de CAO : un arc centré sur le croisement des deux
  lignes (ou sur le bout de la ligne seule, par rapport à l'axe Z), flèches aux deux bouts, rayons de rappel
  au besoin. Le secteur mesuré est celui où vous posez l'étiquette : entre les deux segments, ou son supplément
  de l'autre côté ; un chanfrein se lit 45°, pas 135°. Tirer l'étiquette dans un autre secteur change la lecture
  sans bouger le dessin. Deux lignes : angle entre elles,
  longueur Z entre deux faces verticales, ou écart entre deux lignes parallèles (profondeur de gorge), que l'on
  glisse le long de la première. Deux points : longueur Z. La cote suit le curseur en aperçu, le clic la pose
  et demande sa valeur, proposée à la mesure actuelle. `Ctrl+K` ou le menu du clic droit cotent la sélection.
  Avec le même outil, tirez une valeur de cote déjà posée pour la déplacer, double-cliquez-la pour la modifier.
  Une cote de diamètre affiche aussi le rayon équivalent sous elle ; double-cliquez l'une ou l'autre valeur pour
  l'éditer, l'autre suit.
  Une cote qui sur-contraindrait l'esquisse devient aussitôt une **cote pilotée** : grisée, entre parenthèses,
  elle mesure la géométrie et la suit ; aucune valeur n'est demandée dans ce cas. Le menu du clic droit, ou un
  double-clic, la rend pilotante quand c'est possible, et inversement.
* **Égal entre deux cotes** : sélectionnez deux cotes de même type (deux rayons, deux chanfreins, deux diamètres)
  et posez « Égal » : la seconde prend la valeur de la première et la suit ; on règle la première. Supprimer la
  relation rend la seconde indépendante.
* **À droite** : le dessin. Molette pour zoomer autour du curseur, bouton du milieu pour déplacer la vue, `F` pour tout voir.
* **Ligne** (`L`) : cliquez le départ puis chaque sommet ; la chaîne continue jusqu'au clic droit ou `Échap`.
* **Arc 3 points** (`A`) : départ, arrivée, puis un point par où passe l'arc.
* **Arrondi** (`R`) et **Chanfrein** (`H`) : cliquez le sommet entre deux lignes, donnez le rayon ou la longueur
  du pan ; la dernière valeur est proposée la fois suivante. Le sommet reste comme coin théorique, une petite croix
  hors profil tenue sur le prolongement des deux lignes : les cotes de longueur voisines s'y rattachent, et changer
  le rayon ou le chanfrein ne déplace rien d'autre. L'arrondi est tangent aux deux lignes et porte sa cote de rayon ;
  le chanfrein porte sa longueur depuis le coin théorique et son angle, à lire « 1 × 45° ».
* **Régler une cote à la molette ou en glissant** : clic droit maintenu sur la valeur d'une cote, puis molette, ou
  glisser **le long de sa ligne de cote** : horizontalement pour une longueur Z, verticalement pour un diamètre,
  en diagonale pour un écart ou une distance inclinée, vers l'extérieur de l'arc pour un rayon. Vers la droite
  ou vers le haut, la cote augmente. Un millimètre ou un degré par cran ou par tranche de quelques pixels, un
  dixième avec `Maj`. Sur le « R » d'un diamètre, c'est le rayon qui change. Le relâchement du bouton n'ouvre
  pas le menu et ne fait qu'une étape d'annulation.
* **Élaguer** (`E`) : tirez un trait au travers des lignes ou des arcs à couper. La portion retirée va jusqu'aux
  croisements voisins avec les autres objets, ou jusqu'au bout s'il n'y en a pas ; un objet sans croisement
  disparaît entier. Les nouveaux points de coupe reçoivent « point sur ligne » ou « point sur arc » avec l'objet
  croisé : la coupe suit les modifications du profil.
* **Aimantation** (zone Affichage, chaque case se désactive) : *horizontal / vertical* pose la relation d'office sur
  un trait presque droit ; *45°* aligne le trait sur la diagonale ; *objets proches* accroche aux points (cercle),
  aux lignes et aux arcs (croix, avec la relation « point sur ») et aux alignements avec les points existants
  (pointillés) ; *axe Z* accroche à l'axe de la pièce et pose « sur l'axe », et accroche à la face d'origine
  (la verticale pointillée Z = 0) et pose « origine Z ».
* **Ancrer le profil** : l'origine de la pièce est Z = 0 sur l'axe, par convention la face avant finie ; le
  mandrin sera placé par rapport à elle dans le module machine. Un profil entièrement coté garde un degré de
  liberté tant que rien ne le tient en Z : posez « origine Z » sur un point (automatique si le tracé part de
  l'origine), ou une cote « position Z » sur une face, ou « fixe » sur un point.
* **Survol** : l'élément que le prochain clic prendrait (point, ligne, arc, cote, relation) luit en magenta, une
  couleur distincte de l'orange de la sélection, quel que soit l'outil.
* **Sélection** (`S`) : les clics successifs s'ajoutent à la sélection, un second clic sur un élément le retire,
  un clic dans le vide vide la sélection. Tirez un point pour le faire glisser : le solveur recalcule tout le profil
  en continu en respectant relations et cotes. Tirez une valeur de cote pour déplacer son étiquette ; double-cliquez-la
  pour changer sa valeur. `Suppr` supprime la sélection.
* **Clic droit** : menu contextuel avec, en première ligne, les relations possibles pour la sélection sous forme
  d'icônes (le nom en infobulle), puis les cotes possibles (pour une ligne horizontale : diamètre par rapport à
  l'axe Z et longueur Z), Arrondi et Chanfrein si la sélection est un coin ou deux
  lignes concourantes, la suppression, les outils et « Tout voir ». Pendant un tracé, le clic droit termine la chaîne.
* **Relations** : sélectionnez les éléments concernés puis cliquez le bouton (ou le menu du clic droit).
  Une relation ou une cote en conflit est affichée en rouge, une relation redondante en jaune.
* **État** : « sous-contraint » avec le nombre de degrés de liberté, « entièrement contraint » (profil en vert),
  ou « sur-contraint » avec les relations en cause. Un contour fermé se remplit d'une teinte discrète.
* **Vue 3D** (en haut à droite, touche `3` pour la masquer) : la pièce obtenue par révolution des contours fermés,
  mise à jour en continu. Bouton gauche : orbite. Molette : zoom. Bouton du milieu : déplacement. Double-clic ou
  `Ctrl+3` : recadrer. Le coin inférieur gauche la redimensionne. Les boutons *Côté*, *Face* et *Biais* donnent
  les vues typiques ; la flèche de *Biais* mémorise la vue actuelle comme vue de biais ou en règle les angles.
* **Fichiers** : les esquisses sont enregistrées en `.ctg` (JSON lisible). `Ctrl+Z` / `Ctrl+Y` annulent et rétablissent.

## Machine et montage

Menu *Pièce → Machine et montage…* (`Ctrl+M`) : la machine (courses, broche, position de changement d'outil,
à relever sur le CT200), le mandrin SMW-Autoblok 210 BH-FC et ses mors 474 (dimensions à vérifier sur le mandrin ;
le passage de barre de 42 mm est une caractéristique du mandrin, affichée mais pas réglable ; les références
gravées « 210 BH-FC » et « 12082030 (1/16"x90°) » sont rappelées discrètement sur le dessin),
le brut (rond plein ou tube, diamètre, matière), la prise de pièce (serrage, mors retournés ou non, appui du
brut, dépassement de la face des mors à la face finie, surépaisseur de la face avant) et la contre-pointe.
Le brut peut aussi n'appuyer sur rien : choisissez *Aucun appui*, et la cote « prise » de l'esquisse (face des
mors → arrière du brut) se règle alors directement ; la régler fait d'office renoncer à l'appui.

Les **mors** sont des mors durs étagés et réversibles : chaque étage, numéroté depuis le bout, a une longueur et
un épaulement derrière lui ; le mors est le plus épais au fond. Mors normaux, la face étagée regarde l'axe et
serre le brut par l'extérieur ; le brut s'appuie sur l'épaulement derrière l'étage qui le serre, ou sur la face
du mandrin s'il traverse tous les étages. Mors retournés, la face étagée regarde dehors et écarte un tube par
son alésage, avec les mêmes appuis ; la face plate, vers l'axe, serre un gros brut par l'extérieur avec appui
sur le mandrin. Ces réglages se font **directement sur le mors dessiné** : double-clic pour retourner les mors,
clic droit pour choisir le serrage et l'appui (la face du mandrin ou un épaulement). Quand un appui devient
impossible, le premier réalisable est pris. Les références gravées sont rappelées en haut à gauche du corps du
mandrin et du mors ; un **clic droit sur la référence du mors** ouvre l'édition de ses cotes : L longueur de
chaque étage, h épaulement derrière lui, E épaisseur au fond, toutes réglables comme les cotes du brut, le
reste du dessin grisé et inerte jusqu'à *Valider* (ou Entrée) ; *Annuler* (ou Échap) rend le mors d'avant.
Le repère est celui de la pièce :
Z = 0 sur la face avant finie, Z négatif vers le mandrin. Le montage est enregistré avec la pièce et le dernier
réglé sert de défaut aux nouvelles pièces. Il se dessine en retrait dans l'esquisse, brut en pointillés et mors
hachurés, et dans la vue 3D, brut translucide ; la touche `M` le masque. Trois cotes du brut restent toujours
affichées en ambre : « Ø brut », « L brut », « marge » (en bout, entre la face brute et la face finie) et
« prise » (face des mors → arrière du brut).
Double-clic ou clic droit + molette pour les changer ; une longueur de brut se répartit sur le dépassement, la
prise dans les mors et la marge ne bougent pas.

**Références du montage** : la face de référence (Z = 0, en retrait de la marge par rapport au bout du brut),
la face avant des mors, l'épaulement d'appui, la face du mandrin et les surfaces du brut (extérieure, alésage
d'un tube) sont tracés en trait mixte et nommés.
Sélectionnez un point ou une face, puis clic droit : *Aligner sur une référence* pose la relation « sur une
référence » (le point ou la face y reste, et suit le montage quand il change), *Coter depuis une référence* pose
l'écart signé depuis ce plan, lu « mors 15 » ou « mandrin 190 ». Avec l'aimantation *Axe Z*, un tracé qui
s'approche d'une référence s'y accroche et reçoit la relation d'office.

## L'atelier : tourelle, stock d'outils, plaquettes

Zone ancrée à droite (*Affichage → Atelier*, touche `O`), faite de **trois volets repliables latéralement**,
de gauche à droite : **Tourelle**, **Stock d'outils**, **Plaquettes**. Chaque volet se replie sur son bandeau
vertical, d'un clic sur le bandeau ou par le menu *Affichage* ; l'état de chacun est mémorisé. Au premier
lancement, seul le stock d'outils est déplié : cliquez les bandeaux « Tourelle » et « Plaquettes » pour
ouvrir les deux autres.

### Tourelle

La tourelle du tour vue de face : un disque à **douze postes VDI 30** (DIN 69880), chacun recevant la queue
cylindrique de Ø 30 mm d'un porte-outil. Le poste 1 est en haut, la numérotation tourne dans le sens horaire.
Cliquez un poste, dans le dessin ou dans la liste, pour le mettre en travail ; la flèche le désigne.

Un porte-outil VDI se monte soit sur la circonférence de la tourelle, soit sur sa face. Sur le CT200, la
moitié des outils sont montés **transversalement en périphérie** : les outils de tournage extérieur, à queue
carrée, dont l'arête attaque le diamètre. L'autre moitié travaille **dans l'axe** : barres d'alésage, forets,
filetage intérieur, à queue cylindrique. Les postes alternent les deux implantations, et chaque poste se
règle à part. Le dessin le montre : un trait transversal en périphérie, un trait vers l'axe pour un outil
axial ; les postes garnis sont en vert.

Sous le dessin, la liste des douze postes donne pour chacun ce qui y est monté, **le porte-plaquette et sa
plaquette**, et son correcteur. Le formulaire du poste choisi permet de le garnir : le choix des
porte-plaquettes se borne à ce que l'implantation accepte, queue carrée en transversal, cylindrique en axial.
On y note aussi **les corrections à appliquer** : le numéro de correcteur sur la commande numérique, les
corrections en X et en Z, le rayon de bec, qui suit la plaquette montée, et le code d'orientation du nez
d'outil. La garniture est mémorisée avec les préférences : elle appartient à la machine, pas à la pièce.

Le diamètre du disque et le rayon d'implantation sont des ordres de grandeur, à relever sur le CT200 ; le
Ø 30 de la queue vient de la norme. La convention des codes d'orientation et la façon dont la correction X
se compte sont à vérifier dans le manuel NUM 750 T avant d'écrire le post-processeur.

### Stock d'outils

Les **porte-plaquettes montables sur les
porte-outils VDI 30** du CT200, c'est-à-dire de queue 20 mm au plus, carrée (16 × 16, 20 × 20) ou cylindrique
(Ø 10 à Ø 20). Ils sont rangés en cinq familles : extérieur en plaquette négative (ébauche), extérieur en
plaquette positive (finition), barres d'alésage, filetage, gorge et tronçonnage. Chaque ligne donne la
désignation, la plaquette précédée d'une **icône de sa forme** (losange 80°, 55° ou 35°, trigon, triangle,
carré, ronde, plaquette de filetage, de gorge, lame), l'angle d'attaque, la queue et la fixation ; l'infobulle
ajoute l'usage, l'alésage minimal des outils intérieurs et la norme.

Les désignations suivent l'**ISO 5608** (queue carrée) et l'**ISO 6261** (barres) ; les outils de filetage, de
gorge et de tronçonnage portent leur référence du commerce, signalée comme telle. Le détail de la lecture d'un
code est en tête de `ctgraph/outils.py`.

Le catalogue dit ce qu'il est **possible** de monter. Cochez la case d'une ligne pour dire que l'atelier la
possède : les coches sont mémorisées, et le filtre *En stock* n'affiche plus qu'elles. Le champ de filtre
cherche dans la désignation, la plaquette, la queue, la main et l'usage.

### Plaquettes

Les plaquettes **ISO 1832** qui garnissent ces porte-plaquettes, rangées en quatre familles : négatives
(ébauche, dépouille 0°, deux faces utilisables), positives (finition, dépouille 5 à 11°), filetage, gorge et
tronçonnage. Même principe que le stock d'outils : filtre, cases « en stock », icône de la forme.
Les colonnes donnent la dépouille, la longueur d'arête, l'épaisseur et le rayon de bec.

Choisissez une ligne : la plaquette est **dessinée cotée** en dessous, de face avec son contour, ses becs
arrondis et son cercle inscrit, de profil avec son épaisseur `s` et son angle de dépouille `α` ; le bec est
entouré et repéré `r`. Les deux lignes sous le dessin donnent les valeurs. La lecture d'un code ISO 1832 est
détaillée en tête de `ctgraph/plaquettes.py`.

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
  montage.py               machine, mandrin, mors étagés, brut, prise de pièce ; plans de référence
  outils.py                catalogue des porte-plaquettes montables en VDI 30 (ISO 5608 et ISO 6261)
  plaquettes.py            formes, géométrie et catalogue des plaquettes (ISO 1832)
  tourelle.py              tourelle VDI 30 à douze postes : répartition, poste en travail
  ui/vue_esquisse.py       QGraphicsView : tracé, aimantation, sélection, élagage, dessin des cotes et des symboles
  ui/zone_atelier.py       les trois volets repliables ancrés à droite
  ui/volet_lateral.py      volet repliable latéralement : bandeau vertical cliquable
  ui/zone_tourelle.py      tourelle vue de face, poste en travail au clic
  ui/zone_outils.py        volet « Stock d'outils » : catalogue filtrable, cases « en stock »
  ui/zone_plaquettes.py    volet « Plaquettes » : catalogue et dessin coté de la plaquette choisie
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
