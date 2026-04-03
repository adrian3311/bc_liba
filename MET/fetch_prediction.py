"""
Skript na ziskanie predikcnych dat z MET Norway Locationforecast API.
Dokumentacia: https://api.met.no/doc/GettingStarted
Endpoint:     https://api.met.no/weatherapi/locationforecast/2.0/complete
"""

import argparse
import math
import time
from collections import Counter
from datetime import datetime, timezone

import requests

# MET Norway vyzaduje User-Agent s kontaktom podla ich podmienok
USER_AGENT = "bc_liba/1.0 98758927-960b-44b3-98fd-8257668c7ad6"

GEOCODING_URL = "https://nominatim.openstreetmap.org/search"
FORECAST_URL = "https://api.met.no/weatherapi/locationforecast/2.0/complete"

# Mapovanie premennych zo skriptu na kluce v odpovedi MET Norway
VARIABLE_MAP = {
    "temperature_2m":           ("instant", "air_temperature"),
    "cloud_cover":              ("instant", "cloud_area_fraction"),
    "cloud_cover_low":          ("instant", "cloud_area_fraction_low"),
    "cloud_cover_medium":       ("instant", "cloud_area_fraction_medium"),
    "cloud_cover_high":         ("instant", "cloud_area_fraction_high"),
    "wind_speed":               ("instant", "wind_speed"),
    "wind_direction":           ("instant", "wind_from_direction"),
    "wind_speed_gust":          ("instant", "wind_speed_of_gust"),
    "humidity":                 ("instant", "relative_humidity"),
    "pressure":                 ("instant", "air_pressure_at_sea_level"),
    "dew_point":                ("instant", "dew_point_temperature"),
    "fog":                      ("instant", "fog_area_fraction"),
    "uv_index":                 ("instant", "ultraviolet_index_clear_sky"),
    "precipitation_1h":         ("next_1_hours", "precipitation_amount"),
    "precipitation_6h":         ("next_6_hours", "precipitation_amount"),
    "precipitation_12h":        ("next_12_hours", "precipitation_amount"),
    "precipitation_prob_1h":    ("next_1_hours", "probability_of_precipitation"),
    "precipitation_prob_6h":    ("next_6_hours", "probability_of_precipitation"),
    "thunder_prob_1h":          ("next_1_hours", "probability_of_thunder"),
    "thunder_prob_6h":          ("next_6_hours", "probability_of_thunder"),
    "symbol_1h":                ("next_1_hours", "summary_symbol_code"),
    "symbol_6h":                ("next_6_hours", "summary_symbol_code"),
    "symbol_12h":               ("next_12_hours", "summary_symbol_code"),
}

DEFAULT_VARIABLES = "temperature_2m,cloud_cover,precipitation_1h,wind_speed,wind_direction,humidity,pressure,dew_point,uv_index,fog,wind_speed_gust,precipitation_prob_1h,thunder_prob_1h"


def resolve_city(city: str) -> tuple[float, float, str]:
    """Prevedie nazov mesta na suradnice cez Nominatim (OpenStreetMap)."""
    params = {
        "q": city,
        "format": "json",
        "limit": 1,
    }
    headers = {"User-Agent": USER_AGENT}
    resp = requests.get(GEOCODING_URL, params=params, headers=headers, timeout=10)
    resp.raise_for_status()
    results = resp.json()
    if not results:
        raise ValueError(f"Mesto '{city}' sa nenaslo v geocoding databaze.")
    r = results[0]
    return float(r["lat"]), float(r["lon"]), r.get("display_name", city)


def fetch_forecast(lat: float, lon: float, altitude: int | None = None) -> dict:
    """Stiahne kompletnu predpoved z MET Norway API."""
    params: dict = {"lat": round(lat, 4), "lon": round(lon, 4)}
    if altitude is not None:
        params["altitude"] = altitude

    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
    }

    resp = requests.get(FORECAST_URL, params=params, headers=headers, timeout=20)

    if resp.status_code == 429:
        retry_after = int(resp.headers.get("Retry-After", 60))
        print(f"Rate limit - cakam {retry_after}s...")
        time.sleep(retry_after)
        resp = requests.get(FORECAST_URL, params=params, headers=headers, timeout=20)

    resp.raise_for_status()
    return resp.json()


def extract_variable(timeseries_entry: dict, var_key: str) -> object:
    """Vyberie hodnotu premennej z jedneho casoveho zaznamu."""
    if var_key not in VARIABLE_MAP:
        return None
    period, field = VARIABLE_MAP[var_key]
    data = timeseries_entry.get("data", {})
    if period == "instant":
        return data.get("instant", {}).get("details", {}).get(field)
    else:
        block = data.get(period, {})
        if field == "precipitation_amount":
            return block.get("details", {}).get(field)
        elif field == "summary_symbol_code":
            return block.get("summary", {}).get("symbol_code")
    return None


