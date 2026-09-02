---
description: Regenerate a single rejected asset with anchor chaining
argument-hint: "<slug> [feedback]"
---

# /opil:redo

Load the `openillust` skill BEFORE doing anything else.

## Constraints

- One asset per invocation — never batch rework.
- Archive the current SVG to `.openillust/campaigns/<c>/refs/<slug>/history/` before overwriting anything.
- The reworked asset must pass `qc_svg.py --strict --campaign` before the preview updates.

## Steps

1. Resolve the active campaign; locate the asset's origin and provenance — a sheet cell (search
   `sheets/*/manifest.txt` for the slug) or a plan asset (search `plans/*.md`).
2. Choose the rework route: the original route by default; the owner's feedback can override it
   (e.g. "vectorizer mangled the curves" → `parametric`; "shape is wrong" → regenerate the raster).
3. Regenerate the single asset with **anchor chaining**: make the approved anchors plus the
   nearest approved family member visible at generation, per `references/prompt-rules.md`. If a
   new raster is needed, hand the owner a single-asset generation package (prompt + attachments +
   save path) and resume when the file lands.
4. Normalize → QC → self-check overlay (`render_overlay.py`, use `--zoom` on the area the feedback
   pointed at) → update the preview entry in place.
5. Report what changed against the previous version (kept in `history/`), and hand off to
   `/opil:review`.
