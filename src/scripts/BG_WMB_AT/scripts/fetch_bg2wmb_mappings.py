import requests
import sys
from pathlib import Path

# Find project root
script_dir = Path(__file__).resolve().parent
project_root = script_dir.parent.parent.parent.parent

# Google Sheet ID and GID
SHEET_ID = "1NwO-_BQumtfVYcTNP--vRa5434Elvj5me1oEKV1Q-gE"
GID = "1470945829"
CSV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={GID}"

# Default output path
DEFAULT_OUT_PATH = script_dir.parent / "source_data" / "MWB_consensus_homology.csv"

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Fetch BG2WMB mappings from Google Sheets')
    parser.add_argument('--output', type=Path, default=DEFAULT_OUT_PATH,
                       help='Output CSV file path')
    args = parser.parse_args()

    # Ensure output directory exists
    args.output.parent.mkdir(parents=True, exist_ok=True)

    try:
        resp = requests.get(CSV_URL)
        resp.raise_for_status()
        args.output.write_bytes(resp.content)
        print(f"Downloaded and saved to {args.output}")
    except Exception as e:
        print(f"Error downloading sheet: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
