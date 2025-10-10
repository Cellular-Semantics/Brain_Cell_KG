#!/usr/bin/env python3
"""
Example generator for annotation transfer templates.
Demonstrates the pattern for processing heterogeneous tabular sources.
"""

import sys
import pandas as pd
from pathlib import Path

# Add utils to path for imports
sys.path.append(str(Path(__file__).parent.parent.parent / "utils"))
from template_generator import AnnotationTransferGenerator


def load_source_data():
    """Load and preprocess source annotation data."""
    data_dir = Path(__file__).parent.parent / "data"

    # Example: Load CSV with annotation mappings
    # Replace with actual data loading logic
    sample_data = {
        "source_id": [
            "WHB:CS202210140_3", "WHB:CS202210140_1", "WHB:CS202210140_2",
            "WHB:CS202210140_315", "WHB:CS202210140_309"
        ],
        "target_id": [
            "WMB:CS20230722_SUBC_338", "WMB:CS20230722_SUBC_338", "WMB:CS20230722_SUBC_338",
            "WMB:CS20230722_SUBC_313", "WMB:CS20230722_SUBC_315"
        ]
        # Note: confidence_score is optional - can be included or omitted
        # "confidence_score": [1.0, 0.99, 0.99, 0.97, 0.96]
    }

    return pd.DataFrame(sample_data)


def main():
    """Generate ROBOT template from source data."""
    # Load source data
    source_data = load_source_data()

    # Initialize generator
    generator = AnnotationTransferGenerator()
    generator.set_confidence_threshold(0.5)

    # Generate template
    output_file = "example_annotation_transfer.tsv"
    template_path = generator.generate_template(source_data, output_file)

    print(f"Generated template: {template_path}")

    # Validate the generated template
    from template_generator import validate_template_file
    if validate_template_file(template_path):
        print("Template validation successful")
    else:
        print("Template validation failed")
        sys.exit(1)


if __name__ == "__main__":
    main()