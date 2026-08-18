# SpaceInvader

Analyse reproductible des releves Klaxo-3 pour la partie 1 du projet.

Le rapport couvre les phases 1 a 18 dans `RAPPORT.md`. Le script `analyse.py`
reconstruit les chiffres depuis le CSV local ou le telecharge si besoin.

## Lancer

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python analyse.py
```

Le script telecharge le CSV dans `data/releves_klaxo3.csv` si le fichier est absent.
Le CSV, l'environnement virtuel et les fichiers IDE ne
sont pas versionnes dans Git.
