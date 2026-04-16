#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INPUT_DIR="${1:-$SCRIPT_DIR}"
OUTPUT_BASE_DIR="${2:-$SCRIPT_DIR/backfill-blocks}"
PROMTOOL_BIN="${PROMTOOL_BIN:-promtool}"
MAX_BLOCK_DURATION="${MAX_BLOCK_DURATION:-}"

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

if ! command -v "$PROMTOOL_BIN" >/dev/null 2>&1; then
  echo "error: promtool not found: $PROMTOOL_BIN" >&2
  exit 2
fi

mkdir -p "$OUTPUT_BASE_DIR"

for label in "${quarters[@]}"; do
  input_file="$INPUT_DIR/${label}.om"
  output_dir="$OUTPUT_BASE_DIR/${label}"

  if [[ ! -f "$input_file" ]]; then
    echo "warning: skipping missing input $input_file" >&2
    continue
  fi

  mkdir -p "$output_dir"
  echo "Backfilling $input_file -> $output_dir" >&2

  if [[ -n "$MAX_BLOCK_DURATION" ]]; then
    "$PROMTOOL_BIN" tsdb create-blocks-from openmetrics \
      --max-block-duration="$MAX_BLOCK_DURATION" \
      "$input_file" \
      "$output_dir"
  else
    "$PROMTOOL_BIN" tsdb create-blocks-from openmetrics \
      "$input_file" \
      "$output_dir"
  fi
done

echo "Done. Wrote TSDB blocks under $OUTPUT_BASE_DIR" >&2
