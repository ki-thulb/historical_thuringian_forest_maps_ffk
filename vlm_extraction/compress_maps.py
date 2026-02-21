#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = [
#     "pillow",
#     "tqdm",
# ]
# ///
"""
compress_maps.py — Pre-processing for the Forstkarten VLM pipeline.

Batch-compresses large JPG scans (8-25 MB) to ~1-4 MB while preserving
text legibility for OCR and VLM inference (Qwen via OpenRouter).

Design choices:
  - JPEG quality 75:    good OCR/VLM balance vs file size
  - Max 4096px:         longest side; VLMs handle up to 4096px natively
  - Subsampling 4:4:4:  preserves chroma resolution for text sharpness
  - Idempotent:         --skip-existing skips already-compressed outputs

Usage:
    uv run compress_maps.py INPUT_DIR OUTPUT_DIR [options]

    uv run compress_maps.py map-images/ compressed/
    uv run compress_maps.py map-images/ compressed/ --quality 75 --max-size 4096
    uv run compress_maps.py map-images/ compressed/ --skip-existing
"""

import argparse
import os
import sys

from PIL import Image
from tqdm import tqdm

# Disable Pillow's decompression bomb check — these are trusted internal scans
# that can legitimately exceed 178 MP (e.g. 25 MB JPG = ~260 MP at full resolution)
Image.MAX_IMAGE_PIXELS = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def find_jpg_inputs(input_dir):
    """Return sorted list of absolute .jpg/.jpeg paths in input_dir (non-recursive)."""
    entries = sorted(os.listdir(input_dir))
    result = []
    for name in entries:
        if name.lower().endswith((".jpg", ".jpeg")):
            result.append(os.path.join(input_dir, name))
    return result


def resize_if_needed(img, max_size):
    """
    Downscale img so its longest dimension <= max_size using LANCZOS resampling.
    Returns the original object unchanged if already within bounds.
    Does NOT upscale smaller images.
    """
    w, h = img.size
    if max(w, h) <= max_size:
        return img
    scale = max_size / max(w, h)
    new_w = int(w * scale)
    new_h = int(h * scale)
    return img.resize((new_w, new_h), Image.LANCZOS)


def compress_single(src_path, dst_path, quality, max_size, subsampling=0):
    """
    Load src, convert to RGB, resize if needed, save as JPEG to dst.
    subsampling=0 means 4:4:4 in Pillow (better for text edges).
    Returns (src_mb, dst_mb) for stats reporting.
    """
    src_mb = os.path.getsize(src_path) / 1_000_000.0

    with Image.open(src_path) as img:
        if img.mode != "RGB":
            img = img.convert("RGB")
        img = resize_if_needed(img, max_size)
        img.save(dst_path, format="JPEG", quality=quality,
                 optimize=True, subsampling=subsampling)

    dst_mb = os.path.getsize(dst_path) / 1_000_000.0
    return src_mb, dst_mb


# ---------------------------------------------------------------------------
# Batch processor
# ---------------------------------------------------------------------------

def compress_batch(input_dir, output_dir, quality, max_size, skip_existing):
    os.makedirs(output_dir, exist_ok=True)

    jpg_files = find_jpg_inputs(input_dir)
    if not jpg_files:
        print(f"No JPG files found in: {input_dir}")
        sys.exit(1)

    print(f"Found {len(jpg_files)} JPG(s) in {input_dir}")
    print(f"Settings: quality={quality}  max_size={max_size}px  "
          f"subsampling=4:4:4  skip_existing={skip_existing}")
    print()

    total_src_mb = 0.0
    total_dst_mb = 0.0
    n_done = 0
    n_skipped = 0
    n_failed = 0

    for src_path in tqdm(jpg_files, unit="img"):
        dst_path = os.path.join(output_dir, os.path.basename(src_path))

        if skip_existing and os.path.exists(dst_path):
            n_skipped += 1
            continue

        try:
            src_mb, dst_mb = compress_single(src_path, dst_path, quality, max_size)
            total_src_mb += src_mb
            total_dst_mb += dst_mb
            n_done += 1
        except Exception as exc:
            tqdm.write(f"[WARN] skipping {os.path.basename(src_path)}: {exc}")
            n_failed += 1

    print()
    print(f"Compressed {n_done}/{len(jpg_files)} images  "
          f"({n_skipped} skipped, {n_failed} failed)")
    if total_src_mb > 0:
        total_src_gb = total_src_mb / 1024.0
        total_dst_gb = total_dst_mb / 1024.0
        reduction = 100.0 * (1.0 - total_dst_mb / total_src_mb)
        if total_src_gb >= 0.1:
            print(f"  Total input:   {total_src_gb:.2f} GB")
            print(f"  Total output:  {total_dst_gb:.2f} GB")
        else:
            print(f"  Total input:   {total_src_mb:.1f} MB")
            print(f"  Total output:  {total_dst_mb:.1f} MB")
        print(f"  Reduction:     {reduction:.1f} %")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Batch-compress Forstkarte JPGs for VLM/OCR processing.")
    parser.add_argument("input_dir", metavar="INPUT_DIR",
                        help="Directory containing source JPG scans")
    parser.add_argument("output_dir", metavar="OUTPUT_DIR",
                        help="Directory to write compressed JPGs")
    parser.add_argument("--quality", type=int, default=75, metavar="N",
                        help="JPEG quality 1-95 (default: 75)")
    parser.add_argument("--max-size", type=int, default=4096, metavar="PX",
                        help="Max pixels on longest dimension (default: 4096)")
    parser.add_argument("--skip-existing", action="store_true",
                        help="Skip output files that already exist")
    args = parser.parse_args()

    compress_batch(
        input_dir=args.input_dir,
        output_dir=args.output_dir,
        quality=args.quality,
        max_size=args.max_size,
        skip_existing=args.skip_existing,
    )


if __name__ == "__main__":
    main()
