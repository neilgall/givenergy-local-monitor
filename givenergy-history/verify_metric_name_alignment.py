#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# ///

"""
Verify that live exporter metric names match backfilled OpenMetrics metric names.

Examples:
  uv run --script verify_metric_name_alignment.py \
    --backfill-file ./2022Q1.om \
    --live-url http://localhost:9100/metrics

  uv run --script verify_metric_name_alignment.py \
    --backfill-file ./2022Q1.om \
    --live-file ./live-metrics.txt
"""

from __future__ import annotations

import argparse
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path


METRIC_RE = re.compile(r"^[a-zA-Z_:][a-zA-Z0-9_:]*$")


def parse_metric_names(text: str, prefix: str) -> set[str]:
    names: set[str] = set()

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        # OpenMetrics/Prometheus comment lines may declare metric families.
        if line.startswith("#"):
            if line.startswith("# TYPE ") or line.startswith("# HELP "):
                parts = line.split()
                if len(parts) >= 3:
                    candidate = parts[2]
                    if candidate.startswith(prefix) and METRIC_RE.match(candidate):
                        names.add(candidate)
            continue

        token = line.split()[0]
        metric_name = token.split("{", 1)[0]
        if metric_name.startswith(prefix) and METRIC_RE.match(metric_name):
            names.add(metric_name)

    return names


def read_text_file(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def fetch_text(url: str, timeout: float) -> str:
    request = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read().decode("utf-8", errors="replace")
    except urllib.error.URLError as exc:
        raise RuntimeError(f"failed to fetch live metrics from {url}: {exc}") from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Compare metric names in a backfill OpenMetrics file against live exporter metrics."
        )
    )
    parser.add_argument(
        "--backfill-file",
        required=True,
        type=Path,
        help="Path to backfill OpenMetrics file (e.g. 2022Q1.om)",
    )
    parser.add_argument(
        "--live-url",
        default="http://localhost:9100/metrics",
        help="Exporter metrics URL when --live-file is not provided",
    )
    parser.add_argument(
        "--live-file",
        type=Path,
        help="Optional path to a saved live metrics text file instead of scraping --live-url",
    )
    parser.add_argument(
        "--prefix",
        default="givenergy_",
        help="Metric name prefix to compare (default: givenergy_)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=10.0,
        help="HTTP timeout in seconds for --live-url (default: 10)",
    )
    parser.add_argument(
        "--show-extra",
        action="store_true",
        help="Also print metric names that exist live but not in backfill",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()

    if not args.backfill_file.exists():
        print(f"error: backfill file does not exist: {args.backfill_file}", file=sys.stderr)
        return 2

    backfill_text = read_text_file(args.backfill_file)
    backfill_metrics = parse_metric_names(backfill_text, args.prefix)

    if args.live_file is not None:
        if not args.live_file.exists():
            print(f"error: live file does not exist: {args.live_file}", file=sys.stderr)
            return 2
        live_text = read_text_file(args.live_file)
        live_source = str(args.live_file)
    else:
        try:
            live_text = fetch_text(args.live_url, args.timeout)
        except RuntimeError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        live_source = args.live_url

    live_metrics = parse_metric_names(live_text, args.prefix)

    missing_in_live = sorted(backfill_metrics - live_metrics)
    extra_in_live = sorted(live_metrics - backfill_metrics)

    print(f"Backfill source: {args.backfill_file}")
    print(f"Live source: {live_source}")
    print(f"Compared prefix: {args.prefix}")
    print(f"Backfill metric names: {len(backfill_metrics)}")
    print(f"Live metric names: {len(live_metrics)}")

    if missing_in_live:
        print("\nMissing in live (present in backfill):")
        for name in missing_in_live:
            print(name)
    else:
        print("\nNo missing metric names in live output.")

    if args.show_extra:
        if extra_in_live:
            print("\nExtra in live (not present in backfill):")
            for name in extra_in_live:
                print(name)
        else:
            print("\nNo extra metric names in live output.")

    return 1 if missing_in_live else 0


if __name__ == "__main__":
    raise SystemExit(main())
