# SHMU Downloader

Tento adresar obsahuje skript `download_kli_inter_json.py` na stahovanie JSON suborov zo SHMU OpenData.

## Co skript vie

- `recent` - stiahne mesacny subor `kli-inter - YYYY-MM.json`
- `now` - stiahne minutovy subor `aws1min - YYYY-MM-DD HH-MM-SS.json`
- `now --all-times` - stiahne vsetky 5-min sloty za den (alebo v intervale)
- `now --from-datetime --to-datetime` - stiahne vsetky sloty v intervale od-do (aj cez viac dni)

## Predpoklady

- Python 3.10+
- kniznica `requests`

Instalacia (ak treba):

```powershell
python -m pip install requests
```

## Spustenie

Spustaj z korena projektu (`bc_liba`):

```powershell
python .\SHMU\download_kli_inter_json.py --help
python .\SHMU\download_kli_inter_json.py recent --help
python .\SHMU\download_kli_inter_json.py now --help
```

## Priklady pouzitia

### 1) Monthly recent (`kli-inter`)

```powershell
python .\SHMU\download_kli_inter_json.py recent --month 2025-01 --out-dir .\SHMU\downloads
```

Poznamka: podla aktualneho nastavenia skriptu je limit pre `recent` do `2025-10`.

### 2) Jeden `aws1min` subor pre konkretny cas

```powershell
python .\SHMU\download_kli_inter_json.py now --date 20260203 --time 00-30-00 --out-dir .\SHMU\downloads
```

### 3) Cely den po 5 minutach

```powershell
python .\SHMU\download_kli_inter_json.py now --date 20260203 --all-times --skip-existing --out-dir .\SHMU\downloads
```

### 4) Cely den, ale len casovy usek

```powershell
python .\SHMU\download_kli_inter_json.py now --date 20260203 --all-times --from-time 06-00-00 --to-time 09-00-00 --skip-existing --out-dir .\SHMU\downloads
```

### 5) Interval od-do (aj cez viac dni)

```powershell
python .\SHMU\download_kli_inter_json.py now --from-datetime 20260203-00-00-00 --to-datetime 20260204-03-30-00 --skip-existing --out-dir .\SHMU\downloads
```

## Overenie stiahnutia

```powershell
Get-ChildItem .\SHMU\downloads
Get-ChildItem .\SHMU\downloads\aws1min-20260203-*.json
```

## Formaty vstupu

- `--month`: `YYYY-MM` (napr. `2025-01`)
- `--date`: `YYYYMMDD` (napr. `20260203`)
- `--time`: `HH-MM-SS` (napr. `00-30-00`)
- `--from-datetime`/`--to-datetime`: `YYYYMMDD-HH-MM-SS`

## Caste chyby

- `Neplatny format ...` -> oprav format argumentu podla sekcie vyssie.
- `--from-datetime musi byt mensi...` -> prehod poradie od-do.
- 404/RequestException -> dany subor/cas na SHMU nemusi existovat.
- SSL warning je v skripte potlaceny, ale sietove chyby sa stale mozu vyskytnut.

## GRIB Predikcie (ALADIN)

Pre stiahnutie vsetkych `.grb` suborov pouzi `fetch_prediction.py`.

Instalacia zavislosti:

```powershell
python -m pip install -r .\SHMU\requirements.txt
```

### Dry-run (len kontrola poctov)

```powershell
python .\SHMU\fetch_prediction.py --date 11.2.2026 --dry-run --insecure
```

### Stiahnutie vsetkych runov pre den (0000/0600/1200/1800)

```powershell
python .\SHMU\fetch_prediction.py --date 11.2.2026 --workers 8 --skip-existing --insecure
```

Skript ocakava pocty:
- `0000` -> 103 suborov
- `0600` -> 73 suborov
- `1200` -> 73 suborov
- `1800` -> 73 suborov

Output bude v:
- `.\SHMU\downloads\20260211\0000\...`
- `.\SHMU\downloads\20260211\0600\...`
- `.\SHMU\downloads\20260211\1200\...`
- `.\SHMU\downloads\20260211\1800\...`

### Len vybrane runy

```powershell
python .\SHMU\fetch_prediction.py --date 11.2.2026 --runs 0000,0600 --skip-existing --insecure
```

### Overenie stiahnutia

```powershell
Get-ChildItem .\SHMU\downloads\20260211\0000\*.grb | Measure-Object
Get-ChildItem .\SHMU\downloads\20260211\0600\*.grb | Measure-Object
Get-ChildItem .\SHMU\downloads\20260211\1200\*.grb | Measure-Object
Get-ChildItem .\SHMU\downloads\20260211\1800\*.grb | Measure-Object
```
