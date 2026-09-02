#!/usr/bin/env python3
"""
qc_svg.py - Deterministic QC gate for OpenIllust campaign SVG assets.

This is a GATE, not a fixer: it only validates and reports. It never
modifies, rewrites, or "auto-corrects" an input SVG. A failed gate means
the calling pipeline should regenerate the icon, not patch the file.

Pure Python 3 standard library only (xml.etree.ElementTree + re). No
network access, no third-party dependencies.

Style rules enforced, all driven by a required --campaign campaign.yaml
(see references/campaign-schema.md):
  - viewBox exactly "0 0 <canvas> <canvas>" for the campaign's canvas size
  - only the campaign's allowed palette colors for fill/stroke/stop-color
  - only the campaign's whitelisted gradient ids (none, if the campaign
    declares no palette.gradients)
  - stroke width within the campaign's stroke.main range, where declared
    (skipped entirely otherwise); dashed construction-colored lines use the
    campaign's stroke.construction range, where declared
  - content margin/centering within the campaign's qc thresholds
  - no text/raster/effects content

Usage:
    python qc_svg.py --campaign CAMPAIGN FILE [FILE ...]
    python qc_svg.py --campaign CAMPAIGN --dir DIR
    python qc_svg.py --campaign CAMPAIGN FILE --strict
    python qc_svg.py --campaign CAMPAIGN FILE --json

Exit codes:
    0 - all files passed
    1 - at least one file failed (or, under --strict, had a warning)
    2 - usage error or an input file could not be read/parsed as bytes

Output is ASCII-only (no unicode symbols/emoji) so it renders correctly
on narrow Windows console code pages.
"""

import argparse
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants: generic product defaults, plus fixed structural values that are
# not part of any campaign's style contract (namespaces, tag names, regexes).
# Palette, gradients, canvas, and stroke ranges always come from the loaded
# campaign -- see build_config() -- since campaign.py guarantees the fields
# this script needs (name, canvas, palette.allowed) are present.
# ---------------------------------------------------------------------------

SVG_NS = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"

GRADIENT_TAGS = {"linearGradient", "radialGradient"}

FORBIDDEN_EXACT_TAGS = {"text", "tspan", "image", "foreignobject", "script", "style"}

BAD_NS_SUBSTRINGS = ("inkscape", "sodipodi", "ns.adobe.com", "adobe.com")

ALLOWED_CAP_JOIN = {"butt", "miter", "round"}

NUMERIC_ATTRS = {
    "x", "y", "cx", "cy", "r", "rx", "ry", "width", "height",
    "x1", "y1", "x2", "y2", "points", "d", "stroke-width", "offset",
}

HREF_KEYS = ("href", "{%s}href" % XLINK_NS)

URL_REF_RE = re.compile(r'^url\(\s*[\'"]?#([A-Za-z_][\w\-.:]*)[\'"]?\s*\)$', re.IGNORECASE)
PREC_RE = re.compile(r'-?\d+\.\d{3,}')

# Canvas geometry used for margin/occupancy checks always comes from the
# campaign's `canvas` value (see build_config()) rather than from the file's
# own viewBox, so that a broken viewBox (caught separately by VIEWBOX001)
# does not also corrupt the margin math.
#
# Margin/center-offset thresholds below are generic product defaults, used
# only when a campaign omits the corresponding qc.* key.
MARGIN_FAIL_MAX_PCT = 86.0
MARGIN_FAIL_MIN_PCT = 50.0
MARGIN_WARN_MIN_PCT = 68.0
MARGIN_WARN_MAX_PCT = 82.0
CENTER_OFFSET_WARN_PCT = 6.0


# ---------------------------------------------------------------------------
# Campaign wiring: build an effective config dict from a loaded campaign.yaml
# (see campaign.load_campaign). That loader guarantees name/canvas/
# palette.allowed are present; every other key a campaign may declare
# (palette.gradients, stroke.main, stroke.construction, qc.*) is optional,
# and build_config() below applies this script's own rule for each: an
# absent stroke.main disables stroke-width checking entirely, an absent
# palette.gradients means no gradient id is whitelisted, and absent qc.*
# keys fall back to the generic product defaults declared above.
# ---------------------------------------------------------------------------

def _cget(campaign, *path, default=None):
    d = campaign
    for k in path:
        if not isinstance(d, dict) or k not in d:
            return default
        d = d[k]
    return default if d is None else d


def _fmt_num(x):
    """Format a campaign-configured number as a clean display string:
    '512' rather than '512.0' for whole numbers."""
    xf = float(x)
    return str(int(xf)) if xf.is_integer() else str(xf)


