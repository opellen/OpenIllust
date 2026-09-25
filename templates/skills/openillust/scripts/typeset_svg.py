"""Typeset text with a real font into a single-path SVG - the "typeset" route.

Text is never traced: it is shaped with HarfBuzz (kerning + ligatures) and its
glyph outlines are emitted directly as SVG path data via fontTools. This is
the productized, campaign-neutral form of the proven one-off prototype
(open-goal .openillust/campaigns/logo/plans/2026-08-31-concept-design-4-typeset-wordmark.py);
the shaping/outline/centering math below is kept verbatim from it.

Usage:
  python typeset_svg.py --text "State Designer" --font Inter-Medium.ttf --fill "#20211F"
      --output out.svg
      [--campaign campaign.yaml [--profile <type>]]   # canvas source
      [--canvas N|WxH]                                # explicit override
      [--target-ratio 0.6 | --target-width 614]       # ink width sizing

Canvas resolution (first match wins):
  1. --canvas N (square) or WxH (non-square)
  2. asset_profiles.<profile>.canvas from --campaign (requires --profile;
     scalar -> square, [w, h] -> non-square)
  3. the campaign's root `canvas` (requires --campaign)
  4. error: no canvas source given

--campaign/campaign.py is imported lazily, only when --campaign is passed, so
the --canvas-only path never requires PyYAML (house pattern; see campaign.py
and vectorize.py).

--font accepts a path; if that path does not exist, %WINDIR%\\Fonts\\<value>
is also tried before erroring (so a bare font filename resolves against the
system font directory, matching how the prototype hardcoded C:\\Windows\\Fonts).

Sizing: the target ink width is --target-width px, or --target-ratio times
the canvas width (default 0.6) - the two flags are mutually exclusive. If the
resulting ink height would exceed the canvas height, this is a hard error
(suggesting a smaller ratio/width) rather than a silent shrink.
"""
import argparse
import os
import re
import sys
from pathlib import Path

try:
    import uharfbuzz as hb
    from fontTools.ttLib import TTFont
    from fontTools.pens.svgPathPen import SVGPathPen
    from fontTools.pens.transformPen import TransformPen
    from fontTools.pens.boundsPen import BoundsPen
    from fontTools.misc.transform import Transform
except ImportError as exc:
    sys.exit(
        "typeset_svg.py requires uharfbuzz and fontTools to shape text and outline "
        "glyphs (pip install uharfbuzz fonttools, or see "
        "templates/skills/openillust/requirements.txt): %s" % exc
    )

DEFAULT_TARGET_RATIO = 0.6

CANVAS_RE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*[xX]\s*(\d+(?:\.\d+)?)\s*$")


def parse_canvas(s):
    """Parse --canvas: a bare number (square) or WxH (non-square), e.g. 1760x320."""
    m = CANVAS_RE.match(s)
    if m:
        w, h = float(m.group(1)), float(m.group(2))
    else:
        try:
            w = h = float(s)
        except ValueError:
            raise argparse.ArgumentTypeError(
                f"invalid canvas {s!r}: expected a number or WxH (e.g. 1760x320)")
    if w <= 0 or h <= 0:
        raise argparse.ArgumentTypeError(f"canvas dimensions must be positive: {s!r}")
    return (w, h)


def resolve_profile_canvas(value):
    """Normalize an asset_profiles.<type>.canvas value to a (w, h) tuple.

    Accepts a scalar (square: w == h) or a 2-item [w, h] list/tuple
    (non-square), per references/campaign-schema.md. Raises ValueError with a
    human-readable message otherwise (caller turns that into a usage error).
    """
    if isinstance(value, (list, tuple)):
        if len(value) != 2:
            raise ValueError(
                "canvas list must have exactly 2 items [w, h] (got %r)" % (value,))
        w_raw, h_raw = value
    else:
        w_raw = h_raw = value
    try:
        w = float(w_raw)
        h = float(h_raw)
    except (TypeError, ValueError):
        raise ValueError("canvas value(s) must be numbers (got %r)" % (value,))
    if not (w > 0 and h > 0):
        raise ValueError("canvas value(s) must be positive (got %r)" % (value,))
    return (w, h)


