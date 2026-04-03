import importlib.util
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT_DIR = Path(__file__).resolve().parent.parent
OPEN_METEO_DIR = ROOT_DIR / "Open-Meteo"
VC_DIR = ROOT_DIR / "Visual-Crossing"
MET_DIR = ROOT_DIR / "MET"
METEOSOURCE_DIR = ROOT_DIR / "MeteoSource"
SHMU_DIR = ROOT_DIR / "SHMU"
SOLCAST_DIR = ROOT_DIR / "Solcast"
VC_API_KEY = os.getenv("VISUAL_CROSSING_API_KEY", "QBY2GE2MTCEFA8TB6586RXWZJ")
MS_API_KEY = os.getenv("METEOSOURCE_API_KEY", "kvoz0j3rt9h66wt9u8pmbtvgxwipbxbvrm7hcy2t")
SOLCAST_API_KEY = os.getenv("SOLCAST_API_KEY", "-XOgWsapTi3B3BVhkqsyhllWDM24dolU")
DEFAULT_SOLCAST_DATASET_TYPE = "radiation_and_weather"
DEFAULT_SHMU_DATA_TYPE = "aws1min"
SHMU_VERIFY_SSL = False

if str(OPEN_METEO_DIR) not in sys.path:
    sys.path.insert(0, str(OPEN_METEO_DIR))
