---
name: openillust
description: Produces contract-compliant vector assets (icons, logos, and related graphics) for any campaign, driven entirely by that campaign's campaign.yaml design contract -- sheet-based batch generation via gpt-image and provider-switchable vectorization (Recraft API or local vtracer), freeform plan-driven conversion of arbitrary source art, and parametric hand-authoring as a fallback, all gated by deterministic QC. Use when creating or revising assets through the /opil:* commands for an OpenIllust campaign.
---

# OpenIllust

OpenIllust turns a campaign's design language into a consistent set of contract-compliant vector
assets -- icons, logos, illustrations, and other graphics. It is the campaign-agnostic
generalization of a production-proven icon workflow: the same production machinery, driven by a
swappable per-campaign configuration instead of values baked into code or prompts.

This skill is the shared brain: tool usage, QC philosophy, and prompt rules that hold across every
campaign. It is loaded by six `/opil:*` commands -- `init`, `sheet`, `vectorize`, `redo`, `review`,
`status` -- which own the workflow entry points and step-by-step state machines. This file states
principles and tool knowledge; it does not reproduce command procedures.

## The campaign contract

Every campaign lives under `.openillust/campaigns/<name>/`, anchored by `campaign.yaml` -- the single
machine-readable authority for that campaign's palette, canvas size, stroke rules, QC thresholds,
and prompt language (schema: `templates/skills/openillust/references/campaign-schema.md`). `/opil:init` distills it
once from a free-form human design guide (procedure: `references/distill-guide.md`); after that,
`campaign.yaml` is what every prompt, script, and QC check reads.

**Never hardcode style values.** Do not write a hex code, canvas size, stroke width, or avoid-list
line into a prompt, an SVG, or a judgment call from memory or a previous campaign. Always read it
from the active campaign's `campaign.yaml` (`palette.allowed`, `palette.gradients`,
`palette.accent`, `canvas`, `stroke.*`, `prompt.*`, `asset_profiles.*`). A field the campaign
doesn't answer is a gap for `/opil:init`'s interview, not something to invent.

## Core rules

- The agent writes every creative prompt itself -- raster prompts, sheet-guide prompts, plan
  documents. Scripts never draw product art; they build kits, convert, normalize, validate, and
  render checks only.
- QC (`qc_svg.py`) is a gate, not a fixer. FAIL means rework the SVG or regenerate the reference,
  then re-run -- never silently patch geometry to satisfy a numeric check while violating its intent.
- Provenance is mandatory. Every asset traces to a `prompt-used.txt` (sheet/raster route) or a plan
  reference (`.openillust/campaigns/<c>/plans/*.md`, freeform route). An asset without provenance cannot be
  approved.
- One asset per generation, except sheets -- a sheet is a deliberate batch of one family's cells in
  a single generation, sliced afterward by `crop_sheet.py`.
- One vectorizer provider per asset family. Provider choice (campaign.yaml `tooling.vectorizer`; recraft API or local vtracer) is execution tooling, not style contract -- but a mid-family swap can shift curve texture in ways QC does not measure, so pin it for the family's lifetime.
- Self-check before showing the owner. Run `render_overlay.py` against the SVG and its reference and
  correct visible deviations yourself; do not spend the owner's review cycle on flaws you could have
  caught.
- Clean-room: never open, copy, or show third-party artwork to any model. Visual references shown at
  generation time must be campaign-owned assets -- approved anchors, prior family members, or the
  campaign's own concept art.
- Accent policy comes from `palette.accent` in `campaign.yaml` (a hex plus a usage scope, e.g.
  "dots-handles"). If `accent.hex` is `null`, the campaign has adopted an accent slot but not chosen
  a color yet -- do not invent one.

## Reporting to the owner

Owner-facing reports -- plan presentations, execution reports, QC results -- are built for
decision-making, not record-keeping. Records live in files; the chat carries what changes the
owner's next action. Report in the conversation language, and use markdown structure (lists,
tables, an ASCII diagram where it helps) so the report scans at a glance. Structure every
substantive report in this order:

1. **Decision needed** -- what the owner must decide now, ending with the approval affordance
   (`references/plan-format.md`, Approval section) when a go/no-go is requested. When reporting
   results only, say "no decision needed" explicitly.
2. **Deliverables** -- a table of what was produced: asset, file path, QC status. Every artifact,
   record, or recipe mentioned anywhere in the report carries its file path; "recorded in the
   plan" without a path is a defect.
