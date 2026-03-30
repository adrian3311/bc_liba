# MET Norway — Locationforecast 2.0

Skript na získanie **predikčných dát** z MET Norway Locationforecast API.

- **Dokumentácia API:** https://api.met.no/doc/GettingStarted
- **Endpoint:** `https://api.met.no/weatherapi/locationforecast/2.0/complete`
- **Bez API kľúča** — stačí platný `User-Agent`
- **Pokrytie:** celý svet
- **Časový rozsah:** ~9–10 dní dopredu od aktuálneho dátumu (nie historické dáta)
- **Rozlíšenie:** hodinové záznamy (UTC)

---

## Požiadavky

```bash
pip install requests
```

---

## Spustenie

```bash
python fetch_prediction.py --city <MESTO> --start-date <OD> --end-date <DO>
```

### Argumenty

| Argument | Povinný | Popis | Príklad |
|---|---|---|---|
| `--city` | ✅ | Názov mesta | `Zilina`, `Bratislava` |
| `--start-date` | ✅ | Dátum/čas od | `2026-03-30` alebo `2026-03-30T08:00` |
| `--end-date` | ✅ | Dátum/čas do | `2026-04-02` alebo `2026-03-30T18:00` |
| `--variables` | ❌ | Premenné oddelené čiarkou | `temperature_2m,cloud_cover` |
| `--altitude` | ❌ | Nadmorská výška v metroch | `350` |
| `--dry-run` | ❌ | Zobraz URL bez stiahnutia dát | — |

> Formát dátumu: `YYYY-MM-DD` alebo `YYYY-MM-DDTHH:MM`

---

## Príklady

**Základné použitie — Žilina, 3 dni:**
```bash
python fetch_prediction.py --city Zilina --start-date 2026-03-30 --end-date 2026-04-02
```

**Konkrétny časový úsek v ten istý deň:**
```bash
python fetch_prediction.py --city Bratislava --start-date 2026-03-30T06:00 --end-date 2026-03-30T18:00
```

**Vlastné premenné:**
```bash
python fetch_prediction.py --city Kosice --start-date 2026-03-30 --end-date 2026-04-01 --variables temperature_2m,cloud_cover,symbol_1h,precipitation_1h
```

**S nadmorskou výškou:**
```bash
python fetch_prediction.py --city Zilina --start-date 2026-03-30 --end-date 2026-04-01 --altitude 350
```

**Dry-run (iba zobraz URL):**
```bash
python fetch_prediction.py --city Zilina --start-date 2026-03-30 --end-date 2026-04-01 --dry-run
```

---

## Dostupné premenné

| Premenná | Jednotka | Popis |
|---|---|---|
| `temperature_2m` | °C | Teplota vzduchu vo výške 2 m |
| `cloud_cover` | % | Pokrytie oblohy oblakmi |
| `wind_speed` | m/s | Rýchlosť vetra |
| `wind_direction` | ° | Smer vetra |
| `humidity` | % | Relatívna vlhkosť vzduchu |
| `pressure` | hPa | Atmosferický tlak na hladine mora |
| `dew_point` | °C | Teplota rosného bodu |
| `fog` | % | Plocha pokrytá hmlou |
| `precipitation_1h` | mm | Zrážky za posledných 1 hodinu |
| `precipitation_6h` | mm | Zrážky za posledných 6 hodín |
| `precipitation_12h` | mm | Zrážky za posledných 12 hodín |
| `symbol_1h` | — | Počasie (ikona) pre nasledujúcu 1 hodinu |
| `symbol_6h` | — | Počasie (ikona) pre nasledujúcich 6 hodín |
| `symbol_12h` | — | Počasie (ikona) pre nasledujúcich 12 hodín |
| `uv_index` | — | UV index (pri jasnej oblohe) |

> Predvolené premenné: `temperature_2m, cloud_cover, precipitation_1h, wind_speed, humidity`

---

## Výstup

Skript vypíše:
1. **Nájdené mesto** a jeho súradnice (geocoding cez OpenStreetMap Nominatim)
2. **Tabuľku** hodinových hodnôt pre zvolené premenné
3. **Štatistiky** — min, max, priemer pre každú premennú

```
Hladam mesto: Zilina...
Najdene: Žilina, okres Žilina, Žilinský kraj, Slovensko
Suradnice: lat=49.2235, lon=18.7393

Stiahuvam predpoved z MET Norway...
Aktualizovane: 2026-03-30T13:16:12Z
Pocet hodinovych zaznamov celkovo: 93
Zaznamov v zadanom rozmezi: 36

================================================================
PREDIKCNE DATA (MET Norway): Zilina
================================================================
Cas (UTC)                   temperature_2m(celsius) cloud_cover(%) ...
------------------------------------------------------------------------
2026-03-30T13:00:00Z        7.2                     100.0          ...
...

================================================================
STATISTIKY
================================================================
  temperature_2m            Min=1.80  Max=8.10  Priemer=3.82
  cloud_cover               Min=83.60  Max=100.00  Priemer=98.35
```

---

## Poznámky

- Všetky časy sú v **UTC**
- MET Norway neposkytuje **historické dáta** — pre historické merania použi `Open-Meteo/fetch_reality.py` alebo `SHMU/fetch_reality.py`
- API nevyžaduje registráciu ani API kľúč
- Pri rate limite (HTTP 429) skript automaticky počká a zopakuje požiadavku
- Geocoding funguje pre mestá na celom svete

