# Open-Meteo comparison script

This project compares historical forecast and archive reality values from Open-Meteo for a selected city and datetime.

## Files
- `requirements.txt` - Python dependencies

## Install

```powershell
python -m pip install -r .\requirements.txt
```

## Run
Accepted datetime formats:

- `YYYY-MM-DD HH:MM`
- `YYYY-MM-DDTHH:MM`

## Reality Script

Hourly (teplota + oblacnost):

```powershell
python .\fetchRealityOpenMeteo.py --city Zilina --start-date 2026-03-01 --end-date 2026-03-02 --mode hourly --hourly temperature_2m,cloud_cover
```

Daily (osvit):

```powershell
python .\fetchRealityOpenMeteo.py --city Zilina --start-date 2026-03-01 --end-date 2026-03-07 --mode daily --daily sunshine_duration
```
