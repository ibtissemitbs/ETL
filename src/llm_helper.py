import json
import logging
import os
import shlex
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional

import requests
from openai import OpenAI
from requests.exceptions import RequestException

from .cag_engine import get_cag_engine
from .domain_context import format_domain_context
from .hybrid_ml import get_hybrid_ml_service
from .rag_engine import RAGEngine


logger = logging.getLogger(__name__)

LLM_SYSTEM_PROMPT = """
You are a SAFE data quality planning assistant for an automated ETL pipeline.

Your task is to analyze a dataset profile and produce a CONSERVATIVE cleaning plan.
The LLM is NOT allowed to directly modify data. It must only generate a JSON plan.
All transformations will be validated and executed later by a deterministic rules engine.

CRITICAL SAFETY RULES:
1. Never replace missing numeric business values with 0.
2. Never convert price, quantity, weight, shipping_cost, amount, cost, total, or revenue to datetime.
3. Never drop important business columns.
4. Never rename columns.
5. Never compute sums, totals, averages, aggregations, groupby, or derived metrics unless explicitly requested by the user.
6. Never delete rows without a deterministic reason.
7. Preserve identifiers such as id, order_id, shipment_id, tracking_id, code, reference, uuid.
8. For price, quantity, weight, and shipping_cost: invalid, empty, non-numeric, or negative values must be marked as anomalies and converted to NaN by the rules engine.
9. Missing price, quantity, weight, and shipping_cost should remain NaN, not imputed automatically.
10. Use fill_missing only for safe categorical columns such as customer_name, country, product, origin, destination, or status.

Allowed actions only:
- fill_missing
- convert_type
- standardize_date
- remove_duplicate
- mark_as_anomaly
- reject_row

Dataset-specific guidance:
- Sales columns: order_id, customer_name, product, price, quantity, order_date, country.
  * order_id is protected and used for duplicate detection.
  * price and quantity are numeric business columns; never convert them to datetime and never fill them with 0.
  * negative price or invalid quantity must be marked as anomaly.
- Logistics columns: shipment_id, origin, destination, weight, shipping_cost, delivery_date, status.
  * shipment_id is protected and used for duplicate detection.
  * weight and shipping_cost are numeric business columns; never convert them to datetime and never fill them with 0.
  * negative weight or shipping_cost must be marked as anomaly.

JSON structure (STRICT - no markdown, no explanations):
{
    "dataset_summary": {
    "dataset_type": "sales|logistics|generic",
        "general_quality": "low|medium|high",
        "critical_issues": ["issue1", "issue2"],
        "notes": ["observation1", "observation2"]
    },
    "plan": [
        {
            "column": "column_name",
            "problem": "specific issue description",
            "action": "fill_missing|convert_type|standardize_date|remove_duplicate|mark_as_anomaly|reject_row",
            "confidence": 0.85,
            "priority": "high|medium|low"
        }
    ]
}

Good examples:
- price with abc/invalid/negative values -> convert_type + mark_as_anomaly, not fill_missing with 0.
- shipping_cost with negative values -> convert_type + mark_as_anomaly, not abs() and not 0.
- delivery_date or order_date with mixed date formats -> standardize_date.
- order_id or shipment_id with duplicates -> remove_duplicate.

Return ONLY the JSON object.
"""

_ALLOWED_PLAN_ACTIONS = {
    "fill_missing",
    "convert_type",
    "standardize_date",
    "remove_duplicate",
    "mark_as_anomaly",
    "reject_row",
}


def _load_project_llm_settings() -> Dict[str, Any]:
    settings_path = Path(__file__).parent.parent / "config" / "settings.json"
    try:
        if settings_path.exists():
            with open(settings_path, "r", encoding="utf-8") as fh:
                settings = json.load(fh)
                if isinstance(settings, dict):
                    llm_settings = settings.get("llm", {})
                    if isinstance(llm_settings, dict):
                        return llm_settings
    except Exception:
        pass
    return {}


