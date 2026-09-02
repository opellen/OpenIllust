"""Normalize a vectorizer's SVG output into the campaign's icon contract.

Takes the raw SVG a converter produces (Vectorizer.AI, vtracer, an HF model...)
and makes it contract-shaped: every color snapped to the nearest allowed
campaign hex, geometry rescaled/baked into the campaign's canvas with a
margin, background/speckle regions dropped. Gradient assignment and any
region surgery (e.g. removing a ground shadow) remain deliberate authoring
acts - this script never invents or deletes meaningful geometry beyond the
explicit flags below.

Usage:
  python svg_normalize.py --input raw.svg --output icon.svg --campaign campaign.yaml
      [--margin 0.13] [--drop-background] [--min-area-ratio 0.0005]
      [--drop-color HEX]... [--map SRC=DST]...

Then run qc_svg.py on the result.

--campaign (required) supplies the palette and canvas, plus the --margin and
--min-area-ratio defaults, from a campaign.yaml (see
references/campaign-schema.md). Precedence for --margin/--min-area-ratio: an
explicit flag always wins; then the campaign's normalize.* value; then this
script's generic default. Precedence for --canvas: an explicit flag always
wins; otherwise the campaign's canvas value is used.
"""
import argparse
import re
import sys
from pathlib import Path

from svgelements import SVG, Path as SePath, Shape, Matrix, Color

NUM_RE = re.compile(r"-?\d+\.\d+")


def round_d(d, places=2):
    return NUM_RE.sub(lambda m: f"{float(m.group(0)):.{places}f}".rstrip("0").rstrip("."), d)

# Generic fallback defaults, used when the campaign doesn't set
# normalize.margin / normalize.min_area_ratio.
DEFAULT_MARGIN = 0.13
DEFAULT_MIN_AREA_RATIO = 0.0005


