"""
Skript na ziskanie predikcnych dat z Visual Crossing Timeline API.
Dokumentacia: https://www.visualcrossing.com/resources/documentation/weather-api/timeline-weather-api/

URL format:
  https://weather.visualcrossing.com/.../timeline/[location]/[date1]/[date2]?key=API_KEY

CLI je navrhnute co najpodobnejsie ako Open-Meteo/fetch_prediction.py.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

BASE_URL = "https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services/timeline"
DEFAULT_HOURLY = "temp,cloudcover,precip,humidity,windspeed,winddir,windgust,solarradiation,solarenergy,uvindex,conditions,visibility,pressure,dewpoint,snow,snowdepth,preciptype,feelslike,cape"
DEFAULT_DAILY  = "tempmax,tempmin,temp,precip,humidity,windspeed,winddir,windgust,solarradiation,solarenergy,uvindex,conditions,visibility,pressure,dewpoint,snow,snowdepth,preciptype,feelslike,moonrise,moonset,sunrise,sunset,moonphase,precipcover,severerisk"


def parse_date(value: str) -> str:
    """Validuj datum vo formate YYYY-MM-DD."""
    try:
        datetime.strptime(value, "%Y-%m-%d")
        return value
    except ValueError as exc:
        raise ValueError(f"Neplatny format datumu: {value}. Pouzi YYYY-MM-DD") from exc


def build_location(city: str, lat: float | None, lon: float | None) -> str:
    """Vytvori location string pre API (city alebo lat,lon)."""
    if lat is not None and lon is not None:
        return f"{lat},{lon}"
    return city


def build_url(
    location: str,
    start_date: str,
    end_date: str,
    variables: list[str],
    timezone: str,
    mode: str,
    unit_group: str,
    api_key: str,
) -> str:
    """
    Zostavi URL podla oficialnej dokumentacie:
      BASE/[location]/[date1]/[date2]?key=...&unitGroup=...&include=...
    datetime musi byt vzdy v elements (Visual Crossing to vyzaduje).
    """
    encoded_location = quote(location, safe=",")
    # datetime musi byt vzdy prve
    all_elements = ["datetime"] + [v for v in variables if v != "datetime"]
    include = "hours" if mode == "hourly" else "days"

    params = {
        "key": api_key,
        "unitGroup": unit_group,
        "include": include,
        "elements": ",".join(all_elements),
        "timezone": timezone,
        "contentType": "json",
    }
    return f"{BASE_URL}/{encoded_location}/{start_date}/{end_date}?{urlencode(params)}"


def fetch_prediction_data(
    location: str,
    start_date: str,
    end_date: str,
    variables: list[str],
    timezone: str,
    mode: str,
    unit_group: str,
    api_key: str,
) -> tuple[dict, str]:
    """Stiahne predikcne data z Visual Crossing Timeline API."""
    url = build_url(location, start_date, end_date, variables, timezone, mode, unit_group, api_key)
    req = Request(url, headers={"User-Agent": "bc_liba/1.0"})
    try:
        with urlopen(req, timeout=30) as resp:
            payload = resp.read().decode("utf-8")
        return json.loads(payload), url
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {body}") from exc
    except URLError as exc:
        raise RuntimeError(f"Network chyba: {exc}") from exc


def payload_to_rows(payload: dict, variables: list[str], mode: str) -> list[dict]:
    """Konvertuje API odpoved na zoznam riadkov podobne ako DataFrame rows."""
    rows: list[dict] = []
    days = payload.get("days", [])

    if mode == "hourly":
        for day in days:
            day_date = day.get("datetime")
            for hour in day.get("hours", []) or []:
                row = {"date": f"{day_date} {hour.get('datetime', '')}"}
                for var in variables:
                    row[var] = hour.get(var)
                rows.append(row)
    else:
        for day in days:
            row = {"date": day.get("datetime")}
            for var in variables:
                row[var] = day.get(var)
            rows.append(row)

    return rows


def save_csv(rows: list[dict], output_path: str) -> Path:
    """Ulozi rows do CSV suboru."""
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        out.write_text("", encoding="utf-8")
        return out
    columns = ["date", *[k for k in rows[0].keys() if k != "date"]]
    with out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    return out


def print_rows(rows: list[dict]) -> None:
    """Vypise rows ako textovu tabulku."""
    if not rows:
        print("Pre zadane obdobie sa nenasli ziadne data.")
        return
    headers = list(rows[0].keys())
    widths = {h: max(len(h), max(len(str(r.get(h, ""))) for r in rows)) for h in headers}
    print(" | ".join(f"{h:<{widths[h]}}" for h in headers))
    print("-+-".join("-" * widths[h] for h in headers))
    for row in rows:
        print(" | ".join(f"{str(row.get(h, '')):<{widths[h]}}" for h in headers))


def print_stats(rows: list[dict], variables: list[str]) -> None:
    """Vypise statistiky pre numericke premenne."""
    print(f"\n{'=' * 60}")
    print("STATISTIKY")
    print(f"{'=' * 60}")
    if not rows:
        print("Bez dat na statistiky.")
        return
    for var in variables:
        vals = [float(r[var]) for r in rows if isinstance(r.get(var), (int, float))]
        if vals:
            print(f"\n{var}: Min={min(vals):.2f} | Max={max(vals):.2f} | Priemer={sum(vals)/len(vals):.2f}")
        else:
            print(f"\n{var}: bez numerickych hodnot")


def parse_args() -> argparse.Namespace:
    """Parsuj CLI argumenty."""
    parser = argparse.ArgumentParser(
        description="Ziskaj predikcne data z Visual Crossing Timeline API.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Priklady:
  python fetch_prediction.py --city Zilina --start-date 2026-03-30 --end-date 2026-04-01 --api-key KEY
  python fetch_prediction.py --city Bratislava --start-date 2026-03-30 --end-date 2026-03-30 --mode daily --api-key KEY
  python fetch_prediction.py --city Zilina --start-date 2026-03-30 --end-date 2026-03-30 --dry-run
        """,
    )
    parser.add_argument("--city",       default="Zilina",  help="Mesto (napr. Zilina)")
    parser.add_argument("--lat",        type=float, default=None, help="Volitelne latitude")
    parser.add_argument("--lon",        type=float, default=None, help="Volitelne longitude")
    parser.add_argument("--start-date", required=True,     help="Datum od (YYYY-MM-DD)")
    parser.add_argument("--end-date",   required=True,     help="Datum do (YYYY-MM-DD)")
    parser.add_argument("--mode",       choices=["hourly", "daily"], default="hourly", help="Rezolucia dat")
    parser.add_argument("--hourly",     default=DEFAULT_HOURLY, help="Hodinove premenne (csv)")
    parser.add_argument("--daily",      default=DEFAULT_DAILY,  help="Denne premenne (csv)")
    parser.add_argument("--timezone",   default="Europe/Bratislava", help="Casova zona (napr. Europe/Bratislava, UTC)")
    parser.add_argument("--unit-group", default="metric",  choices=["metric", "us", "uk", "base"], help="Jednotky")
    parser.add_argument("--api-key",    default=os.getenv("VISUAL_CROSSING_API_KEY", ""),
                        help="API kluc (alebo env VISUAL_CROSSING_API_KEY)")
    parser.add_argument("--output-csv", default="",        help="Volitelny vystupny CSV subor")
    parser.add_argument("--dry-run",    action="store_true", help="Iba vypise URL bez stahovania dat")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        start = parse_date(args.start_date)
        end   = parse_date(args.end_date)
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 2

    if start > end:
        print("start-date musi byt mensie alebo rovne end-date.", file=sys.stderr)
        return 2

    variables = [v.strip() for v in (args.hourly if args.mode == "hourly" else args.daily).split(",") if v.strip()]
    if not variables:
        print("Musis zadat aspon jednu premennu.", file=sys.stderr)
        return 2

    location = build_location(args.city, args.lat, args.lon)

    if not args.api_key and not args.dry_run:
        print("Chyba: zadaj --api-key alebo nastav VISUAL_CROSSING_API_KEY", file=sys.stderr)
        return 2

    # dry-run: zostavime URL a skoncime (bez volania API)
    if args.dry_run:
        url = build_url(location, start, end, variables, args.timezone, args.mode, args.unit_group,
                        args.api_key or "YOUR_API_KEY")
        print("[dry-run] URL:")
        print(url)
        return 0

    try:
        payload, request_url = fetch_prediction_data(
            location, start, end, variables,
            args.timezone, args.mode, args.unit_group, args.api_key,
        )
    except RuntimeError as exc:
        print(f"Chyba pri stahovani dat: {exc}", file=sys.stderr)
        return 1

    city_name = payload.get("resolvedAddress", location)
    rows = payload_to_rows(payload, variables, args.mode)

    print(f"\n{'=' * 60}")
    print(f"PREDIKCNE DATA (Visual Crossing): {city_name}")
    print(f"{'=' * 60}")
    print(f"Obdobie: {start} az {end} | Zaznamov: {len(rows)}")
    print(f"Rezim:    {args.mode}")
    print(f"Premenne: {', '.join(variables)}")
    print("\nVsetky zaznamy:")
    print_rows(rows)
    print_stats(rows, variables)

    if args.output_csv:
        out = save_csv(rows, args.output_csv)
        print(f"\nCSV ulozene: {out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())