def build_config(campaign):
    """Build the effective QC config dict from a loaded campaign.

    campaign is a dict loaded via campaign.load_campaign(), which guarantees
    name, canvas, and palette.allowed are present. Every other key this
    function reads is optional -- see the module comment above for how each
    is defaulted or disabled when the campaign omits it.
    """
    canvas = float(campaign["canvas"])

    allowed_colors = {str(c).upper() for c in campaign["palette"]["allowed"]}

    gradients_cfg = _cget(campaign, "palette", "gradients")
    if gradients_cfg:
        allowed_gradient_ids = set(gradients_cfg.keys())
        gradient_stops = {
            gid: {str(c).upper() for c in stops}
            for gid, stops in gradients_cfg.items()
        }
    else:
        # No palette.gradients declared: no gradient id is whitelisted, so
        # no gradient may be defined or referenced (see
        # check_colors_and_gradients / GRADIENT001).
        allowed_gradient_ids = set()
        gradient_stops = {}

    main_width = _cget(campaign, "stroke", "main", "width")
    stroke_main = (float(main_width[0]), float(main_width[1])) if main_width else None

    constr = _cget(campaign, "stroke", "construction")
    constr_width = constr.get("width") if constr else None
    if constr and constr_width:
        stroke_construction_color = str(constr.get("color", "")).strip().lower()
        stroke_construction_requires_dash = bool(constr.get("requires_dash", True))
        stroke_construction_width = (float(constr_width[0]), float(constr_width[1]))
    else:
        # No (usable) stroke.construction declared: there is no
        # construction-line exception; every stroke is checked against
        # stroke_main (see check_stroke_width).
        stroke_construction_color = None
        stroke_construction_requires_dash = True
        stroke_construction_width = None

    occ_warn = _cget(campaign, "qc", "occupancy_warn")
    occ_fail = _cget(campaign, "qc", "occupancy_fail")
    center_max = _cget(campaign, "qc", "center_offset_max")

    return {
        "canvas": canvas,
        "allowed_colors": allowed_colors,
        "allowed_gradient_ids": allowed_gradient_ids,
        "gradient_stops": gradient_stops,
        "stroke_main": stroke_main,
        "stroke_construction_color": stroke_construction_color,
        "stroke_construction_requires_dash": stroke_construction_requires_dash,
        "stroke_construction_width": stroke_construction_width,
        "margin_warn_min_pct": float(occ_warn[0]) * 100.0 if occ_warn else MARGIN_WARN_MIN_PCT,
        "margin_warn_max_pct": float(occ_warn[1]) * 100.0 if occ_warn else MARGIN_WARN_MAX_PCT,
        "margin_fail_min_pct": float(occ_fail[0]) * 100.0 if occ_fail else MARGIN_FAIL_MIN_PCT,
        "margin_fail_max_pct": float(occ_fail[1]) * 100.0 if occ_fail else MARGIN_FAIL_MAX_PCT,
        "center_offset_max_pct": float(center_max) * 100.0 if center_max else CENTER_OFFSET_WARN_PCT,
    }


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def localname(tag):
    """Strip a Clark-notation namespace off an ElementTree tag."""
    if isinstance(tag, str) and tag.startswith("{"):
        return tag.split("}", 1)[1]
    return tag if isinstance(tag, str) else str(tag)


def is_element(elem):
    """True for real elements; False for Comment/ProcessingInstruction nodes."""
    return isinstance(elem.tag, str)


def elem_desc(elem):
    """Human-readable identifier for an element in violation messages.

    ElementTree does not track source line numbers, so identification is
    done by tag name plus id="" (when present) rather than by file position.
    """
    ln = localname(elem.tag)
    eid = elem.get("id")
    if eid:
        return "<%s id=%s>" % (ln, eid)
    return "<%s>" % ln


def get_style_dict(elem):
    """Parse a style="" attribute into a lowercase-keyed property dict.

    Limitation: only inline style="" is considered. External/embedded CSS
    (e.g. a <style> block with class selectors) is not resolved -- and the
    <style> element itself is forbidden content anyway (FORBID001), so this
    is not expected to matter for compliant icons.
    """
    style = elem.get("style")
    d = {}
    if style:
        for decl in style.split(";"):
            if ":" in decl:
                k, v = decl.split(":", 1)
                d[k.strip().lower()] = v.strip()
    return d


def get_prop(elem, style_dict, name):
    """Effective value of a presentation property: style="" wins over the
    plain attribute, matching normal SVG/CSS cascade rules."""
    if name in style_dict:
        return style_dict[name]
    return elem.get(name)


