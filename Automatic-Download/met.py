from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import pymysql

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in os.sys.path:
    os.sys.path.insert(0, str(ROOT_DIR))

from MET.fetch_prediction import (  # noqa: E402
    extract_variable,
    fetch_forecast,
    filter_timeseries,
    resolve_city,
)

DEFAULT_DB_HOST = os.getenv("MARIADB_HOST", "127.0.0.1")
DEFAULT_DB_PORT = int(os.getenv("MARIADB_PORT", "3306"))
DEFAULT_DB_USER = os.getenv("MARIADB_USER", "root")
DEFAULT_DB_PASSWORD = os.getenv("MARIADB_PASSWORD", "al561860")
DEFAULT_DB_NAME = os.getenv("MARIADB_DATABASE", "weather_viewer")
DEFAULT_SHMU_MS_URL = os.getenv("SHMU_MS_URL", "https://www.shmu.sk/File/metaklin/ms.pdf")

DEFAULT_VARIABLES = [
    "temperature_2m",
    "cloud_cover",
    "precipitation_1h",
    "humidity",
    "wind_speed",
    "wind_direction",
    "wind_speed_gust",
    "uv_index",
    "pressure",
    "dew_point",
    "symbol_1h",
    "precipitation_prob_1h",
    "thunder_prob_1h",
    "fog",
]

MET_TO_DB_COLUMN = {
    "temperature_2m": "temperature",
    "temperature_2m_min": "temperature_min",
    "temperature_2m_max": "temperature_max",
    "temperature_2m_mean": "temperature_mean",
    "cloud_cover": "cloud_cover",
    "precipitation_1h": "precipitation",
    "precipitation_1h_sum": "precipitation_sum",
    "humidity": "humidity",
    "wind_speed": "wind_speed",
    "wind_direction": "wind_direction",
    "wind_speed_gust": "wind_gusts",
    "uv_index": "uv_index",
    "pressure": "surface_pressure",
    "dew_point": "dew_point",
    "symbol_1h": "weather_code",
    "precipitation_prob_1h": "precipitation_probability",
    "thunder_prob_1h": "thunder_probability",
    "fog": "fog",
}

DB_WEATHER_COLUMNS = sorted(
    {
        "temperature",
        "temperature_min",
        "temperature_max",
        "temperature_mean",
        "cloud_cover",
        "precipitation",
        "precipitation_sum",
        "precipitation_probability",
        "humidity",
        "wind_speed",
        "wind_direction",
        "wind_gusts",
        "solar_radiation",
        "uv_index",
        "visibility",
        "surface_pressure",
        "dew_point",
        "feels_like",
        "snow",
        "weather_code",
        "thunder_probability",
        "fog",
        "cape",
        "evapotranspiration",
        "vapour_pressure_deficit",
        "sunshine_duration",
        "precipitation_hours",
    }
)

BASE_COLUMNS = [
    "city",
    "resolved_city",
    "station_id",
    "granularity",
    "data_kind",
    "forecast_for",
    "latitude",
    "longitude",
    "timezone_name",
    "unit_system",
    *DB_WEATHER_COLUMNS,
    "raw_payload",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download MET forecast for many locations and persist into MariaDB (met_data)."
    )
    parser.add_argument("--city", action="append", default=[], help="City name (repeatable)")
    parser.add_argument("--cities-file", help="Text file with one city per line")
    parser.add_argument(
        "--city-set",
        choices=["none", "shmu_mapping"],
        default="shmu_mapping",
        help="Default city source when --city/--cities-file are not provided",
    )
    parser.add_argument("--max-cities", type=int, default=0, help="Limit loaded default city set (0 = all)")
    parser.add_argument("--shmu-url", default=DEFAULT_SHMU_MS_URL, help="SHMU ms.pdf URL for city mapping")
    parser.add_argument("--days-ahead", type=int, default=10, help="Forecast horizon from now (default: 10)")
    parser.add_argument("--start-date", help="Optional start date YYYY-MM-DD")
    parser.add_argument("--end-date", help="Optional end date YYYY-MM-DD")
    parser.add_argument("--mode", choices=["hourly", "daily"], default="hourly")
    parser.add_argument("--variables", default=",".join(DEFAULT_VARIABLES), help="Comma-separated MET variables")
    parser.add_argument("--altitude", type=int, default=None, help="Optional altitude in meters")
    parser.add_argument("--batch-size", type=int, default=500, help="DB executemany chunk size")
    parser.add_argument("--dry-run", action="store_true", help="Fetch/process only, do not write DB")
    parser.add_argument("--continue-on-error", action="store_true", help="Continue when one city fails")

    parser.add_argument("--db-host", default=DEFAULT_DB_HOST)
    parser.add_argument("--db-port", type=int, default=DEFAULT_DB_PORT)
    parser.add_argument("--db-user", default=DEFAULT_DB_USER)
    parser.add_argument("--db-password", default=DEFAULT_DB_PASSWORD)
    parser.add_argument("--db-name", default=DEFAULT_DB_NAME)
    return parser.parse_args()


