---
description: Batch-produce a family of assets via the sprite-sheet pipeline
argument-hint: "<family-name or asset list>"
---

# /opil:sheet

Load the `openillust` skill BEFORE doing anything else.

## Constraints

- The cell manifest requires owner approval before the kit is built.
- Any owner-supplied sheet image is COPIED into the sheet directory before processing (provenance).
- Every produced SVG must pass `qc_svg.py --strict --campaign` before it reaches the preview.
- The color `--map` for a sheet is a design decision: propose it, confirm with the owner when a
  source color's role is ambiguous.

## Steps

1. Resolve the active campaign: exactly one `.openillust/campaigns/*/campaign.yaml` → use it; several → ask;
   none → stop and suggest `/opil:init`.
2. Derive the sheet slug from the argument and read the state of
   `.openillust/campaigns/<c>/sheets/<slug>/` — the directory IS the state:

   **No `manifest.txt` → PLAN.** Draft the cell list (`slug | Title | one-object-one-action
   subject description`, rules in `references/prompt-rules.md`), grid shape (~9 cells, 3x3
   default; never starve per-cell resolution). Present for approval. On approval: write
   `manifest.txt`, run `make_sheet_guide.py --campaign`, then hand the owner the generation
   package: attachment list (guide.png, the campaign design guide, up to 2 approved anchors,
   campaign concept art), `prompt.txt` to paste, and the EXACT save path
   (`.openillust/campaigns/<c>/sheets/<slug>/sheet.png`).

   **Manifest + kit, no `sheet.png` → WAITING.** Remind the owner of the save path; if they give
   any other path, copy the file into place and continue.

   **`sheet.png` present, no crops → PROCESS.** `crop_sheet.py` → per-cell
   `vectorize.py` (report cost; provider from `tooling.vectorizer`, default `recraft`) → inspect the first raw SVG's colors and propose the
   sheet-wide `--map` → `svg_normalize.py --campaign` → `qc_svg.py --strict --campaign` →
   spot self-check with `render_overlay.py` → add preview entries → report per-cell results.

3. Hand off with a single next step: `/opil:review`.
