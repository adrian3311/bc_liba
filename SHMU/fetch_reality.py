"""
Nacita SHMU aws1min JSON a pripravi prakticky reality vystup.

Vstup:
- jeden JSON subor, priecinok so subormi, alebo glob pattern

Vystup:
- teplota `t`
- odhad oblacnosti `cloudiness_proxy` (0-100) z `sln_trv` a/alebo `zglo`
"""

import argparse
import glob
import json
from pathlib import Path

import numpy as np
import pandas as pd


def parse_args():
    ap = argparse.ArgumentParser(description="Spracuj SHMU aws1min JSON (teplota + odhad oblacnosti)")
    ap.add_argument(
        "--input",
        required=True,
        help="Vstup: JSON subor, priecinok, alebo glob pattern (napr. SHMU/downloadsPredictions/aws1min-20260203-*.json)",
    )
    ap.add_argument("--ind-kli", help="Volitelny filter stanice (ind_kli)")
    ap.add_argument(
        "--stations-csv",
        help="Volitelny CSV ciselnik stanic s minimalne stlpcami: ind_kli,lat,lon (a volitelne station_name)",
    )
    ap.add_argument("--stations-sep", default=",", help="Oddelovac v --stations-csv (predvolene ,)")
    ap.add_argument("--preview-rows", type=int, default=30, help="Kolko riadkov vypisat v preview")
    ap.add_argument("--export-csv", help="Volitelny vystupny CSV subor")
    return ap.parse_args()


def collect_input_files(input_arg: str) -> list[Path]:
    p = Path(input_arg)
    if p.is_file():
        return [p]
    if p.is_dir():
        return sorted(p.glob("*.json"))
    return [Path(x) for x in sorted(glob.glob(input_arg))]


def load_json_records(path: Path) -> pd.DataFrame:
    with path.open("r", encoding="utf-8") as f:
        payload = json.load(f)

    if isinstance(payload, dict) and isinstance(payload.get("data"), list):
        records = payload["data"]
    elif isinstance(payload, list):
        records = payload
    else:
        records = []

    df = pd.DataFrame(records)
    if not df.empty:
        df["_source_file"] = path.name
    return df


def to_numeric_if_exists(df: pd.DataFrame, col: str) -> pd.Series:
    if col not in df.columns:
        return pd.Series(index=df.index, dtype=float)
    return pd.to_numeric(df[col], errors="coerce")


def compute_cloudiness_proxy(df: pd.DataFrame) -> pd.DataFrame:
    proxy = pd.Series(np.nan, index=df.index, dtype=float)
    source = pd.Series("", index=df.index, dtype=object)

    # 1) Priorita: sln_trv (sekundy slnecneho svitu za minutu), 0..60
    sln = to_numeric_if_exists(df, "sln_trv")
    if not sln.empty:
        sln_norm = (sln / 60.0).clip(0.0, 1.0)
        cloud_from_sln = (1.0 - sln_norm) * 100.0
        mask = cloud_from_sln.notna()
        proxy[mask] = cloud_from_sln[mask]
        source[mask] = "sln_trv"

    # 2) Fallback: zglo (globalne ziarenie), vyssie ziarenie => menej oblakov
    zglo = to_numeric_if_exists(df, "zglo")
    if not zglo.empty and zglo.notna().any():
        ref = zglo.quantile(0.95)
        if pd.isna(ref) or ref <= 0:
            ref = zglo.max()
        if pd.notna(ref) and ref > 0:
            cloud_from_zglo = (1.0 - (zglo.clip(lower=0, upper=ref) / ref)) * 100.0
            mask = proxy.isna() & cloud_from_zglo.notna()
            proxy[mask] = cloud_from_zglo[mask]
            source[mask] = "zglo"

    df["cloudiness_proxy"] = proxy.clip(0, 100)
    df["cloudiness_proxy_source"] = source
    return df


