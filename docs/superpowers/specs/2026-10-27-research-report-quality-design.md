# Research and Report Quality Design

**Date:** 2026-10-27  
**Status:** proposed  
**Scope:** Allen Skills reusable research, evidence, review, and A4 report pipeline

## Goal

Make future company, startup-idea, BP, and topic reports consistently strong in three areas:

1. customer pain and competitive analysis are decision-grade rather than descriptive lists;
2. important factual claims receive granular, adversarial verification;
3. A4 reports remain readable and visually calm, without full references repeated at the bottom of every page.

The current AIDC GPU-pool report is a regression fixture, not a special-case implementation.

## Current failure

The existing system contains the necessary methods and evidence tools, but it does not force them to converge into a sufficiently deep analysis. A task can technically pass while:

- using only a reduced STP or market-entry analysis despite material customer, competitor, substitute, pricing, and bargaining questions;
- treating vendor case studies as demand validation;
- presenting competitors as a short feature list without substitutes, failure modes, regional availability, or customer switching logic;
- recording a source without checking whether it supports the exact scope and strength of the claim;
- rendering long source strings on each page, which preserves traceability but damages report readability.

This is a pipeline-contract problem, not a one-report formatting problem.

## Chosen approach

Add a small set of reusable quality contracts and executable gates to the existing pipeline. Do not create a parallel research system or replace the A4 renderer.

The design has four coordinated changes:

1. strengthen scene and method-selection requirements;
2. add reusable pain, competition, and fact-check contracts;
3. separate reader-facing citations from the full evidence appendix;
4. add regression tests that fail when these requirements are lost.

## Research quality contracts

### Pain analysis

When customer pain affects the decision, each material pain must be represented with:

- affected segment and workload;
- trigger or usage situation;
- current workaround or substitute;
- operational or economic consequence;
- observable purchase or switching signal;
- supporting evidence and counterevidence;
- evidence strength and unresolved validation need.

A vendor-selected customer story may establish that a phenomenon exists. It cannot by itself establish prevalence, demand strength, willingness to pay, or target-market fit. Those stronger claims require independent user behavior, transaction or procurement evidence, a representative survey, or direct primary research.

### Competition analysis

When competition affects the decision, the analysis must cover the relevant layers rather than only named direct competitors:

- direct products serving the same segment and job;
- indirect products using another delivery model;
- do-it-yourself and incumbent workarounds;
- adjacent providers able to enter;
- the option to delay, avoid, or not buy.

Comparison dimensions must follow the purchase decision. Typical dimensions include total cost, availability, reliability, deployment effort, lock-in, support, compliance, service level, switching cost, and regional coverage. Market share or competitive intensity must remain unknown unless supported by comparable adoption, transaction, capacity, or financial data.

### Consulting-method coverage

`core-method-select` remains responsible for selecting methods; the scene skills must not hard-code a universal framework stack. For company, idea, BP, and topic tasks, the method plan must nevertheless show that the following questions were considered when material:

- customer and competitor interaction: 3C or an explicitly justified equivalent;
- substitutes and bargaining structure: Five Forces or a narrower substitute/bargaining analysis;
- customer segmentation and target selection: STP;
- price, value, and cost boundaries: pricing triangle;
- purchase or usage friction: customer journey;
- ability to win: KSF and company-capability gap.

Each selected method records its input sufficiency. If prerequisites are missing, the output is labelled as a hypothesis or candidate conclusion; the missing data and next validation are named. Methods are not considered used merely because their names appear in the plan.

### Fact-checking

Every decision-critical claim must include:

- claim identity: fact, reported data, estimate, forecast, assumption, judgment, or recommendation;
- exact scope: entity, segment, geography, period, and workload when applicable;
- at least one supporting source with a locator;
- counterevidence or an explicit record of the adversarial search performed;
- independence and conflict-of-interest assessment;
- confidence with a reason;
- the strongest plausible narrower wording if the evidence does not support the original claim.

Claims about prevalence, willingness to pay, competitive intensity, market growth, causality, or regulatory obligation receive stricter checks because they are frequently overstated. Issuer marketing and selected case studies cannot independently support them.

## Report citation and layout contract

The A4 report remains the default reading format.

Reader-facing pages must not contain full URLs, long source titles, or multi-line reference strips. The allowed body-page citation is a compact marker such as `[12]`, attached to the relevant statement or exhibit. Full bibliographic details, source quality, locator, and access date belong in a consolidated evidence appendix.

The report must preserve machine traceability through content keys and source IDs even though the full source text is rendered only in the appendix. HTML markers link to appendix entries; PDF markers and appendix numbering remain identical.

The A4 visual baseline is:

- editorial document hierarchy rather than slide composition;
- restrained page furniture and consistent margins;
- one dominant conclusion per page or spread;
- tables split or continued instead of shrinking text;
- no bottom source band competing with the conclusion;
- evidence confidence and limitations presented as content, not as visual clutter.

## Automated gates

The implementation adds tests or validators for observable invariants:

1. body pages contain no raw `http://` or `https://` reference text and no legacy full-width source strip;
2. every rendered citation marker resolves to exactly one appendix record;
3. report input preserves source IDs and locators after compact rendering;
4. decision-critical claims contain identity, scope, confidence, support, and adversarial treatment;
5. pain and competition sections use the required schemas when those questions are material;
6. method plans record prerequisite checks and downgrade unsupported outputs;
7. A4 geometry, pagination, overflow, font-size, and visual-regression checks continue to pass.

The validator checks structure and traceability. It does not pretend to prove that a qualitative judgment is correct; independent fact, method, red-team, and final-product reviews remain required at the appropriate depth.

## Files and ownership

The smallest expected change surface is:

- `scene-idea/` and the other research-producing scene skills: require the shared analysis contracts when material;
- `core-method-select/`: record method coverage and prerequisite downgrades;
- `core-evidence/` and `core-research/`: strengthen critical-claim and adversarial-evidence requirements;
- `core-review/`: review the new contracts and citation presentation;
- `core-storyline/`: carry compact citation IDs into report input;
- `out-report/`: render compact markers in the body and full evidence entries in the appendix;
- existing test suites: add focused contract and A4 regression cases.

If a shared reference can express a judgment rule without duplication, scene skills link to it. Mechanical requirements belong in validators and tests rather than repeated prose.

## Compatibility and migration

Existing evidence ledgers and report inputs remain valid. The renderer derives compact markers from existing source IDs; no historical task must be rewritten merely to install the update.

New or refreshed L2/L3 reports use the new gates. A task lacking the new critical-claim fields is reported as incomplete rather than silently upgraded. L1 answers retain proportionate depth and are not forced through a full research package.

## Verification

Implementation is complete only when:

1. focused tests demonstrate the old behavior fails the new contracts;
2. all modified skill and renderer tests pass;
3. the repository quick self-test passes;
4. the AIDC task is regenerated without page-bottom reference strips;
5. the regenerated AIDC report contains materially deeper pain, competitor, and fact-check sections without project-specific renderer logic;
6. HTML and PDF receive independent visual review against the approved A4 baseline.

## Out of scope

- inventing market evidence that public research cannot provide;
- forcing every report to use every consulting framework;
- rebuilding report-forge or the A4 renderer from scratch;
- optimizing only the AIDC report through hard-coded templates or content;
- changing presentation-deck output unless a shared contract requires a compatible citation fix.
