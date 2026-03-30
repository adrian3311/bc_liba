"""Skript na ziskanie predikcnych dat z MeteoSource API."""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests

BASE_URL = "https://www.meteosource.com/api/v1"


def parse_date(value: str) -> str:
    """Validuj datum vo formate YYYY-MM-DD."""
    try:
        datetime.strptime(value, "%Y-%m-%d")
        return value
    except ValueError as exc:
        raise ValueError(f"Neplatny format datumu: {value}. Pouzi YYYY-MM-DD") from exc


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ziskaj predikcne data z MeteoSource API.")
    parser.add_argument("--city", required=True, help="Nazov mesta (napr. Zilina)")
    parser.add_argument("--start-date", required=True, help="Datum od (YYYY-MM-DD)")
    parser.add_argument("--end-date", required=True, help="Datum do (YYYY-MM-DD)")
    parser.add_argument("--mode", choices=["hourly", "daily"], default="daily", help="Rezim: hourly alebo daily")
    parser.add_argument("--hourly", default="temperature,wind_speed,cloud_cover,precipitation_sum", help="Hodinove premenne (csv)")
    parser.add_argument("--daily", default="temperature,precipitation_sum", help="Denne premenne (csv)")
    parser.add_argument("--api-key", default=os.getenv("METEOSOURCE_API_KEY", ""), help="API kluc alebo env METEOSOURCE_API_KEY")
    parser.add_argument("--output-csv", default="", help="Volitelny vystupny CSV subor")
    parser.add_argument("--dry-run", action="store_true", help="Iba vypise URL bez stahovania dat")
    return parser.parse_args()


def find_place(city: str, api_key: str) -> tuple[str, str, float | None, float | None]:
    """Najde place_id pre mesto cez find_places endpoint."""
    url = f"{BASE_URL}/free/find_places"
    params = {
        "text": city,
        "key": api_key,
    }

    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    if not isinstance(data, list) or len(data) == 0:
        raise ValueError(f"Mesto '{city}' sa nepodarilo najst v MeteoSource.")

    place = data[0]
    place_id = place.get("place_id")
    name = place.get("name", city)
    lat = place.get("lat")
    lon = place.get("lon")

    return place_id, name, lat, lon


def fetch_daily_data(place_id: str, api_key: str) -> tuple[dict, str]:
    """Stiahne denne data pre miesto."""
    url = f"{BASE_URL}/free/point"
    params = {
        "place_id": place_id,
        "sections": "daily",
        "key": api_key,
    }

    final_url = requests.Request("GET", url, params=params).prepare().url or url
    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json(), final_url


def fetch_hourly_data(place_id: str, api_key: str) -> tuple[dict, str]:
    """Stiahne hodinove data pre miesto."""
    url = f"{BASE_URL}/free/point"
    params = {
        "place_id": place_id,
        "sections": "hourly",
        "key": api_key,
    }

    final_url = requests.Request("GET", url, params=params).prepare().url or url
    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json(), final_url


def extract_daily_rows(payload: dict, variables: list[str], start_date: str, end_date: str) -> list[dict]:
    """Extrakt denne riadky z payload."""
    rows: list[dict] = []
    daily = payload.get("daily", {})
    data_list = daily.get("data", [])

    for entry in data_list:
        dt = entry.get("day", "")
        if dt < start_date or dt > end_date:
            continue

        all_day = entry.get("all_day", {})
        row = {"date": dt}
        for var in variables:
            # Skus najprv v all_day sekcii
            if var in all_day:
                row[var] = all_day.get(var)
            # Ak premenna ma nested strukturu (napr. wind, cloud_cover), extrakt flat
            elif var == "temperature":
                row[var] = all_day.get("temperature")
            elif var == "temperature_min":
                row[var] = all_day.get("temperature_min")
            elif var == "temperature_max":
                row[var] = all_day.get("temperature_max")
            elif var == "wind_speed":
                wind = all_day.get("wind", {})
                row[var] = wind.get("speed")
            elif var == "cloud_cover":
                cloud = all_day.get("cloud_cover", {})
                row[var] = cloud.get("total")
            elif var == "precipitation_sum":
                precip = all_day.get("precipitation", {})
                row[var] = precip.get("total")
            else:
                row[var] = all_day.get(var)
        rows.append(row)

    return rows