def parse_length(s):
    """Parse a CSS length like '10', '10.5', or '10px' to a float, or None."""
    if s is None:
        return None
    s = s.strip()
    m = re.match(r'^(-?\d*\.?\d+(?:[eE][-+]?\d+)?)\s*(px)?$', s)
    if not m:
        return None
    try:
        return float(m.group(1))
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Path 'd' bounding-box approximation
#
# Limitations (this is a deliberately approximate, "good enough for a QC
# sanity gate" implementation, not a geometry engine):
#   - Curve commands (C/S/Q/T) contribute their control points and end
#     points to the point cloud, not the curve's true geometric extrema.
#     This can over- or under-estimate the real bbox slightly, which is
#     acceptable for a margin/occupancy sanity check with FAIL bounds at
#     50%/86% and WARN bounds at 68%/82%.
#   - Elliptical arcs (A/a) only contribute their endpoint; rx/ry/rotation
#     are not solved for the arc's true extrema.
#   - Relative commands accumulate against a running "current point" as the
#     path is walked left to right.
#   - Malformed/truncated coordinate groups are skipped rather than raising,
#     so one broken path degrades gracefully instead of crashing the run.
#   - The number tokenizer does not handle pathological glued decimals with
#     no separator (e.g. "1.5.5" meaning 1.5 then 0.5); ordinary path data
#     (space/comma separated, or numbers meeting at a '-' sign) tokenizes
#     correctly.
#   - <use>/<symbol> references are not resolved/expanded, so content that
#     only exists inside a referenced (and therefore <defs>-excluded)
#     template is not counted.
# ---------------------------------------------------------------------------

_PATH_TOKEN_RE = re.compile(
    r'[MmLlHhVvCcSsQqTtAaZz]'
    r'|-?\d+\.\d+(?:[eE][-+]?\d+)?'
    r'|-?\.\d+(?:[eE][-+]?\d+)?'
    r'|-?\d+(?:[eE][-+]?\d+)?'
)

_PATH_ARGC = {
    "M": 2, "L": 2, "T": 2, "H": 1, "V": 1,
    "C": 6, "S": 4, "Q": 4, "A": 7, "Z": 0,
}

_PATH_LETTERS = "MmLlHhVvCcSsQqTtAaZz"


def _tokenize_path(d):
    tokens = []
    for tok in _PATH_TOKEN_RE.findall(d):
        if tok in _PATH_LETTERS:
            tokens.append(("cmd", tok))
        else:
            try:
                tokens.append(("num", float(tok)))
            except ValueError:
                pass
    return tokens


def path_bbox_points(d):
    """Return an approximate point cloud bounding the given path 'd' data.

    See the module-level comment above this section for documented limits.
    """
    tokens = _tokenize_path(d)
    points = []
    cur = (0.0, 0.0)
    start = (0.0, 0.0)
    cmd = None
    i = 0
    n = len(tokens)
    while i < n:
        ttype, tval = tokens[i]
        if ttype == "cmd":
            cmd = tval
            i += 1
            if cmd.upper() == "Z":
                cur = start
                points.append(cur)
                cmd = None
                continue
        if cmd is None:
            i += 1
            continue
        base = cmd.upper()
        argc = _PATH_ARGC.get(base)
        if argc is None:
            i += 1
            cmd = None
            continue
        if i + argc > n:
            break
        args = []
        bad = False
        for k in range(argc):
            t2 = tokens[i + k]
            if t2[0] != "num":
                bad = True
                break
            args.append(t2[1])
        if bad:
            i += 1
            continue
        i += argc
        relative = cmd.islower()
        if base == "H":
            x = (cur[0] + args[0]) if relative else args[0]
            cur = (x, cur[1])
            points.append(cur)
        elif base == "V":
            y = (cur[1] + args[0]) if relative else args[0]
            cur = (cur[0], y)
            points.append(cur)
        elif base in ("M", "L", "T"):
            x, y = args
            if relative:
                x += cur[0]
                y += cur[1]
            cur = (x, y)
            points.append(cur)
            if base == "M":
                start = cur
                # Subsequent bare coordinate pairs after an initial M are
                # implicit linetos per the SVG path grammar.
                cmd = "l" if relative else "L"
        elif base == "C":
            x1, y1, x2, y2, x, y = args
            if relative:
                x1 += cur[0]; y1 += cur[1]
                x2 += cur[0]; y2 += cur[1]
                x += cur[0]; y += cur[1]
            points.extend([(x1, y1), (x2, y2), (x, y)])
            cur = (x, y)
        elif base == "S":
            x2, y2, x, y = args
            if relative:
                x2 += cur[0]; y2 += cur[1]
                x += cur[0]; y += cur[1]
            points.extend([(x2, y2), (x, y)])
            cur = (x, y)
        elif base == "Q":
            x1, y1, x, y = args
            if relative:
                x1 += cur[0]; y1 += cur[1]
                x += cur[0]; y += cur[1]
            points.extend([(x1, y1), (x, y)])
            cur = (x, y)
        elif base == "A":
            rx, ry, xrot, large, sweep, x, y = args
            if relative:
                x += cur[0]
                y += cur[1]
            points.append((x, y))
            cur = (x, y)
    return points


