"""
Utilities - Helper functions for the ETL pipeline.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger(__name__)


def load_config(config_path: str = "config/settings.json") -> Dict[str, Any]:
    """
    Load configuration from JSON file.

    Args:
        config_path (str): Path to the configuration file.

    Returns:
        Dict: Configuration dictionary.
    """
    try:
        with open(config_path, "r") as f:
            config = json.load(f)
        logger.info(f"Configuration loaded from {config_path}")
        return config
    except FileNotFoundError:
        logger.warning(f"Config file not found at {config_path}. Using defaults.")
        return {}
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing config file: {e}")
        raise


def ensure_directories(config: Dict[str, Any]) -> None:
    """
    Ensure all required directories exist.

    Args:
        config (Dict): Configuration dictionary with path settings.
    """
    paths = config.get("paths", {})
    for key, path_str in paths.items():
        path = Path(path_str)
        path.mkdir(parents=True, exist_ok=True)
        logger.info(f"Ensured directory exists: {path}")


def save_json(data: Dict, output_path: str) -> None:
    """
    Save a dictionary to JSON file with proper formatting.

    Args:
        data (Dict): Data to save.
        output_path (str): Path to output file.
    """
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    logger.info(f"Saved JSON to {output_path}")


def load_json(input_path: str) -> Dict:
    """
    Load data from JSON file.

    Args:
        input_path (str): Path to input file.

    Returns:
        Dict: Loaded data.
    """
    with open(input_path, "r") as f:
        data = json.load(f)
    logger.info(f"Loaded JSON from {input_path}")
    return data


if __name__ == "__main__":
    config = load_config()
    print(json.dumps(config, indent=2))
