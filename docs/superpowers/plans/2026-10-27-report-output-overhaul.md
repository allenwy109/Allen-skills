# Report Output Overhaul Implementation Roadmap

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preserve every upstream consulting-report-forge capability, add a deterministic A4 report system, and prove both outputs meet the approved visual benchmark.

**Architecture:** Keep `slides.json → report-forge` for decks. Add `slides.json → report.json → A4 renderer` for reading reports. Both projections share the ledger, coverage manifests, acceptance records, and independent visual review, but not CSS or pagination rules.

**Tech Stack:** Python 3 standard library, Node.js 20 CommonJS, Playwright Chromium, HTML/CSS/SVG, unittest, upstream report-forge.

---

Execute these plans in order:

1. [Upstream parity and showcase](2026-10-27-report-phase-1-upstream-parity.md)
2. [A4 contracts and golden booklet](2026-10-27-report-phase-2-a4-contracts.md)
3. [A4 renderer and out-report](2026-10-27-report-phase-3-a4-renderer.md)
4. [out-deck and release acceptance](2026-10-27-report-phase-4-deck-release.md)

Do not begin phase 2 until the phase-1 capability matrix has no `missing` entries. Do not implement the general A4 renderer until the golden booklet is approved. Do not switch application defaults until all six scenario fixtures pass and an independent reviewer signs the anonymous A/B comparison.