def filter_timeseries(
    timeseries: list[dict],
    start_dt: datetime | None,
    end_dt: datetime | None,
) -> list[dict]:
    """Filtruje zaznamy podla zadaneho casoveho rozmedzia (UTC)."""
    filtered = []
    for entry in timeseries:
        time_str = entry.get("time", "")
        try:
            dt = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
        except ValueError:
            continue
        if start_dt and dt < start_dt:
            continue
        if end_dt and dt > end_dt:
            continue
        filtered.append(entry)
    return filtered


def parse_datetime(value: str) -> datetime:
    """Parsuje datum vo formate YYYY-MM-DD alebo YYYY-MM-DDTHH:MM."""
    for fmt in ("%Y-%m-%dT%H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    raise ValueError(f"Neplatny format datumu/casu: '{value}'. Pouzi YYYY-MM-DD alebo YYYY-MM-DDTHH:MM")


def parse_args():
    ap = argparse.ArgumentParser(
        description="Ziskaj predikcne data z MET Norway Locationforecast 2.0 API.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Dostupne premenne (--variables):
  {chr(10).join(f"  {k:<25} ({v[1]})" for k, v in VARIABLE_MAP.items())}

Priklady:
  python fetch_prediction.py --city Zilina --start-date 2026-03-25 --end-date 2026-03-27
  python fetch_prediction.py --city Bratislava --start-date 2026-03-25T06:00 --end-date 2026-03-25T18:00 --variables temperature_2m,cloud_cover,symbol_1h
        """,
    )
    ap.add_argument("--city", required=True, help="Nazov mesta (napr. Zilina)")
    ap.add_argument("--start-date", required=True, help="Datum/cas od (YYYY-MM-DD alebo YYYY-MM-DDTHH:MM)")
    ap.add_argument("--end-date", required=True, help="Datum/cas do (YYYY-MM-DD alebo YYYY-MM-DDTHH:MM)")
    ap.add_argument(
        "--variables",
        default=DEFAULT_VARIABLES,
        help=f"Zoznam premennych oddeleny ciarkou (predvolene: {DEFAULT_VARIABLES})",
    )
    ap.add_argument("--altitude", type=int, default=None, help="Nadmorska vyska v metroch (volitelne)")
    ap.add_argument("--dry-run", action="store_true", help="Iba zobraz URL bez stahovania dat")
    ap.add_argument(
        "--mode",
        choices=["hourly", "daily"],
        default="hourly",
        help="Rezolucia vystupu: hourly alebo daily (agregacia po UTC dnoch).",
    )
    return ap.parse_args()


def _to_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        num = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(num):
        return None
    return num


def aggregate_daily_rows(filtered: list[dict], variables: list[str]) -> tuple[list[dict], list[str]]:
    """Agreguje hodinove zaznamy na denny vystup (UTC)."""
    by_day: dict[str, dict[str, list[object]]] = {}

    for entry in filtered:
        time_str = entry.get("time", "")
        try:
            dt = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
        except ValueError:
            continue

        day_key = dt.date().isoformat()
        if day_key not in by_day:
            by_day[day_key] = {var: [] for var in variables}

        for var in variables:
            by_day[day_key][var].append(extract_variable(entry, var))

    rows: list[dict] = []
    output_columns: list[str] = []
    for var in variables:
        if var == "temperature_2m":
            output_columns.extend([f"{var}_min", f"{var}_max", f"{var}_mean"])
        elif var.startswith("precipitation_"):
            output_columns.append(f"{var}_sum")
        elif var.startswith("symbol_"):
            output_columns.append(f"{var}_mode")
        else:
            output_columns.append(f"{var}_mean")

    for day_key in sorted(by_day.keys()):
        out = {"date": day_key}
        for var in variables:
            vals = by_day[day_key][var]
            nums = [n for n in (_to_float(v) for v in vals) if n is not None]

            if var == "temperature_2m":
                out[f"{var}_min"] = min(nums) if nums else None
                out[f"{var}_max"] = max(nums) if nums else None
                out[f"{var}_mean"] = (sum(nums) / len(nums)) if nums else None
            elif var.startswith("precipitation_"):
                out[f"{var}_sum"] = sum(nums) if nums else None
            elif var.startswith("symbol_"):
                labels = [str(v) for v in vals if v is not None and str(v).strip()]
                out[f"{var}_mode"] = Counter(labels).most_common(1)[0][0] if labels else None
            else:
                out[f"{var}_mean"] = (sum(nums) / len(nums)) if nums else None

        rows.append(out)

    return rows, output_columns


def main():
    args = parse_args()

    start_dt = parse_datetime(args.start_date)
    end_dt = parse_datetime(args.end_date)
    if start_dt > end_dt:
        raise ValueError("start-date musi byt mensie alebo rovne end-date.")

    variables = [v.strip() for v in args.variables.split(",") if v.strip()]
    unknown = [v for v in variables if v not in VARIABLE_MAP]
    if unknown:
        raise ValueError(f"Neznama premenna: {unknown}. Pouzi --help pre zoznam dostupnych premennych.")

    print(f"Hladam mesto: {args.city}...")
    lat, lon, city_name = resolve_city(args.city)
    print(f"Najdene: {city_name}")
    print(f"Suradnice: lat={lat:.4f}, lon={lon:.4f}")

    url_preview = f"{FORECAST_URL}?lat={round(lat,4)}&lon={round(lon,4)}"
    if args.altitude:
        url_preview += f"&altitude={args.altitude}"
    print(f"URL: {url_preview}")

    if args.dry_run:
        print("\n[dry-run] Ukoncujem bez stahovania dat.")
        return

    print(f"\nStiahuvam predpoved z MET Norway...")
    data = fetch_forecast(lat, lon, args.altitude)

    meta = data.get("properties", {}).get("meta", {})
    updated = meta.get("updated_at", "N/A")
    units = meta.get("units", {})
    timeseries = data.get("properties", {}).get("timeseries", [])

    print(f"Aktualizovane: {updated}")
    print(f"Pocet hodinovych zaznamov celkovo: {len(timeseries)}")

    filtered = filter_timeseries(timeseries, start_dt, end_dt)
    print(f"Zaznamov v zadanom rozmezi: {len(filtered)}")

    if not filtered:
        print("\nZiadne data pre zadane casove rozmedzie.")
        print("Tip: MET Norway poskytuje predpoved typicky na 9-10 dni dopredu od aktualneho datumu.")
        return

    rows_to_print: list[dict] = []
    columns_to_print: list[str] = []

    if args.mode == "daily":
        rows_to_print, columns_to_print = aggregate_daily_rows(filtered, variables)
        print(f"Dennych agregovanych zaznamov: {len(rows_to_print)}")
        if not rows_to_print:
            print("\nZiadne agregovane data pre zadane obdobie.")
            return
    else:
        columns_to_print = list(variables)
        for entry in filtered:
            row = {"date": entry.get("time", "")}
            for var in variables:
                row[var] = extract_variable(entry, var)
            rows_to_print.append(row)

    first_col = "Cas (UTC)" if args.mode == "hourly" else "Datum (UTC)"
    header_parts = [first_col]
    for col in columns_to_print:
        base_var = col
        suffix = ""
        for tail in ("_min", "_max", "_mean", "_sum", "_mode"):
            if col.endswith(tail):
                base_var = col[: -len(tail)]
                suffix = tail
                break

        unit = ""
        if base_var in VARIABLE_MAP:
            _, field = VARIABLE_MAP[base_var]
            unit = units.get(field, "")

        header_parts.append(f"{col}({unit})" if unit and suffix != "_mode" else col)

    col_w = 28
    var_w = 24
    header = f"{first_col:<{col_w}}" + "".join(f"{h:<{var_w}}" for h in header_parts[1:])
    sep = "-" * (col_w + var_w * len(columns_to_print))

    print(f"\n{'=' * len(sep)}")
    title = "PREDIKCNE DATA" if args.mode == "hourly" else "DENNE AGREGOVANE DATA"
    print(f"{title} (MET Norway): {args.city}")
    print(f"{'=' * len(sep)}")
    print(f"Obdobie: {args.start_date} az {args.end_date}")
    print(f"Mode: {args.mode}")
    print(f"Premenne: {', '.join(variables)}")
    print(f"\n{header}")
    print(sep)

    stats: dict[str, list[float]] = {c: [] for c in columns_to_print}

    for row_data in rows_to_print:
        row = f"{str(row_data.get('date', '')):<{col_w}}"
        for col in columns_to_print:
            val = row_data.get(col)
            if val is None:
                cell = "N/A"
            elif isinstance(val, float):
                cell = f"{val:.1f}"
            else:
                cell = str(val)

            num = _to_float(val)
            if num is not None:
                stats[col].append(num)
            row += f"{cell:<{var_w}}"
        print(row)

    print(sep)
    print(f"\n{'=' * len(sep)}")
    print("STATISTIKY")
    print(f"{'=' * len(sep)}")
    for col in columns_to_print:
        vals = stats[col]
        if vals:
            print(f"  {col:<25} Min={min(vals):.2f}  Max={max(vals):.2f}  Priemer={sum(vals)/len(vals):.2f}")
        else:
            print(f"  {col:<25} (ziadne numericke hodnoty)")


if __name__ == "__main__":
    main()


