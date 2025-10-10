#!/usr/bin/env python3
"""
Generic utilities for generating ROBOT templates from heterogeneous tabular sources.
Provides base classes and helper functions for consistent template generation.
"""

import pandas as pd
from pathlib import Path
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any


class TemplateGenerator(ABC):
    """Abstract base class for ROBOT template generators."""

    def __init__(self, output_dir: str = "src/templates"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    @abstractmethod
    def process_data(self, input_data: Any) -> pd.DataFrame:
        """Process input data and return standardized DataFrame."""
        pass

    @abstractmethod
    def get_template_structure(self) -> Dict[str, str]:
        """Return ROBOT template column headers and types."""
        pass

    def generate_template(self, input_data: Any, output_filename: str) -> str:
        """Generate ROBOT template TSV file."""
        # Process data
        df = self.process_data(input_data)

        # Get template structure
        headers = self.get_template_structure()

        # Create template with headers
        template_rows = []
        template_rows.append(list(headers.keys()))  # Column names
        template_rows.append(list(headers.values()))  # ROBOT types

        # Add data rows
        for _, row in df.iterrows():
            template_rows.append([str(row.get(col, "")) for col in headers.keys()])

        # Write template file
        output_path = self.output_dir / output_filename
        with open(output_path, 'w') as f:
            for row in template_rows:
                f.write('\t'.join(row) + '\n')

        return str(output_path)


class AnnotationTransferGenerator(TemplateGenerator):
    """Generator for cell set annotation transfer templates."""

    def __init__(self, output_dir: str = "src/templates"):
        super().__init__(output_dir)
        self.confidence_threshold = 0.5

    def get_template_structure(self) -> Dict[str, str]:
        """Standard structure for annotation transfer templates."""
        return {
            "ID": "ID",
            "Type": "TYPE",
            "skos:exactMatch": "AI skos:exactMatch",
            "score": ">AT n2o:Confidence^^xsd:float"
        }

    def process_data(self, input_data: pd.DataFrame) -> pd.DataFrame:
        """Process annotation transfer data with optional confidence filtering."""
        # Ensure required columns exist
        required_cols = ["source_id", "target_id"]
        missing_cols = [col for col in required_cols if col not in input_data.columns]
        if missing_cols:
            raise ValueError(f"Missing required columns: {missing_cols}")

        # Handle optional confidence score
        has_confidence = "confidence_score" in input_data.columns

        if has_confidence:
            # Filter by confidence threshold if scores are available
            filtered_data = input_data[input_data["confidence_score"] >= self.confidence_threshold].copy()
        else:
            filtered_data = input_data.copy()

        # Map to template structure
        template_data = pd.DataFrame({
            "ID": filtered_data["source_id"],
            "Type": "owl:NamedIndividual",
            "skos:exactMatch": filtered_data["target_id"],
            "score": filtered_data.get("confidence_score", 1.0) if has_confidence else 1.0
        })

        # Sort by confidence score descending if available
        if has_confidence:
            template_data = template_data.sort_values("score", ascending=False)

        return template_data

    def set_confidence_threshold(self, threshold: float):
        """Set minimum confidence threshold for mappings."""
        self.confidence_threshold = threshold


class GroupAnnotationGenerator(TemplateGenerator):
    """Generator for group-based annotation transfer templates."""

    def get_template_structure(self) -> Dict[str, str]:
        """Structure for group annotation templates with multiple match types."""
        return {
            "Group": "GROUP",
            "Type": "TYPE",
            "accession_group": "ID",
            "WMB_exact_match": "AI skos:exactMatch SPLIT=|",
            "WMB_related_match": "AI skos:relatedMatch SPLIT=|",
            "WMB_broad_match": "AI skos:broadMatch SPLIT=|"
        }

    def process_data(self, input_data: pd.DataFrame) -> pd.DataFrame:
        """Process grouped annotation data with multiple match types."""
        # Group by source and aggregate matches by type
        grouped_data = []

        for group_name, group_df in input_data.groupby("group_name"):
            row_data = {
                "Group": group_name,
                "Type": "owl:NamedIndividual",
                "accession_group": group_df["group_id"].iloc[0]
            }

            # Aggregate matches by type
            for match_type in ["exact", "related", "broad"]:
                matches = group_df[group_df["match_type"] == match_type]["target_id"].tolist()
                row_data[f"WMB_{match_type}_match"] = "|".join(matches) if matches else ""

            grouped_data.append(row_data)

        return pd.DataFrame(grouped_data)


def validate_template_file(template_path: str) -> bool:
    """Validate ROBOT template file structure."""
    try:
        with open(template_path, 'r') as f:
            lines = f.readlines()

        if len(lines) < 2:
            print(f"Template must have at least header and type rows: {template_path}")
            return False

        # Check tab separation
        header_cols = len(lines[0].strip().split('\t'))
        type_cols = len(lines[1].strip().split('\t'))

        if header_cols != type_cols:
            print(f"Header and type row column mismatch: {template_path}")
            return False

        print(f"Template validation passed: {template_path}")
        return True

    except Exception as e:
        print(f"Template validation failed: {e}")
        return False