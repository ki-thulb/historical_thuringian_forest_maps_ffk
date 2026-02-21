# /// script
# requires-python = ">=3.9"
# dependencies = ["numpy", "pillow"]
# ///
import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None
img = Image.open("map-images/1085149331_000117#0002.jpg").convert("L")
gray = np.array(img)

print(f"Image shape: {gray.shape}")

problematic_x = [(138, 1656), (6530, 7817), (6193, 6451), (0, 84), (7874, 7980)]
for s, e in problematic_x:
    m = np.mean(gray[:, s:e])
    print(f"  cols {s}-{e} width={e-s}: mean={m:.1f}")

problematic_y = [(4099, 4693), (5035, 5559), (1311, 1483), (1559, 1784), (0, 78)]
for s, e in problematic_y:
    m = np.mean(gray[s:e, :])
    print(f"  rows {s}-{e} height={e-s}: mean={m:.1f}")
