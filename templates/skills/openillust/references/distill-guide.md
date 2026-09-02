# Distilling a Design Guide into campaign.yaml

The procedure `/opil:init` follows. The design guide is a free-form human document of any shape
and origin (ChatGPT output, agency PDF-to-md, hand-written); `campaign.yaml` is the fixed-schema
machine contract. **The agent is the format adapter** — this doc is how it adapts.

## Procedure

1. **Discover the guide.** Glob candidates (`*design-guide*`, `*style-guide*`, `*brand*`,
   `*visual*` under `docs/`, `design/`, repo root). One hit → confirm; several → ask which;
   none → ask for a path, or offer to co-write one from the template
   (`templates/skills/openillust/references/design-guide-template.md`).
2. **Read it fully.** Never distill from a skim — avoid-lists and exception clauses hide at the end.
3. **Extract, field by field** (schema: `templates/skills/openillust/references/campaign-schema.md`):

   | Field | How to extract |
   |---|---|
   | `palette.allowed` | EVERY hex in the guide, including backgrounds and gradient stops. Never invent a color — each entry must be traceable to a guide line or an explicit user answer. |
   | `palette.gradients` | only gradients the guide *defines* (id + stops); decorative gradient prose is not a definition |
   | `palette.accent` | an explicitly designated accent/highlight color + its usage scope; absent → omit the key (do not assume campaigns want one) |
   | `canvas` | the guide's stated viewBox/canvas; absent → propose 512 (icon default), flag in the interview |
   | `stroke.*` | stroke widths; convert relative specs ("1.5–2.5% of width") to px at `canvas`; a distinct guide/construction line style becomes the `construction` exception lane |
   | `qc.*` | derive from margin/occupancy statements: margin range `[a,b]` → `occupancy_warn: [1-2b, 1-2a]`; absent → propose defaults `warn [0.68,0.82] / fail [0.50,0.86] / center 0.06` and say so |
   | `normalize.*` | defaults (`margin` = midpoint of guide margin range; `min_area_ratio 0.00002`) unless the guide implies otherwise |
   | `prompt.palette_rules` | 2–5 imperative lines mapping colors to roles, written FROM the guide's own role language, hex-exact |
   | `prompt.style_rules` | the guide's geometry/perspective/composition rules as imperative bullets |
   | `prompt.avoid` | the guide's avoid/never list, near-verbatim, as one paste-able block |
   | `asset_profiles` | text policy per asset type (icons: text forbidden is the safe default), per-type canvas overrides (logo often larger) |

4. **Gap interview.** For every required field the guide does not answer, ask the user —
   batched, concrete, with a proposed default per question. Typical gaps: no explicit palette
   hexes, no canvas, no avoid-list, accent ambiguity, dark-mode variants.
5. **Propose.** Show the drafted yaml with a per-field source note ("palette: guide §4;
   qc: defaults — guide silent"). The user approves or edits; **no campaign work runs before
   approval.**
6. **Write & scaffold.** `.openillust/campaigns/<name>/campaign.yaml` + workspace dirs
   (`anchors/ refs/ sheets/ plans/ icons/ preview/`) + `.env` check (API key prompt if absent).
7. **Resync.** When the guide changes later, re-run distillation and present a field-level diff
   against the current yaml — the guide remains the human authority; the yaml never drifts
   silently.

## Principles

- **Never invent style.** Every value is guide-sourced or user-answered; defaults are labeled as
  defaults in the proposal.
- **Distill, don't copy.** The yaml holds decisions, not prose; long rationale stays in the guide.
- **Unknown extras welcome.** Campaign-specific structures (e.g. `dark_palette`) go in as extra
  keys — consumers read what they know.
- **The interview is part of the product.** A thin guide plus ten good questions yields a valid
  contract; refusing to proceed on a thin guide is wrong, silently guessing is worse.
