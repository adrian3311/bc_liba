# SHMU ALADIN GRIB Downloader – Návod

## Čo to je

Tento skript sťahuje **meteorologické GRIB predikcie** z SHMU ALADIN modelu pre zvolený dátum a časy (runy).

GRIB súbory obsahujú predikované údaje:
- **Teplota vzduchu** (°C)
- **Oblačnosť** (%)
- **Vietor** (m/s)
- **Relatívna vlhkosť** (%)
- **Tlak** (Pa)
- **Konvektívna energia** (J/kg)
- a ďalšie meteorologické parametre

## Kde sú súbory

- **Skript:** `SHMU/fetch_prediction.py`
- **Stiahnuté dáta:** `SHMU/downloads/<YYYYMMDD>/<run>/` (napr. `SHMU/downloads/20260306/0000/`)

## Ako to spustiť

### 1. Inštalácia závislostí

Spusť raz na začiatku:

```powershell
python -m pip install -r .\SHMU\requirements.txt
```

### 2. Základný príkaz

Spustiť zo **koreňa projektu** (`bc_liba`):

```powershell
python .\SHMU\fetch_prediction.py --date 6.3.2026 --workers 8 --skip-existing --insecure
```

**Parametre:**
- `--date 6.3.2026` – Dátum vo formáte `D.M.YYYY` alebo `YYYYMMDD` (napr. `20260306`)
- `--workers 8` – Počet paralelných sťahovaní (default: 8)
- `--skip-existing` – Preskočiť už stiahnute súbory
- `--insecure` – Vypnúť SSL verifikáciu (SHMU má problém s certifikátom)

### 3. Len kontrola bez sťahovania (DRY-RUN)

```powershell
python .\SHMU\fetch_prediction.py --date 6.3.2026 --dry-run --insecure
```

Vypíše koľko súborov sa stiahne, ale nič nestiahne.

### 4. Len konkrétne runy

```powershell
python .\SHMU\fetch_prediction.py --date 6.3.2026 --runs 0000,0600 --skip-existing --insecure
```

Stiahne len runy `0000` a `0600` (nie `1200` a `1800`).

## Čo sa stiahne

Pre dátum `6.3.2026` (spolu **322 súborov**):
- **0000** → 103 súborov (predikcia od 00:00 UTC)
- **0600** → 73 súborov (predikcia od 06:00 UTC)
- **1200** → 73 súborov (predikcia od 12:00 UTC)
- **1800** → 73 súborov (predikcia od 18:00 UTC)

Celkový obsah:
```
SHMU/downloads/20260306/
├── 0000/
│   ├── al-grib_sk_000-20260306-0000-nwp-.grb
│   ├── al-grib_sk_001-20260306-0000-nwp-.grb
│   └── ... (103 súborov)
├── 0600/
│   ├── al-grib_sk_000-20260306-0600-nwp-.grb
│   └── ... (73 súborov)
├── 1200/
│   └── ... (73 súborov)
└── 1800/
    └── ... (73 súborov)
```

## Kontrola počtov po sťahovaní

```powershell
(Get-ChildItem .\SHMU\downloads\20260306\0000\*.grb).Count
(Get-ChildItem .\SHMU\downloads\20260306\0600\*.grb).Count
(Get-ChildItem .\SHMU\downloads\20260306\1200\*.grb).Count
(Get-ChildItem .\SHMU\downloads\20260306\1800\*.grb).Count
```

Alebo všetko spolu:
```powershell
(Get-ChildItem .\SHMU\downloads\20260306\*\*.grb).Count
```

## Príklady

### Príklad 1: Stiahnutie všetkých dát pre dnes (6.3.2026)

```powershell
python .\SHMU\fetch_prediction.py --date 6.3.2026 --workers 8 --skip-existing --insecure
```

Výstup:
```
Datum (vstup): 6.3.2026
Datum (normalizovany): 20260306
Runy: 0000, 0600, 1200, 1800
Output: SHMU\downloads\20260306
Mode: DOWNLOAD

[0000] najdenych .grb: 103 -> OK
[0600] najdenych .grb: 73 -> OK
[1200] najdenych .grb: 73 -> OK
[1800] najdenych .grb: 73 -> OK

Na stiahnutie spolu: 322 suborov

=== SUMAR ===
Uspech: 322
Chyby:  0
Output: SHMU\downloads\20260306
```

### Príklad 2: Len kontrola (DRY-RUN)

```powershell
python .\SHMU\fetch_prediction.py --date 6.3.2026 --dry-run --insecure
```

Vypíše zoznam súborov bez sťahovania.

### Príklad 3: Len run 0000

```powershell
python .\SHMU\fetch_prediction.py --date 6.3.2026 --runs 0000 --insecure
```

## Chyby a riešenia

### CHYBA: Trasa pre datum neexistuje

```
CHYBA: Trasa pre datum neexistuje: https://opendata.shmu.sk/meteorology/weather/nwp/aladin/sk/4.5km/20250203/
```

**Riešenie:** Dátum nemá dostupné údaje na SHMU. Vyskúšaj iný dátum (lepšie budúcnosť alebo nedávnu minulosť).

### InsecureRequestWarning

```
InsecureRequestWarning: Unverified HTTPS request is being made to host 'opendata.shmu.sk'
```

**Riešenie:** To je normálne, keď používaš `--insecure`. SHMU má problém s SSL certifikátom. Aby chyba zmizla, mahals odstrániť `--insecure`, ale potom sťahovanie skončí s SSL chybou.

### Sieťová chyba / Timeout

```
[1200] CHYBA pri listovani: HTTPError 504
```

**Riešenie:** Skús neskôr alebo zväčši `--timeout`:
```powershell
python .\SHMU\fetch_prediction.py --date 6.3.2026 --timeout 120 --insecure
```

## Technické detaily

- **GRIB Engine:** cfgrib (cez xarray)
- **Paralelizácia:** ThreadPoolExecutor (default: 8 vlákien)
- **Formát dátumu:** Akceptuje `D.M.YYYY` (11.2.2026) alebo `YYYYMMDD` (20260211)
- **Verifikácia dátumu:** Skript overí, či dátumová trasa existuje ešte pred začatím sťahovania
- **Caching:** Súbory sa ukladajú do `SHMU/downloads/<YYYYMMDD>/<run>/`

## FAQ

**Q: Ako dlho trvá sťahovanie?**  
A: Cca 2-5 minút v závislosti od internet rýchlosti a zaťaženia SHMU.

**Q: Môžem spustiť skript opakovane?**  
A: Áno, použi `--skip-existing` a skript preskočí už stiahnute súbory.

**Q: Ktoré dátumy majú dostupné údaje?**  
A: Ideálne dátumy v budúcnosti a nedávny minulej. Pre staré dátumy by si mal skúsiť SHMU archív.

**Q: Prečo `--insecure`?**  
A: SHMU opendata.shmu.sk má problém s SSL certifikátom. Bez `--insecure` skončí s `SSLError`.

---

Hotovo! Skript je pripravený na sťahovanie. Skús:

```powershell
python .\SHMU\fetch_prediction.py --date 6.3.2026 --dry-run --insecure
```

