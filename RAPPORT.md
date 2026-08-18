# Rapport - Reception des releves Klaxo-3

## Phase 1 - Ouvrir la caisse

Source utilisee : le fichier complet du depot `planetsig/ufo-reports`, au commit `c0915f18186e5e2227083702049a838258001a2a`.

La consigne donne une URL avec le nom `ufo-completegeocoded-time-standardized.csv`, mais ce chemin renvoie une erreur 404. Le fichier disponible dans le depot source s'appelle `ufo-complete-geocoded-time-standardized.csv`.

- Lignes contenues dans le fichier : 88 875
- Lignes chargees normalement : 88 679
- Lignes traitees a part : 196

Les lignes mises a part ont 12 champs au lieu des 11 attendus par le manifeste. Je ne les charge pas dans le tableau principal, parce que cela decalerait les colonnes. Elles sont gardees dans une liste d'anomalies pour inspection.

Exemple de ligne problematique :

```csv
10/1/2006 12:00,,,,,0,,,"((EDITORIAL COMMENT ABOUT THE UFO PHENOMEN))  ufo+alien+reptiles",10/30/2006,0,0
```

Cette ligne contient une case vide de trop avant le commentaire. Avec les onze champs officiels, le commentaire se retrouve a la place de `date_posted`, puis les coordonnees se decaleraient aussi. Je la garde donc a part au lieu de la charger comme une ligne normale.

## Phase 2 - Rien n'est du bon type

Les 88 679 lignes bien formees de la phase 1 sont converties sans supprimer de ligne. Quand une valeur ne passe pas, je garde la ligne et je mets `None` dans la valeur convertie. Pour `datetime`, les heures ecrites `24:00` sont signalees puis normalisees au lendemain a `00:00`, car Python ne les accepte pas comme heure valide.

Comptes par champ converti :

- `duration_seconds` : 5 valeurs signalees
- `latitude` : 1 valeur signalee
- `longitude` : 0 valeur signalee
- `datetime` : 1 220 valeurs signalees
- `date_posted` : 0 valeur signalee

Anomalies observees :

- Structure CSV invalide : 196 lignes ont 12 champs au lieu de 11. Exemple ligne 877. Origine probable : service de transmission, car le decoupage des colonnes est casse.
- Heure d'observation `24:00` : 1 220 valeurs dans `datetime`, par exemple `10/10/2005 24:00`. Origine probable : temoin ou saisie initiale, car c'est l'heure rapportee pour l'observation.
- Duree numerique invalide : 3 valeurs de `duration_seconds` contiennent un backtick, par exemple `2\``, `8\`` et `0.5\``. Origine probable : service de transmission ou normalisation de la duree, car la colonne est censee etre numerique.
- Duree numerique manquante : 2 valeurs vides dans `duration_seconds`, alors que `duration_hours_min` contient du texte comme `1/3200` ou `1&#39`. Origine probable : temoin pour la duree textuelle ambigue, puis service de normalisation incapable de produire un nombre.
- Latitude invalide : 1 valeur `33q.200088` dans `latitude`. Origine probable : capteur/geocodage ou service de transmission, car une coordonnee numerique contient une lettre.

## Phase 3 - Le Conseil veut trier les canulars

Regle choisie : je marque un releve comme canular si le champ `comments` contient le mot `hoax`.

- Releves marques comme canulars : 802
- Total utilise : 88 679 releves charges normalement
- Proportion : 0,904 %

Cette regle attrape surtout les signalements deja accompagnes d'une note editoriale du type `Possible hoax`. Elle peut donc attraper a tort des cas seulement suspects, pas confirmes. Elle rate aussi tous les canulars qui n'utilisent pas explicitement le mot `hoax` dans le commentaire.

## Phase 4 - Le premier verdict

Modele utilise : `CountVectorizer` puis `LogisticRegression`, entraine uniquement sur la colonne `comments`.

J'ai separe les releves en deux groupes avec `train_test_split`, en gardant la meme proportion de canulars dans les deux groupes (`stratify`). Le modele apprend sur 66 509 releves et il est teste sur 22 170 releves qu'il n'a pas vus pendant l'apprentissage. Le tirage est fixe avec `random_state=42`. Exemples de lignes presentes dans le jeu de test : 11 622, 26 322, 27 726, 28 929, 41 909, 46 519, 49 620, 67 787, 87 320, 88 615.

