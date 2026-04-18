# Automatic MeteoSource Download

Skript na hromadné stiahnutie predikcie z MeteoSource API pre viacero miest a uloženie do MariaDB (`meteosource_data`).

> ⚠️ **Obmedzenia bezplatného plánu MeteoSource:**
> - `--mode daily` → maximálne **7 dní** dopredu (dnes + 6)
> - `--mode hourly` → **dnešný deň + zajtrajšok** (hodina po hodine, max ~48 záznamov)
>
> Dátumový rozsah sa vypočíta **automaticky** — nie je potrebné zadávať `--start-date` / `--end-date`.

## Súbory

- `meteosource.py` — stiahne predikciu MeteoSource pre viacero miest, uloží do `meteosource_data`
- `requirements.txt` — závislosti

## Inštalácia

```powershell
pip install -r Automatic-Download/requirements.txt
```

Spúšťaj z koreňa projektu (`bc_liba/`).

---

## Rýchle spustenie

### Denné dáta — jedno mesto (7 dní dopredu)

```powershell
python Automatic-Download/meteosource.py --mode daily --city Zilina --api-key kvoz0j3rt9h66wt9u8pmbtvgxwipbxbvrm7hcy2t
```

### Hodinové dáta — jedno mesto (dnes + zajtra)

```powershell
python Automatic-Download/meteosource.py --mode hourly --city Zilina --api-key kvoz0j3rt9h66wt9u8pmbtvgxwipbxbvrm7hcy2t
```

### Viacero miest naraz

```powershell
python Automatic-Download/meteosource.py --mode daily --city Zilina --city Bratislava --city Kosice --api-key kvoz0j3rt9h66wt9u8pmbtvgxwipbxbvrm7hcy2t
```

### Mestá zo súboru

Vytvor `cities.txt` (jedno mesto na riadok):

```text
Zilina
Bratislava
Kosice
Banska Bystrica
```

Spusti:

```powershell
python Automatic-Download/meteosource.py --mode daily --cities-file cities.txt --api-key kvoz0j3rt9h66wt9u8pmbtvgxwipbxbvrm7hcy2t --continue-on-error
```

### Všetky mestá zo SHMU mapovania

```powershell
python Automatic-Download/meteosource.py --mode daily --city-set shmu_mapping --api-key kvoz0j3rt9h66wt9u8pmbtvgxwipbxbvrm7hcy2t --continue-on-error
```

---

## Všetky argumenty

| Argument | Popis | Predvolené |
|---|---|---|
| `--city` | Názov mesta (opakovateľný) | — |
| `--cities-file` | Textový súbor, jedno mesto/riadok | — |
| `--city-set` | `shmu_mapping` alebo `none` | `shmu_mapping` |
| `--max-cities` | Max počet miest (0 = všetky) | `0` |
| `--mode` | `daily` (7 dní) alebo `hourly` (dnes + zajtra) | `daily` |
| `--api-key` | API kľúč alebo env `METEOSOURCE_API_KEY` | — |
| `--hourly-variables` | Čiarkou oddelené hodinové premenné | predvolená sada |
| `--daily-variables` | Čiarkou oddelené denné premenné | predvolená sada |
| `--batch-size` | Veľkosť dávky pri zápise do DB | `500` |
| `--dry-run` | Len stiahni/spracuj, nezapisuj do DB | — |
| `--continue-on-error` | Pokračuj aj keď jedno mesto zlyhá | — |
| `--db-host` | Hostiteľ MariaDB | `127.0.0.1` |
| `--db-port` | Port MariaDB | `3306` |
| `--db-user` | Používateľ DB | `root` |
| `--db-password` | Heslo DB | `al561860` |
| `--db-name` | Názov databázy | `weather_viewer` |

---

## Nastavenie API kľúča cez env premennú (raz a hotovo)

```powershell
$env:METEOSOURCE_API_KEY="kvoz0j3rt9h66wt9u8pmbtvgxwipbxbvrm7hcy2t"
```

Potom stačí:

```powershell
python Automatic-Download/meteosource.py --mode daily --city Zilina
```
python Automatic-Download/meteosource.py --mode hourly --api-key kvoz0j3rt9h66wt9u8pmbtvgxwipbxbvrm7hcy2t --continue-on-error

---

## Predvolené premenné

### Daily (`--mode daily`)

```
temperature, temperature_min, temperature_max, precipitation_sum,
wind_speed, cloud_cover, pressure, humidity, uv_index, visibility, weather
```

### Hourly (`--mode hourly`)

```
temperature, wind_speed, wind_direction, cloud_cover, precipitation_sum,
pressure, humidity, dew_point, uv_index, visibility, feels_like, weather
```

Vlastné premenné:

```powershell
python Automatic-Download/meteosource.py --mode daily --city Zilina --daily-variables temperature,temperature_min,temperature_max,precipitation_sum --api-key kvoz0j3rt9h66wt9u8pmbtvgxwipbxbvrm7hcy2t
```
python Automatic-Download/meteosource.py --mode daily --api-key kvoz0j3rt9h66wt9u8pmbtvgxwipbxbvrm7hcy2t --continue-on-error
---

## Bezpečnosť duplikátov

Skript používa `INSERT ... ON DUPLICATE KEY UPDATE` voči tabuľke `meteosource_data`.
Opakovaný beh **aktualizuje** existujúce riadky namiesto vytvárania duplikátov.

---

## Overenie vložených dát

```sql
SELECT city, granularity, MIN(forecast_for), MAX(forecast_for), COUNT(*)
FROM meteosource_data
GROUP BY city, granularity
ORDER BY city;
```

Kontrola duplikátov (výsledok musí byť prázdny):

```sql
SELECT city, forecast_for, granularity, data_kind, COUNT(*) c
FROM meteosource_data
GROUP BY city, forecast_for, granularity, data_kind
HAVING c > 1;
```