def _is_identifier_like_column_name(column_name: str) -> bool:
    lowered = str(column_name).lower()
    if lowered == "id" or lowered.endswith("_id") or lowered.startswith("id_"):
        return True
    return any(
        token in lowered
        for token in [
            "code",
            "ref",
            "reference",
            "identifier",
            "uuid",
            "passeport",
            "order_id",
            "orderid",
            "order id",
        ]
    )




def _is_business_numeric_column_name(column_name: str) -> bool:
    lowered = str(column_name).strip().lower()
    return any(
        token in lowered
        for token in [
            "price",
            "quantity",
            "qty",
            "weight",
            "shipping_cost",
            "amount",
            "cost",
            "total",
            "revenue",
        ]
    )


def _is_date_like_column_name(column_name: str) -> bool:
    lowered = str(column_name).strip().lower()
    return any(token in lowered for token in ["date", "time", "created", "updated", "timestamp"])

def _get_column_profile(profile: Dict[str, Any], column_name: str) -> Dict[str, Any]:
    for column in profile.get("columns", []):
        if column.get("name") == column_name:
            return column
    return {}


def _sanitize_transformation_rules(
    profile: Dict[str, Any], rules: Dict[str, Any]
) -> Dict[str, Any]:
    """Normalize raw LLM output into a plan-only schema."""
    if not isinstance(rules, dict):
        return {"dataset_summary": {}, "plan": []}

    schema_columns = {
        col.get("name") for col in profile.get("columns", []) if col.get("name")
    }
    safe_plan: List[Dict[str, Any]] = []

    def _append_plan_item(
        column: str, problem: str, action: str, confidence: Any
    ) -> None:
        if action not in _ALLOWED_PLAN_ACTIONS:
            return
        if column and column not in schema_columns and column != "__dataset__":
            return

        column_profile = _get_column_profile(profile, column) if column in schema_columns else {}
        problem_text = str(problem).strip() or "unspecified issue"
        problem_lower = problem_text.lower()

        # Protect identifiers: only duplicate/anomaly marking is allowed.
        if column != "__dataset__" and _is_identifier_like_column_name(column):
            if action not in {"remove_duplicate", "mark_as_anomaly"}:
                return

        # Protect business numeric fields from dangerous LLM actions.
        if column != "__dataset__" and _is_business_numeric_column_name(column):
            # Never fill numeric business values through LLM plan. Missing values stay NaN.
            if action == "fill_missing":
                return
            # Never standardize/convert business numeric columns as dates.
            if action == "standardize_date":
                return
            if action == "convert_type" and any(token in problem_lower for token in ["date", "datetime", "timestamp"]):
                return

        # Only allow standardize_date for explicit date-like columns.
        if action == "standardize_date" and column != "__dataset__":
            if not _is_date_like_column_name(column):
                return

        try:
            score = float(confidence)
        except Exception:
            score = 0.5
        score = max(0.0, min(1.0, score))

        safe_plan.append(
            {
                "column": column,
                "problem": problem_text,
                "action": action,
                "confidence": round(score, 4),
            }
        )

    raw_plan = rules.get("plan") or []
    if isinstance(raw_plan, list):
        for item in raw_plan:
            if not isinstance(item, dict):
                continue
            _append_plan_item(
                str(item.get("column", "")).strip(),
                str(item.get("problem", "")).strip(),
                str(item.get("action", "")).strip().lower(),
                item.get("confidence", 0.5),
            )

    legacy_rules = (
        rules.get("legacy_rules")
        if isinstance(rules.get("legacy_rules"), dict)
        else rules
    )
    for column_name, target_type in (legacy_rules.get("convert_types") or {}).items():
        if column_name in schema_columns:
            action = (
                "standardize_date"
                if str(target_type).lower() == "datetime"
                else "convert_type"
            )
            _append_plan_item(
                column_name, f"type should become {target_type}", action, 0.72
            )

    for column_name in (legacy_rules.get("fill_nulls") or {}).keys():
        if column_name in schema_columns:
            _append_plan_item(
                column_name, "missing values detected", "fill_missing", 0.8
            )

    deduplication = legacy_rules.get("deduplication") or {}
    if deduplication.get("remove_duplicates"):
        subset = deduplication.get("subset") or []
        column = subset[0] if subset else "__dataset__"
        _append_plan_item(
            column, "duplicate rows or keys detected", "remove_duplicate", 0.74
        )

    for column_name, rule_value in (legacy_rules.get("validation_rules") or {}).items():
        if column_name in schema_columns and isinstance(rule_value, dict):
            rule_type = str(rule_value.get("type", "")).lower()
            if rule_type in {"range", "past_date", "allowed_values"}:
                _append_plan_item(
                    column_name,
                    f"validation rule: {rule_type}",
                    "mark_as_anomaly",
                    0.68,
                )

    seen = set()
    deduped_plan: List[Dict[str, Any]] = []
    for item in safe_plan:
        key = (item["column"], item["problem"], item["action"])
        if key in seen:
            continue
        seen.add(key)
        deduped_plan.append(item)

    deduped_plan.sort(key=lambda item: item.get("confidence", 0), reverse=True)

    return {
        "dataset_summary": rules.get("dataset_summary", {}),
        "plan": deduped_plan,
    }


