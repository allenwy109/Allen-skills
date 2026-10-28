# Consulting Delivery V2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a consulting-grade formal-report pipeline with specialist research workstreams, auditable skill/review manifests, separate client and evidence deliverables, real A4 exhibits, and decision/visual acceptance gates.

**Architecture:** Add three small validated project contracts and a workstream handoff contract around the existing ledger. Keep research, synthesis, and rendering responsibilities separate. Extend the existing A4 renderer with semantic exhibit components and fail-closed QA, then package the concise client report and independently verifiable evidence package from the same claim/source IDs.

**Tech Stack:** Python 3 standard library and existing JSON-schema helpers; Node.js/CommonJS A4 renderer; Swift PDF link helper where already used; unittest; existing report-forge vendor runtime.

---

## File Map

- `tools/lib/schema/research-coverage.schema.json`: research coverage and saturation contract.
- `tools/lib/schema/skill-usage.schema.json`: actual skill/method execution contract.
- `tools/lib/schema/review-closure.schema.json`: issue repair and re-review contract.
- `tools/lib/schema/research-handoff.schema.json`: specialist workstream handoff contract.
- `tools/consulting_project.py`: initialize, validate, and summarize workstreams/manifests.
- `tools/app_runtime.py`: derive stage completion from required artifacts.
- `tools/package_support.py`: emit evidence package without rendering internals/backups.
- `tools/bridge/to_report.py`: create client-report content and bibliography policy.
- `tools/lib/schema/report.schema.json`: client-report/exhibit semantics.
- `out-report/scripts/a4/components.cjs`: A4-native exhibits.
- `out-report/scripts/a4/render.cjs`: layout routing and client-report bookends.
- `out-report/scripts/a4/qa.cjs`: semantic exhibit, density, repetition, and client-surface checks.
- `out-report/assets/a4-layout-catalog.json`: A4 reading-layout contracts.
- `core-research/`, `core-review/`, `core-storyline/`, `out-report/`, and scene/app `SKILL.md` files: workflow instructions and artifact ownership.
- `tools/tests/` and `out-report/scripts/tests/`: contract, runtime, packaging, renderer, and QA tests.
- `tools/e2e/test_consulting_delivery.py`: complete L3 fixture.

### Task 1: Add consulting project contracts

**Files:**
- Create: `tools/lib/schema/research-coverage.schema.json`
- Create: `tools/lib/schema/skill-usage.schema.json`
- Create: `tools/lib/schema/review-closure.schema.json`
- Create: `tools/lib/schema/research-handoff.schema.json`
- Create: `tools/consulting_project.py`
- Create: `tools/tests/test_consulting_project.py`
- Modify: `tools/validate.py`

- [ ] **Step 1: Write failing contract tests**

Add tests proving that L3 validation rejects: missing research lines, a material pain without two signal classes, a handoff without project-manager disposition, a claimed skill without an output, and an open blocking/major review issue. Add a passing fixture with two research lines, explicit limitations, adopted/rejected skills, and closed reviews.

- [ ] **Step 2: Run the focused tests and verify failure**

Run: `python3 -m unittest tools.tests.test_consulting_project -v`

Expected: import/schema failures because the contracts and CLI do not exist.

- [ ] **Step 3: Implement schemas and the minimal CLI**

Implement these commands:

```text
python3 tools/consulting_project.py init <task> --depth L3
python3 tools/consulting_project.py validate <task>
python3 tools/consulting_project.py summary <task>
```

`init` creates the four artifact families without overwriting existing files. `validate` prints stable error codes and exits non-zero. `summary` reports research lines, coverage gaps, used/adopted skills, and open reviews.

- [ ] **Step 4: Register schemas in repository validation**

Make `tools/validate.py` load every new schema and reject broken internal references without changing existing validation behavior.

- [ ] **Step 5: Run tests and commit**

Run:

```bash
python3 -m unittest tools.tests.test_consulting_project tools.tests.test_validate -v
python3 tools/validate.py
```

Expected: all tests pass and repository validation reports zero errors.

Commit: `feat: add consulting project quality contracts`

### Task 2: Implement specialist research workstreams and truthful run state

**Files:**
- Modify: `core-research/scripts/research.py`
- Modify: `core-research/assets/templates/subagent-task.md`
- Create: `core-research/assets/templates/subagent-handoff.json`
- Modify: `core-research/SKILL.md`
- Modify: `tools/app_runtime.py`
- Modify: `tools/tests/test_app_runtime.py`
- Modify: `core-research/scripts/tests/test_research.py`

