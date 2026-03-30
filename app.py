import importlib.util
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT_DIR = Path(__file__).resolve().parent
OPEN_METEO_DIR = ROOT_DIR / "Open-Meteo"
VC_DIR = ROOT_DIR / "Visual-Crossing"
MET_DIR = ROOT_DIR / "MET"
METEOSOURCE_DIR = ROOT_DIR / "MeteoSource"
VC_API_KEY = os.getenv("VISUAL_CROSSING_API_KEY", "QBY2GE2MTCEFA8TB6586RXWZJ")
MS_API_KEY = os.getenv("METEOSOURCE_API_KEY", "kvoz0j3rt9h66wt9u8pmbtvgxwipbxbvrm7hcy2t")

if str(OPEN_METEO_DIR) not in sys.path:
    sys.path.insert(0, str(OPEN_METEO_DIR))


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Failed to load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
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

# ── helpers ────────────────────────────────────────────────────────────────

def _clean_met_city_name(name: str) -> str:
    """Shorten long MET geocoding labels for cleaner captions."""
    cleaned = name.replace(", Žilinský kraj", "").replace(", Stredné Slovensko", "")
    return cleaned.strip().strip(",")


def _csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8")


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
def load_met(city, start_date, end_date, variables, altitude):
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
        df["date"] = pd.to_datetime(df["date"])
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


# ── UI ──────────────────────────────────────────────────────────────────────

st.set_page_config(page_title="Weather Viewer", layout="wide")
st.title("Weather Viewer")
st.caption("Open-Meteo, Visual Crossing, MET, MeteoSource - provider comparison")

# ── Sidebar ────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Inputs")
    city = st.text_input("City", value="Zilina")
    date_from = st.date_input("Start date")
    date_to = st.date_input("End date")
    mode = st.selectbox("Mode", ["hourly", "daily"])
    om_source = st.selectbox("Open-Meteo source", ["prediction", "reality", "both"])

    # Shared variables — mapping OM name -> VC -> MET -> MeteoSource
    if mode == "hourly":
        VARIABLE_MAP = {
            "Temperature":      ("temperature_2m", "temp", "temperature_2m", "temperature"),
            "Cloud cover":      ("cloud_cover", "cloudcover", "cloud_cover", "cloud_cover"),
            "Precipitation":    ("rain", "precip", "precipitation_1h", "precipitation_sum"),
            "Humidity":         ("relative_humidity_2m", "humidity", "humidity", None),
            "Wind speed":       ("wind_speed_10m", "windspeed", "wind_speed", "wind_speed"),
            "Solar radiation":  ("shortwave_radiation", "solarradiation", None, None),
            "Snow":             ("snowfall", "snow", None, None),
        }
        default_vars = ["Temperature", "Cloud cover", "Precipitation", "Wind speed"]
    else:
        VARIABLE_MAP = {
            "Max temperature":  ("temperature_2m_max", "tempmax", None, "temperature_max"),
            "Min temperature":  ("temperature_2m_min", "tempmin", None, "temperature_min"),
            "Mean temperature": ("temperature_2m_mean", "temp", None, "temperature"),
            "Precipitation":    ("precipitation_sum", "precip", None, "precipitation_sum"),
            "Humidity":         ("relative_humidity_2m_mean", "humidity", None, None),
            "Wind speed":       ("wind_speed_10m_max", "windspeed", None, "wind_speed"),
            "Sunshine":         ("sunshine_duration", "solarradiation", None, None),
        }
        default_vars = ["Max temperature", "Min temperature", "Precipitation"]

    selected_vars = st.multiselect("Variables", options=list(VARIABLE_MAP.keys()), default=default_vars)

    # Z vybranych nazvov odvodime OM, VC, MET a MeteoSource zoznamy
    om_variables = [VARIABLE_MAP[v][0] for v in selected_vars if VARIABLE_MAP[v][0] is not None]
    vc_variables = [VARIABLE_MAP[v][1] for v in selected_vars if VARIABLE_MAP[v][1] is not None]
    met_variables = [VARIABLE_MAP[v][2] for v in selected_vars if VARIABLE_MAP[v][2] is not None]
    ms_variables = [VARIABLE_MAP[v][3] for v in selected_vars if VARIABLE_MAP[v][3] is not None]

    st.divider()
    st.subheader("Open-Meteo")
    om_timezone = st.text_input("Timezone (OM)", value="auto")

    st.subheader("Visual Crossing")
    vc_unit_group = st.selectbox("Units (VC)", ["metric", "us", "uk", "base"])
    vc_timezone = st.text_input("Timezone (VC)", value="Europe/Bratislava")

    st.subheader("MET")
    met_altitude_raw = st.text_input("Altitude (MET, optional)", value="")

    st.subheader("MeteoSource")
    use_meteosource = st.checkbox("Enable MeteoSource", value=True)

    run_btn = st.button("Load data", type="primary")

# ── Hlavná plocha ──────────��───────────────────────────────────────────────
if not run_btn:
    st.info("Click **Load data** in the sidebar.")
    st.stop()

