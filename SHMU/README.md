# SHMU climate-now downloader

Skript `fetch_prediction.py` stahuje SHMU JSON subory z adresara:

- `https://opendata.shmu.sk/meteorology/climate/now/data/YYYYMMDD/`

Format nazvu suboru:

- `<type> - YYYY-MM-DD HH-MM-SS.json`
- priklad: `aws1min - 2026-02-27 00-05-00.json`

## Instalacia

```powershell
pip install -r SHMU/requirements.txt
```

## Zakladne pouzitie

Stiahnutie celeho dna pre `aws1min`:

```powershell
python SHMU/fetch_prediction.py --date 2026-02-27 --type aws1min
```

Stiahnutie iba casoveho intervalu:

```powershell
python SHMU/fetch_prediction.py --date 2026-02-27 --type aws1min --start-time 00:00 --end-time 01:00
```

Iba vypis URL bez stahovania:

```powershell
python SHMU/fetch_prediction.py --date 2026-02-27 --type aws1min --start-time 00:00 --end-time 00:15 --dry-run
```

## CSV export (volitelne)

Vytvor agregovany CSV zo stiahnutych JSON suborov:

```powershell
python SHMU/fetch_prediction.py --date 2026-02-27 --type aws1min --start-time 00:00 --end-time 00:30 --output-csv SHMU/output/aws1min_2026-02-27.csv
```

Vyber iba konkretne JSON polia (dot notacia):

```powershell
python SHMU/fetch_prediction.py --date 2026-02-27 --type aws1min --output-csv SHMU/output/aws1min_fields.csv --fields station.id,temperature
```

## Hodinovy vyber dat podla mesta a ind_kli

Nazov mesta je tolerantny na diakritiku, takze rovnako funguje napriklad:

- `Zilina`
- `Žilina`

Skript najde spravne `ind_kli` podla `ms.pdf`, vyberie pre kazdu hodinu jeden `aws1min` JSON a z neho vytiahne record pre dane mesto.

### Jedno pole

```powershell
python SHMU/fetch_prediction.py --date 2026-03-03 --city Zilina --field t --insecure
```

Rovnaky priklad prirodzenejsimi aliasmi:

```powershell
python SHMU/fetch_prediction.py --miesto Zilina --datum 2026-03-03 --typ-dat t --insecure
```

### Interval datumov od-do

```powershell
python SHMU/fetch_prediction.py --start-date 2026-03-03 --end-date 2026-03-05 --city Zilina --field t --insecure
```

Alebo:

```powershell
python SHMU/fetch_prediction.py --miesto Zilina --od 2026-03-03 --do 2026-03-05 --typ-dat t --insecure
```

### Viac poli naraz

```powershell
python SHMU/fetch_prediction.py --date 2026-03-03 --city Zilina --fields t,vlh_rel,zra_uhrn --insecure
```

### Cely record pod danym ind_kli

```powershell
python SHMU/fetch_prediction.py --date 2026-03-03 --city Zilina --record --insecure
```

### Zoznam dostupnych klucov v recorde

```powershell
python SHMU/fetch_prediction.py --date 2026-03-03 --city Zilina --list-fields --insecure
```

### Iba vypis, co by sa stahovalo

```powershell
python SHMU/fetch_prediction.py --date 2026-03-03 --city Zilina --field t --dry-run --insecure
```

## SSL problem vo Windows/Python

Ak ti lokalne pada certifikat pri HTTPS, mozes docasne pouzit:

```powershell
python SHMU/fetch_prediction.py --date 2026-02-27 --type aws1min --insecure
```

## Vystup

JSON subory sa ukladaju defaultne do:

- `SHMU/downloadsNow/YYYYMMDD/<type>/`
