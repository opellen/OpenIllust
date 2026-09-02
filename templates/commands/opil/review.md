---
description: Walk the approval loop over QC-passed assets
argument-hint: ""
---

# /opil:review

Load the `openillust` skill BEFORE doing anything else.

## Constraints

- Only QC-passed assets are reviewable; never present an asset that skipped the gate.
- Verdicts are recorded append-only in `.openillust/campaigns/<c>/approvals.md`
  (`YYYY-MM-DD <slug> approved|rejected [note]`) — the interim ledger until `build_manifest.py`
  exists. Never rewrite history lines.
- Anchor promotion requires an explicit owner "yes" per asset.

## Steps

1. Resolve the active campaign. Enumerate pending assets: QC-passed entries in the preview whose
   slug has no `approved` line in `approvals.md`.
2. Point the owner at the preview page (16–128px ramp) and surface the agent's own self-check
   notes FIRST (e.g. "the dot may blur at 16px") — the owner should not have to find what the
   agent already saw.
3. Walk verdicts per asset:
   - **approved** → record in `approvals.md`; ensure the SVG sits in `.openillust/campaigns/<c>/icons/`;
     ask once whether to promote it to `anchors/` (recommend for the first approvals of a
     campaign or family).
   - **rejected** → capture the specific feedback in the ledger and queue it; afterwards suggest
     `/opil:redo <slug>` per rejected asset.
4. Report: approved / rejected / still-pending counts, anchors promoted, and the single next step
   (`/opil:redo` if rejections exist, else the next `/opil:sheet` family or `/opil:status`).