if date_from > date_to:
    st.error("Start date must be before or equal to end date.")
    st.stop()

col_om, col_vc = st.columns(2)
row2_col_met, row2_col_ms = st.columns(2)

# ── Open-Meteo stĺpec ──────────────────────────────────────────────────────
with col_om:
    st.header("🌍 Open-Meteo")
    try:
        if not OM_OK:
            st.error(f"Module load failed: {OM_ERR}")
        elif not om_variables:
            st.warning("Select at least one variable.")
        else:
            with st.spinner("Loading Open-Meteo..."):
                try:
                    city_name_om, lat, lon, frames, merged = load_openmeteo(
                        city, str(date_from), str(date_to), mode,
                        tuple(om_variables), om_timezone, om_source,
                    )
                except Exception as exc:
                    st.error(f"Error: {exc}")
                    frames, merged, lat, lon = {}, None, None, None
                    city_name_om = city

            if lat is not None:
                st.caption(f"{city_name_om} (lat={lat:.4f}, lon={lon:.4f})")
            else:
                st.caption(city_name_om)

            tab_labels_om = []
            if "prediction" in frames:
                tab_labels_om.append("Prediction")
            if "reality" in frames:
                tab_labels_om.append("Reality")
            if merged is not None:
                tab_labels_om.append("Comparison")
            if frames:
                tab_labels_om.append("Chart")

            if tab_labels_om:
                tabs_om = st.tabs(tab_labels_om)
                ti = 0
                if "prediction" in frames:
                    with tabs_om[ti]:
                        _show_df("Prediction", frames["prediction"], "om_pred", city, date_from, date_to)
                    ti += 1
                if "reality" in frames:
                    with tabs_om[ti]:
                        _show_df("Reality", frames["reality"], "om_real", city, date_from, date_to)
                    ti += 1
                if merged is not None:
                    with tabs_om[ti]:
                        st.write(f"Common timestamps: {len(merged)}")
                        st.dataframe(merged, use_container_width=True)
                        st.download_button(
                            "Download CSV",
                            data=_csv_bytes(merged),
                            file_name=f"om_cmp_{city}_{date_from}_{date_to}.csv",
                            mime="text/csv",
                            key="dl_om_cmp",
                        )
                        _show_comparison(merged, list(om_variables), "om")
                    ti += 1
                if frames:
                    with tabs_om[ti]:
                        if om_source == "both" and merged is not None:
                            _show_chart(merged, "om")
                        elif "prediction" in frames:
                            _show_chart(frames["prediction"], "om_pred_chart")
                        elif "reality" in frames:
                            _show_chart(frames["reality"], "om_real_chart")
                        else:
                            st.info("No data to chart.")
    except Exception as exc:
        st.error(f"Open-Meteo section failed: {exc}")

# ── Visual Crossing stĺpec ─────────────────────────────────────────────────
with col_vc:
    st.header("🌤 Visual Crossing")
    try:
        if not VC_OK:
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
                except Exception as exc:
                    st.error(f"Error: {exc}")
                    df_vc = pd.DataFrame()
                    city_name_vc = city

            st.caption(city_name_vc)

            tab_data_vc, tab_graf_vc = st.tabs(["Data", "Chart"])
            with tab_data_vc:
                if not df_vc.empty:
                    _show_df("Prediction", df_vc, "vc_pred", city, date_from, date_to)
                else:
                    st.info("No data.")
            with tab_graf_vc:
                if not df_vc.empty:
                    _show_chart(df_vc, "vc")
                else:
                    st.info("No data to chart.")
    except Exception as exc:
        st.error(f"Visual Crossing section failed: {exc}")

# ── MET stĺpec ─────────────────────────────────────────────────────────────
with row2_col_met:
    st.header("🛰 MET")
    try:
        if not MET_OK:
            st.error(f"Module load failed: {MET_ERR}")
        elif mode == "daily":
            st.warning("MET in this app currently supports hourly mode only.")
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
                        city, str(date_from), str(date_to), tuple(met_variables), altitude
                    )
                except Exception as exc:
                    st.error(f"Error: {exc}")
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
                if not df_met.empty:
                    _show_df("Prediction", df_met, "met_pred", city, date_from, date_to)
                else:
                    st.info("No data.")
            with tab_graf_met:
                if not df_met.empty:
                    _show_chart(df_met, "met")
                else:
                    st.info("No data to chart.")
    except Exception as exc:
        st.error(f"MET section failed: {exc}")

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
                except Exception as exc:
                    st.error(f"Error: {exc}")
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
                if not df_ms.empty:
                    _show_df("Prediction", df_ms, "ms_pred", city, date_from, date_to)
                else:
                    st.info("No data.")
            with tab_graf_ms:
                if not df_ms.empty:
                    _show_chart(df_ms, "ms")
                else:
                    st.info("No data to chart.")
    except Exception as exc:
        st.error(f"MeteoSource section failed: {exc}")