def collect_points_for_bbox(root, parent_map):
    """Collect an approximate point cloud for content-occupancy checks.

    Elements inside <defs> are excluded per spec. <use>/<symbol> references
    are not resolved (see path_bbox_points doc for the full limitation
    list).
    """

    def is_in_defs(elem):
        e = elem
        while e in parent_map:
            e = parent_map[e]
            if is_element(e) and localname(e.tag) == "defs":
                return True
        return False

    points = []
    for elem in root.iter():
        if elem is root or not is_element(elem):
            continue
        if is_in_defs(elem):
            continue
        ln = localname(elem.tag).lower()
        try:
            if ln == "rect":
                x = float(elem.get("x", "0")); y = float(elem.get("y", "0"))
                w = float(elem.get("width", "0")); h = float(elem.get("height", "0"))
                points.extend([(x, y), (x + w, y + h)])
            elif ln == "circle":
                cx = float(elem.get("cx", "0")); cy = float(elem.get("cy", "0"))
                r = float(elem.get("r", "0"))
                points.extend([(cx - r, cy - r), (cx + r, cy + r)])
            elif ln == "ellipse":
                cx = float(elem.get("cx", "0")); cy = float(elem.get("cy", "0"))
                rx = float(elem.get("rx", "0")); ry = float(elem.get("ry", "0"))
                points.extend([(cx - rx, cy - ry), (cx + rx, cy + ry)])
            elif ln == "line":
                x1 = float(elem.get("x1", "0")); y1 = float(elem.get("y1", "0"))
                x2 = float(elem.get("x2", "0")); y2 = float(elem.get("y2", "0"))
                points.extend([(x1, y1), (x2, y2)])
            elif ln in ("polyline", "polygon"):
                nums = re.findall(r'-?\d*\.?\d+(?:[eE][-+]?\d+)?', elem.get("points", ""))
                vals = [float(v) for v in nums]
                for k in range(0, len(vals) - 1, 2):
                    points.append((vals[k], vals[k + 1]))
            elif ln == "path":
                dattr = elem.get("d", "")
                if dattr:
                    points.extend(path_bbox_points(dattr))
        except ValueError:
            # Non-numeric coordinate data on an otherwise well-formed
            # element; skip it rather than aborting the whole QC run.
            continue
    return points


# ---------------------------------------------------------------------------
# Individual check groups. Each appends {check, level, detail} dicts.
# ---------------------------------------------------------------------------

def check_viewbox(root, violations, cfg):
    canvas = cfg["canvas"]
    expected_str = "0 0 %s %s" % (_fmt_num(canvas), _fmt_num(canvas))
    vb = root.get("viewBox")
    if vb is None:
        violations.append({
            "check": "VIEWBOX001", "level": "FAIL",
            "detail": 'viewBox attribute is missing (expected "%s")' % expected_str,
        })
        return
    parts = re.split(r'[\s,]+', vb.strip())
    ok = False
    if len(parts) == 4:
        try:
            nums = [float(p) for p in parts]
            ok = nums == [0.0, 0.0, canvas, canvas]
        except ValueError:
            ok = False
    if not ok:
        violations.append({
            "check": "VIEWBOX001", "level": "FAIL",
            "detail": 'viewBox must be exactly "%s" (found %r)' % (expected_str, vb),
        })


