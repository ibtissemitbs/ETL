"""
Report Generator Module - Creates comprehensive ETL execution and profiling reports.

This module:
- Generates execution reports with statistics
- Creates profiling reports
- Produces JSON and text-based outputs
- Tracks pipeline performance metrics
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class ReportGenerator:
    """
    Generates comprehensive reports of ETL pipeline execution.

    Attributes:
        report_dir (Path): Directory where reports are saved
    """

    def __init__(self, report_dir: str = "reports/execution"):
        """
        Initialize the ReportGenerator.

        Args:
            report_dir (str): Directory where reports are saved.
                             Defaults to 'reports/execution'.
        """
        self.report_dir = Path(report_dir)
        self.report_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"ReportGenerator initialized with directory: {self.report_dir}")

    def generate_execution_report(
        self,
        input_filename: str,
        extraction_stats: Dict[str, Any],
        profiling_stats: Dict[str, Any],
        transformation_summary: Dict[str, Any],
        output_path: str,
        llm_rules_used: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        Generate a comprehensive execution report.

        Args:
            input_filename (str): Name of input file
            extraction_stats (Dict): Statistics from extraction phase
            profiling_stats (Dict): Statistics from profiling phase
            transformation_summary (Dict): Summary of transformations applied
            output_path (str): Path where cleaned data was saved
            llm_rules_used (Dict, optional): LLM transformation rules applied

        Returns:
            Dict: Complete execution report
        """
        logger.info("Generating execution report...")

        report = {
            "metadata": {
                "report_type": "ETL Execution Report",
                "timestamp": datetime.now().isoformat(),
                "version": "1.0",
            },
            "input": {
                "filename": input_filename,
                "rows": extraction_stats.get("rows", 0),
                "columns": extraction_stats.get("columns", 0),
            },
            "profiling": {
                "data_quality_score": profiling_stats.get("quality_score", 0),
                "duplicate_rows": profiling_stats.get("duplicate_rows", 0),
                "columns_analyzed": len(profiling_stats.get("columns", [])),
            },
            "transformation": {
                "original_rows": transformation_summary.get("original_rows", 0),
                "final_rows": transformation_summary.get("final_rows", 0),
                "rows_removed": transformation_summary.get("rows_removed", 0),
                "original_columns": transformation_summary.get("original_columns", 0),
                "final_columns": transformation_summary.get("final_columns", 0),
                "columns_removed": transformation_summary.get("columns_removed", 0),
                "transformation_count": transformation_summary.get(
                    "transformation_count", 0
                ),
                "transformations_list": transformation_summary.get(
                    "transformations", []
                ),
            },
            "output": {
                "filepath": output_path,
                "rows": transformation_summary.get("final_rows", 0),
                "columns": transformation_summary.get("final_columns", 0),
            },
            "llm": {
                "rules_applied": llm_rules_used is not None,
                "rules_count": len(llm_rules_used) if llm_rules_used else 0,
            },
            "summary": {
                "status": "success",
                "message": f"Successfully processed {input_filename}",
                "rows_processed": transformation_summary.get("final_rows", 0),
                "data_retained": round(
                    (
                        transformation_summary.get("final_rows", 0)
                        / max(transformation_summary.get("original_rows", 1), 1)
                        * 100
                    ),
                    2,
                ),
            },
        }

        logger.info("✓ Execution report generated")
        return report

    def generate_profiling_report(
        self, profile: Dict[str, Any], filename: str
    ) -> Dict[str, Any]:
        """
        Generate a detailed profiling report.

        Args:
            profile (Dict): Profile data from profiler module
            filename (str): Name of the profiled file

        Returns:
            Dict: Profiling report
        """
        logger.info("Generating profiling report...")

        # Analyze columns for detailed insights
        column_insights = []
        for col in profile.get("columns", []):
            insight = {
                "name": col.get("name"),
                "dtype": col.get("dtype"),
                "stats": {
                    "unique_values": col.get("unique_count", 0),
                    "missing_values": col.get("missing_count", 0),
                    "missing_percentage": col.get("missing_percentage", 0),
                    "sample_values": col.get("sample_values", []),
                },
            }
            column_insights.append(insight)

        report = {
            "metadata": {
                "report_type": "Data Profiling Report",
                "timestamp": datetime.now().isoformat(),
                "filename": filename,
            },
            "dataset_overview": {
                "total_rows": profile.get("metadata", {}).get("rows", 0),
                "total_columns": profile.get("metadata", {}).get("columns", 0),
                "duplicate_rows": profile.get("metadata", {}).get("duplicate_rows", 0),
            },
            "column_analysis": column_insights,
            "data_quality_assessment": {
                "completeness": self._calculate_completeness(profile),
                "uniqueness": self._calculate_uniqueness(profile),
                "consistency": "To be assessed after transformation",
            },
        }

        logger.info("✓ Profiling report generated")
        return report

    def _calculate_completeness(self, profile: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate data completeness metrics."""
        columns = profile.get("columns", [])
        if not columns:
            return {"percentage": 0, "assessment": "No data"}

        total_nulls = sum(col.get("missing_count", 0) for col in columns)
        total_cells = profile.get("metadata", {}).get("rows", 0) * profile.get(
            "metadata", {}
        ).get("columns", 0)

        completeness = (
            round(((total_cells - total_nulls) / max(total_cells, 1) * 100), 2)
            if total_cells > 0
            else 0
        )

        return {
            "percentage": completeness,
            "assessment": (
                "Good"
                if completeness >= 95
                else "Fair" if completeness >= 80 else "Poor"
            ),
        }

    def _calculate_uniqueness(self, profile: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate data uniqueness metrics."""
        columns = profile.get("columns", [])
        if not columns:
            return {"assessment": "No data"}

        total_rows = profile.get("metadata", {}).get("rows", 0)
        if total_rows == 0:
            return {"assessment": "No data"}

        uniqueness_scores = []
        for col in columns:
            unique_count = col.get("unique_count", 0)
            unique_ratio = unique_count / total_rows if total_rows > 0 else 0
            uniqueness_scores.append(unique_ratio)

        avg_uniqueness = (
            sum(uniqueness_scores) / len(uniqueness_scores) if uniqueness_scores else 0
        )

        return {
            "average": round(avg_uniqueness * 100, 2),
            "assessment": (
                "Good"
                if avg_uniqueness > 0.5
                else "Fair" if avg_uniqueness > 0.3 else "Low"
            ),
        }

    def save_report_json(
        self, report: Dict[str, Any], filename: Optional[str] = None
    ) -> str:
        """
        Save report to JSON file.

        Args:
            report (Dict): Report data
            filename (str, optional): Output filename

        Returns:
            str: Path to saved report
        """
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"report_{timestamp}.json"

        filepath = self.report_dir / filename

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(report, f, indent=2, ensure_ascii=False, default=str)
            logger.info(f"✓ Report saved to JSON: {filepath}")
            return str(filepath)
        except IOError as e:
            logger.error(f"Failed to save JSON report: {str(e)}")
            raise

    def save_report_text(
        self, report: Dict[str, Any], filename: Optional[str] = None
    ) -> str:
        """
        Save report to human-readable text file.

        Args:
            report (Dict): Report data
            filename (str, optional): Output filename

        Returns:
            str: Path to saved report
        """
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"report_{timestamp}.txt"

        filepath = self.report_dir / filename

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(self._format_report_text(report))
            logger.info(f"✓ Report saved to TXT: {filepath}")
            return str(filepath)
        except IOError as e:
            logger.error(f"Failed to save text report: {str(e)}")
            raise

    def _format_report_text(self, report: Dict[str, Any]) -> str:
        """Format report as human-readable text."""
        lines = []

        lines.append("=" * 70)
        lines.append(f"ETL PIPELINE EXECUTION REPORT")
        lines.append("=" * 70)

        if "metadata" in report:
            lines.append(f"\nGenerated: {report['metadata'].get('timestamp')}")

        if "input" in report:
            lines.append("\n📥 INPUT")
            lines.append("-" * 70)
            lines.append(f"  Filename:  {report['input'].get('filename')}")
            lines.append(f"  Rows:      {report['input'].get('rows')}")
            lines.append(f"  Columns:   {report['input'].get('columns')}")

        if "transformation" in report:
            trans = report["transformation"]
            lines.append("\n🔄 TRANSFORMATION")
            lines.append("-" * 70)
            lines.append(f"  Rows Before:      {trans.get('original_rows')}")
            lines.append(f"  Rows After:       {trans.get('final_rows')}")
            lines.append(f"  Rows Removed:     {trans.get('rows_removed')}")
            lines.append(f"  Columns Before:   {trans.get('original_columns')}")
            lines.append(f"  Columns After:    {trans.get('final_columns')}")
            lines.append(f"  Columns Removed:  {trans.get('columns_removed')}")
            lines.append(f"  Transformations:  {trans.get('transformation_count')}")

        if "output" in report:
            lines.append("\n📤 OUTPUT")
            lines.append("-" * 70)
            lines.append(f"  Filepath:  {report['output'].get('filepath')}")
            lines.append(f"  Rows:      {report['output'].get('rows')}")
            lines.append(f"  Columns:   {report['output'].get('columns')}")

        if "summary" in report:
            summary = report["summary"]
            lines.append("\n✅ SUMMARY")
            lines.append("-" * 70)
            lines.append(f"  Status:        {summary.get('status')}")
            lines.append(f"  Message:       {summary.get('message')}")
            lines.append(f"  Data Retained: {summary.get('data_retained')}%")

        lines.append("\n" + "=" * 70)

        return "\n".join(lines)

    def save_all_reports(
        self, execution_report: Dict, profiling_report: Optional[Dict] = None
    ) -> Dict[str, str]:
        """
        Save both JSON and text versions of reports.

        Args:
            execution_report (Dict): Execution report data
            profiling_report (Dict, optional): Profiling report data

        Returns:
            Dict: Paths to all saved reports
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        paths = {
            "execution_json": self.save_report_json(
                execution_report, f"execution_{timestamp}.json"
            ),
            "execution_text": self.save_report_text(
                execution_report, f"execution_{timestamp}.txt"
            ),
        }

        if profiling_report:
            paths["profiling_json"] = self.save_report_json(
                profiling_report, f"profiling_{timestamp}.json"
            )

        return paths


def generate_execution_report(
    input_filename: str,
    extraction_stats: Dict,
    profiling_stats: Dict,
    transformation_summary: Dict,
    output_path: str,
) -> Dict:
    """
    Quick function to generate and save execution report.

    Args:
        input_filename (str): Name of input file
        extraction_stats (Dict): Stats from extraction
        profiling_stats (Dict): Stats from profiling
        transformation_summary (Dict): Summary of transformations
        output_path (str): Path to output file

    Returns:
        Dict: Generated report
    """
    generator = ReportGenerator()
    report = generator.generate_execution_report(
        input_filename,
        extraction_stats,
        profiling_stats,
        transformation_summary,
        output_path,
    )
    generator.save_all_reports(report)
    return report


if __name__ == "__main__":
    # Example usage
    print("=" * 60)
    print("REPORT GENERATOR - Example Usage")
    print("=" * 60)

    sample_execution_report = {
        "metadata": {
            "report_type": "ETL Execution Report",
            "timestamp": datetime.now().isoformat(),
        },
        "input": {"filename": "customers.csv", "rows": 1000, "columns": 7},
        "transformation": {
            "original_rows": 1000,
            "final_rows": 998,
            "rows_removed": 2,
            "original_columns": 7,
            "final_columns": 6,
            "columns_removed": 1,
            "transformation_count": 12,
            "transformations_list": [],
        },
        "output": {
            "filepath": "data/processed/customers_processed.csv",
            "rows": 998,
            "columns": 6,
        },
        "summary": {
            "status": "success",
            "message": "Successfully processed customers.csv",
            "rows_processed": 998,
            "data_retained": 99.8,
        },
    }

    generator = ReportGenerator()

    print("\n📊 Saving execution report...")
    json_path = generator.save_report_json(
        sample_execution_report, "example_report.json"
    )
    print(f"  JSON: {json_path}")

    txt_path = generator.save_report_text(sample_execution_report, "example_report.txt")
    print(f"  TXT:  {txt_path}")

    print("\n✓ Report generation working correctly!")
