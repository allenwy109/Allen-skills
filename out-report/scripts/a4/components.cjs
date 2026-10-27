'use strict';

const { escapeHtml } = require('./escape.cjs');

const APPROVED_BLOCK_KINDS = Object.freeze(['chart', 'text', 'metric', 'table']);
const APPROVED_COMPONENT_KINDS = Object.freeze([
  'cover',
  'toc',
  'executive-summary',
  'section-title',
  'claim-evidence',
  'data-chart',
  'comparison',
  'pain-demand',
  'market-trend',
  'risk-boundary',
  'recommendation-roadmap',
  'references-appendix',
]);

const DEFAULT_IDENTITY_ENCODINGS = Object.freeze({
  fact: { line: 'solid', fill: 'solid', marker: 'circle', text: 'Fact' },
  data: { line: 'solid', fill: 'solid', marker: 'square', text: 'Data' },
  estimate: { line: 'dashed', fill: 'outline', marker: 'triangle', text: 'Estimate' },
  forecast: { line: 'dotted', fill: 'hatch', marker: 'diamond', text: 'Forecast' },
  assumption: { line: 'dashed', fill: 'outline', marker: 'square', text: 'Assumption' },
  judgment: { line: 'solid', fill: 'outline', marker: 'circle', text: 'Judgment' },
  recommendation: { line: 'double', fill: 'none', marker: 'target-ring', text: 'Recommendation' },
  third_party_view: { line: 'dotted', fill: 'outline', marker: 'triangle', text: 'Third-party view' },
});

function reportError(code, detail) {
  const error = new Error(`${code}: ${detail}`);
  error.code = code;
  return error;
}

function list(value) {
  return Array.isArray(value) ? value : [];
}

function dataRefs(name, values) {
  return list(values).map(value => `<span hidden data-${name}="${escapeHtml(value)}"></span>`).join('');
}

function sourceRefs(block) {
  const declared = dataRefs('source-id', block.source_ids);
  const bindings = list(block.source_bindings).map(binding => {
    const source = escapeHtml(binding && binding.source_id);
    return list(binding && binding.locators).map(locator =>
      `<span hidden data-source-id="${source}" data-source-locator="${escapeHtml(locator)}"></span>`
    ).join('');
  }).join('');
  return declared + bindings;
}

function identityLegend(block, context) {
  const encodings = context && context.identityEncodings ? context.identityEncodings : DEFAULT_IDENTITY_ENCODINGS;
  return list(block.identity).map(identity => {
    const encoding = encodings[identity] || DEFAULT_IDENTITY_ENCODINGS[identity] || {
      line: 'solid', fill: 'outline', marker: 'circle', text: identity,
    };
    return `<span class="identity-key" data-identity="${escapeHtml(identity)}" data-line="${escapeHtml(encoding.line)}" data-fill="${escapeHtml(encoding.fill)}" data-marker="${escapeHtml(encoding.marker)}">${escapeHtml(encoding.text)}</span>`;
  }).join('');
}

function bindings(block, context) {
  return [
    dataRefs('panel-id', block.panel_refs),
    dataRefs('relation-id', block.relation_refs),
    dataRefs('claim-id', block.claim_refs),
    dataRefs('metric-id', block.metric_refs),
    sourceRefs(block),
    `<div class="identity-legend" aria-label="Evidence identity">${identityLegend(block, context)}</div>`,
  ].join('');
}

function blockHeader(block) {
  const content = block.content || {};
  const subtitle = content.subtitle ? `<p class="block-subtitle">${escapeHtml(content.subtitle)}</p>` : '';
  return `<header><h3 id="${escapeHtml(block.id)}-title">${escapeHtml(content.title)}</h3>${subtitle}</header>`;
}

function commonBody(block) {
  const content = block.content || {};
  return `<p class="block-purpose">${escapeHtml(content.purpose)}</p><p class="block-reason">${escapeHtml(content.reason)}</p>`;
}

function chartBody(block) {
  const label = escapeHtml((block.content || {}).visual || (block.content || {}).title || 'Chart');
  return `<figure class="block-figure"><svg aria-hidden="true" viewBox="0 0 120 48" focusable="false"><line x1="8" y1="40" x2="112" y2="40"></line><rect x="18" y="22" width="20" height="18"></rect><rect x="50" y="12" width="20" height="28"></rect><rect x="82" y="6" width="20" height="34"></rect></svg><figcaption>${label}</figcaption></figure>`;
}

function textBody(block) {
  return `<div class="text-body">${commonBody(block)}</div>`;
}

function metricBody(block) {
  const content = block.content || {};
  return `<dl class="metric-body"><div><dt>${escapeHtml(content.relationship)}</dt><dd>${escapeHtml(content.visual || content.purpose)}</dd></div></dl>`;
}

function tableBody(block) {
  const content = block.content || {};
  return `<table class="table-body"><thead><tr><th scope="col">Relationship</th><th scope="col">Evidence</th></tr></thead><tbody><tr><th scope="row">${escapeHtml(content.relationship)}</th><td>${escapeHtml(content.purpose)}</td></tr></tbody></table>`;
}

const BLOCK_RENDERERS = Object.freeze({ chart: chartBody, text: textBody, metric: metricBody, table: tableBody });

function renderBlock(block, context = {}) {
  if (!block || !Object.hasOwn(BLOCK_RENDERERS, block.kind)) {
    throw reportError('REPORT_UNSUPPORTED_BLOCK', `unsupported block kind: ${block && block.kind}`);
  }
  const content = block.content || {};
  const anchor = content.anchor ? ' data-anchor="true"' : '';
  return `<article class="report-block report-block--${escapeHtml(block.kind)}" data-block-id="${escapeHtml(block.id)}" data-block-kind="${escapeHtml(block.kind)}" data-form="${escapeHtml(content.form)}" data-role="${escapeHtml(content.role)}" aria-labelledby="${escapeHtml(block.id)}-title"${anchor}>${blockHeader(block)}${BLOCK_RENDERERS[block.kind](block)}${bindings(block, context)}</article>`;
}

function renderComponent(kind, payload = {}, context = {}) {
  if (!APPROVED_COMPONENT_KINDS.includes(kind)) {
    throw reportError('REPORT_UNSUPPORTED_COMPONENT', `unsupported component kind: ${kind}`);
  }
  const id = payload.id || kind;
  const title = payload.title || '';
  const blocks = list(payload.blocks).map(block => renderBlock(block, context)).join('');
  const tag = kind === 'cover' || kind === 'section-title' ? 'header' : 'section';
  const navLabel = kind === 'toc' ? ' aria-label="Table of contents"' : '';
  return `<${tag} class="report-component report-component--${escapeHtml(kind)}" data-component-kind="${escapeHtml(kind)}" data-component-id="${escapeHtml(id)}" aria-labelledby="${escapeHtml(id)}-title"${navLabel}><h2 id="${escapeHtml(id)}-title">${escapeHtml(title)}</h2>${blocks}</${tag}>`;
}

module.exports = {
  APPROVED_BLOCK_KINDS,
  APPROVED_COMPONENT_KINDS,
  renderBlock,
  renderComponent,
};
