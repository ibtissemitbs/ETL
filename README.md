# ETL Platform

Plateforme web FastAPI pour profiler, nettoyer et exporter des datasets CSV, Excel et JSON. Le projet combine des règles déterministes, des règles métier, une couche ML légère, un plan LLM optionnel, un moteur RAG et un cache CAG.

Le LLM ne modifie jamais les données directement. Il produit uniquement un plan JSON validé, puis le moteur de règles applique les transformations autorisées de façon déterministe.

## Fonctionnalités

- Upload de fichiers CSV, XLSX, XLS et JSON.
- Profiling automatique: types, valeurs nulles, doublons, ratios numériques/date, qualité globale.
- Détection de domaine: `sales`, `logistics` ou `generic`.
- Nettoyage déterministe avec protection des identifiants et colonnes financières.
- Règles métier dédiées Sales / CRM et Logistics / Supply Chain.
- RAG pour enrichir le prompt avec des règles pertinentes.
- CAG pour mettre en cache les plans de transformation par profil de dataset.
- Exports CSV et Excel.
- Frontend statique servi par FastAPI: accueil, workspace ETL, dashboard.

## Stack

- Backend: FastAPI, Pandas, NumPy, Pydantic.
- Frontend: HTML, CSS, JavaScript sans build step.
- ML: scikit-learn, joblib, modèles pré-entraînés dans `models/`.
- LLM: OpenAI, Groq ou Ollama local.
- RAG: ChromaDB si disponible, fallback mémoire sinon.
- Tests: pytest.

## Installation

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Sur Linux/macOS:

```bash
python -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
```

Copier la configuration optionnelle:

```powershell
Copy-Item .env.example .env
```

Les clés LLM sont optionnelles. Sans clé, le système utilise les règles fallback déterministes.

## Démarrage

Windows:

```powershell
.\start_backend.bat
```

Linux/macOS:

```bash
./start_backend.sh
```

Ou directement:

```powershell
.venv\Scripts\python.exe -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

URLs:

- Application: `http://127.0.0.1:8000/`
- Workspace ETL: `http://127.0.0.1:8000/etl`
- Dashboard: `http://127.0.0.1:8000/dashboard`
- API docs: `http://127.0.0.1:8000/docs`

Pour tester rapidement:

```powershell
.venv\Scripts\python.exe scripts\upload_sample.py
```

## Architecture

```text
ETL/
├── backend/
│   ├── main.py              # API FastAPI, routes frontend, upload, export
│   └── uploads/.gitkeep     # fichiers runtime ignorés par Git
├── frontend/
│   ├── index.html           # accueil
│   ├── etl.html             # upload et résultats
│   └── dashboard.html       # dernier rapport
├── src/
│   ├── extract.py           # lecture CSV/Excel/JSON
│   ├── profiler.py          # profil dataset et score de qualité
│   ├── domain_context.py    # détection Sales/Logistics/Generic
│   ├── hybrid_ml.py         # prédiction rôles/actions/anomalies
│   ├── llm_helper.py        # prompt, clients LLM, fallback, validation plan
│   ├── rag_engine.py        # règles RAG via ChromaDB ou mémoire
│   ├── cag_engine.py        # cache de plans par profil
│   ├── rules_engine.py      # règles déterministes partagées
│   ├── transform.py         # application du plan validé
│   ├── sales_domain_cleaner.py
│   ├── logistics_domain_cleaner.py
│   ├── data_structure_detector.py
│   └── load.py
├── config/
│   ├── settings.json
│   └── prompt_examples.json
├── models/                  # modèles ML joblib versionnés
├── examples/
│   └── sample_sales.csv
├── scripts/
│   ├── upload_sample.py
│   ├── apply_rules_demo.py
│   └── run_local_llm_test.py
├── tests/
│   └── test_core_pipeline.py
├── data/                    # dossiers de travail vides
└── reports/                 # rapports générés ignorés par Git
```

## Pipeline de traitement

1. Upload et validation de format.
2. Lecture du fichier avec fallback pour certains `.xls` corrompus.
3. Profiling du dataset.
4. Détection de domaine et détection de structure pivotée.
5. Prédictions ML: rôle de colonne, action probable, score d'anomalie.
6. Application des règles métier du domaine.
7. Génération ou récupération du plan LLM.
8. Validation stricte du plan: actions autorisées uniquement.
9. Application déterministe des règles.
10. Calcul des métriques avant/après.
11. Stockage du rapport en mémoire pour le dashboard.
12. Export CSV ou Excel à la demande.

## LLM

Le LLM est utilisé comme assistant de planification, pas comme moteur de mutation.

Actions autorisées:

- `fill_missing`
- `convert_type`
- `standardize_date`
- `remove_duplicate`
- `mark_as_anomaly`
- `reject_row`

Protections importantes:

