#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = [
#     "openai",
#     "tqdm",
#     "pillow",
#     "python-dotenv",
# ]
# ///
"""
extract_map_metadata.py — VLM-based metadata extraction for Forstkarten.

For each compressed JPG in INPUT_DIR:
  1. Encodes image as base64 JPEG (max 2048px for API token limits)
  2. Calls Qwen VLM via OpenRouter (OpenAI-compatible API)
  3. Parses GeoJSON from the response
  4. Writes a per-image <stem>.geojson to OUTPUT_DIR

After all images are processed, merges all per-image GeoJSON files into
all_maps_merged.geojson.

Auth:
  Set OPENROUTER_API_KEY in your environment or in a .env file in the
  working directory (or vlm_extraction/ directory).

Usage:
    uv run extract_map_metadata.py INPUT_DIR OUTPUT_DIR [options]

    uv run extract_map_metadata.py compressed/ geojson_out/
    uv run extract_map_metadata.py compressed/ geojson_out/ --model qwen/qwen3.5-plus-02-15
    uv run extract_map_metadata.py compressed/ geojson_out/ --delay 2.0 --skip-existing
    uv run extract_map_metadata.py compressed/ geojson_out/ --price-input 0.14 --price-output 0.28

Cost options (in $/M tokens — check https://openrouter.ai/models for current rates):
    --price-input FLOAT   Cost per 1M input  tokens  (default: 0.0 = not shown)
    --price-output FLOAT  Cost per 1M output tokens  (default: 0.0 = not shown)
"""

import argparse
import base64
import io
import json
import os
import re
import sys
import time

from dotenv import load_dotenv
from openai import OpenAI
from PIL import Image
from tqdm import tqdm


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL       = "qwen/qwen3.5-plus-02-15"
DEFAULT_DELAY       = 1.0      # seconds between API calls
DEFAULT_MAX_API_PX  = 2048     # longest side before base64 encoding
MAX_RETRIES         = 3
RETRY_BASE_DELAY    = 2.0      # seconds; doubles each attempt (exponential backoff)

# System context injected as the system message
CONTEXT_NOTE = (
    "Es handelt sich bei dem Kartenmaterial um historische Forstkarten, auf denen "
    "Gemarkungen, Laendereien, Baum-Populationen und deren Verbreitungen sowie weitere "
    "fuer Geo Informationssysteme relevante Informationen dokumentiert sind."
)

# User extraction prompt (verbatim from project specification)
EXTRACTION_PROMPT = (
    "Extrahiere alle erkennbaren Textinformationen und beschreibenen Metadaten "
    "von den digitalisierten Karten. Bitte extrahiere alle Informationen in einem "
    "validen GeoJSON, halluziniere nicht und markiere ggf. unleserliche Textbereiche.\n\n"
    "Antworte AUSSCHLIESSLICH mit einem validen JSON-Objekt im folgenden Format "
    "(kein umliegender Text, kein Markdown-Codeblock):\n"
    '{\n'
    '  "type": "FeatureCollection",\n'
    '  "metadata": {\n'
    '    "source_file": "<Dateiname>",\n'
    '    "map_title": "<Kartentitel oder null>",\n'
    '    "map_date": "<Kartendatum oder null>",\n'
    '    "map_scale": "<Massstab z.B. 1:10000 oder null>",\n'
    '    "map_region": "<Region/Gebiet oder null>",\n'
    '    "notes": "<Sonstige Anmerkungen>"\n'
    '  },\n'
    '  "features": [\n'
    '    {\n'
    '      "type": "Feature",\n'
    '      "geometry": null,\n'
    '      "properties": {\n'
    '        "category": "<Gemarkung|Ortsname|Forstbestand|Weg|Gewaesser|Legende|Beschriftung|Grenze|Sonstiges>",\n'
    '        "text": "<extrahierter Text>",\n'
    '        "readable": true,\n'
    '        "confidence": "<high|medium|low>",\n'
    '        "location_description": "<Beschreibung der Position auf der Karte>"\n'
    '      }\n'
    '    }\n'
    '  ]\n'
    '}\n\n'
    "Kategorien: Gemarkung, Ortsname, Forstbestand (Baumarten/Bestandsnummer), "
    "Weg, Gewaesser, Legende, Beschriftung, Grenze, Sonstiges.\n"
    "Fuer unleserliche Textbereiche: readable=false und text=\"[unleserlich]\"."
)


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def load_api_key():
    """
    Load OPENROUTER_API_KEY from environment or .env file.
    Checks both the current working directory and the script's directory.
    Exits with a helpful message if not found.
    """
    # Try .env in cwd first, then in the script's own directory
    load_dotenv()
    script_dir = os.path.dirname(os.path.abspath(__file__))
    load_dotenv(os.path.join(script_dir, ".env"))

    key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not key:
        sys.exit(
            "Error: OPENROUTER_API_KEY not set.\n"
            "  Option 1 — set in your shell:\n"
            "    export OPENROUTER_API_KEY=sk-or-...\n"
            "  Option 2 — create vlm_extraction/.env:\n"
            "    OPENROUTER_API_KEY=sk-or-..."
        )
    return key