def check_colors_and_gradients(root, violations, cfg, parent_map):
    allowed_colors = cfg["allowed_colors"]
    allowed_gradient_ids = cfg["allowed_gradient_ids"]
    gradient_stops = cfg["gradient_stops"]  # {} unless --campaign declared palette.gradients

    # Pass 1: which gradients are validly defined (linearGradient, allowed id).
    defined_valid_ids = set()
    for elem in root.iter():
        if not is_element(elem):
            continue
        ln = localname(elem.tag)
        if ln not in GRADIENT_TAGS:
            continue
        gid = elem.get("id")
        if ln != "linearGradient":
            violations.append({
                "check": "GRADIENT001", "level": "FAIL",
                "detail": "%s is not allowed; only linearGradient may be defined (id=%s)"
                          % (ln, gid or "<none>"),
            })
        elif not gid or gid not in allowed_gradient_ids:
            violations.append({
                "check": "GRADIENT001", "level": "FAIL",
                "detail": "linearGradient id %r is not in the allowed set %s"
                          % (gid, sorted(allowed_gradient_ids)),
            })
        else:
            defined_valid_ids.add(gid)

    def enclosing_gradient_id(elem):
        e = elem
        while e in parent_map:
            e = parent_map[e]
            if is_element(e) and localname(e.tag) == "linearGradient":
                return e.get("id")
        return None

    # Pass 2: every fill / stroke / stop-color value.
    for elem in root.iter():
        if not is_element(elem):
            continue
        style = get_style_dict(elem)
        for prop in ("fill", "stroke", "stop-color"):
            val = get_prop(elem, style, prop)
            if val is None:
                continue
            v = val.strip()
            if not v:
                continue
            if v.lower().startswith("url("):
                m = URL_REF_RE.match(v)
                if not m:
                    violations.append({
                        "check": "COLOR001", "level": "FAIL",
                        "detail": "%s %s=%r is not a valid internal url(#id) reference"
                                  % (elem_desc(elem), prop, val),
                    })
                else:
                    ref_id = m.group(1)
                    if ref_id not in defined_valid_ids:
                        violations.append({
                            "check": "GRADIENT002", "level": "FAIL",
                            "detail": "%s %s references url(#%s) which does not resolve "
                                      "to a defined allowed gradient"
                                      % (elem_desc(elem), prop, ref_id),
                        })
                continue
            if v.lower() == "none":
                continue
            # Campaign-only stricter check: a <stop> under a gradient id whose
            # exact stop colors are declared in palette.gradients must use
            # one of those declared colors, not merely any campaign palette color.
            if prop == "stop-color" and gradient_stops and localname(elem.tag) == "stop":
                gid = enclosing_gradient_id(elem)
                if gid is not None and gid in gradient_stops:
                    if v.upper() in gradient_stops[gid]:
                        continue
                    violations.append({
                        "check": "GRADIENT003", "level": "FAIL",
                        "detail": "%s stop-color=%r is not one of the declared stops "
                                  "for gradient %r %s"
                                  % (elem_desc(elem), val, gid, sorted(gradient_stops[gid])),
                    })
                    continue
            if v.upper() in allowed_colors:
                continue
            violations.append({
                "check": "COLOR001", "level": "FAIL",
                "detail": "%s %s=%r is not in the campaign's allowed palette"
                          % (elem_desc(elem), prop, val),
            })


def check_stroke_width(root, violations, cfg):
    stroke_main = cfg["stroke_main"]
    if stroke_main is None:
        # Campaign declares no stroke.main range: this style has no
        # stroke-width rule, so STROKE001 is not evaluated at all.
        return
    constr_color = cfg["stroke_construction_color"]  # already lowercased, or falsy to disable
    constr_requires_dash = cfg["stroke_construction_requires_dash"]
    constr_width = cfg["stroke_construction_width"]

    def walk(elem, inherited_stroke, inherited_width, inherited_dash):
        eff_stroke, eff_width_raw, eff_dash = inherited_stroke, inherited_width, inherited_dash
        if is_element(elem):
            style = get_style_dict(elem)
            own_stroke = get_prop(elem, style, "stroke")
            own_width = get_prop(elem, style, "stroke-width")
            own_dash = get_prop(elem, style, "stroke-dasharray")
            eff_stroke = own_stroke if own_stroke is not None else inherited_stroke
            eff_width_raw = own_width if own_width is not None else inherited_width
            eff_dash = own_dash if own_dash is not None else inherited_dash
            if eff_stroke is not None and eff_stroke.strip().lower() not in ("none", ""):
                # Construction/blueprint guide lines (style-contract section 6): dashed
                # strokes in the campaign's construction color use the contract's own
                # width range instead of the main-stroke range.
                if constr_color:
                    color_match = eff_stroke.strip().lower() == constr_color
                    dash_match = (
                        (eff_dash is not None and eff_dash.strip().lower() not in ("none", ""))
                        if constr_requires_dash else True
                    )
                    is_construction = color_match and dash_match
                else:
                    is_construction = False
                lo, hi = constr_width if is_construction else stroke_main
                wnum = parse_length(eff_width_raw)
                if wnum is None:
                    violations.append({
                        "check": "STROKE001", "level": "FAIL",
                        "detail": "%s has stroke=%r but effective stroke-width %r is not numeric"
                                  % (elem_desc(elem), eff_stroke, eff_width_raw),
                    })
                elif not (lo <= wnum <= hi):
                    violations.append({
                        "check": "STROKE001", "level": "FAIL",
                        "detail": "%s effective stroke-width %s is outside [%g, %g]%s"
                                  % (elem_desc(elem), wnum, lo, hi,
                                     " (dashed %s construction line)" % constr_color.upper()
                                     if is_construction else ""),
                    })
        for child in list(elem):
            walk(child, eff_stroke, eff_width_raw, eff_dash)

    # SVG initial values: stroke=none, stroke-width=1, no dasharray.
    walk(root, "none", "1", None)


