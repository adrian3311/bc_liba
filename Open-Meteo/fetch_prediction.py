"""
Skript na ziskanie predikcnych dat z Open-Meteo historical forecast API.
"""

import argparse
from datetime import datetime

from openmeteo_utils import create_client, resolve_city_to_coords, response_to_dataframe

PREDICTION_URL = "https://historical-forecast-api.open-meteo.com/v1/forecast"


def fetch_prediction_data(
    client,
    lat: float,
    lon: float,
    start_date: str,
    end_date: str,
    variables: list[str],
    timezone: str,
    mode: str,
):
    """Stiahne predikcne data z historical forecast API pre hourly alebo daily rezim."""
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start_date,
        "end_date": end_date,
        "timezone": timezone,
        mode: ",".join(variables),
    }
    responses = client.weather_api(PREDICTION_URL, params=params)
    if not responses:
        raise RuntimeError("Prediction API nevratilo ziadne odpovede.")
    return responses[0]


def parse_date(value: str) -> str:
    """Validuj datum vo formate YYYY-MM-DD."""
    try:
        datetime.strptime(value, "%Y-%m-%d")
        return value
    except ValueError:
        raise ValueError(f"Neplatny format datumu: {value}. Pouzi YYYY-MM-DD")


def parse_args():
    """Parsuj CLI argumenty."""
    ap = argparse.ArgumentParser(description="Ziskaj predikcne data z Open-Meteo historical forecast API.")
    ap.add_argument("--city", required=True, help="Mesto (napr. Zilina)")
    ap.add_argument("--start-date", required=True, help="Datum od (YYYY-MM-DD)")
    ap.add_argument("--end-date", required=True, help="Datum do (YYYY-MM-DD)")
    ap.add_argument("--mode", choices=["hourly", "daily"], default="hourly", help="Rezolucia dat")
    ap.add_argument("--hourly", default="temperature_2m,cloud_cover,rain,snowfall,relative_humidity_2m,wind_speed_10m,wind_direction_10m,surface_pressure,shortwave_radiation,direct_radiation,diffuse_radiation,precipitation,weather_code,visibility,wind_gusts_10m,soil_temperature_0cm,soil_moisture_0_to_1cm,cape,et0_fao_evapotranspiration,vapour_pressure_deficit", help="Hodinove premenne (csv)")
    ap.add_argument("--daily", default="temperature_2m_max,temperature_2m_min,temperature_2m_mean,precipitation_sum,rain_sum,snowfall_sum,precipitation_hours,sunshine_duration,wind_speed_10m_max,wind_gusts_10m_max,wind_direction_10m_dominant,shortwave_radiation_sum,et0_fao_evapotranspiration,weather_code", help="Denne premenne (csv)")
    ap.add_argument("--timezone", default="auto", help="Casova zona")
    return ap.parse_args()


def main():
    """Hlavna funkcia scriptu."""
    args = parse_args()

    start = parse_date(args.start_date)
    end = parse_date(args.end_date)
    if start > end:
        raise ValueError("start-date musi byt mensie alebo rovne end-date.")

    if args.mode == "hourly":
        variables = [v.strip() for v in args.hourly.split(",") if v.strip()]
    else:
        variables = [v.strip() for v in args.daily.split(",") if v.strip()]

    if not variables:
        raise ValueError("Musis zadat aspon jednu premennu pre zvoleny rezim.")

    client, http_session = create_client()
    print(f"Hladam mesto: {args.city}...")
    lat, lon, city_name = resolve_city_to_coords(http_session, args.city)
    print(f"Najdene: {city_name} (lat={lat:.4f}, lon={lon:.4f})")

    print(f"\nStiahuvam predikcne data od {start} do {end}...")
    response = fetch_prediction_data(
        client,
        lat,
        lon,
        start,
        end,
        variables,
        args.timezone,
        args.mode,
    )
    df = response_to_dataframe(response, variables, args.mode)

    print(f"\n{'=' * 60}")
    print(f"PREDIKCNE DATA: {city_name}")
    print(f"{'=' * 60}")
    print(f"Obdobie: {start} az {end} | Zaznamov: {len(df)}")
    print(f"Rezim: {args.mode}")
    print(f"Premenne: {', '.join(variables)}")
    print("\nVsetky zaznamy:")
    if df.empty:
        print("Pre zadane obdobie sa nenasli ziadne data.")
    else:
        print(df.to_string(index=False))

    print(f"\n{'=' * 60}")
    print("STATISTIKY")
    print(f"{'=' * 60}")
    for var in variables:
        if var in df.columns:
            print(f"\n{var}: Min={df[var].min():.2f} | Max={df[var].max():.2f} | Priemer={df[var].mean():.2f}")


if __name__ == "__main__":
    main()

