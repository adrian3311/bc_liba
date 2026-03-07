"""Jednoduche porovnanie Open-Meteo predikcie vs reality s vypisom do konzoly."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

# Umozni import skriptov z rodicovskeho priecinka Open-Meteo
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from fetch_prediction import fetch_prediction_data  # type: ignore  # noqa: E402
from fetch_reality import fetch_reality_data  # type: ignore  # noqa: E402
from openmeteo_utils import create_client, resolve_city_to_coords, response_to_dataframe  # type: ignore  # noqa: E402


def parse_date(value: str) -> str:
    try:
        datetime.strptime(value, "%Y-%m-%d")
        return value
    except ValueError as exc:
        raise ValueError(f"Neplatny format datumu: {value}. Pouzi YYYY-MM-DD") from exc


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Porovnanie Open-Meteo predikcie a reality (vypis do konzoly).")
    parser.add_argument("--city", required=True, help="Mesto, napr. Zilina")
    parser.add_argument("--start-date", required=True, help="Datum od (YYYY-MM-DD)")
    parser.add_argument("--end-date", required=True, help="Datum do (YYYY-MM-DD)")
    parser.add_argument("--mode", choices=["hourly", "daily"], default="hourly", help="Rezolucia dat")
    parser.add_argument(
        "--variables",
        default="temperature_2m,cloud_cover",
        help="Premenne oddelene ciarkou, napr. temperature_2m,cloud_cover",
    )
    parser.add_argument("--timezone", default="auto", help="Casova zona")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        start_date = parse_date(args.start_date)
        end_date = parse_date(args.end_date)
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 2

    if start_date > end_date:
        print("start-date musi byt mensie alebo rovne end-date.", file=sys.stderr)
        return 2

    variables = [v.strip() for v in args.variables.split(",") if v.strip()]
    if not variables:
        print("Musis zadat aspon jednu premennu cez --variables.", file=sys.stderr)
        return 2

    client, http_session = create_client()

    try:
        lat, lon, city_name = resolve_city_to_coords(http_session, args.city)
    except Exception as exc:
        print(f"Chyba geokodovania: {exc}", file=sys.stderr)
        return 1

    try:
        pred_response = fetch_prediction_data(
            client,
            lat,
            lon,
            start_date,
            end_date,
            variables,
            args.timezone,
            args.mode,
        )
        real_response = fetch_reality_data(
            client,
            lat,
            lon,
            start_date,
            end_date,
            variables,
            args.timezone,
            args.mode,
        )
    except Exception as exc:
        print(f"Chyba pri stahovani dat: {exc}", file=sys.stderr)
        return 1

    df_pred = response_to_dataframe(pred_response, variables, args.mode)
    df_real = response_to_dataframe(real_response, variables, args.mode)

    merged = pd.merge(df_pred, df_real, on="date", how="inner", suffixes=("_pred", "_real"))

    print(f"\n{'=' * 70}")
    print("OPEN-METEO POROVNANIE: PREDIKCIA VS REALITA")
    print(f"{'=' * 70}")
    print(f"Mesto: {city_name}")
    print(f"Obdobie: {start_date} az {end_date}")
    print(f"Rezim: {args.mode}")
    print(f"Premenne: {', '.join(variables)}")
    print(f"Spolocnych zaznamov: {len(merged)}")

    if merged.empty:
        print("\nNenasiel sa prienik timestampov.")
        return 0

    print("\nVsetky porovnane zaznamy:")
    print(merged.to_string(index=False))

    print(f"\n{'=' * 70}")
    print("METRIKY (predikcia - realita)")
    print(f"{'=' * 70}")

    for var in variables:
        pred_col = f"{var}_pred"
        real_col = f"{var}_real"

        if pred_col not in merged.columns or real_col not in merged.columns:
            print(f"- {var}: chyba stlpec v porovnanych datach")
            continue

        valid = merged[[pred_col, real_col]].dropna()
        if valid.empty:
            print(f"- {var}: bez hodnot")
            continue

        diff = valid[pred_col] - valid[real_col]
        mae = diff.abs().mean()
        rmse = (diff.pow(2).mean()) ** 0.5
        bias = diff.mean()

        print(
            f"- {var}: count={len(valid)} | MAE={mae:.4f} | RMSE={rmse:.4f} | BIAS={bias:.4f}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