Resultats sur le jeu de test :

- Canulars reels dans le test : 201
- Signalements marques comme canulars par le modele : 200
- Sur 100 canulars reellement presents, le modele en attrape 99,5
- Sur 100 releves que le modele signale, 100,0 sont vraiment marques comme canulars

Ce premier verdict est tres fort, mais il faut deja se mefier : l'etiquette de la phase 3 vient du texte `comments`, et le modele lit aussi `comments`. C'est utile pour un premier essai, mais ce n'est pas encore une preuve solide.

## Phase 5 - Le Conseil ne vous croit pas

Audit des colonnes utilisees avant et apres correction :

| Colonne | Qui ecrit cette information | A quel moment | Savait deja si c'etait un canular |
| --- | --- | --- | --- |
| `comments` | temoin puis note editoriale du Bureau | recit initial puis traitement du dossier | oui |
| `datetime` | temoin | au moment du signalement | non |
| `city` | temoin | au moment du signalement | non |
| `state` | temoin ou formulaire | au moment du signalement | non |
| `country` | temoin ou formulaire | au moment du signalement | non |
| `shape` | temoin | au moment du signalement | non |
| `duration_seconds` | service de normalisation | apres saisie de la duree | non |
| `duration_hours_min` | temoin | au moment du signalement | non |
| `latitude` | capteur ou geocodage | avant l'analyse du dossier | non |
| `longitude` | capteur ou geocodage | avant l'analyse du dossier | non |

La colonne `comments` sort du modele, parce que mon etiquette `is_hoax` vient justement du mot `hoax` trouve dans ce texte. Le modele corrige utilise donc `datetime`, `city`, `state`, `country`, `shape`, `duration_seconds`, `duration_hours_min`, `latitude` et `longitude`.

Scores avant / apres :

| Version du modele | Colonnes principales | Canulars attrapes sur 100 vrais canulars | Vrais canulars sur 100 signalements marques |
| --- | --- | ---: | ---: |
| Avant audit | `comments` | 99,5 | 100,0 |
| Apres audit | champs de lieu, temps, forme, duree et coordonnees | 13,9 | 4,9 |

Le premier chiffre n'avait pas vraiment le droit d'exister : le modele lisait le meme texte qui avait servi a fabriquer la reponse attendue. Il ne detectait pas un canular a partir d'un nouveau signalement, il reconnaissait surtout la trace du mot `hoax` deja ecrit dans le dossier. Une fois cette information retiree, les autres champs donnent quelques signaux faibles, mais beaucoup moins fiables.

## Phase 6 - Le modele le plus bete du Bureau

Systeme du stagiaire : repondre toujours `ce n'est pas un canular`.

Scores sur le meme jeu de test que les phases 4 et 5 :

| Systeme | Taux de bonnes reponses | Canulars attrapes sur 100 vrais canulars | Vrais canulars sur 100 signalements marques |
| --- | ---: | ---: | ---: |
| Stagiaire | 99,09 % | 0,0 | 0,0 |
| Modele corrige | 96,79 % | 13,9 | 4,9 |

Le taux de bonnes reponses du stagiaire est eleve parce que les canulars sont tres rares : seulement 201 cas dans les 22 170 releves du test. Dire toujours `pas canular` donne donc presque toujours la bonne reponse, mais ne trouve strictement aucun canular. Pour defendre mon travail, je presente le rappel des canulars, parce que c'est la mesure qui repond a la vraie question du Conseil : combien de canulars le systeme arrive a attraper.

## Phase 7 - Plusieurs temoins, un seul evenement

Pour reconnaitre deux releves qui parlent probablement du meme evenement, j'utilise quatre informations : la date d'observation, la ville, l'etat et le pays. Je n'utilise pas le commentaire pour construire cette cle, parce que ce serait trop proche du texte que le modele apprend.

- Evenements avec plusieurs temoins : 2 399
- Nombre de temoins dans le plus gros evenement : 56
- Evenements coupes entre apprentissage et test dans l'ancienne decoupe aleatoire : 979
- Releves appartenant a ces evenements coupes : 2 419

