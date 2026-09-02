"""Build the sprite-sheet generation kit from a cell manifest:
a layout-only grid guide image + a paste-ready image-generation prompt.

Manifest format (one line per cell, ordered left-to-right, top-to-bottom):
  slug | Title | subject-and-action description
Lines starting with # are comments.

Usage:
  python make_sheet_guide.py --manifest .../sheets/<family>/manifest.txt
      --rows 3 --cols 3 --campaign campaign.yaml [--cell 340] [--out-dir <manifest dir>]

Outputs (next to the manifest by default): guide.png, prompt.txt

--campaign (required) wires the prompt from a campaign.yaml (see
references/campaign-schema.md): the campaign name, its AVOID block
(prompt.avoid, with a generic built-in fallback), and its rule lines
(prompt.palette_rules / prompt.style_rules, both required for sheet mode).
"""
import argparse
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# Generic fallback used only when the campaign omits prompt.avoid.
AVOID_BLOCK = """Do not use: photorealistic rendering, glassmorphism, heavy drop shadows, excessive
gradients, neon effects, thick black outlines, cartoon styling, random perspective,
arbitrary decoration, text, labels, or watermarks."""


def parse_manifest(path):
    cells = []
    for line in Path(path).read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        slug, title, desc = (p.strip() for p in line.split("|", 2))
        cells.append((slug, title, desc))
    return cells


def draw_guide(rows, cols, cell, safe_ratio, out_path):
    pad = 16
    W, H = cols * cell + 2 * pad, rows * cell + 2 * pad
    img = Image.new("RGB", (W, H), (255, 255, 255))
    d = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype(r"C:\Windows\Fonts\arial.ttf", cell // 5)
    except OSError:
        font = ImageFont.load_default()
    n = 0
    for r in range(rows):
        for c in range(cols):
            n += 1
            x0, y0 = pad + c * cell, pad + r * cell
            x1, y1 = x0 + cell, y0 + cell
            d.rectangle([x0, y0, x1, y1], outline=(160, 165, 180), width=3)
            m = int(cell * safe_ratio)
            # dashed safe-area rectangle
            step = 14
            for x in range(x0 + m, x1 - m, step):
                d.line([x, y0 + m, min(x + 7, x1 - m), y0 + m], fill=(200, 205, 220), width=2)
                d.line([x, y1 - m, min(x + 7, x1 - m), y1 - m], fill=(200, 205, 220), width=2)
            for y in range(y0 + m, y1 - m, step):
                d.line([x0 + m, y, x0 + m, min(y + 7, y1 - m)], fill=(200, 205, 220), width=2)
                d.line([x1 - m, y, x1 - m, min(y + 7, y1 - m)], fill=(200, 205, 220), width=2)
            d.text((x0 + m, y0 + m), str(n), fill=(120, 126, 145), font=font)
    img.save(out_path)
    return W, H


# The style- and palette-rule bullets come verbatim from the campaign
# (prompt.style_rules, then prompt.palette_rules); everything else is the
# campaign-neutral kit framing. See module docstring.
PROMPT_TEMPLATE = """Create ONE sprite sheet image containing {n} icons for the "{campaign_name}"
design system, in an EXACT {rows}x{cols} grid of equal square cells.

Attachments and their roles:
- The attached design-guide document defines this design system's visual language:
  palette, geometry, composition. Follow it strictly. The instructions below override
  any example prompts inside it.
- The grid guide image is a LAYOUT-ONLY reference: take from it only the cell count,
  positions, equal slot sizes, and safe padding. Do NOT reproduce its lines, boxes,
  or numbers in the output - the finished sheet has NO visible grid.
- Any icon images attached are APPROVED STYLE ANCHORS: match their style exactly -
  palette, relative stroke weight, margins. Only each cell's subject changes.
- Any app screenshot attached shows the UI these icons will live in - match its
  overall mood.

Grid cells, left-to-right then top-to-bottom:
{cells}

Rules for every cell:
{style_rules}
{palette_rules}
- every icon fully inside its cell's safe area with generous margin - nothing touches
  a cell edge; consistent scale and stroke weight across ALL cells
- no text, no labels, no numbers, no cell borders, no UI chrome, no drop shadows,
  no background tint

{avoid}
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--rows", type=int, required=True)
    ap.add_argument("--cols", type=int, required=True)
    ap.add_argument("--cell", type=int, default=340)
    ap.add_argument("--safe-ratio", type=float, default=0.10)
    ap.add_argument("--out-dir", default=None)
    ap.add_argument("--campaign", required=True,
                    help="Path to a campaign.yaml (see references/campaign-schema.md). "
                         "Supplies the campaign name, AVOID block, and palette/style rule lines.")
    args = ap.parse_args()

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from campaign import load_campaign, CampaignError  # lazy: import only at run time
    try:
        campaign = load_campaign(args.campaign)
    except CampaignError as exc:
        raise SystemExit(f"make_sheet_guide.py: error: {exc}")

    cells = parse_manifest(args.manifest)
    if len(cells) != args.rows * args.cols:
        raise SystemExit(f"manifest has {len(cells)} cells; grid needs {args.rows * args.cols}")
    out_dir = Path(args.out_dir) if args.out_dir else Path(args.manifest).parent
    out_dir.mkdir(parents=True, exist_ok=True)

    W, H = draw_guide(args.rows, args.cols, args.cell, args.safe_ratio, out_dir / "guide.png")
    cell_lines = "\n".join(f"{i + 1}. {t} - {d}" for i, (_, t, d) in enumerate(cells))

    prompt_cfg = campaign.get("prompt") or {}
    avoid = str(prompt_cfg.get("avoid") or AVOID_BLOCK).rstrip("\n")
    palette_rules = str(prompt_cfg.get("palette_rules") or "").rstrip("\n")
    style_rules = str(prompt_cfg.get("style_rules") or "").rstrip("\n")
    if not palette_rules or not style_rules:
        raise SystemExit(
            "make_sheet_guide.py: error: campaign is missing required "
            "prompt.palette_rules / prompt.style_rules for sheet mode"
        )
    prompt = PROMPT_TEMPLATE.format(
        n=len(cells), rows=args.rows, cols=args.cols, cells=cell_lines,
        campaign_name=campaign.get("name"),
        avoid=avoid, palette_rules=palette_rules, style_rules=style_rules,
    )
    (out_dir / "prompt.txt").write_text(prompt, encoding="utf-8")
    print(f"wrote {out_dir / 'guide.png'} ({W}x{H}) and {out_dir / 'prompt.txt'} "
          f"({len(cells)} cells)")


if __name__ == "__main__":
    main()
