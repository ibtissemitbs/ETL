"""
RAG Engine - Retrieval-Augmented Generation pour ETL Rules
Stocke et récupère les règles de nettoyage basées sur similarité avec le dataset profil
"""

import json
import os
import warnings
from pathlib import Path
from typing import Any, Dict, List, Optional

# Try to import ChromaDB - graceful fallback if not available
try:
    import chromadb
    from chromadb.config import Settings

    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False
    chromadb = None
    Settings = None
    warnings.warn(
        "ChromaDB not available. RAG Engine will operate in simulation mode. "
        "Install it with: pip install chromadb",
        ImportWarning,
    )

# Initialiser ChromaDB si disponible
chroma_client = None
if CHROMADB_AVAILABLE:
    try:
        CHROMA_DB_PATH = Path(__file__).parent.parent / "data" / "chroma_db"
        CHROMA_DB_PATH.mkdir(parents=True, exist_ok=True)

        # Client ChromaDB avec persistance
        chroma_client = chromadb.Client(
            Settings(
                chroma_db_impl="duckdb+parquet",
                persist_directory=str(CHROMA_DB_PATH),
                anonymized_telemetry=False,
            )
        )
    except Exception as e:
        warnings.warn(
            f"ChromaDB initialization failed: {e}. RAG Engine will operate in simulation mode.",
            RuntimeWarning,
        )
        chroma_client = None
        CHROMADB_AVAILABLE = False

# Collection pour les règles ETL
ETL_RULES_COLLECTION = "etl_cleaning_rules"


