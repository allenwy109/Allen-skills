#!/usr/bin/env node
'use strict';

const fs = require('fs');
const crypto = require('crypto');

const COVERAGE_SETS = Object.freeze(['claims', 'a_cards', 'panels', 'relations', 'metrics', 'sources']);
const A4 = Object.freeze([210, 297]);
const MEDIA_TOLERANCE_MM = 0.2;

function normalizedText(value) {
  return String(value || '').replace(/\s+/g, ' ').trim();
}

function digest(value) {
  return crypto.createHash('sha256').update(value).digest('hex');
}

function issue(code, location, detail, evidence = {}) {
  return { code, location: String(location || ''), detail: String(detail || ''), evidence };
}

function stableUnique(values) {
  return [...new Set(values || [])].sort();
}

function sameSet(left, right) {
  return JSON.stringify(stableUnique(left)) === JSON.stringify(stableUnique(right));
}

function validDisposition(value) {
  return value && value.decision === 'accepted' &&
    typeof value.reviewer === 'string' && value.reviewer.trim() &&
    typeof value.reason === 'string' && value.reason.trim() &&
    typeof value.reviewedAt === 'string' && value.reviewedAt.trim();
}

function evaluate(evidence) {
  if (!evidence || typeof evidence !== 'object' || Array.isArray(evidence)) {
    const error = new Error('REPORT_QA_INPUT: evidence must be an object');
    error.code = 'REPORT_QA_INPUT';
    throw error;
  }
  const blocking = [];
  const warnings = [];
  const pagination = evidence.pagination || {};
  const paginationPages = Array.isArray(pagination.pages) ? pagination.pages : [];
  const geometryPages = Array.isArray(evidence.geometry && evidence.geometry.pages) ? evidence.geometry.pages : [];

  for (const page of paginationPages) {
    if (Number(page.usedHeightPx) > Number(page.contentHeightPx) + 1) {
      blocking.push(issue('REPORT_PAGE_OVERFLOW', page.id, `${page.usedHeightPx}px exceeds ${page.contentHeightPx}px`, { usedHeightPx: page.usedHeightPx, contentHeightPx: page.contentHeightPx }));
    }
  }
  if (Number(pagination.pageCount) !== paginationPages.length) {
    blocking.push(issue('REPORT_PAGE_MANIFEST_MISMATCH', 'pagination', `${pagination.pageCount} declared, ${paginationPages.length} listed`));
  }
  const paginationIds = paginationPages.map(page => page.id);
  const geometryIds = geometryPages.map(page => page.id);
  if (JSON.stringify(paginationIds) !== JSON.stringify(geometryIds)) {
    blocking.push(issue('REPORT_PAGE_MANIFEST_MISMATCH', 'geometry', 'geometry and pagination page inventories differ', { pagination: paginationIds, geometry: geometryIds }));
  }

  for (const page of geometryPages) {
    const box = page.mediaBoxMm || [];
    if (box.length !== 2 || box.some((value, index) => !Number.isFinite(Number(value)) || Math.abs(Number(value) - A4[index]) > MEDIA_TOLERANCE_MM)) {
      blocking.push(issue('REPORT_MEDIA_BOX', page.id, `expected A4 within ${MEDIA_TOLERANCE_MM}mm`, { mediaBoxMm: box }));
    }
    if ((page.overlaps || []).length) blocking.push(issue('REPORT_ELEMENT_OVERLAP', page.id, 'elements overlap', { overlaps: page.overlaps }));
    if ((page.clipped || []).length) blocking.push(issue('REPORT_CONTENT_CLIPPED', page.id, 'content is clipped', { clipped: page.clipped }));
    const paginationPage = paginationPages.find(candidate => candidate.id === page.id);
    if (page.empty && !(paginationPage && paginationPage.intentionalBlank)) blocking.push(issue('REPORT_EMPTY_PAGE', page.id, 'unintentional empty page'));
    for (const font of page.fonts || []) {
      const minimum = font.role === 'source' ? 7.5 : 8.5;
      if (Number(font.minimumPt) < minimum) blocking.push(issue('REPORT_FONT_TOO_SMALL', page.id, `${font.role} ${font.minimumPt}pt is below ${minimum}pt`, font));
    }
  }

  const coverage = evidence.coverage || {};
  for (const name of COVERAGE_SETS) {
    const input = coverage.input && coverage.input[name];
    const output = coverage.output && coverage.output[name];
    if (!Array.isArray(input) || !Array.isArray(output) || !sameSet(input, output)) {
      blocking.push(issue('REPORT_COVERAGE_MISMATCH', name, 'input and output sets differ', { input: stableUnique(input), output: stableUnique(output) }));
    }
  }

  const htmlPages = Array.isArray(evidence.media && evidence.media.htmlPages) ? evidence.media.htmlPages : [];
  const pdfPages = Array.isArray(evidence.media && evidence.media.pdfPages) ? evidence.media.pdfPages : [];
  const htmlText = htmlPages.map(page => ({ id: page.id, text: normalizedText(page.text), digest: digest(normalizedText(page.text)) }));
  const pdfText = pdfPages.map(page => ({ id: page.id, text: normalizedText(page.text), digest: digest(normalizedText(page.text)) }));
  if (JSON.stringify(htmlText.map(({ id, digest: value }) => ({ id, digest: value }))) !== JSON.stringify(pdfText.map(({ id, digest: value }) => ({ id, digest: value })))) {
    blocking.push(issue('REPORT_TEXT_MISMATCH', 'media', 'HTML and PDF page text manifests differ'));
  }
  if (htmlPages.length !== paginationPages.length || pdfPages.length !== paginationPages.length) {
    blocking.push(issue('REPORT_PAGE_MANIFEST_MISMATCH', 'media', 'HTML, PDF, and pagination page counts differ'));
  }
  for (const resource of (evidence.media && evidence.media.resources) || []) {
    if (!resource.embedded || !String(resource.url || '').startsWith('data:')) {
      blocking.push(issue('REPORT_EXTERNAL_RESOURCE', resource.type || 'resource', 'resource is not embedded', { url: resource.url || '' }));
    }
  }

  const regression = evidence.regression || {};
  if (!regression.baselineDigest || !regression.candidateDigest) {
    blocking.push(issue('REPORT_VISUAL_BASELINE_MISSING', 'visual-regression', 'baseline and candidate digests are required'));
  }
  const changed = regression.baselineDigest !== regression.candidateDigest || (regression.differences || []).length > 0;
  if (regression.baselineDigest && regression.candidateDigest && changed) {
    if (validDisposition(regression.disposition)) {
      warnings.push(issue('REPORT_VISUAL_DIFFERENCE_ACCEPTED', 'visual-regression', regression.disposition.reason, { disposition: regression.disposition, differences: regression.differences || [] }));
    } else {
      blocking.push(issue('REPORT_VISUAL_REGRESSION', 'visual-regression', 'visual differences require a complete human disposition', { differences: regression.differences || [] }));
    }
  }

  const sorter = (left, right) => left.code.localeCompare(right.code) || left.location.localeCompare(right.location) || left.detail.localeCompare(right.detail);
  blocking.sort(sorter);
  warnings.sort(sorter);
  return {
    schemaVersion: '1.0',
    status: blocking.length ? 'failed' : warnings.length ? 'passed-with-disposition' : 'passed',
    blocking,
    warnings,
    pageManifest: { pageCount: paginationPages.length, pages: paginationPages.map(page => ({ id: page.id, number: page.number, intentionalBlank: Boolean(page.intentionalBlank), geometry: page.geometry })) },
    textManifest: { pages: htmlText.map((page, index) => ({ id: page.id, htmlDigest: page.digest, pdfDigest: pdfText[index] && pdfText[index].digest })) },
    audit: { visualRegression: { baselineDigest: regression.baselineDigest || '', candidateDigest: regression.candidateDigest || '', differences: regression.differences || [], disposition: regression.disposition || null } },
  };
}

function main() {
  const input = process.argv[2] ? fs.readFileSync(process.argv[2], 'utf8') : fs.readFileSync(0, 'utf8');
  const result = evaluate(JSON.parse(input));
  const output = `${JSON.stringify(result, null, 2)}\n`;
  if (process.argv[3]) fs.writeFileSync(process.argv[3], output);
  process.stdout.write(output);
}

if (require.main === module) {
  try { main(); } catch (error) { process.stderr.write(`${error.code || 'REPORT_QA_FAILED'}: ${error.message}\n`); process.exit(1); }
}

module.exports = { A4, COVERAGE_SETS, MEDIA_TOLERANCE_MM, evaluate };
