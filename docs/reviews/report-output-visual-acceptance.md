# Report Output Visual Acceptance

Date: 2026-10-27

Decision: approved after final verification

Scope: A4 `out-report` and 16:9/4:3 `out-deck`

## Decision

The revised A4 report and the Allen deck composer satisfy the release visual gates. The A4 booklet has an explicitly user-approved candidate digest. The final deck candidate beats the locked pre-composer reference in three of eight dimensions and is no worse in the other five.

This conclusion uses only the final synchronized artifacts. Earlier review rounds are retained below because they materially changed the implementation and must not be mistaken for successful evidence.

## Review independence

The final reviewers were fresh, read-only agents given only the reviewer-facing artifact directories. They were instructed not to inspect Git, source code, temporary identity maps, earlier packets, or candidate identities. Identity was revealed only after the scorecard was returned.

- Deck reviewer packet: `out-deck/build/visual-benchmark-final`
- A4 reviewer packet: `out-report/golden/build/current-review`
- Deck anonymous labels: Cinder and Willow
- Revealed identities: Cinder = candidate; Willow = locked reference
- Common deck input SHA-256: `735bee1e80f372f05db013374a9c74ef4eb443166d187f2aac64c4cce3179438`
- Common deck blueprint SHA-256: `4838621e1af9d2251cc8313c8b4cd2676335b27bff35d97d68f94b32d4a73db5`

## Final deck scorecard

| Dimension | Candidate Cinder | Reference Willow | Page evidence |
|---|---:|---:|---|
| Visual focus | 4 | 4 | P2 establishes chart → boundary → conclusion; P3 establishes forecast → decision table → action. |
| Evidence geometry | 5 | 4 | P2 directly labels values; P3 pairs forecast, recommendation, assumptions, and boundaries; P4 closes page/claim/locator coverage. |
| Density | 4 | 4 | P2–P3 balance evidence and whitespace; P4 remains deliberately restrained. |
| Typography | 4 | 4 | P1/P5 bookends and P2–P4 hierarchy remain consistent and readable. |
| Chart clarity | 5 | 5 | P2 labels 2024/2025 and 1800/3200 万元 directly and states the limit of the 77.8% comparison. |
| Book rhythm | 5 | 4 | Candidate closes fact → decision → traceability before the back cover; reference has a thinner P4 transition. |
| Source integration | 5 | 4 | Candidate adds a near-claim locator on P3 and page/claim/source/reproducibility evidence on P4. |
| Finish | 4 | 4 | Both variants pass HTML/PDF acceptance geometry with no errors; candidate media are synchronized. |

Release rule: every dimension must be at least 4/5; the candidate must beat the reference in at least two dimensions and be no worse in the remainder. Cinder wins three dimensions and ties five. Result: **PASS**.

Cross-media evidence:

- Anonymous manifest SHA-256: `c72cb7a932aae1df07d64755ce88c4e8a8552e21eacdc8e253bb583a1bf74f4b`
- Candidate PDF SHA-256: `ac2275ccd34ad34a3f78b05b31aa24d4f0418736e2c82011e69a650d9595c81d`
- Candidate cross-media manifest SHA-256: `0d8046af8e2fdde9d425d9fb178edfcfdad3a1548578cbebf47634f5ae6ab5dd`
- Both variants: acceptance complete, geometry PASS, five HTML pages, five PDF pages, zero errors.
- Per-page HTML/PDF text similarity is 1.0; fresh HTML render hashes match the packaged PNGs; contact-sheet input hashes match the same PNG set.

## Final A4 scorecard

| Dimension | Score | Page evidence |
|---|---:|---|
| Visual focus | 5 | P3, P4, P10, P14 |
| Evidence geometry | 5 | P5–P7, P11–P13 |
| Density | 4 | P4, P8, P10, P15–P16 |
| Typography | 5 | P4, P6, P8, P14 |
| Chart clarity | 5 | P5–P7, P9, P13 |
| Book rhythm | 5 | P1–P4, P9–P10, P14–P16 |
| Source integration | 5 | P3, P5–P16 |
| Finish | 4 | P2 and P15–P16; current contact sheets and page hashes are synchronized. |

Every dimension is at least 4/5. Result: **PASS**.

- Approved candidate digest: `59742bde7d67fc1ecbe5c96684a4d9212ecc5c813500d3d1befc69ac04cb2fe7`
- Approved by: user
- Approved at: `2026-10-27T15:17:48+10:30`
- Approval wording: `确认 A4 新基准`
- Visual baseline manifest SHA-256: `00620041cac19c57ea32d7a767cefafa07d70c67500bbef7b0e78bbe70ee8fa5`
- Current review manifest SHA-256: `de993387fbe6a42b18200bb4d4e9323afdf21fd8eb1434ca5a872658910dc0ba`
- The rebuilt whole-book and four chapter contact sheets bind all 16 current page hashes.

## Review history and dispositions

1. The first deck A/B packet was byte-identical. It established parity only and was rejected because it could not prove improvement; chart clarity, rhythm, source integration, and finish were also below the gate.
2. Early composer candidates added forms but performed worse than the reference because they exposed implementation structure, repeated conclusions, used internal metric IDs, and created dead space. They were rejected.
3. Later candidates reached the absolute 4/5 threshold but still lost comparative dimensions. They were rejected rather than relabeled.
4. The first visually passing packet was withheld after the reviewer found cross-media contamination in the reference P4. Root cause was a plan-mutation run overwriting accepted artifacts. The benchmark was rebuilt with isolated work directories, clean staging, atomic replacement, HTML/PDF text comparison, fresh PNG hashes, and contact-sheet input hashes.
5. Only `visual-benchmark-final` is release evidence. Its independent final review passed without blockers.
6. The initial A4 candidate passed most visual dimensions but had a wrong chapter start and ambiguous approval wording. Both were corrected; contact sheets were rebuilt; the user approved the new digest explicitly.

## Capability and scenario evidence

- Upstream parity: 38 layouts, 6 masters, 3 themes, 16:9 and 4:3 ratios, full form/capacity contracts, independent planning, representative/worst-page review, HTML/PDF review, official showcase, and screenshot inventories.
- Six fixed report scenarios: startup idea, company profile, BP review, topic research, quantitative-heavy, and evidence-heavy.
- Each scenario has a fully materialized input digest, a positive accepted path, a mutation-specific negative path, and a missing-review failure-closed path.

The machine-readable release record is `references/report-output-release.json`.
