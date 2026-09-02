"""Deterministic 'perception' for the freeform recipe: sample the reference
raster along a chosen axis frame and report exact color-band boundaries.

Define the subject axis with two points (--p0 tip, --p1 far end, image px).
--cross F samples perpendicular to the axis at fraction F (0..1) of its
length; --along S samples parallel to the axis at perpendicular offset S px.
Colors are clustered to coarse families so AA fringes do not fragment runs.

Output: runs of color families with their extents in axis units
(t = px along p0->p1, s = px perpendicular, right-hand side positive),
plus the same values scaled to a 512 canvas given --canvas-len (the length
p0->p1 will occupy on the icon canvas, for direct coordinate reuse).
"""
import argparse
import math
from pathlib import Path

from PIL import Image


def family(rgb):
    r, g, b = rgb[:3]
    mx, mn = max(r, g, b), min(r, g, b)
    if mx > 235 and mx - mn < 25:
        return "white"
    if mx < 90:
        return "dark"
    if b > 120 and b > r + 30 and g < b:
        return "navy" if b < 150 or r < 80 else "blue"
    if r > 140 and r > b + 40:
        # split light vs shaded red by brightness
        return "red-lit" if r > 195 else "red-shade"
    if mx - mn < 30:
        return "gray"
    return "other"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--p0", required=True, help="axis start (tip), 'x,y' image px")
    ap.add_argument("--p1", required=True, help="axis end, 'x,y' image px")
    ap.add_argument("--cross", type=float, action="append", default=[],
                    help="sample perpendicular at this fraction (0..1) along the axis")
    ap.add_argument("--along", type=float, action="append", default=[],
                    help="sample parallel to the axis at this perpendicular offset (image px)")
    ap.add_argument("--span", type=float, default=None,
                    help="half-range of a cross scan in px (default: axis length * 0.25)")
    ap.add_argument("--canvas-len", type=float, default=None,
                    help="what the p0->p1 length maps to on the 512 canvas; prints scaled values")
    args = ap.parse_args()

    img = Image.open(args.input).convert("RGB")
    W, H = img.size
    x0, y0 = (float(v) for v in args.p0.split(","))
    x1, y1 = (float(v) for v in args.p1.split(","))
    L = math.hypot(x1 - x0, y1 - y0)
    d = ((x1 - x0) / L, (y1 - y0) / L)
    p = (-d[1], d[0])  # right-hand perpendicular
    k = (args.canvas_len / L) if args.canvas_len else None
    print(f"image {W}x{H}; axis p0=({x0:.0f},{y0:.0f}) p1=({x1:.0f},{y1:.0f}) "
          f"len={L:.1f} dir=({d[0]:.3f},{d[1]:.3f})"
          + (f"; canvas scale k={k:.4f}" if k else ""))

    def sample(px, py):
        xi, yi = int(round(px)), int(round(py))
        if 0 <= xi < W and 0 <= yi < H:
            return family(img.getpixel((xi, yi)))
        return "off"

    def report(tag, points, coord):
        runs = []
        for c, fam in points:
            if runs and runs[-1][0] == fam:
                runs[-1][2] = c
            else:
                runs.append([fam, c, c])
        parts = []
        for fam, a, b in runs:
            if fam in ("white", "off") and (b - a) > L * 0.4:
                parts.append(f"{fam}[...]")
                continue
            if k:
                parts.append(f"{fam}[{coord}={a:.0f}..{b:.0f} | {a*k:.0f}..{b*k:.0f}c]")
            else:
                parts.append(f"{fam}[{coord}={a:.0f}..{b:.0f}]")
        print(f"{tag}: " + " ".join(parts))

    span = args.span if args.span else L * 0.25
    for f in args.cross:
        cx, cy = x0 + d[0] * L * f, y0 + d[1] * L * f
        pts = []
        s = -span
        while s <= span:
            pts.append((s, sample(cx + p[0] * s, cy + p[1] * s)))
            s += 1.0
        report(f"cross t={L*f:.0f}px (f={f})", pts, "s")
    for off in args.along:
        pts = []
        t = 0.0
        while t <= L:
            pts.append((t, sample(x0 + d[0] * t + p[0] * off,
                                  y0 + d[1] * t + p[1] * off)))
            t += 1.0
        report(f"along s={off:.0f}px", pts, "t")


if __name__ == "__main__":
    main()
