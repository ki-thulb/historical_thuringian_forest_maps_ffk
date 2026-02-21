# Von zerschnittenen Karten zum GIS-Layer

**Thüringer Forstgeschichte digital neu entdecken** — ThULB Hackathon Challenge 3

Automatisierte Rekonstruktion und Georeferenzierung historischer Forstkarten aus Thüringen.

## Das Problem

Tausende historische Forstkarten schlummern in Archiven. Die Karten wurden zerschnitten, auf Leinen geklebt, gefaltet und eingescannt — das hinterlässt:
- Sichtbare Faltlinien als Gitterraster über der Karte
- Dunkle Scanränder rund um das Bild
- Maßstabsverschiebungen in den Faltbereichen

## Pipeline

```
Scan (JPG/TIFF)
      │
      ▼
 1. clean_map.py       → Ränder entfernen, Faltlinien korrigieren
      │
      ▼
 2. georeference.py    → Historische Karte → GeoTIFF (EPSG:25832)
      │
      ▼
 3. extract_places.py  → OCR Ortsnamen → Geocoding → GeoJSON/Shapefile
      │
      ▼
 GeoTIFF + GIS-Layer mit historischen Ortspunkten
```

## Setup

```bash
# uv installieren (falls noch nicht vorhanden)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Repo klonen
git clone <repo-url>
cd Hack_the_heritage
```

Alle Skripte tragen ihre Abhängigkeiten direkt per [PEP 723](https://peps.python.org/pep-0723/) — kein separates `pip install` nötig.

## Verwendung

### Schritt 1: Ränder & Faltlinien entfernen

```bash
uv run clean_map.py Jena-03-Gem1.jpg
# → Jena-03-Gem1_clean.jpg

# Mit Debug-Ausgaben
uv run clean_map.py Jena-03-Gem1.jpg --debug

# Parameter überschreiben
uv run clean_map.py Jena-03-Gem1.jpg --border-thresh 60 --output output.jpg
```

**Optionen:**

| Option | Standard | Beschreibung |
|--------|----------|--------------|
| `INPUT` | — | Eingabebild (JPG/TIFF) |
| `--output` | `*_clean.jpg` | Ausgabepfad |
| `--border-thresh N` | 80 | Schwellwert für Randerkennung (0–255) |
| `--no-border-crop` | — | Randentfernung überspringen |
| `--debug` | — | Zwischenergebnisse speichern |

## Dateistruktur

```
Hack_the_heritage/
├── clean_map.py            # Schritt 1: Rand- & Faltlinienentfernung
├── Jena-03-Gem1.jpg        # Beispielkarte: Gemeindewaldung Kunitz 1933
└── Forstkarten_Inventarliste_2026-01-20_hackathon.xlsx
```

## Tech Stack

- Python 3.9, [uv](https://docs.astral.sh/uv/)
- OpenCV, NumPy, Pillow
- GDAL/Rasterio (Schritt 2)
- EasyOCR / Tesseract (Schritt 3)

## Hackathon

**ThULB — Hack the Heritage**, Challenge 3: Forstgeschichte
Mentor: Tom Meißner | Digitales Kultur- und Sammlungsmanagement
