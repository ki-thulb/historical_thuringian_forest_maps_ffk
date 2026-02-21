"""
Stage 1 — Outer border removal.

Detects and crops the dark scanning border that surrounds the map content.
"""

import numpy as np


def detect_content_bbox(gray: np.ndarray, dark_thresh: int = 80,
                        edge_ratio: float = 0.60, margin: int = 10) -> tuple:
    """
    Scan inward from each edge and find where the dark scanning border ends.

    A row/column is considered "border" when more than `edge_ratio` of its
    pixels are darker than `dark_thresh`. Scanning stops at the first
    row/column that no longer meets this criterion.

    Returns (top, bottom, left, right) crop coordinates.
    """
    h, w = gray.shape
    max_scan = 0.15  # never scan more than 15 % in from any edge

    def find_edge(profile_fn, length, reverse=False):
        rng = range(int(length * max_scan))
        if reverse:
            rng = range(length - 1, length - int(length * max_scan) - 1, -1)
        for i in rng:
            strip = profile_fn(i)
            if np.mean(strip < dark_thresh) < edge_ratio:
                return i
        return 0 if not reverse else length - 1

    top    = find_edge(lambda i: gray[i, :], h, reverse=False)
    bottom = find_edge(lambda i: gray[i, :], h, reverse=True)
    left   = find_edge(lambda i: gray[:, i], w, reverse=False)
    right  = find_edge(lambda i: gray[:, i], w, reverse=True)

    # Safety margin (inward) to eliminate residual border pixels
    top    = min(top    + margin, h // 2)
    bottom = max(bottom - margin, h // 2 + 1)
    left   = min(left   + margin, w // 2)
    right  = max(right  - margin, w // 2 + 1)

    return top, bottom, left, right
