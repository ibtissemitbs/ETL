"""
Extract Module - Reads raw CSV or Excel files from data/in directory.

This module handles:
- File detection and loading
- CSV and Excel format support
- Basic error handling and validation
- Returns a pandas DataFrame for further processing
"""

import logging
from pathlib import Path
from typing import Optional, Tuple

import pandas as pd

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class DataExtractor:
    """
    Handles extraction of raw data from CSV or Excel files.

    Attributes:
        input_dir (Path): Directory path where raw files are stored
        supported_formats (tuple): Supported file extensions
    """

    SUPPORTED_FORMATS = (".csv", ".xlsx", ".xls")

    def __init__(self, input_dir: str = "data/in"):
        """
        Initialize the DataExtractor.

        Args:
            input_dir (str): Path to the directory containing raw files.
                            Defaults to 'data/in'.
        """
        self.input_dir = Path(input_dir)

        # Create directory if it doesn't exist
        self.input_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"DataExtractor initialized with input directory: {self.input_dir}")

    def find_files(self) -> list:
        """
        Find all supported data files in the input directory.

        Returns:
            list: List of Path objects for supported files.
        """
        files = []
        for ext in self.SUPPORTED_FORMATS:
            files.extend(self.input_dir.glob(f"*{ext}"))

        logger.info(f"Found {len(files)} file(s) in {self.input_dir}")
        return sorted(files)

    def load_csv(self, file_path: Path) -> pd.DataFrame:
        """
        Load a CSV file into a pandas DataFrame.

        Args:
            file_path (Path): Path to the CSV file.

        Returns:
            pd.DataFrame: Loaded data.

        Raises:
            Exception: If the file cannot be read.
        """
        try:
            df = pd.read_csv(file_path, encoding="utf-8")
            logger.info(f"Successfully loaded CSV: {file_path.name} ({len(df)} rows)")
            return df
        except UnicodeDecodeError:
            # Try with different encoding if UTF-8 fails
            try:
                df = pd.read_csv(file_path, encoding="latin-1")
                logger.warning(f"CSV loaded with latin-1 encoding: {file_path.name}")
                return df
            except Exception as e:
                logger.error(f"Failed to load CSV {file_path.name}: {str(e)}")
                raise

    def load_excel(self, file_path: Path, sheet_name: int = 0) -> pd.DataFrame:
        """
        Load an Excel file into a pandas DataFrame.

        Args:
            file_path (Path): Path to the Excel file.
            sheet_name (int): Sheet index to load. Defaults to 0 (first sheet).

        Returns:
            pd.DataFrame: Loaded data.

        Raises:
            Exception: If the file cannot be read.
        """
        try:
            df = pd.read_excel(file_path, sheet_name=sheet_name)
            logger.info(
                f"Successfully loaded Excel: {file_path.name} "
                f"(sheet {sheet_name}, {len(df)} rows)"
            )
            return df
        except Exception as e:
            logger.error(f"Failed to load Excel {file_path.name}: {str(e)}")
            raise

    def load_file(self, file_path: Path) -> pd.DataFrame:
        """
        Load a data file based on its extension.

        Args:
            file_path (Path): Path to the file.

        Returns:
            pd.DataFrame: Loaded data.

        Raises:
            ValueError: If file format is not supported.
            Exception: If the file cannot be loaded.
        """
        file_path = Path(file_path)
        suffix = file_path.suffix.lower()

        if suffix == ".csv":
            return self.load_csv(file_path)
        elif suffix in (".xlsx", ".xls"):
            return self.load_excel(file_path)
        else:
            raise ValueError(
                f"Unsupported file format: {suffix}. "
                f"Supported formats: {self.SUPPORTED_FORMATS}"
            )

    def extract(self, file_path: Optional[str] = None) -> Tuple[pd.DataFrame, str]:
        """
        Extract data from a file. If no file is specified, use the first available file.

        Args:
            file_path (str, optional): Path to a specific file.
                                      If None, uses the first found file.

        Returns:
            Tuple[pd.DataFrame, str]: (DataFrame, file_name)

        Raises:
            FileNotFoundError: If no files are found.
            Exception: If data cannot be loaded.
        """
        if file_path:
            target_file = Path(file_path)
        else:
            files = self.find_files()
            if not files:
                raise FileNotFoundError(
                    f"No data files found in {self.input_dir}. "
                    f"Supported formats: {self.SUPPORTED_FORMATS}"
                )
            target_file = files[0]
            logger.info(f"Using first available file: {target_file.name}")

        df = self.load_file(target_file)

        # Validate the DataFrame
        if df.empty:
            logger.warning(f"Warning: Loaded file is empty!")
        else:
            logger.info(
                f"Extraction complete: {df.shape[0]} rows, {df.shape[1]} columns"
            )

        return df, target_file.name


# Convenience function for quick usage
def extract_data(
    input_dir: str = "data/in", file_path: Optional[str] = None
) -> Tuple[pd.DataFrame, str]:
    """
    Quick extraction function. Creates an extractor and loads data in one call.

    Args:
        input_dir (str): Directory containing raw files.
        file_path (str, optional): Specific file to load.

    Returns:
        Tuple[pd.DataFrame, str]: (Data, file_name)
    """
    extractor = DataExtractor(input_dir)
    return extractor.extract(file_path)


def load_file(file_path: str) -> pd.DataFrame:
    """
    Charge directement un fichier CSV/Excel via DataExtractor.
    """
    extractor = DataExtractor(input_dir=str(Path(file_path).parent))
    df, _ = extractor.extract(file_path=file_path)
    return df


if __name__ == "__main__":
    # Example usage
    try:
        df, filename = extract_data()
        print(f"\nExtracted: {filename}")
        print(f"Shape: {df.shape}")
        print(f"\nFirst few rows:\n{df.head()}")
    except FileNotFoundError as e:
        print(f"Error: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")