# ---------------------------------------------------------------------------
# Image encoding
# ---------------------------------------------------------------------------

def encode_image_b64(img_path, max_px=DEFAULT_MAX_API_PX):
    """
    Open img_path with Pillow, convert to RGB, downscale if needed,
    re-encode as JPEG quality=85 in-memory, return base64 string.
    """
    with Image.open(img_path) as img:
        if img.mode != "RGB":
            img = img.convert("RGB")
        w, h = img.size
        if max(w, h) > max_px:
            scale = max_px / max(w, h)
            img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85, subsampling=0)
        return base64.b64encode(buf.getvalue()).decode("ascii")


# ---------------------------------------------------------------------------
# API call
# ---------------------------------------------------------------------------

def build_messages(b64_image, filename):
    """
    Construct the OpenAI-compatible messages list with image + prompt.
    """
    prompt = EXTRACTION_PROMPT.replace("<Dateiname>", filename)
    return [
        {"role": "system", "content": CONTEXT_NOTE},
        {
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{b64_image}"
                    },
                },
                {
                    "type": "text",
                    "text": prompt,
                },
            ],
        },
    ]


def call_vlm_with_retry(client, model, messages, max_retries=MAX_RETRIES):
    """
    Call the VLM API with exponential backoff on failure.
    Returns (content: str, usage: dict) where usage has keys:
      prompt_tokens, completion_tokens, total_tokens
    Raises RuntimeError after max_retries exhausted.
    """
    last_exc = None
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=16384,
            )
            content = response.choices[0].message.content
            usage = {
                "prompt_tokens":     getattr(response.usage, "prompt_tokens",     0) or 0,
                "completion_tokens": getattr(response.usage, "completion_tokens", 0) or 0,
                "total_tokens":      getattr(response.usage, "total_tokens",      0) or 0,
            }
            return content, usage
        except Exception as exc:
            last_exc = exc
            wait = RETRY_BASE_DELAY * (2 ** attempt)
            tqdm.write(f"  [WARN] API error (attempt {attempt + 1}/{max_retries}): {exc}")
            if attempt < max_retries - 1:
                tqdm.write(f"  Retrying in {wait:.0f}s ...")
                time.sleep(wait)
    raise RuntimeError(
        f"API call failed after {max_retries} retries. Last error: {last_exc}"
    )


# ---------------------------------------------------------------------------
# Parsing + validation
# ---------------------------------------------------------------------------

def parse_geojson_from_response(raw_text):
    """
    Extract and parse GeoJSON from VLM response text.

    Four-level fallback:
      1. Direct json.loads (clean response)
      2. ```json ... ``` fenced block
      3. ``` ... ``` fenced block (generic)
      4. Outermost { ... } brace pair
    Raises ValueError if all fail.
    """
    stripped = raw_text.strip()

    # Level 1: clean JSON string
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass

    # Level 2+3: fenced code blocks
    for pattern in [
        r"```json\s*([\s\S]+?)\s*```",
        r"```\s*([\s\S]+?)\s*```",
    ]:
        m = re.search(pattern, stripped)
        if m:
            try:
                return json.loads(m.group(1))
            except json.JSONDecodeError:
                continue

    # Level 4: outermost brace pair
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(stripped[start:end + 1])
        except json.JSONDecodeError:
            pass

    raise ValueError(
        f"Cannot parse GeoJSON from VLM response. "
        f"First 300 chars: {raw_text[:300]!r}"
    )


def validate_geojson(data, source_file):
    """
    Ensure the parsed dict has required GeoJSON FeatureCollection structure.
    Injects/updates metadata.source_file.
    Returns a conformant dict (does not raise).
    """
    if not isinstance(data, dict):
        data = {"type": "FeatureCollection", "features": []}
    if data.get("type") != "FeatureCollection":
        # Wrap a bare Feature or other object
        data = {"type": "FeatureCollection", "features": [data]}
    if not isinstance(data.get("features"), list):
        data["features"] = []
    if "metadata" not in data or not isinstance(data["metadata"], dict):
        data["metadata"] = {}
    data["metadata"]["source_file"] = source_file
    return data


