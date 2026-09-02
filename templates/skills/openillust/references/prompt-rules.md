# Prompt Rules -- OpenIllust

Procedure rules for generating OpenIllust assets. Style facts (palette, geometry, stroke,
avoid-list) live in the active campaign's `campaign.yaml`, distilled from that campaign's design
guide -- this file never restates them; it tells the agent **how to prompt and author**. Workflow
sequencing (when to generate what, approval gates) lives in `SKILL.md` and the owning `/opil:`
command.

## Division of labor

1. **Raster concept reference** -- generated with gpt-image (best-in-class image quality). It is a
   *reference*, never the deliverable.
2. **SVG production** -- how the SVG comes to exist depends on the route. On the sheet pipeline and
   the vectorize-route of the freeform plan, `vectorize.py` converts the raster and
   `svg_normalize.py` bakes it onto the contract; the agent's job there is the raster prompt, the
   `--map` color decisions, and the self-check -- not manual authoring. On the parametric route
   (fallback lane, or any plan asset routed to `parametric`), the agent hand-writes the final SVG,
   informed by the raster reference and the campaign contract -- the SVG is the product and the
   single source of truth for that asset.
3. The agent writes every creative prompt itself. Scripts never draw product art; they only convert,
   validate (`qc_svg.py`), and assemble. Do not procedurally generate final asset geometry from code
   templates.

## Global rules -- every raster prompt

- Include a brand-essence / style-summary line and the relevant palette roles from the campaign's
  `prompt.palette_rules` (`campaign.yaml`) in the prompt text. Exact hex values from the campaign,
  not color names.
- One asset per image on this per-asset generation path. The sheet pipeline's manifest-driven
  multi-cell sheets are a separate, sanctioned mechanism owned by `/opil:sheet` and
  `make_sheet_guide.py` -- this rule does not apply to them.
- Square canvas sized to the campaign's `canvas` field. Background: the campaign's designated
  background color from `palette.allowed` (commonly a flat white) -- no gradient, no backdrop grid,
  no floor plane, no vignette, unless the campaign's `prompt.style_rules` says otherwise.
- Always append: "no text, no labels, no UI chrome, no watermark, no drop shadow, no reflection" plus
  the avoid-list block from the campaign's `prompt.avoid`.
- Describe the asset using the campaign's own style vocabulary (from `prompt.style_rules`), never
  "3D render", "realistic", or "logo mockup" -- unless the campaign's design guide explicitly calls
  for that register.

## Fixed vs variable -- state both, explicitly, in every prompt

- **Fixed (never varies across a campaign's assets):** the palette roles and hexes from
  `palette.allowed` / `prompt.palette_rules`, the geometry and perspective language from
  `prompt.style_rules` (whatever axis system, lighting convention, or projection the campaign's
  design guide specifies), the stroke weight from `stroke.main`, the margin from the campaign's
  stated margin, and any other constant the campaign contract states.
- **Variable (the only thing that changes):** the specific subject and the one
  action/transformation the asset depicts.
- Phrase it in the prompt: "Keep the palette, perspective, stroke weight, margin and surface style
  exactly as fixed per the campaign contract. Only the depicted subject changes:
  [SUBJECT + ACTION]."

## Visual reference handoff (consistency chaining)

- A file path string is **not** a reference. The reference image must be visibly present to the
  model (attached to the generation request / visible in context) immediately before generation.
- Once campaign anchors exist (`.openillust/campaigns/<c>/anchors/`), every generation shows 1-2 anchor assets
  first, with: "Use the assets just shown as the visual reference for style, palette, stroke weight,
  perspective and margin, per the campaign contract. Match them exactly. Change only the depicted
  subject."
- Within a family, chain from the first approved member of that family in addition to the campaign
  anchors.
- **Clean-room rule:** never show third-party artwork (a competitor's product, licensed art,
  anything not owned by the campaign) to any model, and never open those files. An inventory or
  brief contributes names/descriptions only.

## Raster reference prompt template

```
[STYLE DESCRIPTOR from the campaign's prompt.style_rules, e.g. "minimal flat geometric vector"]
[ASSET TYPE] for "[ASSET NAME]", [ONE-LINE CAMPAIGN CONTEXT].
Subject: [PRIMARY OBJECT -- the thing the asset depicts].
Action: [THE ONE TRANSFORMATION OR COMPOSITION, if applicable, expressed spatially].
[BRAND ESSENCE / STYLE SUMMARY -- from the campaign's design guide]
[PALETTE + SURFACE ROLE LINES -- campaign.yaml prompt.palette_rules, exact hex]
[GEOMETRY / PERSPECTIVE LINES -- campaign.yaml prompt.style_rules]
Solid flat [BACKGROUND COLOR from palette.allowed] background. Approximately
[MARGIN % from the campaign's margin setting] empty margin on all sides.
No text, no labels, no UI chrome, no watermark, no drop shadow, no reflection.
[AVOID-LIST BLOCK -- campaign.yaml prompt.avoid]
```

Fill the bracketed slots from the active campaign and the specific asset; keep the rest stable. Save
the exact prompt text used.

## SVG authoring rules (parametric route)

- Interpret the raster as **intent, not pixels**: do not trace. Rebuild the geometry as clean vector
  shapes -- integer or half-unit coordinates, the exact axes/geometry language from the campaign's
  `prompt.style_rules`, exact palette hexes from `palette.allowed`, gradient defs only from
  `palette.gradients`.
- Reuse anchor assets' structural conventions (axis directions, stroke width, margin box, gradient
  usage) verbatim -- copy the numbers from anchor SVGs or `stroke.main`, do not re-derive them per
  asset.
- Prefer `polygon`/`path` with straight segments; curves only when the subject itself is about arcs,
  circles, or rotation, per the campaign's geometry language. No editor metadata, no `text` (unless
  the asset's `asset_profiles.<type>.text` is `allowed`), no raster embeds.
- Deviation policy: if the raster reference conflicts with the campaign contract, **the contract
  wins**. Minor raster flaws (slight color drift, small decorations) are corrected silently in the
  SVG. Major flaws (wrong perspective, cluttered composition, off-brand look) mean regenerate the
  raster -- an off-brand reference must not remain the archived reference for an approved asset.
- After authoring, run `qc_svg.py --campaign <path to campaign.yaml>` (add `--strict` on the
  freeform route). A FAIL means rework or regenerate. Never bend geometry solely to satisfy a
  numeric gate while violating its intent (e.g. adding an invisible margin rect) -- gates are
  proxies for the contract.

## Provenance

- Raster references: `.openillust/campaigns/<c>/refs/<slug>/reference.png` + `.../prompt-used.txt` (exact
  prompt text, plus which anchors were shown).
- Freeform-route assets additionally trace to their plan: `.openillust/campaigns/<c>/plans/<date>-<slug>.md`.
- Final SVGs: `.openillust/campaigns/<c>/icons/<slug>.svg` (or the campaign's equivalent asset directory);
  authoring notes and QC result are recorded in the owning command's state tracking, not in the SVG.
- An asset without its prompt file or plan reference is not acceptable for approval.
