#!/usr/bin/env python3
"""SHMU climate-now: hodinovy vyber dat podla datumu, mesta a typu dat."""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import quote, unquote

import pandas as pd
import requests
from maping import build_ind_kli_map

BASE_URL = "https://opendata.shmu.sk/meteorology/climate/now/data"
MS_PDF_URL = "https://www.shmu.sk/File/metaklin/ms.pdf"
HREF_JSON_RE = re.compile(r'href=["\']([^"\']+\.json)["\']', re.IGNORECASE)
FILE_RE = re.compile(
    r"^(?P<dtype>.+?) - (?P<date>\d{4}-\d{2}-\d{2}) (?P<clock>\d{2}-\d{2}-\d{2})\.json$"
)
@dataclass(frozen=True)
class DayFile:
    name: str
    data_type: str
    timestamp: datetime

    @property
    def encoded_name(self) -> str:
        return quote(self.name, safe="-_.~")


@dataclass(frozen=True)
class Station:
    ind_kli: str
    name: str


def normalize_text(value: str) -> str:
    base = unicodedata.normalize("NFKD", value)
    no_acc = "".join(ch for ch in base if not unicodedata.combining(ch))
    return " ".join(re.sub(r"[^a-zA-Z0-9\s-]", " ", no_acc).lower().split())


def parse_date(value: str) -> date:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError(f"Neplatny datum '{value}', pouzi YYYY-MM-DD") from exc


def resolve_days(args: argparse.Namespace) -> list[date]:
    if args.date:
        if args.start_date or args.end_date:
            raise ValueError("Pouzi bud --date alebo dvojicu --start-date a --end-date.")
        return [parse_date(args.date)]

    if bool(args.start_date) != bool(args.end_date):
        raise ValueError("Pri intervale musis zadat aj --start-date aj --end-date.")

    if not args.start_date and not args.end_date:
        raise ValueError("Zadaj --date alebo --start-date a --end-date.")

    start_day = parse_date(args.start_date)
    end_day = parse_date(args.end_date)
    if start_day > end_day:
        raise ValueError("start-date musi byt mensi alebo rovny end-date.")

    days: list[date] = []
    current = start_day
    while current <= end_day:
        days.append(current)
        current += timedelta(days=1)
    return days


def day_url(day: date) -> str:
    return f"{BASE_URL}/{day.strftime('%Y%m%d')}/"


def parse_day_file_name(filename: str) -> DayFile | None:
    match = FILE_RE.match(filename)
    if not match:
        return None

    ts = datetime.strptime(
        f"{match.group('date')} {match.group('clock').replace('-', ':')}",
        "%Y-%m-%d %H:%M:%S",
    )
    return DayFile(name=filename, data_type=match.group("dtype"), timestamp=ts)


def list_day_files(session: requests.Session, day: date, verify_ssl: bool) -> list[DayFile]:
    response = session.get(day_url(day), timeout=40, verify=verify_ssl)
    response.raise_for_status()

    unique: dict[str, DayFile] = {}
    for href in HREF_JSON_RE.findall(response.text):
        name = Path(unquote(href)).name
        parsed = parse_day_file_name(name)
        if parsed:
            unique[name] = parsed

    return sorted(unique.values(), key=lambda item: item.timestamp)


def select_hourly_files(files: list[DayFile], wanted_type: str) -> list[DayFile]:
    groups: dict[int, list[DayFile]] = defaultdict(list)
    for file in files:
        if file.data_type != wanted_type:
            continue
        groups[file.timestamp.hour].append(file)

    selected: list[DayFile] = []
    for hour in sorted(groups):
        hour_files = sorted(groups[hour], key=lambda f: f.timestamp)
        exact = next((f for f in hour_files if f.timestamp.minute == 0), None)
        selected.append(exact or hour_files[0])

    return selected


