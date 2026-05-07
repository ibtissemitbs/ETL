# 🚀 PERFORMANCE TESTING GUIDE

Suite complète de tests de performance pour ETL / LLM / RAG

## 📋 Quick Start

### Option 1: Menu Interactif (Recommandé)
```bash
python test_menu.py
```

Choisissez parmi 6 options de tests avec interface interactive.

### Option 2: Suite Complète
```bash
python performance_tests.py
```

Exécute tous les tests avec rapport JSON détaillé.

### Option 3: Micro-Benchmarks
```bash
python micro_benchmarks.py
```

Tests détaillés avec `timeit` et `cProfile`.

---

## 🎯 Tests Disponibles

### 1️⃣ Full Performance Suite (`performance_tests.py`)

**Inclut 8 tests complets:**
- ✅ Extract Performance - Mesure l'extraction de données
- ✅ Profiler Performance - Analyse de profil des données  
- ✅ Transform Performance - Transformation et nettoyage
- ✅ Load Performance - Export CSV/Excel
- ✅ RAG Indexing - Indexation de documents
- ✅ RAG Queries - Performance des requêtes RAG
- ✅ LLM Performance - Test du LLM (nécessite API keys)
- ✅ Full Pipeline - Test E2E complet

**Métriques collectées pour chaque test:**
```
✅ Status                 - Succès/Échec
📊 Rows Processed        - Nombre de lignes traitées
⏱ Duration               - Temps d'exécution en secondes
📈 Throughput            - Lignes/sec (rows/sec)
💾 Memory Used           - Mémoire consommée (MB)
📍 Memory Peak           - Pic de mémoire (MB)
🖥 CPU Usage             - Utilisation CPU (%)
```

**Sortie:**
- Affichage temps réel en couleur dans VS Code
- Rapport JSON sauvegardé: `reports/execution/performance_report.json`

**Durée:** 2-5 minutes

---

### 2️⃣ Micro-Benchmarks (`micro_benchmarks.py`)

**Benchmarks précis avec `timeit`:**

#### DataFrame Operations (Pandas)
- Filtering: Temps pour filtrer des lignes
- Group By: Agrégation par groupes
- Fill NA: Remplissage des valeurs manquantes
- Merge: Fusion de DataFrames

#### Component Testing
- CSV Reading: Lecture de fichiers
- Data Cleaning: Transformation
- RAG Operations: Indexation et requêtes

#### Profiling (cProfile)
- Profil d'Extraction: Top 10 fonctions
- Profil de Transformation: Top 10 fonctions

**Durée:** 1-2 minutes

---

### 3️⃣ Quick ETL Test

Test rapide des 3 étapes: Extract → Transform → Load

```
⏱ Temps total
📊 Nombre de lignes
💾 Mémoire utilisée
```

**Durée:** 30 secondes

---

### 4️⃣ RAG Performance

- Indexation de 100 documents
- 20 requêtes (5 types × 4 répétitions)
- Temps moyen par requête

**Durée:** 1 minute

---

### 5️⃣ LLM Performance

- Exécute 3 prompts via LLM
- Temps par prompt
- Total temps d'exécution

