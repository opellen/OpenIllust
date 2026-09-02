---
description: Create or resync a campaign — distill its design guide into campaign.yaml
argument-hint: "[campaign-name]"
---

# /opil:init

Load the `openillust` skill BEFORE doing anything else.

## Constraints

- Never write `campaign.yaml` without the owner's explicit approval of the proposed contract.
- Never invent style values — every field is guide-sourced, user-answered, or a labeled default
  (see the skill's core rules and `references/distill-guide.md`).
- Never print API keys.

## Steps

1. Resolve the target campaign name from the argument (slug). If `.openillust/campaigns/<name>/campaign.yaml`
   already exists → **resync mode**: re-run the distillation against the (possibly changed) design
   guide and present a field-level diff against the current yaml; apply only on approval. Otherwise
   **create mode**.
2. Follow `references/distill-guide.md` end to end: discover the design guide (glob candidates →
   confirm/ask) → read it fully → extract every schema field
   (`templates/skills/openillust/references/campaign-schema.md`) → run the gap interview (batched questions, each with
   a proposed default).
3. Present the proposed `campaign.yaml` with a per-field source note ("palette: guide §4;
   qc: defaults — guide silent"). Iterate until the owner approves.
4. On approval: write `.openillust/campaigns/<name>/campaign.yaml`; scaffold the workspace
   (`anchors/ refs/ sheets/ plans/ icons/ preview/`); check `.env` for `RECRAFT_API_KEY` and, if
   absent, tell the owner how to add it.
5. Report: contract summary (palette size, canvas, accent state, profiles), workspace path, and the
   single recommended next step (`/opil:sheet` for a set, `/opil:vectorize` for existing art).
