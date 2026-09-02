# PNG→SVG Vectorization Survey (2026-08-23)

Goal: production-grade conversion of flat icon/illustration raster art into clean SVG
("sharp edges, noise removed, shapes preserved" — professional-designer level).
Local hardware constraint: Windows 11, RTX 4060 Laptop 8GB VRAM, 24GB RAM.
Already evaluated in-session: vtracer (fast, wobbly curve-soup), StarVector-8B (needs 16GB+),
Vectorizer.AI (commercial benchmark, ~$10/mo), Recraft (hybrid gen+vectorize).
Survey by research subagent; key hardware claim (OmniSVG VRAM) independently verified
against the official README by main on 2026-08-23.

> **Outcome (2026-09-02):** this survey informed the production decision — Recraft API as the
> primary vectorizer, with local vtracer as the free/keyless alternative (both now behind
> `vectorize.py --provider`). Pricing and model claims below are an August 2026 snapshot.

## Track 1 — HuggingFace models (image-to-SVG)

| Model | Notes | VRAM | Verdict for us |
|---|---|---|---|
| **OmniSVG 1.1** (8B/4B, 3B legacy) | Qwen-VL-based; text- and image-to-SVG; trained on 904K icons + 255K illustrations (NeurIPS 2025); paper claims it beats StarVector on complex illustrations (self-claim). Apache-2.0, weights released, active (Dec 2025). | **17GB (4B/3B), 26GB (8B) — verified from official README** | Best conceptual fit, but did not fit 8GB; the rented-cloud-GPU batch path was later superseded by the Recraft/vtracer provider integration. |
| StarVector-1B | Icons benchmark 0.975 vs 8B's 0.984 — icons hold up at 1B. Apache-2.0. | fits 8GB | Runnable today but research-grade output. |
| InternSVG-8B (Oct 2025) | InternViT + Qwen2.5-7B; 16M-sample dataset incl. icons. No icon benchmarks surfaced; very new. | ~16GB+ (inferred) | Not runnable locally; too unproven. |
| DuetSVG, Reason-SVG (CVPR 2026) | Paper-only; no code/weights found. | — | Watch list. |

## Track 2 — Research algorithms with public code

| Method | What it does | Windows feasibility | Verdict |
|---|---|---|---|
| **LIVE** (CVPR 2022 Oral) | Layer-wise vectorization: progressively adds few, clean, closed Bézier layers (5 paths vs 256 for naive diffvg on a demo) — design goal matches "flat icon, few clean shapes" exactly. Apache-2.0 + commercial-contact clause; frozen research code. | Depends on diffvg — **Windows build confirmed painful** (manual setup.py/C++ workarounds, GitHub issue #71). | Closest conceptual match; setup-cost risk. |
| **Optimize & Reduce** (AAAI 2024) | Top-down successor to LIVE: optimize Béziers then reduce shape count; emoji-tested; MIT. Docker setup provided (sidesteps native diffvg build if Docker+GPU passthrough works). | Docker path plausible | Most practical of the diffvg family; code frozen (3 commits). |
| PyTorch-SVGRender | Maintained toolkit bundling diffvg/LIVE/CLIPasso/VectorFusion etc. MPL-2.0, active. | Same diffvg caveat | Entry point if we go the research route. |
| SAMVG (2023) | SAM-guided vectorization — paper only, **no usable code**. | — | Not usable. |
| Chat2SVG / LLM4SVG (CVPR 2025) | Text-prompt-driven SVG generation/understanding — **not raster vectorizers**. | — | Modality mismatch. |
| diffvg | The underlying differentiable rasterizer (infrastructure). | Painful native build; issue #71 | Dependency only. |

## Track 3 — Classical tools beyond vtracer

| Tool | Notes | Verdict |
|---|---|---|
| potrace | B/W only, upstream dead (last release 2019). | Superseded. |
| **autotrace** | Actively maintained (Windows CI + installers); **centerline tracing** — structurally different from outline tracers; quality for flat icons unproven. | Cheap local experiment. |
| Vector Magic Desktop | Strong Bézier fitting on logos/line art per 2026 reviews; $295 one-time (online $5.49/mo); reviewers say alternatives have caught up. | Overpriced vs Vectorizer.AI. |
| Inkscape Trace | potrace-based; rounds corners excessively per user reports. | Not competitive. |

## Track 4 — Commercial services beyond Vectorizer.AI / Recraft

| Service | Notes | Verdict |
|---|---|---|
| Kittl Vectorizer | Mature platform, Pro $12–15/mo; no standalone vectorization API confirmed; marketing-only quality claims. | Secondary option. |
| **SVG AI (svgai.org)** | Claims "semantic shape recognition, not pixel-edge tracing", low anchor counts, icon showcases; **free tier, no signup** — cheap to test. Algorithm undisclosed. | Free A/B candidate. |
| PerfectVector | Free; self-ranked #1 for icons (conflict of interest — its own blog). | Free A/B candidate, low weight. |
| VectorArt.ai | Generation-centric hybrid; API via sales contact. | Skip for now. |
| PicWish | Vectorization capability could not be confirmed to exist. | Skip. |
| Long tail (vectorizer.io etc.) | Mostly vtracer/potrace-class wrappers. | Skip. |

## Shortlist

**Local (8GB constraint):** ① LIVE (best conceptual match, diffvg build risk), ② Optimize&Reduce
(Docker path, MIT), ③ autotrace (maintained, centerline — unproven quality hypothesis).

**Service:** ① Vectorizer.AI (benchmark; free preview before paying), ② SVG AI free tier (semantic-shape
claims worth one test). Kittl as backup. OmniSVG-4B on a rented cloud GPU is the "open-model batch"
fallback if services disappoint.

## Caveats

- OmniSVG/SVG AI/PerfectVector quality claims are self-published — treat as claims.
- No published VRAM figures for the diffvg-family methods (small optimization problems; plausible on 8GB, unverified).
- Chat2SVG/LLM4SVG excluded on modality (text-driven), SAMVG on missing code, PicWish on unconfirmed capability.
