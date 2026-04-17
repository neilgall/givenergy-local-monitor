#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INPUT_DIR="${1:-$SCRIPT_DIR/monthly-openmetrics}"
OUTPUT_BASE_DIR="${2:-$SCRIPT_DIR/backfill-blocks}"
PROMTOOL_BIN="${PROMTOOL_BIN:-promtool}"
MAX_BLOCK_DURATION="${MAX_BLOCK_DURATION:-31d}"
JOBS="${JOBS:-$(getconf _NPROCESSORS_ONLN 2>/dev/null || echo 4)}"

if ! command -v "$PROMTOOL_BIN" >/dev/null 2>&1; then
  echo "error: promtool not found: $PROMTOOL_BIN" >&2
  exit 2
fi

mkdir -p "$OUTPUT_BASE_DIR"

shopt -s nullglob
inputs=("$INPUT_DIR"/*.om)
shopt -u nullglob

if [[ ${#inputs[@]} -eq 0 ]]; then
  echo "error: no .om files found in $INPUT_DIR" >&2
  exit 2
fi

run_backfill() {
  local input_file="$1"
  local output_dir="$OUTPUT_BASE_DIR/$(basename "${input_file%.om}")"

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
}

running=0
failures=0

for input_file in "${inputs[@]}"; do
  run_backfill "$input_file" &
  running=$((running + 1))

  if (( running >= JOBS )); then
    if ! wait -n; then
      failures=$((failures + 1))
    fi
    running=$((running - 1))
  fi
done

while (( running > 0 )); do
  if ! wait -n; then
    failures=$((failures + 1))
  fi
  running=$((running - 1))
done

if (( failures > 0 )); then
  echo "error: $failures backfill job(s) failed" >&2
  exit 1
fi

echo "Done. Wrote TSDB blocks under $OUTPUT_BASE_DIR" >&2