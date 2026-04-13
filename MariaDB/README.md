# MariaDB setup

This folder prepares **one MariaDB database** with **6 tables** for weather providers:

- `openmeteo_data`
- `visualcrossing_data`
- `met_data`
- `meteosource_data`
- `shmu_data`
- `solcast_data`

## What is created

The script creates one database and six provider tables with the same practical schema:

- city / resolved city
- hourly or daily granularity
- prediction or reality kind
- forecast timestamp (`forecast_for`)
- latitude / longitude
- common weather columns used by the app
- `raw_payload` for saving the original API row if needed
- indexes + unique key to avoid duplicate imports

## Files

- `schema.sql` - SQL schema for database and tables
- `init_db.py` - Python script that executes the SQL schema
- `requirements.txt` - Python dependency for MariaDB connection

## Install dependency

Run in PowerShell:

```powershell
python -m pip install -r "C:\Users\adoli\Documents\bc_liba\MariaDB\requirements.txt"
```

## Quick start

If your MariaDB runs locally and user `root` can connect:

```powershell
python "C:\Users\adoli\Documents\bc_liba\MariaDB\init_db.py" --host 127.0.0.1 --port 3306 --user root --password "" --database weather_viewer
```

## Using environment variables

The script also supports these environment variables:

- `MARIADB_HOST`
- `MARIADB_PORT`
- `MARIADB_USER`
- `MARIADB_PASSWORD`
- `MARIADB_DATABASE`

Example in PowerShell:

```powershell
$env:MARIADB_HOST = "127.0.0.1"
$env:MARIADB_PORT = "3306"
$env:MARIADB_USER = "root"
$env:MARIADB_PASSWORD = ""
$env:MARIADB_DATABASE = "weather_viewer"
python "C:\Users\adoli\Documents\bc_liba\MariaDB\init_db.py"
```

## Main columns in each table

Each provider table contains a shared set of columns so later imports and comparisons are easier:

- `city`
- `resolved_city`
- `station_id`
- `granularity`
- `data_kind`
- `forecast_for`
- `latitude`
- `longitude`
- `timezone_name`
- `unit_system`
- `temperature`
- `temperature_min`
- `temperature_max`
- `temperature_mean`
- `cloud_cover`
- `precipitation`
- `precipitation_sum`
- `precipitation_probability`
- `humidity`
- `wind_speed`
- `wind_direction`
- `wind_gusts`
- `solar_radiation`
- `uv_index`
- `visibility`
- `surface_pressure`
- `dew_point`
- `feels_like`
- `snow`
- `weather_code`
- `thunder_probability`
- `fog`
- `cape`
- `evapotranspiration`
- `vapour_pressure_deficit`
- `sunshine_duration`
- `precipitation_hours`
- `raw_payload`

## Notes

- Timestamps are intended to be stored in UTC in `forecast_for`.
- `granularity` should be `hourly` or `daily`.
- `data_kind` is mainly `prediction`; for SHMU reality you can use `reality`.
- The current setup creates the database structure only. The next step can be an importer script that writes fetched DataFrames into these tables.