- Les identifiants (`id`, `order_id`, `shipment_id`, `uuid`, etc.) ne sont pas convertis en dates ou nombres destructifs.
- Les colonnes métier numériques (`price`, `quantity`, `weight`, `shipping_cost`, `amount`, `revenue`, etc.) ne sont jamais remplies automatiquement avec `0`.
- Les colonnes financières ne sont jamais converties en datetime.
- Les grands fichiers contournent l'appel LLM et utilisent un fallback local pour éviter les blocages.

Providers:

- `LLM_PROVIDER=openai` avec `OPENAI_API_KEY`
- `LLM_PROVIDER=groq` avec `GROQ_API_KEY`
- `LLM_PROVIDER=local` avec Ollama et `LLM_LOCAL_MODEL`

## RAG

Le moteur RAG (`src/rag_engine.py`) enrichit le prompt avec des règles de nettoyage pertinentes.

Comportement:

- Si ChromaDB fonctionne, les règles sont stockées dans `data/chroma_db/`.
- Sinon, le système continue en mode mémoire.
- Les packs métier peuvent alimenter le contexte avec des exemples de règles par domaine.

Le dossier `data/chroma_db/` est ignoré par Git car il s'agit d'un état local régénérable.

## CAG

Le CAG (`src/cag_engine.py`) cache les plans de transformation à partir d'un hash du profil dataset:

- nombre de lignes;
- nombre de colonnes;
- noms/types de colonnes;
- bucket de valeurs manquantes;
- cardinalité.

Objectifs:

- éviter des appels LLM répétés sur des datasets similaires;
- réduire la latence;
- réduire le coût API;
- rendre les traitements plus stables.

Le cache disque `data/cag_cache/` est ignoré par Git.

## Règles métier

### Sales / CRM

Colonnes typiques:

- `order_id`
- `customer_name`
- `product`
- `price`
- `quantity`
- `order_date`
- `country`

Règles:

- dédoublonnage conservateur par `order_id`;
- trim des textes;
- noms clients invalides remplacés par `Unknown`;
- produits invalides remplacés par le mode;
- prix invalides ou négatifs convertis en `NaN`;
- quantités invalides converties en `NaN`;
- dates standardisées en `YYYY-MM-DD`;
- pays invalides remplacés par le mode.

### Logistics / Supply Chain

Colonnes typiques:

- `shipment_id`
- `origin`
- `destination`
- `weight`
- `shipping_cost`
- `delivery_date`
- `status`

Règles:

- protection de `shipment_id`;
- normalisation des villes, statuts et transporteurs;
- validation des poids et coûts;
- dates de livraison standardisées;
- conservation des valeurs sensibles en `NaN` plutôt que remplissage arbitraire.

### Generic

Quand aucun domaine n'est détecté:

- suppression très conservatrice des colonnes presque vides;
- normalisation des tokens manquants (`N/A`, `null`, `unknown`, etc.);
- trim et standardisation texte;
- conversion type seulement si le ratio de parsing est suffisant;
- marquage d'anomalies plutôt que suppression agressive.

## API

| Méthode | Route | Description |
| --- | --- | --- |
| `GET` | `/` | Accueil |
| `GET` | `/etl` | Interface ETL |
| `GET` | `/dashboard` | Dashboard du dernier rapport |
| `POST` | `/upload-and-process` | Upload et nettoyage |
| `GET` | `/last-report` | Dernier rapport en mémoire |
| `POST` | `/export-csv` | Export CSV du dernier run |
| `POST` | `/export-excel` | Export Excel du dernier run |
| `POST` | `/retrain-ml` | Réentraînement ML optionnel |

Exemple upload:

```bash
curl -F "file=@examples/sample_sales.csv" "http://127.0.0.1:8000/upload-and-process?domain_override=sales"
```

## Tests

```powershell
.venv\Scripts\python.exe -m pytest -q
```

Les tests actuels valident:

- import de l'application FastAPI;
- règles métier Sales;
- fallback LLM sans clé API;
- override de domaine.

## Données et Git

Le dépôt ne versionne pas:

- environnements virtuels;
- `node_modules`;
- uploads utilisateurs;
- exports nettoyés;
- caches RAG/CAG;
- gros datasets de test;
- rapports générés.

Les dossiers runtime sont conservés avec `.gitkeep`:

- `backend/uploads/`
- `data/in/`
- `data/processed/`
- `data/archive/`
- `reports/execution/`
- `reports/logs/`
- `reports/profiling/`

## Préparation avant push

```powershell
git status --short
.venv\Scripts\python.exe -m pytest -q
git add .
git commit -m "Clean and structure ETL platform repository"
```

Le repo est volontairement léger: le code, les modèles utiles, la config, le frontend et un exemple minimal restent versionnés; les artefacts volumineux sont exclus.
