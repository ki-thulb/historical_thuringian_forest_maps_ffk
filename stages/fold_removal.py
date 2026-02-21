"""
Stage 3 — Fold band removal.

Reconstructs the fold/stitch zone by interpolating across it from both edges.
The content on either side of a fold is continuous (same sheet of paper), so
linear blending of the two boundary columns/rows gives a visually clean result.
A feather ramp at each end of the band avoids introducing new hard edges.
"""

import numpy as np


def remove_fold_band(img: np.ndarray,
                     fold_line: tuple,
                     axis: str = 'vertical',
                     feather: int = 30) -> np.ndarray:
    """
    Remove a fold/stitch band by interpolating across it from both edges.

    Parameters
    ----------
    img       : BGR image (uint8)
    fold_line : (center, left_edge, right_edge) from detect_fold_lines()
    axis      : 'vertical' or 'horizontal'
    feather   : pixels on each side where reconstruction blends back into
                the original (avoids hard boundaries at the band edges)

    Returns
    -------
    Corrected BGR image (uint8, same shape as input).
    """
    center, left, right = fold_line
    img_f  = img.astype(np.float32)
    h, w   = img_f.shape[:2]
    band_w = right - left + 1

    # Smooth feather weight: 0 at band edge → 1 in the interior
    blend    = np.ones(band_w, dtype=np.float32)
    ramp     = min(feather, band_w // 2)
    for i in range(ramp):
        alpha              = i / ramp
        blend[i]           = alpha
        blend[band_w-1-i]  = alpha

    if axis == 'vertical':
        # Boundary columns just outside the detected band
        col_l = img_f[:, max(0, left  - 1), :]        # (h, 3)
        col_r = img_f[:, min(w - 1, right + 1), :]    # (h, 3)

        # Linear interpolation across the band width
        t      = np.linspace(0.0, 1.0, band_w, dtype=np.float32)   # (band_w,)
        interp = (col_l[:, np.newaxis, :] * (1 - t)[np.newaxis, :, np.newaxis]
                + col_r[:, np.newaxis, :] *      t [np.newaxis, :, np.newaxis])

        # Blend: keep original where blend=0, use interp where blend=1
        orig   = img_f[:, left:right + 1, :]
        result = orig * (1 - blend)[np.newaxis, :, np.newaxis] \
               + interp * blend    [np.newaxis, :, np.newaxis]
        img_f[:, left:right + 1, :] = result

    else:  # horizontal
        row_t = img_f[max(0, left  - 1), :, :]        # (w, 3)
        row_b = img_f[min(h - 1, right + 1), :, :]    # (w, 3)

        t      = np.linspace(0.0, 1.0, band_w, dtype=np.float32)
        interp = (row_t[np.newaxis, :, :] * (1 - t)[:, np.newaxis, np.newaxis]
                + row_b[np.newaxis, :, :] *      t [:, np.newaxis, np.newaxis])

        orig   = img_f[left:right + 1, :, :]
        result = orig * (1 - blend)[:, np.newaxis, np.newaxis] \
               + interp * blend    [:, np.newaxis, np.newaxis]
        img_f[left:right + 1, :, :] = result

    return np.clip(img_f, 0, 255).astype(np.uint8)
