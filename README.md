# Von zerschnittenen Karten zum GIS-Layer

**Thüringer Forstgeschichte digital neu entdecken** — ThULB Hackathon Challenge 3

Automatisierte Rekonstruktion und Georeferenzierung historischer Forstkarten aus Thüringen.

---

## Das Problem

Die Karten wurden ursprünglich als große bedruckte Bögen hergestellt, dann physisch in Stücke **gleicher Größe** geschnitten, auf Leinen aufgeklebt, gefaltet und eingescannt. Das hinterlässt:

- Dunkle **Scanränder** rings um das Bild
- Sichtbare **Faltlinien** als Gitterraster über der Karte (ggf. leicht gebogen)
- Geringfügige **Maßstabsverschiebungen** in den Faltbereichen

---

## Pipeline

```
Scan (JPG/TIFF)
      │
      ▼
 Stage 1 ── Rand-Erkennung & Zuschnitt
      │       detect_content_bbox()
      │       → dunkle Ränder entfernen
      │
      ▼
 Stage 2 ── Falzlinien-Erkennung
      │       detect_fold_lines()  oder  detect_fold_lines_hough()
      │       → Liste (center, left_edge, right_edge) je Falz
      │
      ▼
 Stage 3 ── Begradigung & Entfernung
      │       detect_fold_curve()   → tatsächlichen Kurvenverlauf bestimmen
      │       straighten_fold()     → cv2.remap, Kurve → gerade Linie
      │       remove_straight_fold()→ Band ausschneiden, Seiten zusammenfügen
      │
      ▼
 Stitched output (JPG, 95 % Qualität)
      │
      ▼
 2. Georeferenzierung  (georeference.py, TODO)
      │
      ▼
 3. OCR + Geocoding   (extract_places.py, TODO)
      │
      ▼
 GeoTIFF + GIS-Layer mit historischen Ortspunkten
```

---

## Skripte

### `stitch_tiles.py` — Hauptpipeline

Führt alle drei Stages für einen Scan durch.

```bash
uv run stitch_tiles.py INPUT [--output OUTPUT] [--border-thresh N]
                        [--detection-method legacy|hough] [--debug]
```

| Option | Standard | Beschreibung |
|--------|----------|--------------|
| `INPUT` | — | Eingabebild (JPG/TIFF) |
| `--output` | `*_stitched.jpg` | Ausgabepfad |
| `--border-thresh N` | 80 | Schwellwert Randerkennung (0–255) |
| `--detection-method` | `legacy` | Erkennungsalgorithmus (s. unten) |
| `--debug` | — | Falz-Overlay-Bild speichern |

**Beispiele:**

```bash
uv run stitch_tiles.py Jena-03-Gem1.jpg --debug
uv run stitch_tiles.py "Weimar-64-VW-3#2.jpg" --detection-method hough --debug
uv run stitch_tiles.py map-images/1085149331_000108#0002.jpg
```

---

### `clean_map.py` — Einfache Falzentfernung (ohne Begradigung)

Entfernt Rand und schneidet Falzbänder direkt aus — kein Remap, kein Straightening.
Schneller, aber keine Korrektur gebogener Falzlinien.

```bash
uv run clean_map.py INPUT [--output OUTPUT] [--border-thresh N]
                    [--no-border-crop] [--debug]
```

---

## Stage-Beschreibungen

### Stage 1 — Rand-Erkennung (`stages/border_removal.py`)

`detect_content_bbox()` scannt von jedem Rand nach innen und sucht die erste
Zeile/Spalte, bei der weniger als 60 % der Pixel dunkler als `dark_thresh` sind.
Ergebnis: `(top, bottom, left, right)` — Koordinaten des nutzbaren Bildbereichs.

---

### Stage 2 — Falzlinien-Erkennung (`stages/fold_detection.py`)

Die Kacheln sind immer gleich groß, d. h. die Falzlinien bilden ein **gleichmäßiges
Raster** (z. B. 4×7-Kacheln → 3 vertikale + 6 horizontale Falzlinien).

Zwei Erkennungsmethoden stehen zur Wahl:

#### `detect_fold_lines()` — Matched-Filter (Standard)

1. **Helligkeitsprofil** — Median über den mittleren 35–65 %-Streifen des Bildes
   (vermeidet Legende und Rahmen).

2. **Symmetrischer Matched-Filter-Score** — Für jede Position i:

   ```
   score[i] = min(mean(linke Nachbarn) − mean(Band),
                  mean(rechte Nachbarn) − mean(Band))
   ```

   Positiv nur wenn das Band **dunkler** als **beide** Nachbarbereiche ist —
   die exakte Signatur einer Falzkante (dunkler Streifen zwischen zwei hellen
   Bereichen). Einseitige Übergänge (Waldrand auf einer Seite, Felder auf der
   anderen) erzeugen einen negativen Minimalwert und werden auf 0 gesetzt.

3. **Peakerkennung** mit Prominenzschwelle `mean + 2,5 · std`.

