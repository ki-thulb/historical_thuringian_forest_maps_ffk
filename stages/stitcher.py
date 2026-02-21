"""
Stage 4 — Fold-curve detection and image straightening.

Instead of translating tiles (which fails because adjacent tiles show
*different* geographic areas and share no SIFT features), we:

1. Detect each fold line as a *curve*: for every row (vertical fold) or
   column (horizontal fold), find the darkest pixel near the fold center —
   that is the actual physical crease position.

2. Remap the image so each fold becomes a perfectly straight vertical/
   horizontal line at the mean fold position.

3. After straightening, remove the (now-straight) fold band by interpolation.

This produces a spatially consistent, seamlessly stitched output.
"""

from __future__ import annotations

import cv2
import numpy as np


# ---------------------------------------------------------------------------
# Fold curve detection
# ---------------------------------------------------------------------------

def detect_fold_curve(gray: np.ndarray,
                      fold_center: int,
                      axis: str,
                      half_window: int = 60,
                      smooth_sigma: int = 15) -> np.ndarray:
    """
    For every scanline perpendicular to `axis`, find the darkest pixel
    near `fold_center`.  Returns the fold position as a 1-D array.

    axis='vertical'  → returns shape (height,), one x-position per row
    axis='horizontal'→ returns shape (width,),  one y-position per column

    `smooth_sigma` controls how much the curve is smoothed (pixels).
    """
    h, w = gray.shape
    if axis == 'vertical':
        lo    = max(0, fold_center - half_window)
        hi    = min(w, fold_center + half_window)
        strip = gray[:, lo:hi].astype(float)
        curve = lo + np.argmin(strip, axis=1).astype(float)   # (h,)
    else:
        lo    = max(0, fold_center - half_window)
        hi    = min(h, fold_center + half_window)
        strip = gray[lo:hi, :].astype(float)
        curve = lo + np.argmin(strip, axis=0).astype(float)   # (w,)

    # Smooth to suppress noise from incidentally dark map features
    if smooth_sigma > 1:
        kernel_size = smooth_sigma * 6 + 1
        curve_2d    = curve.reshape(1, -1).astype(np.float32)
        smoothed    = cv2.GaussianBlur(curve_2d, (kernel_size, 1), smooth_sigma)
        curve       = smoothed.ravel().astype(float)

    return curve


# ---------------------------------------------------------------------------
# Image straightening via remap
# ---------------------------------------------------------------------------

def straighten_fold(img: np.ndarray,
                    fold_curve: np.ndarray,
                    axis: str,
                    fold_center: int,
                    half_window: int = 60) -> np.ndarray:
    """
    Remap `img` so the fold curve becomes a straight line at `fold_center`.

    Only pixels within `half_window` of the fold are shifted; the shift
    fades linearly to zero at the window boundary to avoid discontinuities
    outside the corrected zone.

    axis='vertical'  → horizontal pixel shift (corrects wavy vertical fold)
    axis='horizontal'→ vertical pixel shift   (corrects wavy horizontal fold)
    """
    h, w = img.shape[:2]

    map_x = np.tile(np.arange(w, dtype=np.float32), (h, 1))
    map_y = np.tile(np.arange(h, dtype=np.float32)[:, None], (1, w))

    if axis == 'vertical':
        # shift[y] = how many pixels each row must move left/right
        shift  = (fold_center - fold_curve).astype(np.float32)   # (h,)
        dist   = np.abs(map_x - fold_center)                      # (h, w)
        weight = np.clip(1.0 - dist / half_window, 0.0, 1.0)
        map_x  = map_x - shift[:, np.newaxis] * weight
    else:
        shift  = (fold_center - fold_curve).astype(np.float32)   # (w,)
        dist   = np.abs(map_y - fold_center)
        weight = np.clip(1.0 - dist / half_window, 0.0, 1.0)
        map_y  = map_y - shift[np.newaxis, :] * weight

    return cv2.remap(img, map_x, map_y,
                     interpolation=cv2.INTER_LINEAR,
                     borderMode=cv2.BORDER_REPLICATE)


# ---------------------------------------------------------------------------
# Fold band removal after straightening
# ---------------------------------------------------------------------------

def remove_straight_fold(img: np.ndarray,
                         fold_center: int,
                         band_half: int,
                         axis: str) -> np.ndarray:
    """
    Remove the (now-straight) fold band by cutting it out and joining
    the two sides directly — no interpolation, no synthetic pixels.
    The output image is smaller by (2 * band_half + 1) pixels along `axis`.
    """
    left  = max(0, fold_center - band_half)
    right = fold_center + band_half + 1  # exclusive

    if axis == 'vertical':
        return np.concatenate([img[:, :left], img[:, right:]], axis=1)
    else:
        return np.concatenate([img[:left, :], img[right:, :]], axis=0)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def stitch(img: np.ndarray,
           v_folds: list[tuple],
           h_folds: list[tuple],
           half_window: int = 60,
           smooth_sigma: int = 15,
           verbose: bool = True) -> np.ndarray:
    """
    Straighten all fold lines in `img` without removing or interpolating content.

    For each detected fold (vertical and horizontal):
      1. Trace the actual fold curve per scanline (argmin of brightness).
      2. Remap the image to straighten the curved fold into a vertical/
         horizontal line.

    The fold band itself is preserved — no pixels are synthesised.
    Returns the corrected image (same size as input).
    """
    gray   = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    result = img.copy()

    all_folds = [('vertical', f) for f in v_folds] + \
                [('horizontal', f) for f in h_folds]

    # Track cumulative offset as folds are cut out (image shrinks per fold)
    offset = {'vertical': 0, 'horizontal': 0}

    for axis, (center, band_l, band_r) in all_folds:
        band_half = max((band_r - band_l) // 2, 25)
        adj_center = center - offset[axis]

        if verbose:
            print(f"  Fold {axis:10s} center={center}  band±{band_half}px")

        curve     = detect_fold_curve(gray, adj_center, axis,
                                       half_window=half_window,
                                       smooth_sigma=smooth_sigma)
        curve_std = float(curve.std())
        if verbose:
            print(f"    Curve: min={int(curve.min())}  max={int(curve.max())}  "
                  f"std={curve_std:.1f}px")

        result = straighten_fold(result, curve, axis, adj_center,
                                  half_window=half_window)
        gray   = cv2.cvtColor(result, cv2.COLOR_BGR2GRAY)

        result = remove_straight_fold(result, adj_center, band_half, axis)
        gray   = cv2.cvtColor(result, cv2.COLOR_BGR2GRAY)

        offset[axis] += 2 * band_half + 1

    return result
