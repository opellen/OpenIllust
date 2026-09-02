"""Extract clean vertex skeletons from a flat raster reference.

For freeform silhouettes the LLM should not invent: trace the raster
(vtracer polygon mode, low color), simplify each color region's outline with
RDP, and print per-region vertex lists ready to be re-authored as clean
contract-compliant SVG geometry. The output is a COORDINATE REFERENCE, not a final SVG —
the agent still rebuilds geometry with contract palette/gradients/strokes.

Usage:
  python trace_skeleton.py --input ref.png [--scale 512] [--fit] [--margin 0.13]
      [--eps-ratio 0.008] [--min-area-ratio 0.003] [--max-regions 10]

--fit maps the combined content bbox (background excluded) into the target
canvas with the given margin, so printed vertices can be pasted directly.
"""
import argparse
import re
import tempfile
from pathlib import Path

import vtracer
from PIL import Image


def parse_paths(svg_text):
    """Yield (fill, [subpath_pts...]) per <path>; subpaths split on M."""
    out = []
    for m in re.finditer(r'<path d="([^"]+)" fill="(#[0-9A-Fa-f]{6})"'
                         r'(?: transform="translate\(([\d.]+),([\d.]+)\)")?', svg_text):
        d, fill = m.group(1), m.group(2)
        tx, ty = float(m.group(3) or 0), float(m.group(4) or 0)
        subpaths, pts, cur = [], [], (0.0, 0.0)
        for cm in re.finditer(r'([MLml])\s*(-?[\d.]+)[ ,](-?[\d.]+)', d):
            c, x, y = cm.group(1), float(cm.group(2)), float(cm.group(3))
            if c in "Mm" and pts:
                subpaths.append(pts)
                pts = []
            cur = (cur[0] + x, cur[1] + y) if c.islower() else (x, y)
            pts.append((cur[0] + tx, cur[1] + ty))
        if pts:
            subpaths.append(pts)
        subpaths = [p for p in subpaths if len(p) >= 3]
        if subpaths:
            out.append((fill, subpaths))
    return out


def area(pts):
    s = 0.0
    for i in range(len(pts)):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % len(pts)]
        s += x1 * y2 - x2 * y1
    return abs(s) / 2


def rdp(pts, eps):
    if len(pts) < 3:
        return pts
    ax, ay = pts[0]
    bx, by = pts[-1]
    dmax, idx = -1.0, 0
    for i in range(1, len(pts) - 1):
        px, py = pts[i]
        dx, dy = bx - ax, by - ay
        L = (dx * dx + dy * dy) ** 0.5 or 1e-9
        d = abs(dy * px - dx * py + bx * ay - by * ax) / L
        if d > dmax:
            dmax, idx = d, i
    if dmax > eps:
        left = rdp(pts[: idx + 1], eps)
        return left[:-1] + rdp(pts[idx:], eps)
    return [pts[0], pts[-1]]


def simplify_ring(pts, eps):
    far = max(range(len(pts)),
              key=lambda i: (pts[i][0] - pts[0][0]) ** 2 + (pts[i][1] - pts[0][1]) ** 2)
    a = rdp(pts[: far + 1], eps)
    b = rdp(pts[far:] + [pts[0]], eps)
    ring = a[:-1] + b[:-1]
    return ring


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--scale", type=float, default=512.0, help="target canvas size")
    ap.add_argument("--fit", action="store_true",
                    help="fit content bbox into the canvas with --margin")
    ap.add_argument("--margin", type=float, default=0.13)
    ap.add_argument("--eps-ratio", type=float, default=0.008)
    ap.add_argument("--min-area-ratio", type=float, default=0.003)
    ap.add_argument("--max-regions", type=int, default=10)
    ap.add_argument("--color-precision", type=int, default=6)
    ap.add_argument("--filter-speckle", type=int, default=10)
    ap.add_argument("--layer-difference", type=int, default=16)
    ap.add_argument("--hierarchical", default="cutout", choices=["cutout", "stacked"],
                    help="cutout: non-overlapping visible regions (best for skeletons)")
    ap.add_argument("--emit-svg", metavar="PATH",
                    help="also write the simplified regions as a literal SVG "
                         "(original traced colors, paint order preserved) — a fidelity "
                         "probe, NOT a contract-compliant icon")
    args = ap.parse_args()

    src = Path(args.input)
    img = Image.open(src)
    W, H = img.size
    print(f"source {W}x{H}")

    with tempfile.TemporaryDirectory() as td:
        traced = Path(td) / "traced.svg"
        vtracer.convert_image_to_svg_py(str(src), str(traced), colormode="color",
                                        hierarchical=args.hierarchical, mode="polygon",
                                        filter_speckle=args.filter_speckle,
                                        color_precision=args.color_precision,
                                        layer_difference=args.layer_difference)
        svg = traced.read_text(encoding="utf-8")

    eps = max(W, H) * args.eps_ratio
    raw = []
    for fill, subpaths in parse_paths(svg):
        for pts in subpaths:
            a = area(pts)
            if a < W * H * args.min_area_ratio:
                continue
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            # background: covers nearly the whole image
            if (max(xs) - min(xs)) > 0.95 * W and (max(ys) - min(ys)) > 0.95 * H:
                continue
            raw.append((len(raw), a, fill, simplify_ring(pts, eps)))
    regions = sorted(raw, key=lambda r: -r[1])[: args.max_regions]
    if not regions:
        print("no regions found")
        return
    keep = {r[0] for r in regions}
    regions = [(a, fill, ring) for _, a, fill, ring in regions]

    # transform: fit combined bbox into canvas, or plain uniform scale
    allx = [p[0] for _, _, ring in regions for p in ring]
    ally = [p[1] for _, _, ring in regions for p in ring]
    if args.fit:
        bw, bh = max(allx) - min(allx), max(ally) - min(ally)
        usable = args.scale * (1 - 2 * args.margin)
        s = usable / max(bw, bh)
        ox = (args.scale - bw * s) / 2 - min(allx) * s
        oy = (args.scale - bh * s) / 2 - min(ally) * s
    else:
        s = args.scale / max(W, H)
        ox = oy = 0.0

    print(f"{len(regions)} regions (largest first); canvas {args.scale:g}"
          f"{' fitted, margin %.0f%%' % (args.margin * 100) if args.fit else ''}")
    for a, fill, ring in regions:
        pts = " ".join(f"{x * s + ox:.0f},{y * s + oy:.0f}" for x, y in ring)
        print(f"\nfill={fill} area={100 * a / (W * H):.1f}% vertices={len(ring)}")
        print(f"  points: {pts}")

    if args.emit_svg:
        out = Path(args.emit_svg)
        out.parent.mkdir(parents=True, exist_ok=True)
        polys = []
        for idx, a, fill, ring in raw:  # paint order = trace order
            if idx not in keep:
                continue
            pts = " ".join(f"{x * s + ox:.0f},{y * s + oy:.0f}" for x, y in ring)
            polys.append(f'  <polygon points="{pts}" fill="{fill}"/>')
        c = int(args.scale)
        out.write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d">\n'
            "  <!-- literal trace probe from %s - traced colors, not contract palette -->\n"
            "%s\n</svg>\n" % (c, c, src.name, "\n".join(polys)),
            encoding="utf-8")
        print(f"\nemitted literal SVG: {out} ({len(polys)} polygons)")


if __name__ == "__main__":
    main()
