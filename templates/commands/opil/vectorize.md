---
description: Convert an arbitrary image into contract-compliant vector assets (Plan → Approve → Execute)
argument-hint: "<image-path>"
---

# /opil:vectorize

Load the `openillust` skill BEFORE doing anything else.

## Constraints

- **No execution before the plan's front-matter reads `status: approved`.**
- **Text is never traced** — typeset with the real font or exclude; no third option.
- The plan lists EVERYTHING visible in the image (assets, exclusions, drops) so approval is informed.
- Converter inputs need ≥256px on the short side — upscale crops, flag hopeless sources.

## Steps

1. Resolve the active campaign (as in `/opil:sheet` step 1).
2. Copy the source image into `.openillust/campaigns/<c>/refs/sources/` (provenance) and view it.
3. Analyze against the campaign contract and write
   `.openillust/campaigns/<c>/plans/YYYY-MM-DD-<slug>.md` per `references/plan-format.md`
   (`status: proposed`): per-asset table with route
   (`parametric | vectorize | typeset | exclude | drop`), regions, outputs (with per-type canvas
   from `asset_profiles`), palette map, open questions.
4. Present the plan. Iterate on owner feedback; on approval set `status: approved`.
5. Execute per asset by route:
   - `vectorize`: crop region → `vectorize.py` → `svg_normalize.py --campaign --map` →
     `qc_svg.py --strict --campaign`
   - `parametric`: measure (`trace_skeleton.py`, `measure_bands.py`) → hand-author → self-check
     (`render_overlay.py`) → QC
   - `typeset`: real font only (an unanswered font question blocks that asset, not the others)
   - `exclude` / `drop`: skip, but keep them listed in the plan
6. Add preview entries, report per-asset results + cost, set `status: executed`.
7. Hand off with a single next step: `/opil:review`.

A re-invocation resumes from the plan's `status` — proposed: continue the approval conversation;
approved: execute; executed: report and point at `/opil:review` or `/opil:redo`.
