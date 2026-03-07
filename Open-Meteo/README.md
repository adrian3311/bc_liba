# Open-Meteo fetch skripty

Tento priecinok obsahuje 2 hlavne skripty:
- `fetch_prediction.py` - stiahne predikcne data (historical forecast API)
- `fetch_reality.py` - stiahne realne historicke data (archive API)

## Instalacia

```powershell
cd C:\Users\adoli\Documents\bc_liba\Open-Meteo
python -m pip install -r .\requirements.txt
```

## 1) Predikcia - `fetch_prediction.py`

### Hourly priklad (teplota + oblacnost)

```powershell
cd C:\Users\adoli\Documents\bc_liba\Open-Meteo
python .\fetch_prediction.py --city Zilina --start-date 2026-03-01 --end-date 2026-03-02 --mode hourly --hourly temperature_2m,cloud_cover
```

### Daily priklad (osvit)

```powershell
cd C:\Users\adoli\Documents\bc_liba\Open-Meteo
python .\fetch_prediction.py --city Zilina --start-date 2026-03-01 --end-date 2026-03-07 --mode daily --daily sunshine_duration
```

## 2) Realita - `fetch_reality.py`

### Hourly priklad (teplota + oblacnost + dazd + snezenie)

```powershell
cd C:\Users\adoli\Documents\bc_liba\Open-Meteo
python .\fetch_reality.py --city Zilina --start-date 2026-03-01 --end-date 2026-03-02 --mode hourly --hourly temperature_2m,cloud_cover,rain,snowfall
```

### Daily priklad (osvit + hodiny zrazok)

```powershell
cd C:\Users\adoli\Documents\bc_liba\Open-Meteo
python .\fetch_reality.py --city Zilina --start-date 2026-03-01 --end-date 2026-03-07 --mode daily --daily sunshine_duration,precipitation_hours
```

## Najdolezitejsie argumenty

- `--city` nazov mesta (napr. `Zilina`)
- `--start-date` datum od (`YYYY-MM-DD`)
- `--end-date` datum do (`YYYY-MM-DD`)
- `--mode` `hourly` alebo `daily`
- `--hourly` zoznam hourly premennych (len pri `--mode hourly`)
- `--daily` zoznam daily premennych (len pri `--mode daily`)
- `--timezone` casova zona (predvolene `auto`)

## Poznamka

Ak chces porovnat predikciu vs realitu, pouzi skript:

```powershell
cd C:\Users\adoli\Documents\bc_liba\Open-Meteo
python .\tests\compare_openmeteo.py --city Zilina --start-date 2026-03-01 --end-date 2026-03-02 --mode hourly --variables temperature_2m,cloud_cover
```
