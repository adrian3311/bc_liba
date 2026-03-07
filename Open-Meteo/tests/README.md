# Open-Meteo tests - pouzitie

Tento priecinok obsahuje skript `compare_openmeteo.py`, ktory:
- stiahne predikciu aj realitu z Open-Meteo,
- spoji data podla spolocneho casu (`date`),
- vypise porovnane zaznamy do konzoly,
- vypocita metriky: `MAE`, `RMSE`, `BIAS`.

## 1) Instalacia zavislosti

```powershell
cd C:\Users\adoli\Documents\bc_liba\Open-Meteo
python -m pip install -r .\requirements.txt
```

## 2) Spustenie porovnania (hourly)

```powershell
cd C:\Users\adoli\Documents\bc_liba\Open-Meteo
python .\tests\compare_openmeteo.py --city Zilina --start-date 2026-03-01 --end-date 2026-03-02 --mode hourly --variables temperature_2m,cloud_cover
```

## 3) Spustenie porovnania (daily)

```powershell
cd C:\Users\adoli\Documents\bc_liba\Open-Meteo
python .\tests\compare_openmeteo.py --city Zilina --start-date 2026-03-01 --end-date 2026-03-07 --mode daily --variables sunshine_duration
```

## Argumenty

- `--city` nazov mesta (napr. `Zilina`)
- `--start-date` datum od (`YYYY-MM-DD`)
- `--end-date` datum do (`YYYY-MM-DD`)
- `--mode` `hourly` alebo `daily`
- `--variables` premenne oddelene ciarkou
- `--timezone` volitelne, predvolene `auto`

## Poznamky

- Ak sa nenajde prienik timestampov, skript to vypise a skonci.
- Pri porovnani je dolezite zadat premenne, ktore su dostupne v predikcii aj v realite.

