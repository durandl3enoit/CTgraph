# CTgraph

Logiciel de FAO pour un tour **Cazeneuve CT200** à commande numérique **NUM 750 T** (deux axes, X et Z).
Il va du dessin de la pièce jusqu'à l'envoi du programme ISO à la machine.

Nom antérieur du projet, à ne plus utiliser : TourGraphe.

## Périmètre

1. Bibliothèque d'outils : plaquettes, porte-plaquettes, porte-outils, tourelle.
2. Dessin des pièces par esquisse paramétrique ; import STEP dans un second temps.
3. Représentation 3D de l'ensemble mandrin, brut, outil sur la tourelle.
4. Création des séquences d'usinage.
5. Génération du G-code par un post-processeur NUM 750 T.
6. Transmission du code à la machine par liaison série RS232.

Briques jugées nécessaires en plus, à confirmer avec l'utilisateur avant de les développer :
définition de la machine (courses, broche, mandrin, contre-pointe), brut et prise de pièce,
matières et conditions de coupe, jauges et correcteurs avec fiche de réglage,
vérification par relecture du G-code généré, réception des programmes depuis la machine.

## Décisions prises

- **La pièce est un profil 2D.** Un demi-profil dans le plan XZ, fait de lignes et d'arcs exacts
  (centre et rayon, jamais de segments approximés). Un profil extérieur, un profil intérieur optionnel.