- [ ] **Step 1: Write failing workstream tests**

Cover creation of named workstreams with unique prefixes, staging directories and handoffs; duplicate-prefix rejection; accepted/needs-revision/rejected disposition; and L3 completion rejection while required handoffs or manifests remain open.

- [ ] **Step 2: Verify the tests fail**

Run:

```bash
python3 -m unittest core-research.scripts.tests.test_research tools.tests.test_app_runtime -v
```

Expected: failures for missing workstream/handoff behavior and false completed state.

- [ ] **Step 3: Add workstream commands**

Extend the research CLI with:

```text
research workstream add <task> <code> --role <role> --question <question>
research workstream handoff <task> <code> <handoff.json>
research workstream decide <task> <code> --status accepted|needs_revision|rejected --reason <text>
```

The command owns only task/handoff metadata; existing `ledger.py merge` remains the only merge path.

- [ ] **Step 4: Make completion derived, not handwritten**

Update `app_runtime.py` so an L2/L3 formal-report run cannot complete while consulting-project validation has blocking errors or acceptance lacks the required deliverables. Preserve L1 and non-report compatibility.

- [ ] **Step 5: Update research instructions**

Require the project manager to select workstreams from the issue tree, provide each subagent only its task contract, merge accepted staging data, and reject unaccepted claims from synthesis.

- [ ] **Step 6: Run tests and commit**

Run focused research/runtime tests plus `tools/selftest.sh --quick`.

Commit: `feat: orchestrate specialist research workstreams`

### Task 3: Separate client report and evidence package

**Files:**
- Modify: `tools/package_support.py`
- Modify: `tools/bridge/to_report.py`
- Modify: `tools/bridge/MAPPING.md`
- Modify: `out-report/scripts/out_report.py`
- Modify: `out-report/SKILL.md`
- Modify: `tools/tests/test_package_support.py`
- Modify: `tools/tests/test_bridge_report.py`
- Modify: `out-report/scripts/tests/test_out_report.py`

- [ ] **Step 1: Write failing packaging tests**

Assert that default output is `08_deliverables/client-report/{report.html,report.pdf}` plus `08_deliverables/evidence-package/` and ZIP; client HTML contains compact source anchors but no raw URL, source grade, capture timestamp, or full bibliography; evidence package includes source index, snapshots, ledger, data, calculations, logs, reviews, manifests, and checksum manifest while excluding `.backup`, build caches, and rendering internals.

- [ ] **Step 2: Verify focused failures**

Run packaging, bridge, and out-report tests. Expected: old `report/` path and bibliography assertions fail.

- [ ] **Step 3: Implement explicit bibliography policy**

Add report metadata:

```json
{
  "bibliography_policy": "evidence_package",
  "client_citations": "compact"
}
```

Allow `bibliography_policy=full` only when explicitly selected. Maintain a transitional read alias for existing `08_deliverables/report/` tasks without duplicating new outputs.

- [ ] **Step 4: Build the evidence package from verified artifacts**

Reuse existing seal/manifest helpers. The package must verify outside the task directory and retain the report's claim/source identifiers.

- [ ] **Step 5: Run tests and commit**

Run focused tests, support-package verification, and a fixture HTML scan for forbidden client-surface fields.

Commit: `feat: separate client reports from evidence packages`

### Task 4: Add A4-native semantic exhibits and fail-closed rendering

**Files:**
- Create: `out-report/assets/a4-layout-catalog.json`
- Modify: `tools/lib/schema/report.schema.json`
- Modify: `tools/bridge/to_report.py`
- Modify: `out-report/scripts/a4/components.cjs`
- Modify: `out-report/scripts/a4/render.cjs`
- Modify: `out-report/scripts/a4/qa.cjs`
- Modify: `out-report/scripts/tests/test_a4_components.py`
- Modify: `out-report/scripts/tests/test_a4_qa.py`
- Modify: `out-report/scripts/tests/test_design_catalogs.py`

- [ ] **Step 1: Write failing exhibit tests**

Add fixtures for executive summary, answer-and-reasons, pain comparison, competitor matrix, decision tree, mechanism/process, paired scenarios, 30/60/90 roadmap, and methods/limitations. Assert each semantic kind renders a distinct structured exhibit and that a declared exhibit with missing/mismatched form fails with `REPORT_EXHIBIT_MISSING` or `REPORT_EXHIBIT_MISMATCH`.

