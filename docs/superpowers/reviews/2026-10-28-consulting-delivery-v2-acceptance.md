# Consulting Delivery V2 acceptance

Date: 2026-10-28 (Australia/Adelaide)

## Decision

The regenerated idea-evaluation deliverables passed the consulting-project, research-quality, storyline, report, evidence-package, and independent-review gates. The business recommendation remains conditional on the decision gates documented in the client report; this repository record does not reproduce the confidential analysis.

## Business-task evidence

The business artifacts remain outside this repository at `/Users/markjackson/Repos/entservice/work/aidc-gpu-pool-2026-10-27`.

| Artifact | Task-relative path | Verified identity |
|---|---|---|
| Client PDF | `08_deliverables/client-report/report.pdf` | 10 A4 pages; SHA-256 `59fa8a02afbe831b5c6bfc57f4be8f8f93ca5686060f2f20695c86ab47203e5c` |
| Client HTML | `08_deliverables/client-report/report.html` | SHA-256 `ec980232a6d3412b580844f6557b3d450d864bb11555cf273d80b8f34adf9dfb` |
| Evidence package | `08_deliverables/evidence-package.zip` | SHA-256 `2a022ffd4b166fd503e145c20291f65341d50bc163ba3d2f35a575df051cc932` |
| Final acceptance summary | `08_deliverables/task8-final-acceptance-summary.md` | Records the checks and retained limitations |

The accepted report is bound to artifact digest `092566c2e48bc4990d39529bd64059aa15c21897e43984af086e890cfe0bf09c` and pagination digest `8e44e209024212a4b5ee76221ccca7d947d89112157c2b8e5485f6111579961f`.

## Independent review

- The original decision reviewer closed every blocking and major issue in `08_deliverables/decision-review-v2-r2.md`.
- The original visual reviewer closed RV-0001 through RV-0007 and accepted the current HTML/PDF pair in `08_deliverables/visual-review-v2-r1.md`.
- In the anonymous old/new comparison, the accepted candidate scored 9.0 for decision clarity, 8.5 for evidence credibility, and 8.5 for visual quality. The retained old baseline scored 6.5, 8.0, and 6.5 respectively.
- The accepted report keeps compact source markers; full titles, URLs, locators, snapshots, grades, capture metadata, and checksums are confined to the separately verified evidence package.

## Mechanical verification

- `consulting_project validate`: passed.
- `research_quality check`: passed.
- `research check`: `PASS_AUTOMATED`, zero errors.
- Storyline check: passed; all eight A-grade exhibits reached the report.
- Client report acceptance: passed.
- Evidence and support-package acceptances: passed.
- The 148-file evidence package was extracted outside the task directory and independently verified against its manifest, file sizes, and SHA-256 checksums.

## Retained limitations

- Five early search-log timestamps retain their original timezone-format warnings rather than being rewritten after the fact.
- Claim `cl-0012` has one independent source and no primary S/A-grade source. The report therefore treats API-versus-GPU economics as a preregistered experiment, not an established fact.
- The project still lacks its own customer interviews, orders, supply quotations, observed workloads, repeat-use data, and legal advice. `T8-GAP-PRIMARY-DEMAND` remains open as a minor disclosed gap.
- The preserved 12-page report under `08_deliverables/report/` is the comparison baseline, not the accepted client deliverable.