def check_forbidden_content(root, violations):
    for elem in root.iter():
        if not is_element(elem):
            continue
        ln = localname(elem.tag)
        ln_lower = ln.lower()

        # FORBID001: forbidden element types.
        if (ln_lower in FORBIDDEN_EXACT_TAGS
                or ln_lower == "filter"
                or ln_lower.startswith("fe")
                or ln_lower.startswith("animate")):
            violations.append({
                "check": "FORBID001", "level": "FAIL",
                "detail": "forbidden element <%s> is not allowed" % ln,
            })

        # FORBID002: inkscape/sodipodi/adobe namespaced element or attribute.
        if elem.tag.startswith("{"):
            ns = elem.tag[1:elem.tag.index("}")]
            if any(s in ns.lower() for s in BAD_NS_SUBSTRINGS):
                violations.append({
                    "check": "FORBID002", "level": "FAIL",
                    "detail": "element in forbidden editor namespace: %s" % elem.tag,
                })
        for attr in elem.attrib:
            if attr.startswith("{"):
                ns = attr[1:attr.index("}")]
                if any(s in ns.lower() for s in BAD_NS_SUBSTRINGS):
                    violations.append({
                        "check": "FORBID002", "level": "FAIL",
                        "detail": "%s has attribute in forbidden editor namespace: %s"
                                  % (elem_desc(elem), attr),
                    })

        # FORBID003 / FORBID004: href / xlink:href.
        for key in HREF_KEYS:
            val = elem.attrib.get(key)
            if val is None:
                continue
            v = val.strip()
            if v.lower().startswith("data:"):
                violations.append({
                    "check": "FORBID004", "level": "FAIL",
                    "detail": "%s %s is a data: URI, which is not allowed"
                              % (elem_desc(elem), key),
                })
            elif not v.startswith("#"):
                violations.append({
                    "check": "FORBID003", "level": "FAIL",
                    "detail": '%s %s=%r points outside the document (must start with "#")'
                              % (elem_desc(elem), key, val),
                })

        # FORBID004: data: URI in any other attribute.
        for key, val in elem.attrib.items():
            if key in HREF_KEYS:
                continue
            if isinstance(val, str) and "data:" in val.lower():
                violations.append({
                    "check": "FORBID004", "level": "FAIL",
                    "detail": "%s attribute %s contains a data: URI, which is not allowed"
                              % (elem_desc(elem), localname(key)),
                })


def check_margin(root, parent_map, violations, cfg):
    canvas = cfg["canvas"]
    margin_fail_min_pct = cfg["margin_fail_min_pct"]
    margin_fail_max_pct = cfg["margin_fail_max_pct"]
    margin_warn_min_pct = cfg["margin_warn_min_pct"]
    margin_warn_max_pct = cfg["margin_warn_max_pct"]
    center_offset_max_pct = cfg["center_offset_max_pct"]

    points = collect_points_for_bbox(root, parent_map)
    if not points:
        violations.append({
            "check": "MARGIN001", "level": "FAIL",
            "detail": "no measurable content found (no rect/circle/ellipse/line/"
                      "polyline/polygon/path elements outside <defs>)",
        })
        return
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    w = max_x - min_x
    h = max_y - min_y
    dim = max(w, h)
    pct = dim / canvas * 100.0
    cx = (min_x + max_x) / 2.0
    cy = (min_y + max_y) / 2.0
    off_x_pct = abs(cx - canvas / 2.0) / canvas * 100.0
    off_y_pct = abs(cy - canvas / 2.0) / canvas * 100.0
    canvas_label = _fmt_num(canvas)

    if pct > margin_fail_max_pct or pct < margin_fail_min_pct:
        violations.append({
            "check": "MARGIN001", "level": "FAIL",
            "detail": "content bbox larger dimension is %.1f%% of the %s canvas "
                      "(bbox=%.1f x %.1f); must be within [%.0f%%, %.0f%%]"
                      % (pct, canvas_label, w, h, margin_fail_min_pct, margin_fail_max_pct),
        })
    elif pct < margin_warn_min_pct or pct > margin_warn_max_pct:
        violations.append({
            "check": "MARGIN002", "level": "WARN",
            "detail": "content bbox larger dimension is %.1f%% of the %s canvas; "
                      "recommended range is [%.0f%%, %.0f%%]"
                      % (pct, canvas_label, margin_warn_min_pct, margin_warn_max_pct),
        })

    if off_x_pct > center_offset_max_pct or off_y_pct > center_offset_max_pct:
        violations.append({
            "check": "MARGIN003", "level": "WARN",
            "detail": "content bbox center is offset from canvas center by "
                      "(%.1f%%, %.1f%%); must be within %.0f%% on each axis"
                      % (off_x_pct, off_y_pct, center_offset_max_pct),
        })


