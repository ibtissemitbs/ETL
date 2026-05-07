"""
Load Module - Saves transformed data to various formats and destinations.

This module:
- Saves to CSV format
- Saves to Excel format
- Handles file naming and paths
- Manages output directories
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)


class DataLoader:
    """
    Handles saving transformed data to files.

    Attributes:
        output_dir (Path): Directory where processed files are saved
    """

    def __init__(self, output_dir: str = "data/processed"):
        """
        Initialize the DataLoader.

        Args:
            output_dir (str): Directory where processed files are saved.
                             Defaults to 'data/processed'.
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"DataLoader initialized with output directory: {self.output_dir}")

    def generate_filename(
        self,
        original_filename: str = "data",
        format_ext: str = "csv",
        add_timestamp: bool = True,
    ) -> str:
        """
        Generate a clean output filename.

        Args:
            original_filename (str): Original input filename
            format_ext (str): File extension (csv, xlsx)
            add_timestamp (bool): Whether to add timestamp to filename

        Returns:
            str: Generated filename
        """
        # Remove original extension
        base_name = Path(original_filename).stem

        if add_timestamp:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{base_name}_processed_{timestamp}.{format_ext}"
        else:
            filename = f"{base_name}_processed.{format_ext}"

        return filename

    def save_csv(
        self, df: pd.DataFrame, filename: Optional[str] = None, index: bool = False
    ) -> str:
        """
        Save DataFrame to CSV file.

        Args:
            df (pd.DataFrame): DataFrame to save
            filename (str, optional): Output filename. Auto-generated if not provided.
            index (bool): Whether to save index column (default: False)

        Returns:
            str: Full path to saved file

        Raises:
            IOError: If file cannot be written
        """
        if filename is None:
            filename = self.generate_filename(format_ext="csv")

        output_path = self.output_dir / filename

        try:
            df.to_csv(output_path, index=index, encoding="utf-8")
            logger.info(f"✓ Data saved to CSV: {output_path}")
            logger.info(f"  Rows: {len(df)}, Columns: {len(df.columns)}")
            return str(output_path)

        except IOError as e:
            logger.error(f"Failed to save CSV file: {str(e)}")
            raise

    def save_excel(
        self, df: pd.DataFrame, filename: Optional[str] = None, sheet_name: str = "Data"
    ) -> str:
        """
        Save DataFrame to Excel file.

        Args:
            df (pd.DataFrame): DataFrame to save
            filename (str, optional): Output filename. Auto-generated if not provided.
            sheet_name (str): Name of the sheet in Excel file (default: "Data")

        Returns:
            str: Full path to saved file

        Raises:
            IOError: If file cannot be written
        """
        if filename is None:
            filename = self.generate_filename(format_ext="xlsx")

        output_path = self.output_dir / filename

        try:
            with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
                df.to_excel(writer, sheet_name=sheet_name, index=False)

            logger.info(f"✓ Data saved to Excel: {output_path}")
            logger.info(f"  Rows: {len(df)}, Columns: {len(df.columns)}")
            return str(output_path)

        except IOError as e:
            logger.error(f"Failed to save Excel file: {str(e)}")
            raise

    def save(
        self, df: pd.DataFrame, format: str = "csv", filename: Optional[str] = None
    ) -> str:
        """
        Save DataFrame in specified format.

        Args:
            df (pd.DataFrame): DataFrame to save
            format (str): Output format ('csv' or 'excel')
            filename (str, optional): Output filename. Auto-generated if not provided.

        Returns:
            str: Full path to saved file

        Raises:
            ValueError: If format is not supported
        """
        if format.lower() in ["csv", ".csv"]:
            return self.save_csv(df, filename)
        elif format.lower() in ["excel", "xlsx", ".xlsx", "xls"]:
            return self.save_excel(df, filename)
        else:
            raise ValueError(f"Unsupported format: {format}. Use 'csv' or 'excel'")

    def archive_file(self, file_path: str, archive_dir: str = "data/archive") -> str:
        """
        Move a file to the archive directory.

        Args:
            file_path (str): Path to file to archive
            archive_dir (str): Archive directory path

        Returns:
            str: New file path in archive
        """
        try:
            source = Path(file_path)
            archive = Path(archive_dir)
            archive.mkdir(parents=True, exist_ok=True)

            # Add timestamp to archived filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            archive_filename = f"{source.stem}_{timestamp}{source.suffix}"
            dest = archive / archive_filename

            source.rename(dest)
            logger.info(f"✓ File archived: {file_path} → {dest}")
            return str(dest)

        except Exception as e:
            logger.error(f"Failed to archive file: {str(e)}")
            raise

    def reject_file(
        self, file_path: str, reject_dir: str = "data/reject", reason: str = "Unknown"
    ) -> str:
        """
        Move a file to the reject directory.

        Args:
            file_path (str): Path to file to reject
            reject_dir (str): Reject directory path
            reason (str): Reason for rejection

        Returns:
            str: New file path in reject directory
        """
        try:
            source = Path(file_path)
            reject = Path(reject_dir)
            reject.mkdir(parents=True, exist_ok=True)

            # Keep naming consistent
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            reject_filename = f"{source.stem}_{timestamp}{source.suffix}"
            dest = reject / reject_filename

            source.rename(dest)
            logger.warning(f"⚠ File rejected: {file_path} → {dest}")
            logger.warning(f"  Reason: {reason}")
            return str(dest)

        except Exception as e:
            logger.error(f"Failed to reject file: {str(e)}")
            raise


def save_data(
    df: pd.DataFrame,
    output_dir: str = "data/processed",
    format: str = "csv",
    filename: Optional[str] = None,
) -> str:
    """
    Quick function to save data.

    Args:
        df (pd.DataFrame): DataFrame to save
        output_dir (str): Output directory
        format (str): Output format (csv or excel)
        filename (str, optional): Output filename

    Returns:
        str: Full path to saved file
    """
    loader = DataLoader(output_dir)
    return loader.save(df, format=format, filename=filename)


if __name__ == "__main__":
    # Example usage
    print("=" * 60)
    print("LOAD MODULE - Example Usage")
    print("=" * 60)

    # Create sample DataFrame
    sample_data = {
        "customer_name": ["Alice", "Bob", "Charlie", "David", "Eve"],
        "email": [
            "alice@ex.com",
            "bob@ex.com",
            "charlie@ex.com",
            "david@ex.com",
            "eve@ex.com",
        ],
        "signup_date": [
            "2023-01-15",
            "2023-02-20",
            "2023-01-15",
            "2023-03-10",
            "2023-04-05",
        ],
        "age": [28, 35, 42, 31, 29],
    }

    df = pd.DataFrame(sample_data)

    print("\n📊 Sample Data:")
    print(df)

    loader = DataLoader()

    print("\n\n💾 Saving as CSV...")
    csv_path = loader.save_csv(df, filename="example_customers.csv")
    print(f"  Saved to: {csv_path}")

    print("\n💾 Saving as Excel...")
    excel_path = loader.save_excel(df, filename="example_customers.xlsx")
    print(f"  Saved to: {excel_path}")

    print("\n✓ Load module working correctly!")