Le plus gros evenement est Tinley Park, `il`, `us`, le 31/10/2004. Avec la nouvelle decoupe par evenement, ses 56 releves sont tous du meme cote : apprentissage. `analyse.py` les affiche tous a l'ecran, avec leur ligne, leur heure et leur commentaire court.

J'ai aussi compte les commentaires recopies exactement :

- Groupes de commentaires identiques dans tout le fichier : 252
- Releves concernes : 615
- Groupes de commentaires identiques dans un meme evenement : 22

Je ne les supprime pas, car certains textes identiques sont trop courts pour prouver une vraie copie, par exemple `Fireball`. Par contre, quand ils appartiennent au meme evenement, la nouvelle decoupe les garde ensemble du meme cote.

Scores avant / apres decoupe par evenement :

| Modele | Decoupe | Canulars attrapes sur 100 vrais canulars | Vrais canulars sur 100 signalements marques |
| --- | --- | ---: | ---: |
| Phase 4 avec `comments` | aleatoire | 99,5 | 100,0 |
| Phase 4 avec `comments` | par evenement | 99,5 | 100,0 |
| Modele corrige sans `comments` | aleatoire | 13,9 | 4,9 |
| Modele corrige sans `comments` | par evenement | 9,3 | 3,0 |

Le score du modele de phase 4 ne bouge pas, ce qui confirme surtout qu'il depend encore de la fuite par `comments`. La comparaison utile est donc celle du modele corrige : quand les temoignages d'un meme evenement ne peuvent plus etre repartis des deux cotes, le rappel passe de 13,9 a 9,3 et la precision de 4,9 a 3,0.

## Phase 8 - L'ordre des choses

Pour la decoupe temporelle, j'utilise `date_posted`. C'est la date ou le dossier arrive dans la base du Bureau, donc c'est celle qui correspond le mieux a une transmission que le systeme devra traiter dans le futur. La date d'observation dit quand le temoin a leve les yeux, mais pas quand le Bureau a recu l'information.

- Date de coupure : 10/10/2011
- Releves dans l'apprentissage : 66 109
- Releves dans le test chronologique : 22 570

Proportions de canulars :

| Cote | Periode | Releves | Proportion de canulars |
| --- | --- | ---: | ---: |
| Apprentissage | avant le 10/10/2011 | 66 109 | 0,954 % |
| Test | a partir du 10/10/2011 | 22 570 | 0,758 % |

Ces deux proportions ne sont pas egales. Il y a moins de canulars marques dans les dossiers recents du test. Comme mon etiquette depend du mot `hoax` dans les commentaires, cela peut venir d'une difference dans la maniere dont le Bureau annotait les dossiers selon les periodes.

Scores apres decoupe temporelle :

| Modele | Canulars attrapes sur 100 vrais canulars | Vrais canulars sur 100 signalements marques |
| --- | ---: | ---: |
| Phase 4 avec `comments` | 100,0 | 100,0 |
| Modele corrige sans `comments` | 2,3 | 1,6 |

Le modele avec `comments` reste parfait, mais ce n'est toujours pas rassurant : il lit encore la colonne qui contient le mot ayant servi a fabriquer l'etiquette. Le modele corrige, lui, tombe fortement avec l'ordre temporel. C'est le signe que la decoupe aleatoire donnait une vision trop optimiste.

## Phase 9 - Les cases vides

J'ai pris les trois colonnes les plus trouees et j'ai compare la proportion de canulars quand la case est vide avec la proportion quand elle est remplie.

| Colonne | Cases vides | Canulars si vide | Cases remplies | Canulars si rempli |
| --- | ---: | ---: | ---: | ---: |
| `country` | 12 365 | 1,156 % | 76 314 | 0,864 % |
| `state` | 7 409 | 1,296 % | 81 270 | 0,869 % |
| `duration_hours_min` | 3 017 | 2,353 % | 85 662 | 0,853 % |

Les trous ne se comportent pas exactement comme les cases remplies. Le cas le plus net est `duration_hours_min` : les releves sans duree ecrite par le temoin ont une proportion de canulars beaucoup plus haute.

Traitement retenu : je ne jette pas ces lignes et je ne remplace pas les trous par la valeur la plus frequente. Dans les variables donnees au modele, un trou devient le marqueur explicite `__missing__`.

Ce traitement ne detruit pas ce que je viens de mesurer, parce que le modele peut toujours voir qu'une case etait vide. Par exemple, `country=__missing__` reste different de `country=us`.

