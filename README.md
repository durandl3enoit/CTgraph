# CTgraph

Logiciel de FAO pour le tour **Cazeneuve CT200** à commande numérique **NUM 750 T** (deux axes, X et Z).
Il ira du dessin de la pièce jusqu'à l'envoi du programme ISO à la machine.

État actuel : **esquisse paramétrique, montage, bibliothèque d'outils et premières séquences d'usinage**
(version 0.1). Le post-processeur NUM 750 T et la liaison RS232 viendront ensuite. Voir `docs/ETAT.md`.

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
affichées en ambre : « Ø brut », « L brut », « dépassement brut » (face des mors → face finie, juste sous la
longueur), « marge » (en bout, entre la face brute et la face finie) et « prise » (face des mors → arrière
du brut).
Double-clic ou clic droit + molette pour les changer ; une longueur de brut se répartit sur le dépassement, la
prise dans les mors et la marge ne bougent pas.

**Références du montage** : la face de référence (Z = 0, en retrait de la marge par rapport au bout du brut),
la face avant des mors, l'épaulement d'appui, la face du mandrin et les surfaces du brut (extérieure, alésage
d'un tube) sont tracés en trait mixte et nommés.
Sélectionnez un point ou une face, puis clic droit : *Aligner sur une référence* pose la relation « sur une
référence » (le point ou la face y reste, et suit le montage quand il change), *Coter depuis une référence* pose
l'écart signé depuis ce plan, lu « mors 15 » ou « mandrin 190 ». Avec l'aimantation *Axe Z*, un tracé qui
s'approche d'une référence s'y accroche et reçoit la relation d'office.

## L'atelier : usinage, tourelle, stock d'outils, plaquettes

Zone ancrée à droite (*Affichage → Atelier*, touche `O`), faite de **volets repliables latéralement**,
de gauche à droite : **Usinage**, **Tourelle**, **Stock d'outils**, **Plaquettes**. Chaque volet se replie sur
son bandeau vertical, d'un clic sur le bandeau ou par le menu *Affichage* ; l'état de chacun est mémorisé. Les
bandeaux sont présentés de la même façon : le titre en haut, lu de haut en bas, et un chevron qui montre le
sens où le contenu va aller — vers la gauche quand le volet est replié, vers la droite quand il est déployé.
Au premier lancement, seul le stock d'outils est déplié : cliquez les autres bandeaux pour les ouvrir.

### Usinage

La **gamme** de la pièce : la suite ordonnée des séquences à exécuter. Le bouton **Proposer la gamme type**
pose d'un coup l'enchaînement habituel d'une pièce sur barre, dans l'ordre, du plus rigide au moins rigide :
dressage, centrage, perçage, ébauche, alésage (ébauche puis finition), finition de profil, gorge, filetage,
tronçonnage. Les opérations qui demandent une cote que le dessin ne donne pas sont posées décochées : l'ordre
est là, il reste à dire si la pièce en a besoin, et à les renseigner. Les postes sont pris de la tourelle,
par famille d'outil, quand elle porte ce qu'il faut.

Chaque opération **part de la matière que l'opération d'avant a laissée** : l'ébauche attaque le diamètre
qui reste, l'alésage le trou déjà percé, et aucune approche rapide ne traverse le métal. Les passes se
limitent à ce qu'il y a vraiment à couper — une ébauche ne brasse pas l'air au-dessus d'un diamètre déjà
fait — et une ébauche s'arrête d'une surépaisseur avant un épaulement, pour que la finition ait de quoi
dresser la face.

Dix opérations :

* **dressage de face** : passes de la matière vers l'axe, du bout du brut jusqu'à la face finie ;
* **centrage** : pointe l'axe avant le foret, ou perce le centre de la contre-pointe ;
* **perçage dans l'axe** : de la face vers le fond du trou, par débourrages successifs ;
* **ébauche de chariotage** : passes parallèles à l'axe, du diamètre du brut jusqu'au profil augmenté de la
  surépaisseur de finition ; une passe plus profonde que l'épaulement qui la précède n'entre en matière
  qu'après lui ;
* **ébauche d'alésage** : ouvre le trou percé jusqu'à la paroi voulue, à la barre, en passes parallèles à
  l'axe, en laissant la surépaisseur de finition. **Au plan** — sans diamètre donné, c'est le défaut —
  elle suit la paroi dessinée de l'alésage, **épaulements compris**, jusqu'au fond du trou dessiné : les
  passes épousent les marches, s'arrêtent d'une surépaisseur devant chaque épaulement et ne repassent pas
  dans ce qu'une passe plus fine a déjà ouvert, exactement comme l'ébauche extérieure d'un arbre épaulé.
  Un diamètre donné en fait un cylindre que l'on place à la main ;
* **finition d'alésage** : un passage le long de la paroi, au plan ou au diamètre donné ;
* **finition extérieure** : un passage qui suit le profil fini ;
* **gorge** : des plongées côte à côte, à la largeur de l'outil, jusqu'au diamètre de fond ; une gorge plus
  large que l'outil se fait en autant de plongées qu'il faut, qui se recouvrent ;
* **filetage**, extérieur ou **intérieur** : des passes le long du filet, de plus en plus fines pour garder
  la section de copeau. La profondeur du filet est celle du profil ISO métrique tant qu'on n'en donne pas
  une autre, et l'avance d'un filetage est son pas ;
* **tronçonnage** : une plongée jusqu'au diamètre demandé, ou jusqu'à l'axe pour détacher la pièce.

Les boutons du haut ajoutent une séquence, chacun avec les conditions de coupe habituelles de son type ;
elle se pose **juste après l'étape montrée**, pas en fin de gamme. La case de chaque ligne l'active ou la met
de côté sans la perdre. La liste donne pour chaque séquence son poste de tourelle, le nombre de passes et la
longueur à couper. L'ordre d'usinage se change avec les flèches, ou en **tirant une ligne sur une autre** :
un trait montre où elle va se poser.

**La liste est le curseur d'étape.** Sa première ligne est le *brut*, tel qu'il est serré ; choisir une ligne
montre la pièce telle qu'elle est après cette opération, et les lignes qui suivent se grisent, n'étant pas
encore passées. Le curseur se voit à droite de la liste : un trait, un cran par étape, et une **poignée** en
face de la ligne choisie, que l'on tire à la souris ou que l'on pousse à la molette. La matière qui reste est
teintée sur le dessin, et **ce que l'étape vient d'enlever ressort en orange**, à côté de la trajectoire qui
l'a enlevée. Les boutons et la gamme restent fixés en haut du volet ; seul le formulaire défile.

Le **perçage et le centrage** montrent le trou tel que le foret le laisse : fond conique à 135° pour un foret
hélicoïdal, et pour un foret à centrer les deux étages — bout guide au petit diamètre, puis cône à 60° jusqu'au
corps. Le foret se choisit dans un champ de l'opération ; le *Z de fin* est celui de la **pointe**, si bien
qu'un centrage trop court ne fait que son avant-trou, et cela se voit. Le **filetage** se dessine en dents de
scie au pas, entre la crête et le fond de filet : il n'enlève pas de matière à la silhouette — un filet est une
rainure hélicoïdale — mais on voit qu'il est fait. Le modèle de matière sert à voir, pas à vérifier : il ne
détecte aucune collision.

Le formulaire règle la séquence choisie et **ne montre que les réglages qui comptent pour son type**, nommés
pour ce qu'ils y sont (« Fond du trou » plutôt que « Z de fin ») : une finition n'a ni passes ni surépaisseur,
une gorge demande la largeur de l'outil et le diamètre de fond, un filetage son pas. Le filetage, le perçage
et le centrage tournent à vitesse de broche fixe : il n'y a pas de limitation de broche à régler. Le poste de
tourelle, écrit `T1` à `T12` comme sur la machine, se saisit au numéro, ou
**en glissant une ligne du volet Tourelle sur la séquence** : elle prend ce poste avec la combinaison qui y
est montée, rappelée sous le numéro.

Certaines valeurs se règlent **directement sur le dessin**, comme les cotes du brut. Les quatre opérations
en profondeur — centrage, perçage, alésage, filetage — portent la leur sous l'axe : « P 30 » pour une
profondeur, « L 20 » pour une longueur de filet. Elle se change au double-clic ou au clic droit + molette.
**Sa référence est la surface travaillée** : après un dressage, on perce depuis la face dressée, pas depuis
le bout du brut.

Les opérations proposées par la gamme type sont décochées quand elles demandent une cote que le dessin ne
donne pas, mais elles partent de réglages qui donnent un résultat visible : on coche, on voit, on ajuste.

Le dessin de la pièce est un **support** : il sert de référence géométrique aux opérations, qui s'y
aimantent sans s'y figer. Chaque opération se voit en surimpression du dessin et se reprend à la souris.

**Toutes les opérations ont leurs poignées.** Sa **poignée centrale** — le rond orange au milieu de la
zone rouge — déplace l'opération d'un endroit de la pièce à un autre ; le rayon où vous la lâchez décide
du côté usiné : dans le trou, l'opération devient **intérieure** ; sur le profil, **extérieure**. C'est
ainsi qu'un filetage ou une gorge passe de l'extérieur à l'alésage. Les **prises de bord** — arêtes et
coins — poussent une limite à la fois, et chacune règle ce qui a un sens pour l'opération : le bord
gauche d'une gorge est sa largeur, celui d'un dressage la surépaisseur laissée sur la face ; la paroi
d'une ébauche est la surépaisseur laissée au rayon, celle d'un perçage le diamètre du foret, celle d'un
alésage le diamètre alésé. L'aimantation de l'esquisse joue : la zone s'aligne sur les points, les faces
et les plans de référence de la pièce finie.

Une barre d'alésage bore ce qu'elle peut atteindre : elle part du trou par lequel elle entre, et une
passe ne court que là où elle a au plus sa profondeur à prendre — elle s'arrête au cône du foret, mais
dresse en passant la surépaisseur laissée sur la face d'un épaulement. Un diamètre plus grand derrière un
plus petit — un dégagement intérieur — n'est pas pour la barre : il attend une gorge intérieure. Seul le
trou d'entrée borne le diamètre alésé : un alésage Ø 6 est permis. Lâcher la poignée de paroi sur la
paroi dessinée de l'alésage ramène l'opération **au plan** ; la lâcher ailleurs en fait un cylindre. Sur
une pièce dessinée pleine, un alésage au plan dit qu'il lui manque le trou.

Chaque opération porte sa cote maîtresse dans son nom — « Perçage Ø 10 », « Alésage Ø 20 » ou
« Alésage au plan », « Gorge Ø 20 × 4 », « Filetage pas 1,5 » — pour que deux lignes voisines se
distinguent d'un coup d'œil. Un nom donné à la main l'emporte.

La **trajectoire de la séquence choisie se dessine sur l'esquisse** : trait plein pour la coupe, pointillé pour
les déplacements rapides, un cercle au point de départ. Elle est **recalculée depuis le profil résolu**, jamais
recopiée : changer une cote, un diamètre de brut ou la prise de pièce la refait aussitôt. Le chemin est celui
de la pointe théorique de l'outil ; la correction de rayon de bec sera posée par la commande numérique. Une
séquence ne descend jamais dans les mors, et la finition ne redescend pas la face arrière jusqu'à l'axe : la
pièce y tient encore à la barre, c'est au tronçonnage de la détacher.

La gamme est enregistrée avec la pièce dans le fichier `.ctg`. Le G-code viendra ensuite (point 5 du
périmètre) ; aucun programme ne partira à la machine sans relecture.

### Tourelle

La tourelle du tour vue de face : un disque à **douze postes VDI 30** (DIN 69880), chacun recevant la queue
cylindrique de Ø 30 mm d'un porte-outil. Les postes s'écrivent **T1 à T12**, comme sur la commande numérique ;
T1 est en haut, la numérotation tourne dans le sens horaire.
Cliquez un poste, dans le dessin ou dans la liste, pour le mettre en travail ; la flèche le désigne.

Un porte-outil VDI se monte soit sur la circonférence de la tourelle, soit sur sa face. Sur le CT200, la
moitié des outils sont montés **transversalement en périphérie** : les outils de tournage extérieur, à queue
carrée, dont l'arête attaque le diamètre. L'autre moitié travaille **dans l'axe** : barres d'alésage, forets,
filetage intérieur, à queue cylindrique. Les postes alternent les deux implantations, et chaque poste se
règle à part. Le dessin le montre : un trait transversal en périphérie, un trait vers l'axe pour un outil
axial ; les postes garnis sont en vert.

Sous le dessin, la liste des douze postes, tous visibles d'un coup, donne pour chacun ce qui y est monté,
**le porte-plaquette et sa plaquette**, et son correcteur. C'est le volet entier qui défile si la fenêtre est
courte, pour que le disque garde une taille lisible. Le formulaire du poste choisi permet de le garnir : le choix des
porte-plaquettes se borne à ce que l'implantation accepte, queue carrée en transversal, cylindrique en axial.

**Glisser-déposer** : tirez une ligne du *Stock d'outils* ou des *Plaquettes* et lâchez-la sur un poste, soit
sur le schéma de la tourelle, soit sur une ligne du tableau. Le poste visé s'entoure tant que le dépôt est
possible, et le curseur refuse un outil que l'implantation du poste ne tient pas. Déposer un porte-plaquette
ne touche pas à la plaquette déjà montée, et inversement : on garnit un poste en deux gestes.
Dans l'autre sens, tirez un logement du schéma ou une ligne du tableau et lâchez-la sur une séquence du
volet *Usinage* : la séquence prend ce poste, avec la combinaison qui y est montée.
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

Choisissez une ligne : le porte-plaquette est **dessiné coté** en dessous, vu de dessus et en coupe de queue,
à la même hauteur que le dessin des plaquettes pour que les deux volets s'alignent. L'outil est couché à
l'horizontale et **sa queue est toujours un rectangle**. La plaquette est au bout gauche, son coin actif en
avant et une de ses arêtes le long de l'arête principale ; elle déborde largement de la queue. C'est sa
position en hauteur qui dit la main :

* **outil à droite** : plaquette en bas à gauche, débordant vers le bas et vers la gauche ;
* **outil à gauche** : plaquette en haut à gauche, débordant vers le haut et vers la gauche ;
* **outil neutre** : plaquette dans l'axe, sa pointe fine dardant droit devant.

La main est rappelée sous le dessin, pour qu'il n'y ait pas de doute. L'angle d'attaque `κr` est tracé au
nez, entre le sens d'avance et l'arête de coupe elle-même. La cote de longueur se place du côté opposé à la
plaquette, là où il reste de la place.

Les valeurs sont portées sur les éléments : `l1` la longueur hors tout, `h × b` la queue carrée ou `d` son
diamètre, `κr` l'angle d'attaque sur son arc, et pour une barre l'alésage minimal où elle passe, tracé en
cercle pointillé. La cote `f`, du flanc de la queue à la pointe, dépend du modèle : elle n'est pas donnée
tant qu'elle n'est pas relevée.

### Plaquettes

Les plaquettes **ISO 1832** qui garnissent ces porte-plaquettes, rangées en quatre familles : négatives
(ébauche, dépouille 0°, deux faces utilisables), positives (finition, dépouille 5 à 11°), filetage, gorge et
tronçonnage. Même principe que le stock d'outils : filtre, cases « en stock », icône de la forme.
Les colonnes donnent la dépouille, la longueur d'arête, l'épaisseur et le rayon de bec.

Choisissez une ligne : la plaquette est **dessinée cotée** en dessous, de face avec son contour, ses becs
arrondis et son cercle inscrit, de profil avec son épaisseur et son angle de dépouille. Chaque élément porte
sa valeur, celle de la plaquette choisie : `l 12,9` sur l'arête, `IC 12,7` dans le cercle inscrit, `r 0,8`
au bec entouré, `s 4,76` sur l'épaisseur, `α 0°` sur l'angle de dépouille. Le bec repéré est **le coin qui
travaille**, le plus aigu : sur un losange, c'est l'un des deux coins aigus, jamais un obtus. Une plaquette ronde est cotée par
son diamètre, une barrette de gorge par sa largeur de coupe. La lecture d'un code ISO 1832 est détaillée en
tête de `ctgraph/plaquettes.py`.

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
  forets.py                forets et forets à centrer : la forme du trou qu'ils laissent
  usinage/profil.py        le profil tourné tiré des contours fermés : rayon, tranches usinables
  usinage/sequences.py     la gamme et ses séquences : type, poste, conditions de coupe, passes
  usinage/trajectoires.py  les chemins d'outil, recalculés depuis le profil et le montage
  usinage/matiere.py       la matière restante après chaque étape, et ce que chacune a enlevé
  ui/vue_esquisse.py       QGraphicsView : tracé, aimantation, sélection, élagage, dessin des cotes et des symboles
  ui/zone_atelier.py       les volets repliables ancrés à droite
  ui/volet_lateral.py      volet repliable latéralement : bandeau vertical cliquable
  ui/zone_usinage.py       volet « Usinage » : la gamme, ses réglages, le résumé des passes
  ui/zone_tourelle.py      tourelle vue de face, postes garnis, corrections ; cible du glisser-déposer
  ui/transfert.py          glisser-déposer : outil ou plaquette vers un poste, poste vers une séquence
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
