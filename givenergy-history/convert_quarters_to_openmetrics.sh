#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INPUT_DIR="${1:-$SCRIPT_DIR}"
OUTPUT_DIR="${2:-$SCRIPT_DIR}"

mkdir -p "$OUTPUT_DIR"

quarters=(
  "2022Q1"
  "2022Q2"
  "2022Q3"
  "2022Q4"
  "2023Q1"
  "2023Q2"
  "2023Q3"
  "2023Q4"
  "2024Q1"
  "2024Q2"
  "2024Q3"
  "2024Q4"
  "2025Q1"
  "2025Q2"
  "2025Q3"
  "2025Q4"
  "2026Q1"
)

for label in "${quarters[@]}"; do
  input_file="$INPUT_DIR/${label}.json"
  output_file="$OUTPUT_DIR/${label}.om"

  if [[ ! -f "$input_file" ]]; then
    echo "warning: skipping missing input $input_file" >&2
    continue
  fi

  echo "Converting $input_file -> $output_file" >&2
  uv run --script "$SCRIPT_DIR/json_to_openmetrics.py" \
    --input "$input_file" \
    --output "$output_file"
done

echo "Done. Wrote OpenMetrics files to $OUTPUT_DIR" >&2