# ---------------------------------------------------------------------------
# Single image processor
# ---------------------------------------------------------------------------

def format_cost(usage, price_input, price_output):
    """Return a cost string like '$0.0023' or '' if prices are both 0."""
    if price_input == 0.0 and price_output == 0.0:
        return ""
    cost = (usage["prompt_tokens"] * price_input +
            usage["completion_tokens"] * price_output) / 1_000_000.0
    return f"  |  ${cost:.4f}"


def process_single_image(img_path, output_dir, client, model, max_api_px,
                         price_input=0.0, price_output=0.0):
    """
    Full pipeline for one image: encode -> call VLM -> parse -> validate -> write.

    Output: output_dir/<stem>.geojson on success
            output_dir/<stem>.error.json on failure (preserves raw_response for debugging)
    Returns (out_path, usage) on success, (None, None) on failure.
    usage = {"prompt_tokens": N, "completion_tokens": N, "total_tokens": N}
    """
    basename = os.path.basename(img_path)
    stem = os.path.splitext(basename)[0]
    out_path = os.path.join(output_dir, f"{stem}.geojson")
    err_path = os.path.join(output_dir, f"{stem}.error.json")
    raw_text = None

    try:
        b64 = encode_image_b64(img_path, max_px=max_api_px)
        msgs = build_messages(b64, filename=basename)
        raw_text, usage = call_vlm_with_retry(client, model, msgs)
        data = parse_geojson_from_response(raw_text)
        data = validate_geojson(data, source_file=basename)

        # Embed token stats into the GeoJSON metadata for traceability
        data["metadata"]["token_usage"] = usage

        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        n_feat = len(data.get("features", []))
        cost_str = format_cost(usage, price_input, price_output)
        tqdm.write(
            f"  {basename}  →  {n_feat} features"
            f"  |  in: {usage['prompt_tokens']:,} / out: {usage['completion_tokens']:,} tok"
            f"{cost_str}"
        )
        return out_path, usage

    except Exception as exc:
        error_obj = {
            "source_file": basename,
            "error": str(exc),
            "raw_response": raw_text[:3000] if raw_text else None,
        }
        with open(err_path, "w", encoding="utf-8") as f:
            json.dump(error_obj, f, ensure_ascii=False, indent=2)
        tqdm.write(f"  [ERROR] {basename}: {exc}")
        return None, None


# ---------------------------------------------------------------------------
# Merge
# ---------------------------------------------------------------------------

def merge_geojson_files(geojson_dir, output_path):
    """
    Read all *.geojson files in geojson_dir (excluding the merged file itself),
    merge into one FeatureCollection.

    Each feature gets a source_metadata property from its image's metadata block.
    Writes to output_path.
    """
    all_features = []
    merged_basename = os.path.basename(output_path)
    skipped = 0

    for fname in sorted(os.listdir(geojson_dir)):
        if not fname.endswith(".geojson"):
            continue
        if fname == merged_basename:
            continue  # don't include the merged file itself in the merge
        fpath = os.path.join(geojson_dir, fname)
        try:
            with open(fpath, encoding="utf-8") as f:
                data = json.load(f)
            src_meta = data.get("metadata", {})
            for feat in data.get("features", []):
                if not isinstance(feat, dict):
                    continue
                feat.setdefault("properties", {})
                feat["properties"]["source_metadata"] = src_meta
                all_features.append(feat)
        except Exception as exc:
            tqdm.write(f"  [WARN] skipping {fname} during merge: {exc}")
            skipped += 1

    merged = {
        "type": "FeatureCollection",
        "features": all_features,
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)

    n_files = len([
        f for f in os.listdir(geojson_dir)
        if f.endswith(".geojson") and f != merged_basename
    ])
    print(f"Merged {len(all_features)} features from {n_files - skipped} file(s) "
          f"→ {output_path}")
    if skipped:
        print(f"  ({skipped} file(s) skipped due to parse errors)")


# ---------------------------------------------------------------------------
# Batch loop
# ---------------------------------------------------------------------------

