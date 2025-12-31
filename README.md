# Temperature Atlas (Weather / Travel Planning Prototype)

A lightweight, **static** “temperature atlas” that visualizes average monthly temperatures for cities around the world. It renders an interactive MapLibre basemap, then draws a temperature “heat field” on top using inverse-distance weighting (IDW) interpolation from city averages.

The repo also includes a small Python data pipeline that scrapes city monthly averages from Wikipedia into SQLite and exports a map-friendly JSON (and a `window.TEMPERATURE_DATA` JS wrapper for best local-file compatibility).

---

## What’s in here

- **Interactive map UI**: `index.html` (no build step)
- **City temperature dataset (browser-friendly)**: `temperature_data.js` (sets `window.TEMPERATURE_DATA`)
- **City temperature dataset (raw JSON)**: `temperature_data.json`
- **SQLite database**: `city_temperatures.db` (scraped/derived data)
- **Scraper**: `scrape_temperatures.py` (Wikipedia → SQLite)
- **Exporter**: `export_with_coords.py` (SQLite → JSON with lat/lng for cities we know)
- **MapLibre vendor files** (optional/offline use): `vendor/`

---

## Quick start (view the map)

### Option A: open directly (fastest)

Open `index.html` in your browser.

The app prefers `temperature_data.js`, so it usually works even via `file://` (where `fetch()` of local files may be blocked).

### Option B: run a tiny local server (most compatible)

From the repo directory:

```bash
python3 -m http.server 8000
```

Then open:

```text
http://localhost:8000
```

---

## How the visualization works

### Data model

Each city record includes:

- `city`, `country`, `continent`
- `jan` … `dec` (average monthly temperature in °C)
- `yearly_avg` (°C)
- `lat`, `lng`

The map UI expects:

- `window.TEMPERATURE_DATA = { cities: [...] }` (provided by `temperature_data.js`)
- Fallback: `fetch('temperature_data.json')` if the global isn’t present

### Rendering approach

In `index.html`:

- MapLibre GL renders a raster basemap (Carto Voyager tiles).
- A `<canvas>` overlays the map.
- For each output pixel (rendered at reduced resolution for speed), the app:
  - Unprojects pixel → lat/lng using the map projection
  - Computes an IDW interpolation from all city points for the selected month
  - Converts temperature → RGB color via a multi-stop gradient
  - Writes pixels to the canvas, then scales up smoothly

This produces a continuous temperature field that updates as you pan/zoom and as you change months.

---

## Refreshing / rebuilding the dataset (optional)

### 1) Scrape Wikipedia into SQLite

`scrape_temperatures.py` downloads and parses:

`https://en.wikipedia.org/wiki/List_of_cities_by_average_temperature`

It creates/overwrites (or updates) a local SQLite database:

- `city_temperatures.db`

Run:

```bash
python3 scrape_temperatures.py
```

Dependencies:

```bash
python3 -m pip install requests beautifulsoup4
```

### 2) Export JSON with coordinates

`export_with_coords.py` reads `city_temperatures.db` and produces:

- `temperature_data.json`

Important note: despite the docstring mentioning geocoding, **the current exporter does not call a geocoding API**. It only assigns coordinates for cities present in the hard-coded `CITY_COORDS` map, and it exports only those “known-coordinate” cities.

Run:

```bash
python3 export_with_coords.py
```

If you want more cities on the map, extend `CITY_COORDS` (or add a real geocoding step).

### 3) Generate `temperature_data.js` from `temperature_data.json`

`temperature_data.js` is a convenience wrapper so the app can load data without `fetch()` (helpful for `file://` viewing).

You can regenerate it like this:

```bash
python3 - <<'PY'
import json
data = json.load(open("temperature_data.json", "r", encoding="utf-8"))
with open("temperature_data.js", "w", encoding="utf-8") as f:
    f.write("// Auto-generated from temperature_data.json\n")
    f.write("window.TEMPERATURE_DATA = ")
    json.dump(data, f, ensure_ascii=False)
    f.write(";\n")
print("Wrote temperature_data.js")
PY
```

---

## Notes / limitations

- **Basemap tiles require internet** (Carto raster tiles).
- **WebGL is required** (MapLibre).
- The temperature field is an **interpolation** of city averages; it is not a true gridded climate model and will be less meaningful over oceans/remote regions.
- Export coverage depends on which cities have coordinates in `CITY_COORDS`.

---

## Credits / attribution

- Source table: Wikipedia “List of cities by average temperature”
- Map rendering: MapLibre GL JS
- Basemap tiles: Carto Voyager raster tiles (with OpenStreetMap contributors)


