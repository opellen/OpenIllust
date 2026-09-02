"""Split a generated sprite sheet into per-icon reference PNGs.

Uses the same manifest as make_sheet_guide.py for slugs and cell order.
Each cell is cropped on a uniform grid (optionally trimmed), upscaled to at
least --min-size (Recraft's vectorize API requires >=256px; we target 512),
and saved as assets/refs/<slug>/reference.png with a provenance note.

Usage:
  python crop_sheet.py --input sheet.png --manifest manifest.txt
      --rows 3 --cols 3 [--trim 0.02] [--min-size 512]
      [--refs-dir assets/refs] [--prompt prompt.txt]
"""
import argparse
from datetime import date
from pathlib import Path

from PIL import Image

from make_sheet_guide import parse_manifest


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="the generated sheet PNG")
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--rows", type=int, required=True)
    ap.add_argument("--cols", type=int, required=True)
    ap.add_argument("--trim", type=float, default=0.02,
                    help="fraction of each cell trimmed on every side (grid-line bleed)")
    ap.add_argument("--min-size", type=int, default=512)
    ap.add_argument("--refs-dir", default="assets/refs")
    ap.add_argument("--prompt", help="prompt.txt used for the sheet (recorded in provenance)")
    args = ap.parse_args()

    cells = parse_manifest(args.manifest)
    if len(cells) != args.rows * args.cols:
        raise SystemExit(f"manifest has {len(cells)} cells; grid needs {args.rows * args.cols}")

    sheet = Image.open(args.input).convert("RGB")
    W, H = sheet.size
    cw, ch = W / args.cols, H / args.rows
    refs = Path(args.refs_dir)
    today = date.today().isoformat()

    for i, (slug, title, desc) in enumerate(cells):
        r, c = divmod(i, args.cols)
        tx, ty = cw * args.trim, ch * args.trim
        box = (int(c * cw + tx), int(r * ch + ty),
               int((c + 1) * cw - tx), int((r + 1) * ch - ty))
        cell = sheet.crop(box)
        if min(cell.size) < args.min_size:
            k = args.min_size / min(cell.size)
            cell = cell.resize((round(cell.size[0] * k), round(cell.size[1] * k)),
                               Image.LANCZOS)
        out = refs / slug
        out.mkdir(parents=True, exist_ok=True)
        cell.save(out / "reference.png")
        (out / "prompt-used.txt").write_text(
            f"# {slug} ({title}) - cell {i + 1} of sheet {Path(args.input).name}, {today}\n"
            f"# subject: {desc}\n"
            f"# full sheet prompt: {args.prompt or 'see the sheet directory'}\n",
            encoding="utf-8")
        print(f"cell {i + 1:>2} -> {out / 'reference.png'} ({cell.size[0]}x{cell.size[1]})")


if __name__ == "__main__":
    main()
