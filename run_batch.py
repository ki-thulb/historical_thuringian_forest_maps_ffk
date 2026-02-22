#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""
run_batch.py — Batch processor for Forstkarten pipeline.

Runs both pipelines for every original image in map-images/:
  1. stitch.py        → <stem>_cropped.jpg   (projection histogram crop)
  2. stitch_tiles.py  → <stem>_stitched.jpg  (SIFT stitch)

Skips images that are already pipeline outputs (_cropped, _stitched, _clean).

Usage:
    uv run run_batch.py [--dir DIR] [--dry-run] [--skip-existing]
"""

import argparse
import subprocess
import sys
from pathlib import Path

SKIP_SUFFIXES = ("_cropped", "_stitched", "_clean", "_debug")


def is_original(path: Path) -> bool:
    stem = path.stem
    return not any(stem.endswith(s) for s in SKIP_SUFFIXES)


def run(cmd: list[str], dry_run: bool) -> bool:
    print(f"  $ {' '.join(cmd)}")
    if dry_run:
        return True
    result = subprocess.run(cmd)
    return result.returncode == 0


def main():
    parser = argparse.ArgumentParser(description="Batch-run both pipelines on all map images.")
    parser.add_argument("--dir", default="map-images",
                        help="Directory with input images (default: map-images)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print commands without executing")
    parser.add_argument("--skip-existing", action="store_true",
                        help="Skip if output file already exists")
    args = parser.parse_args()

    img_dir = Path(args.dir)
    if not img_dir.exists():
        sys.exit(f"Error: directory not found: {img_dir}")

    images = sorted(p for p in img_dir.glob("*.jpg") if is_original(p))

    if not images:
        sys.exit("No original images found.")

    print(f"Found {len(images)} original image(s) in {img_dir}/\n")

    ok = err = skip = 0

    for img in images:
        print(f"\n{'='*60}")
        print(f"Image: {img.name}")
        print(f"{'='*60}")

        # --- Pipeline 1: stitch.py → *_cropped.jpg ---
        out_crop = img.parent / (img.stem + "_cropped" + img.suffix)
        if args.skip_existing and out_crop.exists():
            print(f"  [SKIP] stitch.py  — {out_crop.name} exists")
            skip += 1
        else:
            print(f"  [1/2] stitch.py (projection histogram crop)")
            success = run(["uv", "run", "stitch.py", str(img)], args.dry_run)
            if success:
                ok += 1
            else:
                print(f"  [ERROR] stitch.py failed for {img.name}")
                err += 1

        # --- Pipeline 2: stitch_tiles.py → *_stitched.jpg ---
        out_stitch = img.parent / (img.stem + "_stitched" + img.suffix)
        if args.skip_existing and out_stitch.exists():
            print(f"  [SKIP] stitch_tiles.py — {out_stitch.name} exists")
            skip += 1
        else:
            print(f"  [2/2] stitch_tiles.py (SIFT stitch)")
            success = run(["uv", "run", "stitch_tiles.py", "--debug", str(img)], args.dry_run)
            if success:
                ok += 1
            else:
                print(f"  [ERROR] stitch_tiles.py failed for {img.name}")
                err += 1

    print(f"\n{'='*60}")
    print(f"Done — {ok} OK  |  {err} errors  |  {skip} skipped")
    if err:
        sys.exit(1)


if __name__ == "__main__":
    main()
