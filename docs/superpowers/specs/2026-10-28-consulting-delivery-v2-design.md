# Consulting Delivery V2 Design

## Goal

Turn Allen Skills from a technically valid research-report pipeline into a repeatable consulting engagement system that separates client communication from audit evidence, uses specialist research agents for L3 work, renders real A4-native exhibits, and rejects visually weak deliverables.

## Scope

This design applies to startup-idea, company, BP, topic, capital, ecosystem, and diligence workflows that produce formal reports. It preserves the current evidence ledger, research package, storyline, acceptance, HTML, and PDF infrastructure. It does not replace the deck pipeline or add speculative presentation formats.

The AIDC GPU pool task is the regression case, not a special-case implementation.

## Product Boundary

Every formal report task produces two customer-facing products:

1. `client-report/`: a concise HTML/PDF decision document. It contains conclusions, reasoning, exhibits, actions, brief limitations, and compact source markers. It does not contain full URLs, capture timestamps, source grades, research-process labels, or a full bibliography.
2. `evidence-package/`: a self-verifying directory and ZIP with source index, immutable snapshots, extracts, datasets, calculations, search logs, claim-evidence mappings, method records, review records, and a manifest.

The report and package share source and claim identifiers. Removing the bibliography from the report must not break traceability.

## A4 Report Architecture

A4 is a reading product, not a resized deck. The renderer owns an A4-specific layout catalog with ten initial archetypes: cover, executive summary, answer-and-reasons, pain comparison, competitor matrix, decision tree, mechanism/process, paired scenarios, 30/60/90 roadmap, and methods/limitations.

Each report component declares its semantic relationship and required rendered form. Components declared as charts, processes, timelines, matrices, scenarios, or decision trees must produce a matching SVG or structured HTML exhibit. A generic claim card is not an acceptable fallback. Missing or mismatched exhibits fail QA and return the task to storyline authoring.

Layout selection is driven by reader question, claim, evidence relationship, content capacity, reading order, co-location constraints, and pagination risk. The renderer records considered layouts and the reason for selection. Content is merged rather than padded when it cannot justify a full page.

## Client Report Content Contract

The executive summary uses a fixed decision structure:

- decision level;
- three decisive reasons;
- largest upside;
- largest risk;
- immediate actions;
- continue/stop thresholds.

The body shows one dominant conclusion per reading unit. Internal evidence identities, source grades, complete counter-search notes, and English debug labels remain in the evidence package. The client report may show compact source numbers and one concise limitation when it materially changes interpretation.

The final page is a short methods-and-limitations page. Full references are excluded by default and may only be included when the user explicitly requests an academic or regulatory bibliography.

## Consulting Orchestrator

L3 scene workflows create specialist research workstreams selected from the issue tree. Available roles are pain-and-sentiment, customer-purchase, competitors-and-substitutes, market-and-data, business-model-and-unit-economics, capital, and regulation. The project manager remains the only writer of the merged plan, curated data, synthesis, and storyline.

Each workstream has a task file, source prefix, staging ledger, extracted data, and handoff JSON. A handoff contains a short summary, source IDs, data files, supported claims, counter-evidence, limitations, unresolved questions, and next-search recommendation. The project manager records `accepted`, `needs_revision`, or `rejected`; unaccepted claims cannot reach the storyline.

L1 remains single-agent. L2 uses only the research lines needed by the issue tree. L3 requires at least two independent research lines and the full applicable review roles; it does not blindly launch every role.

## Audit Manifests

Three machine-validated files are mandatory for L2/L3 formal reports:

- `research-coverage.json`: per-subquestion coverage of first-party sources, user voice, behavioral evidence, transaction signals, counter-evidence, geography, time, saturation, and unresolved gaps.
- `skill-usage-manifest.json`: routed skills, method cards read, prerequisites, adopted/downgraded/rejected status, inputs, outputs, and project-manager disposition.
- `review-closure.json`: reviewer, issue severity, location, remedy, remedy evidence, re-reviewer, and final status.

Run-state completion is derived from these artifacts and acceptance state. `app-run.json` cannot claim completion while a required plan item or review closure remains open.

## Research Quality Gates

For each material pain, the pipeline requires at least two of user voice, behavioral evidence, and transaction/purchase signal before calling the pain validated. Cases and vendor materials may establish that a mechanism exists but cannot establish prevalence or willingness to pay.

Competition coverage must include direct competitors, indirect substitutes, DIY, no-buy/delay, adjacent entrants, and applicable regional players. Comparative claims require a structured dataset or must be labeled qualitative. Two consecutive search rounds with no new material pain, competitor, buying criterion, or counterexample are required before marking a line saturated.

Claim language is bounded by evidence maturity: public cases support “phenomenon exists”; multiple customer records support a pain pattern; priced intent supports willingness-to-pay discussion; orders and real workloads support unit economics; sustained delivery supports a higher decision grade.

## Review and Acceptance

Content review occurs before storyline: fact, red-team, method, and research-package review as applicable. The original reviewer rechecks blocking and major fixes once. Open blocking or major issues prevent report generation.

Final review has two independent roles:

- visual design reviewer: hierarchy, functional whitespace, exhibit fidelity, repetition, typography, worst page, and HTML/PDF parity;
- decision-maker reviewer: answer visibility, executive summary completeness, argument sufficiency, actions, ownership, and continue/stop thresholds.

Technical geometry checks remain necessary but cannot satisfy aesthetic acceptance. A report with no clipping may still fail for weak hierarchy, fake exhibits, excessive repetition, or non-functional whitespace.

## Migration and Compatibility

Existing task folders remain readable. New client/evidence paths are introduced for new runs and migration tests; compatibility aliases may keep `08_deliverables/report/` readable during transition. Deck output continues using the existing deck contracts. Academic or user-requested bibliography output remains an explicit option rather than the default.

## Verification

The implementation is complete only when:

- unit and contract tests pass;
- release and repository validation pass;
- an L3 fixture proves independent research handoffs and all three manifests;
- a declared exhibit cannot silently render as a claim card;
- a client report contains no full bibliography or raw URLs by default;
- the evidence package independently verifies;
- the AIDC task is regenerated through the new pipeline;
- the AIDC client report is at most ten pages, has a complete executive summary and at least four real business exhibits;
- independent visual and decision-maker reviewers accept the worst page and the full report;
- a blind comparison rates the new AIDC report above the prior version for decision clarity, evidence credibility, and visual quality.

