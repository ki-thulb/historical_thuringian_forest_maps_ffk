#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = [
#     "opencv-python-headless",
#     "numpy",
#     "pillow",
# ]
# ///
"""
clean_map.py — Step 1 of the Forstkarten pipeline.

Removes:
  - Outer scanning border  (Stage 1)
  - Internal fold/stitch lines  (Stage 2 + 3)

Usage:
    uv run clean_map.py INPUT [--output OUTPUT] [--border-thresh N]
                        [--no-border-crop] [--debug]
"""

import argparse
import os
import sys

import cv2
import numpy as np

from stages.border_removal import detect_content_bbox
from stages.fold_detection import detect_fold_lines
from stages.fold_removal import remove_fold_band
from stages.debug_utils import save_fold_overlay, save_profile_image


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

def save_stage(img: np.ndarray, debug_dir: str, stem: str, stage: str) -> None:
    path = os.path.join(debug_dir, f"{stem}_{stage}.jpg")
    cv2.imwrite(path, img, [cv2.IMWRITE_JPEG_QUALITY, 90])
    h, w = img.shape[:2]
    print(f"  [stage] {stage} → {path}  ({w}x{h})")


def process(input_path: str, output_path: str,
            border_thresh: int, no_border_crop: bool, debug: bool) -> None:

    print(f"Loading {input_path} ...")
    img = cv2.imread(input_path)
    if img is None:
        sys.exit(f"Error: could not read image: {input_path}")

    h, w = img.shape[:2]
    print(f"  Size: {w}x{h}")

    stem      = os.path.splitext(os.path.basename(input_path))[0]
    debug_dir = os.path.join(os.path.dirname(os.path.abspath(input_path)),
                             f"{stem}_debug")
    os.makedirs(debug_dir, exist_ok=True)
    print(f"  Stage outputs → {debug_dir}/")

    # ---- Stage 1: Border crop ------------------------------------------ #
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    if no_border_crop:
        print("Stage 1: border crop skipped.")
        img_s1 = img
    else:
        top, bottom, left, right = detect_content_bbox(
            gray, dark_thresh=border_thresh)
        print(f"Stage 1: border crop  top={top} bottom={bottom} "
              f"left={left} right={right}")
        img_s1 = img[top:bottom, left:right]

    save_stage(img_s1, debug_dir, stem, "s1_border_removed")

    # ---- Stage 2: Fold line detection ----------------------------------- #
    gray_s1 = cv2.cvtColor(img_s1, cv2.COLOR_BGR2GRAY)

    v_folds = detect_fold_lines(gray_s1, axis='vertical')
    h_folds = detect_fold_lines(gray_s1, axis='horizontal')

    print(f"Stage 2: detected  {len(v_folds)} vertical fold(s)  "
          f"→ {len(v_folds)+1} columns")
    print(f"         detected  {len(h_folds)} horizontal fold(s) "
          f"→ {len(h_folds)+1} rows")
    for i, (c, l, r) in enumerate(v_folds):
        print(f"  V{i}: center={c}  band=[{l}, {r}]  width={r-l}px")
    for i, (c, t, b) in enumerate(h_folds):
        print(f"  H{i}: center={c}  band=[{t}, {b}]  width={b-t}px")

    if debug:
        save_fold_overlay(img_s1, v_folds, h_folds, debug_dir, stem)
        v_profile = np.median(gray_s1, axis=0).astype(float)
        h_profile = np.median(gray_s1, axis=1).astype(float)
        save_profile_image(v_profile,
                           [c for c, _, _ in v_folds], debug_dir, f"{stem}_v")
        save_profile_image(h_profile,
                           [c for c, _, _ in h_folds], debug_dir, f"{stem}_h")

    # ---- Stage 3: Fold band removal ------------------------------------- #
    img_s3 = img_s1.copy()

    if v_folds or h_folds:
        print("Stage 3: removing fold bands ...")
        for fold in v_folds:
            img_s3 = remove_fold_band(img_s3, fold, axis='vertical')
        for fold in h_folds:
            img_s3 = remove_fold_band(img_s3, fold, axis='horizontal')
    else:
        print("Stage 3: no fold lines detected — skipping.")

    save_stage(img_s3, debug_dir, stem, "s3_folds_removed")

    # ---- Final output --------------------------------------------------- #
    cv2.imwrite(output_path, img_s3, [cv2.IMWRITE_JPEG_QUALITY, 95])
    out_h, out_w = img_s3.shape[:2]
    print(f"Saved → {output_path}  ({out_w}x{out_h})")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Remove outer border and fold lines from a scanned Forstkarte.")
    parser.add_argument("input", metavar="INPUT",
                        help="Input image path (JPG or TIFF)")
    parser.add_argument("--output", "-o", default=None,
                        help="Output path (default: <stem>_clean.jpg)")
    parser.add_argument("--border-thresh", type=int, default=80, metavar="N",
                        help="Darkness threshold for border detection 0-255 (default: 80)")
    parser.add_argument("--no-border-crop", action="store_true",
                        help="Skip outer border removal")
    parser.add_argument("--debug", action="store_true",
                        help="Save additional debug images (profiles, overlay)")
    args = parser.parse_args()

    if args.output is None:
        stem, _ = os.path.splitext(args.input)
        args.output = f"{stem}_clean.jpg"

    process(
        input_path=args.input,
        output_path=args.output,
        border_thresh=args.border_thresh,
        no_border_crop=args.no_border_crop,
        debug=args.debug,
    )


if __name__ == "__main__":
    main()