## Phase 10 - La chaine de traitement du Bureau

La correction importante est dans l'ordre des operations : je coupe d'abord les indices d'apprentissage et de test, puis le `CountVectorizer` apprend son vocabulaire seulement sur les textes construits depuis l'apprentissage. Le test est transforme ensuite avec ce vocabulaire deja appris. Le marqueur `__missing__` est une regle fixe, pas une valeur calculee depuis tout le fichier.

J'utilise la decoupe temporelle de la phase 8 :

| Cote | Releves | Proportion de canulars |
| --- | ---: | ---: |
| Apprentissage | 66 109 | 0,954 % |
| Test | 22 570 | 0,758 % |

Demonstration avec un releve invente a la main :

```text
datetime=2014-06-01 22:30:00 | city=tinley park | state=il | country=us | shape=light | duration_seconds=180.0 | duration_hours_min=3 minutes | latitude=41.5734 | longitude=-87.7845
```

Ce releve passe dans la meme chaine que les vraies lignes : construction des variables, vectorisation avec le vocabulaire appris sur l'apprentissage, puis prediction par la regression logistique. La prediction sortie par `analyse.py` est `0`, donc `pas canular`.

Scores apres correction de la chaine, sur le test temporel :

- Sur 100 canulars reellement presents, le modele en attrape 2,3
- Sur 100 releves que le modele signale, 1,6 sont vraiment marques comme canulars

Ces chiffres sont bas, mais ils sont plus honnetes : le vocabulaire du modele n'a pas ete appris sur les releves du test.

## Phase 11 - Combien de temps ca a dure

Je construis une duree numerique finale sans supprimer de ligne. Je pars de `duration_seconds` quand elle est exploitable, puis j'utilise `duration_hours_min` pour recuperer des cas que la colonne numerique a rates, par exemple les fractions ou les durees ecrites avec des mots.

- Releves dont la duree reste inutilisable apres traitement : 3
- Releves ou les deux colonnes de duree se contredisent : 1 529
- Duree mediane retenue : 120 secondes
- Releves qui annoncent plus d'une journee d'observation : 208

Exemples ou les deux colonnes ne racontent pas la meme chose :

| Ligne | `duration_seconds` | `duration_hours_min` interprete | Texte brut |
| ---: | ---: | ---: | --- |
| 4 | 20 | 1 800 | `1/2 hour` |
| 10 | 120 | 240 | `several minutes` |
| 23 | 1 200 | 3 600 | `one hour?` |

Trois durees les plus longues :

| Ligne | Duree retenue | Texte brut | Decision |
| ---: | ---: | --- | --- |
| 610 | 97 836 000 s | `31 years` | gardee comme valeur extreme, exclue de la mediane |
| 59 367 | 82 800 000 s | `23000hrs` | gardee comme valeur extreme, exclue de la mediane |
| 82 653 | 66 276 000 s | `21 years` | gardee comme valeur extreme, exclue de la mediane |

Je garde ces valeurs dans le comptage des durees superieures a une journee, parce qu'elles existent dans le fichier. Par contre, je les exclus de la mediane : elles ressemblent souvent a une periode de phenomenes repetes ou a une saisie aberrante, pas a une seule observation continue. Sinon, quelques valeurs enormes peuvent tirer la statistique centrale dans une direction peu defendable.

## Phase 12 - La ville et l'heure

Pour utiliser la ville sans fabriquer un tableau absurde, je garde seulement les villes presentes au moins 20 fois dans l'apprentissage ; toutes les autres villes deviennent `__rare_city__`. Cette liste est apprise apres la decoupe temporelle, uniquement sur l'apprentissage.

Largeur du tableau :

| Version | Colonnes |
| --- | ---: |
| Avant traitement : ville brute + forme brute + heure brute | 22 071 |
| Apres traitement : villes frequentes + formes traitees + heure cyclique | 522 |

Dans toute la transmission, 14 177 villes n'apparaissent qu'une seule fois. Les garder chacune dans une colonne separee pousserait le modele a apprendre par coeur des cas qu'il ne reverra probablement jamais.

Pour l'heure, je n'utilise pas un nombre de 0 a 23. Je l'encode sur un cercle avec deux valeurs, sinus et cosinus. Les distances obtenues sont :

