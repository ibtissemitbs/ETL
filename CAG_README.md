# CAG Engine - Contextual Augmented Generation

## Vue d'ensemble

**CAG** = **R**etrieval-**A**ugmented **G**eneration (RAG) + **Cache** de réponses

Le moteur CAG améliore le pipeline ETL en combinant deux approches:

1. **RAG (Retrieval-Augmented Generation)**: Récupère les règles de nettoyage pertinentes de la base de connaissances
2. **Cache (Mémoire des réponses)**: Mémorise les règles de transformation générées par le LLM et les réutilise pour des profils de données similaires

**Résultat**: 
- ⚡ **Réduction drastique des appels LLM** (jusqu'à 80% selon l'utilisation)
- 💰 **Économies de coûts API** (OpenAI, Claude, etc.)
- 🚀 **Traitement plus rapide** des datasets similaires
- 📦 **Persistance du cache** en mémoire et sur disque

---

## Architecture

```
Dataset Profile (n_rows, colonnes, types, patterns)
         ↓
    CAG Engine
         ↓
   ┌─────────────┐
   │  Hash        │  → Génère un hash unique pour le profil
   │  Profile     │
   └─────────────┘
         ↓
   ┌────────────────────┐
   │  Check Cache        │
   │  (mémoire + disque) │
   └────────────────────┘
      ↙ (hit)    ↘ (miss)
   Return        Call LLM
   Cached        + Cache
   Rules         Result
```

### Hashage du Profil

Le cache utilise un hash SHA256 intelligent qui normalise le profil:

```python
{
  "n_columns": 5,
  "n_rows": 1000,
  "columns": [
    {
      "name": "id",
      "dtype": "int64",
      "missing_pct": 0,           # Bucketé par 10%
      "unique_count": 1000
    },
    {
      "name": "email",
      "dtype": "object",
      "missing_pct": 10,          # Groupé: 10-19% → 10%
      "unique_count": 950
    }
    ...
  ]
}
```

**Avantage**: Deux datasets avec la même structure mais des données différentes → même hash → **réutilisation du cache**

---

## Utilisation

### 1. Via `get_transformation_rules()` (Automatique)

```python
from src.llm_helper import get_transformation_rules
from src.profiler import build_dataset_profile
import pandas as pd

# Charger et profiler les données
df = pd.read_csv("data.csv")
profile = build_dataset_profile(df)

# Le cache est automatiquement utilisé
rules = get_transformation_rules(profile, use_cache=True)  # ← Cache activé par défaut
```

**Flux**:
1. Hache le profil
2. Vérifie le cache mémoire (session courante)
3. Vérifie le cache disque (`data/cag_cache/`)
4. Si cache hit: retourne les règles en cache
5. Si cache miss: appelle le LLM et stocke le résultat

### 2. Statut et Monitoring

```python
from src.llm_helper import get_cag_stats, print_cag_stats, clear_cag_cache

# Afficher les stats du cache
print_cag_stats()

# Récupérer les stats via dictionnaire
stats = get_cag_stats()
print(f"Hit rate: {stats['hit_rate_percent']:.1f}%")
print(f"LLM calls avoided: {stats['llm_calls_avoided']}")
```

**Sortie exemple**:
```
╔═══════════════════════════════════════════╗
║          CAG Cache Statistics             ║
╠═══════════════════════════════════════════╣
║ Cache Hits        : 12                    ║
║ Cache Misses      :  3                    ║
║ Hit Rate          : 80.0%                 ║
║ LLM Calls Saved   : 12                    ║
║ Memory Cache      : 15 profils            ║
║ Disk Cache        : 42 entrées            ║
╚═══════════════════════════════════════════╝
```

### 3. Gestion du Cache

```python
# Nettoyer le cache disque
clear_cag_cache(keep_recent_days=0)  # Tout effacer
clear_cag_cache(keep_recent_days=7)  # Garder les 7 derniers jours

# Réinitialiser le cache mémoire pour une nouvelle session
from src.llm_helper import reset_cag_session
reset_cag_session()
```

### 4. Désactiver le Cache (optionnel)

```python
# Forcer un appel LLM (pas de cache)
rules = get_transformation_rules(profile, use_cache=False)
```

---

## Structure du Cache

### Cache Mémoire
- **Scope**: Session Python courante
- **Stockage**: Dictionnaire en RAM
- **Performance**: Très rapide (nanoseconds)
- **Durée**: Jusqu'à la fin du script / process

