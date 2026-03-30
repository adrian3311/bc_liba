"""
Skript na ziskanie predikcnych dat z MET Norway Locationforecast API.
Dokumentacia: https://api.met.no/doc/GettingStarted
Endpoint:     https://api.met.no/weatherapi/locationforecast/2.0/complete
"""

import argparse
import time
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
    "wind_speed":               ("instant", "wind_speed"),
    "wind_direction":           ("instant", "wind_from_direction"),
    "humidity":                 ("instant", "relative_humidity"),
    "pressure":                 ("instant", "air_pressure_at_sea_level"),
    "dew_point":                ("instant", "dew_point_temperature"),
    "fog":                      ("instant", "fog_area_fraction"),
    "precipitation_1h":         ("next_1_hours", "precipitation_amount"),
    "precipitation_6h":         ("next_6_hours", "precipitation_amount"),
    "precipitation_12h":        ("next_12_hours", "precipitation_amount"),
    "symbol_1h":                ("next_1_hours", "summary_symbol_code"),
    "symbol_6h":                ("next_6_hours", "summary_symbol_code"),
    "symbol_12h":               ("next_12_hours", "summary_symbol_code"),
    "uv_index":                 ("instant", "ultraviolet_index_clear_sky"),
}

DEFAULT_VARIABLES = "temperature_2m,cloud_cover,precipitation_1h,wind_speed,humidity"


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
    return ap.parse_args()


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
        print(f"Tip: MET Norway poskytuje predpoved typicky na 9-10 dni dopredu od aktualneho datumu.")
        return

    # --- Vypis hlavicky ---
    header_parts = ["Cas (UTC)"]
    for var in variables:
        _, field = VARIABLE_MAP[var]
        unit = units.get(field, "")
        header_parts.append(f"{var}({unit})" if unit else var)

    col_w = 28
    var_w = 20
    header = f"{'Cas (UTC)':<{col_w}}" + "".join(f"{h:<{var_w}}" for h in header_parts[1:])
    sep = "-" * (col_w + var_w * len(variables))

    print(f"\n{'=' * len(sep)}")
    print(f"PREDIKCNE DATA (MET Norway): {args.city}")
    print(f"{'=' * len(sep)}")
    print(f"Obdobie: {args.start_date} az {args.end_date}")
    print(f"Premenne: {', '.join(variables)}")
    print(f"\n{header}")
    print(sep)

    stats: dict[str, list] = {v: [] for v in variables}

    for entry in filtered:
        time_str = entry.get("time", "")
        row = f"{time_str:<{col_w}}"
        for var in variables:
            val = extract_variable(entry, var)
            if val is None:
                cell = "N/A"
            elif isinstance(val, float):
                cell = f"{val:.1f}"
                stats[var].append(val)
            else:
                cell = str(val)
                try:
                    stats[var].append(float(val))
                except (ValueError, TypeError):
                    pass
            row += f"{cell:<{var_w}}"
        print(row)

    print(sep)
    print(f"\n{'=' * len(sep)}")
    print("STATISTIKY")
    print(f"{'=' * len(sep)}")
    for var in variables:
        vals = stats[var]
        if vals:
            print(f"  {var:<25} Min={min(vals):.2f}  Max={max(vals):.2f}  Priemer={sum(vals)/len(vals):.2f}")
        else:
            print(f"  {var:<25} (ziadne numericke hodnoty)")


if __name__ == "__main__":
    main()