**Durée:** 30 sec - 2 min (dépend de l'API)

**Prérequis:** Ajouter dans `.env`:
```
OPENAI_API_KEY=sk-...
# OU
GROQ_API_KEY=...
```

---

### 6️⃣ Memory Profiling

Profiling détaillé avec `tracemalloc`:
- Pic de mémoire
- Mémoire actuelle
- Allocation détaillée

**Durée:** 1 minute

---

## 📊 Métriques Expliquées

### ⏱ Duration
Temps d'exécution du test en secondes. Plus bas = mieux.

### 📈 Throughput
Nombre d'éléments traités par seconde.
```
Throughput = Rows / Duration
```
Plus élevé = mieux.

### 💾 Memory Used
Mémoire supplémentaire utilisée (différence start/end).

### 📍 Memory Peak
Pic de mémoire atteint pendant l'exécution.

### 🖥 CPU Usage
Pourcentage moyen d'utilisation CPU pendant le test.

---

## 🎨 Légende des Couleurs

```
🟢 GREEN  - Succès / Métriques
🔵 BLUE   - Timing / Duration
🟡 YELLOW - Mémoire / CPU
🔴 RED    - Erreurs
🔷 CYAN   - Titres / Sections
```

---

## 📁 Résultats & Rapports

### Fichiers Générés

```
reports/
├── execution/
│   └── performance_report.json   # Rapport JSON complet
├── logs/
└── profiling/
    └── (Profiling data si applicable)
```

### Format du Rapport JSON

```json
{
  "timestamp": "2026-04-20T14:30:45",
  "tests": [
    {
      "test_name": "Extract",
      "duration": 0.523,
      "memory_start": 145.2,
      "memory_end": 156.8,
      "memory_peak": 180.5,
      "cpu_percent": 45.3,
      "rows_processed": 1000,
      "throughput": 1911.28,
      "status": "OK"
    }
  ],
  "summary": {
    "total_duration": 15.234,
    "total_memory": 42.5,
    "avg_cpu": 42.1,
    "total_tests": 8
  }
}
```

---

## 🔧 Configuration

### Requirements

Installés automatiquement au premier lancement:
```
psutil         - Monitoring ressources
pandas         - DataFrame operations
numpy          - Calculs numériques
timeit         - Micro-timing
cProfile       - Profiling
tracemalloc    - Memory profiling
```

### Installation Manuelle

```bash
pip install psutil pandas numpy
```

---

## 💡 Tips & Tricks

### 1. Lancer un Test Spécifique
```bash
python -c "from performance_tests import test_extract_performance; test_extract_performance()"
```

### 2. Exporter les Résultats
Les rapports JSON sont sauvegardés automatiquement dans `reports/execution/`.

### 3. Comparer Résultats
Gardez les JSON de différentes exécutions pour comparer les performances dans le temps.

### 4. Tester avec Différentes Tailles
Modifiez les constantes dans les scripts pour tester avec différents volumes de données.

---

## 🐛 Troubleshooting

### "ModuleNotFoundError: No module named 'src'"
```bash
# Lancez depuis le répertoire racine du projet
cd c:\Users\LENOVO\Desktop\ETL
python performance_tests.py
```

### LLM Test Skip
Le test LLM est skippé si les API keys ne sont pas configurées. Ajoutez dans `.env`:
```
OPENAI_API_KEY=sk-your-key-here
```

### Résultats Anormaux
- Fermez les autres applications
- Relancez le test (les résultats peuvent varier)
- Vérifiez que le disque n'est pas saturé

---

## 📈 Interprétation des Résultats

### ✅ Bonnes Performances
- **Duration**: < 1 sec pour 1000 lignes
- **Throughput**: > 1000 rows/sec
- **Memory**: < 100 MB pour 10K lignes
- **CPU**: 20-60%

### ⚠️ À Optimiser
- **Duration**: > 5 sec pour 1000 lignes
- **Throughput**: < 200 rows/sec
- **Memory**: > 200 MB pour 10K lignes
- **CPU**: > 90%

---

## 🚀 Next Steps

1. **Run Full Suite**: `python test_menu.py` → Option 1
2. **Check Report**: Ouvrez `reports/execution/performance_report.json`
3. **Analyze Results**: Comparez avec les benchmarks
4. **Optimize**: Améliorez les composants lents
5. **Iterate**: Relancez pour valider les améliorations

---

## 📞 Notes

- Tous les tests sont **non-destructifs** (pas de modification des données)
- Les fichiers de test sont créés dans `data/processed/` avec préfixe `perf_test_`
- Les résultats peuvent varier selon:
  - Charge système
  - Taille du disque disponible
  - Autres applications en cours
  - Configuration matérielle

---

**Créé:** 2026-04-20  
**Version:** 1.0.0  
**ETL Platform Performance Testing Suite**