if str(SHMU_DIR) not in sys.path:
    sys.path.insert(0, str(SHMU_DIR))


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Failed to load {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    try:
        spec.loader.exec_module(mod)
    except Exception:
        sys.modules.pop(name, None)
        raise
    return mod


# --- Open-Meteo ---
OM_OK = False
OM_ERR = ""
# --- Visual Crossing ---
VC_OK = False
VC_ERR = ""
# --- MET ---
MET_OK = False
MET_ERR = ""
# --- MeteoSource ---
MS_OK = False
MS_ERR = ""
# --- SHMU ---
SHMU_OK = False
SHMU_ERR = ""
# --- Solcast ---
SOLCAST_OK = False
SOLCAST_ERR = ""

try:
    _om_pred = _load_module("om_fetch_prediction", OPEN_METEO_DIR / "fetch_prediction.py")
    _om_real = _load_module("om_fetch_reality",    OPEN_METEO_DIR / "fetch_reality.py")
    _om_util = _load_module("om_utils",            OPEN_METEO_DIR / "openmeteo_utils.py")
    om_fetch_prediction   = _om_pred.fetch_prediction_data
    om_fetch_reality      = _om_real.fetch_reality_data
    om_create_client      = _om_util.create_client
    om_resolve_city       = _om_util.resolve_city_to_coords
    om_to_dataframe       = _om_util.response_to_dataframe
    OM_OK = True
except Exception as e:
    OM_OK = False
    OM_ERR = str(e)

try:
    _vc = _load_module("vc_fetch_prediction", VC_DIR / "fetch_prediction.py")
    vc_build_location       = _vc.build_location
    vc_fetch_prediction     = _vc.fetch_prediction_data
    vc_payload_to_rows      = _vc.payload_to_rows
    VC_OK = True
except Exception as e:
    VC_OK = False
    VC_ERR = str(e)

try:
    _met = _load_module("met_fetch_prediction", MET_DIR / "fetch_prediction.py")
    met_resolve_city = _met.resolve_city
    met_fetch_forecast = _met.fetch_forecast
    met_filter_timeseries = _met.filter_timeseries
    met_extract_variable = _met.extract_variable
    MET_OK = True
except Exception as e:
    MET_OK = False
    MET_ERR = str(e)

try:
    _ms = _load_module("meteosource_fetch_prediction", METEOSOURCE_DIR / "fetch_prediction.py")
    ms_find_place = _ms.find_place
    ms_fetch_daily_data = _ms.fetch_daily_data
    ms_fetch_hourly_data = _ms.fetch_hourly_data
    ms_extract_daily_rows = _ms.extract_daily_rows
    ms_extract_hourly_rows = _ms.extract_hourly_rows
    MS_OK = True
except Exception as e:
    MS_OK = False
    MS_ERR = str(e)

try:
    _shmu = _load_module("shmu_fetch_prediction", SHMU_DIR / "fetch_prediction.py")
    shmu_fetch_data = _shmu.fetch_shmu_data
    SHMU_OK = True
except Exception as e:
    SHMU_OK = False
    SHMU_ERR = str(e)

try:
    _solcast = _load_module("solcast_fetch_prediction", SOLCAST_DIR / "fetch_prediction.py")
    solcast_resolve_city_to_coords = _solcast.resolve_city_to_coords
    solcast_fetch_prediction_data = _solcast.fetch_prediction_data
    solcast_payload_to_rows = _solcast.payload_to_rows
    SOLCAST_OK = True
except Exception as e:
    SOLCAST_OK = False
    SOLCAST_ERR = str(e)

# ── helpers ────────────────────────────────────────────────────────────────

def _clean_met_city_name(name: str) -> str:
    """Shorten long MET geocoding labels for cleaner captions."""
    cleaned = name.replace(", Žilinský kraj", "").replace(", Stredné Slovensko", "")
    return cleaned.strip().strip(",")


def _csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8")


def _show_provider_fetch_notice() -> None:
    return


def _show_df(label: str, df: pd.DataFrame, file_prefix: str, city: str, date_from, date_to):
    st.subheader(label)
    st.dataframe(df, use_container_width=True)
    st.download_button(
        f"Download {label} CSV",
        data=_csv_bytes(df),
        file_name=f"{file_prefix}_{city}_{date_from}_{date_to}.csv",
        mime="text/csv",
        key=f"dl_{file_prefix}_{label}",
    )


def _show_chart(df: pd.DataFrame, key_suffix: str):
    numeric_cols = [c for c in df.columns if c != "date" and pd.api.types.is_numeric_dtype(df[c])]
    if not numeric_cols:
        st.info("No numeric columns available for charting.")
        return
    chosen = st.multiselect("Variables for chart", options=numeric_cols,
                             default=numeric_cols[:min(3, len(numeric_cols))],
                             key=f"chart_{key_suffix}")
    if not chosen:
        st.info("Select at least one variable.")
        return
    plot = df[["date", *chosen]].copy()
    plot["date"] = pd.to_datetime(plot["date"])
    st.line_chart(plot.set_index("date"))


def _show_comparison(merged: pd.DataFrame, variables: list[str], key_suffix: str):
    chart_var = st.selectbox("Comparison variable", options=variables, key=f"cmp_{key_suffix}")
    pc, rc = f"{chart_var}_pred", f"{chart_var}_real"
    if pc not in merged.columns or rc not in merged.columns:
        st.info("Selected variable is not available in both sources.")
        return
    comp = merged[["date", pc, rc]].copy()
    comp["date"] = pd.to_datetime(comp["date"])
    comp = comp.set_index("date").rename(columns={pc: "prediction", rc: "reality"})
    st.line_chart(comp)

    metrics = []
    for var in variables:
        p, r = f"{var}_pred", f"{var}_real"
        if p not in merged.columns or r not in merged.columns:
            continue
        v = merged[[p, r]].apply(pd.to_numeric, errors="coerce").dropna()
        if v.empty:
            continue
        d = v[p] - v[r]
        metrics.append({"variable": var, "count": len(v),
                         "mae": round(d.abs().mean(), 4),
                         "rmse": round((d**2).mean()**0.5, 4),
                         "bias": round(d.mean(), 4)})
    if metrics:
        st.subheader("Metrics (prediction - reality)")
        st.dataframe(pd.DataFrame(metrics), use_container_width=True)


def _normalize_date_series(series: pd.Series) -> pd.Series:
    """Normalize timestamps to timezone-naive datetime64[ns] for safe merges."""
    dt = pd.to_datetime(series, errors="coerce", utc=True)
    return dt.dt.tz_localize(None)


def _resolve_provider_col(base_col: str, label: str, provider_columns: set[str], mode: str) -> str | None:
    if base_col in provider_columns:
        return base_col
    if mode != "daily":
        return None

    lower = label.lower()
    if "max" in lower and f"{base_col}_max" in provider_columns:
        return f"{base_col}_max"
    if "min" in lower and f"{base_col}_min" in provider_columns:
        return f"{base_col}_min"
    if "mean" in lower and f"{base_col}_mean" in provider_columns:
        return f"{base_col}_mean"
    if ("sum" in lower or "precip" in lower or "rain" in lower or "snow" in lower) and f"{base_col}_sum" in provider_columns:
        return f"{base_col}_sum"

    prefix = f"{base_col}_"
    for col in sorted(provider_columns):
        if col.startswith(prefix):
            return col
    return None


def _build_provider_comparison_df(
    provider_df: pd.DataFrame,
    reality_df: pd.DataFrame,
    selected_labels: list[str],
    variable_map: dict,
    provider_index: int,
    mode: str,
) -> tuple[pd.DataFrame, list[str]]:
    if provider_df.empty or reality_df.empty:
        return pd.DataFrame(), []

    p = provider_df.copy()
    r = reality_df.copy()
    p["date"] = _normalize_date_series(p["date"])
    r["date"] = _normalize_date_series(r["date"])

    p_cols = set(p.columns)
    merged = None
    comparable_labels: list[str] = []

    for label in selected_labels:
        om_col = variable_map[label][0]
        provider_base = variable_map[label][provider_index]
        if om_col is None or provider_base is None or om_col not in r.columns:
            continue

        provider_col = _resolve_provider_col(provider_base, label, p_cols, mode)
        if provider_col is None:
            continue

        left = p[["date", provider_col]].rename(columns={provider_col: f"{label}_pred"})
        right = r[["date", om_col]].rename(columns={om_col: f"{label}_real"})
        pair = pd.merge(left, right, on="date", how="inner")
        if pair.empty:
            continue

        comparable_labels.append(label)
        merged = pair if merged is None else pd.merge(merged, pair, on="date", how="outer")

    if merged is None or merged.empty:
        return pd.DataFrame(), []

    merged = merged.sort_values("date").reset_index(drop=True)
    return merged, comparable_labels


def _show_provider_comparison_chart(merged_df: pd.DataFrame, labels: list[str], key_suffix: str):
    if merged_df.empty or not labels:
        st.info("No comparable data for shared chart.")
        return

    label = st.selectbox("Comparison variable", options=labels, key=f"cmp_provider_{key_suffix}")
    pred_col = f"{label}_pred"
    real_col = f"{label}_real"
    if pred_col not in merged_df.columns or real_col not in merged_df.columns:
        st.info("Selected variable is not available in both series.")
        return

    chart_df = merged_df[["date", pred_col, real_col]].copy()
    chart_df["date"] = pd.to_datetime(chart_df["date"], errors="coerce")
    chart_df = chart_df.set_index("date").rename(columns={pred_col: "prediction", real_col: "reality"})
    st.line_chart(chart_df)


# ── cached loaders ──────────────────────────────────────────────────────────

@st.cache_data(show_spinner=False)
def load_openmeteo(city, start_date, end_date, mode, variables, timezone, source):
    client, session = om_create_client()
    lat, lon, city_name = om_resolve_city(session, city)
    frames: dict[str, pd.DataFrame] = {}
    if source in ("prediction", "both"):
        r = om_fetch_prediction(client, lat, lon, start_date, end_date, list(variables), timezone, mode)
        frames["prediction"] = om_to_dataframe(r, list(variables), mode)
    if source in ("reality", "both"):
        r = om_fetch_reality(client, lat, lon, start_date, end_date, list(variables), timezone, mode)
        frames["reality"] = om_to_dataframe(r, list(variables), mode)
    merged = None
    if source == "both" and "prediction" in frames and "reality" in frames:
        merged = pd.merge(frames["prediction"], frames["reality"], on="date",
                          how="inner", suffixes=("_pred", "_real"))
    return city_name, lat, lon, frames, merged


@st.cache_data(show_spinner=False)
def load_visualcrossing(city, start_date, end_date, mode, variables, timezone, unit_group, api_key):
    location = vc_build_location(city, None, None)
    payload, _ = vc_fetch_prediction(location, start_date, end_date, list(variables),
                                      timezone, mode, unit_group, api_key)
    city_name = payload.get("resolvedAddress", city)
    rows = vc_payload_to_rows(payload, list(variables), mode)
    df = pd.DataFrame(rows)
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
    return city_name, df


@st.cache_data(show_spinner=False)
def load_met(city, start_date, end_date, mode, variables, altitude):
    lat, lon, city_name = met_resolve_city(city)
    payload = met_fetch_forecast(lat, lon, altitude)
    timeseries = payload.get("properties", {}).get("timeseries", [])

    start_dt = datetime.fromisoformat(f"{start_date}T00:00:00+00:00").astimezone(timezone.utc)
    end_dt = datetime.fromisoformat(f"{end_date}T23:59:59+00:00").astimezone(timezone.utc)
    filtered = met_filter_timeseries(timeseries, start_dt, end_dt)

    rows = []
    for entry in filtered:
        row = {"date": entry.get("time")}
        for var in variables:
            row[var] = met_extract_variable(entry, var)
        rows.append(row)

    df = pd.DataFrame(rows)
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce", utc=True)

    if mode == "daily" and not df.empty:
        value_cols = [c for c in df.columns if c != "date"]
        for col in value_cols:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df["day"] = df["date"].dt.strftime("%Y-%m-%d")

        grouped = df.groupby("day")
        out = pd.DataFrame({"date": grouped.size().index})
        for col in value_cols:
            if col == "temperature_2m":
                out[f"{col}_min"] = grouped[col].min().values
                out[f"{col}_max"] = grouped[col].max().values
                out[f"{col}_mean"] = grouped[col].mean().values
            elif col.startswith("precipitation_"):
                out[f"{col}_sum"] = grouped[col].sum(min_count=1).values
            else:
                out[f"{col}_mean"] = grouped[col].mean().values
        df = out

    return city_name, lat, lon, df


@st.cache_data(show_spinner=False)
def load_meteosource(city, start_date, end_date, mode, variables, api_key):
    place_id, city_name, lat, lon = ms_find_place(city, api_key)
    if mode == "hourly":
        payload, _ = ms_fetch_hourly_data(place_id, api_key)
        rows = ms_extract_hourly_rows(payload, list(variables), start_date, end_date)
    else:
        payload, _ = ms_fetch_daily_data(place_id, api_key)
        rows = ms_extract_daily_rows(payload, list(variables), start_date, end_date)

    df = pd.DataFrame(rows)
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
    return city_name, lat, lon, df


@st.cache_data(show_spinner=False)
def load_shmu(city, start_date, end_date, variables, data_file_type, verify_ssl):
    city_name, ind_kli, df = shmu_fetch_data(
        city=city,
        start_date=start_date,
        end_date=end_date,
        fields=list(variables),
        data_type=data_file_type,
        verify_ssl=verify_ssl,
    )
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
    return city_name, ind_kli, df


@st.cache_data(show_spinner=False)
def load_solcast(city, start_date, end_date, variables, dataset_type, api_key, mode):
    lat, lon, city_name = solcast_resolve_city_to_coords(city)
    payload, _ = solcast_fetch_prediction_data(
        latitude=lat,
        longitude=lon,
        start_date=start_date,
        end_date=end_date,
        output_parameters=list(variables),
        data_type=dataset_type,
        api_key=api_key,
    )
    rows = solcast_payload_to_rows(payload, list(variables))
    df = pd.DataFrame(rows)
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        # Solcast often returns 30-minute points; keep whole-hour records only.
        df = df[df["date"].dt.minute == 0].reset_index(drop=True)
    return city_name, lat, lon, df


# ── UI ──────────────────────────────────────────────────────────────────────

st.set_page_config(page_title="Weather Viewer", layout="wide")
st.title("Weather Viewer")
st.caption("Open-Meteo, Visual Crossing, MET, MeteoSource, SHMU, Solcast - provider comparison")

# ── Sidebar ────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Inputs")
    city = st.text_input("City", value="Zilina")
    date_from = st.date_input("Start date")
    date_to = st.date_input("End date")
    mode = st.selectbox("Mode", ["hourly", "daily"])
    om_source = st.selectbox("Source", ["predictions", "reality", "both"])
    om_source_internal = {"predictions": "prediction", "reality": "reality", "both": "both"}[om_source]

    # Shared variables — mapping OM name -> VC -> MET -> MeteoSource
    if mode == "hourly":
        VARIABLE_MAP = {
            "Temperature":          ("temperature_2m",           "temp",             "temperature_2m",           "temperature",          "air_temp"),
            "Cloud cover":          ("cloud_cover",              "cloudcover",       "cloud_cover",              "cloud_cover",          "cloud_opacity"),
            "Precipitation":        ("rain",                     "precip",           "precipitation_1h",         "precipitation_sum",    "precipitation_rate"),
            "Humidity":             ("relative_humidity_2m",     "humidity",         "humidity",                 "humidity",             "relative_humidity"),
            "Wind speed":           ("wind_speed_10m",           "windspeed",        "wind_speed",               "wind_speed",           "wind_speed_10m"),
            "Wind direction":       ("wind_direction_10m",       "winddir",          "wind_direction",           "wind_direction",       "wind_direction_10m"),
            "Wind gusts":           ("wind_gusts_10m",           "windgust",         "wind_speed_gust",          None,                   None),
            "Solar radiation":      ("shortwave_radiation",      "solarradiation",   None,                        None,                   "ghi"),
            "UV index":             (None,                       "uvindex",          "uv_index",                 "uv_index",             None),
            "Visibility":           ("visibility",               "visibility",       None,                        "visibility",           None),
            "Surface pressure":     ("surface_pressure",         "pressure",         "pressure",                 "pressure",             "surface_pressure"),
            "Dew point":            (None,                       "dewpoint",         "dew_point",                "dew_point",            "dewpoint_temp"),
            "Feels like":           (None,                       "feelslike",        None,                        "feels_like",           None),
            "Snow":                 ("snowfall",                 "snow",             None,                        None,                   "snow_depth"),
            "Weather code":         ("weather_code",             "conditions",       "symbol_1h",                "weather",              "weather_type"),
            "Precipitation prob.":  (None,                       None,               "precipitation_prob_1h",    None,                   None),
            "Thunder prob.":        (None,                       None,               "thunder_prob_1h",          None,                   None),
            "Fog":                  (None,                       None,               "fog",                      None,                   None),
            "CAPE":                 ("cape",                     "cape",             None,                        None,                   None),
            "Evapotranspiration":   ("et0_fao_evapotranspiration", None,             None,                        None,                   None),
            "Vapour pressure def.": ("vapour_pressure_deficit",  None,               None,                        None,                   None),
        }
        default_vars = ["Temperature", "Cloud cover", "Precipitation", "Wind speed", "Humidity"]
        SHMU_VARIABLE_MAP = {
            "Temperature": "t",
            "Precipitation": "zra_uhrn",
            "Humidity": "vlh_rel",
            "Wind speed": "vie_pr_rych",
            "Wind direction": "vie_pr_smer",
            "Wind gusts": "vie_max_rych",
            "Solar radiation": "zglo",
            "Visibility": "dohl",
            "Surface pressure": "tlak",
            "Snow": "sneh_pokr",
            "Weather code": "stav_poc",
            "Sunshine": "sln_trv",
        }
    else:
        VARIABLE_MAP = {
            "Max temperature":      ("temperature_2m_max",              "tempmax",      "temperature_2m",   "temperature_max",   None),
            "Min temperature":      ("temperature_2m_min",              "tempmin",      "temperature_2m",   "temperature_min",   None),
            "Mean temperature":     ("temperature_2m_mean",             "temp",         "temperature_2m",   "temperature",       None),
            "Precipitation":        ("precipitation_sum",               "precip",       "precipitation_1h", "precipitation_sum", None),
            "Humidity":             (None,                              "humidity",     "humidity",         "humidity",          None),
            "Wind speed":           ("wind_speed_10m_max",              "windspeed",    "wind_speed",       "wind_speed",        None),
            "Wind direction":       ("wind_direction_10m_dominant",     "winddir",      "wind_direction",   None,                None),
            "Wind gusts":           ("wind_gusts_10m_max",              "windgust",     "wind_speed_gust",  None,                None),
            "Solar radiation":      ("shortwave_radiation_sum",         "solarradiation", None,              None,                None),
            "UV index":             (None,                              "uvindex",      "uv_index",         "uv_index",          None),
            "Visibility":           (None,                              "visibility",   None,                "visibility",        None),
            "Pressure":             (None,                              "pressure",     "pressure",         "pressure",          None),
            "Snow":                 ("snowfall_sum",                    "snow",         None,                None,                None),
            "Rain":                 ("rain_sum",                        None,           None,                None,                None),
            "Sunshine":             ("sunshine_duration",               "solarenergy",  None,                None,                None),
            "Precip. hours":        ("precipitation_hours",             None,           None,                None,                None),
            "Weather code":         ("weather_code",                    "conditions",   "symbol_1h",        "weather",           None),
            "Evapotranspiration":   ("et0_fao_evapotranspiration",      None,           None,                None,                None),
        }
        default_vars = ["Max temperature", "Min temperature", "Precipitation", "Wind speed"]
        SHMU_VARIABLE_MAP = {}

    selected_vars = st.multiselect("Variables", options=list(VARIABLE_MAP.keys()), default=default_vars)

    # Z vybranych nazvov odvodime OM, VC, MET a MeteoSource zoznamy
    om_variables = [VARIABLE_MAP[v][0] for v in selected_vars if VARIABLE_MAP[v][0] is not None]
    vc_variables = [VARIABLE_MAP[v][1] for v in selected_vars if VARIABLE_MAP[v][1] is not None]
    met_variables = [VARIABLE_MAP[v][2] for v in selected_vars if VARIABLE_MAP[v][2] is not None]
    ms_variables = [VARIABLE_MAP[v][3] for v in selected_vars if VARIABLE_MAP[v][3] is not None]
    solcast_variables = [VARIABLE_MAP[v][4] for v in selected_vars if VARIABLE_MAP[v][4] is not None]
    shmu_variables = [SHMU_VARIABLE_MAP[v] for v in selected_vars if v in SHMU_VARIABLE_MAP]

    st.divider()
    st.subheader("Open-Meteo")
    use_openmeteo = st.checkbox("Enable Open-Meteo", value=True)
    om_timezone = st.text_input("Timezone (OM)", value="auto")

    st.subheader("Visual Crossing")
    use_visualcrossing = st.checkbox("Enable Visual Crossing", value=True)
    vc_unit_group = st.selectbox("Units (VC)", ["metric", "us", "uk", "base"])
    vc_timezone = st.text_input("Timezone (VC)", value="Europe/Bratislava")

    st.subheader("MET")
    use_met = st.checkbox("Enable MET", value=True)
    met_altitude_raw = st.text_input("Altitude (MET, optional)", value="")

    st.subheader("MeteoSource")
    use_meteosource = st.checkbox("Enable MeteoSource", value=True)

    st.subheader("Solcast")
    use_solcast = st.checkbox("Enable Solcast", value=True)

    st.subheader("SHMU")
    use_shmu = st.checkbox("Enable SHMU", value=True)

    run_btn = st.button("Load data", type="primary")

solcast_api_key = SOLCAST_API_KEY

# ── Hlavná plocha ──────────��───────────────────────────────────────────────
if not run_btn:
    st.info("Click **Load data** in the sidebar.")
    st.stop()

if date_from > date_to:
    st.error("Start date must be before or equal to end date.")
    st.stop()

om_reality_baseline = pd.DataFrame()

reality_only_mode = om_source_internal == "reality"
if reality_only_mode:
    col_om = st.container()
    shmu_container, solcast_container = st.columns(2)
else:
    col_om, col_vc = st.columns(2)
    row2_col_met, row2_col_ms = st.columns(2)
    shmu_container, solcast_container = st.columns(2)

# ── Open-Meteo stĺpec ──────────────────────────────────────────────────────
with col_om:
    st.header("🌍 Open-Meteo")
    try:
        if not use_openmeteo:
            st.info("Open-Meteo is disabled in the sidebar.")
        elif not OM_OK:
            st.error(f"Module load failed: {OM_ERR}")
        elif not om_variables:
            st.warning("Select at least one variable.")
        else:
            with st.spinner("Loading Open-Meteo..."):
                try:
                    city_name_om, lat, lon, frames, merged = load_openmeteo(
                        city, str(date_from), str(date_to), mode,
                        tuple(om_variables), om_timezone, om_source_internal,
                    )
                except Exception:
                    _show_provider_fetch_notice()
                    frames, merged, lat, lon = {}, None, None, None
                    city_name_om = city

            if lat is not None:
                st.caption(f"{city_name_om} (lat={lat:.4f}, lon={lon:.4f})")
            else:
                st.caption(city_name_om)

            tab_labels_om = []
            if om_source_internal == "both":
                if merged is not None:
                    tab_labels_om = ["Data", "Comparison"]
            else:
                if "prediction" in frames:
                    tab_labels_om.append("Data")
                if "reality" in frames:
                    tab_labels_om.append("Data")
                if frames:
                    tab_labels_om.append("Chart")

            if tab_labels_om:
                tabs_om = st.tabs(tab_labels_om)
                if om_source_internal == "both" and merged is not None:
                    om_reality_baseline = frames.get("reality", pd.DataFrame())
                    with tabs_om[0]:
                        _show_df("Prediction + Reality", merged, "om_cmp", city, date_from, date_to)
                    with tabs_om[1]:
                        _show_comparison(merged, list(om_variables), "om")
                else:
                    ti = 0
                    if "prediction" in frames:
                        with tabs_om[ti]:
                            _show_df("Prediction", frames["prediction"], "om_pred", city, date_from, date_to)
                        ti += 1
                    if "reality" in frames:
                        with tabs_om[ti]:
                            _show_df("Reality", frames["reality"], "om_real", city, date_from, date_to)
                        ti += 1
                    if frames:
                        with tabs_om[ti]:
                            if "prediction" in frames:
                                _show_chart(frames["prediction"], "om_pred_chart")
                            elif "reality" in frames:
                                _show_chart(frames["reality"], "om_real_chart")
                            else:
                                st.info("No data to chart.")
    except Exception as exc:
        st.error(f"Open-Meteo section failed: {exc}")

# ── Visual Crossing stĺpec ─────────────────────────────────────────────────
if not reality_only_mode:
    with col_vc:
        st.header("🌤 Visual Crossing")
        try:
            if not use_visualcrossing:
                st.info("Visual Crossing is disabled in the sidebar.")
            elif not VC_OK:
                st.error(f"Module load failed: {VC_ERR}")
            elif not vc_variables:
                st.warning("Select at least one variable.")
            else:
                with st.spinner("Loading Visual Crossing..."):
                    try:
                        city_name_vc, df_vc = load_visualcrossing(
                            city, str(date_from), str(date_to), mode,
                            tuple(vc_variables), vc_timezone, vc_unit_group, VC_API_KEY,
                        )
                    except Exception:
                        _show_provider_fetch_notice()
                        df_vc = pd.DataFrame()
                        city_name_vc = city

                st.caption(city_name_vc)

                tab_data_vc, tab_graf_vc = st.tabs(["Data", "Chart"])
                with tab_data_vc:
                    if om_source_internal == "both":
                        merged_vc, labels_vc = _build_provider_comparison_df(
                            df_vc, om_reality_baseline, selected_vars, VARIABLE_MAP, 1, mode
                        )
                        if not merged_vc.empty:
                            _show_df("Prediction + Reality", merged_vc, "vc_cmp", city, date_from, date_to)
                        else:
                            st.info("No comparable prediction/reality data.")
                    elif not df_vc.empty:
                        _show_df("Prediction", df_vc, "vc_pred", city, date_from, date_to)
                    else:
                        st.info("No data.")
                with tab_graf_vc:
                    if om_source_internal == "both":
                        merged_vc, labels_vc = _build_provider_comparison_df(
                            df_vc, om_reality_baseline, selected_vars, VARIABLE_MAP, 1, mode
                        )
                        _show_provider_comparison_chart(merged_vc, labels_vc, "vc")
                    elif not df_vc.empty:
                        _show_chart(df_vc, "vc")
                    else:
                        st.info("No data to chart.")
        except Exception as exc:
            st.error(f"Visual Crossing section failed: {exc}")

# ── MET stĺpec ─────────────────────────────────────────────────────────────
if not reality_only_mode:
    with row2_col_met:
        st.header("🛰 MET")
        try:
            if not use_met:
                st.info("MET is disabled in the sidebar.")
            elif not MET_OK:
                st.error(f"Module load failed: {MET_ERR}")
            elif not met_variables:
                st.warning("No MET-equivalent variables for current selection.")
            else:
                altitude = None
                if met_altitude_raw.strip():
                    try:
                        altitude = int(met_altitude_raw.strip())
                    except ValueError:
                        st.warning("Altitude must be an integer. Ignoring this value.")

                with st.spinner("Loading MET..."):
                    try:
                        city_name_met, lat_met, lon_met, df_met = load_met(
                            city, str(date_from), str(date_to), mode, tuple(met_variables), altitude
                        )
                    except Exception:
                        _show_provider_fetch_notice()
                        df_met = pd.DataFrame()
                        city_name_met = city
                        lat_met = None
                        lon_met = None

                if lat_met is not None:
                    st.caption(f"{_clean_met_city_name(city_name_met)} (lat={lat_met:.4f}, lon={lon_met:.4f})")
                else:
                    st.caption(_clean_met_city_name(city_name_met))

                tab_data_met, tab_graf_met = st.tabs(["Data", "Chart"])
                with tab_data_met:
                    if om_source_internal == "both":
                        merged_met, labels_met = _build_provider_comparison_df(
                            df_met, om_reality_baseline, selected_vars, VARIABLE_MAP, 2, mode
                        )
                        if not merged_met.empty:
                            _show_df("Prediction + Reality", merged_met, "met_cmp", city, date_from, date_to)
                        else:
                            st.info("No comparable prediction/reality data.")
                    elif not df_met.empty:
                        _show_df("Prediction", df_met, "met_pred", city, date_from, date_to)
                    else:
                        st.info("No data.")
                with tab_graf_met:
                    if om_source_internal == "both":
                        merged_met, labels_met = _build_provider_comparison_df(
                            df_met, om_reality_baseline, selected_vars, VARIABLE_MAP, 2, mode
                        )
                        _show_provider_comparison_chart(merged_met, labels_met, "met")
                    elif not df_met.empty:
                        _show_chart(df_met, "met")
                    else:
                        st.info("No data to chart.")
        except Exception as exc:
            st.error(f"MET section failed: {exc}")

if not reality_only_mode:
    with row2_col_ms:
        st.header("☁ MeteoSource")
        try:
            if not use_meteosource:
                st.info("MeteoSource is disabled in the sidebar.")
            elif not MS_OK:
                st.error(f"Module load failed: {MS_ERR}")
            elif not MS_API_KEY:
                st.error("Missing MeteoSource API key. Set METEOSOURCE_API_KEY or update app.py")
            elif not ms_variables:
                st.warning("No MeteoSource-equivalent variables for current selection.")
            else:
                with st.spinner("Loading MeteoSource..."):
                    try:
                        city_name_ms, lat_ms, lon_ms, df_ms = load_meteosource(
                            city,
                            str(date_from),
                            str(date_to),
                            mode,
                            tuple(ms_variables),
                            MS_API_KEY,
                        )
                    except Exception:
                        _show_provider_fetch_notice()
                        df_ms = pd.DataFrame()
                        city_name_ms = city
                        lat_ms = None
                        lon_ms = None

                if lat_ms is not None:
                    st.caption(f"{city_name_ms} (lat={lat_ms}, lon={lon_ms})")
                else:
                    st.caption(city_name_ms)

                tab_data_ms, tab_graf_ms = st.tabs(["Data", "Chart"])
                with tab_data_ms:
                    if om_source_internal == "both":
                        merged_ms, labels_ms = _build_provider_comparison_df(
                            df_ms, om_reality_baseline, selected_vars, VARIABLE_MAP, 3, mode
                        )
                        if not merged_ms.empty:
                            _show_df("Prediction + Reality", merged_ms, "ms_cmp", city, date_from, date_to)
                        else:
                            st.info("No comparable prediction/reality data.")
                    elif not df_ms.empty:
                        _show_df("Prediction", df_ms, "ms_pred", city, date_from, date_to)
                    else:
                        st.info("No data.")
                with tab_graf_ms:
                    if om_source_internal == "both":
                        merged_ms, labels_ms = _build_provider_comparison_df(
                            df_ms, om_reality_baseline, selected_vars, VARIABLE_MAP, 3, mode
                        )
                        _show_provider_comparison_chart(merged_ms, labels_ms, "ms")
                    elif not df_ms.empty:
                        _show_chart(df_ms, "ms")
                    else:
                        st.info("No data to chart.")
        except Exception as exc:
            st.error(f"MeteoSource section failed: {exc}")

if not reality_only_mode:
    with shmu_container:
        st.header("🇸🇰 SHMU")
        try:
            if not use_shmu:
                st.info("SHMU is disabled in the sidebar.")
            elif not SHMU_OK:
                st.error(f"Module load failed: {SHMU_ERR}")
            elif mode != "hourly":
                st.info("SHMU currently supports hourly mode only.")
            elif not shmu_variables:
                st.warning("No SHMU-equivalent variables for current selection.")
            else:
                with st.spinner("Loading SHMU..."):
                    try:
                        city_name_shmu, ind_kli_shmu, df_shmu = load_shmu(
                            city,
                            str(date_from),
                            str(date_to),
                            tuple(shmu_variables),
                            DEFAULT_SHMU_DATA_TYPE,
                            SHMU_VERIFY_SSL,
                        )
                    except Exception:
                        _show_provider_fetch_notice()
                        city_name_shmu = city
                        ind_kli_shmu = None
                        df_shmu = pd.DataFrame()

                if ind_kli_shmu is not None:
                    st.caption(f"{city_name_shmu} | ind_kli={ind_kli_shmu}")
                else:
                    st.caption(city_name_shmu)

                tab_data_shmu, tab_chart_shmu = st.tabs(["Data", "Chart"])
                with tab_data_shmu:
                    if not df_shmu.empty:
                        df_shmu_table = df_shmu.drop(columns=["minuta", "ind_kli"], errors="ignore")
                        _show_df("Prediction", df_shmu_table, "shmu_obs", city, date_from, date_to)
                    else:
                        st.info("No data.")
                with tab_chart_shmu:
                    if not df_shmu.empty:
                        _show_chart(df_shmu, "shmu")
                    else:
                        st.info("No data to chart.")
        except Exception as exc:
            st.error(f"SHMU section failed: {exc}")

    with solcast_container:
        st.header("☀ Solcast")
        try:
            if not use_solcast:
                st.info("Solcast is disabled in the sidebar.")
            elif not SOLCAST_OK:
                st.error(f"Module load failed: {SOLCAST_ERR}")
            elif mode != "hourly":
                st.info("Solcast currently supports hourly mode only.")
            elif not solcast_api_key.strip():
                st.error("Missing Solcast API key. Set SOLCAST_API_KEY env variable.")
            else:
                # Ak žiadna vybraná premenná nemá Solcast ekvivalent, použi default set
                effective_solcast_vars = solcast_variables if solcast_variables else ["ghi", "dni", "dhi", "air_temp"]
                with st.spinner("Loading Solcast..."):
                    try:
                        city_name_sol, lat_sol, lon_sol, df_sol = load_solcast(
                            city,
                            str(date_from),
                            str(date_to),
                            tuple(effective_solcast_vars),
                            DEFAULT_SOLCAST_DATASET_TYPE,
                            solcast_api_key.strip(),
                            mode,
                        )
                    except Exception:
                        _show_provider_fetch_notice()
                        city_name_sol = city
                        lat_sol = None
                        lon_sol = None
                        df_sol = pd.DataFrame()

                if lat_sol is not None:
                    st.caption(f"{city_name_sol} (lat={lat_sol:.4f}, lon={lon_sol:.4f})")
                else:
                    st.caption(city_name_sol)

                tab_data_sol, tab_chart_sol = st.tabs(["Data", "Chart"])
                with tab_data_sol:
                    if om_source_internal == "both":
                        merged_sol, labels_sol = _build_provider_comparison_df(
                            df_sol, om_reality_baseline, selected_vars, VARIABLE_MAP, 4, mode
                        )
                        if not merged_sol.empty:
                            _show_df("Prediction + Reality", merged_sol, "solcast_cmp", city, date_from, date_to)
                        else:
                            st.info("No comparable prediction/reality data.")
                    elif not df_sol.empty:
                        df_sol_table = df_sol.drop(columns=["period"], errors="ignore")
                        _show_df("Prediction", df_sol_table, "solcast_pred", city, date_from, date_to)
                    else:
                        st.info("No data.")
                with tab_chart_sol:
                    if om_source_internal == "both":
                        merged_sol, labels_sol = _build_provider_comparison_df(
                            df_sol, om_reality_baseline, selected_vars, VARIABLE_MAP, 4, mode
                        )
                        _show_provider_comparison_chart(merged_sol, labels_sol, "solcast")
                    elif not df_sol.empty:
                        _show_chart(df_sol, "solcast")
                    else:
                        st.info("No data to chart.")
        except Exception as exc:
            st.error(f"Solcast section failed: {exc}")