def print_token_summary(all_usage, price_input, price_output):
    """Print cumulative token usage and optional cost breakdown."""
    total_in  = sum(u["prompt_tokens"]     for u in all_usage)
    total_out = sum(u["completion_tokens"] for u in all_usage)
    total_tok = sum(u["total_tokens"]      for u in all_usage)

    print("Token usage summary:")
    print(f"  Input tokens:   {total_in:>10,}")
    print(f"  Output tokens:  {total_out:>10,}")
    print(f"  Total tokens:   {total_tok:>10,}")

    if price_input > 0.0 or price_output > 0.0:
        cost_in  = total_in  * price_input  / 1_000_000.0
        cost_out = total_out * price_output / 1_000_000.0
        cost_tot = cost_in + cost_out
        print(f"  Cost (input):   ${cost_in:>9.4f}  (at ${price_input}/M tok)")
        print(f"  Cost (output):  ${cost_out:>9.4f}  (at ${price_output}/M tok)")
        print(f"  Cost (total):   ${cost_tot:>9.4f}")
    else:
        print("  (no pricing set — use --price-input / --price-output to show costs)")


def extract_batch(input_dir, output_dir, model, delay, skip_existing, max_api_px,
                  price_input=0.0, price_output=0.0):
    os.makedirs(output_dir, exist_ok=True)

    api_key = load_api_key()
    client = OpenAI(api_key=api_key, base_url=OPENROUTER_BASE_URL)

    jpg_files = []
    for name in sorted(os.listdir(input_dir)):
        if name.lower().endswith((".jpg", ".jpeg")):
            jpg_files.append(os.path.join(input_dir, name))

    if not jpg_files:
        print(f"No JPG files found in: {input_dir}")
        sys.exit(1)

    print(f"Found {len(jpg_files)} image(s) in {input_dir}")
    print(f"Model:       {model}")
    print(f"Delay:       {delay}s between API calls")
    print(f"Max API px:  {max_api_px}px")
    print(f"Output dir:  {output_dir}")
    if price_input > 0.0 or price_output > 0.0:
        print(f"Pricing:     ${price_input}/M input tok  |  ${price_output}/M output tok")
    print()

    n_ok = 0
    n_fail = 0
    n_skip = 0
    all_usage = []

    for i, img_path in enumerate(tqdm(jpg_files, unit="img")):
        stem = os.path.splitext(os.path.basename(img_path))[0]
        out_path = os.path.join(output_dir, f"{stem}.geojson")

        if skip_existing and os.path.exists(out_path):
            n_skip += 1
            continue

        result, usage = process_single_image(
            img_path, output_dir, client, model, max_api_px,
            price_input=price_input, price_output=price_output,
        )
        if result:
            n_ok += 1
            all_usage.append(usage)
        else:
            n_fail += 1

        # Sleep between requests (not after the last one)
        if delay > 0 and i < len(jpg_files) - 1:
            time.sleep(delay)

    print()
    print(f"Done: {n_ok} ok, {n_fail} failed, {n_skip} skipped")
    if n_fail > 0:
        print(f"  Failed images saved as *.error.json — re-run with "
              f"--skip-existing to retry only failures.")

    if all_usage:
        print()
        print_token_summary(all_usage, price_input, price_output)

    # Always merge at the end
    print()
    merged_path = os.path.join(output_dir, "all_maps_merged.geojson")
    merge_geojson_files(output_dir, merged_path)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Extract map metadata via VLM (Qwen) for Forstkarten.")
    parser.add_argument("input_dir", metavar="INPUT_DIR",
                        help="Directory with compressed JPG files")
    parser.add_argument("output_dir", metavar="OUTPUT_DIR",
                        help="Directory to write per-image .geojson files")
    parser.add_argument("--model", default=DEFAULT_MODEL,
                        help=f"OpenRouter model ID (default: {DEFAULT_MODEL})")
    parser.add_argument("--delay", type=float, default=DEFAULT_DELAY, metavar="SEC",
                        help=f"Seconds to sleep between API calls (default: {DEFAULT_DELAY})")
    parser.add_argument("--skip-existing", action="store_true",
                        help="Skip images where <stem>.geojson already exists")
    parser.add_argument("--max-api-size", type=int, default=DEFAULT_MAX_API_PX,
                        dest="max_api_px", metavar="PX",
                        help=f"Max pixels on longest side before base64 encoding "
                             f"(default: {DEFAULT_MAX_API_PX})")
    parser.add_argument("--price-input", type=float, default=0.0, metavar="USD",
                        help="Cost per 1M input tokens in USD (default: 0 = not shown). "
                             "Check https://openrouter.ai/models for current rates.")
    parser.add_argument("--price-output", type=float, default=0.0, metavar="USD",
                        help="Cost per 1M output tokens in USD (default: 0 = not shown).")
    args = parser.parse_args()

    extract_batch(
        input_dir=args.input_dir,
        output_dir=args.output_dir,
        model=args.model,
        delay=args.delay,
        skip_existing=args.skip_existing,
        max_api_px=args.max_api_px,
        price_input=args.price_input,
        price_output=args.price_output,
    )


if __name__ == "__main__":
    main()
