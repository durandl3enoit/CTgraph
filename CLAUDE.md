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
  Courses et broche de la machine : valeurs provisoires, à relever. Trois **cotes du brut** sont toujours affichées
  dans l'esquisse (étiquettes de genre « brut », non sélectionnables, éditables au double-clic et à la molette) :
  Ø brut, L brut, marge en bout ; changer la longueur ajuste le dépassement (prise et marge fixes).

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
- **Atelier : trois volets repliables latéralement** (`ui/zone_atelier.py`, demandé le 24 novembre 2026), un
  seul `QDockWidget` sans barre de titre ancré à droite (visibilité `atelier.visible`, touche `O`), contenant
  de gauche à droite **Tourelle**, **Stock d'outils**, **Plaquettes**. Chacun est un `VoletLateral`
  (`ui/volet_lateral.py`) : bandeau vertical cliquable, titre tourné, chevron ; replié, le volet est borné à
  `LARGEUR_BANDEAU`. Bandeau du côté extérieur (à gauche pour les deux premiers, à droite pour le dernier).
  État mémorisé dans `volet.<clé>`, déplié par défaut pour le seul stock d'outils ; le menu Affichage a une
  entrée par volet. Les tests d'interface masquent l'atelier : il rétrécit la vue d'esquisse et fausserait
  les clics simulés.
- **Tourelle** (`ctgraph/tourelle.py`, `ui/zone_tourelle.py`) : douze postes **VDI 30** (DIN 69880), queue
  Ø 30 mm fixée par la norme (c'est elle qui borne `outils.QUEUE_MAXI` à 20 mm). Poste 1 en haut,
  numérotation horaire vue de face ; clic sur un logement ou sur sa ligne pour le mettre en travail.
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
