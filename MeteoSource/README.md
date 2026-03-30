# MeteoSource - Návod na obsluhu

Skript na stiahnutie meteorologických predpovedí z MeteoSource API.

## Čo potrebuješ

1. **Python 3.8+** (už máš)
2. **API kľúč** od MeteoSource: `kvoz0j3rt9h66wt9u8pmbtvgxwipbxbvrm7hcy2t`
3. **Knižnice** — inštaluj ich:

```powershell
pip install pandas requests
```

## Ako sa to spúšťa

Otvor **Terminal v PyCharme** (`Alt+F12`) a spustí príkaz:

```powershell
python MeteoSource/fetch_prediction.py --city MESTO --start-date DÁTUM_OD --end-date DÁTUM_DO --api-key kvoz0j3rt9h66wt9u8pmbtvgxwipbxbvrm7hcy2t
```

### Príklad — Denné dáta pre Žilinu

```powershell
python MeteoSource/fetch_prediction.py --city Zilina --start-date 2026-03-25 --end-date 2026-03-30 --api-key kvoz0j3rt9h66wt9u8pmbtvgxwipbxbvrm7hcy2t
```

Skript vypíše:
- Mesto a GPS súradnice
- Tabuľku s dennými údajmi
- Štatistiky (Min, Max, Priemer)

### Príklad — Hodinové dáta

```powershell
python MeteoSource/fetch_prediction.py --city Zilina --start-date 2026-03-25 --end-date 2026-03-26 --mode hourly --api-key kvoz0j3rt9h66wt9u8pmbtvgxwipbxbvrm7hcy2t
```

## Hlavné argumenty

| Argument | Čo to robí | Príklad |
|----------|-----------|---------|
| `--city` | Mesto, ktoré chceš | `--city Zilina` |
| `--start-date` | Dátum od (YYYY-MM-DD) | `--start-date 2026-03-25` |
| `--end-date` | Dátum do (YYYY-MM-DD) | `--end-date 2026-03-30` |
| `--mode` | `daily` alebo `hourly` | `--mode daily` (predvolené) |
| `--api-key` | Tvoj API kľúč | `--api-key kvoz0j3rt9h66wt9u8pmbtvgxwipbxbvrm7hcy2t` |

## Výber údajov (premenných)

### Denné dáta (`--daily`)

Ktoré údaje chceš vidieť? Môžeš vybrať:

```powershell
--daily temperature,temperature_min,temperature_max,precipitation_sum,wind_speed,cloud_cover
```

**Možnosti:**
- `temperature` — priemerná teplota v °C
- `temperature_min` — najchladnejšie v deň
- `temperature_max` — najteplejšie v deň
- `precipitation_sum` — koľko zaprší (mm)
- `wind_speed` — silnosť vetra (m/s)
- `cloud_cover` — oblačnosť v %

**Príklad — Len teploty:**
```powershell
python MeteoSource/fetch_prediction.py --city Zilina --start-date 2026-03-25 --end-date 2026-03-30 --daily temperature,temperature_min,temperature_max --api-key kvoz0j3rt9h66wt9u8pmbtvgxwipbxbvrm7hcy2t
```

### Hodinové dáta (`--hourly`)

```powershell
--hourly temperature,wind_speed,cloud_cover,precipitation_sum
```

**Príklad — Teplota a vietor každú hodinu:**
```powershell
python MeteoSource/fetch_prediction.py --city Zilina --start-date 2026-03-25 --end-date 2026-03-26 --mode hourly --hourly temperature,wind_speed --api-key kvoz0j3rt9h66wt9u8pmbtvgxwipbxbvrm7hcy2t
```

## Ďalšie možnosti

### Ulož výsledok do CSV súboru

```powershell
python MeteoSource/fetch_prediction.py --city Zilina --start-date 2026-03-25 --end-date 2026-03-30 --output-csv output.csv --api-key kvoz0j3rt9h66wt9u8pmbtvgxwipbxbvrm7hcy2t
```

Dáta sa uložia do `output.csv` — otvoríš ho cez Excel alebo Calc.

### Testuj bez API volania (dry-run)

Ak chceš skontrolovať URL bez stiahnutia dát:

```powershell
python MeteoSource/fetch_prediction.py --city Zilina --start-date 2026-03-25 --end-date 2026-03-30 --dry-run
```

## Kombinácie (Komplexnejšie príkazy)

### 1. Teplota + zrážky, export do CSV

```powershell
python MeteoSource/fetch_prediction.py --city Bratislava --start-date 2026-03-20 --end-date 2026-03-25 --daily temperature,precipitation_sum --output-csv bratislava.csv --api-key kvoz0j3rt9h66wt9u8pmbtvgxwipbxbvrm7hcy2t
```

### 2. Hodinové — vietor a oblačnosť

```powershell
python MeteoSource/fetch_prediction.py --city Zilina --start-date 2026-03-25 --end-date 2026-03-25 --mode hourly --hourly wind_speed,cloud_cover --api-key kvoz0j3rt9h66wt9u8pmbtvgxwipbxbvrm7hcy2t
```

### 3. Iné mestá

```powershell
python MeteoSource/fetch_prediction.py --city Prague --start-date 2026-03-25 --end-date 2026-03-30 --api-key kvoz0j3rt9h66wt9u8pmbtvgxwipbxbvrm7hcy2t
```

(Funguje s ľubovoľným mestom — zadaj názov v angličtine)

## Skrátenie — Vynechaj API kľúč v príkaze

Ak nechceš písať kľúč zakaždým, nastav env premennú:

```powershell
$env:METEOSOURCE_API_KEY="kvoz0j3rt9h66wt9u8pmbtvgxwipbxbvrm7hcy2t"
```

Teraz stačí:
```powershell
python MeteoSource/fetch_prediction.py --city Zilina --start-date 2026-03-25 --end-date 2026-03-30
```

(Bez `--api-key` — použije sa env premená)

## Čo dostaneš ako výsledok

Skript vypíše do konzoly:

```
============================================================
PREDIKCNE DATA (MeteoSource): Zilina
============================================================
Suradnice: lat=48.7411, lon=18.7481
Obdobie: 2026-03-25 az 2026-03-30 | Zaznamov: 6
Rezim: daily
Premenne: temperature, temperature_min, temperature_max

Vsetky zaznamy:
date         temperature  temperature_min  temperature_max
2026-03-25      12.50            9.20             15.80
2026-03-26      13.10           10.00             16.50
2026-03-27      11.80            8.90             14.70
...

============================================================
STATISTIKY
============================================================
temperature                | Min=11.80 | Max=13.50 | Priemer=12.80
temperature_min            | Min=8.90  | Max=10.00 | Priemer=9.54
temperature_max            | Min=14.70 | Max=16.50 | Priemer=15.70
```

## Správa chýb

Ak skript napíše chybu:

- **"Mesto sa nenašlo"** → Skús iný názov mesta alebo kontrola kľúča
- **"Chyba: 401 Unauthorized"** → API kľúč je nesprávny
- **"Ziadne data"** → Dátum je v budúcnosti alebo príliš ďaleko

## Zhrnutie

**Najjednoduchší príkaz:**
```powershell
python MeteoSource/fetch_prediction.py --city Zilina --start-date 2026-03-25 --end-date 2026-03-30 --api-key kvoz0j3rt9h66wt9u8pmbtvgxwipbxbvrm7hcy2t
```

**Viac možností:** kombinuj `--mode`, `--daily`/`--hourly`, `--output-csv` podľa potreby.

**Všetko jasné?** Spustí skript v PyCharm Terminale a vidíš výsledok! 👍





