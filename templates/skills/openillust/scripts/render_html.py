"""Render an agent-authored HTML/CSS page at an exact pixel size.

The deterministic half of the compose route: the agent authors an HTML/CSS
page (scripts never draw) and this script screenshots it headlessly at exact
dimensions, guarded against blank/flake renders. Layout and typography live
in the HTML, not here.

Usage:
  python render_html.py --html page.html --size 1760x320 --out out.png \
      [--webp out.webp] [--min-colors 50] [--retries 3]

Requires Microsoft Edge or Chrome (headless screenshot, via
render_overlay.find_browser). Pure Pillow otherwise.
"""
import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image

from render_overlay import find_browser


def parse_size(spec: str) -> tuple[int, int]:
    m = re.fullmatch(r"(\d+)x(\d+)", spec)
    if not m:
        sys.exit(f"--size must be WxH with positive integers, got {spec!r}")
    w, h = int(m.group(1)), int(m.group(2))
    if w <= 0 or h <= 0:
        sys.exit(f"--size must be WxH with positive integers, got {spec!r}")
    return w, h


def shoot(html_path: Path, w: int, h: int, browser: str, min_colors: int,
          retries: int) -> Image.Image:
    for _ in range(retries):
        with tempfile.TemporaryDirectory() as td:
            shot = Path(td) / "shot.png"
            profile = Path(td) / "profile"  # fresh profile per attempt
            cmd = [
                browser, "--headless=new", "--disable-gpu", "--no-first-run",
                "--no-default-browser-check", f"--user-data-dir={profile}",
                "--hide-scrollbars", f"--window-size={w},{h}", f"--screenshot={shot}",
                html_path.resolve().as_uri(),
            ]
            subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if not shot.exists():
                continue
            img = Image.open(shot).convert("RGB").copy()
        colors = img.getcolors(maxcolors=1 << 20)
        if colors and len(colors) > min_colors:  # not a blank/uniform shot
            return img
    sys.exit(f"no valid render for {html_path} after {retries} attempt(s): "
              f"shot never exceeded {min_colors} distinct colors (blank-shot guard)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--html", required=True, help="HTML file to render")
    ap.add_argument("--size", required=True, help="WxH in pixels, e.g. 1760x320")
    ap.add_argument("--out", required=True, help="output PNG path")
    ap.add_argument("--webp", help="also save a lossless WEBP here")
    ap.add_argument("--min-colors", type=int, default=50,
                     help="distinct-color count the render must exceed (blank-shot guard)")
    ap.add_argument("--retries", type=int, default=3,
                     help="render attempts before giving up")
    args = ap.parse_args()

    html_path = Path(args.html)
    if not html_path.exists():
        sys.exit(f"HTML file not found: {html_path}")
    w, h = parse_size(args.size)

    browser = find_browser()
    img = shoot(html_path, w, h, browser, args.min_colors, args.retries)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, "PNG")
    actual = Image.open(out).size
    if actual != (w, h):
        sys.exit(f"rendered PNG is {actual[0]}x{actual[1]}, requested {w}x{h}")
    print(f"wrote {out} ({w}x{h})")

    if args.webp:
        webp = Path(args.webp)
        webp.parent.mkdir(parents=True, exist_ok=True)
        img.save(webp, "WEBP", lossless=True)
        print(f"wrote {webp} ({w}x{h})")


if __name__ == "__main__":
    main()