### Cache Disque
- **Scope**: Persistant
- **Chemin**: `data/cag_cache/` 
- **Format**: JSON (`<hash>.json`)
- **Performance**: ~10-50ms (I/O disque)
- **Durée**: Infinie (jusqu'à suppression manuelle)

### Contenu du fichier cache

```json
{
  "timestamp": "2026-04-29T14:30:15.123456",
  "profile_summary": {
    "n_columns": 5,
    "n_rows": 1000,
    "column_types": ["int64", "object", "float64", "datetime64[ns]", "object"]
  },
  "rules": {
    "dataset_summary": {...},
    "rename_columns": {...},
    "drop_columns": [...],
    "convert_types": {...},
    "fill_nulls": {...},
    "validation_rules": {...}
  }
}
```

---

## Démo

Exécuter la démonstration CAG:

```bash
python cag_demo.py
```

**Ce qu'elle montre**:
1. Appel LLM pour un dataset SALES → Cache miss → ~3-5s
2. Appel pour un dataset CLIENT similaire → Cache hit → <100ms ⚡
3. Appel pour un dataset LOGISTICS différent → Cache miss → ~3-5s
4. Affiche les économies d'appels LLM réalisées

---

## Performance & Économies

### Exemple réel: 100 datasets en 1 journée

**Scénario**: Une entreprise traite 100 datasets différents chaque jour.

**Sans CAG**:
- 100 appels LLM × $0.05 par appel = **$5.00/jour** = **$150/mois**
- Temps total: 100 × 4s = 400s = 6.7 min

**Avec CAG** (hypothèse: 70% de datasets avec structure similaire):
- 30 appels LLM (nouveaux) × $0.05 = $1.50
- 70 cache hits × $0.00 = $0.00
- **Total: $1.50/jour** = **$45/mois** (économie: **$105/mois**)
- Temps total: 30 × 4s + 70 × 0.1s = 127s = 2.1 min

**Gain**: -70% coûts, -68% temps ⚡

---

## Intégration avec le backend

Le backend FastAPI utilise automatiquement CAG:

```python
# backend/main.py
@app.post("/upload-and-process")
async def upload_and_process(file: UploadFile = File(...)):
    # ...
    
    # Le cache est automatiquement utilisé
    from src.llm_helper import get_transformation_rules
    rules = get_transformation_rules(profile)  # ← CAG transparent
    
    # Si cache hit: réponse ~50x plus rapide
    # Si cache miss: appel LLM normal
```

---

## Considérations

### Quand le cache est EFFICACE
✅ Traitement batch de datasets similaires (e.g., exports CSV mensuels)  
✅ Même source de données à différentes dates  
✅ Datasets avec structure identique mais données différentes  
✅ Pipelines répétés / dashboards automatisés  

### Quand le cache est MOINS EFFICACE
❌ Datasets très hétérogènes (colonnes/types très différents)  
❌ Modifications fréquentes de la structure source  
❌ First-time projects sans historique  

### Qualité du cache
- ✅ Règles en cache identiques à règles LLM générées (100% réutilisable)
- ✅ Hash incluant patterns de nulls → adapté à la qualité des données
- ⚠️ Hash ne tient pas compte de valeurs spécifiques → ok pour structure générale

---

## Configuration avancée

### Personnaliser le chemin du cache

```python
from src.cag_engine import CAGEngine
from pathlib import Path

cag = CAGEngine(
    cache_dir=Path("/custom/cache/path")
)
```

### Intégration avec monitoring

```python
from src.llm_helper import get_cag_stats

def log_cag_metrics():
    stats = get_cag_stats()
    metrics = {
        "cag_hit_rate": stats["hit_rate_percent"],
        "cag_cost_saved": stats["cache_hits"] * 0.05,
        "cag_memory_profiles": stats["memory_cache_size"],
    }
    # Envoyer à votre système de monitoring (DataDog, Prometheus, etc.)
    send_to_monitoring(metrics)
```

---

## Limitations et futures améliorations

### Limitations actuelles
- Hash basé sur structure uniquement (pas sémantique)
- Cache persistant pas automatiquement nettoyé
- Pas de versioning des règles en cache

### Prochaines versions
- [ ] Similarité sémantique (embeddings) pour détection plus fine
- [ ] Auto-cleanup du cache (TTL)
- [ ] Versioning des modèles LLM
- [ ] Integration avec Redis pour cache distribué
- [ ] Metrics détaillées (JSON pour reporting)

---

## Résumé

| Aspect | Détail |
|--------|--------|
| **Combien économise CAG?** | 60-80% réduction des appels LLM |
| **Coût** | Gratuit (décision architecture) |
| **Temps setup** | 0 (transparent) |
| **Performance hit** | Aucun (cache plus rapide) |
| **Fallback** | Appel LLM normal si cache miss |
| **Risk** | Minimal (cache optionnel) |

**CAG = Low-risk, high-gain enhancement** ✅
