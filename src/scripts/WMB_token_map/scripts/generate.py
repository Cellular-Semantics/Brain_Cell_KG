#!/usr/bin/env python3
"""
WMB Token Mapping Generation Script

This script follows the repository pattern for source data processing.
It generates comprehensive token mapping reports for WMB cell clusters.
"""

import sys
from pathlib import Path

# Add current directory to path to import our modules
current_dir = Path(__file__).parent
sys.path.append(str(current_dir))

from generate_wmb_token_reports import generate_complete_token_report


def main():
    """Generate WMB token mapping reports following repository conventions."""

    # Define paths relative to this script
    script_dir = Path(__file__).parent
    wmb_project_dir = script_dir.parent
    source_data_dir = wmb_project_dir / "source_data"

    # Input file
    token_file = source_data_dir / "WMB_tokens_20250922.csv"

    # Output directory (in the WMB_token_map directory)
    output_dir = wmb_project_dir / "reports"

    if not token_file.exists():
        print(f"Error: Token file not found: {token_file}")
        sys.exit(1)

    print(f"Generating WMB token mapping reports...")
    print(f"Input file: {token_file}")
    print(f"Output directory: {output_dir}")

    # Generate reports with default Neo4j connection
    generate_complete_token_report(
        str(token_file),
        str(output_dir)
    )

    print(f"\nWMB token mapping generation complete!")


if __name__ == "__main__":
    main()