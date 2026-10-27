#!/usr/bin/env node
'use strict';

const fs = require('fs');
const crypto = require('crypto');

const COVERAGE_SETS = Object.freeze(['claims', 'a_cards', 'panels', 'relations', 'metrics', 'sources']);
const A4 = Object.freeze([210, 297]);
const MEDIA_TOLERANCE_MM = 0.2;
const PAGE_ID = /^page-\d{3,}$/;
const SHA256 = /^[0-9a-f]{64}$/;
const ISO8601_TZ = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/;

function normalizedText(value) {
  return String(value || '').replace(/\s+/g, ' ').trim();
}

function digest(value) {
  return crypto.createHash('sha256').update(value).digest('hex');
}

function canonicalJson(value) {
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(',')}]`;
  if (value && typeof value === 'object') return `{${Object.keys(value).sort().map(key => `${JSON.stringify(key)}:${canonicalJson(value[key])}`).join(',')}}`;
  return JSON.stringify(value);
}

function structuredDigest(value) {
  return digest(canonicalJson(value));
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

function validDisposition(value, regression) {
  return value && value.decision === 'accepted' &&
    typeof value.reviewer === 'string' && value.reviewer.trim() &&
    typeof value.reason === 'string' && value.reason.trim() &&
    typeof value.reviewedAt === 'string' && ISO8601_TZ.test(value.reviewedAt) && Number.isFinite(Date.parse(value.reviewedAt)) &&
    value.baselineDigest === regression.baselineDigest &&
    value.candidateDigest === regression.candidateDigest &&
    value.differenceDigest === regression.differenceDigest;
}

function deriveDifferences(baselinePages, candidatePages) {
  const baseline = new Map((baselinePages || []).map(page => [page.id, page.digest]));
  const candidate = new Map((candidatePages || []).map(page => [page.id, page.digest]));
  return [...new Set([...baseline.keys(), ...candidate.keys()])].sort().flatMap(page => {
    const before = baseline.get(page) ?? null;
    const after = candidate.get(page) ?? null;
    if (before === after) return [];
    return [{ page, kind: before === null ? 'added' : after === null ? 'removed' : 'changed', baseline: before, candidate: after }];
  });
}

function finiteNumber(value) {
  return typeof value === 'number' && Number.isFinite(value);
}

function visibleHtml(value) {
  let html = String(value || '');
  let previous;
  do {
    previous = html;
    html = html.replace(/<([a-z][\w:-]*)\b[^>]*\s+hidden(?:\s*=\s*(?:"[^"]*"|'[^']*'|[^\s>]+))?[^>]*>[\s\S]*?<\/\1\s*>/gi, '');
  } while (html !== previous);
  return html.replace(/<[^>]*\s+hidden(?:\s*=\s*(?:"[^"]*"|'[^']*'|[^\s>]+))?[^>]*\/?>/gi, '');
}

function classPattern(name) {
  return new RegExp(`class\\s*=\\s*["'][^"']*\\b${name}\\b[^"']*["']`, 'i');
}

