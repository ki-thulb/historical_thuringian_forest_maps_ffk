# /// script
# requires-python = ">=3.9"
# dependencies = [
#     "numpy",
#     "pillow",
#     "matplotlib",
#     "scipy",
# ]
# ///

#%%
import argparse
from pathlib import Path
import numpy as np
from PIL import Image
import matplotlib.pyplot as plt
from scipy.ndimage import gaussian_filter1d


def load_image_grayscale(path):

    Image.MAX_IMAGE_PIXELS = None  # disable decompression bomb limit for large maps
    img_rgb = Image.open(path)
    img_gray = img_rgb.copy().convert("L")  # convert to grayscale

    return np.array(img_gray), np.array(img_rgb)

def compute_projection_histograms(gray_img):
    # switched to standard dev -> should be small if grey values are similar
    x_hist = np.std(gray_img, axis=0)  # columns
    y_hist = np.std(gray_img, axis=1)  # rows
    return x_hist, y_hist

# ----------------------------
# Auto threshold via Otsu
# ----------------------------
def _otsu_threshold(values):
    """Compute Otsu's threshold for a 1D array of floats."""
    hist, bin_edges = np.histogram(values, bins=256)
    bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2
    hist = hist.astype(float) / hist.sum()

    total_mu = np.sum(hist * bin_centers)
    best_thresh = bin_centers[0]
    best_bcv = 0.0
    w0, mu0_sum = 0.0, 0.0

    for i in range(len(hist)):
        w0 += hist[i]
        mu0_sum += hist[i] * bin_centers[i]
        w1 = 1.0 - w0
        if w0 < 1e-10 or w1 < 1e-10:
            continue
        mu0 = mu0_sum / w0
        mu1 = (total_mu - mu0_sum) / w1
        bcv = w0 * w1 * (mu0 - mu1) ** 2
        if bcv > best_bcv:
            best_bcv = bcv
            best_thresh = bin_centers[i]

    return best_thresh

def plot_histograms(x_hist, y_hist, x_smooth, y_smooth, x_thresh, y_thresh, debug_dir):
    _, axes = plt.subplots(2, 1, figsize=(10, 6))

    axes[0].plot(x_hist, alpha=0.5, label="Raw")
    axes[0].plot(x_smooth, label="Smoothed")
    axes[0].axhline(x_thresh, color="r", linestyle="--", label=f"Threshold ({x_thresh:.1f})")
    axes[0].set_title("X Projection Histogram (Vertical Lines)")
    axes[0].legend()

    axes[1].plot(y_hist, alpha=0.5, label="Raw")
    axes[1].plot(y_smooth, label="Smoothed")
    axes[1].axhline(y_thresh, color="r", linestyle="--", label=f"Threshold ({y_thresh:.1f})")
    axes[1].set_title("Y Projection Histogram (Horizontal Lines)")
    axes[1].legend()

    plt.tight_layout()
    plt.savefig(debug_dir / "histograms.png", dpi=100)
    plt.close()

# ----------------------------
# Peak Window Detection
# ----------------------------
def find_line_windows(hist, sigma=5, min_width=3):
    """
    Detect line windows in projection histogram using automatic Otsu threshold.

    Parameters:
        sigma: smoothing factor
        min_width: minimum consecutive width
    """

    smooth_hist = gaussian_filter1d(hist.astype(float), sigma=sigma)
    threshold = _otsu_threshold(smooth_hist)
    mask = smooth_hist < threshold

    windows = []
    start = None
    for i, val in enumerate(mask):
        if val and start is None:
            start = i
        elif not val and start is not None:
            if i - start >= min_width:
                windows.append((start, i))
            start = None

    # Handle trailing window
    if start is not None and len(mask) - start >= min_width:
        windows.append((start, len(mask)))

    return windows, smooth_hist, threshold

# ----------------------------
# Visualization
# ----------------------------
def overlay_detected_lines(gray_img, x_windows, y_windows, debug_dir):
    fig, ax = plt.subplots(figsize=(8, 8))
    ax.imshow(gray_img, cmap="gray")

    # Vertical lines (X windows)
    for (start, end) in x_windows:
        ax.axvspan(start, end, color="red", alpha=0.3)

    # Horizontal lines (Y windows)
    for (start, end) in y_windows:
        ax.axhspan(start, end, color="blue", alpha=0.3)

    ax.set_title("Detected Vertical (red) and Horizontal (blue) Lines")
    ax.axis("off")
    plt.savefig(debug_dir / "detected_lines.png", dpi=100)
    plt.close()

def crop_detected_windows(img_rgb, x_windows, y_windows):
    """
    Remove detected vertical (x_windows) and horizontal (y_windows) regions
    from the image.

    Returns:
        cropped_img
    """

    h, w = img_rgb.shape[:2]

    # Initialize masks (True = keep)
    keep_cols = np.ones(w, dtype=bool)
    keep_rows = np.ones(h, dtype=bool)

    # Remove vertical windows (columns)
    for start, end in x_windows:
        keep_cols[start:end] = False

    # Remove horizontal windows (rows)
    for start, end in y_windows:
        keep_rows[start:end] = False

    # Apply cropping
    cropped_img = img_rgb[np.ix_(np.where(keep_rows)[0], np.where(keep_cols)[0])]

    return cropped_img

def main(image_path):
    debug_dir = image_path.parent / (image_path.stem + "_debug")
    debug_dir.mkdir(exist_ok=True)

    gray_img, img_rgb = load_image_grayscale(image_path)

    x_hist, y_hist = compute_projection_histograms(gray_img)

    x_windows, x_smooth, x_thresh = find_line_windows(x_hist)
    y_windows, y_smooth, y_thresh = find_line_windows(y_hist)

    print("Detected vertical line windows:", x_windows)
    print("Detected horizontal line windows:", y_windows)
    print(f"Auto thresholds — x: {x_thresh:.1f}, y: {y_thresh:.1f}")

    plot_histograms(x_hist, y_hist, x_smooth, y_smooth, x_thresh, y_thresh, debug_dir)
    overlay_detected_lines(gray_img, x_windows, y_windows, debug_dir)

    cropped_img = crop_detected_windows(img_rgb, x_windows, y_windows)

    new_filename = image_path.stem + "_cropped" + image_path.suffix
    output_path = image_path.parent / new_filename
    Image.fromarray(cropped_img).save(output_path)
    print(f"Saved cropped image to: {output_path}")

    # Save cropped result debug plot
    plt.figure(figsize=(6, 6))
    plt.imshow(cropped_img, cmap="gray")
    plt.title("Image After Cropping Detected Line Windows")
    plt.axis("off")
    plt.savefig(debug_dir / "cropped_result.png", dpi=100)
    plt.close()
    print(f"Debug plots saved to: {debug_dir}/")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Detect and remove fold lines from a scanned Forstkarte.")
    parser.add_argument("input", metavar="INPUT",
                        help="Input image path (JPG or TIFF)")
    args = parser.parse_args()

    main(Path(args.input))

# %%
