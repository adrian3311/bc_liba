# Visual Crossing - fetch prediction

Skript `fetch_prediction.py` stahuje predikcne data z Visual Crossing Timeline API.

CLI je navrhnute co najpodobnejsie ako `Open-Meteo/fetch_prediction.py`:

- `--city`, `--start-date`, `--end-date`
- `--mode hourly|daily`
- `--hourly`, `--daily`
- `--timezone`
- plus Visual-Crossing specificke `--unit-group`, `--api-key`

## Spustenie

```bash
cd C:\Users\adoli\Documents\bc_liba\Visual-Crossing
python fetch_prediction.py --city Zilina --start-date 2026-03-30 --end-date 2026-03-31 --mode hourly --api-key YOUR_API_KEY
```

## API kluc

Moznosti:

1. priamo argument:

```bash
python fetch_prediction.py --city Zilina --start-date 2026-03-30 --end-date 2026-03-31 --api-key YOUR_API_KEY
```

2. cez env premennu `VISUAL_CROSSING_API_KEY`:

```bash
set VISUAL_CROSSING_API_KEY=YOUR_API_KEY
python fetch_prediction.py --city Zilina --start-date 2026-03-30 --end-date 2026-03-31
```

## Volitelne argumenty

- `--lat`, `--lon` - ak chces miesto mesta zadat suradnice
- `--hourly` - zoznam hodinovych premennych (CSV)
- `--daily` - zoznam dennych premennych (CSV)
- `--output-csv` - ulozenie vysledkov do CSV
- `--dry-run` - iba vypise finalny request URL

## Priklady

### Hourly (predvolene)

```bash
python fetch_prediction.py --city Zilina --start-date 2026-03-30 --end-date 2026-03-31 --mode hourly --api-key YOUR_API_KEY
```

### Daily

```bash
python fetch_prediction.py --city Zilina --start-date 2026-03-30 --end-date 2026-04-03 --mode daily --daily tempmax,tempmin,temp,precip --api-key YOUR_API_KEY
```

### CSV export

```bash
python fetch_prediction.py --city Zilina --start-date 2026-03-30 --end-date 2026-04-01 --api-key YOUR_API_KEY --output-csv downloads\visualcrossing_zilina.csv
```

### Dry run

```bash
python fetch_prediction.py --city Zilina --start-date 2026-03-30 --end-date 2026-03-30 --dry-run
```
