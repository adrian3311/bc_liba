# Open-Meteo Streamlit App (kroky)

Tento workspace obsahuje jednoduche web UI v `app.py`, ktore cita data z providerov `Open-Meteo/`, `Visual-Crossing/`, `MET/`, `MeteoSource/` a `SHMU/`.

## Co sme museli importovat a preco

V `app.py` su importy:

- `streamlit` - web UI (formular, tlacidla, tabulky, graf)
- `pandas` - praca s DataFrame, merge a metriky
- `pathlib.Path`, `importlib.util` - dynamicke nacitanie modulov z `Open-Meteo/`
- `fetch_prediction_data` z `Open-Meteo/fetch_prediction.py` - predikcie
- `fetch_reality_data` z `Open-Meteo/fetch_reality.py` - realne (archive) data
- `create_client`, `resolve_city_to_coords`, `response_to_dataframe` z `Open-Meteo/openmeteo_utils.py`

Poznamka: priecinok sa vola `Open-Meteo` (s pomlckou), preto sa moduly nacitavaju cez `importlib` z konkretnej cesty suboru.

## Co appka aktualne robi (Krok 3)

- vstupy: mesto, datum od/do, rezim (`hourly`/`daily`), zdroj (`prediction`/`reality`/`both`), premenne
- geocoding mesta cez Open-Meteo geocoding API
- nacitanie dat z Open-Meteo API
- nacitanie dalsich providerov: Visual Crossing, MET, MeteoSource a SHMU
- vypis DataFrame pre prediction/reality
- pri `both` spravi merge na `date` a vypocita MAE/RMSE/BIAS
- grafy:
  - `prediction`/`reality`: multiselect numerickych premennych
  - `both`: overlay `prediction` vs `reality` pre vybranu premennu
- CSV export tlacidlami (`prediction`, `reality`, `comparison`)
- SHMU je aktualne v appke ako samostatny hourly provider s pozorovaniami (`aws1min`)

## Instalacia

Pouzi root `requirements.txt`:

```bash
pip install -r requirements.txt
```

## Spustenie

```bash
cd C:\Users\adoli\Documents\bc_liba
streamlit run app.py
```
python -m streamlit run app.py
## Rychly test bez UI

```bash
python -m py_compile app.py
```

## Poznamka

Ak pri `both` niektora premenna nema v oboch datasetoch hodnoty pre rovnaky cas, v porovnani sa nezobrazi (alebo bude mat mensi pocet bodov).
