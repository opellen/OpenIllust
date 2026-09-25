---
description: Compose derived assets (lockups, banners) from approved components (Plan → Approve → Execute)
argument-hint: "<deliverable brief, or an existing plan slug to resume>"
---

# /opil:compose

Load the `openillust` skill BEFORE doing anything else.

## Constraints

- **No execution before the plan's front-matter reads `status: approved`.**
- **Reused components are never redrawn** — translate/scale only; a recolor or path edit is a
  NEW asset (route it to `parametric`, or bounce to `/opil:vectorize`).
- Only APPROVED campaign assets may be `reuse`d (check `approvals.md`).
- **Text in SVG deliverables is never traced** — typeset via `typeset_svg.py` with a real font.
  Text in raster deliverables may be CSS text (the deliverable is pixels).
- Raster deliverables: the agent authors the HTML/CSS; `render_html.py` renders it
  (exact size, blank-render retry) — scripts never draw.
- **Every recipe script is copied beside the plan BEFORE `status: executed`** — a deliverable
  whose recipe lives only in the session scratchpad is not done.

## Steps

1. Resolve the active campaign (as in `/opil:sheet` step 1).
2. Derive the slug from the argument; if `plans/*-<slug>.md` exists, resume from its `status`
   (proposed: continue approval; approved: execute; executed: report → `/opil:review`).
3. Inventory: approved assets (`icons/`, `anchors/` × `approvals.md`) as the component roster;
   `asset_profiles.<type>` for each deliverable's canvas/format — a missing profile is an open
   question (proposed values included), not an invention.
4. Write `plans/YYYY-MM-DD-<slug>.md` (`status: proposed`) per the compose-mode body in
   `references/plan-format.md`: deliverables table (output | profile | svg/webp/png), components
   table (route: `reuse <path>` | `typeset "<text>"` | `ingest <path>` | `parametric`), layout
   spec (SVG assembly geometry, or the HTML recipe outline for raster), open questions with
   defaults.
5. Present per the Approval section of `references/plan-format.md`; on approval set
   `status: approved`.
6. Execute per deliverable:
   - typeset parts → `typeset_svg.py --campaign --profile <type>` (font/fill from the plan)
   - SVG deliverable → author the assembly recipe script (components verbatim) → run →
     `qc_svg.py --strict --campaign --profile <type>` → self-check (`render_overlay.py`)
   - raster deliverable → author the HTML recipe → `render_html.py --size WxH [--webp]` →
     the script's exact-dimension check must pass
   - copy every recipe script beside the plan
7. Add preview entries, report per-deliverable results (cost: $0 — no converter calls), set
   `status: executed`.
8. Hand off with a single next step: `/opil:review` (SVG deliverables) / owner visual approval
   recorded in `approvals.md` (raster deliverables).
