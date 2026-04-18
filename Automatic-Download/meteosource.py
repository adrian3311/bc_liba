"""Automaticke stahovanie predikcie z MeteoSource API a ukladanie do MariaDB.

Obmedzenia bezplatneho planu:
  - daily  : maximalne 7 dni dopredu
  - hourly : dnesok + zajtra (hodina po hodine)
"""

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

from MeteoSource.fetch_prediction import (  # noqa: E402
    extract_daily_rows,
    extract_hourly_rows,
    fetch_daily_data,
    fetch_hourly_data,
    find_place,
)

DEFAULT_DB_HOST = os.getenv("MARIADB_HOST", "127.0.0.1")
DEFAULT_DB_PORT = int(os.getenv("MARIADB_PORT", "3306"))
DEFAULT_DB_USER = os.getenv("MARIADB_USER", "root")
DEFAULT_DB_PASSWORD = os.getenv("MARIADB_PASSWORD", "al561860")
DEFAULT_DB_NAME = os.getenv("MARIADB_DATABASE", "weather_viewer")
DEFAULT_API_KEY = os.getenv("METEOSOURCE_API_KEY", "")
DEFAULT_SHMU_MS_URL = os.getenv("SHMU_MS_URL", "https://www.shmu.sk/File/metaklin/ms.pdf")

# Maximalne obmedzenia bezplatneho planu MeteoSource
MAX_DAILY_DAYS = 7   # dennych zaznamov dopredu
MAX_HOURLY_DAYS = 2  # hodinove data pre dnesok + zajtra

DEFAULT_HOURLY_VARIABLES = [
    "temperature",
    "wind_speed",
    "wind_direction",
    "cloud_cover",
    "precipitation_sum",
    "pressure",
    "humidity",
    "dew_point",
    "uv_index",
    "visibility",
    "feels_like",
    "weather",
]

DEFAULT_DAILY_VARIABLES = [
    "temperature",
    "temperature_min",
    "temperature_max",
    "precipitation_sum",
    "wind_speed",
    "cloud_cover",
    "pressure",
    "humidity",
    "uv_index",
    "visibility",
    "weather",
]

# Mapovanie MeteoSource premennych na stlpce DB
METEOSOURCE_TO_DB_COLUMN: dict[str, str] = {
    "temperature": "temperature",
    "temperature_min": "temperature_min",
    "temperature_max": "temperature_max",
    "wind_speed": "wind_speed",
    "wind_direction": "wind_direction",
    "cloud_cover": "cloud_cover",
    "precipitation_sum": "precipitation_sum",
    "pressure": "surface_pressure",
    "humidity": "humidity",
    "dew_point": "dew_point",
    "uv_index": "uv_index",
    "visibility": "visibility",
    "feels_like": "feels_like",
    "weather": "weather_code",
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
        description=(
            "Stiahni predikciu z MeteoSource API a uloz do MariaDB (meteosource_data). "
            "Obmedzenie free planu: daily = 7 dni, hourly = dnesok + zajtra."
        )
    )
    parser.add_argument("--city", action="append", default=[], help="Nazov mesta (opakovatelny)")
    parser.add_argument("--cities-file", help="Textovy subor s jednym mestom na riadok")
    parser.add_argument(
        "--city-set",
        choices=["none", "shmu_mapping"],
        default="shmu_mapping",
        help="Predvoleny zdroj miest ked --city/--cities-file nie su zadane",
    )
    parser.add_argument("--max-cities", type=int, default=0, help="Obmedzenie poctu miest (0 = vsetky)")
    parser.add_argument("--shmu-url", default=DEFAULT_SHMU_MS_URL, help="URL SHMU ms.pdf pre mapovanie miest")
    parser.add_argument(
        "--mode",
        choices=["hourly", "daily"],
        default="daily",
        help="Rezim: hourly (dnesok + zajtra) alebo daily (max 7 dni)",
    )
    parser.add_argument(
        "--hourly-variables",
        default=",".join(DEFAULT_HOURLY_VARIABLES),
        help="Hodinove premenne (csv)",
    )
    parser.add_argument(
        "--daily-variables",
        default=",".join(DEFAULT_DAILY_VARIABLES),
        help="Denne premenne (csv)",
    )
    parser.add_argument(
        "--api-key",
        default=DEFAULT_API_KEY,
        help="API kluc MeteoSource alebo env METEOSOURCE_API_KEY",
    )
    parser.add_argument("--batch-size", type=int, default=500, help="Velkost davky pre DB executemany")
    parser.add_argument("--dry-run", action="store_true", help="Len stiahni/spracuj, nezapisuj do DB")
    parser.add_argument("--continue-on-error", action="store_true", help="Pokracuj aj ked jedno mesto zlyha")

    parser.add_argument("--db-host", default=DEFAULT_DB_HOST)
    parser.add_argument("--db-port", type=int, default=DEFAULT_DB_PORT)
    parser.add_argument("--db-user", default=DEFAULT_DB_USER)
    parser.add_argument("--db-password", default=DEFAULT_DB_PASSWORD)
    parser.add_argument("--db-name", default=DEFAULT_DB_NAME)
    return parser.parse_args()


def compute_date_range(mode: str) -> tuple[str, str]:
    """Vypocitaj rozsah datumov podla rezimu a obmedzeni MeteoSource free planu."""
    today = datetime.now(timezone.utc).date()
    start = today
    if mode == "hourly":
        end = today + timedelta(days=1)  # dnesok + zajtra
    else:
        end = today + timedelta(days=MAX_DAILY_DAYS - 1)  # 7 dni celkovo
    return start.isoformat(), end.isoformat()


