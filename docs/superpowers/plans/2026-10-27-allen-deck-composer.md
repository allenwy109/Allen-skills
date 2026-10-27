# Allen Deck Composer Execution Design

**Goal:** Turn an accepted semantic blueprint and its three accepted planning records into finished, evidence-led deck pages without changing `report-forge`.

**Interface:** `out_deck.py compose <task>` calls `allen_compose.py`. The composer reads `deck-blueprint.json` plus `obs/chart-plan.json`, `obs/layout-plan.json`, and `obs/module-fill-plan.json`; every plan must bind the current blueprint SHA-256. It writes only `deck-work/pages.html`, `deck-work/page.css`, and `deck-work/.allen/composition-manifest.json`.

**Selection:** Page semantics choose among `trend-bars`, `comparison-matrix`, `roadmap`, and `evidence-quote`, with four distinct page skeletons. The manifest records the chosen form, layout, evidence references, and source locators. A three-page window may not repeat one skeleton.

**Failure behavior:** Missing or stale plans, unsupported capacity, unsafe content, missing evidence bindings, or a repeated three-page skeleton fail before writing output. Text and attributes are escaped; SVG is renderer-owned.

**Success criteria:** deterministic output; at least four forms and four layouts in the fixed benchmark; sources appear beside evidence; a single-source deck has no sparse references page; formal compile has no preview marker; HTML/PDF geometry passes; existing lifecycle and capability tests remain green.