def build_user_prompt(profile: Dict[str, Any], dataframe: Optional[Any] = None) -> str:
    """
    Construit le prompt utilisateur a partir du profil du dataset.
    Augmente le prompt avec les règles pertinentes du RAG.
    """
    domain_hint = None
    if isinstance(profile.get("domain_context"), dict):
        domain_hint = profile.get("domain_context", {}).get("domain")

    ml_service = get_hybrid_ml_service(domain=domain_hint)
    ml_context = ml_service.build_llm_context(profile, dataframe=dataframe)
    domain_context = format_domain_context(profile, dataframe=dataframe)
    row_count = int(profile.get("n_rows", 0) or 0)
    volume_hint = ""
    if row_count >= 100000:
        volume_hint = (
            "\nLarge dataset detected: use conservative, batch-safe rules only. "
            "Prefer normalization, text cleanup, validation, and deduplication. Avoid destructive type conversions."
        )

    # Récupérer les règles pertinentes du RAG
    rag = RAGEngine()
    augmented_rules = rag.get_augmented_prompt(profile, top_k=3, domain=domain_hint)

    # Load few-shot examples if available
    examples_text = ""
    try:
        examples_path = Path(__file__).parent.parent / "config" / "prompt_examples.json"
        if examples_path.exists():
            with open(examples_path, "r", encoding="utf-8") as ef:
                ex = json.load(ef)
                for i, e in enumerate(ex.get("examples", []), 1):
                    example_json = json.dumps(
                        e.get("example_json", {}), ensure_ascii=False, indent=2
                    )
                    examples_text += f"### Example {i}: {e.get('profile_hint', '')}\n{example_json}\n\n"
    except Exception:
        examples_text = ""

    base_prompt = f"""
Analyze the following dataset profile and generate a JSON ETL cleaning plan.

Return a STRICT JSON object with a dataset_summary and a plan list.

Plan item requirements:
- Use only these actions: fill_missing, convert_type, standardize_date, remove_duplicate, mark_as_anomaly, reject_row
- Never rename columns
- Never correct values directly
- Never calculate sums or derived metrics
- Never drop columns
- Never delete rows without a deterministic reason

Important safety note:
- Preserve business identifiers and keys.
- Never convert identifier-like columns to numeric or datetime.
- Never convert price, quantity, weight, shipping_cost, amount, cost, total, or revenue to datetime.
- Never replace missing numeric business values with 0.
- For price, quantity, weight, shipping_cost: invalid, empty, non-numeric, or negative values must become NaN after deterministic validation.
- Use fill_missing only for safe categorical fields, not for price, quantity, weight, or shipping_cost.
- Only suggest type conversions when the evidence is strong.
- Avoid destructive actions on large datasets.
{volume_hint}

Dataset profile:
{json.dumps(profile, indent=2, ensure_ascii=False)}

Domain context (business):
{domain_context}

ML guidance (signals):
{ml_context}

Relevant examples from knowledge base (RAG):
{augmented_rules}

Few-shot examples:
{examples_text}

Return ONLY the JSON object.
"""

    return base_prompt