- [ ] **Step 2: Verify failures**

Run A4 component/design/QA tests. Expected: semantic exhibit assertions fail against generic claim-card fallback.

- [ ] **Step 3: Implement the smallest exhibit components**

Use accessible HTML/SVG with embedded text, stable IDs, print-safe colors, and no new runtime dependency. Reuse existing table and flow primitives where they already satisfy the contract.

- [ ] **Step 4: Add the A4 layout catalog and router**

Each layout records semantic relationships, soft/hard capacity, reading path, co-location constraints, forbidden content, and pagination behavior. Route by declared relationship and capacity; do not use deck ratio or deck layout IDs.

- [ ] **Step 5: Fail closed in QA**

Validate declared kind against rendered DOM structure. Generic text fallback is permitted only for `point_evidence` and must be explicitly declared.

- [ ] **Step 6: Run tests and commit**

Run all out-report tests and render the golden fixture.

Commit: `feat: render native A4 consulting exhibits`

### Task 5: Enforce executive hierarchy, density, and visual quality

**Files:**
- Modify: `out-report/assets/report-tokens.css`
- Modify: `out-report/scripts/a4/components.cjs`
- Modify: `out-report/scripts/a4/paginate.cjs`
- Modify: `out-report/scripts/a4/qa.cjs`
- Modify: `out-report/scripts/a4/visual_regression.py`
- Modify: `out-report/golden/golden-report.json`
- Modify: `out-report/scripts/tests/test_a4_pagination.py`
- Modify: `out-report/scripts/tests/test_a4_qa.py`
- Modify: `out-report/scripts/tests/test_golden_contract.py`

- [ ] **Step 1: Write failing hierarchy/density tests**

Require the six-part executive summary, reject duplicate section/block titles, detect non-functional whitespace above the configured threshold, reject consecutive repeated primary structures without an approved reason, enforce A4 type minimums, and identify the worst page in QA evidence.

- [ ] **Step 2: Verify failures**

Run pagination, QA, and golden tests. Expected: current sparse golden fixture fails new hierarchy and fill rules.

- [ ] **Step 3: Implement natural A4 composition**

Allow compatible components to share a page, keep sections continuous, split tables at semantic boundaries, and avoid padding a short claim to a full page. Preserve existing no-overflow and link guarantees.

- [ ] **Step 4: Replace the golden fixture**

Create a decision-oriented A4 golden report with real exhibits and a concise methods page. Render HTML/PDF/PNGs and approve the new baseline only after visual inspection.

- [ ] **Step 5: Run tests and commit**

Run the full out-report test suite and visual regression checks.

Commit: `feat: enforce A4 hierarchy and visual quality`

### Task 6: Add content, visual, and decision-maker review closure

**Files:**
- Modify: `core-review/SKILL.md`
- Modify: `core-review/references/reviewer-prompts.md`
- Modify: `core-review/references/output-standard.md`
- Modify: `tools/acceptance.py`
- Modify: `tools/tests/test_acceptance.py`
- Modify: `out-report/scripts/tests/test_out_report.py`

- [ ] **Step 1: Write failing review tests**

Reject report acceptance when blocking/major content issues are open, visual review omits worst-page assessment, decision-maker review cannot answer the six executive questions, or the same author is recorded as the independent reviewer.

- [ ] **Step 2: Verify failures**

Run acceptance and out-report tests. Expected: current acceptance permits incomplete aesthetic/decision review.

- [ ] **Step 3: Implement closure-aware acceptance**

Require review digests, independent role identity, remedy evidence, and one re-review for blocking/major issues. Geometry and visual-regression checks remain separate from human visual acceptance.

- [ ] **Step 4: Update reviewer prompts**

Give visual reviewers only final media; give decision reviewers only the PDF. Require concrete page findings and prohibit “no overflow” from being treated as aesthetic approval.

- [ ] **Step 5: Run tests and commit**

Run focused acceptance/review tests and quick selftest.

Commit: `feat: close consulting review and acceptance loops`

### Task 7: Integrate contracts across all formal-report scenes

