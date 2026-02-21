"""
Debug helpers — save intermediate images for visual inspection.
"""

import os

import cv2
import numpy as np


def save_fold_overlay(img: np.ndarray, v_folds: list, h_folds: list,
                      debug_dir: str, name: str) -> None:
    """Draw detected fold band rectangles and centre lines on a copy of the image."""
    overlay = img.copy()
    for center, left, right in v_folds:
        cv2.rectangle(overlay, (left, 0), (right, overlay.shape[0]), (0, 0, 255), 2)
        cv2.line(overlay, (center, 0), (center, overlay.shape[0]), (0, 200, 0), 1)
    for center, top, bottom in h_folds:
        cv2.rectangle(overlay, (0, top), (overlay.shape[1], bottom), (255, 0, 0), 2)
        cv2.line(overlay, (0, center), (overlay.shape[1], center), (0, 200, 0), 1)
    path = os.path.join(debug_dir, f"{name}_fold_overlay.jpg")
    cv2.imwrite(path, overlay, [cv2.IMWRITE_JPEG_QUALITY, 80])
    print(f"  [debug] fold overlay → {path}")


def save_profile_image(profile: np.ndarray, peaks: list,
                       debug_dir: str, name: str) -> None:
    """Render a 1-D brightness profile as a small image with peak markers."""
    n     = len(profile)
    h_img = 200
    canvas = np.ones((h_img, n, 3), dtype=np.uint8) * 240
    norm   = profile - profile.min()
    if norm.max() > 0:
        norm = norm / norm.max()
    for x in range(n):
        y = h_img - 1 - int(norm[x] * (h_img - 1))
        canvas[y, x] = [0, 0, 0]
    for p in peaks:
        cv2.line(canvas, (p, 0), (p, h_img - 1), (0, 0, 200), 1)
    path = os.path.join(debug_dir, f"{name}_profile.jpg")
    cv2.imwrite(path, canvas)
    print(f"  [debug] profile → {path}")