def get_llm_client(provider: str = "openai") -> OpenAI:
    """
    Cree le client OpenAI a partir de la cle API dans les variables d'environnement.
    """
    provider_key = str(provider or "openai").strip().lower()
    if provider_key == "groq":
        api_key = os.getenv("GROQ_API_KEY") or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError(
                "GROQ_API_KEY introuvable dans les variables d'environnement."
            )
        return OpenAI(
            api_key=api_key,
            base_url=os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1"),
            timeout=30,
        )

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError(
            "OPENAI_API_KEY introuvable dans les variables d'environnement."
        )

    return OpenAI(api_key=api_key, timeout=30)


def _call_local_ollama(prompt: str, model: str = "llama2") -> str:
    """Try to call a local Ollama instance (HTTP preferred, since CLI can timeout on long prompts).

    Returns the raw text output from the model.
    """
    # First try HTTP API (default Ollama port) — best for long prompts
    logger.info(f"Trying Ollama HTTP API (model={model})...")
    try:
        url = os.getenv("OLLAMA_API_URL", "http://127.0.0.1:11434/api/generate")
        payload = {"model": model, "prompt": prompt, "stream": False}
        resp = requests.post(
            url, json=payload, timeout=180
        )  # Allow 3 min for generation
        if resp.ok:
            try:
                j = resp.json()
                # Ollama HTTP API may return different shapes; prefer a textual field
                if isinstance(j, dict):
                    # common keys: 'response', 'text', 'output', 'result'
                    for k in ("response", "text", "output", "result"):
                        if k in j:
                            return (
                                j[k]
                                if isinstance(j[k], str)
                                else json.dumps(j[k], ensure_ascii=False)
                            )
                # If no recognized key, try the full response
                return json.dumps(j, ensure_ascii=False) if j else resp.text
            except Exception as e:
                logger.warning(f"HTTP response parse failed: {e}, returning raw text")
                return resp.text
        else:
            logger.warning(f"HTTP request failed: {resp.status_code} {resp.text[:200]}")
    except Exception as e:
        logger.warning(f"Ollama HTTP API failed: {e}")

    # Fallback: try CLI with a shorter timeout or simplified prompt
    logger.info("Fallback: trying Ollama CLI...")
    try:
        # For CLI, use stdin (less prone to argument issues)
        proc = subprocess.run(
            ["ollama", "run", model],
            input=prompt,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=180,
        )
        if proc.returncode == 0:
            return proc.stdout.strip()
        else:
            logger.warning(
                f"Ollama CLI returned code {proc.returncode}: {proc.stderr[:200]}"
            )
    except FileNotFoundError:
        logger.warning("Ollama CLI not found")
    except subprocess.TimeoutExpired:
        logger.warning("Ollama CLI timed out after 180s")
    except Exception as e:
        logger.warning(f"Ollama CLI failed: {e}")

    # Both HTTP and CLI failed
    raise RuntimeError("Local Ollama not reachable via HTTP API or CLI")


