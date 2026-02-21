"""
Stage 2 — Fold line detection.

Locates the horizontal and vertical fold/stitch bands in a cropped map image.

Two detectors are provided:

  detect_fold_lines()       — matched-filter (local-contrast) on a 1-D profile.
  detect_fold_lines_hough() — edge-density profiling + Hough-line validation.
                              More robust on multi-colour maps with fragmented
                              or partially-occluded fold lines.

Both return the same list[(center, left_edge, right_edge)] contract.
"""

import math

import cv2
import numpy as np


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _find_peaks(signal: np.ndarray, min_prominence: float,
                min_distance: int = 50) -> list:
    """Local-maxima peak finder with prominence and distance constraints."""
    peaks = []
    n = len(signal)
    for i in range(1, n - 1):
        if signal[i] >= signal[i - 1] and signal[i] >= signal[i + 1]:
            left_min  = np.min(signal[max(0, i - min_distance):i])
            right_min = np.min(signal[i + 1:min(n, i + min_distance)])
            prominence = signal[i] - max(left_min, right_min)
            if prominence >= min_prominence:
                peaks.append(i)

    # Suppress duplicates within min_distance (keep the first / leftmost)
    filtered = []
    for p in peaks:
        if not filtered or p - filtered[-1] >= min_distance:
            filtered.append(p)
    return filtered


def _matched_filter_score(profile: np.ndarray,
                           fold_half_width: int = 25,
                           gap: int = 10,
                           neighbor_width: int = 80) -> np.ndarray:
    """
    Vectorised O(n) local-contrast score via cumulative sums.

    At each position i the score = |mean(band) - mean(neighbours)|, where
    band   = profile[i-hw : i+hw]
    neighbours = profile[i-hw-gap-nw : i-hw-gap]  ∪  profile[i+hw+gap : i+hw+gap+nw]
    """
    n  = len(profile)
    cs = np.concatenate([[0.0], np.cumsum(profile)])
    idx = np.arange(n)
    hw, g, nw = fold_half_width, gap, neighbor_width

    c_s = np.clip(idx - hw,          0, n)
    c_e = np.clip(idx + hw,          0, n)
    l_s = np.clip(idx - hw - g - nw, 0, n)
    l_e = np.clip(idx - hw - g,      0, n)
    r_s = np.clip(idx + hw + g,      0, n)
    r_e = np.clip(idx + hw + g + nw, 0, n)

    c_len  = np.maximum(c_e - c_s, 1)
    c_mean = (cs[c_e] - cs[c_s]) / c_len

    n_len  = (l_e - l_s) + (r_e - r_s)
    n_sum  = (cs[l_e] - cs[l_s]) + (cs[r_e] - cs[r_s])
    n_mean = np.where(n_len > 0, n_sum / np.maximum(n_len, 1), c_mean)

    return np.abs(c_mean - n_mean)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def detect_fold_lines(gray: np.ndarray,
                      axis: str = 'vertical',
                      fold_half_width: int = 25,
                      gap: int = 10,
                      neighbor_width: int = 80,
                      min_distance_frac: float = 0.12,
                      edge_guard_frac: float = 0.10,
                      prominence_std_mult: float = 2.5) -> list:
    """
    Detect fold line positions along the given axis.

    Parameters
    ----------
    gray               : grayscale image (uint8)
    axis               : 'vertical' (constant-x bands) or 'horizontal' (constant-y)
    fold_half_width    : half-width of the fold band used by the matched filter (px)
    gap                : gap between band and neighbour windows (px)
    neighbor_width     : width of each neighbour window (px)
    min_distance_frac  : minimum spacing between fold lines as fraction of image size
    edge_guard_frac    : fraction of image size masked at each edge
    prominence_std_mult: peak must exceed mean + N*std of the score signal

    Returns
    -------
    List of (center, left_edge, right_edge) tuples, one per detected fold line.
    """
    h, w = gray.shape

    # Use a central strip to avoid legend areas (typically top-left corner).
    # For vertical folds: compute column profile from the middle horizontal band
    # so the legend's bright rows don't bias the detection leftward.
    # For horizontal folds: compute row profile from the middle vertical band.
    STRIP_LO, STRIP_HI = 0.35, 0.65
    if axis == 'vertical':
        lo, hi = int(h * STRIP_LO), int(h * STRIP_HI)
        profile = np.median(gray[lo:hi, :], axis=0).astype(float)
    else:
        lo, hi = int(w * STRIP_LO), int(w * STRIP_HI)
        profile = np.median(gray[:, lo:hi], axis=1).astype(float)

    n            = len(profile)
    min_distance = max(50, int(n * min_distance_frac))
    guard        = max(10, int(n * edge_guard_frac))

    score = _matched_filter_score(profile, fold_half_width, gap, neighbor_width)
    score[:guard]  = 0.0
    score[-guard:] = 0.0

    inner             = score[guard:-guard]
    prominence_thresh = np.mean(inner) + prominence_std_mult * np.std(inner)

    peaks = _find_peaks(score, min_prominence=prominence_thresh,
                        min_distance=min_distance)

    # Refine each peak: the matched filter peaks at the contrast edge, but the
    # actual fold center is the darkest (most compressed) column/row nearby.
    # Snap to the brightness minimum within a generous search window.
    REFINE_HALF = 150
    refined_peaks = []
    for p in peaks:
        lo = max(0, p - REFINE_HALF)
        hi = min(n,  p + REFINE_HALF)
        refined = lo + int(np.argmin(profile[lo:hi]))
        refined_peaks.append(refined)

    fold_lines = []
    for p in refined_peaks:
        threshold = score[p] * 0.30
        left = p
        while left > 0 and score[left] > threshold:
            left -= 1
        right = p
        while right < n - 1 and score[right] > threshold:
            right += 1
        left  = min(left,  p - fold_half_width)
        right = max(right, p + fold_half_width)
        fold_lines.append((p, max(0, left), min(n - 1, right)))

    return fold_lines


