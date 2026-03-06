"""
Spolocne utility funkcie pre Open-Meteo skripty.
"""

from typing import Tuple, cast

import openmeteo_requests
import pandas as pd
import requests_cache
from requests import Session
from retry_requests import retry

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"


def create_client() -> Tuple[openmeteo_requests.Client, requests_cache.CachedSession]:
    """Vytvori Open-Meteo klienta s cache a retry."""
    cache_session = requests_cache.CachedSession(".cache", expire_after=3600)
    retry_session = retry(cache_session, retries=5, backoff_factor=0.2)
    client = openmeteo_requests.Client(session=cast(Session, retry_session))
    return client, retry_session


def resolve_city_to_coords(http_session, city: str) -> Tuple[float, float, str]:
    """Geokoduje mesto na GPS suradnice pomocou Open-Meteo Geocoding API."""
    response = http_session.get(
        GEOCODING_URL,
        params={
            "name": city,
            "count": 1,
            "language": "en",
            "format": "json"
        },
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()
    results = data.get("results")

    if not results or len(results) == 0:
        raise ValueError(f"Mesto '{city}' sa nepodarilo najst v Open-Meteo geokodingu.")

    first = results[0]
    lat = first.get("latitude")
    lon = first.get("longitude")
    name = first.get("name", city)
    country = first.get("country", "")
    admin1 = first.get("admin1", "")

    # Zformatuj vhodny nazov mesta
    parts = [name]
    if admin1 and admin1 != name:
        parts.append(admin1)
    if country:
        parts.append(country)
    resolved_name = ", ".join(parts)

    return lat, lon, resolved_name


def response_to_dataframe(response, variables: list[str], mode: str = "hourly") -> pd.DataFrame:
    """Konvertuje Open-Meteo odpoved na pandas DataFrame pre hourly alebo daily rezim."""
    if mode == "hourly":
        section = response.Hourly()
    elif mode == "daily":
        section = response.Daily()
    else:
        raise ValueError(f"Neznamy rezim: {mode}")

    if len(variables) > 0:
        num_points = len(section.Variables(0).ValuesAsNumpy())
    else:
        num_points = 0

    date_utc = pd.date_range(
        start=pd.to_datetime(section.Time(), unit="s", utc=True),
        periods=num_points,
        freq=pd.Timedelta(seconds=section.Interval()),
    )

    timezone_name = response.Timezone()
    if isinstance(timezone_name, bytes):
        timezone_name = timezone_name.decode("utf-8", errors="ignore")

    try:
        date_local = date_utc.tz_convert(timezone_name).tz_localize(None)
    except Exception:
        date_local = (date_utc + pd.to_timedelta(response.UtcOffsetSeconds(), unit="s")).tz_localize(None)

    # Pri daily rezime je prehladnejsi datum bez casu.
    if mode == "daily":
        date_local = pd.to_datetime(date_local.date)

    data = {"date": date_local}

    for idx, variable_name in enumerate(variables):
        values = section.Variables(idx).ValuesAsNumpy()
        if len(values) != len(date_local):
            raise ValueError(
                f"Nesedi pocet timestampov ({len(date_local)}) a hodnot pre '{variable_name}' ({len(values)})."
            )
        data[variable_name] = values

    return pd.DataFrame(data=data)