def extract_hourly_rows(payload: dict, variables: list[str], start_date: str, end_date: str) -> list[dict]:
    """Extrakt hodinove riadky z payload."""
    rows: list[dict] = []
    hourly = payload.get("hourly", {})
    data_list = hourly.get("data", [])

    for entry in data_list:
        dt_full = entry.get("date", "")  # Napr. "2025-09-24T09:00:00"
        if not dt_full:
            continue
        dt = dt_full[:10]  # Vyberi iba YYYY-MM-DD cast
        if dt < start_date or dt > end_date:
            continue

        row = {"date": dt_full}
        for var in variables:
            # Hodinove premenne su vo flat strukture alebo nested
            if var in entry:
                row[var] = entry.get(var)
            elif var == "temperature":
                row[var] = entry.get("temperature")
            elif var == "wind_speed":
                wind = entry.get("wind", {})
                row[var] = wind.get("speed")
            elif var == "cloud_cover":
                cloud = entry.get("cloud_cover", {})
                row[var] = cloud.get("total")
            elif var == "precipitation_sum":
                precip = entry.get("precipitation", {})
                row[var] = precip.get("total")
            else:
                row[var] = entry.get(var)
        rows.append(row)

    return rows


def print_stats(df: pd.DataFrame, variables: list[str]) -> None:
    """Vypocitaj a vypis statistiky."""
    print(f"\n{'=' * 80}")
    print("STATISTIKY")
    print(f"{'=' * 80}")

    if df.empty:
        print("Ziadne data pre vypocet statistik.")
        return

    for var in variables:
        if var not in df.columns:
            print(f"{var:30s} | stlpec neexistuje")
            continue

        series = pd.to_numeric(df[var], errors="coerce").dropna()

        if series.empty:
            print(f"{var:30s} | bez numerickych hodnot")
            continue

        print(f"{var:30s} | Min={series.min():8.2f} | Max={series.max():8.2f} | Priemer={series.mean():8.2f}")


def main() -> int:
    args = parse_args()

    try:
        start = parse_date(args.start_date)
        end = parse_date(args.end_date)
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 2

    if start > end:
        print("start-date musi byt mensie alebo rovne end-date.", file=sys.stderr)
        return 2

    # Vyber premenne na zaklade modu
    if args.mode == "hourly":
        variables = [v.strip() for v in args.hourly.split(",") if v.strip()]
    else:
        variables = [v.strip() for v in args.daily.split(",") if v.strip()]

    if not variables:
        print("Musis zadat aspon jednu premennu.", file=sys.stderr)
        return 2

    if not args.api_key and not args.dry_run:
        print("Chyba: zadaj --api-key alebo nastav METEOSOURCE_API_KEY", file=sys.stderr)
        return 2

    if args.dry_run:
        url = requests.Request(
            "GET",
            f"{BASE_URL}/free/point",
            params={"place_id": "YOUR_PLACE_ID", "sections": args.mode, "key": args.api_key or "YOUR_API_KEY"},
        ).prepare().url
        print("[dry-run] URL:")
        print(url)
        return 0

    try:
        place_id, city_name, lat, lon = find_place(args.city, args.api_key)

        if args.mode == "hourly":
            payload, request_url = fetch_hourly_data(place_id, args.api_key)
            rows = extract_hourly_rows(payload, variables, start, end)
        else:
            payload, request_url = fetch_daily_data(place_id, args.api_key)
            rows = extract_daily_rows(payload, variables, start, end)
    except Exception as exc:
        print(f"Chyba: {exc}", file=sys.stderr)
        return 1

    df = pd.DataFrame(rows)

    print(f"\n{'=' * 80}")
    print(f"PREDIKCNE DATA (MeteoSource): {city_name}")
    print(f"{'=' * 80}")
    if lat is not None and lon is not None:
        print(f"Suradnice: lat={lat}, lon={lon}")
    print(f"Obdobie: {start} az {end} | Zaznamov: {len(df)}")
    print(f"Rezim: {args.mode}")
    print(f"Premenne: {', '.join(variables)}")
    print(f"\n{request_url}\n")

    if df.empty:
        print("Ziadne data pre zadane obdobie.")
    else:
        print("Vsetky zaznamy:")
        print(df.to_string(index=False))
        print_stats(df, variables)

    if args.output_csv:
        out = Path(args.output_csv)
        out.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(out, index=False)
        print(f"\nCSV ulozene: {out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())









