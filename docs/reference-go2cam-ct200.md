# CTgraph — Ce que produit le post-processeur Go2CAM pour le CT200

Rédigé le 23 novembre 2026, par lecture de neuf programmes ISO réellement générés par Go2CAM
pour le tour Cazeneuve CT200 (NUM 750 T) entre 2020 et 2023. Les fichiers sont copiés dans
`docs/exemples-cn/`. Les originaux sont sur le disque D: du poste de la semaine :

- `D:\D Métal\chantiers archivés\plus vieux\2020\2020-02-18 Trinq - rondelles\` (deux `.NC`, février 2020)
- `D:\D Métal\atelier\2023-08-28 cintreuse - galets à usiner\Go2CAM\` (trois `.txt`, septembre 2023, dont filetage)
- `D:\D Métal\atelier\0 - archives atelier\2023-10-14 support multipieds\Go2CAM\` (quatre `.txt`, novembre 2023, dont perçage G83)

Le post-processeur Go2CAM lui-même (ses fichiers de configuration) et le logiciel d'envoi RS232
n'ont pas été trouvés sur ce poste. Go2CAM n'y est pas installé (seule la licence est archivée dans
`D:\D Métal\documentation technique\logiciels\GO2CAM\`, avec le guide *Création Porte Plaquette 6.08.pdf*,
utile pour le module porte-plaquettes).

Ce document décrit **ce que l'on observe**, pas ce que dit le manuel. La signification des paramètres
des cycles est à confirmer dans le manuel de programmation NUM 750 T avant d'être codée.

## Enveloppe du programme

```
%4                          numéro de programme (1 à 4 chiffres observés : %4, %9022)
(ARBRE TOURNAGE DE GALET)   titre, sans numéro de bloc
N5 (12/09/23)               date
N10 G95 G40 G80 G90         état initial : avance/tour, pas de correction de rayon, pas de cycle, absolu
N15 G52 G0 X0.              retrait à l'origine machine, X d'abord
N20 G52 G0 Z0.              puis Z
...                         une section par opération
N530 M2                     fin de programme
%
```

- Numéros de bloc `N` par pas de 5, sur toutes les lignes sauf le titre et les lignes vides.
- Une ligne vide sépare les opérations (2023). Les programmes de 2020 n'en ont pas.
- Commentaires entre parenthèses (2023). En 2020 le post-processeur émettait des messages `$EBAUCHE`,
  `$PDJNL 2020K-11` à la place : le `$` affiche un message à l'opérateur sur la CN NUM.
- Nombres : point décimal toujours présent sur les cotes, même entières (`X0.`, `Z5.`, `K3.`, `R1.`),
  trois décimales au plus. Pas de point sur `S`, `T`, `D`, `M`, `Q`, `P10`, `F1`.
- Pas de variables `L`, pas de sauts, pas de sous-programmes : de l'ISO plat. C'est aussi ce que
  `CLAUDE.md` prescrit tant que la grille d'options de la CN n'est pas connue.

## Squelette d'une opération (2023)

```
N80 (EBAUCHE)                   nom de l'opération
N85 (DCLNR 2020K 12)            désignation de l'outil
N90 M3 M41 G97 S1000            broche en route à vitesse fixe 1000 tr/min, gamme M41, avant le changement d'outil
N95 T11 D11 M6                  outil 11, correcteur 11, changement
N100 X54. Z2.167                approche (G0 modal hérité du G52 G0)
N105 G92 S2500                  limitation de vitesse de broche pour la vitesse de coupe constante
N110 G96 S100                   vitesse de coupe constante, 100 m/min
N115 G0 G90 X54. Z2.167         point de départ
N120 M7                         arrosage
N125 G95 G1 F0.25 X50.          avance par tour 0,25 mm/tr, première passe
...                             passes en G0 / G1 explicites
N180 M9                         arrosage coupé
N185 G52 G0 X0.                 retrait origine machine, X d'abord
N190 G52 G0 Z0.                 puis Z
```

Observations :

- **Sens de broche** : `M3` avec les outils à droite (DCLNR, PDJNR), `M4` avec les outils à gauche
  (DCLNL, PDJNL). La règle exacte dépend de la position de la tourelle, à confirmer avec l'utilisateur.
- **Gamme** : `M41` en 2023, `M40` en 2020.
- **Le `G97 S1000` précède tout changement d'outil**, puis `G96` est réarmé pour la coupe.
- Quand deux opérations enchaînent le même outil (ébauche puis finition au DCLNL), le post-processeur
  ne refait ni retrait ni changement d'outil : il change seulement `G96 S` et l'avance.
- Les **ébauches paraxiales sont des trajectoires explicites** `G0`/`G1`, pas des cycles `G64`.
  Passe de coupe, dégagement en X de 1 à 2 mm, retour en Z rapide, passe suivante.
  C'est donc la voie « explicite d'abord » qui est éprouvée sur la machine.
- **Finition** : correction de rayon `G41` ou `G42` posée sur le premier `G1` d'approche, levée par
  `G0 G40` sur le dégagement final. Exemple : `G95 G1 F0.05 G42 X36. Z2.` … `G0 G40 X41.6`.
- Les chanfreins et cônes sont des `G1 X.. Z..` combinés. Aucun arc `G2`/`G3` dans ces neuf programmes :
  la syntaxe des arcs (centre `I K` ou rayon) reste à vérifier dans le manuel.
- **Gorge et tronçonnage** (plaquette RF123H25) : `G1 F0.08 X-2.` plonge au-delà de l'axe.

## Cycles observés

Les lignes ci-dessous sont copiées telles quelles. Le sens des adresses est une lecture plausible,
**à confirmer dans le manuel** avant usage.

### Filetage `G33`

```
N505 G0 G90 X40. Z2.
N510 G33 X36. Z-27. Q0 K3. P1.86 F1 S15 R1. EB30. EA0.
N515 M5
```

Pour un M36 × 3 : `X36.` diamètre nominal, `Z-27.` fin de filet, `K3.` pas, `P` profondeur totale
(1,86 dans l'essai, 1,47 dans l'autre version), `S15` et `F1` ressemblent à des nombres de passes
(ébauche, finition), `R1.` à une longueur de dégagement, `EB30.` à l'angle de pénétration, `EA0.` et `Q0`
à un angle ou un décalage de départ. Point d'attention : le post-processeur laisse `G96` actif avant le
`G33`, ce qui surprend pour un filetage ; vérifier sur la machine ce que fait la CN dans ce cas.

### Perçage débourrage `G83`

```
N50 G97 S868
N55 G0 X0. Z5.
N60 F0.24 G83 Z-38.175 P10 Q3 ER5.
N65 G80
```

`P10` première passe, `Q3` passes suivantes, `ER5.` plan de dégagement : lecture plausible. `G80`
annule le cycle juste après. Le perçage simple au foret D13 est un `G1` ordinaire (`G95 G1 F0.3 Z-37.692`).

### Centrage

```
N50 G97 S637
N55 G0 X0. Z5.
N60 G1 F0.18 Z-8.
N65 G0 Z5.
```

## Tourelle telle qu'utilisée en 2023

Postes et outils relevés dans les programmes, point de départ pour la bibliothèque d'outils :

| Poste | Outil | Usage |
| --- | --- | --- |
| T1 D1 | PDJNR 2020K 15 ou PDJNL 2020K-11 | finition, chariotage |
| T2 D2 | SER 2020 K16 + plaquette 16ER300ISO (Nikko), ou foret à centrer | filetage extérieur |
| T4 D4 | foret à centrer D10 | centrage |
| T5 D5 | DCLNL 2020K 12 / PDJNL | finition |
| T6 D6 | foret D11 | perçage |
| T8 D8 | foret D13 | perçage |
| T10 D10 | RF123H25-2020BM (Sandvik CoroCut) | gorge, tronçonnage |
| T11 D11 | DCLNR ou DCLNL 2020K 12, PCLNL 2020K-12 | ébauche |

Les postes changent d'un programme à l'autre : la tourelle est rééquipée par pièce.

## Conditions de coupe relevées

| Opération | Outil | Vc (G96) | Limite (G92) | Avance (G95) |
| --- | --- | --- | --- | --- |
| Ébauche acier, plaquette CNMG 12 | DCLNR 2020K 12 | 100 à 250 m/min | 2500 à 5000 tr/min | 0,25 à 0,33 mm/tr |
| Finition, plaquette DNMG 15 | PDJNR 2020K 15 | 250 à 280 m/min | — | 0,05 à 0,1 mm/tr |
| Gorge, tronçonnage | RF123H25 | 50 à 150 m/min | 2500 tr/min | 0,05 à 0,08 mm/tr |
| Filetage | 16ER300ISO | 100 m/min (G96, à vérifier) | 2500 tr/min | pas 3 mm |
| Perçage D11, D13 | forets | G97 868 et 735 tr/min | — | 0,24 à 0,3 mm/tr |
| Centrage D10 | foret à centrer | G97 637 tr/min | — | 0,18 mm/tr |

Les rondelles de 2020 (diamètre 38 à 55) étaient tournées à 40 m/min, 0,1 mm/tr, limite 9000 tr/min :
matière différente, probablement.

## Ce que cela fixe pour le post-processeur CTgraph

1. Reproduire d'abord **exactement** ce squelette : il a tourné sur la machine. Un programme CTgraph
   doit pouvoir être comparé ligne à ligne à un programme Go2CAM pour la même pièce.
2. Trajectoires explicites `G0`/`G1` pour l'ébauche et la finition, cycles `G33` et `G83` repris tels
   quels avec leurs adresses, dès que leur signification est confirmée.
3. Arcs : rien d'observé, syntaxe à vérifier dans le manuel avant d'émettre `G2`/`G3`.
