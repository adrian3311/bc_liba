#!/usr/bin/env python3
"""Solcast fetcher: vyber dat podla miesta, intervalu a typu dat (output parameters)."""

from __future__ import annotations

import argparse
import csv
import os
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode

import requests

SOLCAST_BASE_URL = "https://api.solcast.com.au/data/historic"
GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
DEFAULT_OUTPUT_PARAMETERS = "ghi,dni,dhi,air_temp"


def parse_date(value: str) -> datetime:
    try:
        return datetime.strptime(value, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError(f"Neplatny datum '{value}', pouzi YYYY-MM-DD") from exc


def resolve_city_to_coords(city: str, timeout: int = 20) -> tuple[float, float, str]:
    params = {"name": city, "count": 1, "language": "sk", "format": "json"}
    resp = requests.get(GEOCODE_URL, params=params, timeout=timeout)
    resp.raise_for_status()
    payload = resp.json()
    results = payload.get("results") or []
    if not results:
        raise ValueError(f"Mesto '{city}' sa nenaslo.")

    best = results[0]
    return float(best["latitude"]), float(best["longitude"]), str(best.get("name", city))


def build_duration(start_date: str, end_date: str) -> str:
    start_dt = parse_date(start_date)
    end_dt = parse_date(end_date)
    if start_dt > end_dt:
        raise ValueError("start-date musi byt mensi alebo rovny end-date")
    days = (end_dt - start_dt).days + 1
    return f"P{days}D"


def build_request(
    latitude: float,
    longitude: float,
    start_date: str,
    end_date: str,
    output_parameters: list[str],
    data_type: str,
    api_key: str,
) -> tuple[str, dict]:
    url = f"{SOLCAST_BASE_URL}/{data_type}"
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "start": f"{start_date}T00:00:00Z",
        "duration": build_duration(start_date, end_date),
        "output_parameters": ",".join(output_parameters),
        "format": "json",
        "api_key": api_key,
    }
    return url, params


def fetch_prediction_data(
    latitude: float,
    longitude: float,
    start_date: str,
    end_date: str,
    output_parameters: list[str],
    data_type: str,
    api_key: str,
    timeout: int = 40,
) -> tuple[dict, str]:
    url, params = build_request(
        latitude=latitude,
        longitude=longitude,
        start_date=start_date,
        end_date=end_date,
        output_parameters=output_parameters,
        data_type=data_type,
        api_key=api_key,
    )
    resp = requests.get(url, params=params, timeout=timeout)
    if resp.status_code != 200:
        raise RuntimeError(f"HTTP {resp.status_code}: {resp.text}")
    return resp.json(), resp.url


def payload_to_rows(payload: dict, output_parameters: list[str]) -> list[dict]:
    records = payload.get("estimated_actuals") or payload.get("forecasts") or []
    rows: list[dict] = []
    for item in records:
        row = {"date": item.get("period_end"), "period": item.get("period")}
        for field in output_parameters:
            row[field] = item.get(field)
        rows.append(row)
    return rows


def print_rows(rows: list[dict]) -> None:
    if not rows:
        print("No data.")
        return

    headers = list(rows[0].keys())
    widths = {h: max(len(h), max(len(str(r.get(h, ""))) for r in rows)) for h in headers}
    print(" | ".join(f"{h:<{widths[h]}}" for h in headers))
    print("-+-".join("-" * widths[h] for h in headers))
    for row in rows:
        print(" | ".join(f"{str(row.get(h, '')):<{widths[h]}}" for h in headers))


def save_csv(rows: list[dict], output_path: str) -> Path:
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        out.write_text("", encoding="utf-8")
        return out

    headers = list(rows[0].keys())
    with out.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)
    return out


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Solcast: data podla miesta, intervalu a typu dat")
    parser.add_argument("--city", default="", help="Mesto, napr. Zilina")
    parser.add_argument("--lat", type=float, default=None, help="Latitude (volitelne)")
    parser.add_argument("--lon", type=float, default=None, help="Longitude (volitelne)")
    parser.add_argument("--start-date", required=True, help="Datum od vo formate YYYY-MM-DD")
    parser.add_argument("--end-date", required=True, help="Datum do vo formate YYYY-MM-DD")
    parser.add_argument(
        "--output-parameters",
        "--fields",
        "--data-type",
        "--typ-dat",
        default=DEFAULT_OUTPUT_PARAMETERS,
        dest="output_parameters",
        help="CSV zoznam parametrov, napr. ghi,dni,dhi,air_temp",
    )
    parser.add_argument(
        "--dataset-type",
        "--type",
        default="radiation_and_weather",
        dest="dataset_type",
        help="Solcast endpoint typ, default radiation_and_weather",
    )
    parser.add_argument(
        "--api-key",
        default=os.getenv("SOLCAST_API_KEY", ""),
        help="API kluc (alebo env SOLCAST_API_KEY)",
    )
    parser.add_argument("--output-csv", default="", help="Volitelny vystupny CSV subor")
    parser.add_argument("--dry-run", action="store_true", help="Len vypise request URL/parametre")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        parse_date(args.start_date)
        parse_date(args.end_date)
        build_duration(args.start_date, args.end_date)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    fields = [p.strip() for p in args.output_parameters.split(",") if p.strip()]
    if not fields:
        print("Musis zadat aspon jeden output parameter.", file=sys.stderr)
        return 2

    if args.lat is not None and args.lon is not None:
        lat, lon = args.lat, args.lon
        location_label = f"{lat},{lon}"
    elif args.city.strip():
        try:
            lat, lon, resolved_name = resolve_city_to_coords(args.city.strip())
        except (requests.RequestException, ValueError) as exc:
            print(f"Chyba pri geokodovani: {exc}", file=sys.stderr)
            return 1
        location_label = resolved_name
    else:
        print("Zadaj --city alebo dvojicu --lat a --lon.", file=sys.stderr)
        return 2

    if not args.api_key and not args.dry_run:
        print("Chyba: zadaj --api-key alebo nastav SOLCAST_API_KEY", file=sys.stderr)
        return 2

    req_url, req_params = build_request(
        latitude=lat,
        longitude=lon,
        start_date=args.start_date,
        end_date=args.end_date,
        output_parameters=fields,
        data_type=args.dataset_type,
        api_key=args.api_key or "YOUR_API_KEY",
    )

    if args.dry_run:
        print("[dry-run] URL:")
        print(f"{req_url}?{urlencode(req_params)}")
        return 0

    try:
        payload, request_url = fetch_prediction_data(
            latitude=lat,
            longitude=lon,
            start_date=args.start_date,
            end_date=args.end_date,
            output_parameters=fields,
            data_type=args.dataset_type,
            api_key=args.api_key,
        )
    except (requests.RequestException, RuntimeError) as exc:
        print(f"Chyba pri stahovani dat: {exc}", file=sys.stderr)
        return 1

    rows = payload_to_rows(payload, fields)

    print(f"Mesto: {location_label} (lat={lat}, lon={lon})")
    print(f"Obdobie: {args.start_date} -> {args.end_date}")
    print(f"Typ dat: {', '.join(fields)} | Dataset: {args.dataset_type} | Rezim: hourly")
    print(f"URL: {request_url}")
    print(f"Zaznamov: {len(rows)}")
    print_rows(rows)

    if args.output_csv:
        out = save_csv(rows, args.output_csv)
        print(f"CSV ulozene: {out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