class RAGEngine:
    """Moteur RAG pour gérer les règles de nettoyage ETL"""

    def __init__(self):
        """Initialise le RAG engine"""
        self.client = chroma_client
        self.collection = self._get_or_create_collection()
        # Fallback: store rules in memory if ChromaDB not available
        self._memory_rules = {}
        # Load domain packs from data/rag_rules if present
        try:
            self._load_domain_packs()
        except Exception:
            pass

    def _get_or_create_collection(self):
        """Crée ou récupère la collection ChromaDB"""
        if not CHROMADB_AVAILABLE or self.client is None:
            return None

        try:
            # Essayer de récupérer la collection existante
            collection = self.client.get_collection(name=ETL_RULES_COLLECTION)
        except (ValueError, AttributeError):
            # Créer une nouvelle collection si elle n'existe pas
            try:
                collection = self.client.create_collection(
                    name=ETL_RULES_COLLECTION,
                    metadata={"hnsw:space": "cosine"},
                )
            except Exception:
                collection = None
        except Exception:
            collection = None

        return collection

    def add_cleaning_rule(
        self,
        rule_id: str,
        rule_name: str,
        rule_description: str,
        rule_content: Dict[str, Any],
        tags: List[str],
        domain: str = "general",
    ) -> None:
        """
        Ajoute une règle de nettoyage à la base vectorielle

        Args:
            rule_id: Identifiant unique de la règle
            rule_name: Nom de la règle
            rule_description: Description détaillée
            rule_content: Le contenu JSON de la règle (transformations)
            tags: Tags pour la recherche (ex: ["email", "normalization"])
        """
        # Texte à embédifier
        text = f"""
Rule: {rule_name}
Description: {rule_description}
Tags: {', '.join(tags)}
Content: {json.dumps(rule_content, ensure_ascii=False)}
        """

        # Store in memory
        self._memory_rules[rule_id] = {
            "rule": text,
            "metadata": {
                "rule_name": rule_name,
                "tags": ",".join(tags),
                "rule_type": tags[0] if tags else "general",
                "domain": domain,
            },
        }

        # Ajouter à ChromaDB si disponible
        if self.collection is not None:
            try:
                self.collection.add(
                    ids=[rule_id],
                    documents=[text],
                    metadatas=[
                        {
                            "rule_name": rule_name,
                            "tags": ",".join(tags),
                            "rule_type": tags[0] if tags else "general",
                            "domain": domain,
                        }
                    ],
                )
            except Exception as e:
                print(f"[WARNING] Could not add rule to ChromaDB: {e}")

    def retrieve_rules(
        self, profile: Dict[str, Any], top_k: int = 3, domain: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Récupère les règles pertinentes basées sur le profil du dataset

        Args:
            profile: Profil du dataset (sortie du profiler)
            top_k: Nombre de règles à récupérer

        Returns:
            Liste des règles pertinentes
        """
        # If ChromaDB available, use it
        target_domain = (
            (domain or _extract_domain_from_profile(profile)).strip().lower()
        )

        if self.collection is not None:
            try:
                # Construire un query text basé sur le profil
                query_text = self._build_query_from_profile(profile)

                where_clause = None
                if target_domain and target_domain != "generic":
                    where_clause = {"domain": target_domain}

                # Rechercher les règles similaires
                results = self.collection.query(
                    query_texts=[query_text],
                    n_results=top_k,
                    where=where_clause,
                )

                # Formatter les résultats
                relevant_rules = []
                if (
                    results
                    and results["documents"]
                    and len(results["documents"][0]) > 0
                ):
                    for i, doc in enumerate(results["documents"][0]):
                        relevant_rules.append(
                            {
                                "rule": doc,
                                "metadata": results["metadatas"][0][i],
                                "distance": (
                                    results["distances"][0][i]
                                    if results["distances"]
                                    else 0
                                ),
                            }
                        )
                return relevant_rules
            except Exception as e:
                print(f"[WARNING] ChromaDB query failed: {e}, falling back to memory")

        # Fallback: return rules from memory
        if self._memory_rules:
            relevant_rules = []
            for rule_id, rule_data in list(self._memory_rules.items()):
                rule_domain = str(
                    rule_data.get("metadata", {}).get("domain", "")
                ).lower()
                if target_domain and target_domain != "generic":
                    if rule_domain and rule_domain != target_domain:
                        continue
                relevant_rules.append(
                    {
                        "rule": rule_data["rule"],
                        "metadata": rule_data["metadata"],
                        "distance": 0.0,
                    }
                )
                if len(relevant_rules) >= top_k:
                    break
            return relevant_rules

        return []

    def _build_query_from_profile(self, profile: Dict[str, Any]) -> str:
        """Construit un query text partir du profil du dataset"""
        query_parts = []
        column_types = []

        # Analyser les colonnes et leurs types
        if "schema" in profile:
            for col in profile["schema"]:
                col_type = col.get("type", "unknown")
                col_name = col.get("name", "")
                nulls = col.get("nulls", 0)

                column_types.append(col_type)

                # Ajouter des tags basés sur les problèmes détectés
                if nulls > 20:
                    query_parts.append("missing values")
                if col_type == "string":
                    query_parts.append("text normalization")
                if col_type == "datetime":
                    query_parts.append("date formatting")
                if "email" in col_name.lower():
                    query_parts.append("email validation")
                if "phone" in col_name.lower():
                    query_parts.append("phone standardization")

        # Ajouter infos du dataset
        if "dataset" in profile:
            rows = profile["dataset"].get("rows", 0)
            if rows > 10000:
                query_parts.append("large dataset")

        # Construire le query text
        query_text = f"""
        Dataset profile analysis:
        Column types found: {', '.join(column_types) if column_types else 'unknown'}
        Issues to address: {', '.join(query_parts) if query_parts else 'general cleaning'}
        """

        return query_text

    def get_augmented_prompt(
        self, profile: Dict[str, Any], top_k: int = 3, domain: Optional[str] = None
    ) -> str:
        """
        Génère un prompt augmenté avec les règles pertinentes

        Args:
            profile: Profil du dataset
            top_k: Nombre de règles à inclure

        Returns:
            Prompt augmenté
        """
        relevant_rules = self.retrieve_rules(profile, top_k=top_k, domain=domain)

        if not relevant_rules:
            return ""

        # Formatter les règles
        rules_text = "## RELEVANT ETL RULES FROM KNOWLEDGE BASE\n\n"

        for i, rule_info in enumerate(relevant_rules, 1):
            rules_text += (
                f"### Rule {i}: {rule_info['metadata'].get('rule_name', 'Unknown')}\n"
            )
            rules_text += f"{rule_info['rule']}\n\n"

        augmented_prompt = f"""
You have access to the following relevant ETL rules from our knowledge base.
Use these examples to guide your transformation decisions:

{rules_text}

Apply these patterns to the current dataset profile where applicable.
"""
        return augmented_prompt

    def persist(self) -> None:
        """Persiste la base de données ChromaDB"""
        if self.client is not None and hasattr(self.client, "persist"):
            try:
                self.client.persist()
            except Exception as e:
                print(f"[WARNING] Could not persist ChromaDB: {e}")

    def _load_domain_packs(self) -> None:
        """Load JSON domain packs from data/rag_rules and add them to memory rules."""
        try:
            base = Path(__file__).parent.parent
            packs_dir = base / "data" / "rag_rules"
            if not packs_dir.exists():
                return

            for path in sorted(packs_dir.glob("*.json")):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        content = json.load(f)
                        domain = _extract_domain_from_payload(content) or "generic"

                        # New format: file contains a list of rules with domain metadata
                        if isinstance(content.get("rules"), list):
                            for idx, rule in enumerate(content.get("rules") or []):
                                if not isinstance(rule, dict):
                                    continue
                                rule_domain = str(rule.get("domain") or domain).lower()
                                rule_name = (
                                    rule.get("rule")
                                    or rule.get("problem")
                                    or f"{path.stem}-{idx}"
                                )
                                rid = rule.get("rule_id") or f"{path.stem}_{idx}"
                                tags = (
                                    [rule_domain, rule.get("column_role", "domain")]
                                    if rule_domain
                                    else ["domain"]
                                )
                                text = "\n".join(
                                    [
                                        f"Rule: {rule_name}",
                                        f"Domain: {rule_domain}",
                                        f"Column role: {rule.get('column_role', 'unknown')}",
                                        f"Problem: {rule.get('problem', '')}",
                                        f"Action: {rule.get('action', '')}",
                                        f"Severity: {rule.get('severity', '')}",
                                    ]
                                )

                                self._memory_rules[rid] = {
                                    "rule": text,
                                    "metadata": {
                                        "rule_name": rule_name,
                                        "tags": ",".join([t for t in tags if t]),
                                        "rule_type": rule.get("column_role", "domain"),
                                        "domain": rule_domain,
                                    },
                                }
                            continue

                        rid = content.get("rule_id") or path.stem
                        name = content.get("rule_name", path.stem)
                        description = content.get("rule_description", "domain pack")
                        tags = content.get("tags", [])
                        rule_content = content.get(
                            "rule_content", content.get("rules", {})
                        )

                        text = f"Rule: {name}\nDescription: {description}\nTags: {', '.join(tags)}\nContent: {json.dumps(rule_content, ensure_ascii=False)}"

                        self._memory_rules[rid] = {
                            "rule": text,
                            "metadata": {
                                "rule_name": name,
                                "tags": ",".join(tags),
                                "rule_type": tags[0] if tags else "domain",
                                "domain": domain,
                            },
                        }
                except Exception:
                    continue
        except Exception:
            return


def _extract_domain_from_profile(profile: Dict[str, Any]) -> str:
    context = (
        profile.get("domain_context")
        if isinstance(profile.get("domain_context"), dict)
        else {}
    )
    domain = str(context.get("domain", "")).strip().lower()
    return domain or "generic"


def _extract_domain_from_payload(payload: Dict[str, Any]) -> str:
    raw = str(payload.get("domain", "")).strip().lower()
    if raw:
        return raw
    tags = payload.get("tags", []) if isinstance(payload.get("tags"), list) else []
    for tag in tags:
        if str(tag).lower() in {"sales", "logistics"}:
            return str(tag).lower()
    return ""


def initialize_rag_with_examples() -> None:
    """Initialise la base RAG avec des règles d'exemples"""
    try:
        rag = RAGEngine()

        # Vérifier si des règles existent déjà
        try:
            if rag.collection is not None:
                existing = rag.collection.count()
                if existing > 0:
                    return  # Les règles existent déjà
        except Exception:
            pass  # If collection check fails, continue with adding rules

        # RÈGLE 1: Email Standardization
        rag.add_cleaning_rule(
            rule_id="rule_email_001",
            rule_name="Email Standardization",
            rule_description="Standardize email addresses: lowercase, trim spaces",
            rule_content={"action": "standardize_email"},
            tags=["email", "validation", "normalization"],
        )

        # RÈGLE 2: Phone Standardization
        rag.add_cleaning_rule(
            rule_id="rule_phone_001",
            rule_name="Phone Standardization",
            rule_description="Standardize phone numbers to XXX-XXXX format",
            rule_content={"action": "standardize_phone"},
            tags=["phone", "standardization", "validation"],
        )

        # RÈGLE 3: Date Standardization
        rag.add_cleaning_rule(
            rule_id="rule_date_001",
            rule_name="Date Standardization",
            rule_description="Convert dates to ISO format (YYYY-MM-DD)",
            rule_content={"action": "standardize_date"},
            tags=["date", "datetime", "formatting"],
        )

        # RÈGLE 4: Handle Missing Values
        rag.add_cleaning_rule(
            rule_id="rule_nulls_001",
            rule_name="Handle Missing Values",
            rule_description="Fill null values with median/mode based on column type",
            rule_content={"action": "fill_nulls"},
            tags=["missing values", "null handling", "imputation"],
        )

        # RÈGLE 5: Deduplication
        rag.add_cleaning_rule(
            rule_id="rule_dedup_001",
            rule_name="Deduplication Strategy",
            rule_description="Remove exact and partial duplicates",
            rule_content={"action": "remove_duplicates"},
            tags=["deduplication", "duplicates"],
        )

        # RÈGLE 6: Text Cleaning
        rag.add_cleaning_rule(
            rule_id="rule_text_001",
            rule_name="Text Cleaning and Normalization",
            rule_description="Clean text: title case, trim whitespace",
            rule_content={"action": "normalize_text"},
            tags=["text", "normalization", "cleanup"],
        )

        # RÈGLE 7: Column Merging
        rag.add_cleaning_rule(
            rule_id="rule_merge_001",
            rule_name="Similar Column Merging",
            rule_description="Merge columns with similar names",
            rule_content={"action": "merge_similar_columns"},
            tags=["column merging", "rename", "consolidation"],
        )

        # RÈGLE 8: Outlier Detection
        rag.add_cleaning_rule(
            rule_id="rule_outliers_001",
            rule_name="Outlier Detection and Handling",
            rule_description="Detect and remove outliers using IQR method",
            rule_content={"action": "remove_outliers"},
            tags=["outliers", "validation", "data quality"],
        )

        # RÈGLE 9: Type Conversion
        rag.add_cleaning_rule(
            rule_id="rule_types_001",
            rule_name="Automatic Type Detection",
            rule_description="Detect and convert columns to appropriate types",
            rule_content={"action": "convert_types"},
            tags=["type conversion", "type inference", "data types"],
        )

        # RÈGLE 10: Full Pipeline
        rag.add_cleaning_rule(
            rule_id="rule_cascade_001",
            rule_name="Full ETL Cascade Pipeline",
            rule_description="Complete ETL pipeline with all steps",
            rule_content={"action": "full_cascade"},
            tags=["pipeline", "cascade", "full cleaning"],
        )

        rag.persist()

        # Display status
        rule_count = 0
        try:
            if rag.collection is not None:
                rule_count = rag.collection.count()
            else:
                rule_count = len(rag._memory_rules)
        except Exception:
            rule_count = len(rag._memory_rules)

        status = (
            "[OK] RAG Engine initialized"
            if CHROMADB_AVAILABLE
            else "[WARN] RAG Engine (simulation mode)"
        )
        print(f"{status} with {rule_count} rules")

    except Exception as e:
        print(f"[WARN] RAG initialization error: {e}")


# Initialiser au démarrage du module
try:
    if CHROMADB_AVAILABLE:
        initialize_rag_with_examples()
    else:
        print(
            "[WARN] ChromaDB not available - RAG Engine will use in-memory simulation mode"
        )
except Exception as e:
    print(f"[WARN] Error during RAG initialization: {e}")