def resolve_canvas(args):
    """Resolve the (canvas_w, canvas_h) to typeset onto. See module docstring
    for the precedence order. --campaign/campaign.py is imported lazily, only
    on the branch that actually needs it, so a --canvas-only invocation never
    requires PyYAML."""
    if args.canvas is not None:
        return args.canvas

    if not args.campaign:
        sys.exit(
            "typeset_svg.py: error: no canvas source given; pass --canvas N|WxH, "
            "or --campaign campaign.yaml (optionally with --profile TYPE)"
        )

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from campaign import load_campaign, CampaignError  # lazy: keep --canvas-only path PyYAML-free
    try:
        campaign = load_campaign(args.campaign)
    except CampaignError as exc:
        sys.exit(f"typeset_svg.py: error: {exc}")

    if args.profile:
        profiles = campaign.get("asset_profiles") or {}
        if not isinstance(profiles, dict) or args.profile not in profiles:
            available = sorted(profiles.keys()) if isinstance(profiles, dict) else []
            if available:
                sys.exit(
                    "typeset_svg.py: error: --profile %r not found in asset_profiles "
                    "(available: %s)" % (args.profile, ", ".join(available))
                )
            sys.exit(
                "typeset_svg.py: error: --profile %r not found; campaign %s declares "
                "no asset_profiles" % (args.profile, args.campaign)
            )
        profile_entry = profiles[args.profile] or {}
        raw_canvas = profile_entry.get("canvas")
        if raw_canvas is not None:
            try:
                return resolve_profile_canvas(raw_canvas)
            except ValueError as exc:
                sys.exit(f"typeset_svg.py: error: asset_profiles.{args.profile}.canvas: {exc}")
        # profile declares no canvas override: fall through to the campaign root canvas

    if campaign.get("canvas") in (None, ""):
        sys.exit(f"typeset_svg.py: error: campaign {args.campaign!r} has no root 'canvas'")
    c = float(campaign["canvas"])
    return (c, c)


def resolve_font(value):
    """--font accepts a path; if it doesn't exist, also try it under the
    system Fonts directory (mirrors the prototype's hardcoded
    C:\\Windows\\Fonts\\Inter-Medium.ttf)."""
    if os.path.isfile(value):
        return value
    windir = os.environ.get("WINDIR", r"C:\Windows")
    candidate = os.path.join(windir, "Fonts", value)
    if os.path.isfile(candidate):
        return candidate
    sys.exit(f"typeset_svg.py: error: font not found: {value!r} (also tried {candidate!r})")