def check_dimensions_warn(root, violations):
    if root.get("width") is not None or root.get("height") is not None:
        violations.append({
            "check": "DIM001", "level": "WARN",
            "detail": "root <svg> has width/height attribute(s); viewBox-only sizing is preferred",
        })


def check_precision(root, violations):
    for elem in root.iter():
        if not is_element(elem):
            continue
        style = get_style_dict(elem)
        for attr in NUMERIC_ATTRS:
            val = get_prop(elem, style, attr)
            if val is None:
                continue
            m = PREC_RE.search(val)
            if m:
                violations.append({
                    "check": "PREC001", "level": "WARN",
                    "detail": "%s %s=%r has numeric precision beyond 2 decimal places (%s)"
                              % (elem_desc(elem), attr, val, m.group(0)),
                })


def check_linecap_join(root, violations):
    for elem in root.iter():
        if not is_element(elem):
            continue
        style = get_style_dict(elem)
        for prop in ("stroke-linecap", "stroke-linejoin"):
            val = get_prop(elem, style, prop)
            if val is None:
                continue
            if val.strip().lower() not in ALLOWED_CAP_JOIN:
                violations.append({
                    "check": "LINECAP001", "level": "WARN",
                    "detail": "%s %s=%r is not in {butt, miter, round}"
                              % (elem_desc(elem), prop, val),
                })


# ---------------------------------------------------------------------------
# Top-level per-file check
# ---------------------------------------------------------------------------

def check_svg(path, cfg):
    """Run every check against one file. Returns a list of violation dicts.

    Never writes to `path`; this function only reads. `cfg` is the effective
    campaign-sourced config dict from build_config().
    """
    violations = []
    try:
        with open(path, "rb") as f:
            data = f.read()
    except OSError as exc:
        return [{"check": "IO001", "level": "FAIL", "detail": "could not read file: %s" % exc}]

    try:
        root = ET.fromstring(data)
    except ET.ParseError as exc:
        return [{"check": "XML001", "level": "FAIL", "detail": "not well-formed XML: %s" % exc}]

    # XML002: root must be <svg xmlns="http://www.w3.org/2000/svg">.
    if localname(root.tag) != "svg" or root.tag != "{%s}svg" % SVG_NS:
        violations.append({
            "check": "XML002", "level": "FAIL",
            "detail": 'root element must be <svg> with xmlns="%s" (found tag=%r)'
                      % (SVG_NS, root.tag),
        })

    parent_map = {c: p for p in root.iter() for c in p}

    check_viewbox(root, violations, cfg)
    check_colors_and_gradients(root, violations, cfg, parent_map)
    check_stroke_width(root, violations, cfg)
    check_forbidden_content(root, violations)

    check_margin(root, parent_map, violations, cfg)
    check_dimensions_warn(root, violations)
    check_precision(root, violations)
    check_linecap_join(root, violations)

    return violations


# ---------------------------------------------------------------------------
# Check-id reference table (for --help / documentation use)
# ---------------------------------------------------------------------------