- **Dessin interne d'abord**, par un vrai module d'esquisse à la souris.
- **Esquisse paramétrique** : relations géométriques et cotes pilotantes.
- **Solveur de contraintes : PlaneGCS** (issu de FreeCAD, LGPL 2.1 ou ultérieure, dépend d'Eigen et de Boost).
  À lier dynamiquement (DLL) pour respecter la LGPL. SolveSpace est écarté (GPL v3).
- **Import STEP plus tard**, par Open CASCADE (LGPL 2.1). L'import doit produire le même profil 2D
  que l'esquisse interne, sans rien changer au reste du logiciel.
- **Les séquences d'usinage référencent le profil résolu**, elles n'en gardent pas de copie.
  Modifier une cote recalcule les trajectoires et le G-code.
- **Le dessin de la pièce est un support, pas une contrainte** (direction donnée le 27 novembre 2026).
  Il sert de **référence géométrique** aux opérations : leurs zones et leurs trajectoires s'y aimantent,
  mais ne s'y fixent pas. Toute opération se voit en surimpression du dessin et se reprend **à la
  souris**, par assez de poignées pour que l'utilisateur garde la main : une poignée centrale qui
  déplace la zone entière — d'un contour extérieur vers un alésage, par exemple — et des poignées de
  bord pour chaque limite. Ce que l'interface ne sait pas encore attraper doit le devenir.
- **Profil extérieur et profil intérieur** (`usinage/profil.py`, `_profils`, 26 et 27 novembre 2026) :
  le contour fermé de la pièce est coupé en deux. Le **profil extérieur** part du pied de la face avant —
  l'axe pour une pièce pleine, le coin de l'alésage pour une pièce creuse — suit le dessus et s'arrête
  au pied de la face arrière. Le **profil intérieur** est la paroi de l'alésage dessiné, épaulements
  compris, **sans les faces de bout** (la face avant est au dressage, le fond plat d'un alésage borgne
  n'est pas pour la barre) ; vide pour une pièce pleine. Pièce percée de part en part : le contour **ne
  touche jamais l'axe**, c'est un anneau, `_bords_anneau` le coupe au sommet le plus haut de chacune de
  ses deux faces de bout et la chaîne de plus grand rayon moyen est l'extérieur. Pièce pleine ou à
  alésage borgne : on ouvre le contour sur l'axe, puis on le coupe au sommet de la face avant. Sans cela
  la finition descendait dans l'alésage et rabotait toute la pièce. Couper plutôt sur « ce sommet
  porte-t-il le plus grand rayon de son abscisse » casserait la chaîne à chaque épaulement : le coin bas
  d'une face d'épaulement est sous l'enveloppe et appartient pourtant au bord extérieur.
- **Pile technique (validée le 23 novembre 2026)** : Python 3.12 et PySide6, comme DXFgraph et PDFgraph.
  Solveur par le paquet PyPI `planegcs` (roue binaire Windows, LGPL 2.1+, liaison dynamique : la condition
  de la LGPL est remplie). Liaison série par `pyserial`. Distribution par PyInstaller (`build.ps1`) et
  l'installeur de DXFgraph. Vue 3D par révolution du profil dans un `QOpenGLWidget`. Import STEP plus tard
  par `cadquery-ocp` (Open CASCADE pour Python, LGPL 2.1).
- **Format de fichier** : `.ctg`, JSON lisible, décrit dans `ctgraph/esquisse/modele.py`.
- **Repère de l'esquisse** : `z` le long de l'axe, `x` le rayon. Les cotes de diamètre valent 2 × x.
  Pour PlaneGCS : x = z du modèle, y = x du modèle.
- **Tangence en un point commun** : traduite par un angle au point (0 ou π), comme FreeCAD, et non par la
  contrainte générique distance centre-droite = rayon, qui converge mal (racine double).
- **Relations automatiques du tracé** (horizontal, vertical, sur l'axe) : ajoutées, puis retirées si le
  solveur les trouve en conflit ou redondantes.
- **Sélection** : les clics s'ajoutent (un second clic retire), un clic dans le vide vide la sélection, pas de Ctrl.
  Le clic droit ouvre le menu des relations et cotes possibles pour la sélection ; pendant un tracé, il termine la chaîne.
- **Aimantation** débrayable par cases (zone Affichage) : horizontal/vertical, 45°, objets proches, axe Z.
  Accrocher sur une ligne ou un arc pose « point sur ligne » ou « point sur arc ».
- **Changement d'outil** : boutons à icônes dessinées (`ctgraph/icons.py`, couleur du thème), touches S/L/A/E,
  ou clic droit maintenu + molette avec le nom de l'outil sous le curseur, comme dans DXFgraph.
- **Geste d'élagage** : clic gauche semi-long (350 ms sans bouger) puis glisser élague quel que soit l'outil ;
  l'outil d'avant revient au relâchement.
- **Symboles des relations** : horizontal = « -z- », vertical = x coupant une barre verticale ; dessinés dans
  `Etiquette`, pas des lettres H et V.
- **Diamètre et rayon ensemble** : une cote de diamètre porte deux étiquettes, « Ø 50 » et « R 25 » ; le double-clic
  sur l'une ou l'autre édite la grandeur correspondante (le modèle ne stocke que le diamètre).
- **Icônes sobres** : un trait, une idée par icône, pas de points ni de pointillés. Les boutons de relations
  portent une petite icône (`icone_relation`), les mêmes symboles que dans l'esquisse pour horizontal et vertical.
  Le menu contextuel et les menus ont des icônes (`icone_action` pour supprimer, désélectionner, tout voir, pilotée).
  Dans le menu contextuel, les relations possibles sont une rangée d'icônes seules (`QWidgetAction`), nom en infobulle.
  Le menu propose Arrondi et Chanfrein quand la sélection est un coin (point entre deux lignes) ou deux lignes
  concourantes (`coin_depuis_selection`).
- **Zone Relations repliable** (`ZoneRepliable`), repliée par défaut, état mémorisé.
- **Curseur par outil** (`curseur_outil`) : croix au point chaud et symbole de l'outil en bas à droite ; la sélection
  garde la flèche. L'outil Cote déplace aussi les cotes posées et les édite au double-clic.
- **Cycle d'outils à la molette** : bande d'icônes (`BulleOutils`) tournée pour garder l'outil actif au centre.
  Si le bouton droit a été enfoncé sur l'étiquette d'une cote, la molette règle la cote (1 par cran, 0,1 avec Maj,
  rayon sur le « R » d'un diamètre), et le glisser aussi, **projeté sur la direction de la ligne de cote**
  (`_direction_cotes`, relevée au dessin de chaque cote ; `_vecteur_glisser` : droite ou haut = plus, rayon :
  vers l'extérieur de l'arc ; un pas par `PIXELS_PAR_PAS`) ; une seule étape d'annulation au relâchement, qui
  n'ouvre pas le menu.
- **Arrondi et chanfrein** (`ctgraph/esquisse/coins.py`) : outils sur un sommet entre deux lignes. Le sommet devient
  un **point de construction** (`Point.construction`, coin théorique, croix diagonale) tenu par « point sur ligne »
  sur les deux lignes ; il échappe au balayage des orphelins. Les cotes de longueur portées par les lignes passent
  sur (autre extrémité, coin) : changer le rayon ou le pan ne déplace que le congé ou le pan. Arrondi : arc + deux
  tangences + cote rayon. Chanfrein : pan + distance (coin, point du pan) + angle du pan (lecture « 1 × 45° »).
- **Origine de la pièce** : Z = 0 sur l'axe, la face avant finie par convention ; le mandrin se placera par rapport à
  elle. Relation `ORIGINE_Z` (z = 0, posée d'office quand le tracé s'accroche à la verticale Z = 0) et cote
  `POSITION_Z` (coordonnée z signée d'un point ou d'une face, affichée « Z -30 »). « Fixe » ne fige que ce que
  « sur l'axe » et « origine Z » ne tiennent pas déjà.
- **Modifier une cote ne déplace pas le dessin** : après la résolution, `AdaptateurSolveur._compenser_derive`
  annule la translation d'ensemble (déplacement médian des points étrangers à la cote) que PlaneGCS choisit
  arbitrairement quand l'esquisse n'est pas ancrée, puis résout à nouveau ; une référence absolue reprend le dessus.
- **Pose d'une cote** : ajoutée d'abord à la mesure, puis diagnostic ; si elle sur-contraint elle devient pilotée sans
  demander de valeur ; sinon la valeur est demandée et appliquée par `modifier_cote` (abandon = pas de cote).
- **Égal entre deux cotes** (`EGAL`, forme (cote, cote), même type, la seconde suit la première) : la suiveuse garde
  une contrainte pilotante mais un paramètre libre égalé à celui de la maîtresse (`s.equal`) ; les cotes sont
  traduites avant les relations. Elle ne se règle pas (`cote_maitresse`), sa valeur est relue après résolution.
- **Cote sur-contrainte = cote pilotée** : une cote posée qui entre en conflit, est redondante ou n'est pas atteignable passe
  automatiquement en cote pilotée (`Cote.pilotee`, paramètre libre et `driving=False` pour PlaneGCS), grisée et
  entre parenthèses ; le solveur y écrit la mesure après chaque résolution. Elle redevient pilotante à la demande
  si cela ne sur-contraint pas.
- **Vue 3D** (`ctgraph/ui/vue_3d.py`) : QOpenGLWidget incrusté en haut à droite de l'esquisse, nuanceurs GLSL 1.20,
  sans PyOpenGL. Révolution des contours fermés à 96 facettes, normales exactes de la surface de révolution
  lissées le long du profil sous un angle de pli de 30° (arcs lisses, épaulements nets), éclairage deux faces.
  Le sens de parcours des triangles est accordé à la normale ; les maillages du montage, construits avec des
  profils parcourus dans le sens horaire (normales sortantes), sont rendus avec élimination des faces arrière,
  si bien que l'on voit au travers du mandrin quand la caméra y entre. Le brut est translucide.
  Repère : Z pièce = X monde. `CTGRAPH_SANS_3D=1` la désactive (tests hors écran). Boutons de vues typiques
  dans le cadre (`angles_de_vue`) : de côté (lacet 0, tangage 0), de face (lacet −90), de biais réglable
  (mémorisé dans les préférences `vue3d.biais`). Recadrage (`distance_de_cadrage`) : la sphère englobante de
  la pièce tient dans l'ouverture de 32°, quelle que soit l'orientation. L'outil sur la tourelle viendra s'y ajouter.
- **Contours fermés remplis** d'une teinte discrète (`VueEsquisse.contours_fermes`) : chaînes dont chaque sommet
  relie exactement deux éléments, refermées sur elles-mêmes ou dont les deux bouts touchent l'axe (fermeture par
  l'axe de révolution). Deux points liés par « coïncident » comptent pour un seul sommet (union-find).
  Les boucles à sommets de degré ≥ 3 attendent un vrai parcours de faces.
- **Les cotes sont un seul outil** (`Cote`, touche C), pas cinq boutons : le type se déduit des éléments cliqués et de
  l'endroit où la cote est posée (`VueEsquisse.deduire_cote`). Point → diamètre ; arc → rayon ; ligne → longueur Z
  si posée au-dessus ou au-dessous, sinon diamètre (horizontale), angle (inclinée) ou distance (verticale) ;
  ligne inclinée (et deux points) : à côté, entre les extrémités (boîte élargie de 12 px) → distance (longueur
  vraie, parallèle, comme la cote alignée des CAO) ; au-dessus ou au-dessous → longueur Z ; à droite ou à gauche
  → **longueur X** (`TypeCote.LONGUEUR_X`, écart radial, `difference` sur les paramètres x) ; en diagonale au-delà
  d'un coin → angle ;
  deux lignes → angle, longueur Z entre deux verticales, ou écart (`TypeCote.ECART`, distance point-droite
  PlaneGCS) entre deux parallèles ; deux points → longueur Z (distance si même z).
- **Élaguer** : un trait tiré au travers des objets, un seul comportement : la portion retirée va jusqu'aux croisements
  voisins (`elagage.elaguer` garde ses autres modes en réserve, l'interface ne les expose plus).
  Les points de coupe reçoivent « point sur » l'objet croisé ; une ligne scindée garde horizontal/vertical/parallèle/
  perpendiculaire sur ses deux morceaux, un arc scindé garde son centre et reçoit « égal » entre ses morceaux ;
  les cotes de longueur disparaissent.

- **Machine et montage** (`ctgraph/montage.py`, validé par l'utilisateur le 24 novembre 2026) : CT200 avec mandrin à mors
  **SMW-Autoblok 210 BH-FC** (référence gravée « 210 BH-FC », passage de barre **42 mm** : constante
  `PASSAGE_MANDRIN`, affichée, ni réglable ni enregistrée), mors **SMW-Autoblok 474** (référence gravée
  « 12082030 (1/16"x90°) »), contre-pointe possible, brut rond plein par défaut, tube possible. Les références
  gravées sont inscrites discrètement sur le dessin (`Inscription`, sans cadre ni interaction).
  Repère pièce : Z = 0 face avant finie, Z négatif vers le mandrin ; prise décrite par dépassement (face des mors →
  face finie), surépaisseur de face, serrage extérieur ou intérieur (tube), mors retournés ou non, et **appui**
  de l'arrière du brut : face du mandrin (0), épaulement derrière l'étage k, ou aucun (−1 : prise libre
  `prise_libre`, réglable par la cote « prise » de l'esquisse, qui serre alors l'étage le plus profond atteint) ;
  la longueur engagée en découle.
  **Mors durs étagés réversibles** (`Mandrin.etages`, depuis le bout : longueur + épaulement derrière ; le mors est le
  plus épais au fond, `epaisseur_mors`). La face étagée serre quand (mors normaux ∧ extérieur) ou (retournés ∧
  intérieur) ; sinon c'est la face plate, et l'appui ne peut être que le mandrin. `Montage.blocs_mors` (un bloc par
  étage, placé pour que la face qui serre touche le brut) sert à la 3D, `profil_mors` au dessin 2D. Les réglages
  se font sur le mors dessiné (genre « mors ») : double-clic = retourner, clic droit = serrage et appui ; quand
  un appui devient impossible, `_ajuster_appui` prend le premier réalisable. Les dimensions sont à vérifier.
  **Cotes du mors éditées en place** : clic droit sur la référence gravée (genre « reference_mors ») →
  `commencer_edition_mors` ; `VueEsquisse.mode_mors` dessine les cotes du mors (genre « cote_mors », clés
  `Montage.cles_mors()` : `mors.epaisseur`, `mors.etage{i}.longueur|epaulement`, textes « E 40 », « L1 20 »,
  « h1 8 »), grise tout le reste (opacité 0,28) et le rend inerte ; bandeau Valider / Annuler, Entrée / Échap ;
  annuler rend le montage d'avant. Les valeurs éditables du montage passent toutes par `Montage.valeur`,
  `definir_valeur`, `texte`, `libelle` (brut et mors), appliquées en direct par `definir_montage`.
- **Références du montage** (`Montage.references()` → `modele.Reference(nom, axe "z"|"x", valeur, libellé,
  court)`) : face de référence (Z = 0, en retrait de la marge par rapport au bout du brut ; demandée par
  l'utilisateur, pas le bout du brut), face des mors, épaulement d'appui, face du mandrin, surface du brut,
  alésage d'un tube.
  Le contrôleur les pose dans `Esquisse.references` (non enregistrées, relues du montage à chaque changement,
  puis reconstruction et résolution). Relation `SUR_REFERENCE` (point ou ligne, champ `Relation.reference`) :
  coordonnée figée à la valeur du plan ; cote `DEPUIS_REFERENCE` (`Cote.reference`) : écart signé depuis le
  plan (`difference` avec un paramètre fixe), texte « court valeur ». Menu contextuel d'un point ou d'une face :
  « Aligner sur une référence », « Coter depuis une référence ». Aimantation « axe Z » étendue aux plans
  (`Accroche.reference` → relation posée d'office). Dessin en trait mixte nommé (genre « reference »).
- **Cotes d'angle par secteur, à la façon de SolidWorks** : la valeur d'une cote d'angle est l'angle, dans
  [0, 180], du secteur désigné par l'étiquette (`Cote.secteur`, choisi par `Esquisse.secteur_angle` à la pose et
  à chaque déplacement d'étiquette, enregistré). Ligne seule : bit 0 = bout (p1/p2), bit 1 = axe Z vers + ou − ;
  deux lignes : 0 entre les segments (au croisement des droites, `ancre_angle`), 1 et 3 suppléments, 2 opposé.
  `rayons_angle` donne centre et rayons bordants ; le solveur contraint toujours l'angle orienté
  (`_param_angle` fait la conversion d'après la géométrie courante) et une cote pilotée relit l'angle du
  secteur. Dessin : arc centré, flèches tangentes, rayons de rappel. Limite connue : « égal » entre deux cotes
  d'angle égalise les angles orientés, pas les secteurs.
- **Survol** : sans bouton enfoncé, l'élément que le clic prendrait (`GENRES_SURVOL`) luit en magenta
  (`c["lueur"]`, distinct de l'orange de sélection) : stylo épaissi, point grossi, étiquette recolorée, aspect
  rendu au départ du curseur (`_survoler`). Un élément sélectionné garde sa couleur de sélection.
  Le fichier `.ctg` est désormais une **pièce** (`Piece` : esquisse + montage, format `ctgraph-piece`) ; l'ancien
  format esquisse seule se lit encore. Le dernier montage réglé est le défaut des nouvelles pièces (préférences).
  Courses et broche de la machine : valeurs provisoires, à relever. Cinq **cotes du brut** sont toujours affichées
  dans l'esquisse (étiquettes de genre « brut », non sélectionnables, éditables au double-clic et à la molette) :
  Ø brut, L brut, **dépassement brut** (face des mors → face finie, juste sous L brut, demandé le 27 novembre
  2026), marge en bout, prise ; changer la longueur ajuste le dépassement (prise et marge fixes), changer le
  dépassement fait suivre la longueur.
- **Pas de réglage** (27 novembre 2026) : les diamètres de forets vont par entiers et demi-millimètres — la
  souris sur la paroi et la molette dans le champ (`BoiteDemi`, dont `stepBy` rejoint d'abord le demi
  voisin) s'y calent ; seule la saisie au clavier reste libre. La profondeur de passe va par 0,1 mm à la
  molette.

- **Stock d'outils** (`ctgraph/outils.py`, `ui/zone_outils.py`, demandé le 24 novembre 2026) : catalogue des
  porte-plaquettes montables sur les porte-outils **VDI 30** (DIN 69880) du CT200, borne `QUEUE_MAXI` = 20 mm
  (queue carrée 16 × 16 ou 20 × 20, queue cylindrique Ø 10 à Ø 20). Cinq familles (`FAMILLES`) : extérieur
  négatif, extérieur positif, alésage, filetage, gorge et tronçonnage. Désignations **ISO 5608** (queue carrée)
  et **ISO 6261** (barres) ; filetage, gorge et tronçonnage portent une référence du commerce, marquée « hors
  ISO ». Les gabarits portent « _ » à la place de la lettre de main, `_ajouter` crée une ligne par main. La clé
  de lecture des codes est en tête du module : à garder à jour si des références s'ajoutent.
  La **forme de la plaquette** est déduite de sa désignation (`forme_plaquette`, clés `FORMES_PLAQUETTE` :
  lettre ISO C/D/V/W/T/S/R, ou filetage / gorge / lame) et dessinée par `icons.icone_plaquette`, devant la
  désignation de la plaquette. Les icônes sont construites une fois par zone, pas par ligne : le filtre
  reconstruit la liste à chaque frappe.
  Le catalogue dit ce qui est montable, les coches « en stock » disent ce que l'atelier possède
  (préférence `outils.stock`).
- **Atelier : des volets repliables latéralement** (`ui/zone_atelier.py`, demandé le 24 novembre 2026), un
  seul `QDockWidget` sans barre de titre ancré à droite (visibilité `atelier.visible`, touche `O`), contenant
  de gauche à droite **Usinage**, **Tourelle**, **Stock d'outils**, **Plaquettes**. Chacun est un `VoletLateral`
  (`ui/volet_lateral.py`) : bandeau vertical cliquable de `LARGEUR_BANDEAU`, **présenté pareil pour tous**
  (titre en haut lu de haut en bas, chevron **vers la gauche quand c'est replié, vers la droite quand c'est
  déployé** : il montre le sens où le contenu va aller ; sens inversé le 25 novembre 2026 à la demande de
  l'utilisateur) ; replié, le volet est borné à la largeur du bandeau. Bandeau du côté extérieur (à gauche
  pour les premiers, à droite pour le dernier). Un ressort en fin de rangée garde les bandeaux collés
  quand tous les volets sont repliés.
  État mémorisé dans `volet.<clé>`, déplié par défaut pour le seul stock d'outils ; le menu Affichage a une
  entrée par volet. Les tests d'interface masquent l'atelier : il rétrécit la vue d'esquisse et fausserait
  les clics simulés.
- **Tourelle** (`ctgraph/tourelle.py`, `ui/zone_tourelle.py`) : douze postes **VDI 30** (DIN 69880), queue
  Ø 30 mm fixée par la norme (c'est elle qui borne `outils.QUEUE_MAXI` à 20 mm). Poste 1 en haut,
  numérotation horaire vue de face ; clic sur un logement ou sur sa ligne pour le mettre en travail.
  **Un poste s'écrit « T1 », « T12 »** (`tourelle.nom_poste`, `Poste.nom`), comme sur la commande numérique :
  partout, sur le disque, dans le tableau, dans le formulaire, dans la gamme et dans le glisser-déposer.
  Un seul endroit décide de cette écriture (décidé le 25 novembre 2026).
  Le **tableau montre tous les postes d'un bloc** (`_ajuster_hauteur` fixe sa hauteur au nombre de lignes,
  défilement coupé) ; c'est le volet entier qui défile, `ZoneTourelle` étant un `QScrollArea`, pour que le
  disque garde une taille lisible dans une fenêtre courte au lieu d'être écrasé (demandé le 26 novembre 2026).
  **Implantation** (`IMPLANTATIONS`, relevé le 24 novembre 2026) : un porte-outil VDI se monte sur la
  circonférence de la tourelle ou sur sa face. Sur le CT200, la moitié des outils sont montés
  *transversalement en périphérie* (tournage extérieur, queue carrée), l'autre moitié est *axiale* (barres,
  forets, queue cylindrique) ; les postes alternent par défaut et chacun se règle à part. L'implantation
  borne les porte-plaquettes proposés (queue carrée ou cylindrique).
  Chaque `Poste` porte son porte-plaquette, sa plaquette et son `Correcteur` (numéro sur la CN, corrections
  X et Z, rayon de bec repris de la plaquette, code d'orientation). La garniture appartient à la machine,
  pas à la pièce : elle est mémorisée dans la préférence `tourelle` (JSON), pas dans le fichier `.ctg`.
  Diamètre du disque et rayon d'implantation à relever sur le CT200 ; **la convention des codes
  d'orientation et le comptage de la correction X sont à vérifier dans le manuel NUM 750 T**, rien n'est
  écrit de mémoire.
- **Glisser-déposer entre volets** (`ui/transfert.py`) : les listes du stock d'outils et des plaquettes sont
  des `ArbreGlissable` qui emportent la désignation dans un format propre (`MIME_PORTE_PLAQUETTE`,
  `MIME_PLAQUETTE`) ; le schéma de la tourelle et le tableau des postes l'accueillent (`accueillir` rend le
  poste visé si `accepte_depot` le permet, sinon l'événement est ignoré et le curseur refuse). Déposer un
  porte-plaquette ne touche pas à la plaquette déjà montée, et inversement. Le poste survolé s'entoure.
  **Deuxième chemin, en sens inverse** (demandé le 25 novembre 2026) : la tourelle est aussi une source.
  Tirer un logement du schéma (`commencer_glisser_poste`, au-delà de `startDragDistance`) ou une ligne du
  tableau emporte `MIME_POSTE`, dont la charge est « numéro, puis combinaison montée » (`charger_poste`,
  relue par `zone_usinage._numero_poste`) ; la liste de la gamme l'accueille et donne ce poste à la séquence
  visée. `ZoneTourelle.definir_tourelle` émet `tourelle_changee` : ce qui se réfère à la tourelle, la gamme
  comprise, suit le changement d'objet.
  **Troisième chemin, interne à la gamme** (demandé le 26 novembre 2026) : une ligne de la liste des
  séquences se tire sur une autre pour changer l'ordre d'usinage (`MIME_SEQUENCE`, `Gamme.deplacer_a` au
  rang compté avant le retrait). Le trait d'insertion est dessiné par `ListeSequences.paintEvent` : la
  gestion du dépôt étant la nôtre, Qt ne peut pas poser son propre indicateur.
- **Plaquettes** (`ctgraph/plaquettes.py`, `ui/zone_plaquettes.py`) : catalogue **ISO 1832** des tailles qui
  garnissent les porte-plaquettes, quatre familles (négatives, positives, filetage, gorge). `Plaquette.base`
  (« CNMG 1204 ») relie la plaquette au champ `plaquette` du catalogue des outils ; `pour_base` accepte la
  notation « CNMG 1204.. » et « 16ER / 16EL ». `FORMES_PLAQUETTE`, `forme_plaquette` et `sommets_forme` vivent
  ici : `outils.py` les réexporte et `icons.icone_plaquette` dessine les contours à partir de `sommets_forme`
  (losanges à grande diagonale au diamètre, pour qu'ils se comparent). Le volet dessine la plaquette choisie
  cotée, de face et de profil. **Chaque élément porte sa valeur** (`DessinPlaquette.cotes_portees` :
  « l 12,9 », « IC 12,7 », « r 0,8 », « s 4,76 », « α 0° ») ; la ligne sous le dessin ne dit que ce que les
  cotes ne disent pas (négative ou positive, type, pas). De même pour les porte-plaquettes
  (`DessinPorteOutil`, `PortePlaquette.cotes`) : vue de dessus avec la queue, la plaquette et l'arc
  d'attaque, coupe de queue, valeurs portées « l1 125 », « h × b 20 × 20 » ou « d Ø 16 », « κr 95° », et
  l'alésage minimal d'une barre en cercle pointillé. La cote `f` (flanc de queue à la pointe) dépend du
  modèle : à relever, pas inventée. Nombres à la française (`nombre`, virgule décimale).
  Les deux dessins ont la même hauteur (`volet_lateral.HAUTEUR_DESSIN`) : les volets s'alignent.
  **Le bec coté est le coin qui travaille** : `plaquettes.coin_actif` rend le sommet d'angle le plus aigu
  (le plus à gauche à égalité), jamais un coin obtus de losange. Le dessin du porte-plaquette s'en sert
  aussi pour asseoir la plaquette : coin actif en avant, une arête le long de l'arête principale, le corps
  tourné vers la queue. **Convention de dessin fixée par l'utilisateur le 25 novembre 2026** : l'outil est
  couché à l'horizontale, **la queue est toujours un rectangle** (jamais une enveloppe épousant la
  plaquette), la plaquette est au bout gauche dans les deux cas et déborde largement ; c'est sa hauteur qui
  donne la main, **en bas pour un outil à droite, en haut pour un outil à gauche**. Ne pas inverser : la
  main est écrite sous le dessin pour qu'une erreur se voie. Sur un **outil neutre**, c'est la bissectrice
  du coin actif qui pointe droit devant : la pointe fine darde vers l'extérieur, symétriquement. L'arc de
  `κr` se calcule du sens d'avance jusqu'à l'arête **réellement tracée**, par le plus court chemin : il se
  pose ainsi toujours du bon côté. La cote de longueur va à l'opposé de la plaquette.

- **Séquences d'usinage** (`ctgraph/usinage/`, `ui/zone_usinage.py`, demandé le 25 novembre 2026) : la pièce
  porte une **gamme** (`Gamme`), suite ordonnée de `Sequence`, enregistrée dans le `.ctg` (`Piece.gamme`).
  Une séquence dit son type, son poste de tourelle, ses conditions de coupe (`G96` vitesse de coupe, `G92`
  limitation de broche, `G95` avance par tour), ses passes et son étendue en Z ; `active` la met de côté sans
  la perdre. **Neuf types**, dans l'ordre d'usinage habituel : `DRESSAGE`, `CENTRAGE`, `PERCAGE`,
  `EBAUCHE` paraxiale, `ALESAGE`, `FINITION` de profil, `GORGE`, `FILETAGE`, `TRONCONNAGE`.
  Le centrage est un perçage court (même trajectoire, sans débourrage) ; l'**alésage** reprend le trou
  percé au diamètre voulu, décrit par ses cotes (Ø de départ, Ø à aléser, fond) et non lu dans un profil
  intérieur, qui n'existe pas encore — même parti pris que pour la gorge.
  Chaque type n'a pas les mêmes réglages : `CHAMPS_SEQUENCE` dit lesquels comptent et le formulaire ne montre
  que ceux-là, `LIBELLES_CHAMPS` les nomme pour ce qu'ils y sont (« Fond du trou » plutôt que « Z de fin »),
  `DEFAUTS_SEQUENCE` donne à chaque type ses conditions habituelles à
  l'ajout. Le **filetage**, le **perçage** et le **centrage** tournent à broche fixe (`G97`,
  `Sequence.vitesse_fixe`) : pas de
  limitation de broche à régler, et l'avance d'un filetage est son pas. La profondeur d'un filet vaut
  `PROFONDEUR_FILET` × pas (0,6134, profil ISO métrique extérieur) tant qu'elle n'est pas saisie.
  Gorge et tronçonnage plongent par `_plongee` (passes de `profondeur_passe` avec débourrage) ; une gorge
  plus large que l'outil se fait en plusieurs plongées qui se recouvrent d'un cinquième. Le filetage
  descend à `hauteur × √(i/n)` : section de copeau constante. Le perçage ressort complètement entre deux
  descentes. Le rayon de départ d'une plongée vient de `_matiere_sur` : le profil dans la pièce, le brut
  au-delà de ses bouts, ce qui fait qu'un tronçonnage au fond de la pièce attaque bien au diamètre du brut.
  **Le module ne connaît ni Qt ni PlaneGCS** : il reçoit le profil résolu et le montage, et rend des
  trajectoires. `ProfilTourne` (`usinage/profil.py`) est le profil extérieur, tiré du plus grand contour fermé
  ouvert sur l'axe (`profil_exterieur`), parcouru du bout de la pièce vers le mandrin (z décroissant) ;
  `rayon(z)`, `z_matiere(rayon)`, `intervalles_sous(rayon, …)` (les tranches où une passe paraxiale a le droit
  de couper : un épaulement plus gros devant interdit de partir du bout), `rayon_mini` (jusqu'où l'ébauche
  descend) et `entre(z1, z2)` (le profil rogné sur une tranche).
  `Trajectoire` est une suite de `Mouvement(z, x, travail)` : exactement ce que le post-processeur traduira en
  `G0` et `G1`. Le chemin est celui de la **pointe théorique** : la correction de rayon de bec est laissée à la
  CN (`G41`/`G42`), comme dans les programmes archivés. Une séquence ne descend jamais dans les mors
  (`_bornes` borne à `montage.z_face_mors()`), et **la finition ne redescend pas la face arrière jusqu'à
  l'axe** : la pièce y tient encore à la barre, c'est au tronçonnage de la détacher ; la face avant, elle, se
  finit depuis l'axe.
  **Rien n'est recopié du dessin** : `FenetrePrincipale.profil_usinage()` se vide à chaque résolution et à
  chaque changement de montage, `trajectoire_de` recalcule. C'est la décision de conception prise au départ.
  Volet « Usinage », le plus à gauche de l'atelier : liste ordonnée (ligne, opération, poste, passes, longueur
  de coupe), un bouton d'ajout par type, flèches d'ordre, case d'activation, formulaire de la séquence choisie
  avec rappel de ce que porte son poste de tourelle. On affecte un poste en tapant son numéro ou en **glissant
  une ligne de la tourelle sur la séquence** ; on change l'ordre par les flèches ou en **tirant une ligne sur
  une autre**. La trajectoire de la séquence choisie se dessine sur
  l'esquisse (genre « trajectoire », non sélectionnable) : trait plein en coupe, pointillé en rapide, cercle
  au départ.
- **Gamme type** (`sequences.GAMME_TYPE`, `Gamme.remplir_type`, demandée le 26 novembre 2026) : le bouton
  « Proposer la gamme type » pose les neuf étapes de l'enchaînement habituel d'une pièce sur barre, dans
  l'ordre, du plus rigide au moins rigide (deux lignes d'alésage, ébauche et finition : dix lignes pour
  neuf étapes). Les opérations qui demandent une cote que le dessin ne donne pas (centrage, perçage,
  alésage, gorge, filetage) sont posées **décochées** : l'ordre est là, il reste à dire si la pièce en a
  besoin. Mais chacune part de réglages qui **donnent un résultat visible** (`DEFAUTS_SEQUENCE` et les
  réglages propres à `GAMME_TYPE`) : on coche, on voit, on ajuste. Une opération qui ne montrerait rien
  tant qu'on ne l'a pas renseignée est indiscernable d'une opération cassée — c'est ce qui s'est produit
  le 26 novembre 2026 avec le perçage, l'alésage et le filetage.
  Le poste est pris de la tourelle courante, par famille d'outil (`FAMILLES_OUTIL`, rapproché du
  champ `famille` du catalogue `outils`) ; rien n'est inventé si la tourelle ne porte pas l'outil voulu.
  Remplacer une gamme existante demande confirmation.
- **Matière enlevée, étape par étape** (`usinage/matiere.py`, demandé le 26 novembre 2026) : **la liste
  est le curseur d'étape**. Sa première ligne est le brut (étape 0, `ROLE_ID` 0, ni cochable ni
  déplaçable), chaque ligne suivante est une opération ; choisir une ligne montre la pièce après elle, et
  les lignes qui suivent se grisent (`_marquer_etape`). Il n'y a donc **qu'une seule notion d'étape
  courante**, la ligne choisie : un curseur séparé a existé une demi-journée, l'utilisateur l'a fait
  fondre dans la liste le 26 novembre 2026.
  Le curseur se **voit** quand même : `CurseurEtape` longe la liste à sa droite, un trait avec un cran par
  étape et une poignée en face de la ligne choisie, qui se tire à la souris ou se pousse à la molette. Il
  n'a aucun état propre — il lit et écrit la ligne courante — donc il ne peut pas se désaccorder d'elle.
  **Boutons et gamme sont fixés en haut du volet** ; seul le formulaire de réglage défile, dans son propre
  `QScrollArea`. Sur la ligne du brut, le formulaire s'efface au lieu de se griser.
  **Une opération ajoutée se pose juste après l'étape montrée**, pas en fin de gamme : on la construit de
  proche en proche (demandé le 26 novembre 2026).
  `EtatMatiere` décrit la matière restante en **tranches** de `PAS_TRANCHE` (0,25 mm) le long de l'axe, chacune
  avec son rayon intérieur et son rayon extérieur ; `etats()` rend la suite des états, `enlevee_depuis` les
  copeaux d'une étape. `contours()` et `enlevee_depuis` rendent des **polygones passant par le milieu des
  tranches**, pas des rectangles : sans cela un cône de pointe de foret se dessine en escalier, ce que
  l'utilisateur a refusé le 26 novembre 2026. La vue les dessine (genre « matiere », non sélectionnable) :
  la matière restante en teinte sourde sous le profil, ce que l'étape vient d'emporter en orange **au-dessus
  du remplissage du contour**, faute de quoi un trou de foret, étant à l'intérieur de la pièce, reste invisible.
  **Chaque type enlève à sa façon** : le dressage fait avancer la face, l'ébauche et la finition rabotent
  sous leur chemin tranche par tranche, la gorge et le tronçonnage creusent sur la largeur de l'outil, le
  perçage et le centrage ouvrent le trou **à la forme du foret** (voir ci-dessous), l'alésage l'ouvre
  passe par passe, le
  filetage ne change pas la silhouette (le filet est une rainure hélicoïdale,
  l'enveloppe reste au diamètre nominal) mais pose un `Filet`, que la vue dessine en **dents de scie au
  pas**, entre la crête et le fond de filet, par-dessus tout le reste : un filet est fin, il se perdrait
  sous sa propre trajectoire. L'étendue du filet se lit sur les *segments* de coupe, pas sur leurs points :
  une passe de filetage est un seul mouvement, dont le départ porte la garde.
  Un mouvement radial d'ébauche ou de finition ne fait que longer une
  face : il n'enlève rien de plus. **Ce modèle sert à voir, pas à vérifier** : il ignore la forme de l'outil
  et ne détecte aucune collision.
- **Forets et forets à centrer** (`ctgraph/forets.py`, demandé le 26 novembre 2026) : un foret ne laisse
  pas un trou à fond plat, et un foret à centrer en laisse un **à deux étages**. Chaque `Foret` se décrit
  par `rayon_a(t)`, le rayon du trou à la distance `t` **en arrière de la pointe** : c'est tout ce dont le
  modèle de matière a besoin, et c'est ce qui rend le dessin fidèle. Foret hélicoïdal : un cône de pointe
  (`ANGLE_POINTE` = 135°, l'affûtage de l'atelier). Foret à centrer forme A (DIN 333) : pointe à 118°,
  bout guide cylindrique au petit Ø, puis cône à 60° jusqu'au corps. **Le Z de fin est celui de la pointe**,
  pas du plein diamètre : un centrage trop court ne fait que son avant-trou, et le dessin le montre.
  Le foret se choisit dans un champ de l'opération (`Sequence.foret`, désignation au catalogue) ; régler le
  Ø à la main détache le foret choisi et retombe sur un foret ordinaire de ce Ø. Dimensions et angles **à
  vérifier sur les forets de l'atelier**, comme les autres catalogues.
- **Cotes d'usinage sur le dessin** (demandé le 26 novembre 2026) : la séquence montrée pose ses valeurs
  réglables sur l'esquisse, comme le brut pose les siennes. Genre « cote_sequence », non sélectionnable,
  même maniement que les cotes du brut : double-clic pour saisir, clic droit + molette ou glisser pour
  régler (`Sequence.cotes_dessinees`, `valeur_cote`, `definir_valeur_cote`, `texte_cote` ;
  `FenetrePrincipale.editer_valeur_sequence` et `ajuster_valeur_sequence`).
  Les quatre opérations en profondeur la portent (`LIBELLES_PROFONDEUR`) : centrage, perçage et alésage
  en « P », filetage en « L » (c'est une longueur de filet). **La référence est la surface travaillée**,
  relevée sur la matière de l'étape (`EtatMatiere.z_entree`, `FenetrePrincipale.surface_travaillee`) :
  après un dressage on perce depuis la face dressée, pas depuis le bout du brut. La *trajectoire*, elle,
  approche toujours du bout du brut (`Sequence.z_face`) : partir de plus loin n'est jamais faux, et la
  matière n'est enlevée que là où il y en a. La cote se dessine **sous l'axe**, plus bas que celles du
  brut : sur un centrage, l'étiquette cacherait le trou qu'elle mesure.
- **Un outil enlève ce qui reste après l'opération d'avant** (rappelé par l'utilisateur le 26 novembre
  2026, et c'est la règle). `trajectoire(sequence, profil, montage, etat, paroi)` reçoit donc
  l'`EtatMatiere` que la séquence trouve en arrivant, et `matiere.etats()` le lui passe
  (`calcul_trajectoire(sequence, etat)`). L'ébauche part du diamètre qui reste, l'alésage du trou déjà
  percé (son Ø de départ n'est plus déclaré), le dressage de la face présente, et surtout **aucune
  approche rapide ne traverse la matière** : on contourne par devant la face encore là
  (`_face_matiere`, `_dehors`, `_dedans`). Sans état, on retombe sur le brut : l'ancien comportement,
  prudent.
  **Et les passes se limitent à la matière qui reste** : `EtatMatiere.intervalles_au_dessus` et
  `intervalles_sous_la_paroi` découpent chaque passe là où il y a vraiment quelque chose à couper, de
  sorte qu'une ébauche ne brasse plus l'air au-dessus d'un diamètre déjà fait. Les formes n'étant pas
  toujours rectangulaires, c'est l'état tranche par tranche qui tranche, pas une hypothèse de cylindre.
- **Surépaisseur avant et après un épaulement** (demandée le 26 novembre 2026) : une passe d'ébauche dont
  le bout est fermé par la montée du profil s'arrête d'une surépaisseur avant lui, et repart d'une
  surépaisseur après. Sans cela la finition trouvait la face d'épaulement déjà à cote, sans rien à
  enlever. Les bouts fermés par l'étendue demandée (`z_debut`, `z_fin`), eux, ne reculent pas.
- **Intérieur et extérieur se distinguent** : `FINITION` est la finition **extérieure**, `ALESAGE`
  l'ébauche d'alésage, `FINITION_INTERIEURE` la finition d'alésage — un seul passage le long de la
  paroi, comme la finition extérieure suit le profil. `NOMS_COURTS` donne le nom des boutons et des
  libellés automatiques : « Finition ext. », « Finition int. », parce que « Finition » seul ne
  distinguerait plus rien.
- **Toutes les zones d'usinage ont leurs poignées** (demandé le 27 novembre 2026).
  `FenetrePrincipale.zone_usinee` rend la zone qu'une opération attaque — (z droite, z gauche, rayon bas,
  rayon haut) — **pour les dix opérations**, celles qui balaient le profil comprises : l'ébauche est
  bornée par son étendue et par la surépaisseur qu'elle laisse, le dressage par la face qu'il laisse.
  `poignees_actives` dit quelles prises la zone porte, `deplacer_poignee` ce que chacune règle — et c'est
  **par opération** : le fond d'une gorge est sa largeur, celui d'un dressage la surépaisseur de face, la
  paroi d'une ébauche la surépaisseur au rayon, celle d'un perçage le Ø du foret, celle d'un filetage sa
  profondeur. Une prise qui ne réglerait rien n'est pas dessinée.
  La **poignée centrale** (genre « poignee_usinage », `deplacer_zone`) déplace l'opération le long de
  l'axe, et **le rayon où on la lâche dit de quel côté on travaille** : dans le trou elle devient
  intérieure (`Sequence.interieur`), sur le profil extérieure. C'est le geste qui fait passer un filetage
  ou une gorge de l'extérieur à l'alésage.
- **Une barre d'alésage bore ce qu'elle peut atteindre** (27 novembre 2026) : elle part du trou **par
  lequel elle entre** (`_entree_trou`, la première tranche de matière sous la face), et non du plus
  petit rayon de la tranche, qui serait le sommet du cône du foret — on la voyait faire neuf passes au
  fond d'un cône où elle ne passe pas. Une passe ne court que là où elle a **au plus sa profondeur à
  prendre** (`intervalles_sous_la_paroi(…, prise_maxi=)`) : le cône du foret, un trou bien plus étroit,
  l'arrêtent — mais une bande étroite trop profonde prise entre deux tranches abordables se dresse en
  passant, c'est la surépaisseur laissée sur la face d'un épaulement. Le diamètre alésé n'a pas d'autre
  plancher que ce trou d'entrée : un alésage Ø 6 est permis.
- **L'alésage se fait au plan, épaulements compris** (demandé le 27 novembre 2026 : « gère aussi bien les
  alésages avec épaulement que les chariotages extérieurs avec épaulement »). `diametre_fond` à 0 —
  texte « suivre le dessin », le défaut — fait suivre à `ALESAGE` et `FINITION_INTERIEURE` le **profil
  intérieur** de la pièce (`paroi_alesage`), ramené à ce qu'une barre atteint en entrant par la face :
  un diamètre plus grand derrière un plus petit est plafonné au passage, c'est l'affaire d'une gorge
  intérieure. Le fond est celui de l'alésage dessiné quand aucun Z de fin n'est donné (`fond_alesage`,
  texte « fond de l'alésage dessiné »), et la cote « P » se lit sur lui (`Sequence.valeur_cote(…,
  z_fond)`). Les passes d'ébauche sont **plafonnées à leur rayon et épousent les marches** au-delà, se
  suivent sur une copie de la matière (`ouvrir_alesage`) pour ne pas brasser l'air dans ce qu'une passe
  plus fine a déjà ouvert, et s'arrêtent d'une surépaisseur **devant chaque épaulement**
  (`_avec_surepaisseur`) comme l'ébauche extérieure ; un alésage borgne garde aussi sa surépaisseur au
  fond. La finition est un seul passage le long de la paroi, qui dresse les faces d'épaulement. Un
  diamètre donné reprend l'ancien comportement : un cylindre, ou l'élément d'esquisse désigné, que l'on
  place à la main ; sur une pièce dessinée pleine, l'alésage au plan dit qu'il manque le trou. Libellés
  « Alésage au plan », « Finition int. au plan ».
- **Un filetage enlève de la matière** (27 novembre 2026). En toute rigueur l'enveloppe de révolution
  garde le diamètre des crêtes, le filet étant une rainure hélicoïdale ; mais le creux est bien enlevé,
  et le montrer vaut mieux que de laisser croire que rien n'a été fait. On rabote donc jusqu'au fond de
  filet. **Filetage intérieur** : `Sequence.interieur` part du trou et ouvre vers l'extérieur ; ses
  dents se dessinent pointées vers l'axe.
- **Précision du contour de matière** : `PAS_TRANCHE` vaut 0,05 mm. Les polygones passent par le milieu
  des tranches, ce qui fait d'un cône une pente franche mais penche une face verticale de la largeur
  d'une tranche — d'où la finesse. `_sans_points_inutiles` retire ensuite les sommets alignés : les
  polygones restent courts et les droites franchement droites.
- **Édition graphique de l'alésage** (demandée le 26 novembre 2026) : quand la séquence montrée est un
  alésage, sa zone rouge porte ses prises (genre « poignee_alesage », `VueEsquisse.alesage_montre`,
  `_dessiner_poignees_alesage`) : les trois arêtes — face d'entrée, fond, paroi —, les deux coins du haut,
  **le point d'entrée**, et le corps, qui fait glisser la zone entière le long de Z. On les attrape à la
  souris en mode Sélection (`_glisse_alesage`), et **l'aimantation de l'esquisse s'applique**
  (`accrocher`) : la zone s'aligne sur les points, les faces et les plans de référence de la pièce finie.
  Les poignées passent **avant tout** dans `element_sous` (ordre −1) : posées sur une ligne du dessin,
  elles doivent rester attrapables.
  `FenetrePrincipale.deplacer_alesage` applique le mouvement en gardant la zone cohérente : jamais
  retournée, jamais plus petite que le trou de départ.
  **Une zone à aléser n'est pas forcément rectangulaire** : lâcher la poignée « paroi » sur une ligne ou
  un arc de l'esquisse enregistre cet élément dans `Sequence.paroi`, et l'alésage suit alors cette forme
  (`_paroi_visee`, polyligne résolue par `FenetrePrincipale.paroi_de` via `VueEsquisse.polyligne_element`).
  Chaque passe est plafonnée au rayon de la passe et épouse la paroi au-delà : un cône, un congé. Lâchée
  sur **la paroi dessinée de l'alésage** (`ProfilTourne.porte`), la poignée ramène l'alésage au plan :
  tout le profil intérieur, épaulements compris. Lâchée ailleurs, elle en fait un cylindre au diamètre
  où on l'a posée.
- **Le nom d'une opération porte sa cote maîtresse** : « Perçage Ø 10 », « Alésage Ø 20 » (« Alésage au
  plan » sans diamètre donné), « Gorge Ø 20 × 4 », « Filetage pas 1,5 », « Tronçonnage ép. 3 »
  (`Sequence.libelle`). Deux lignes voisines se distinguent ainsi d'un coup d'œil. Un nom donné à la main
  l'emporte toujours.

## Points ouverts

- Post-processeur : cycles NUM (G64, G33…) ou trajectoires explicites en G1/G2/G3. Les programmes Go2CAM
  archivés (voir `docs/reference-go2cam-ct200.md`) montrent que l'explicite tourne sur la machine.
  Proposition : explicite d'abord, cycles en option par séquence.
- Calculs en 2D sur les profils avec affichage 3D par révolution : proposé, non confirmé.
- Ordre de réalisation : non arrêté.

## Architecture du module d'esquisse

1. **Modèle d'esquisse** : points, lignes, arcs, relations, cotes. C'est ce qui est enregistré.
2. **Adaptateur solveur** : seule partie du code qui connaît PlaneGCS.
3. **Interface** : tracé à la souris, glisser des points avec résolution en continu, édition des cotes.

Contraintes visées : coïncident, horizontal, vertical, parallèle, perpendiculaire, tangent, égal, point sur ligne.
Cotes visées : longueur selon Z, diamètre (distance à l'axe doublée), rayon d'arc, angle.

## Ce que l'on sait du NUM 750 T

Vérifié dans des sources publiques :

- Cycles de tournage : G33 (filetage à pas constant), G63 (ébauche avec gorge), G64 (ébauche paraxiale), G65 (ébauche de gorge), G66 (défonçage).
- Cycles axiaux : G81, G82, G83, G84.
- Programmation structurée et programmation paramétrée sont des options de la CN (bits 81 et 50 de la grille d'options).

Rapporté par des utilisateurs sur un forum, à vérifier sur la machine :

- Chargement depuis un PC par l'entrée « ruban » du menu chargement.
- Liaison série : 9600 bauds, 7 bits de données, parité paire, 1 bit de stop, contrôle de flux RTS/CTS.
- Mode passant (commande PPR) : demande un logiciel CN de version F3 ou supérieure.

À relever sur la machine, inconnu à ce jour : grille d'options, version du logiciel CN, taille de la mémoire programme, réglages de la ligne série.

Tant que la grille d'options n'est pas connue, le post-processeur génère de l'ISO sans variables ni structures.
La syntaxe exacte de chaque fonction se vérifie dans le manuel de programmation NUM 750 T, jamais de mémoire.

Observé dans des programmes qui ont réellement tourné sur la machine (produits par Go2CAM, 2020 à 2023) :
voir `docs/reference-go2cam-ct200.md` et les exemples dans `docs/exemples-cn/`. Le squelette de programme,
le changement d'outil, `G96`/`G92`/`G95`, `G41`/`G42`, `G33` et `G83` y sont relevés tels quels.

## Règles de travail

- Langue : français pour l'interface, la documentation, les identifiants du code et les échanges.
- Environnement : `.venv` à la racine (`py -3.12 -m venv .venv`, puis `requirements.txt`). Tests : `.venv\Scripts\python -m pytest tests`.
  Les tests d'interface tournent hors écran ; `tools\capture.py` donne une capture en vraie fenêtre pour le contrôle visuel.
- Git : sur le poste de la semaine, Git est la version portable MinGit installée par winget
  (`%LOCALAPPDATA%\Microsoft\WinGet\Packages\Git.MinGit_...\cmd`, ajouté au PATH utilisateur).
- Le projet est développé sur deux ordinateurs (un la semaine, un le week-end), synchronisés par Git.
  Les conversations Claude Code ne suivent pas d'un poste à l'autre : tout ce qui doit être retenu va dans ce dépôt.
- En début de séance : lire `docs/ETAT.md`.
- En fin de séance : mettre à jour `docs/ETAT.md`, puis proposer le commit et le push.
- Toute nouvelle décision de conception est ajoutée à ce fichier, dans « Décisions prises ».
- Sécurité machine : un programme ISO n'est jamais envoyé au tour sans relecture par l'utilisateur.