def detect_fold_lines_hough(gray: np.ndarray,
                             axis: str = 'vertical',
                             min_distance_frac: float = 0.12,
                             edge_guard_frac: float = 0.10,
                             prominence_std_mult: float = 2.5,
                             strip_half: int = 80,
                             hough_threshold: int = 30,
                             hough_min_line_frac: float = 0.15,
                             hough_max_gap_frac: float = 0.20,
                             hough_angle_tol_deg: float = 5.0,
                             band_brightness_margin: int = 20,
                             band_half_min: int = 25) -> list:
    """
    Detect fold line positions using edge-density profiling + Hough validation.

    Robust on multi-colour maps where simple brightness argmin drifts toward
    dark content (forest, water) rather than the physical crease.

    Only fold segments that are **actually visible** are used — no missing
    parts are inferred or extrapolated.

    Parameters
    ----------
    gray                  : grayscale image (uint8)
    axis                  : 'vertical' or 'horizontal'
    min_distance_frac     : minimum fold spacing as fraction of image dimension
    edge_guard_frac       : fraction masked at each edge (avoids border artefacts)
    prominence_std_mult   : peak threshold = mean + N*std of density signal
    strip_half            : half-width of Canny strip around each candidate (px)
    hough_threshold       : HoughLinesP accumulator threshold
    hough_min_line_frac   : minimum accepted segment length as fraction of fold length
    hough_max_gap_frac    : max gap to bridge within one segment (fraction of fold length)
    hough_angle_tol_deg   : angular tolerance around perpendicular direction (degrees)
    band_half_min         : minimum half-width of the output band (px)

    Returns
    -------
    List of (center, left_edge, right_edge) tuples — same contract as detect_fold_lines().
    """
    h, w = gray.shape

    # ------------------------------------------------------------------
    # Step 1 & 2: Candidate peaks via matched-filter on brightness profile.
    # The matched filter (local contrast) detects "dark band surrounded by
    # lighter content" — the exact fold signature — and is already robust
    # on multicolour maps (uses central strip + median).  We reuse it here
    # to get reliable candidates, then validate/refine with Hough in Step 4.
    # ------------------------------------------------------------------
    STRIP_LO, STRIP_HI = 0.35, 0.65
    if axis == 'vertical':
        lo_s, hi_s = int(h * STRIP_LO), int(h * STRIP_HI)
        profile  = np.median(gray[lo_s:hi_s, :], axis=0).astype(float)
        dim_along = h
    else:
        lo_s, hi_s = int(w * STRIP_LO), int(w * STRIP_HI)
        profile  = np.median(gray[:, lo_s:hi_s], axis=1).astype(float)
        dim_along = w

    n            = len(profile)
    min_distance = max(50, int(n * min_distance_frac))
    guard        = max(10, int(n * edge_guard_frac))

    score = _matched_filter_score(profile)
    score[:guard]  = 0.0
    score[-guard:] = 0.0

    inner             = score[guard:-guard]
    prominence_thresh = np.mean(inner) + prominence_std_mult * np.std(inner)

    candidate_peaks = _find_peaks(score,
                                   min_prominence=prominence_thresh,
                                   min_distance=min_distance)

    if not candidate_peaks:
        return []

    # ------------------------------------------------------------------
    # Step 3: Build Canny edge image for Hough validation.
    # Bilateral filter first to reduce texture noise while keeping crease
    # edges sharp.
    # ------------------------------------------------------------------
    blurred = cv2.bilateralFilter(gray, d=9, sigmaColor=50, sigmaSpace=50)

    # ------------------------------------------------------------------
    # Step 4: Hough validation + position refinement
    # For each candidate, check that actual near-perpendicular line
    # segments exist in the Canny image.  Segments from legends / text
    # boxes are oblique or horizontal and fail the angle filter.
    # Refined center = median midpoint of all accepted segments.
    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    # Step 4: Hough validation + position refinement per candidate.
    # ------------------------------------------------------------------
    canny = cv2.Canny(blurred, threshold1=30, threshold2=90)

    min_line_len = max(20, int(dim_along * hough_min_line_frac))
    max_line_gap = max(10, int(dim_along * hough_max_gap_frac))

    # Angle target: atan2(|dy|, |dx|) → 90° for vertical, 0° for horizontal
    angle_target = 90.0 if axis == 'vertical' else 0.0

    refined_peaks = []
    for p in candidate_peaks:
        if axis == 'vertical':
            lo  = max(0, p - strip_half)
            hi  = min(w, p + strip_half)
            strip_canny = canny[:, lo:hi]
        else:
            lo  = max(0, p - strip_half)
            hi  = min(h, p + strip_half)
            strip_canny = canny[lo:hi, :]

        lines = cv2.HoughLinesP(
            strip_canny,
            rho=1,
            theta=math.pi / 180.0,
            threshold=hough_threshold,
            minLineLength=min_line_len,
            maxLineGap=max_line_gap,
        )

        if lines is None:
            continue    # no line evidence → not a real fold

        accepted = []
        for x1, y1, x2, y2 in lines[:, 0, :]:
            dx, dy = float(x2 - x1), float(y2 - y1)
            if dx == 0 and dy == 0:
                continue
            angle = math.degrees(math.atan2(abs(dy), abs(dx)))
            if abs(angle - angle_target) <= hough_angle_tol_deg:
                # Convert strip-local coord back to full-image coord
                mid = ((x1 + x2) / 2.0 if axis == 'vertical'
                       else (y1 + y2) / 2.0) + lo
                accepted.append(mid)

        if not accepted:
            continue    # lines found but none perpendicular to axis

        refined_peaks.append(int(round(float(np.median(accepted)))))

    if not refined_peaks:
        return []

    # ------------------------------------------------------------------
    # Step 5: Band edge detection using matched-filter score on the
    # brightness profile.  The density profile (edge sum) is directional
    # and sharp; the brightness profile argmin is used only to pin the
    # center, while the matched-filter score defines the band width.
    # This reuses the same approach as detect_fold_lines() so band widths
    # are consistent and do not bleed to the image boundary.
    # ------------------------------------------------------------------
    if axis == 'vertical':
        brightness_profile = np.median(gray, axis=0).astype(float)
    else:
        brightness_profile = np.median(gray, axis=1).astype(float)

    mf_score = _matched_filter_score(brightness_profile,
                                      fold_half_width=band_half_min,
                                      gap=10,
                                      neighbor_width=80)

    fold_lines = []
    for p in refined_peaks:
        p = max(0, min(n - 1, p))

        threshold = max(mf_score[p] * 0.30, 1e-6)
        left = p
        while left > 0 and mf_score[left] > threshold:
            left -= 1
        right = p
        while right < n - 1 and mf_score[right] > threshold:
            right += 1

        left  = min(left,  p - band_half_min)
        right = max(right, p + band_half_min)
        fold_lines.append((p, max(0, left), min(n - 1, right)))

    return fold_lines
