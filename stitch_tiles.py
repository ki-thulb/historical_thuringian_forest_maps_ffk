#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = [
#     "opencv-python-headless",
#     "numpy",
# ]
# ///
"""
stitch_tiles.py — Step 1b of the Forstkarten pipeline.

Splits the map at fold lines, aligns adjacent tiles with SIFT feature
matching + RANSAC homography, and blends them into a seamless output.

Requires clean_map.py to have been run first (uses the border-cropped
image from the debug directory as input, or any pre-cropped image).

Usage:
    uv run stitch_tiles.py INPUT [--output OUTPUT]
                           [--strip-width N] [--blend-width N] [--debug]

    INPUT can be the original scan or the s1_border_removed output.
"""

import argparse
import os
import sys

import cv2
import numpy as np

from stages.border_removal import detect_content_bbox
from stages.fold_detection import detect_fold_lines, detect_fold_lines_hough
from stages.stitcher import stitch
from stages.debug_utils import save_fold_overlay


def process(input_path: str, output_path: str,
            border_thresh: int, debug: bool,
            detection_method: str = 'legacy') -> None:

    print(f"Loading {input_path} ...")
    img = cv2.imread(input_path)
    if img is None:
        sys.exit(f"Error: could not read image: {input_path}")

    h, w = img.shape[:2]
    print(f"  Size: {w}x{h}")

    stem      = os.path.splitext(os.path.basename(input_path))[0]
    debug_dir = os.path.join(os.path.dirname(os.path.abspath(input_path)),
                             f"{stem}_stitch_debug")
    os.makedirs(debug_dir, exist_ok=True)
    print(f"  Debug outputs → {debug_dir}/")

    # ---- Stage 1: Border crop ------------------------------------------ #
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    top, bottom, left, right = detect_content_bbox(gray, dark_thresh=border_thresh)
    img_cropped = img[top:bottom, left:right]
    print(f"  Border crop: {w}x{h} → {img_cropped.shape[1]}x{img_cropped.shape[0]}")

    # ---- Stage 2: Fold line detection ----------------------------------- #
    gray_cropped = cv2.cvtColor(img_cropped, cv2.COLOR_BGR2GRAY)
    detect_fn = detect_fold_lines_hough if detection_method == 'hough' else detect_fold_lines
    if detection_method == 'hough':
        print("  [detection] Using Hough pipeline")
    v_folds = detect_fn(gray_cropped, axis='vertical')
    h_folds = detect_fn(gray_cropped, axis='horizontal')

    print(f"  Vertical folds:   {[c for c,_,_ in v_folds]}")
    print(f"  Horizontal folds: {[c for c,_,_ in h_folds]}")

    if debug:
        save_fold_overlay(img_cropped, v_folds, h_folds, debug_dir, stem)

    # ---- Stage 3: Straighten + stitch ---------------------------------- #
    print("Straightening and stitching ...")
    result = stitch(img_cropped, v_folds, h_folds, verbose=True)

    # ---- Save output ---------------------------------------------------- #
    cv2.imwrite(output_path, result, [cv2.IMWRITE_JPEG_QUALITY, 95])
    out_h, out_w = result.shape[:2]
    print(f"Saved → {output_path}  ({out_w}x{out_h})")


def main():
    parser = argparse.ArgumentParser(
        description="Straighten fold curves and stitch a scanned Forstkarte.")
    parser.add_argument("input", metavar="INPUT",
                        help="Input image path (JPG or TIFF)")
    parser.add_argument("--output", "-o", default=None,
                        help="Output path (default: <stem>_stitched.jpg)")
    parser.add_argument("--border-thresh", type=int, default=80, metavar="N",
                        help="Border detection threshold (default: 80)")
    parser.add_argument("--debug", action="store_true",
                        help="Save fold overlay debug image")
    parser.add_argument("--detection-method", choices=["legacy", "hough"],
                        default="legacy", metavar="METHOD",
                        help="Fold detection algorithm: legacy (matched-filter) "
                             "or hough (edge-density + Hough validation)")
    args = parser.parse_args()

    if args.output is None:
        stem, _ = os.path.splitext(args.input)
        args.output = f"{stem}_stitched.jpg"

    process(
        input_path=args.input,
        output_path=args.output,
        border_thresh=args.border_thresh,
        debug=args.debug,
        detection_method=args.detection_method,
    )


if __name__ == "__main__":
    main()
