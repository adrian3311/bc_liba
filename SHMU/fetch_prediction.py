"""
Stiahne SHMU ALADIN GRIB predikcie pre zvoleny datum a runy.

Priklad zdroja:
https://opendata.shmu.sk/meteorology/weather/nwp/aladin/sk/4.5km/20260203/0000/
"""

import argparse
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Iterable
from urllib.parse import urljoin

import requests

DEFAULT_BASE_URL = "https://opendata.shmu.sk/meteorology/weather/nwp/aladin/sk/4.5km"
DEFAULT_RUNS = ["0000", "0600", "1200", "1800"]


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="SHMU ALADIN GRIB downloader")
    ap.add_argument("--date", required=True, help="Datum: YYYYMMDD alebo D.M.YYYY (napr. 11.2.2026)")
    ap.add_argument("--runs", default=",".join(DEFAULT_RUNS), help="CSV runov, napr. 0000,0600,1200,1800")
    ap.add_argument("--base-url", default=DEFAULT_BASE_URL, help="Zakladna URL SHMU ALADIN")
    ap.add_argument("--out-dir", default="SHMU/downloadsPredictions", help="Cielovy priecinok")
    ap.add_argument("--workers", type=int, default=8, help="Pocet paralelnych download workerov")
    ap.add_argument("--timeout", type=int, default=60, help="HTTP timeout v sekundach")
    ap.add_argument("--skip-existing", action="store_true", help="Preskoc uz stiahnute subory")
    ap.add_argument("--dry-run", action="store_true", help="Len vypis co by sa stiahlo")
    ap.add_argument("--insecure", action="store_true", help="Vypne SSL verifikaciu (ak treba)")
    ap.add_argument(
        "--expected-counts",
        default="0000:103,0600:73,1200:73,1800:73",
        help="Ocakavane pocty suborov na run, napr. 0000:103,0600:73",
    )
    return ap.parse_args()


def parse_expected_counts(value: str) -> dict[str, int]:
    return {run.strip(): int(count.strip()) for item in value.split(",")
            for run, count in [item.split(":")] if item.strip()}


def normalize_runs(value: str) -> list[str]:
    return [x.strip() for x in value.split(",") if x.strip()]


def run_url(base_url: str, date_yyyymmdd: str, run_hhmm: str) -> str:
    return f"{base_url.rstrip('/')}/{date_yyyymmdd}/{run_hhmm}/"


def date_url(base_url: str, date_yyyymmdd: str) -> str:
    return f"{base_url.rstrip('/')}/{date_yyyymmdd}/"


def check_date_route_exists(session: requests.Session, base_url: str, date_yyyymmdd: str, timeout: int, verify: bool) -> bool:
    """Overi, ci existuje datumova trasa na SHMU (napr. .../20260211/)."""
    try:
        resp = session.get(date_url(base_url, date_yyyymmdd), timeout=timeout, verify=verify)
        return resp.status_code != 404
    except:
        return False


def list_grb_links(session: requests.Session, directory_url: str, timeout: int, verify: bool) -> list[tuple[str, str]]:
    resp = session.get(directory_url, timeout=timeout, verify=verify)
    resp.raise_for_status()
    hrefs = re.findall(r'href="([^"]+\.grb)"', resp.text, flags=re.IGNORECASE)
    return [(href.split("/")[-1], urljoin(directory_url, href)) for href in hrefs
            if href.lower().endswith(".grb")]


def download_file(session: requests.Session, file_url: str, dest: Path, timeout: int, verify: bool) -> tuple[bool, str]:
    try:
        with session.get(file_url, stream=True, timeout=timeout, verify=verify) as r:
            r.raise_for_status()
            dest.parent.mkdir(parents=True, exist_ok=True)
            with dest.open("wb") as f:
                for chunk in r.iter_content(chunk_size=1024 * 512):
                    if chunk:
                        f.write(chunk)
        return True, "ok"
    except Exception as exc:
        return False, str(exc)


def batched(iterable: list, n: int) -> list:
    return [iterable[i:i+n] for i in range(0, len(iterable), n)]


