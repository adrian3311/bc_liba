# Solcast - Ziskanie Predikcnych a Historickych Dat

Skript `fetch_prediction.py` ziskava **predikcie a historicke data** zo Solcast API na zaklade:
- mesta (alebo direktne `--lat` + `--lon`)
- datumov (`--start-date` az `--end-date`)
- vybratych parametrov (`--output-parameters`)
- hodinoveho rezimu vystupu (hourly)

## Instalacia

```powershell
cd C:\Users\adoli\Documents\bc_liba
python -m pip install -r Solcast\requirements.txt
```

## Dostupne Parametre v Tvojom Subscripciu

- **Teplota**: air_temp, max_air_temp, min_air_temp, dewpoint_temp
- **Slnecne ziarenie**: ghi, dni, dhi, clearsky_ghi, clearsky_dni, clearsky_dhi, clearsky_gti, gti
- **Oblacnost**: cloud_opacity
- **Vietor**: wind_speed_10m, wind_speed_100m, wind_direction_10m, wind_direction_100m, azimuth
- **Vzduchovstvo**: relative_humidity, surface_pressure, precipitable_water
- **Zrazky**: precipitation_rate
- **Snehy**: snow_depth, snow_soiling_ground, snow_soiling_rooftop, snow_water_equivalent
- **Ziarenie**: albedo, zenith
- **Znecistenost**: pm10, pm2.5
- **Pocasie**: weather_type

## Spustenie

### Predikcia budúcnosti (dnes az +14 dni)

```powershell
python Solcast\fetch_prediction.py --city Zilina --start-date 2026-04-03 --end-date 2026-04-10 --output-parameters air_temp,ghi,cloud_opacity --api-key=-XOgWsapTi3B3BVhkqsyhllWDM24dolU
```

### Hodinovy rezim

```powershell
python Solcast\fetch_prediction.py --city Zilina --start-date 2026-04-03 --end-date 2026-04-05 --output-parameters air_temp,ghi,dni --api-key=-XOgWsapTi3B3BVhkqsyhllWDM24dolU
```

### Predikcia minulosti (ak je dostupna)

```powershell
python Solcast\fetch_prediction.py --city Zilina --start-date 2026-03-25 --end-date 2026-03-27 --output-parameters air_temp,ghi --api-key=-XOgWsapTi3B3BVhkqsyhllWDM24dolU
```

### Dry-run (bez API volania)

```powershell
python Solcast\fetch_prediction.py --city Zilina --start-date 2026-04-03 --end-date 2026-04-05 --dry-run
```

### Ulozit do CSV

```powershell
python Solcast\fetch_prediction.py --city Zilina --start-date 2026-04-03 --end-date 2026-04-05 --output-csv results.csv --api-key=-XOgWsapTi3B3BVhkqsyhllWDM24dolU
```