**Files:**
- Modify: `scene-idea/SKILL.md`
- Modify: `scene-company/SKILL.md`
- Modify: `scene-bp-review/SKILL.md`
- Modify: `scene-topic/SKILL.md`
- Modify: `allen-idea/SKILL.md`
- Modify: `allen-company/SKILL.md`
- Modify: `allen-bp-review/SKILL.md`
- Modify: `allen-capital/SKILL.md`
- Modify: `allen-ecosystem/SKILL.md`
- Modify: `core-storyline/SKILL.md`
- Modify: `router/SKILL.md`
- Modify: `tools/e2e/test_smoke.py`
- Create: `tools/e2e/test_consulting_delivery.py`

- [ ] **Step 1: Write an L3 end-to-end fixture**

The fixture must create two independent research lines, merge only accepted handoffs, validate all manifests, close a major review issue, render a bibliography-free client report with real exhibits, build the evidence ZIP, and pass visual/decision acceptance metadata.

- [ ] **Step 2: Verify the fixture fails**

Run: `python3 -m unittest tools.e2e.test_consulting_delivery -v`

Expected: missing scene instructions/artifact gates.

- [ ] **Step 3: Update shared and scene instructions**

Keep rules in shared skills and make scenes reference them. Do not duplicate the full workflow in every application skill. Explicitly preserve L1/L2 proportionality.

- [ ] **Step 4: Run validation and commit**

Run E2E, smoke, repository validation, and skill archive build.

Commit: `feat: apply consulting delivery contracts across scenes`

### Task 8: Regenerate and independently evaluate the AIDC report

**Files:**
- Modify: `/Users/markjackson/Repos/entservice/work/aidc-gpu-pool-2026-10-27/` task artifacts through the supported workflow
- Create: `docs/superpowers/reviews/2026-10-28-consulting-delivery-v2-acceptance.md`

- [ ] **Step 1: Preserve the old report as the comparison baseline**

Record hashes and page images without modifying the prior report.

- [ ] **Step 2: Run the new project contracts against the existing research**

Do not invent missing customer evidence. Populate truthful coverage and skill manifests, import existing reviews, and surface remaining gaps.

- [ ] **Step 3: Run targeted new research workstreams**

Use independent pain/sentiment and competitor workstreams at minimum. Store full snapshots and structured comparisons; stop according to the documented saturation rule. Treat public evidence as proxy evidence and preserve the need for primary customer validation.

- [ ] **Step 4: Rebuild storyline and client report**

Produce no more than ten A4 pages, a complete executive summary, compact citations, a short methods/limitations page, and at least four real exhibits: competitive landscape, path decision, statistical-reuse mechanism, and validation roadmap or paired scenarios.

- [ ] **Step 5: Build and verify the evidence package**

Run independent package verification and checksum verification outside the task directory.

- [ ] **Step 6: Run independent reviews and blind comparison**

Assign separate visual and decision-maker reviewers. Compare old/new PDFs without revealing which is new. Require the new report to win decision clarity, evidence credibility, and visual quality; otherwise fix and re-review once.

- [ ] **Step 7: Record acceptance and commit repository-owned evidence**

Commit only reusable repository fixtures/review records. Keep the business-task deliverables in the entservice workspace and report their exact paths.

### Task 9: Release, merge, install, and verify

**Files:**
- Modify only release metadata required by the existing release process.

- [ ] **Step 1: Run full verification**

Run:

```bash
python3 -m unittest discover -s tools/tests -p 'test_*.py'
python3 -m unittest discover -s out-report/scripts/tests -p 'test_*.py'
python3 -m unittest tools.e2e.test_smoke tools.e2e.test_consulting_delivery -v
python3 tools/validate.py
python3 tools/report_release.py check
tools/selftest.sh --quick
```

Expected: zero test failures and zero validation errors.

- [ ] **Step 2: Request final independent code review**

Review the complete branch against this plan, repository policies, backward compatibility, and the AIDC acceptance record. Resolve all blocking/important issues and re-review.

- [ ] **Step 3: Synchronize with remote base**

Fetch `origin/main`; if it advanced, merge it into the topic branch and rerun affected verification.

- [ ] **Step 4: Push and create a PR**

Push `codex/consulting-delivery-v2`, create a PR targeting `main` because this repository has no `dev`, and squash-merge after verification. Delete the remote topic branch.

- [ ] **Step 5: Reinstall local skills and verify provenance**

Install from the merged revision with `./install.sh --codex --force`, verify installed copies are not symlinks, run release validation from the merged commit, and report the final commit SHA, PR, tests, client report, and evidence package.

