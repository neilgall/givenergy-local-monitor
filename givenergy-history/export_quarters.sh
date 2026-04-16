#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${GIVENERGY_API_KEY:-}" ]]; then
  echo "error: GIVENERGY_API_KEY is not set" >&2
  exit 2
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT_DIR="${1:-$SCRIPT_DIR}"

mkdir -p "$OUTPUT_DIR"

quarters=(
  "2022Q1 2022-01-01T00:00:00Z 2022-03-31T23:59:59Z"
  "2022Q2 2022-04-01T00:00:00Z 2022-06-30T23:59:59Z"
  "2022Q3 2022-07-01T00:00:00Z 2022-09-30T23:59:59Z"
  "2022Q4 2022-10-01T00:00:00Z 2022-12-31T23:59:59Z"
  "2023Q1 2023-01-01T00:00:00Z 2023-03-31T23:59:59Z"
  "2023Q2 2023-04-01T00:00:00Z 2023-06-30T23:59:59Z"
  "2023Q3 2023-07-01T00:00:00Z 2023-09-30T23:59:59Z"
  "2023Q4 2023-10-01T00:00:00Z 2023-12-31T23:59:59Z"
  "2024Q1 2024-01-01T00:00:00Z 2024-03-31T23:59:59Z"
  "2024Q2 2024-04-01T00:00:00Z 2024-06-30T23:59:59Z"
  "2024Q3 2024-07-01T00:00:00Z 2024-09-30T23:59:59Z"
  "2024Q4 2024-10-01T00:00:00Z 2024-12-31T23:59:59Z"
  "2025Q1 2025-01-01T00:00:00Z 2025-03-31T23:59:59Z"
  "2025Q2 2025-04-01T00:00:00Z 2025-06-30T23:59:59Z"
  "2025Q3 2025-07-01T00:00:00Z 2025-09-30T23:59:59Z"
  "2025Q4 2025-10-01T00:00:00Z 2025-12-31T23:59:59Z"
  "2026Q1 2026-01-01T00:00:00Z 2026-03-31T23:59:59Z"
)

for item in "${quarters[@]}"; do
  read -r label start end <<<"$item"
  output_file="$OUTPUT_DIR/${label}.json"

  echo "Exporting $label -> $output_file" >&2
  uv run --script "$SCRIPT_DIR/export_givenergy_history.py" \
    --api-key "$GIVENERGY_API_KEY" \
    --start "$start" \
    --end "$end" \
    --output "$output_file"
done

echo "Done. Wrote quarterly JSON files to $OUTPUT_DIR" >&2
