# Rapport - Reception des releves Klaxo-3

## Phase 1 - Ouvrir la caisse

Source utilisee : le fichier complet du depot `planetsig/ufo-reports`, au commit `c0915f18186e5e2227083702049a838258001a2a`.

La consigne donne une URL avec le nom `ufo-completegeocoded-time-standardized.csv`, mais ce chemin renvoie une erreur 404. Le fichier disponible dans le depot source s'appelle `ufo-complete-geocoded-time-standardized.csv`.

- Lignes contenues dans le fichier : 88 875
- Lignes chargees normalement : 88 679
- Lignes traitees a part : 196

Les lignes mises a part ont 12 champs au lieu des 11 attendus par le manifeste. Elles ne sont pas supprimees : elles sont conservees dans une liste d'anomalies pour inspection. Le probleme observe est un champ vide supplementaire qui decale ensuite les colonnes.

Exemple de ligne problematique :

```csv
10/1/2006 12:00,,,,,0,,,"((EDITORIAL COMMENT ABOUT THE UFO PHENOMEN))  ufo+alien+reptiles",10/30/2006,0,0
```

Cette ligne contient une case vide de trop avant le commentaire. Avec les onze champs officiels, le commentaire se retrouve a la place de `date_posted`, puis les coordonnees se decaleraient aussi. Je la garde donc a part au lieu de la charger comme une ligne normale.

## Phase 2 - Rien n'est du bon type

Les 88 679 lignes bien formees de la phase 1 sont converties sans supprimer de ligne. Les valeurs impossibles a convertir restent dans le tableau avec une valeur `None`, et l'anomalie est comptee a part. Pour `datetime`, les heures ecrites `24:00` sont signalees puis normalisees au lendemain a `00:00`, car Python ne les accepte pas comme heure valide.

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