def main():
    ap = argparse.ArgumentParser(
        description="Shape text with HarfBuzz and outline it via fontTools into a "
                     "single-path SVG - never traced.",
    )
    ap.add_argument("--text", required=True, help="the text to typeset")
    ap.add_argument("--font", required=True,
                     help="path to a .ttf/.otf, or a filename under %%WINDIR%%\\Fonts")
    ap.add_argument("--fill", required=True, help="path fill color, e.g. #20211F")
    ap.add_argument("--output", required=True, help="output SVG path")
    ap.add_argument("--campaign", help="path to campaign.yaml (canvas source; see "
                                        "references/campaign-schema.md)")
    ap.add_argument("--profile", help="asset_profiles.<type> whose canvas applies "
                                       "(requires --campaign)")
    ap.add_argument("--canvas", type=parse_canvas, default=None,
                     help="viewBox size: N for square, or WxH (e.g. 1760x320) for "
                          "non-square; overrides --campaign/--profile")
    sizing = ap.add_mutually_exclusive_group()
    sizing.add_argument("--target-ratio", type=float, default=None,
                         help="ink width as a fraction of canvas width (default 0.6)")
    sizing.add_argument("--target-width", type=float, default=None,
                         help="ink width in px (overrides --target-ratio)")
    args = ap.parse_args()

    if args.profile and not args.campaign:
        sys.exit("typeset_svg.py: error: --profile requires --campaign")

    canvas_w, canvas_h = resolve_canvas(args)
    font_path = resolve_font(args.font)

    if args.target_width is not None:
        target_w = args.target_width
    else:
        ratio = args.target_ratio if args.target_ratio is not None else DEFAULT_TARGET_RATIO
        target_w = canvas_w * ratio

    blob = hb.Blob.from_file_path(font_path)
    face = hb.Face(blob)
    hbfont = hb.Font(face)
    buf = hb.Buffer()
    buf.add_str(args.text)
    buf.guess_segment_properties()
    hb.shape(hbfont, buf, {"kern": True, "liga": True})

    tt = TTFont(font_path)
    glyph_set = tt.getGlyphSet()
    glyph_order = tt.getGlyphOrder()
    upm = tt["head"].unitsPerEm

    # Pass 1: ink bbox of the shaped run in font units
    bounds = BoundsPen(glyph_set)
    x = 0
    for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
        gname = glyph_order[info.codepoint]
        tp = TransformPen(bounds, Transform().translate(x + pos.x_offset, pos.y_offset))
        glyph_set[gname].draw(tp)
        x += pos.x_advance
    if bounds.bounds is None:
        sys.exit("typeset_svg.py: error: shaped text has no visible ink (empty --text?)")
    (xmin, ymin, xmax, ymax) = bounds.bounds
    ink_w, ink_h = xmax - xmin, ymax - ymin

    s = target_w / ink_w
    # center ink bbox on the canvas; font y-up -> SVG y-down flip
    tx = (canvas_w - ink_w * s) / 2 - xmin * s
    ty = (canvas_h + ink_h * s) / 2 + ymin * s

    if ink_h * s > canvas_h:
        sys.exit(
            "typeset_svg.py: error: ink height %.1fpx exceeds canvas height %.0fpx at "
            "this size (scale=%.4f, target ink width=%.1fpx); pass a smaller "
            "--target-ratio or --target-width" % (ink_h * s, canvas_h, s, target_w)
        )

    # Pass 2: emit path in SVG coordinates (2-decimal precision per QC PREC001)
    def ntos(n):
        s = "%.2f" % n
        return s.rstrip("0").rstrip(".") if "." in s else s

    pen = SVGPathPen(glyph_set, ntos=ntos)
    x = 0
    for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
        gname = glyph_order[info.codepoint]
        t = Transform(s, 0, 0, -s, tx, ty).translate(x + pos.x_offset, pos.y_offset)
        glyph_set[gname].draw(TransformPen(pen, t))
        x += pos.x_advance
    d = pen.getCommands()

    font_filename = os.path.basename(font_path)
    comment_text = args.text.replace("--", "- -")  # keep the XML comment well-formed
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d">\n'
        '  <!-- "%s" - %s, shaped with HarfBuzz, outlined via fontTools;\n'
        '       ink bbox %.0fx%.0f px centered on canvas -->\n'
        '  <path d="%s" fill="%s"/>\n'
        '</svg>\n'
    ) % (int(canvas_w), int(canvas_h), comment_text, font_filename, ink_w * s, ink_h * s, d, args.fill)

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(svg, encoding="utf-8")

    print("upm=%d ink=%.0fx%.0f units -> %.1fx%.1f px, scale=%.4f"
          % (upm, ink_w, ink_h, ink_w * s, ink_h * s, s))
    print("occupancy(larger dim) = %.3f" % max(ink_w * s / canvas_w, ink_h * s / canvas_h))
    print("wrote", out)


if __name__ == "__main__":
    main()