4. **Gleichabstands-Filter** (`_select_equal_spacing`) — Da alle Kacheln gleich
   groß sind, sitzen k Falzlinien bei `n/(k+1), 2n/(k+1), …, k·n/(k+1)`.
   Die Funktion wählt die Teilmenge, die am besten zu einem gleichmäßigen Raster
   passt (Toleranz ±20 % des Abstands). Sicherheitsprüfung: Peaks, die ≥ 20 %
   des stärksten Peaks erreichen, werden nicht entfernt (Schutz vor ungleichmäßig
   großen Kacheln).

5. **Positions-Verfeinerung** — argmin der Helligkeit im ±50-px-Fenster um den Peak.

6. **Bandbreite** — Die Bandgrenzen werden bestimmt, bis der Score auf 30 % des
   Peakwerts absinkt, mindestens aber ±`fold_half_width` = 25 px.

#### `detect_fold_lines_hough()` — Hough-Validierung (robuster, langsamer)

Gleicher Ablauf für Kandidaten-Peaks (Steps 1–3), danach:

4. **Canny-Kantenbild** via bilateralem Filter + `cv2.Canny`.

5. **HoughLinesP** in einem ±80-px-Streifen um jeden Kandidaten.
   Nur Liniensegmente innerhalb ±5° der Senkrechten zur Falzachse werden
   akzeptiert. Kandidaten ohne solche Segmente werden verworfen.

6. **Verfeinerter Mittelpunkt** = Median der Hough-Segment-Mittelpunkte.

7. Gleichabstands-Filter und Bandbreitenberechnung wie oben.

**Wann welche Methode?**

| Situation | Empfehlung |
|-----------|------------|
| Einfarbige / helle Karte | `legacy` (schneller) |
| Mehrfarbige Karte mit großen Waldgebieten | `hough` (robuster) |
| Fragmentierte oder teils verdeckte Falzlinien | `hough` |

---

### Stage 3 — Begradigung & Entfernung (`stages/stitcher.py`)

Für jede erkannte Falzlinie:

1. **`detect_fold_curve()`** — Pro Zeile (vertikale Falz) oder Spalte (horizontale
   Falz) wird das dunkelste Pixel im ±60-px-Fenster um den Falzmittelpunkt gesucht.
   Der resultierende Kurvenverlauf wird mit σ = 15 px geglättet.

2. **`straighten_fold()`** — `cv2.remap` verschiebt jeden Pixel um
   `fold_center − curve[y]` Pixel, mit linearer Gewichtung die auf 0 abklingt
   bei ±60 px vom Falzmittelpunkt. Die Falzkurve wird so zu einer geraden Linie.

3. **`remove_straight_fold()`** — Das (nun gerade) Falzband wird herausgeschnitten
   und die beiden Seiten direkt zusammengefügt (`np.concatenate`). Keine
   Interpolation, keine synthetischen Pixel. Das Ausgabebild ist um
   `2 · band_half + 1` Pixel schmaler/kürzer.

Bei mehreren Falzlinien werden die Positionen durch einen kumulierten Offset
angepasst, da das Bild nach jedem Schnitt kleiner wird.

---

## Dateistruktur

```
Hack_the_heritage/
├── stitch_tiles.py             # Hauptpipeline (Stage 1–3)
├── clean_map.py                # Einfache Falzentfernung ohne Begradigung
├── stitch.py                   # Älterer Ansatz (Std.-Histogramm + Otsu)
│
├── stages/
│   ├── border_removal.py       # Stage 1: Rand-Erkennung
│   ├── fold_detection.py       # Stage 2: Falzlinien-Erkennung
│   ├── stitcher.py             # Stage 3: Begradigung & Entfernung
│   ├── fold_removal.py         # Einfache Falzentfernung (für clean_map.py)
│   └── debug_utils.py          # Overlay- und Profil-Debugging
│
├── map-images/                 # Eingabebilder (JPG/TIFF)
├── Jena-03-Gem1.jpg            # Beispiel: Gemeindewaldung Kunitz 1933
└── Weimar-64-VW-3#2.jpg        # Beispiel: Weimarer Forstkarte
```

---

## Setup

```bash
# uv installieren (falls noch nicht vorhanden)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Repo klonen
git clone <repo-url>
cd Hack_the_heritage
```

Alle Skripte tragen ihre Abhängigkeiten direkt per [PEP 723](https://peps.python.org/pep-0723/) — kein separates `pip install` nötig.

---

## Tech Stack

- Python 3.9+, [uv](https://docs.astral.sh/uv/)
- OpenCV (`opencv-python-headless`), NumPy
- GDAL/Rasterio — Schritt 2: Georeferenzierung
- EasyOCR / Tesseract — Schritt 3: OCR & Geocoding

---

## Hackathon

**ThULB — Hack the Heritage**, Challenge 3: Forstgeschichte
Mentor: Tom Meißner | Digitales Kultur- und Sammlungsmanagement
