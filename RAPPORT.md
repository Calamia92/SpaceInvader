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
