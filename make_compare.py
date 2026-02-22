#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["pillow"]
# ///
"""
make_compare.py — Build a self-contained compare/ viewer.

Compresses debug images from each pipeline into compare/images/
and writes compare/index.html for side-by-side review.

Usage:
    uv run make_compare.py [--dir map-images] [--quality 60] [--max-width 1200]
"""

import argparse
from pathlib import Path

from PIL import Image

Image.MAX_IMAGE_PIXELS = None  # large maps

STEMS = [
    "1085149331_000001#0002", "1085149331_000002#0002", "1085149331_000003#0002",
    "1085149331_000004#0002", "1085149331_000005#0002", "1085149331_000006#0002",
    "1085149331_000007#0002", "1085149331_000008#0002", "1085149331_000009#0002",
    "1085149331_000011#0002", "1085149331_000012#0002", "1085149331_000017#0002",
    "1085149331_000018#0002", "1085149331_000019#0002", "1085149331_000021#0002",
    "1085149331_000022#0002", "1085149331_000023#0002", "1085149331_000024#0002",
    "1085149331_000025#0002", "1085149331_000026#0002", "1085149331_000027#0002",
    "1085149331_000029#0002", "1085149331_000030#0002", "1085149331_000031#0002",
    "1085149331_000032#0002", "1085149331_000033#0002", "1085149331_000034#0002",
    "1085149331_000035#0002", "1085149331_000036#0002", "1085149331_000037#0002",
    "1085149331_000039#0002", "1085149331_000041#0002", "1085149331_000042#0002",
    "1085149331_000044#0002", "1085149331_000045#0002", "1085149331_000046#0002",
    "1085149331_000047#0002", "1085149331_000048#0002", "1085149331_000050#0002",
    "1085149331_000051#0002", "1085149331_000059#0002", "1085149331_000060#0002",
    "1085149331_000108#0002", "1085149331_000117#0002", "1085149331_000119#0002",
    "3057-4096-max", "Jena-03-Gem1", "Weimar-64-VW-3#2",
]


def compress(src: Path, dst: Path, max_width: int, quality: int) -> bool:
    if not src.exists():
        return False
    img = Image.open(src).convert("RGB")
    if img.width > max_width:
        ratio = max_width / img.width
        img = img.resize((max_width, int(img.height * ratio)), Image.LANCZOS)
    img.save(dst, "JPEG", quality=quality, optimize=True)
    kb_in  = src.stat().st_size // 1024
    kb_out = dst.stat().st_size // 1024
    print(f"  {src.name} → {dst.name}  ({kb_in} KB → {kb_out} KB)")
    return True


HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<title>Fold Detection Comparison</title>
<style>
  body {{ font-family: monospace; background: #111; color: #eee; margin: 0; padding: 16px; }}
  h1 {{ font-size: 1rem; color: #aaa; margin-bottom: 16px; }}
  .grid {{ display: grid; grid-template-columns: 180px 1fr 1fr; gap: 2px; }}
  .header {{ display: contents; }}
  .header > div {{ background: #222; padding: 8px; font-weight: bold; color: #888; font-size: 0.75rem; }}
  .row {{ display: contents; }}
  .row:hover > div {{ background: #1a1a2e; }}
  .label {{ background: #1a1a1a; padding: 8px 10px; display: flex; align-items: center;
             font-size: 0.68rem; word-break: break-all; color: #ccc; }}
  .cell {{ background: #1a1a1a; padding: 4px; }}
  .cell img {{ width: 100%; height: auto; display: block; cursor: zoom-in; }}
  .missing {{ background: #1a1a1a; padding: 8px; color: #444; font-size: 0.7rem;
               display: flex; align-items: center; justify-content: center; }}
  #lb {{ display:none; position:fixed; inset:0; background:rgba(0,0,0,.93);
          z-index:999; align-items:center; justify-content:center; }}
  #lb.open {{ display:flex; }}
  #lb img {{ max-width:96vw; max-height:96vh; object-fit:contain; }}
  #lb-label {{ position:fixed; bottom:12px; left:50%; transform:translateX(-50%);
                background:rgba(0,0,0,.7); padding:4px 12px; border-radius:4px;
                font-size:0.75rem; color:#ccc; }}
</style>
</head>
<body>
<h1>Fold Detection Comparison — stitch.py (detected_lines) vs stitch_tiles.py (fold_overlay) &nbsp;|&nbsp; {n} images</h1>
<div class="grid">
  <div class="header">
    <div>Image</div>
    <div>stitch.py &rarr; detected_lines</div>
    <div>stitch_tiles.py &rarr; fold_overlay</div>
  </div>
{rows}
</div>
<div id="lb"><img id="lb-img" src="" alt=""><div id="lb-label"></div></div>
<script>
function openLb(src, lbl) {{
  document.getElementById('lb-img').src = src;
  document.getElementById('lb-label').textContent = lbl;
  document.getElementById('lb').classList.add('open');
}}
document.getElementById('lb').addEventListener('click', () =>
  document.getElementById('lb').classList.remove('open'));
document.addEventListener('keydown', e => {{
  if (e.key === 'Escape') document.getElementById('lb').classList.remove('open');
}});
</script>
</body>
</html>
"""

ROW_TEMPLATE = """\
  <div class="row">
    <div class="label">{stem}</div>
    {cell_a}
    {cell_b}
  </div>"""

CELL_OK  = '<div class="cell"><img src="{src}" alt="{lbl}" title="{lbl}" onclick="openLb(\'{src}\',\'{lbl}\')"></div>'
CELL_ERR = '<div class="missing">(not found)</div>'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", default="map-images")
    parser.add_argument("--quality", type=int, default=60)
    parser.add_argument("--max-width", type=int, default=1200)
    args = parser.parse_args()

    img_dir     = Path(args.dir)
    compare_dir = img_dir / "compare"
    images_dir  = compare_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    print(f"Output: {compare_dir}/\n")

    rows = []
    found = 0

    for stem in STEMS:
        safe = stem.replace("#", "_")  # filesystem-safe name for output

        # Source paths
        src_dl = img_dir / f"{stem}_debug" / "detected_lines.png"
        src_fo = img_dir / f"{stem}_stitch_debug" / f"{stem}_fold_overlay.jpg"

        # Dest paths
        dst_dl = images_dir / f"{safe}_detected_lines.jpg"
        dst_fo = images_dir / f"{safe}_fold_overlay.jpg"

        print(f"[{stem}]")
        ok_dl = compress(src_dl, dst_dl, args.max_width, args.quality)
        ok_fo = compress(src_fo, dst_fo, args.max_width, args.quality)

        # HTML paths (relative to compare/)
        rel_dl = f"images/{safe}_detected_lines.jpg"
        rel_fo = f"images/{safe}_fold_overlay.jpg"

        cell_a = CELL_OK.format(src=rel_dl, lbl=f"{stem} — detected_lines") if ok_dl else CELL_ERR
        cell_b = CELL_OK.format(src=rel_fo, lbl=f"{stem} — fold_overlay")   if ok_fo else CELL_ERR

        rows.append(ROW_TEMPLATE.format(stem=stem, cell_a=cell_a, cell_b=cell_b))
        if ok_dl or ok_fo:
            found += 1

    html = HTML_TEMPLATE.format(n=found, rows="\n".join(rows))
    out_html = compare_dir / "index.html"
    out_html.write_text(html, encoding="utf-8")
    print(f"\nWrote {out_html}")


if __name__ == "__main__":
    main()
