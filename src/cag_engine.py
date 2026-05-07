"""
CAG Engine - Contextual Augmented Generation
Combine RAG (Retrieval-Augmented Generation) + Cache (mémoire des réponses LLM)
Économise les appels LLM en réutilisant les règles de transformation pour des profils similaires
"""

import hashlib
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class CAGEngine:
    """
    Moteur CAG pour mémoriser et réutiliser les règles de transformation.
    Combine RAG (contexte pertinent) + Cache (mémoire des réponses).
    """

    def __init__(self, cache_dir: Optional[Path] = None):
        """
        Initialise le moteur CAG

        Args:
            cache_dir: Répertoire pour stocker le cache (défaut: data/cag_cache)
        """
        self.cache_dir = (
            cache_dir or Path(__file__).parent.parent / "data" / "cag_cache"
        )
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Cache en mémoire pour la session courante
        self._memory_cache: Dict[str, Dict[str, Any]] = {}

        # Stats
        self.stats = {
            "cache_hits": 0,
            "cache_misses": 0,
            "llm_calls": 0,
        }

    @staticmethod
    def hash_profile(profile: Dict[str, Any]) -> str:
        """
        Génère un hash unique pour un profil de dataset.
        Deux datasets avec la même structure et issues similaires → même hash.

        Args:
            profile: Profil du dataset

        Returns:
            Hash SHA256 du profil
        """
        # Créer une représentation normalisée du profil
        # Focus sur: colonnes, types, patterns de nulls, issues
        normalized = {
            "n_columns": profile.get("n_columns", 0),
            "n_rows": profile.get("n_rows", 0),
            "columns": sorted(
                [
                    {
                        "name": col.get("name"),
                        "dtype": col.get("dtype"),
                        "missing_pct": round(col.get("missing_pct", 0) / 10)
                        * 10,  # Bucket par 10%
                        "unique_count": col.get("unique_count", 0),
                    }
                    for col in profile.get("columns", [])
                ],
                key=lambda x: x["name"],
            ),
        }

        profile_json = json.dumps(normalized, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(profile_json.encode()).hexdigest()

    def get_cache_path(self, profile_hash: str) -> Path:
        """Retourne le chemin du fichier cache pour un hash donné"""
        return self.cache_dir / f"{profile_hash}.json"

    def get_cached_rules(self, profile: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Récupère les règles en cache pour un profil similaire

        Args:
            profile: Profil du dataset

        Returns:
            Règles en cache ou None si pas trouvées
        """
        profile_hash = self.hash_profile(profile)

        # Vérifier le cache mémoire (session courante)
        if profile_hash in self._memory_cache:
            logger.info(
                f"✓ CAG HIT (memory): {profile_hash[:8]}... - Règles réutilisées"
            )
            self.stats["cache_hits"] += 1
            return self._memory_cache[profile_hash]

        # Vérifier le cache disque
        cache_file = self.get_cache_path(profile_hash)
        if cache_file.exists():
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    cache_data = json.load(f)
                    # Stocker en mémoire aussi
                    self._memory_cache[profile_hash] = cache_data["rules"]
                    logger.info(
                        f"✓ CAG HIT (disk): {profile_hash[:8]}... - Règles du cache restaurées"
                    )
                    self.stats["cache_hits"] += 1
                    return cache_data["rules"]
            except Exception as e:
                logger.warning(f"Erreur lecture cache: {e}")

        logger.info(f"✗ CAG MISS: {profile_hash[:8]}... - Appel LLM nécessaire")
        self.stats["cache_misses"] += 1
        return None

    def cache_rules(self, profile: Dict[str, Any], rules: Dict[str, Any]) -> None:
        """
        Stocke les règles de transformation en cache

        Args:
            profile: Profil du dataset
            rules: Règles de transformation du LLM
        """
        profile_hash = self.hash_profile(profile)

        # Stocker en mémoire
        self._memory_cache[profile_hash] = rules

        # Stocker sur disque
        cache_file = self.get_cache_path(profile_hash)
        cache_data = {
            "timestamp": datetime.now().isoformat(),
            "profile_summary": {
                "n_columns": profile.get("n_columns", 0),
                "n_rows": profile.get("n_rows", 0),
                "column_types": [
                    col.get("dtype") for col in profile.get("columns", [])
                ],
            },
            "rules": rules,
        }

        try:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(cache_data, f, indent=2, ensure_ascii=False)
            logger.info(f"✓ Règles mises en cache: {cache_file}")
        except Exception as e:
            logger.warning(f"Erreur écriture cache: {e}")

    def clear_cache(self, keep_recent_days: int = 0) -> Tuple[int, int]:
        """
        Nettoie le cache disque

        Args:
            keep_recent_days: Nombre de jours de cache à conserver (0 = tout effacer)

        Returns:
            (fichiers_supprimés, fichiers_conservés)
        """
        from datetime import datetime as dt
        from datetime import timedelta

        deleted = 0
        kept = 0
        cutoff_time = dt.now() - timedelta(days=keep_recent_days)

        for cache_file in self.cache_dir.glob("*.json"):
            file_time = dt.fromtimestamp(cache_file.stat().st_mtime)
            if file_time < cutoff_time:
                try:
                    cache_file.unlink()
                    deleted += 1
                except Exception as e:
                    logger.warning(f"Erreur suppression {cache_file}: {e}")
            else:
                kept += 1

        logger.info(f"Cache nettoyé: {deleted} supprimés, {kept} conservés")
        return deleted, kept

    def get_stats(self) -> Dict[str, Any]:
        """Retourne les statistiques du cache CAG"""
        total = self.stats["cache_hits"] + self.stats["cache_misses"]
        hit_rate = (self.stats["cache_hits"] / total * 100) if total > 0 else 0

        return {
            "cache_hits": self.stats["cache_hits"],
            "cache_misses": self.stats["cache_misses"],
            "llm_calls_avoided": self.stats["cache_hits"],
            "hit_rate_percent": round(hit_rate, 1),
            "memory_cache_size": len(self._memory_cache),
            "disk_cache_entries": len(list(self.cache_dir.glob("*.json"))),
        }

    def log_stats(self) -> None:
        """Affiche les statistiques du cache"""
        stats = self.get_stats()
        logger.info(
            f"""
        ╔═══════════════════════════════════════════╗
        ║          CAG Cache Statistics             ║
        ╠═══════════════════════════════════════════╣
        ║ Cache Hits        : {stats['cache_hits']:3d}                ║
        ║ Cache Misses      : {stats['cache_misses']:3d}                ║
        ║ Hit Rate          : {stats['hit_rate_percent']:5.1f}%              ║
        ║ LLM Calls Saved   : {stats['llm_calls_avoided']:3d}                ║
        ║ Memory Cache      : {stats['memory_cache_size']:3d} profils          ║
        ║ Disk Cache        : {stats['disk_cache_entries']:3d} entrées         ║
        ╚═══════════════════════════════════════════╝
        """
        )


# Instance globale CAG
_cag_instance: Optional[CAGEngine] = None


def get_cag_engine() -> CAGEngine:
    """Retourne l'instance singleton CAG"""
    global _cag_instance
    if _cag_instance is None:
        _cag_instance = CAGEngine()
    return _cag_instance