function evidenceErrors(evidence) {
  const errors = [];
  const invalid = (location, detail) => errors.push(issue('REPORT_QA_EVIDENCE_INVALID', location, detail));
  const pagination = evidence.pagination;
  if (!pagination || typeof pagination !== 'object' || !Array.isArray(pagination.pages) || !Number.isInteger(pagination.pageCount)) {
    invalid('pagination', 'pageCount integer and pages array are required');
  } else {
    const ids = pagination.pages.map(page => page && page.id);
    pagination.pages.forEach((page, index) => {
      const location = `pagination.pages[${index}]`;
      if (!page || typeof page !== 'object' || typeof page.id !== 'string' || !PAGE_ID.test(page.id) || page.number !== index + 1 ||
          typeof page.intentionalBlank !== 'boolean' || !finiteNumber(page.usedHeightPx) || !finiteNumber(page.contentHeightPx)) {
        invalid(location, 'stable page ID, sequential number, intentionalBlank, usedHeightPx, and contentHeightPx are required');
      }
    });
    if (new Set(ids).size !== ids.length) invalid('pagination.pages', 'page IDs must be unique');
  }
  const geometry = evidence.geometry;
  if (!geometry || typeof geometry !== 'object' || !Array.isArray(geometry.pages)) {
    invalid('geometry', 'pages array is required');
  } else {
    const ids = geometry.pages.map(page => page && page.id);
    geometry.pages.forEach((page, index) => {
      const location = `geometry.pages[${index}]`;
      if (!page || typeof page !== 'object' || typeof page.id !== 'string' || !page.id ||
          !Array.isArray(page.mediaBoxMm) || page.mediaBoxMm.length !== 2 || !page.mediaBoxMm.every(finiteNumber) ||
          !Array.isArray(page.overlaps) || !Array.isArray(page.clipped) || typeof page.empty !== 'boolean' || !Array.isArray(page.fonts)) {
        invalid(location, 'id, finite MediaBox, overlaps, clipped, empty, and fonts are required');
      } else {
        page.fonts.forEach((font, fontIndex) => {
          if (!font || typeof font.role !== 'string' || !font.role || !finiteNumber(font.minimumPt)) invalid(`${location}.fonts[${fontIndex}]`, 'role and finite minimumPt are required');
        });
      }
    });
    if (new Set(ids).size !== ids.length) invalid('geometry.pages', 'page IDs must be unique');
  }
  const media = evidence.media;
  if (!media || typeof media !== 'object' || !Array.isArray(media.htmlPages) || !Array.isArray(media.pdfPages) || !Array.isArray(media.resources)) {
    invalid('media', 'htmlPages, pdfPages, and resources arrays are required');
  } else {
    const intentionalBlankIds = new Set(pagination && Array.isArray(pagination.pages)
      ? pagination.pages.filter(page => page && page.intentionalBlank).map(page => page.id) : []);
    for (const name of ['htmlPages', 'pdfPages']) media[name].forEach((page, index) => {
      if (!page || typeof page.id !== 'string' || !page.id || typeof page.text !== 'string') invalid(`media.${name}[${index}]`, 'id and text strings are required');
      if (name === 'htmlPages') {
        if (!page || typeof page.role !== 'string' || !page.role || typeof page.visibleHtml !== 'string') {
          invalid(`media.${name}[${index}]`, 'role and visibleHtml strings are required');
        } else if (!intentionalBlankIds.has(page.id)) {
          const html = visibleHtml(page.visibleHtml);
          if (!html.trim()) invalid(`media.${name}[${index}].visibleHtml`, 'non-blank pages require visible HTML evidence');
          else if (normalizedText(page.text) && !normalizedText(html.replace(/<[^>]+>/g, ' ').replace(/&(?:nbsp|#160);/gi, ' '))) {
            invalid(`media.${name}[${index}].visibleHtml`, 'visible HTML evidence cannot be text-empty when page text is present');
          }
        }
      }
    });
    media.resources.forEach((resource, index) => {
      if (!resource || typeof resource.type !== 'string' || typeof resource.url !== 'string' || typeof resource.embedded !== 'boolean') invalid(`media.resources[${index}]`, 'type, url, and embedded are required');
    });
    if (!Array.isArray(media.appendixDestinations) || media.appendixDestinations.some(value => typeof value !== 'string' || !value)) invalid('media.appendixDestinations', 'must be an array of non-empty strings');
    for (const name of ['htmlPages', 'pdfPages']) {
      const ids = media[name].map(page => page && page.id);
      if (new Set(ids).size !== ids.length) invalid(`media.${name}`, 'page IDs must be unique');
    }
  }
  const coverage = evidence.coverage;
  if (!coverage || typeof coverage !== 'object') invalid('coverage', 'input and output are required');
  else for (const side of ['input', 'output']) for (const name of COVERAGE_SETS) {
    const values = coverage[side] && coverage[side][name];
    if (!Array.isArray(values) || values.some(value => typeof value !== 'string' || !value.trim())) invalid(`coverage.${side}.${name}`, 'must be an array of non-empty strings');
    else if (new Set(values).size !== values.length) invalid(`coverage.${side}.${name}`, 'duplicate IDs are forbidden');
  }
  const paginationIds = pagination && Array.isArray(pagination.pages) ? pagination.pages.map(page => page && page.id) : [];
  const regression = evidence.regression;
  if (!regression || typeof regression !== 'object') invalid('regression', 'complete regression manifest is required');
  else {
    if (!['identical', 'different'].includes(regression.status)) invalid('regression.status', 'must be identical or different');
    if (!SHA256.test(regression.baselineDigest || '') || !SHA256.test(regression.candidateDigest || '') || !SHA256.test(regression.differenceDigest || '')) invalid('regression', 'summary and difference digests must be SHA-256 hex');
    if (regression.baselineUpdated !== false) invalid('regression.baselineUpdated', 'must be false');
    const baselinePages = regression.baselinePages;
    if (!Array.isArray(baselinePages) || !baselinePages.length || baselinePages.some(page => !page || !PAGE_ID.test(page.id || '') || !SHA256.test(page.digest || '')) || new Set((baselinePages || []).map(page => page.id)).size !== (baselinePages || []).length) invalid('regression.baselinePages', 'must be a non-empty unique stable-page-ID to SHA-256 sequence');
    const candidatePages = regression.candidatePages;
    if (!Array.isArray(candidatePages) || candidatePages.length !== paginationIds.length || candidatePages.some((page, index) => !page || page.id !== paginationIds[index] || !SHA256.test(page.digest || ''))) invalid('regression.candidatePages', 'page IDs/order must match pagination and digests must be SHA-256 hex');
    if (!Array.isArray(regression.differences)) invalid('regression.differences', 'must be an array');
    if (Array.isArray(regression.baselinePages)) {
      const summary = Object.fromEntries(regression.baselinePages.map(page => [page.id, page.digest]));
      if (regression.baselineDigest !== structuredDigest(summary)) invalid('regression.baselineDigest', 'does not summarize baselinePages');
    }
    if (Array.isArray(regression.candidatePages)) {
      const summary = Object.fromEntries(regression.candidatePages.map(page => [page.id, page.digest]));
      if (regression.candidateDigest !== structuredDigest(summary)) invalid('regression.candidateDigest', 'does not summarize candidatePages');
    }
    if (Array.isArray(regression.differences) && regression.differenceDigest !== structuredDigest(regression.differences)) invalid('regression.differenceDigest', 'does not summarize differences');
    if (Array.isArray(baselinePages) && Array.isArray(candidatePages) && Array.isArray(regression.differences)) {
      const expected = deriveDifferences(baselinePages, candidatePages);
      if (canonicalJson(regression.differences) !== canonicalJson(expected)) invalid('regression.differences', 'does not equal differences derived from baselinePages and candidatePages');
      if (regression.differenceDigest !== structuredDigest(expected)) invalid('regression.differenceDigest', 'does not summarize derived differences');
    }
    if (regression.status === 'identical' && (regression.baselineDigest !== regression.candidateDigest || (regression.differences || []).length)) invalid('regression.status', 'identical status contradicts digests or differences');
    if (regression.status === 'different' && regression.baselineDigest === regression.candidateDigest && !(regression.differences || []).length) invalid('regression.status', 'different status requires a digest or page difference');
  }
  return errors;
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
  blocking.push(...evidenceErrors(evidence));

  for (const page of paginationPages) {
    if (finiteNumber(page.usedHeightPx) && finiteNumber(page.contentHeightPx) && page.usedHeightPx > page.contentHeightPx + 1) {
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
    if (Array.isArray(page.overlaps) && page.overlaps.length) blocking.push(issue('REPORT_ELEMENT_OVERLAP', page.id, 'elements overlap', { overlaps: page.overlaps }));
    if (Array.isArray(page.clipped) && page.clipped.length) blocking.push(issue('REPORT_CONTENT_CLIPPED', page.id, 'content is clipped', { clipped: page.clipped }));
    const paginationPage = paginationPages.find(candidate => candidate.id === page.id);
    if (page.empty && !(paginationPage && paginationPage.intentionalBlank)) blocking.push(issue('REPORT_EMPTY_PAGE', page.id, 'unintentional empty page'));
    for (const font of Array.isArray(page.fonts) ? page.fonts : []) {
      const minimum = ['source', 'citation'].includes(font.role) ? 7.5 : 8.5;
      if (finiteNumber(font.minimumPt) && font.minimumPt < minimum) blocking.push(issue('REPORT_FONT_TOO_SMALL', page.id, `${font.role} ${font.minimumPt}pt is below ${minimum}pt`, font));
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
  const appendixDestinations = Array.isArray(evidence.media && evidence.media.appendixDestinations)
    ? evidence.media.appendixDestinations : [];
  const destinationCounts = appendixDestinations.reduce((counts, id) => counts.set(id, (counts.get(id) || 0) + 1), new Map());
  for (const page of htmlPages) {
    const html = visibleHtml(page.visibleHtml);
    if (!html) continue;
    const isReference = page.role === 'references';
    if (!isReference && /https?:\/\//i.test(html.replace(/<[^>]+>/g, ' '))) {
      blocking.push(issue('REPORT_BODY_RAW_REFERENCE', page.id, 'visible body content contains a raw HTTP(S) reference'));
    }
    if (!isReference && (classPattern('source-strip').test(html) || classPattern('source').test(html) || /\bdata-reference-band(?:\s|=|>)/i.test(html))) {
      blocking.push(issue('REPORT_BODY_SOURCE_STRIP', page.id, 'visible body content contains a legacy reference band'));
    }
    const markers = [...html.matchAll(/<[^>]*class\s*=\s*["'][^"']*\bcitation-marker\b[^"']*["'][^>]*>/gi)].map(match => {
      const href = match[0].match(/\bhref\s*=\s*["']#([^"']+)["']/i);
      return href && href[1];
    });
    for (const target of markers) if (!target || destinationCounts.get(target) !== 1) {
      blocking.push(issue('REPORT_CITATION_MISMATCH', page.id, target ? `citation target ${target} must resolve to exactly one appendix destination` : 'citation marker has no appendix destination', { target: target || '', destinations: target ? destinationCounts.get(target) || 0 : 0 }));
    }
    if (isReference && /\bdata-row-split\s*=\s*["']continued["']/i.test(html) && !/\bdata-continuation-header(?:\s|=|>)/i.test(html)) {
      blocking.push(issue('REPORT_PAGE_OVERFLOW', page.id, 'appendix row continues without a continuation header'));
    }
  }
  const htmlText = htmlPages.map(page => ({ id: page.id, text: normalizedText(page.text), digest: digest(normalizedText(page.text)) }));
  const pdfText = pdfPages.map(page => ({ id: page.id, text: normalizedText(page.text), digest: digest(normalizedText(page.text)) }));
  if (JSON.stringify(htmlText.map(({ id, digest: value }) => ({ id, digest: value }))) !== JSON.stringify(pdfText.map(({ id, digest: value }) => ({ id, digest: value })))) {
    blocking.push(issue('REPORT_TEXT_MISMATCH', 'media', 'HTML and PDF page text manifests differ'));
  }
  if (htmlPages.length !== paginationPages.length || pdfPages.length !== paginationPages.length) {
    blocking.push(issue('REPORT_PAGE_MANIFEST_MISMATCH', 'media', 'HTML, PDF, and pagination page counts differ'));
  }
  const htmlIds = htmlPages.map(page => page.id);
  const pdfIds = pdfPages.map(page => page.id);
  if (JSON.stringify(htmlIds) !== JSON.stringify(paginationIds) || JSON.stringify(pdfIds) !== JSON.stringify(paginationIds)) {
    blocking.push(issue('REPORT_PAGE_MANIFEST_MISMATCH', 'media', 'HTML, PDF, and pagination page IDs or order differ', { pagination: paginationIds, html: htmlIds, pdf: pdfIds }));
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
    if (validDisposition(regression.disposition, regression)) {
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

module.exports = { A4, COVERAGE_SETS, MEDIA_TOLERANCE_MM, evaluate, evidenceErrors, deriveDifferences };
