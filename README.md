# Mirror Trade Risk App

App Streamlit pour analyser la cohérence miroir du commerce extérieur à partir des pages publiques officielles WITS / Comtrade.

## Ce que fait l'app

Tu choisis :
- un `HS code`
- une `année`

Puis l'app va :
- récupérer les pages officielles publiques WITS
- prendre chaque pays exportateur trouvé
- comparer :
  - `reported exports` = quantité exportée déclarée par le pays
  - `mirror imports` = quantité importée déclarée par les autres pays depuis ce pays
- calculer un `gap %`
- attribuer un risque `LOW / MEDIUM / HIGH`

Important :
- le score n'utilise pas seulement le pourcentage
- il tient aussi compte du volume absolu en `kg`
- donc un très petit exportateur n'est pas automatiquement pénalisé à cause d'un grand écart en pourcentage
- l'app affiche aussi un résumé explicite de la règle appliquée à chaque pays

## Règles du risque

- `LOW` si le flux est trop petit ou si l'écart reste faible à l'échelle du pays
- `MEDIUM` si l'écart est significatif en `%` et en `kg`
- `HIGH` si l'écart est très fort en `%` et en `kg`

avec :

```text
gap = abs(mirror_imports_kg - reported_exports_kg) / reported_exports_kg
```

## Lancer l'app

```powershell
cd C:\Users\liad\Documents\hackaton
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Ensuite ouvre :

```text
http://localhost:8501
```

## Exemples de codes

```text
283691
850760
```

Note importante :
certains couples `HS code + année` peuvent ne pas être disponibles via le point d'accès public WITS utilisé ici. Dans ce cas, l'app affichera une erreur claire.

Cas spécial :
- `850760` peut utiliser un fichier CSV Comtrade local si tu l'as téléchargé et placé dans le dossier du projet
- cela contourne les limites du point d'accès public WITS sur les batteries

## Cache local

Quand tu cliques sur `Fetch Official Data`, l'app sauvegarde aussi la base localement sous la forme :

```text
mirror_risk_<hs_code>_<year>.json
```

Ensuite tu peux recharger cette version avec `Load Cached Data`.

## Ligne de commande

Tu peux aussi générer un dataset directement :

```powershell
python trade_risk_analysis.py --product-code 283691 --year 2024
```
