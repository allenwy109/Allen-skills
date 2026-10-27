# Research report quality acceptance — 2026-10-27

## Result

Accepted. The reusable research-to-A4 path now carries structured claims, pain-demand chains, and competition matrices from `decision-research.json` into the report model and renders them as purpose-built exhibits. The AIDC GPU pool task was used only as an end-to-end regression fixture.

## Accepted artifacts

- Task: `/Users/markjackson/Repos/entservice/work/aidc-gpu-pool-2026-10-27`
- Decision research: `03_evidence/decision-research.json`
- Packaged HTML: `08_deliverables/report/report.html`
- Packaged PDF: `08_deliverables/report/report.pdf`
- Page PNGs and manifests: `08_deliverables/report/page-001.png` through `page-012.png`, plus the artifact, coverage, geometry, media, pagination, QA, and visual-regression manifests in the same directory
- Author review: `08_deliverables/report/author-review.json`
- Independent review: `08_deliverables/report/independent-review.json`
- Whole-book inspection sheet: `07_storyline/a4-work/build/review/whole-book.png`

The package command completed with unified acceptance status `passed`.

## Content acceptance

- The two priority customer segments are AI application startups and small Token/API providers.
- The 90-day beachhead is compliant Southeast Asian capacity; China capacity is explicitly deferred or isolated because of cross-border and export-control uncertainty.
- Pain evidence is represented as segment, trigger, workaround, consequence, purchase signal, support strength, counter/boundary, and remaining validation gap.
- Competition covers direct GPU clouds, marketplaces, serverless/Token APIs, hyperscalers, self-build, adjacent Southeast Asian entrants, and no-buy/delay across TCO, availability, reliability/recovery, deployment/migration effort, lock-in, support/SLA, data compliance, and regional coverage.
- Decision-critical claims carry support, counter-search status, scope, confidence, limitations, and narrower wording. Vendor cases are visibly labelled as indirect leads and are not used to prove prevalence or willingness to pay.
- The method plan records actual use or downgrade reasons for 3C, Five Forces/substitutes, STP, the pricing triangle, customer journey, and KSF/capability-gap analysis.
- No interviews, orders, utilization data, market share, or willingness-to-pay evidence were invented.

## Visual acceptance

The author inspected representative pages and the independent reviewer inspected both HTML and PDF at 100% plus the whole-book contact sheet.

- Page 1: title, contents, and page references are complete.
- Page 3: both pain chains remain readable at the densest two-column layout.
- Pages 4–5: the competition matrix retains layer, option, and purchasing-dimension context across continuation pages.
- Pages 6 and 9: claim/support/counter/scope/confidence/limitation boundaries remain visible on dense pages.
- Pages 11–12: complete sources appear only in the appendix; long URLs wrap and continuation headers repeat.
- Pages 1, 4, 7, 10, and 12 were specifically rechecked after a general CJK heading-ascent fix. No title clipping remains.
- All 12 pages are A4, with no forced blank pages, overflow, overlap, clipping, or placeholder exhibits.

The first two independent passes rejected the artifact for blank pages, generic appendix content, evidence-directness wording, and CJK title clipping. Each issue was fixed generically and the same reviewer returned final `ACCEPT` with no unresolved blocking or important issue.

## Verification

- `python3 tools/research_quality.py check <AIDC task>` — passed
- `python3 core-research/scripts/research.py check <AIDC task>` — automated checks passed; five legacy search-log timestamps remain warnings
- `python3 tools/lib/ledger.py <AIDC task> check` — 0 errors, 0 warnings
- `python3 core-storyline/scripts/storyline.py check <AIDC task> --json` — passed after sync; only the non-blocking presentation-backup warning remains
- `python3 -m unittest tools.tests.test_research_quality -v` — 29 passed
- `python3 -m unittest discover -s out-report/scripts/tests -p 'test_*.py' -v` — 93 passed
- `ALLEN_RUNTIME=/Users/markjackson/Repos/Allen-skills tools/selftest.sh --quick` — passed (including 251 common tests, 44 diligence tests, 16 intake tests, 40 research tests, 32 storyline tests, 5 chart tests, 25 deck tests, 4 poster tests, and 93 report tests)
- `git diff --check` — passed

## Known limitations

- The AIDC decision remains a validation recommendation, not an investment approval: there are still no first-party customer interviews, signed orders, matched quotes, measured utilization curves, or observed willingness-to-pay data.
- IMDA and other regulatory sources establish applicable constraints and official guidance, but do not remove the need for transaction-specific Singapore, China, export-control, privacy, and data-residency advice.
- Five pre-existing research search-log records use timestamps without timezone offsets. The research checker reports these as warnings; evidence snapshots, locators, source identities, and ledger bindings remain valid.
- The storyline checker warns that the report has no presentation backup pages. This is an A4 report and the omission does not affect the accepted report package.