def rgb(hexstr):
    h = hexstr.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def snap(color, overrides, palette):
    """Map an svgelements Color to the nearest allowed hex (or override)."""
    if color is None or color.value is None:
        return None
    src = "#%02X%02X%02X" % (color.red, color.green, color.blue)
    if src.upper() in overrides:
        return overrides[src.upper()]
    r, g, b = color.red, color.green, color.blue
    best, bd = None, 1e9
    for hx in palette:
        pr, pg, pb = rgb(hx)
        d = (r - pr) ** 2 + (g - pg) ** 2 + (b - pb) ** 2
        if d < bd:
            best, bd = hx, d
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--canvas", type=float, default=None,
                    help="viewBox size; default is the campaign's canvas value")
    ap.add_argument("--margin", type=float, default=None,
                    help="default 0.13, or campaign normalize.margin if set")
    ap.add_argument("--min-area-ratio", type=float, default=None,
                    help="drop shapes smaller than this fraction of the source canvas (speckles); "
                         "default 0.0005, or campaign normalize.min_area_ratio if set")
    ap.add_argument("--drop-background", action="store_true",
                    help="drop near-white shapes covering >80%% of the source canvas")
    ap.add_argument("--drop-color", action="append", default=[],
                    help="drop shapes whose ORIGINAL fill is this hex (repeatable)")
    ap.add_argument("--map", action="append", default=[], metavar="SRC=DST",
                    help="force ORIGINAL hex SRC to snap to DST (repeatable)")
    ap.add_argument("--campaign", required=True,
                    help="Path to a campaign.yaml (see references/campaign-schema.md). "
                         "Supplies the palette and the --margin/--min-area-ratio defaults.")
    args = ap.parse_args()

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from campaign import load_campaign, CampaignError  # lazy: avoid requiring PyYAML at import time
    try:
        campaign = load_campaign(args.campaign)
    except CampaignError as exc:
        raise SystemExit(f"svg_normalize.py: error: {exc}")

    palette = [str(c).upper() for c in campaign["palette"]["allowed"]]

    if args.canvas is None:
        args.canvas = float(campaign["canvas"])

    normalize_cfg = campaign.get("normalize")
    if args.margin is None:
        args.margin = (
            float(normalize_cfg["margin"])
            if normalize_cfg and normalize_cfg.get("margin") is not None
            else DEFAULT_MARGIN
        )
    if args.min_area_ratio is None:
        args.min_area_ratio = (
            float(normalize_cfg["min_area_ratio"])
            if normalize_cfg and normalize_cfg.get("min_area_ratio") is not None
            else DEFAULT_MIN_AREA_RATIO
        )

    overrides = {}
    for m in args.map:
        s, d = m.split("=")
        overrides[s.upper() if s.startswith("#") else "#" + s.upper()] = \
            d if d.startswith("#") else "#" + d
    drops = {c.upper() if c.startswith("#") else "#" + c.upper()
             for c in args.drop_color}

    svg = SVG.parse(args.input, reify=True)  # transforms baked into coordinates
    src_w = float(svg.width) if svg.width else None
    src_h = float(svg.height) if svg.height else None

    shapes = []
    for el in svg.elements():
        if not isinstance(el, Shape):
            continue
        try:
            p = abs(SePath(el))  # as path, transform applied
        except Exception:
            continue
        bb = p.bbox()
        if bb is None:
            continue
        x0, y0, x1, y1 = bb
        w, h = x1 - x0, y1 - y0
        fill = el.fill
        orig = ("#%02X%02X%02X" % (fill.red, fill.green, fill.blue)) \
            if fill is not None and fill.value is not None else None
        shapes.append({"path": p, "bbox": bb, "w": w, "h": h,
                       "orig": orig, "stroke": el.stroke,
                       "stroke_width": el.stroke_width,
                       "rule": el.values.get("fill-rule")})

    if not shapes:
        raise SystemExit("no shapes found")
    if src_w is None or src_h is None:
        src_w = max(s["bbox"][2] for s in shapes)
        src_h = max(s["bbox"][3] for s in shapes)

    kept = []
    for s in shapes:
        if s["orig"] and s["orig"].upper() in drops:
            continue
        if s["w"] * s["h"] < src_w * src_h * args.min_area_ratio:
            continue
        if args.drop_background and s["orig"]:
            r, g, b = rgb(s["orig"])
            if min(r, g, b) > 235 and s["w"] > 0.8 * src_w and s["h"] > 0.8 * src_h:
                continue
        kept.append(s)
    if not kept:
        raise SystemExit("all shapes dropped - loosen the flags")

    x0 = min(s["bbox"][0] for s in kept)
    y0 = min(s["bbox"][1] for s in kept)
    x1 = max(s["bbox"][2] for s in kept)
    y1 = max(s["bbox"][3] for s in kept)
    usable = args.canvas * (1 - 2 * args.margin)
    k = usable / max(x1 - x0, y1 - y0)
    ox = (args.canvas - (x1 - x0) * k) / 2 - x0 * k
    oy = (args.canvas - (y1 - y0) * k) / 2 - y0 * k
    mat = Matrix(f"translate({ox},{oy}) scale({k})")

    out = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d">'
           % (int(args.canvas), int(args.canvas)),
           "  <!-- normalized by svg_normalize.py from %s -->" % Path(args.input).name]
    dropped = len(shapes) - len(kept)
    for s in kept:
        p = s["path"] * mat
        d = round_d(p.d())
        fill = snap(Color(s["orig"]), overrides, palette) if s["orig"] else "none"
        attrs = f'd="{d}" fill="{fill}"'
        if s["rule"]:
            attrs += f' fill-rule="{s["rule"]}"'
        if s["stroke"] is not None and s["stroke"].value is not None:
            sw = (s["stroke_width"] or 1) * k
            attrs += (f' stroke="{snap(s["stroke"], overrides, palette)}"'
                      f' stroke-width="{sw:.1f}"')
        out.append(f"  <path {attrs}/>")
    out.append("</svg>")
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"wrote {args.output}: kept {len(kept)} shapes, dropped {dropped}; "
          f"scale {k:.4f}, content fitted to {usable:.0f}px of {args.canvas:g}")


if __name__ == "__main__":
    main()