| Comparaison | Distance dans l'encodage |
| --- | ---: |
| 23h - 0h | 0,261 |
| 23h - 20h | 0,765 |

Cette fois, 23h est bien plus proche de 0h que de 20h, ce qui correspond a la realite d'un cycle journalier.

Pour `shape`, il y a 29 formes non vides au depart. Je fusionne `changed` avec `changing`, `round` avec `circle`, puis je regroupe les formes presentes moins de 20 fois dans l'apprentissage en `__rare_shape__`. Il reste 22 formes non vides apres traitement, plus le marqueur `__missing__` pour les formes absentes.

Le modele de cette phase utilise seulement la ville traitee, la forme traitee et l'heure cyclique, toujours avec la decoupe temporelle. Il attrape 48,5 canulars sur 100 vrais canulars, mais sa precision tombe a 1,1 vrai canular sur 100 signalements marques. Le rappel monte parce que le modele signale beaucoup plus de dossiers ; ce n'est pas une amelioration globale, c'est surtout une preuve que ces variables bougent le comportement du systeme.

Aucun encodage de cette phase n'utilise la cible `is_hoax`. Les listes de villes et de formes gardees sont apprises sur l'apprentissage seul.

## Phase 13 - La facture du Bureau

Le Conseil impose la facture suivante : un canular rate coute 30 credits, une fausse alerte sur un releve honnete coute 2 credits, et les bonnes decisions coutent 0. Je calcule donc, pour chaque frontiere, la facture :

```text
cout = 30 * canulars rates + 2 * fausses alertes
```

Facture observee sur le test temporel du modele de phase 12 :

| Frontiere | Canulars rates | Fausses alertes | Facture |
| ---: | ---: | ---: | ---: |
| 0,0 | 0 | 22 399 | 44 798 |
| 0,1 | 24 | 18 086 | 36 892 |
| 0,2 | 26 | 17 725 | 36 230 |
| 0,3 | 28 | 17 398 | 35 636 |
| 0,4 | 47 | 12 320 | 26 050 |
| 0,5 | 88 | 7 607 | 17 854 |
| 0,6 | 133 | 2 920 | 9 830 |
| 0,7 | 162 | 1 079 | 7 018 |
| 0,8 | 167 | 368 | 5 746 |
| 0,9 | 170 | 49 | 5 198 |
| 1,0 | 171 | 0 | 5 130 |

La frontiere retenue est donc `1,0`. Dans ce test, cela revient a ne marquer aucun releve comme canular avec ce modele, car aucune probabilite n'atteint exactement 1. Ce n'est pas flatteur pour le modele, mais c'est la decision la moins couteuse avec la grille imposee.

La frontiere par defaut de la bibliotheque, `0,5`, coute 17 854 credits. La frontiere retenue coute 5 130 credits. L'ecart est donc de 12 724 credits en faveur de la frontiere retenue.

La justification ne vient pas d'un score de machine learning : elle vient du prix des erreurs. Avec une precision tres basse, les fausses alertes sont assez nombreuses pour couter plus cher que laisser passer tous les canulars marques dans ce test.

## Conclusion

J'arrive a relancer toute l'analyse depuis le telechargement du fichier jusqu'aux scores actuels. Les donnees sont bien sales : certaines lignes n'ont pas le bon nombre de colonnes, des durees ne sont pas numeriques, une latitude contient une lettre et beaucoup d'heures sont ecrites `24:00`.

Le modele qui utilise `comments` semble excellent, mais il profite d'une fuite d'information. Apres retrait de cette colonne, le modele devient beaucoup moins bon, mais il garde un avantage important sur le systeme du stagiaire : lui trouve au moins une partie des canulars, alors que le stagiaire n'en trouve aucun. Les phases 7 a 13 ajoutent les corrections de methode : un meme evenement ne doit plus etre coupe entre apprentissage et test, le test doit porter sur des dossiers plus recents, les cases vides doivent rester visibles, le vocabulaire du modele doit etre appris uniquement sur l'apprentissage, la duree doit etre reconstruite sans effacer les contradictions, les variables riches comme ville, heure et forme doivent etre encodees sans fuite ni explosion de largeur, et la decision finale doit etre prise en credits plutot qu'avec une frontiere arbitraire a `0,5`.