def normalize_input_date(value: str) -> str:
    """Prijme datum od pouzivatela a vrati YYYYMMDD.

    Podporene formaty:
    - YYYYMMDD (napr. 20260211)
    - D.M.YYYY alebo DD.MM.YYYY (napr. 11.2.2026)
    """
    value = value.strip()

    if re.fullmatch(r"\d{8}", value):
        # over validitu aj pre YYYYMMDD vstup
        datetime.strptime(value, "%Y%m%d")
        return value

    for fmt in ("%d.%m.%Y", "%d.%m.%y"):
        try:
            dt = datetime.strptime(value, fmt)
            # dvojmiestny rok (yy) moze viesť k 1926; pouzivame ho len ak zadany format sedel
            # a date parser uz doplnil storocie podla python pravidiel.
            return dt.strftime("%Y%m%d")
        except ValueError:
            continue

    raise ValueError(
        f"Neplatny format datumu: '{value}'. Pouzi YYYYMMDD alebo D.M.YYYY (napr. 11.2.2026)."
    )


def main() -> None:
    args = parse_args()
    date_yyyymmdd = normalize_input_date(args.date)
    runs = normalize_runs(args.runs)
    expected_counts = parse_expected_counts(args.expected_counts)
    verify = not args.insecure

    session = requests.Session()
    session.headers.update({"User-Agent": "SHMU-GRB-Downloader/1.0"})

    if not check_date_route_exists(session, args.base_url, date_yyyymmdd, timeout=args.timeout, verify=verify):
        print(f"CHYBA: Trasa pre datum neexistuje: {date_url(args.base_url, date_yyyymmdd)}")
        return

    root_out = Path(args.out_dir) / date_yyyymmdd
    root_out.mkdir(parents=True, exist_ok=True)

    print(f"Datum (vstup): {args.date}")
    print(f"Datum (normalizovany): {date_yyyymmdd}")
    print(f"Runy: {', '.join(runs)}")
    print(f"Output: {root_out}")
    print(f"Mode: {'DRY-RUN' if args.dry_run else 'DOWNLOAD'}")

    all_tasks: list[tuple[str, str, Path]] = []

    for run in runs:
        directory = run_url(args.base_url, date_yyyymmdd, run)
        try:
            links = list_grb_links(session, directory, timeout=args.timeout, verify=verify)
        except Exception as exc:
            print(f"\n[{run}] CHYBA pri listovani: {exc}")
            continue

        found = len(links)
        expected = expected_counts.get(run)
        status = "OK"
        if expected is not None and found != expected:
            status = f"MIMO OCAKAVANIA (expected={expected})"

        print(f"\n[{run}] najdenych .grb: {found} -> {status}")

        run_out = root_out / run
        for filename, url in links:
            dest = run_out / filename
            if args.skip_existing and dest.exists():
                continue
            all_tasks.append((filename, url, dest))

    print(f"\nNa stiahnutie spolu: {len(all_tasks)} suborov")

    if args.dry_run:
        for i, (filename, url, dest) in enumerate(all_tasks[:20], start=1):
            print(f"  {i:02d}. {filename} -> {dest}")
        if len(all_tasks) > 20:
            print(f"  ... a dalsich {len(all_tasks) - 20}")
        return

    ok = 0
    fail = 0

    # Mensie batch-e pomahaju drzat output prehladny pri velkom pocte suborov.
    for batch in batched(all_tasks, max(1, args.workers * 4)):
        with ThreadPoolExecutor(max_workers=args.workers) as ex:
            futures = {
                ex.submit(download_file, session, url, dest, args.timeout, verify): (filename, dest)
                for filename, url, dest in batch
            }
            for fut in as_completed(futures):
                filename, dest = futures[fut]
                success, msg = fut.result()
                if success:
                    ok += 1
                else:
                    fail += 1
                    print(f"CHYBA: {filename} -> {msg}")

    print("\n=== SUMAR ===")
    print(f"Uspech: {ok}")
    print(f"Chyby:  {fail}")
    print(f"Output: {root_out}")

if __name__ == "__main__":
    main()