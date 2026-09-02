---
description: Campaign dashboard — production state at a glance
argument-hint: "[campaign-name]"
---

# /opil:status

Load the `openillust` skill BEFORE doing anything else.

## Steps

1. Resolve the target campaign (argument, or the single existing one; several without an
   argument → show one summary line each).
2. Derive state from the filesystem (no separate database):
   - **Approved**: `approved` lines in `.openillust/campaigns/<c>/approvals.md`
   - **Awaiting review**: preview entries without an approval line
   - **Sheets in flight**: each `sheets/<slug>/` classified by its contents
     (manifest only → awaiting generation; sheet.png → awaiting processing; crops+SVGs → awaiting
     review)
   - **Plans**: each `plans/*.md` by front-matter `status` (proposed / approved / executed)
   - **Contract gaps**: open items in `campaign.yaml` (e.g. `palette.accent.hex: null`),
     missing `.env` key
3. Report as a compact table plus ONE recommended next action (decisive, not a menu): the oldest
   blocking wait state first (owner generation > owner review > contract gap > next family).
