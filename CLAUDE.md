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
  rayon sur le « R » d'un diamètre), une seule étape d'annulation au relâchement.
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
- **Cote sur-contrainte = cote pilotée** : une cote posée qui entre en conflit, est redondante ou n'est pas atteignable passe
  automatiquement en cote pilotée (`Cote.pilotee`, paramètre libre et `driving=False` pour PlaneGCS), grisée et
  entre parenthèses ; le solveur y écrit la mesure après chaque résolution. Elle redevient pilotante à la demande
  si cela ne sur-contraint pas.
- **Vue 3D** (`ctgraph/ui/vue_3d.py`) : QOpenGLWidget incrusté en haut à droite de l'esquisse, nuanceurs GLSL 1.20,
  sans PyOpenGL. Révolution des contours fermés à 96 facettes, normales exactes de la surface de révolution
  lissées le long du profil sous un angle de pli de 30° (arcs lisses, épaulements nets), éclairage deux faces.
  Repère : Z pièce = X monde. `CTGRAPH_SANS_3D=1` la désactive (tests hors écran). Le mandrin, le brut et
  l'outil viendront s'y ajouter.
- **Contours fermés remplis** d'une teinte discrète (`VueEsquisse.contours_fermes`) : chaînes dont chaque sommet
  relie exactement deux éléments, refermées sur elles-mêmes ou dont les deux bouts touchent l'axe (fermeture par
  l'axe de révolution). Les boucles à sommets de degré ≥ 3 attendent un vrai parcours de faces.
- **Les cotes sont un seul outil** (`Cote`, touche C), pas cinq boutons : le type se déduit des éléments cliqués et de
  l'endroit où la cote est posée (`VueEsquisse.deduire_cote`). Point → diamètre ; arc → rayon ; ligne → longueur Z
  si posée au-dessus ou au-dessous, sinon diamètre (horizontale), angle (inclinée) ou distance (verticale) ;
  deux lignes → angle, longueur Z entre deux verticales, ou écart (`TypeCote.ECART`, distance point-droite
  PlaneGCS) entre deux parallèles ; deux points → longueur Z (distance si même z).
- **Élaguer** : un trait tiré au travers des objets, un seul comportement : la portion retirée va jusqu'aux croisements
  voisins (`elagage.elaguer` garde ses autres modes en réserve, l'interface ne les expose plus).
  Les points de coupe reçoivent « point sur » l'objet croisé ; une ligne scindée garde horizontal/vertical/parallèle/
  perpendiculaire sur ses deux morceaux, un arc scindé garde son centre et reçoit « égal » entre ses morceaux ;
  les cotes de longueur disparaissent.

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