def get_transformation_rules(
    profile: Dict[str, Any],
    model: str = "gpt-4o-mini",
    use_cache: bool = True,
    dataframe: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Récupère les règles de transformation pour un profil de dataset.
    Utilise CAG (cache) pour éviter les appels LLM redondants.
    Fallback: applique les règles domain pack si LLM échoue.

    Args:
        profile: Profil du dataset
        model: Modèle LLM à utiliser
        use_cache: Activer le cache CAG (défaut: True)
        dataframe: DataFrame optionnel pour contextualisation

    Returns:
        Règles de transformation (du cache, du LLM, ou des fallback)
    """
    # Vérifier le cache CAG d'abord
    if use_cache:
        cag = get_cag_engine()
        cached_rules = cag.get_cached_rules(profile)
        if cached_rules is not None:
            logger.info("📦 Règles récupérées du cache CAG - Appel LLM évité!")
            return cached_rules

    row_count = int(getattr(dataframe, "shape", (profile.get("n_rows", 0) or 0,))[0])
    if row_count >= 50000:
        logger.info(
            "⚠️ Large dataset detected (%s rows) - skipping LLM call and using fallback rules immediately",
            row_count,
        )
        rules = _generate_fallback_rules(profile, dataframe=dataframe)
        rules = _sanitize_transformation_rules(profile, rules)
        if use_cache:
            cag = get_cag_engine()
            cag.cache_rules(profile, rules)
            logger.info("💾 Fallback rules cached for reuse")
        return rules

    # Cache miss → appel LLM (provider selectable via LLM_PROVIDER)
    project_settings = _load_project_llm_settings()
    provider = os.getenv(
        "LLM_PROVIDER", str(project_settings.get("provider", "openai"))
    ).lower()
    if provider == "groq" and not (
        os.getenv("GROQ_API_KEY") or os.getenv("OPENAI_API_KEY")
    ):
        logger.info(
            "⚠️ GROQ provider configured but no API key found - using fallback rules"
        )
        rules = _generate_fallback_rules(profile, dataframe=dataframe)
        rules = _sanitize_transformation_rules(profile, rules)
        if use_cache:
            cag = get_cag_engine()
            cag.cache_rules(profile, rules)
            logger.info("💾 Fallback rules cached for reuse")
        return rules
    logger.info(
        f"🤖 Appel LLM provider={provider} pour générer les règles de transformation..."
    )
    user_prompt = build_user_prompt(profile, dataframe=dataframe)

    content = None

    try:
        if provider in ("local", "ollama"):
            # Use local Ollama (HTTP or CLI)
            local_model = os.getenv("LLM_LOCAL_MODEL", model)
            try:
                content = _call_local_ollama(user_prompt, model=local_model)
            except Exception as e:
                logger.warning(
                    f"Local LLM call failed: {e} - will use domain pack fallback"
                )
                content = None

        elif provider == "openai":
            logger.info("Using OpenAI provider")
            client = get_llm_client(provider=provider)
            response = client.chat.completions.create(
                model=model,
                temperature=0,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": LLM_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
            )
            content = response.choices[0].message.content

        elif provider == "groq":
            logger.info("Using Groq-compatible OpenAI client")
            client = get_llm_client(provider=provider)
            response = client.chat.completions.create(
                model=os.getenv("GROQ_MODEL", model),
                temperature=0,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": LLM_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
            )
            content = response.choices[0].message.content

        else:
            raise ValueError(f"Unsupported LLM_PROVIDER: {provider}")

    except Exception as e:
        logger.warning(
            f"LLM provider {provider} failed: {e} - will use domain pack fallback"
        )
        content = None

    # Try to extract JSON part: prompts ask for RATIONALE then JSON
    if content:
        try:
            # If content already JSON string, load directly
            if isinstance(content, (dict, list)):
                rules = content
            else:
                text = str(content).strip()
                # Find first '{' that likely starts the JSON object
                idx = text.find("{")
                if idx != -1:
                    json_text = text[idx:]
                else:
                    json_text = text
                rules = json.loads(json_text)

            rules = _sanitize_transformation_rules(profile, rules)

            # Stocker en cache pour réutilisation future
            if use_cache:
                cag = get_cag_engine()
                cag.cache_rules(profile, rules)
                logger.info("💾 Règles mises en cache CAG pour réutilisation")

            return rules
        except json.JSONDecodeError as e:
            logger.warning(f"JSON parse failed: {e} - using domain pack fallback")

    # FALLBACK: Generate rules from domain pack + simple heuristics
    logger.info("⚠️ Using domain pack + heuristic fallback rules")
    rules = _generate_fallback_rules(profile, dataframe=dataframe)
    rules = _sanitize_transformation_rules(profile, rules)

    # Store in cache
    if use_cache:
        cag = get_cag_engine()
        cag.cache_rules(profile, rules)
        logger.info("💾 Fallback rules cached for reuse")

    return rules


def _generate_fallback_rules(
    profile: Dict[str, Any], dataframe: Optional[Any] = None
) -> Dict[str, Any]:
    """Generate a plan-only fallback from ML signals and profile heuristics."""
    ml_service = get_hybrid_ml_service()
    prediction = ml_service.predict(profile, dataframe=dataframe)

    plan: List[Dict[str, Any]] = []

    for column_name, action_data in prediction.action_predictions.items():
        action_label = str(action_data.get("label", "ignore")).lower()
        confidence = float(action_data.get("confidence", 0.5) or 0.5)
        fallback_label = str(action_data.get("fallback", "ignore")).lower()
        anomaly_data = prediction.anomaly_scores.get(column_name, {})
        anomaly_flagged = bool(anomaly_data.get("flagged", False))

        if action_label in _ALLOWED_PLAN_ACTIONS and action_label != "ignore":
            problem = f"ML suggested {action_label}"
            if action_label == "convert_type":
                problem = "type mismatch detected"
            elif action_label == "standardize_date":
                problem = "date parsing is inconsistent"
            elif action_label == "fill_missing":
                problem = "missing values present"
            elif action_label == "remove_duplicate":
                problem = "duplicate rows or keys likely"
            elif action_label == "reject_row":
                problem = "row quality is too low"
            plan.append(
                {
                    "column": column_name,
                    "problem": problem,
                    "action": action_label,
                    "confidence": round(max(confidence, 0.55), 4),
                }
            )

        if anomaly_flagged:
            score = float(anomaly_data.get("score", 0.0) or 0.0)
            anomaly_confidence = min(0.99, max(0.6, abs(score)))
            plan.append(
                {
                    "column": column_name,
                    "problem": "statistical anomaly detected",
                    "action": "mark_as_anomaly",
                    "confidence": round(anomaly_confidence, 4),
                }
            )

        if fallback_label == "remove_duplicate" and column_name not in {
            "__dataset__",
            "",
        }:
            plan.append(
                {
                    "column": column_name,
                    "problem": "duplicate identifiers detected",
                    "action": "remove_duplicate",
                    "confidence": 0.65,
                }
            )

    if not plan:
        for column in profile.get("columns", []):
            column_name = column.get("name", "")
            if not column_name:
                continue

            missing_pct = float(column.get("missing_pct", 0) or 0)
            date_ratio = float(column.get("date_parse_ratio", 0) or 0)
            numeric_ratio = float(column.get("numeric_parse_ratio", 0) or 0)
            role = str(column.get("role", "")).lower()

            if missing_pct >= 20:
                if _is_business_numeric_column_name(column_name):
                    plan.append(
                        {
                            "column": column_name,
                            "problem": "missing or invalid business numeric values should remain NaN",
                            "action": "mark_as_anomaly",
                            "confidence": 0.7,
                        }
                    )
                else:
                    plan.append(
                        {
                            "column": column_name,
                            "problem": "missing values present",
                            "action": "fill_missing",
                            "confidence": 0.7,
                        }
                    )
            elif date_ratio >= 0.7 or "date" in column_name.lower() or role == "date":
                plan.append(
                    {
                        "column": column_name,
                        "problem": "date format should be standardized",
                        "action": "standardize_date",
                        "confidence": 0.68,
                    }
                )
            elif numeric_ratio >= 0.7 and str(column.get("dtype", "")).lower() not in {
                "int64",
                "float64",
            }:
                plan.append(
                    {
                        "column": column_name,
                        "problem": "numeric values require conversion",
                        "action": "convert_type",
                        "confidence": 0.66,
                    }
                )

    deduped = []
    seen = set()
    for item in plan:
        key = (item.get("column"), item.get("problem"), item.get("action"))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)

    deduped.sort(
        key=lambda item: float(item.get("confidence", 0.0) or 0.0), reverse=True
    )

    return {
        "dataset_summary": {
            "dataset_type": profile.get("domain_context", {}).get("domain", "unknown"),
            "general_quality": "medium",
            "notes": [
                "Fallback plan: ML heuristics used because LLM output was unavailable or invalid"
            ],
        },
        "plan": deduped,
    }


def save_rules_to_file(rules: Dict[str, Any], output_path: str) -> None:
    """
    Sauvegarde les regles generees dans un fichier JSON.
    """
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(rules, f, indent=2, ensure_ascii=False)


def memorize_applied_rule(
    dataset_name: str,
    profile: Dict[str, Any],
    rules: Dict[str, Any],
) -> None:
    """
    Enregistre les règles appliquées dans la base RAG pour l'apprentissage.
    Permet au système d'apprendre des patterns appliqués précédemment.

    Args:
        dataset_name: Nom du dataset traité
        profile: Profil du dataset analysé
        rules: Règles appliquées
    """
    try:
        rag = RAGEngine()

        # Créer un ID unique pour cette règle
        rule_id = f"learned_{dataset_name}_{len(str(profile))}"

        # Description basée sur les règles appliquées
        plan = rules.get("plan", []) if isinstance(rules, dict) else []
        action_counts: Dict[str, int] = {}
        for item in plan:
            if isinstance(item, dict):
                action = str(item.get("action", "")).lower()
                action_counts[action] = action_counts.get(action, 0) + 1

        if action_counts:
            applied_actions = [
                f"{action}: {count}" for action, count in sorted(action_counts.items())
            ]
        else:
            applied_actions = ["no plan actions recorded"]

        rule_description = f"Applied to {dataset_name}: {', '.join(applied_actions)}"

        # Déterminer les tags basés sur le profil
        tags = ["learned"]
        if "schema" in profile:
            for col in profile["schema"]:
                col_type = col.get("type", "").lower()
                if col_type in ["datetime", "date"]:
                    tags.append("date")
                elif col_type == "string":
                    tags.append("text")
                elif col_type in ["int", "float"]:
                    tags.append("numeric")

        # Ajouter à la base RAG
        rag.add_cleaning_rule(
            rule_id=rule_id,
            rule_name=f"Learned: {dataset_name}",
            rule_description=rule_description,
            rule_content=rules,
            tags=tags,
        )

        rag.persist()
        print(f"✅ Rule memorized for dataset: {dataset_name}")
    except Exception as e:
        print(f"⚠️ Error memorizing rule: {e}")


# ============================================================================
# CAG Utilities - Contextual Augmented Generation
# ============================================================================


def get_cag_stats() -> Dict[str, Any]:
    """
    Retourne les statistiques du cache CAG.
    Utile pour monitorer l'efficacité du cache.
    """
    cag = get_cag_engine()
    return cag.get_stats()


def print_cag_stats() -> None:
    """Affiche les statistiques du cache CAG de manière lisible"""
    cag = get_cag_engine()
    cag.log_stats()


def clear_cag_cache(keep_recent_days: int = 0) -> None:
    """
    Nettoie le cache CAG.

    Args:
        keep_recent_days: Nombre de jours à conserver (0 = tout effacer)
    """
    cag = get_cag_engine()
    deleted, kept = cag.clear_cache(keep_recent_days)
    logger.info(f"CAG cache nettoyé: {deleted} entrées supprimées, {kept} conservées")


def reset_cag_session() -> None:
    """Réinitialise le cache mémoire CAG pour la session courante"""
    cag = get_cag_engine()
    cag._memory_cache.clear()
    cag.stats = {"cache_hits": 0, "cache_misses": 0, "llm_calls": 0}
    logger.info("✓ Cache mémoire CAG réinitialisé pour nouvelle session")
