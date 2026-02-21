# Hack the Heritage — CLAUDE.md

## Project Overview

ThULB hackathon challenge: automate digitization of ~2000 historical Thuringian forest maps (Forstkarten). The maps were cut into tiles, glued onto linen, folded, and rescanned — leaving visible fold grid lines, outer scanning borders, and scale distortions.

**Pipeline (3 steps):**
1. **Kachel-Rekonstruktion** — remove outer borders & fold/stitch lines → clean image
2. **Georeferenzierung** — transform to modern coordinates (GeoTIFF via GDAL)
3. **Textextraktion & Geocoding** — OCR place names, geocode, export as GIS layer (Shapefile/GeoJSON)

**Output:** GeoTIFF + GIS layer with historical place points

## Tech Stack

- **Python 3.9** (see `.python-version`)
- **uv** for package management — always use `uv run <script>.py`
- **PEP 723 inline script metadata** for standalone scripts (preferred over pyproject.toml deps)
- **OpenCV** (`opencv-python-headless`) — image processing
- **NumPy** — array operations
- **Pillow** — image I/O fallback
- **GDAL / Rasterio** — georeferencing (Step 2)
- **EasyOCR / Tesseract** — text extraction (Step 3)

## Running Scripts

```bash
uv run <script>.py [args]
```

Scripts carry their own inline deps — no separate install needed.

## Project Structure

```
Hack_the_heritage/
├── CLAUDE.md               # This file
├── README.md               # Project documentation
├── pyproject.toml          # uv project config
├── .python-version         # 3.9
├── main.py                 # Entry point placeholder
├── clean_map.py            # Step 1: border & fold line removal
├── Jena-03-Gem1.jpg        # Sample input map (Kunitz 1933)
└── Forstkarten_Inventarliste_2026-01-20_hackathon.xlsx  # Map inventory
```

## Conventions

- Code and comments in English
- German domain terms kept as-is (Forstkarte, Bestandeskarte, Faltbereiche, etc.)
- Script outputs go to same directory as input, with suffix: `*_clean.jpg`, `*.tif`
- Debug outputs go to `<stem>_debug/` subdirectory
- Never commit large images or `*_clean.jpg` outputs (see .gitignore)

## Key Domain Knowledge

- Maps have varying fold grids: 2x2, 2x3, 3x3, 4x5 tiles
- Scale is distorted in fold areas (Faltbereiche) — account for this in georeferencing
- Maps are from various epochs; coordinate system is likely German historic grid → needs EPSG:25832 (ETRS89 / UTM zone 32N)
- Place names may use historic German orthography (umlaut variants, old spellings)
- Map scale is typically 1:10000 or 1:15000; stated in legend