def load_cities(args: argparse.Namespace) -> list[str]:
    items = [c.strip() for c in args.city if c and c.strip()]
    if args.cities_file:
        path = Path(args.cities_file).resolve()
        for line in path.read_text(encoding="utf-8").splitlines():
            city = line.strip()
            if city and not city.startswith("#"):
                items.append(city)

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
            "Nepodarilo sa importovat SHMU mapping helpers. Skontroluj zavislosti SHMU."
        ) from exc

    try:
        mapping = build_ind_kli_map(fetch_pdf_bytes(shmu_url))
    except Exception as exc:
        raise RuntimeError(f"Nepodarilo sa nacitat SHMU mapping z {shmu_url}: {exc}") from exc

    if not mapping:
        raise RuntimeError("SHMU mapping neobsahuje ziadne mesta")

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
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except Exception:
        pass
    try:
        return float(value)
    except Exception:
        return None


def to_db_datetime(value) -> datetime | None:
    dt = pd.to_datetime(value, errors="coerce", utc=True)
    if pd.isna(dt):
        return None
    return dt.to_pydatetime().replace(tzinfo=None)


def build_insert_sql() -> str:
    return (
        "INSERT INTO `meteosource_data` ("
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


def rows_for_db(
    df: pd.DataFrame,
    city: str,
    resolved_city: str,
    mode: str,
    lat: float | None,
    lon: float | None,
) -> list[list]:
    output_rows: list[list] = []
    for _, row in df.iterrows():
        forecast_for = to_db_datetime(row.get("date", ""))
        if forecast_for is None:
            continue

        record: dict = {c: None for c in BASE_COLUMNS}
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
                "timezone_name": None,
                "unit_system": None,
                "raw_payload": json.dumps(
                    {
                        k: (None if (isinstance(v, float) and pd.isna(v)) else v)
                        for k, v in row.to_dict().items()
                    },
                    default=str,
                ),
            }
        )

        for src_col, db_col in METEOSOURCE_TO_DB_COLUMN.items():
            if src_col not in df.columns:
                continue
            value = row.get(src_col)
            if db_col == "weather_code":
                is_nan = isinstance(value, float) and pd.isna(value)
                record[db_col] = None if is_nan else (str(value) if value is not None else None)
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
        cur.execute("SHOW TABLES LIKE 'meteosource_data'")
        if cur.fetchone() is None:
            raise RuntimeError("Tabulka 'meteosource_data' neexistuje. Spusti MariaDB/init_db.py najprv.")


def city_dataframe(
    city: str,
    variables: list[str],
    start_date: str,
    end_date: str,
    api_key: str,
    mode: str,
) -> tuple[str, float | None, float | None, pd.DataFrame]:
    """Stiahnit a spracovit data pre jedno mesto."""
    place_id, resolved_city, lat, lon = find_place(city, api_key)

    if mode == "hourly":
        payload, _ = fetch_hourly_data(place_id, api_key)
        rows = extract_hourly_rows(payload, variables, start_date, end_date)
    else:
        payload, _ = fetch_daily_data(place_id, api_key)
        rows = extract_daily_rows(payload, variables, start_date, end_date)

    df = pd.DataFrame(rows)
    return resolved_city, lat, lon, df


def main() -> int:
    args = parse_args()

    if not args.api_key and not args.dry_run:
        import sys
        print("Chyba: zadaj --api-key alebo nastav METEOSOURCE_API_KEY", file=sys.stderr)
        return 2

    cities = load_cities(args)
    if not cities:
        raise ValueError("Ziadne mesta. Pouzi --city alebo --cities-file.")

    if args.mode == "hourly":
        variables = [v.strip() for v in args.hourly_variables.split(",") if v.strip()]
    else:
        variables = [v.strip() for v in args.daily_variables.split(",") if v.strip()]

    start_date, end_date = compute_date_range(args.mode)

    print(f"Mesta: {len(cities)}")
    print(f"Rozsah: {start_date} -> {end_date}")
    print(f"Rezim: {args.mode}")
    print(f"Dry run: {args.dry_run}")
    if args.mode == "daily":
        print(f"(Obmedzenie MeteoSource free: max {MAX_DAILY_DAYS} dni denne)")
    else:
        print(f"(Obmedzenie MeteoSource free: iba {MAX_HOURLY_DAYS} dni hodinove data - dnesok + zajtra)")

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
                print(f"\n[{city}] stahujem...")
                resolved_city, lat, lon, df = city_dataframe(
                    city=city,
                    variables=variables,
                    start_date=start_date,
                    end_date=end_date,
                    api_key=args.api_key,
                    mode=args.mode,
                )
                print(f"[{city}] pripravene riadky: {len(df)}")

                if df.empty:
                    ok += 1
                    continue

                if not args.dry_run and conn is not None:
                    db_rows = rows_for_db(df, city, resolved_city, args.mode, lat, lon)
                    inserted = save_rows(conn, insert_sql, db_rows, args.batch_size)
                    written += inserted
                    print(f"[{city}] upsertovane riadky: {inserted}")

                ok += 1
            except Exception as exc:
                failed += 1
                print(f"[{city}] CHYBA: {exc}")
                if not args.continue_on_error:
                    raise
    finally:
        if conn is not None:
            conn.close()

    print("\n--- Zhrnutie ---")
    print(f"Uspesnych: {ok}")
    print(f"Neuspesnych: {failed}")
    if not args.dry_run:
        print(f"Celkovo upsertovanych riadkov: {written}")

    return 0 if failed == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())







