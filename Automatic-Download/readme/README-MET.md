# Automatic MET Download

This folder contains a bulk importer for MET forecasts into MariaDB.

## Files

- `met.py` - fetches MET forecast for many cities and upserts into `met_data`
- `requirements.txt` - dependencies for this importer

## Install

```bash
pip install -r Automatic-Download/requirements.txt
```

## Quick Run (10 days ahead)

```bash
python Automatic-Download/met.py --city Zilina --city Bratislava
```

## Many Cities From File

Create `cities.txt` (one city per line):

```text
Zilina
Bratislava
Kosice
Banska Bystrica
```

Run:

```bash
python Automatic-Download/met.py --cities-file cities.txt --continue-on-error
```

## Useful Options
- --city-set shmu_mapping --max-cities 20 --days-ahead 10 --mode hourly --continue-on-error --db-host 127.0.0.1 --db-port 3306 --db-user root --db-password "al561860" --db-name weather_viewer
- cd C:\Users\adoli\Documents\bc_liba
python Automatic-Download/met.py --mode daily --continue-on-error
- `--days-ahead 10` - default forecast horizon
- `--mode hourly|daily` - write hourly or daily aggregates
- `--dry-run` - fetch/process only, no DB writes
- `--batch-size 500` - DB write chunk size
- `--start-date YYYY-MM-DD --end-date YYYY-MM-DD` - explicit range

## Duplicate Safety

The script uses `INSERT ... ON DUPLICATE KEY UPDATE` against table `met_data`.
With your schema unique key (`city`, `forecast_for`, `granularity`, `data_kind`), reruns update existing rows instead of creating duplicates.

## Verify Inserted Data

```sql
SELECT city, granularity, MIN(forecast_for), MAX(forecast_for), COUNT(*)
FROM met_data
GROUP BY city, granularity
ORDER BY city;
```

```sql
SELECT city, forecast_for, granularity, data_kind, COUNT(*) c
FROM met_data
GROUP BY city, forecast_for, granularity, data_kind
HAVING c > 1;
```

The second query should return zero rows.