def parse_date_range(args: argparse.Namespace) -> tuple[datetime, datetime]:
    if args.start_date and args.end_date:
        start_dt = datetime.strptime(args.start_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        end_dt = datetime.strptime(args.end_date, "%Y-%m-%d").replace(
            hour=23, minute=59, second=59, tzinfo=timezone.utc
        )
    else:
        start_dt = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
        end_dt = (start_dt + timedelta(days=args.days_ahead)).replace(hour=23, minute=59, second=59)

    if start_dt > end_dt:
        raise ValueError("start date must be before end date")
    return start_dt, end_dt


def load_cities(args: argparse.Namespace) -> list[str]:
    items = [c.strip() for c in args.city if c and c.strip()]
    if args.cities_file:
        path = Path(args.cities_file).resolve()
        for line in path.read_text(encoding="utf-8").splitlines():
            city = line.strip()
            if city and not city.startswith("#"):
                items.append(city)

    # Stable deduplication
    seen: set[str] = set()
    deduped: list[str] = []
    for city in items:
        key = city.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(city)

    if deduped:
        return deduped

    if args.city_set == "shmu_mapping":
        shmu_cities = load_cities_from_shmu_mapping(args.shmu_url)
        if args.max_cities > 0:
            shmu_cities = shmu_cities[: args.max_cities]
        return shmu_cities

    return deduped


def load_cities_from_shmu_mapping(shmu_url: str) -> list[str]:
    try:
        from SHMU.maping import build_ind_kli_map, fetch_pdf_bytes
    except Exception as exc:
        raise RuntimeError(
            "Failed to import SHMU mapping helpers. Ensure SHMU dependencies are installed."
        ) from exc

    try:
        mapping = build_ind_kli_map(fetch_pdf_bytes(shmu_url))
    except Exception as exc:
        raise RuntimeError(f"Failed to load SHMU mapping from {shmu_url}: {exc}") from exc

    if not mapping:
        raise RuntimeError("SHMU mapping returned no cities")

    # Stable deduplication by normalized lower-case string
    seen: set[str] = set()
    cities: list[str] = []
    for name in mapping.values():
        city = " ".join(str(name).split()).strip()
        if not city:
            continue
        key = city.lower()
        if key in seen:
            continue
        seen.add(key)
        cities.append(city)

    cities.sort(key=str.lower)
    return cities


def to_number(value):
    if pd.isna(value):
        return None
    try:
        return float(value)
    except Exception:
        return None


def to_db_datetime(value) -> datetime | None:
    dt = pd.to_datetime(value, errors="coerce", utc=True)
    if pd.isna(dt):
        return None
    return dt.to_pydatetime().replace(tzinfo=None)


def aggregate_daily(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    value_cols = [c for c in df.columns if c != "date"]
    for col in value_cols:
        if col.startswith("symbol_"):
            continue
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df["day"] = pd.to_datetime(df["date"], errors="coerce", utc=True).dt.strftime("%Y-%m-%d")
    grouped = df.groupby("day")
    out = pd.DataFrame({"date": grouped.size().index})

    for col in value_cols:
        if col == "temperature_2m":
            out[f"{col}_min"] = grouped[col].min().values
            out[f"{col}_max"] = grouped[col].max().values
            out[f"{col}_mean"] = grouped[col].mean().values
        elif col.startswith("precipitation_"):
            out[f"{col}_sum"] = grouped[col].sum(min_count=1).values
        elif col.startswith("symbol_"):
            out[col] = grouped[col].agg(lambda x: x.dropna().astype(str).mode().iat[0] if not x.dropna().empty else None).values
        else:
            out[f"{col}_mean"] = grouped[col].mean().values

    return out


def build_insert_sql() -> str:
    return (
        "INSERT INTO `met_data` ("
        + ", ".join(f"`{c}`" for c in BASE_COLUMNS)
        + ") VALUES ("
        + ", ".join(["%s"] * len(BASE_COLUMNS))
        + ") ON DUPLICATE KEY UPDATE "
        + ", ".join(
            f"`{c}`=VALUES(`{c}`)"
            for c in BASE_COLUMNS
            if c not in {"city", "forecast_for", "granularity", "data_kind"}
        )
    )


def rows_for_db(df: pd.DataFrame, city: str, resolved_city: str, mode: str, lat: float, lon: float) -> list[list]:
    output_rows: list[list] = []
    for _, row in df.iterrows():
        forecast_for = to_db_datetime(row.get("date"))
        if forecast_for is None:
            continue

        record = {c: None for c in BASE_COLUMNS}
        record.update(
            {
                "city": city,
                "resolved_city": resolved_city,
                "station_id": None,
                "granularity": mode,
                "data_kind": "prediction",
                "forecast_for": forecast_for,
                "latitude": to_number(lat),
                "longitude": to_number(lon),
                "timezone_name": "UTC",
                "unit_system": None,
                "raw_payload": json.dumps({k: (None if pd.isna(v) else v) for k, v in row.to_dict().items()}, default=str),
            }
        )

        for provider_col, db_col in MET_TO_DB_COLUMN.items():
            if provider_col not in df.columns:
                continue
            value = row.get(provider_col)
            if db_col == "weather_code":
                record[db_col] = None if pd.isna(value) else str(value)
            else:
                record[db_col] = to_number(value)

        output_rows.append([record[c] for c in BASE_COLUMNS])

    return output_rows


def save_rows(conn, insert_sql: str, rows: list[list], batch_size: int) -> int:
    if not rows:
        return 0
    total = 0
    with conn.cursor() as cur:
        for i in range(0, len(rows), batch_size):
            chunk = rows[i : i + batch_size]
            cur.executemany(insert_sql, chunk)
            total += len(chunk)
    return total


def ensure_table_exists(conn) -> None:
    with conn.cursor() as cur:
        cur.execute("SHOW TABLES LIKE 'met_data'")
        if cur.fetchone() is None:
            raise RuntimeError("Table 'met_data' does not exist. Run MariaDB/init_db.py first.")


def city_dataframe(city: str, variables: list[str], start_dt: datetime, end_dt: datetime, altitude: int | None, mode: str):
    lat, lon, resolved_city = resolve_city(city)
    payload = fetch_forecast(lat, lon, altitude)
    timeseries = payload.get("properties", {}).get("timeseries", [])
    filtered = filter_timeseries(timeseries, start_dt, end_dt)

    rows = []
    for entry in filtered:
        row = {"date": entry.get("time")}
        for var in variables:
            row[var] = extract_variable(entry, var)
        rows.append(row)

    df = pd.DataFrame(rows)
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce", utc=True)

    if mode == "daily" and not df.empty:
        df = aggregate_daily(df)

    return resolved_city, lat, lon, df


def main() -> int:
    args = parse_args()
    cities = load_cities(args)
    if not cities:
        raise ValueError("No cities provided. Use --city or --cities-file.")

    variables = [v.strip() for v in args.variables.split(",") if v.strip()]
    start_dt, end_dt = parse_date_range(args)

    print(f"Cities: {len(cities)}")
    print(f"Range (UTC): {start_dt.isoformat()} -> {end_dt.isoformat()}")
    print(f"Mode: {args.mode}")
    print(f"Dry run: {args.dry_run}")

    conn = None
    insert_sql = build_insert_sql()
    if not args.dry_run:
        conn = pymysql.connect(
            host=args.db_host,
            port=args.db_port,
            user=args.db_user,
            password=args.db_password,
            database=args.db_name,
            charset="utf8mb4",
            autocommit=True,
            cursorclass=pymysql.cursors.DictCursor,
        )
        ensure_table_exists(conn)

    ok = 0
    failed = 0
    written = 0

    try:
        for city in cities:
            try:
                print(f"\n[{city}] fetching...")
                resolved_city, lat, lon, df = city_dataframe(
                    city=city,
                    variables=variables,
                    start_dt=start_dt,
                    end_dt=end_dt,
                    altitude=args.altitude,
                    mode=args.mode,
                )

                print(f"[{city}] rows prepared: {len(df)}")
                if df.empty:
                    ok += 1
                    continue

                if not args.dry_run and conn is not None:
                    rows = rows_for_db(df, city, resolved_city, args.mode, lat, lon)
                    inserted = save_rows(conn, insert_sql, rows, args.batch_size)
                    written += inserted
                    print(f"[{city}] rows upserted: {inserted}")

                ok += 1
            except Exception as exc:
                failed += 1
                print(f"[{city}] ERROR: {exc}")
                if not args.continue_on_error:
                    raise
    finally:
        if conn is not None:
            conn.close()

    print("\n--- Summary ---")
    print(f"Succeeded: {ok}")
    print(f"Failed: {failed}")
    if not args.dry_run:
        print(f"Total rows upserted: {written}")

    return 0 if failed == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())