3. **Rationale** -- the judgments behind the proposal or result, as bullets or a table with one
   point per row, each traceable to its contract clause. Never pack independent arguments into a
   single inline-enumerated paragraph.
4. **Records** -- one pointer line: "Process details: `<path>`". Retries, transient QC failures,
   and tooling notes go in the file, not the chat.

Promotion rule: a workaround that masks a product limitation (e.g. a QC check satisfied via a
temporary contract copy) is not a process detail -- it is a defect. Report it under Rationale
explicitly; never bury it in Records.

Terminology: plain words. Introduce a tool or model name once with a one-line gloss ("image
generation (gpt-image)"), then refer to it generically. QC rule IDs and other technical codes
belong in the Records layer unless the owner must act on them.

## Production routes

Three ways to get from a campaign to an approved asset. Each is owned by a command; this section
only orients.

**Sheet pipeline (primary).** Batch-produce a family of related assets in one generation:
`make_sheet_guide.py` builds a layout guide and prompt from `campaign.yaml` and a cell manifest ->
the owner generates the sheet in gpt-image -> `crop_sheet.py` slices it into per-slug references ->
`vectorize.py` converts each (provider per `tooling.vectorizer`, default recraft) -> `svg_normalize.py --campaign` bakes it onto the contract
canvas -> `qc_svg.py --strict --campaign` gates it -> preview -> owner approval. Owned by
`/opil:sheet`; raster-prompt rules in `references/prompt-rules.md`.

**Freeform plan pipeline.** For an arbitrary source image that doesn't map to a sheet: the agent
proposes a per-asset plan -- route (`parametric` | `vectorize` | `typeset` | `exclude` | `drop`),
palette map, outputs -- the owner approves it, then execution reuses the same convert/normalize/QC
chain (or hand-authoring, for the parametric route). No execution before `status: approved`. Owned
by `/opil:vectorize`; format and rules in `references/plan-format.md`.

**Parametric fallback.** For single hero assets, logos, or geometry the vectorizer mangles, and for
any plan asset routed to `parametric`: hand-author the SVG directly. Measure the reference with
`trace_skeleton.py` (vertex skeletons) and `measure_bands.py` (color-band boundaries) instead of
eyeballing, then self-check with `render_overlay.py` before QC. SVG-authoring rules in
`references/prompt-rules.md`; reached through `/opil:vectorize`'s parametric route, or `/opil:redo`
when reworking a single rejected asset.

## Tool roster

All scripts are pure Python (Pillow / svgelements / vtracer, no GPU) under `scripts/`.

| Script | Input -> Output | Job | `--campaign` |
|---|---|---|---|
| `make_sheet_guide.py` | manifest -> `guide.png` + `prompt.txt` | Builds the sheet kit: a layout-only guide image plus a paste-ready generation prompt, with palette/style/avoid pulled from the campaign | yes |
| `crop_sheet.py` | sheet PNG + manifest -> per-slug `reference.png` | Slices the generated sheet on its grid, trims bleed, upscales to the API minimum, writes provenance | no |
| `vectorize.py` | reference PNG -> raw SVG | Provider-switchable raster-to-vector conversion (`recraft` API / `vtracer` local), no creative judgment | tooling default only |
| `svg_normalize.py` | raw SVG -> contract SVG | Snaps colors to the campaign palette, bakes geometry onto the campaign canvas with margin, drops junk, strips metadata | yes |
| `qc_svg.py` | SVG -> PASS/FAIL + violations | The contract gate: palette/gradient whitelist, canvas, stroke widths, occupancy/centering, forbidden content, all read from the campaign | yes |
| `render_overlay.py` | SVG (+ reference) -> overlay PNG | Headless render composited against the reference; the agent's self-check before QC or owner review | no |
| `trace_skeleton.py` | raster -> vertex skeletons | Measurement aid: each region's outline as a short vertex list, for parametric re-authoring, not final output | no |
| `measure_bands.py` | raster + axis -> band boundaries | Measurement aid: exact color-band extents along an axis, for parametric re-authoring | no |

## Failure handling

Two consecutive failed regenerations of the same asset (QC fail or visibly off-brand) -> stop and
report to the owner with the artifacts produced so far; do not keep burning attempts. If a rule here
conflicts with the active campaign's `campaign.yaml`, the campaign contract wins for style; this
file wins for cross-campaign procedure; the invoking `/opil:*` command wins for that route's
step-by-step sequencing.