def download_json(
    session: requests.Session,
    day: date,
    file_meta: DayFile,
    output_dir: Path,
    verify_ssl: bool,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / file_meta.name

    if not target.exists():
        url = f"{day_url(day)}{file_meta.encoded_name}"
        response = session.get(url, timeout=60, verify=verify_ssl)
        response.raise_for_status()
        target.write_bytes(response.content)

    return target


def load_station_map(session: requests.Session, verify_ssl: bool) -> list[Station]:
    response = session.get(MS_PDF_URL, timeout=50, verify=verify_ssl)
    response.raise_for_status()

    mapping = build_ind_kli_map(response.content)
    return [Station(ind_kli=ind_kli, name=name) for ind_kli, name in mapping.items()]


def resolve_ind_kli_for_city(stations: list[Station], city: str) -> Station:
    needle = normalize_text(city)

    # Automaticky vyhľadaj "-letisko" variant pre Bratislavu a Košice
    if needle in ["bratislava", "kosice"]:
        airport_name = f"{needle}-letisko"
        airport_stations = [s for s in stations if normalize_text(s.name) == airport_name]
        if airport_stations:
            return airport_stations[0]

    # Fallback: presné mestá
    exact = [s for s in stations if normalize_text(s.name) == needle]
    if exact:
        return exact[0]

    # Fallback: čiastočná zhoda
    partial = [s for s in stations if needle in normalize_text(s.name)]
    if partial:
        return partial[0]

    raise ValueError(f"Mesto '{city}' sa nenaslo v ms.pdf mapovani.")


def select_record_for_station(payload: dict, ind_kli: str) -> dict | None:
    records = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(records, list):
        return None

    station_rows = [row for row in records if str(row.get("ind_kli")) == ind_kli]
    if not station_rows:
        return None

    # Preferuj presne xx:00, inak najblizsi zaznam v subore.
    on_hour = [r for r in station_rows if str(r.get("minuta", "")).endswith(":00")]
    if on_hour:
        return on_hour[0]

    return station_rows[0]


def resolve_requested_fields(args: argparse.Namespace) -> list[str]:
    if args.fields:
        return [field.strip() for field in args.fields.split(",") if field.strip()]
    if args.field:
        return [args.field.strip()]
    return []


def format_selected_values(record: dict, fields: list[str]) -> str:
    return " | ".join(f"{field}={record.get(field)}" for field in fields)


def fetch_shmu_data(
    city: str,
    start_date: str,
    end_date: str,
    fields: list[str],
    data_type: str = "aws1min",
    output_dir: str = "SHMU/downloadsNow",
    verify_ssl: bool = True,
) -> tuple[str, str, pd.DataFrame]:
    start_day = parse_date(start_date)
    end_day = parse_date(end_date)
    if start_day > end_day:
        raise ValueError("start_date must be before or equal to end_date")

    session = requests.Session()
    stations = load_station_map(session, verify_ssl)
    try:
        station = resolve_ind_kli_for_city(stations, city)
    except ValueError:
        # Keep helper API usable without raising when station is missing.
        return city, "", pd.DataFrame()

    days: list[date] = []
    current = start_day
    while current <= end_day:
        days.append(current)
        current += timedelta(days=1)

    rows: list[dict] = []
    base_fields = [field for field in fields if field]

    for selected_day in days:
        day_files = list_day_files(session, selected_day, verify_ssl)
        hourly_files = select_hourly_files(day_files, data_type)
        out_dir = Path(output_dir) / selected_day.strftime("%Y%m%d") / data_type

        for item in hourly_files:
            local_path = download_json(session, selected_day, item, out_dir, verify_ssl)
            payload = json.loads(local_path.read_text(encoding="utf-8"))
            record = select_record_for_station(payload, station.ind_kli)
            if record is None:
                continue

            row = {
                "date": item.timestamp,
                "minuta": record.get("minuta"),
                "ind_kli": station.ind_kli,
            }
            for field in base_fields:
                row[field] = record.get(field)
            rows.append(row)

    df = pd.DataFrame(rows)
    if not df.empty and "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
    return station.name, station.ind_kli, df


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="SHMU: zadaj miesto, datum od-do a typ dat; skript vypise najdene hodnoty"
    )
    parser.add_argument("--date", "--datum", default="", help="Jeden datum vo formate YYYY-MM-DD")
    parser.add_argument(
        "--start-date", "--from-date", "--od",
        default="",
        dest="start_date",
        help="Zaciatok intervalu vo formate YYYY-MM-DD",
    )
    parser.add_argument(
        "--end-date", "--to-date", "--do",
        default="",
        dest="end_date",
        help="Koniec intervalu vo formate YYYY-MM-DD",
    )
    parser.add_argument(
        "--city", "--place", "--miesto",
        required=True,
        dest="city",
        help="Mesto/stanica, napr. Zilina",
    )
    parser.add_argument(
        "--field", "--data-type", "--typ-dat",
        default="",
        dest="field",
        help="Jeden JSON kluc, napr. t alebo vlh_rel",
    )
    parser.add_argument(
        "--fields", "--data-types", "--typy-dat",
        default="",
        dest="fields",
        help="Viac JSON klucov oddelenych ciarkou, napr. t,vlh_rel,zra_uhrn",
    )
    parser.add_argument(
        "--record",
        action="store_true",
        help="Vypise cely najdeny record pod danym ind_kli",
    )
    parser.add_argument(
        "--list-fields",
        action="store_true",
        help="Vypise dostupne kluce v recorde pre dane ind_kli a skonci",
    )
    parser.add_argument(
        "--type", "--dataset-type", "--file-type",
        default="aws1min",
        dest="type",
        help="Typ SHMU suborov, default aws1min",
    )
    parser.add_argument("--output-dir", default="SHMU/downloadsNow", help="Kde ulozit JSON subory")
    parser.add_argument("--insecure", action="store_true", help="Vypne SSL verifikaciu")
    parser.add_argument("--dry-run", action="store_true", help="Len vypise co by sa stiahlo")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    verify_ssl = not args.insecure
    selected_fields = resolve_requested_fields(args)

    try:
        selected_days = resolve_days(args)
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 2

    session = requests.Session()

    try:
        stations = load_station_map(session, verify_ssl)
        station = resolve_ind_kli_for_city(stations, args.city)
    except requests.RequestException as exc:
        print(f"Chyba pri nacitani mapovania ms.pdf: {exc}", file=sys.stderr)
        return 1
    except ValueError:
        print(f"No data for {args.city}")
        return 0

    selected_by_day: list[tuple[date, list[DayFile]]] = []
    listing_errors = 0
    for selected_day in selected_days:
        try:
            day_files = list_day_files(session, selected_day, verify_ssl)
        except requests.RequestException as exc:
            listing_errors += 1
            print(
                f"Chyba pri citani denneho priecinka {selected_day.isoformat()}: {exc}",
                file=sys.stderr,
            )
            continue

        hourly_files = select_hourly_files(day_files, args.type)
        if hourly_files:
            selected_by_day.append((selected_day, hourly_files))

    if not selected_by_day:
        print("Pre zvoleny datum/typ neboli najdene subory.")
        return 1 if listing_errors else 0

    total_hourly_files = sum(len(files) for _, files in selected_by_day)

    print(f"Mesto: {station.name} | ind_kli: {station.ind_kli}")
    if args.record:
        print(f"Typ dat: cely record | Suborovy typ: {args.type}")
    elif selected_fields:
        print(f"Typ dat: {', '.join(selected_fields)} | Suborovy typ: {args.type}")
    else:
        print(f"Typ dat: cely record | Suborovy typ: {args.type}")
    if len(selected_days) == 1:
        print(f"Hodinovych suborov: {total_hourly_files}")
    else:
        print(
            f"Interval: {selected_days[0].isoformat()} -> {selected_days[-1].isoformat()} | Hodinovych suborov: {total_hourly_files}"
        )

    for selected_day, hourly_files in selected_by_day:
        out_dir = Path(args.output_dir) / selected_day.strftime("%Y%m%d") / args.type

        for item in hourly_files:
            url = f"{day_url(selected_day)}{item.encoded_name}"
            if args.dry_run:
                print(f"[dry-run] {selected_day.isoformat()} {item.timestamp.strftime('%H:%M')} -> {url}")
                continue

            try:
                local_path = download_json(session, selected_day, item, out_dir, verify_ssl)
                payload = json.loads(local_path.read_text(encoding="utf-8"))
            except (requests.RequestException, json.JSONDecodeError) as exc:
                print(f"Preskakujem {item.name}: {exc}", file=sys.stderr)
                continue

            record = select_record_for_station(payload, station.ind_kli)
            if record is None:
                print(
                    f"{selected_day.isoformat()} {item.timestamp.strftime('%H:%M')} | bez zaznamu pre ind_kli {station.ind_kli}"
                )
                continue

            if args.list_fields:
                print("Dostupne kluce:")
                for key in sorted(record.keys()):
                    print(f"- {key}")
                return 0

            minute = str(record.get("minuta", ""))
            prefix = f"{selected_day.isoformat()} {item.timestamp.strftime('%H:%M')} | minuta={minute}"

            if args.record or not selected_fields:
                print(f"{prefix} | record={json.dumps(record, ensure_ascii=False)}")
                continue

            print(f"{prefix} | {format_selected_values(record, selected_fields)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())