def enrich_with_station_coordinates(df: pd.DataFrame, stations_csv: str, sep: str = ",") -> pd.DataFrame:
    """Doplni suradnice stanic do dataframe podla ind_kli."""
    station_df = pd.read_csv(stations_csv, sep=sep)
    required = {"ind_kli", "lat", "lon"}
    missing = required - set(station_df.columns)
    if missing:
        raise ValueError(
            f"V --stations-csv chybaju povinne stlpce: {sorted(missing)}. "
            "Ocakavane minimalne: ind_kli,lat,lon"
        )

    keep_cols = [c for c in ["ind_kli", "lat", "lon", "station_name"] if c in station_df.columns]
    station_df = station_df[keep_cols].copy()
    station_df["ind_kli"] = station_df["ind_kli"].astype(str)

    out = df.copy()
    if "ind_kli" in out.columns:
        out["ind_kli"] = out["ind_kli"].astype(str)
    out = out.merge(station_df, on="ind_kli", how="left")
    return out


def main():
    args = parse_args()
    files = collect_input_files(args.input)

    if not files:
        raise FileNotFoundError(f"Nenasli sa ziadne JSON subory pre: {args.input}")

    frames = []
    for fp in files:
        try:
            df = load_json_records(fp)
            if not df.empty:
                frames.append(df)
        except Exception as exc:
            print(f"Preskakujem {fp.name} (chyba citania): {exc}")

    if not frames:
        print("Nepodarilo sa nacitat ziadne zaznamy z JSON suborov.")
        return

    df = pd.concat(frames, ignore_index=True)

    if "minuta" in df.columns:
        df["minuta"] = pd.to_datetime(df["minuta"], errors="coerce")

    # Teplota
    if "t" in df.columns:
        df["t"] = pd.to_numeric(df["t"], errors="coerce")

    # Odhad oblacnosti
    df = compute_cloudiness_proxy(df)

    # Volitelne doplnenie suradnic
    if args.stations_csv:
        try:
            df = enrich_with_station_coordinates(df, args.stations_csv, sep=args.stations_sep)
        except Exception as exc:
            print(f"Pozor: nepodarilo sa doplnit suradnice zo stations CSV: {exc}")

    # Filter stanice
    if args.ind_kli:
        if "ind_kli" not in df.columns:
            print("Stlpec 'ind_kli' nie je v datach, filter sa neda aplikovat.")
        else:
            df = df[df["ind_kli"].astype(str) == str(args.ind_kli)].copy()
            if df.empty:
                print(f"Po filtri ind_kli={args.ind_kli} nezostali ziadne zaznamy.")
                return

    print(f"Nacitane subory: {len(files)}")
    print(f"Zaznamov: {len(df)}")
    if "ind_kli" in df.columns:
        print(f"Stanice: {df['ind_kli'].nunique()}")

    preview_cols = [
        "minuta",
        "ind_kli",
        "station_name",
        "lat",
        "lon",
        "t",
        "cloudiness_proxy",
        "cloudiness_proxy_source",
        "sln_trv",
        "zglo",
        "_source_file",
    ]
    preview_cols = [c for c in preview_cols if c in df.columns]

    print("\nPreview:")
    print(df[preview_cols].head(args.preview_rows).to_string(index=False))

    print("\nSTATISTIKY")
    if "t" in df.columns and df["t"].notna().any():
        print(
            f"t (st.C): min={df['t'].min():.2f}, max={df['t'].max():.2f}, "
            f"mean={df['t'].mean():.2f}"
        )
    if "cloudiness_proxy" in df.columns and df["cloudiness_proxy"].notna().any():
        print(
            f"cloudiness_proxy (%): min={df['cloudiness_proxy'].min():.2f}, "
            f"max={df['cloudiness_proxy'].max():.2f}, mean={df['cloudiness_proxy'].mean():.2f}"
        )

    if args.export_csv:
        out = Path(args.export_csv)
        out.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(out, index=False)
        print(f"\nCSV export: {out}")


if __name__ == "__main__":
    main()

