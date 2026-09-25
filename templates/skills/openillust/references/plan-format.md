# Vectorization Plan — Format & Rules

The plan is the approval artifact of the freeform flow (`/opil:vectorize`) and the composition
flow (`/opil:compose`). The agent analyzes the source — an arbitrary image, or a derivation brief
plus the campaign's approved assets — against the campaign contract and proposes this document;
the user approves (possibly with edits); only then does execution start. Sheet mode skips this —
its manifest is a pre-approved plan.

## File

`.openillust/campaigns/<campaign>/plans/YYYY-MM-DD-<slug>.md`, front-matter:

```yaml
---
campaign: <name>
source: <image path>          # copied into the campaign workspace for provenance
status: proposed | approved | executed
---
```

`status` is the state marker (directory-as-state): `/opil:vectorize` re-invoked resumes from it.

## Body structure

```markdown
# Vectorization Plan — <source name>

## Assets
| # | Asset | Region (x,y,w,h) | Route | Output | Notes |
|---|-------|------------------|-------|--------|-------|
| 1 | logo mark | 240,390 x 190,190 | parametric | logo-mark.svg @1024 | frame + dot, 2 shapes |
| 2 | wordmark "OpenGoal" | ... | typeset | wordmark.svg | font? -> open question |
| 3 | tagline + captions | ... | exclude | - | document text, not an asset |
| 4 | background texture | full | drop | - | |

## Palette map (source -> campaign)
| source color | maps to | role |

## Open questions
- (anything the user must answer before execution — fonts, ambiguous regions, output names;
  each SHOULD carry a default so silence does not block — see Approval)
```

## Routes (the core judgment — one per asset)

| Route | When | Execution |
|---|---|---|
| **parametric** | simple/geometric shapes (few primitives, exact curves beat tracing) | hand-authored clean geometry; measure with `trace_skeleton.py` / `measure_bands.py`; self-check with `render_overlay.py`; $0 |
| **vectorize** | organic/complex flat art faithful reproduction | crop region → `vectorize.py` (provider: `recraft` API / `vtracer` local) → `svg_normalize --map` → QC |
| **typeset** | ANY text (wordmarks, labels) | re-set with the real font — **text is never traced**; if the font is unknown, it is an open question or the asset is excluded |
| **exclude** | captions, decorative text, non-assets | listed explicitly so the user sees what is left out |
| **drop** | backgrounds, shadows, textures | removed at normalize (`--drop-background`, `--drop-color`) |
| **reuse** | an APPROVED campaign asset needed as a component | referenced verbatim from the campaign (`icons/`, `anchors/`; must appear in `approvals.md`); translate/scale only — a recolor or path edit is a NEW asset (route it `parametric`) |
| **ingest** | an externally produced SVG (designer handoff) | `svg_normalize --campaign` (non-square targets via `--canvas WxH`) → QC — the converter is skipped |
| **compose** | a deliverable assembled from components (lockups, banners, social cards) | assembly recipe script (SVG output, gated by `qc_svg --strict --campaign --profile <type>`) or agent-authored HTML → `render_html.py` (raster output, exact-dimension + blank-render guard); components come from `reuse` / `typeset` / `parametric` rows |

Route defaults, overridable by the user at approval:
- counts of primitives ≤ ~6 and straight/arc geometry → parametric
- photographic / 3D-rendered / heavily textured content → warn: converter will produce artifacts
  (a stated limitation of the recraft provider; local tracing fares no better); propose exclude or a regenerated flat reference instead

## Compose-mode body (plans opened by `/opil:compose`)

A compose plan has no source image; its tables are deliverables and components:

```markdown
## Deliverables
| # | Output | Profile | Format | Components |
|---|--------|---------|--------|------------|
| 1 | lockup-horizontal.svg | lockup | svg | mark (reuse), wordmark (typeset) |
| 2 | readme-banner-dark.webp | banner | webp | lockup #1 (reuse), heading text (HTML/CSS) |

## Components
| Component | Route | Source / text | Notes |
|-----------|-------|---------------|-------|
| mark | reuse | icons/logo-mark.svg | approved (see approvals.md) |
| wordmark | typeset | "State Designer" | font → open question (default proposed) |

## Layout
- (per deliverable: assembly geometry for SVG, or the HTML recipe outline for raster)
```

Every deliverable names its `asset_profiles` profile — a campaign missing that profile gets an
open question PROPOSING canvas/format values, never an invented one. Raster deliverables use
agent-authored HTML rendered by `render_html.py`; text in raster deliverables may be CSS text
(the deliverable is pixels), while text in SVG deliverables is always typeset outlines.

## Approval

Approval is a state transition, not a chat vibe: the trigger is conversational, the record is
durable. There is no separate approve command — the agent is the interpreter, under these rules.

- **Affordance.** Every plan presentation MUST end by stating the exact approval keywords in the
  conversation language — e.g. "approve" / "proceed" (English), "승인" / "진행" (Korean) — and
  that any other reply is treated as modification instructions or questions. Positive sentiment
  ("looks good") is never approval.
- **Defaults.** On approval, unanswered open questions resolve to their stated defaults. A
  question without a default blocks only the assets that depend on it — the rest execute.
- **Mixed replies.** Edits plus a go-signal in one reply: apply the edits to the plan, record
  them, then proceed as approved. If an edit is ambiguous, ask — never guess and execute.
- **Scope guard.** Approval binds only to the plan presented immediately before it in this
  conversation. A go-word in any other context never starts execution. On session resume,
  re-present the plan summary and the affordance before accepting approval.
- **Durable write.** On approval: set `status: approved` in the front-matter, resolve defaults
  into the plan body, and append to the campaign's `approvals.md` ledger — date, plan path, the
  user's approving utterance quoted verbatim (any language), and the defaults resolved. Ledger
  field values stay in English; only the utterance is quoted as-is.

These semantics govern every owner-approval moment in the workflow — freeform plans, sheet cell
manifests, review promotions — not only this document.

## Hard rules

1. **No execution before `status: approved`.**
2. **Text is never traced** — typeset or exclude, no third option.
3. Every produced asset gets provenance (`prompt-used.txt` or plan reference) and passes
   `qc_svg.py --strict` under the campaign contract (per-asset profile canvas, e.g. logo @1024).
4. Region crops that feed the converter must be ≥256px on the short side (API minimum) — upscale
   from the source if needed, flag if the source is too small for quality.
5. The plan lists EVERYTHING visible in the image — assets, exclusions, drops — so approval is
   informed; nothing is silently ignored.
6. **Recipes are provenance.** Every script that produced a derived asset (assembly, typeset
   invocation, HTML render) is copied beside the plan in `plans/` BEFORE the plan is set
   `status: executed` — a deliverable whose recipe lives only in a session scratchpad is not
   done.
7. **Reused components are never mutated** — translate/scale only, and only assets recorded as
   approved in `approvals.md` may be reused.
