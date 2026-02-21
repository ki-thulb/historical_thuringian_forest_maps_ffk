# vlm_extraction — VLM-basierte Metadatenextraktion für Forstkarten

Zweistufige Pipeline zur Batch-Verarbeitung von ~1000 historischen Forstkarten-Scans:

1. **compress_maps.py** — Reduziert 8–25 MB Scans auf ~1–4 MB (Textkanten bleiben scharf)
2. **extract_map_metadata.py** — Extrahiert Karten-Metadaten via Qwen VLM → GeoJSON

## Quick Start

### 1. API-Key einrichten

Umgebungsvariable setzen:
```bash
export OPENROUTER_API_KEY=sk-or-...
```

Oder `.env`-Datei in diesem Ordner anlegen:
```
OPENROUTER_API_KEY=sk-or-...
```

### 2. Scans komprimieren

```bash
uv run vlm_extraction/compress_maps.py map-images/ compressed/
```

### 3. Metadaten extrahieren

```bash
uv run vlm_extraction/extract_map_metadata.py compressed/ geojson_out/
```

Ausgabe: `geojson_out/<stem>.geojson` pro Bild + `geojson_out/all_maps_merged.geojson`

### Unterbrochene Läufe fortsetzen

Beide Scripts unterstützen `--skip-existing`:

```bash
uv run vlm_extraction/compress_maps.py map-images/ compressed/ --skip-existing
uv run vlm_extraction/extract_map_metadata.py compressed/ geojson_out/ --skip-existing
```

Fehlgeschlagene Bilder (`*.error.json`) werden beim nächsten Lauf automatisch
wiederholt (kein `.geojson` vorhanden → kein Skip).

---

## Optionen

### compress_maps.py

| Option | Default | Beschreibung |
|--------|---------|--------------|
| `INPUT_DIR` | — | Verzeichnis mit Quell-JPGs |
| `OUTPUT_DIR` | — | Ausgabeverzeichnis für komprimierte JPGs |
| `--quality N` | `75` | JPEG-Qualität 1–95 |
| `--max-size PX` | `4096` | Max. Pixel auf der längsten Seite |
| `--skip-existing` | — | Überspringt bereits vorhandene Outputs |

**Design-Entscheidungen:**
- Qualität 75: gutes Gleichgewicht zwischen Textlesbarkeit für OCR/VLM und Dateigröße
- 4096px: VLMs verarbeiten bis zu 4096px nativ
- Subsampling 4:4:4: erhält Chroma-Auflösung → schärfere Textkanten gegenüber Standard-4:2:0

### extract_map_metadata.py

| Option | Default | Beschreibung |
|--------|---------|--------------|
| `INPUT_DIR` | — | Verzeichnis mit komprimierten JPGs |
| `OUTPUT_DIR` | — | Ausgabeverzeichnis für .geojson-Dateien |
| `--model STR` | `qwen/qwen3.5-plus-02-15` | OpenRouter Modell-ID |
| `--delay SEC` | `1.0` | Sekunden zwischen API-Calls |
| `--skip-existing` | — | Überspringt Bilder mit vorhandener .geojson |
| `--max-api-size PX` | `2048` | Max. Pixel vor Base64-Kodierung für API |

---

## GeoJSON-Ausgabeformat

Jedes Bild erzeugt eine Datei `<stem>.geojson`:

```json
{
  "type": "FeatureCollection",
  "metadata": {
    "source_file": "Dateiname.jpg",
    "map_title": "Forstkarte Jena-03",
    "map_date": "1933",
    "map_scale": "1:10000",
    "map_region": "Thüringen",
    "notes": "..."
  },
  "features": [
    {
      "type": "Feature",
      "geometry": null,
      "properties": {
        "category": "Gemarkung",
        "text": "Kunitz",
        "readable": true,
        "confidence": "high",
        "location_description": "Oben links, Kartentitel"
      }
    },
    {
      "type": "Feature",
      "geometry": null,
      "properties": {
        "category": "Forstbestand",
        "text": "[unleserlich]",
        "readable": false,
        "confidence": "low",
        "location_description": "Mitte, stark verblasst"
      }
    }
  ]
}
```

Kategorien: `Gemarkung`, `Ortsname`, `Forstbestand`, `Weg`, `Gewässer`, `Legende`, `Beschriftung`, `Grenze`, `Sonstiges`

Die zusammengeführte Datei `all_maps_merged.geojson` enthält alle Features aller
Bilder. Jedes Feature erhält zusätzlich `properties.source_metadata` mit den
Bild-Metadaten.

---

## Fehlerbehandlung

| Situation | Verhalten |
|-----------|-----------|
| API-Fehler | Exponential Backoff: 3 Versuche (2s → 4s → 8s), dann `*.error.json` |
| JSON nicht parsebar | 4-Ebenen-Fallback, bei Misserfolg `*.error.json` |
| Einzelbild-Fehler | Weiter mit nächstem Bild (kein Abbruch) |
| Rate Limit | `--delay` erhöhen (z.B. `--delay 2.0`) |

`.error.json`-Dateien enthalten `source_file`, `error` und `raw_response`
(erste 3000 Zeichen) zur Diagnose.

**Resume-Strategie:** `--skip-existing` überspringt Bilder mit vorhandener
`.geojson`. Bilder mit nur `.error.json` werden wiederholt → Lauf einfach neu
starten bis keine Fehler mehr auftreten.

---

## Kosten (Richtwert)

- Kosten variieren je nach gewähltem Modell auf OpenRouter
- Default: `qwen/qwen3.5-plus-02-15`
- Aktuelle Preise: https://openrouter.ai/models

---

## Modell wechseln

Das Modell ist per `--model` konfigurierbar:

```bash
# Beispiel: anderes Modell verwenden
uv run vlm_extraction/extract_map_metadata.py compressed/ geojson_out/ \
    --model qwen/qwen2.5-vl-72b-instruct
```

Alle auf OpenRouter verfügbaren Modelle: https://openrouter.ai/models
