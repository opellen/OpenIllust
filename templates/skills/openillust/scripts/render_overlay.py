"""Render an SVG headlessly and composite it over its raster reference.

The agent-side half of the "Illustrator tracing" loop: author SVG -> render ->
look at the overlay -> self-correct before showing the user.

Output is a single 3-panel PNG: [reference | svg render | 50/50 overlay].

Usage:
  python render_overlay.py --svg assets/icons/tb_select.svg \
      --ref assets/refs/tb_select/reference.png --out overlay.png [--size 512]

Requires Microsoft Edge or Chrome (headless screenshot). Pure PIL otherwise.
"""
import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw

BROWSERS = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
]


def find_browser():
    for p in BROWSERS:
        if Path(p).exists():
            return p
    sys.exit("no Edge/Chrome found for headless rendering")


def render_svg(svg_path: Path, size: int) -> Image.Image:
    browser = find_browser()
    with tempfile.TemporaryDirectory() as td:
        shot = Path(td) / "shot.png"
        profile = Path(td) / "profile"  # isolated profile: never clashes with a running browser
        cmd = [
            browser, "--headless=new", "--disable-gpu", "--no-first-run",
            "--no-default-browser-check", f"--user-data-dir={profile}",
            f"--window-size={size},{size}", f"--screenshot={shot}",
            svg_path.resolve().as_uri(),
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if not shot.exists():
            sys.exit("headless screenshot failed: %s" % (res.stderr or res.stdout))
        return Image.open(shot).convert("RGB").copy()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--svg", required=True)
    ap.add_argument("--ref", help="raster reference to compare against (optional)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--size", type=int, default=512)
    ap.add_argument("--ref-opacity", type=float, default=0.5,
                    help="reference weight in the overlay panel (0..1)")
    ap.add_argument("--zoom", metavar="X0,Y0,X1,Y1",
                    help="crop this canvas-coordinate box from every panel and "
                         "magnify 2x - for part-level junction inspection")
    args = ap.parse_args()

    size = args.size
    svg_img = render_svg(Path(args.svg), size)

    panels = []
    labels = []
    if args.ref:
        ref_img = Image.open(args.ref).convert("RGB").resize((size, size), Image.LANCZOS)
        overlay = Image.blend(svg_img, ref_img, args.ref_opacity)
        panels = [ref_img, svg_img, overlay]
        labels = ["reference", "svg render", "overlay"]
    else:
        panels = [svg_img]
        labels = ["svg render"]

    if args.zoom:
        x0, y0, x1, y1 = (max(0, min(size, int(v))) for v in args.zoom.split(","))
        panels = [p.crop((x0, y0, x1, y1)).resize(((x1 - x0) * 2, (y1 - y0) * 2),
                                                  Image.LANCZOS) for p in panels]
        labels = [f"{lb} zoom({x0},{y0})-({x1},{y1})" for lb in labels]
        size_w, size_h = (x1 - x0) * 2, (y1 - y0) * 2
    else:
        size_w = size_h = size

    pad, header = 8, 20
    sheet = Image.new("RGB", (len(panels) * (size_w + pad) + pad, size_h + header + pad),
                      (230, 230, 235))
    draw = ImageDraw.Draw(sheet)
    for i, (panel, label) in enumerate(zip(panels, labels)):
        x = pad + i * (size_w + pad)
        draw.text((x + 2, 4), label, fill=(60, 60, 70))
        sheet.paste(panel, (x, header))
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    sheet.save(args.out)
    print(f"wrote {args.out} ({sheet.size[0]}x{sheet.size[1]})")


if __name__ == "__main__":
    main()
