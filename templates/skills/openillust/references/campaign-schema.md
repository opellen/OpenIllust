# campaign.yaml — Schema

The machine-readable contract of a campaign. Produced by `/opil:init` (agent distills the
free-form design guide, user approves); consumed by `qc_svg.py`, `svg_normalize.py`,
`make_sheet_guide.py`, and the skill's plan/prompt procedures. Humans rarely edit it by hand.

```yaml
name: <campaign slug>                 # required
design_guide: <path>                  # required — the human style document this was distilled from

canvas: 512                           # required — viewBox size (square)

palette:                              # required
  allowed: ["#RRGGBB", ...]           # every hex QC accepts; includes backgrounds
  gradients:                          # optional — whitelisted gradient defs
    <id>: ["#start", "#end"]
  accent:                             # optional — accent color policy
    hex: "#RRGGBB" | null             # null = adopted but not yet chosen
    scope: dots-handles               # free text, used by prompt/plan procedures

stroke:                               # required for stroke-using styles
  main: { width: [min, max] }         # px at canvas scale
  construction:                       # optional exception lane
    color: "#RRGGBB"
    requires_dash: true
    width: [min, max]

qc:                                   # required — gate thresholds (fractions of canvas)
  occupancy_warn: [0.68, 0.82]        # content bbox larger-dimension warn band
  occupancy_fail: [0.50, 0.86]        # hard bounds
  center_offset_max: 0.06

normalize:                            # optional — svg_normalize defaults
  margin: 0.13
  min_area_ratio: 0.00002             # speckle filter; small enough to keep dashed segments

prompt:                               # required for sheet mode
  palette_rules: |                    # verbatim lines injected into the sheet prompt
    ...
  style_rules: |                      # perspective/geometry lines
    ...
  avoid: |                            # the campaign avoid-block, copy-paste-able
    ...

asset_profiles:                       # consumed by the freeform plan flow (not by QC yet)
  icon:  { text: forbidden }
  logo:  { text: allowed, canvas: 1024 }

tooling:                              # optional — execution defaults, NOT part of the style contract
  vectorizer: recraft                 # recraft (API, best quality, needs RECRAFT_API_KEY) | vtracer (local, free, keyless)
```

Rules:
- Unknown extra keys are allowed (campaigns differ); consumers read what they know.
- Style-aware scripts (`make_sheet_guide`, `svg_normalize`, `qc_svg`) REQUIRE
  `--campaign <path to campaign.yaml>` — there are no built-in style defaults. Omitting
  `palette.gradients` allows no gradients; omitting `stroke.main` disables stroke checking.
- `dark_palette` and other campaign-specific extensions live as extra keys until a consumer needs them.
- `tooling.*` is advisory execution config, not contract. Vectorizer resolution: `--provider` flag > `OPENILLUST_VECTORIZER` env > `tooling.vectorizer` > `recraft`. A missing API key is an error, never a silent provider fallback. Pin one provider per asset family.
