#!/usr/bin/env python3
"""Jednoduche mapovanie SHMU: ind_kli (11800+) -> nazov stanice z ms.pdf."""

from __future__ import annotations

import argparse
import io
import json
import re
import sys
from pathlib import Path

import requests
from pypdf import PdfReader

MS_PDF_URL = "https://www.shmu.sk/File/metaklin/ms.pdf"


def fetch_pdf_bytes(url: str, timeout: int = 40) -> bytes:
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()
    return response.content


def is_number_token(token: str) -> bool:
    cleaned = re.sub(r"[^\d.]", "", token)
    return bool(cleaned) and bool(re.fullmatch(r"\d+(?:\.\d+)?", cleaned))


def is_coord_token(token: str) -> bool:
    cleaned = re.sub(r"\D", "", token)
    return bool(cleaned) and len(cleaned) <= 2


def find_station_name_end(parts: list[str]) -> int | None:
    for idx in range(1, len(parts) - 7):
        coord_block = parts[idx : idx + 6]
        altitude_block = parts[idx + 6 : idx + 8]
        if len(coord_block) < 6 or len(altitude_block) < 2:
            continue
        if all(is_coord_token(token) for token in coord_block) and all(
            is_number_token(token) for token in altitude_block
        ):
            return idx
    return None


def build_ind_kli_map(pdf_bytes: bytes, min_ind_kli: int = 11800) -> dict[str, str]:
    text = "\n".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(pdf_bytes)).pages)
    raw_lines = [" ".join(line.split()) for line in text.splitlines() if line.strip()]

    mapping: dict[str, str] = {}
    pending_code: str | None = None
    pending_name: str = ""

    for line in raw_lines:
        # Ak predtym prisiel samostatny kod, pripoj nasledujuci riadok k nemu.
        if pending_code is not None and not re.match(r"^\d{3,5}\b", line):
            line = f"{pending_code} {pending_name} {line}".strip()
            pending_code = None
            pending_name = ""

        only_code = re.fullmatch(r"(\d{3,5})", line)
        if only_code:
            pending_code = only_code.group(1)
            pending_name = ""
            continue

        parts = line.split()
        if not parts or not re.fullmatch(r"\d{3,5}", parts[0]):
            continue

        code = parts[0]
        if int(code) < min_ind_kli:
            continue

        name_end_idx = find_station_name_end(parts)

        if name_end_idx is None:
            pending_code = code
            pending_name = " ".join(parts[1:]).strip()
            continue

        station_name = " ".join(parts[1:name_end_idx]).strip()
        if not station_name and pending_code == code and pending_name:
            station_name = pending_name

        if station_name and code not in mapping:
            mapping[code] = station_name

        pending_code = None
        pending_name = ""

    return mapping


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Hash mapa SHMU ind_kli -> stanica (od 11800)")
    parser.add_argument("--ind-kli", default="", help="Vypis konkretny kod, napr. 11865")
    parser.add_argument("--list", action="store_true", help="Vypise cele mapovanie")
    parser.add_argument("--json", action="store_true", help="JSON vystup")
    parser.add_argument("--save-json", default="", help="Ulozi mapovanie do JSON")
    parser.add_argument("--url", default=MS_PDF_URL, help="URL na SHMU ms.pdf")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        mapping = build_ind_kli_map(fetch_pdf_bytes(args.url))
    except requests.RequestException as exc:
        print(f"Chyba pri stahovani PDF: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Chyba pri parsovani PDF: {exc}", file=sys.stderr)
        return 1

    if not mapping:
        print("Nepodarilo sa vyparsovat mapovanie.", file=sys.stderr)
        return 1

    if args.save_json:
        out = Path(args.save_json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(mapping, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Ulozene: {out}")

    if args.ind_kli:
        name = mapping.get(args.ind_kli)
        if name is None:
            print(f"ind_kli {args.ind_kli} sa nenasiel")
        else:
            if args.json:
                print(json.dumps({args.ind_kli: name}, ensure_ascii=False, indent=2))
            else:
                print(f"{args.ind_kli}\t{name}")
        return 0

    if args.list:
        if args.json:
            print(json.dumps(mapping, ensure_ascii=False, indent=2))
        else:
            for key in sorted(mapping, key=lambda x: int(x)):
                print(f"{key}\t{mapping[key]}")
        return 0

    print(f"Nacitanych stanic od 11800: {len(mapping)}")
    print("Pouzi --ind-kli 11865 alebo --list")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