CHECK_TABLE = [
    ("XML001", "FAIL", "SVG must be well-formed XML"),
    ("XML002", "FAIL", 'root element must be <svg xmlns="http://www.w3.org/2000/svg">'),
    ("VIEWBOX001", "FAIL", 'viewBox must be exactly "0 0 <canvas> <canvas>" for the campaign canvas'),
    ("COLOR001", "FAIL", "fill/stroke/stop-color values must be in the campaign's allowed palette (or none / url(#id))"),
    ("GRADIENT001", "FAIL", "only linearGradient elements with a campaign-whitelisted id may be defined (none, if the campaign declares no palette.gradients)"),
    ("GRADIENT002", "FAIL", "every url(#id) color reference must resolve to a defined allowed gradient"),
    ("GRADIENT003", "FAIL", "campaign-only: a gradient's <stop> colors must match the stops declared for its id in palette.gradients"),
    ("STROKE001", "FAIL", "effective stroke-width must be within the campaign's stroke.main range wherever stroke is not none; dashed construction-colored lines use the campaign's stroke.construction range; not evaluated at all when the campaign declares no stroke.main"),
    ("FORBID001", "FAIL", "forbidden element (text/tspan/image/foreignObject/script/style/filter/fe*/animate*)"),
    ("FORBID002", "FAIL", "inkscape/sodipodi/adobe namespaced element or attribute present"),
    ("FORBID003", "FAIL", "href/xlink:href references outside the document"),
    ("FORBID004", "FAIL", "data: URI present"),
    ("MARGIN001", "FAIL", "content bbox larger dimension is outside the campaign's qc.occupancy_fail bounds (margin collapsed, or content too small) relative to the campaign canvas"),
    ("DIM001", "WARN", "root <svg> has width/height attributes"),
    ("MARGIN002", "WARN", "content bbox larger dimension outside the campaign's recommended qc.occupancy_warn range"),
    ("MARGIN003", "WARN", "content bbox center offset from canvas center exceeds the campaign's qc.center_offset_max"),
    ("PREC001", "WARN", "numeric precision beyond 2 decimal places"),
    ("LINECAP001", "WARN", "stroke-linecap/linejoin present but not in {butt, miter, round}"),
]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_arg_parser():
    p = argparse.ArgumentParser(
        prog="qc_svg.py",
        description="Deterministic QC gate for OpenIllust campaign SVG assets. "
                     "Validates only; never modifies input files.",
    )
    p.add_argument("files", nargs="*", help="SVG file(s) to validate")
    p.add_argument("--dir", help="Validate all *.svg files in DIR (non-recursive)")
    p.add_argument("--strict", action="store_true",
                    help="Promote WARN-level violations to FAIL")
    p.add_argument("--json", action="store_true",
                    help="Emit a machine-readable JSON report instead of text")
    p.add_argument("--campaign", required=True,
                    help="Path to a campaign.yaml (see references/campaign-schema.md).")
    return p


def main(argv=None):
    parser = build_arg_parser()
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from campaign import load_campaign, CampaignError  # lazy: avoid requiring PyYAML at import time
    try:
        campaign = load_campaign(args.campaign)
    except CampaignError as exc:
        sys.stderr.write("qc_svg.py: error: %s\n" % exc)
        return 2
    cfg = build_config(campaign)

    targets = list(args.files)
    if args.dir:
        if not os.path.isdir(args.dir):
            sys.stderr.write("qc_svg.py: error: --dir path not found: %s\n" % args.dir)
            return 2
        targets.extend(sorted(
            os.path.join(args.dir, fn)
            for fn in os.listdir(args.dir)
            if fn.lower().endswith(".svg") and os.path.isfile(os.path.join(args.dir, fn))
        ))

    if not targets:
        sys.stderr.write("qc_svg.py: error: no input files given (pass FILE... or --dir DIR)\n")
        return 2

    reports = []
    io_error = False
    for path in targets:
        if not os.path.isfile(path):
            sys.stderr.write("qc_svg.py: error: file not found: %s\n" % path)
            io_error = True
            continue
        try:
            violations = check_svg(path, cfg)
        except Exception as exc:  # defensive: never crash the whole run on one bad file
            sys.stderr.write("qc_svg.py: error: unexpected failure reading %s: %s\n" % (path, exc))
            io_error = True
            continue

        if args.strict:
            for v in violations:
                if v["level"] == "WARN":
                    v["level"] = "FAIL"

        passed = not any(v["level"] == "FAIL" for v in violations)
        reports.append({"file": path, "pass": passed, "violations": violations})

    if args.json:
        sys.stdout.write(json.dumps(reports, indent=2) + "\n")
    else:
        for r in reports:
            fail_count = sum(1 for v in r["violations"] if v["level"] == "FAIL")
            warn_count = sum(1 for v in r["violations"] if v["level"] == "WARN")
            status = "PASS" if r["pass"] else "FAIL"
            print("%s: %s (fail=%d, warn=%d)" % (status, r["file"], fail_count, warn_count))
            for v in r["violations"]:
                print("  [%s] %s: %s" % (v["level"], v["check"], v["detail"]))

    if io_error:
        return 2

    all_pass = all(r["pass"] for r in reports)
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
