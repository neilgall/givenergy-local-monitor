#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# ///

"""
Convert one GivEnergy quarterly JSON export into OpenMetrics text format.

This script expects the input schema written by export_givenergy_history.py:
{
  "inverters": [
    {
      "serial": "...",
      "rows": [{"time": "...", ...}, ...]
    }
  ]
}

Usage example:
  uv run --script json_to_openmetrics.py \
    --input ./2022Q1.json \
    --output ./2022Q1.om
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable


def parse_timestamp(value: str) -> datetime:
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"

    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def sanitize_metric_part(part: str) -> str:
    lowered = part.strip().lower()
    normalized = re.sub(r"[^a-z0-9_]", "_", lowered)
    normalized = re.sub(r"_+", "_", normalized).strip("_")
    return normalized or "value"


def to_metric_name(prefix: str, path: list[str]) -> str:
    segments = [sanitize_metric_part(prefix)] + [sanitize_metric_part(p) for p in path]
    metric = "_".join(seg for seg in segments if seg)
    if not metric:
        metric = "givenergy_value"
    if metric[0].isdigit():
        metric = f"m_{metric}"
    return metric


def escape_label_value(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


def format_labels(labels: dict[str, str]) -> str:
    if not labels:
        return ""
    ordered = sorted(labels.items())
    rendered = ",".join(f'{k}="{escape_label_value(v)}"' for k, v in ordered)
    return "{" + rendered + "}"


def iter_numeric_metrics(
    obj: Any,
    path: list[str],
    labels: dict[str, str],
) -> Iterable[tuple[str, float, dict[str, str]]]:
    if isinstance(obj, bool):
        yield (to_metric_name("givenergy", path), 1.0 if obj else 0.0, labels)
        return

    if isinstance(obj, (int, float)):
        yield (to_metric_name("givenergy", path), float(obj), labels)
        return

    if isinstance(obj, dict):
        for key in sorted(obj.keys()):
            # "array" is used as a label for PV array entries and should not be duplicated as a metric.
            if key == "array":
                continue
            next_obj = obj[key]
            yield from iter_numeric_metrics(next_obj, path + [key], labels)
        return

    if isinstance(obj, list):
        for index, item in enumerate(obj):
            if isinstance(item, dict) and "array" in item:
                array_id = item.get("array")
                next_labels = dict(labels)
                next_labels["array"] = str(array_id)
                yield from iter_numeric_metrics(item, path, next_labels)
                continue

            next_labels = dict(labels)
            next_labels["index"] = str(index)
            yield from iter_numeric_metrics(item, path, next_labels)


def iter_row_samples(serial: str, row: dict[str, Any]) -> Iterable[tuple[str, float, dict[str, str]]]:
    base_labels = {"inverter_serial": serial}

    status = row.get("status")
    if isinstance(status, str) and status.strip():
        status_labels = dict(base_labels)
        status_labels["status"] = status.strip()
        yield ("givenergy_status", 1.0, status_labels)

    if isinstance(row.get("is_metered"), bool):
        yield (
            "givenergy_is_metered",
            1.0 if row["is_metered"] else 0.0,
            dict(base_labels),
        )

    for key in ("power", "today", "total"):
        if key in row:
            yield from iter_numeric_metrics(row[key], [key], dict(base_labels))


def freeze_labels(labels: dict[str, str]) -> tuple[tuple[str, str], ...]:
    """Convert labels to a deterministic tuple for sorting/grouping."""
    return tuple(sorted(labels.items()))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Convert one GivEnergy JSON export file to OpenMetrics for promtool."
    )
    parser.add_argument("--input", required=True, type=Path, help="Input JSON file path")
    parser.add_argument("--output", type=Path, help="Output OpenMetrics file path")
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Output directory for sharded OpenMetrics files",
    )
    parser.add_argument(
        "--split-period",
        choices=("none", "month"),
        default="none",
        help="Write a single file or split output into monthly files",
    )
    return parser


def bucket_key(ts: datetime, split_period: str) -> str:
    if split_period == "month":
        return ts.strftime("%Y-%m")
    return "single"


def resolve_output_paths(args: argparse.Namespace, buckets: set[str]) -> dict[str, Path]:
    if args.split_period == "none":
        if args.output is None:
            raise ValueError("--output is required when --split-period=none")
        if args.output_dir is not None:
            raise ValueError("--output-dir cannot be used when --split-period=none")
        return {"single": args.output}

    if args.output_dir is None:
        raise ValueError("--output-dir is required when --split-period=month")
    if args.output is not None:
        raise ValueError("--output cannot be used when --split-period=month")

    return {bucket: args.output_dir / f"{bucket}.om" for bucket in sorted(buckets)}


def write_samples(output_path: Path, sample_rows: list[tuple[str, tuple[tuple[str, str], ...], int, float]]) -> tuple[int, int]:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    written_samples = 0
    written_types: set[str] = set()

    sample_rows.sort(key=lambda item: (item[0], item[1], item[2]))

    with output_path.open("w", encoding="utf-8") as out:
        for metric, frozen_labels, ts_sec, value in sample_rows:
            if metric not in written_types:
                out.write(f"# TYPE {metric} gauge\n")
                written_types.add(metric)

            label_text = format_labels(dict(frozen_labels))
            out.write(f"{metric}{label_text} {value} {ts_sec}\n")
            written_samples += 1

        out.write("# EOF\n")

    return written_samples, len(written_types)


def main() -> int:
    args = build_parser().parse_args()

    if not args.input.exists():
        print(f"error: input file does not exist: {args.input}", file=sys.stderr)
        return 2

    try:
        with args.input.open("r", encoding="utf-8") as fh:
            payload = json.load(fh)
    except json.JSONDecodeError as exc:
        print(f"error: invalid JSON in {args.input}: {exc}", file=sys.stderr)
        return 2

    inverters = payload.get("inverters") if isinstance(payload, dict) else None
    if not isinstance(inverters, list):
        print("error: input JSON does not contain an 'inverters' list", file=sys.stderr)
        return 2

    bucketed_rows: dict[str, list[tuple[str, tuple[tuple[str, str], ...], int, float]]] = defaultdict(list)

    for inverter in inverters:
        if not isinstance(inverter, dict):
            continue

        serial = inverter.get("serial")
        rows = inverter.get("rows")
        if not isinstance(serial, str) or not isinstance(rows, list):
            continue

        for row in rows:
            if not isinstance(row, dict):
                continue

            ts_raw = row.get("time") or row.get("timestamp") or row.get("datetime")
            if not isinstance(ts_raw, str):
                continue

            try:
                ts = parse_timestamp(ts_raw)
            except ValueError:
                continue

            ts_sec = int(ts.timestamp())
            bucket = bucket_key(ts, args.split_period)

            for metric, value, labels in iter_row_samples(serial, row):
                bucketed_rows[bucket].append((metric, freeze_labels(labels), ts_sec, value))

    try:
        output_paths = resolve_output_paths(args, set(bucketed_rows.keys()) or {"single"})
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    for bucket, output_path in output_paths.items():
        written_samples, metric_count = write_samples(output_path, bucketed_rows.get(bucket, []))
        print(
            f"Wrote {written_samples} samples across {metric_count} metrics to {output_path}",
            file=sys.stderr,
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())