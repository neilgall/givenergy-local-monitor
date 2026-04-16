#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# ///

"""
Export historical metrics from the GivEnergy Cloud API to JSON.

Usage example:
  uv run --script export_givenergy_history.py \
    --api-key "$GIVENERGY_API_KEY" \
    --start "2025-01-01T00:00:00Z" \
    --end "2025-01-31T23:59:59Z" \
        --output ./givenergy-history.json
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

BASE_URL = "https://api.givenergy.cloud/v1"


@dataclass(frozen=True)
class Inverter:
    serial: str


class ApiHTTPError(Exception):
    """Raised when an API request returns an HTTP error status."""


class ApiClient:
    """Tiny JSON API client using the Python standard library."""

    def __init__(self, base_url: str, api_key: str, timeout: float) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def get_json(self, path: str, params: dict[str, Any]) -> Any:
        full_url = f"{self.base_url}/{path.lstrip('/')}"
        query = urllib.parse.urlencode(params)
        if query:
            full_url = f"{full_url}?{query}"

        request = urllib.request.Request(full_url, headers=self.headers, method="GET")

        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                body = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            body = ""
            try:
                raw = exc.read()
                if isinstance(raw, bytes):
                    body = raw.decode("utf-8", errors="replace")
            except Exception:
                body = ""

            detail = ""
            if body:
                try:
                    err = json.loads(body)
                    detail = err.get("message") if isinstance(err, dict) else ""
                except json.JSONDecodeError:
                    detail = body[:200]

            if detail:
                raise ApiHTTPError(f"HTTP {exc.code}: {exc.reason} ({detail})") from exc
            raise ApiHTTPError(f"HTTP {exc.code}: {exc.reason}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Network error calling {full_url}: {exc.reason}") from exc

        try:
            return json.loads(body)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Invalid JSON response from {full_url}") from exc


def parse_timestamp(value: str) -> datetime:
    """Parse an ISO-8601 timestamp into a UTC datetime."""
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"

    try:
        dt = datetime.fromisoformat(text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"Invalid timestamp '{value}'. Use ISO-8601, e.g. 2026-01-01T00:00:00Z"
        ) from exc

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def normalize_payload(payload: Any) -> list[dict[str, Any]]:
    """Return a list of records from API payload variants."""
    if isinstance(payload, list):
        return [p for p in payload if isinstance(p, dict)]

    if isinstance(payload, dict):
        if isinstance(payload.get("data"), list):
            return [p for p in payload["data"] if isinstance(p, dict)]
        if isinstance(payload.get("data"), dict):
            return [payload["data"]]

    return []


def get_meta(payload: Any) -> dict[str, Any]:
    """Return pagination meta object if present."""
    if isinstance(payload, dict) and isinstance(payload.get("meta"), dict):
        return payload["meta"]
    return {}


def discover_inverters(client: ApiClient) -> list[Inverter]:
    """Discover inverter serials from communication devices and sites."""
    serials: set[str] = set()

    # Primary discovery path from docs.
    page = 1
    while True:
        payload = client.get_json("/communication-device", {"page": page, "pageSize": 100})
        rows = normalize_payload(payload)
        if not rows:
            break

        for row in rows:
            inverter = row.get("inverter") if isinstance(row, dict) else None
            serial = None
            if isinstance(inverter, dict):
                serial = inverter.get("serial")
            if isinstance(serial, str) and serial.strip():
                serials.add(serial.strip())

        meta = get_meta(payload)
        current = meta.get("current_page")
        last = meta.get("last_page")
        if isinstance(current, int) and isinstance(last, int) and current >= last:
            break
        page += 1

    # Fallback discovery from sites endpoint, in case communication devices are absent.
    if not serials:
        page = 1
        while True:
            payload = client.get_json("/site", {"page": page, "pageSize": 100})
            rows = normalize_payload(payload)
            if not rows:
                break

            for row in rows:
                if not isinstance(row, dict):
                    continue
                products = row.get("products")
                if not isinstance(products, list):
                    continue
                for product in products:
                    if not isinstance(product, dict):
                        continue
                    data = product.get("data")
                    if not isinstance(data, list):
                        continue
                    for inverter in data:
                        if not isinstance(inverter, dict):
                            continue
                        serial = inverter.get("serial")
                        if isinstance(serial, str) and serial.strip():
                            serials.add(serial.strip())

            meta = get_meta(payload)
            current = meta.get("current_page")
            last = meta.get("last_page")
            if isinstance(current, int) and isinstance(last, int) and current >= last:
                break
            page += 1

    if not serials:
        raise RuntimeError(
            "No inverters discovered for this API key. "
            "Check key permissions and account access."
        )

    return [Inverter(serial=s) for s in sorted(serials)]


def daterange(start: datetime, end: datetime) -> Iterable[datetime]:
    """Yield one UTC date boundary per day inclusive."""
    day = datetime(start.year, start.month, start.day, tzinfo=timezone.utc)
    last = datetime(end.year, end.month, end.day, tzinfo=timezone.utc)
    while day <= last:
        yield day
        day += timedelta(days=1)


def fetch_data_points_rows(
    client: ApiClient,
    serial: str,
    start: datetime,
    end: datetime,
    page_size: int,
) -> list[dict[str, Any]]:
    """Fetch data points for one inverter across the time window."""
    all_rows: list[dict[str, Any]] = []

    # Docs endpoint: inverter/{serial}/data-points/{date}
    for day in daterange(start, end):
        date_text = day.date().isoformat()
        path = f"/inverter/{serial}/data-points/{date_text}"
        page = 1
        while True:
            try:
                payload = client.get_json(
                    path,
                    {"page": page, "pageSize": page_size},
                )
            except ApiHTTPError:
                break

            rows = normalize_payload(payload)
            if not rows:
                break

            all_rows.extend(rows)

            meta = get_meta(payload)
            current = meta.get("current_page")
            last = meta.get("last_page")
            if isinstance(current, int) and isinstance(last, int) and current >= last:
                break
            page += 1

    return all_rows


def filter_rows_by_window(
    rows: list[dict[str, Any]],
    start: datetime,
    end: datetime,
) -> list[dict[str, Any]]:
    """Keep only records whose timestamps fall within the requested window."""
    filtered_rows: list[dict[str, Any]] = []
    for row in rows:
        ts_raw = row.get("time") or row.get("timestamp") or row.get("datetime")
        ts: datetime | None = None
        if isinstance(ts_raw, str):
            try:
                ts = parse_timestamp(ts_raw)
            except argparse.ArgumentTypeError:
                ts = None

        # Keep only records in the requested window when timestamps exist.
        if ts is not None and (ts < start or ts > end):
            continue

        filtered_rows.append(row)

    return filtered_rows


def write_json(output_path: Path, payload: dict[str, Any]) -> None:
    """Write the collected payload to a JSON file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=True)
        fh.write("\n")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Collect historical GivEnergy API metrics and export raw JSON."
    )
    parser.add_argument("--api-key", required=True, help="GivEnergy API key")
    parser.add_argument(
        "--start",
        required=True,
        type=parse_timestamp,
        help="Start timestamp (ISO-8601), e.g. 2026-01-01T00:00:00Z",
    )
    parser.add_argument(
        "--end",
        required=True,
        type=parse_timestamp,
        help="End timestamp (ISO-8601), e.g. 2026-01-31T23:59:59Z",
    )
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="Destination JSON file path",
    )
    parser.add_argument(
        "--base-url",
        default=BASE_URL,
        help=f"Base API URL (default: {BASE_URL})",
    )
    parser.add_argument(
        "--timeout",
        default=30.0,
        type=float,
        help="HTTP timeout in seconds (default: 30)",
    )
    parser.add_argument(
        "--page-size",
        default=200,
        type=int,
        help="Page size for paginated API requests (default: 200)",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()

    if args.start > args.end:
        print("error: --start must be earlier than or equal to --end", file=sys.stderr)
        return 2

    if args.page_size <= 0:
        print("error: --page-size must be greater than 0", file=sys.stderr)
        return 2

    inverter_payloads: list[dict[str, Any]] = []

    client = ApiClient(base_url=args.base_url, api_key=args.api_key, timeout=args.timeout)
    inverters = discover_inverters(client)

    print(f"Discovered {len(inverters)} inverter(s)", file=sys.stderr)

    for inverter in inverters:
        try:
            raw_rows = fetch_data_points_rows(
                client,
                serial=inverter.serial,
                start=args.start,
                end=args.end,
                page_size=args.page_size,
            )
        except (ApiHTTPError, RuntimeError) as exc:
            print(
                f"warning: failed to fetch data-points for {inverter.serial}: {exc}",
                file=sys.stderr,
            )
            continue

        filtered_rows = filter_rows_by_window(
            rows=raw_rows,
            start=args.start,
            end=args.end,
        )
        inverter_payloads.append(
            {
                "serial": inverter.serial,
                "dataset": "data-points",
                "rows": filtered_rows,
            }
        )
        print(
            f"Fetched {len(filtered_rows)} rows for {inverter.serial} (data-points)",
            file=sys.stderr,
        )

    output_payload = {
        "start": args.start.isoformat(),
        "end": args.end.isoformat(),
        "base_url": args.base_url,
        "dataset": "data-points",
        "inverters": inverter_payloads,
    }

    total_rows = sum(len(inverter["rows"]) for inverter in inverter_payloads)

    if total_rows == 0:
        print(
            "warning: no rows collected in the requested window; writing empty JSON payload",
            file=sys.stderr,
        )

    write_json(args.output, output_payload)
    print(f"Wrote {total_rows} rows to {args.output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
