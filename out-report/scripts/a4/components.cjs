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

function componentContract(allowedBlocks, visualHierarchy, allowedLayouts, capacity, splitStrategy, failureConditions, requiredFields = [], predicates = []) {
  return Object.freeze({
    allowed_blocks: Object.freeze(allowedBlocks),
    visual_hierarchy: Object.freeze(visualHierarchy),
    allowed_layouts: Object.freeze(allowedLayouts),
    capacity_dimensions: Object.freeze({ ...capacity, field: capacity.field || 'blocks' }),
    split_strategy: splitStrategy,
    failure_conditions: Object.freeze(failureConditions),
    required_fields: Object.freeze(requiredFields),
    predicates: Object.freeze(predicates),
  });
}

const COMPONENT_CONTRACTS = Object.freeze({
  cover: componentContract(
    ['text'], ['title', 'decision', 'date'], ['overview-detail'],
    { soft: 1, hard: 1, unit: 'title groups' }, 'Never split the cover.',
    ['More than one title group', 'Analytical exhibits on the cover'],
  ),
  toc: componentContract(
    ['text'], ['title', 'chapter list', 'page reference'], ['full-evidence'],
    { soft: 8, hard: 12, unit: 'entries', field: 'entries' }, 'Continue the entry list with the heading repeated.',
    ['Entry without a destination', 'More than twelve entries on one page'], ['entries'], ['entry_destination'],
  ),
  'executive-summary': componentContract(
    ['text', 'metric', 'chart'], ['answer', 'decisions', 'evidence chain'], ['overview-detail', 'small-multiples'],
    { soft: 3, hard: 4, unit: 'decisions or metrics' }, 'Move supporting analysis to dedicated evidence pages.',
    ['More than one governing answer', 'Metric without qualification'],
  ),
  'section-title': componentContract(
    ['text'], ['chapter number', 'chapter claim', 'reading cue'], ['overview-detail'],
    { soft: 1, hard: 1, unit: 'chapter claims' }, 'Never split a chapter opener.',
    ['More than one chapter claim', 'Evidence table on a chapter opener'],
  ),
  'claim-evidence': componentContract(
    ['text', 'table', 'chart'], ['claim', 'primary evidence', 'limitation', 'source'], ['full-evidence', 'prose-aside'],
    { soft: 4, hard: 6, unit: 'evidence groups' }, 'Split after the primary exhibit and repeat the claim context.',
    ['Evidence without a claim', 'Source detached from evidence'],
  ),
  'data-chart': componentContract(
    ['chart', 'table', 'text'], ['claim', 'plot', 'annotation', 'source'], ['full-evidence', 'chart-sidebar', 'chart-table', 'small-multiples', 'decision-matrix'],
    { soft: 5, hard: 7, unit: 'chart categories or steps', field: 'items' }, 'Continue detail after the plot; do not shrink the plot below its form minimum.',
    ['Unlabelled unit or period', 'Color-only identity', 'Plot above hard capacity'], ['unit', 'period', 'items'], ['unit_period'],
  ),
  comparison: componentContract(
    ['table', 'metric', 'text'], ['decision claim', 'shared criteria', 'preferred option', 'implication'], ['comparison-columns'],
    { soft: 3, hard: 4, unit: 'alternatives', field: 'alternatives' }, 'Start a second comparison page with criteria repeated.',
    ['Alternatives use different criteria', 'Preference encoded by color alone'], ['criteria', 'alternatives'], ['shared_criteria'],
  ),
  'pain-demand': componentContract(
    ['text', 'metric', 'chart', 'table'], ['pain claim', 'customer evidence', 'demand strength', 'limitation'], ['chart-sidebar', 'small-multiples', 'prose-aside', 'full-evidence'],
    { soft: 4, hard: 6, unit: 'pain or evidence groups' }, 'Keep one pain cluster per page and carry limitations forward.',
    ['Anonymous evidence without limitation', 'Demand strength without observable behavior'],
  ),
  'market-trend': componentContract(
    ['chart', 'table', 'text', 'metric'], ['market claim', 'trend exhibit', 'drivers', 'uncertainty'], ['chart-sidebar', 'full-evidence', 'small-multiples'],
    { soft: 4, hard: 6, unit: 'series or drivers' }, 'Split by horizon or driver while repeating unit and period.',
    ['Mixed units without normalization', 'Forecast shown as actual'],
  ),
  'risk-boundary': componentContract(
    ['chart', 'table', 'text'], ['risk claim', 'risk field', 'counter-evidence', 'boundary'], ['decision-matrix', 'full-evidence'],
    { soft: 5, hard: 8, unit: 'risks' }, 'Move lower-priority risks to a continued register.',
    ['Risk without response priority', 'Qualitative position presented as measured probability'],
  ),
  'recommendation-roadmap': componentContract(
    ['text', 'metric', 'table'], ['recommendation', 'stages', 'decision gates', 'stop condition'], ['process-roadmap'],
    { soft: 3, hard: 5, unit: 'stages', field: 'stages' }, 'Continue only after a stage boundary and repeat the time context.',
    ['Stage without a gate', 'Date without an accountable output'], ['stages'], ['stage_gate'],
  ),
  'references-appendix': componentContract(
    ['table', 'text', 'metric'], ['section heading', 'auditable records', 'notes'], ['continued-table', 'full-evidence'],
    { soft: 7, hard: 8, unit: 'rows per page', field: 'references' }, 'Continue at a row boundary with headers and context repeated.',
    ['Changed columns across pages', 'Missing source locator'], ['references'], ['source_locator'],
  ),
});

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

function present(value) {
  return typeof value === 'string' ? value.trim().length > 0 : value !== undefined && value !== null;
}

const COMPONENT_PREDICATES = Object.freeze({
  entry_destination(payload) {
    return Array.isArray(payload.entries) && payload.entries.length > 0 && payload.entries.every(entry => entry && present(entry.destination));
  },
  unit_period(payload) {
    return present(payload.unit) && present(payload.period);
  },
  shared_criteria(payload) {
    if (!Array.isArray(payload.criteria) || payload.criteria.length === 0 || !Array.isArray(payload.alternatives) || payload.alternatives.length === 0) return false;
    return payload.criteria.every(present) && payload.alternatives.every(alternative => {
      const values = alternative && alternative.values;
      return values && payload.criteria.every(criterion => Object.hasOwn(values, criterion));
    });
  },
  stage_gate(payload) {
    return Array.isArray(payload.stages) && payload.stages.length > 0 && payload.stages.every(stage => stage && present(stage.gate));
  },
  source_locator(payload) {
    return Array.isArray(payload.references) && payload.references.length > 0 && payload.references.every(reference =>
      reference && Array.isArray(reference.locators) && reference.locators.length > 0 && reference.locators.every(present)
    );
  },
});

function validateComponentContent(kind, payload, contract) {
  for (const field of contract.required_fields) {
    if (!present(payload[field])) {
      throw reportError('REPORT_COMPONENT_CONTRACT', `${kind} requires field: ${field}`);
    }
  }
  for (const predicateName of contract.predicates) {
    const predicate = COMPONENT_PREDICATES[predicateName];
    if (!predicate || !predicate(payload)) {
      throw reportError('REPORT_COMPONENT_CONTRACT', `${kind} failed predicate: ${predicateName}`);
    }
  }
}

function deriveCapacity(payload, contract, componentBlocks) {
  const field = contract.capacity_dimensions.field;
  if (field === 'blocks') return componentBlocks.length;
  return Array.isArray(payload[field]) ? payload[field].length : 0;
}

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
  const contract = COMPONENT_CONTRACTS[kind];
  const layoutId = payload.layout_id;
  if (!contract.allowed_layouts.includes(layoutId)) {
    throw reportError('REPORT_COMPONENT_CONTRACT', `${kind} does not allow layout: ${layoutId}`);
  }
  const componentBlocks = list(payload.blocks);
  const invalidBlock = componentBlocks.find(block => !contract.allowed_blocks.includes(block && block.kind));
  if (invalidBlock) {
    throw reportError('REPORT_COMPONENT_CONTRACT', `${kind} does not allow block kind: ${invalidBlock.kind}`);
  }
  validateComponentContent(kind, payload, contract);
  const capacityCount = deriveCapacity(payload, contract, componentBlocks);
  if (payload.capacity_count !== undefined && payload.capacity_count !== capacityCount) {
    throw reportError('REPORT_COMPONENT_CONTRACT', `${kind} capacity_count ${payload.capacity_count} does not match derived capacity ${capacityCount}`);
  }
  if (!Number.isInteger(capacityCount) || capacityCount < 0) {
    throw reportError('REPORT_COMPONENT_CONTRACT', `${kind} capacity_count must be a non-negative integer`);
  }
  if (capacityCount > contract.capacity_dimensions.hard) {
    throw reportError('REPORT_COMPONENT_CAPACITY', `${kind} capacity ${capacityCount} exceeds ${contract.capacity_dimensions.hard}`);
  }
  const id = payload.id || kind;
  const title = payload.title || '';
  const blocks = componentBlocks.map(block => renderBlock(block, context)).join('');
  const tag = kind === 'toc' ? 'nav' : kind === 'references-appendix' ? 'aside' : 'section';
  const landmarkLabel = kind === 'toc' ? ' aria-label="Table of contents"' : kind === 'references-appendix' ? ' aria-label="References and appendix"' : '';
  const headingTag = kind === 'cover' ? 'h1' : 'h2';
  return `<${tag} class="report-component report-component--${escapeHtml(kind)}" data-component-kind="${escapeHtml(kind)}" data-component-id="${escapeHtml(id)}" data-layout-id="${escapeHtml(layoutId)}" data-capacity-count="${capacityCount}" data-capacity-soft="${contract.capacity_dimensions.soft}" data-capacity-hard="${contract.capacity_dimensions.hard}" data-capacity-unit="${escapeHtml(contract.capacity_dimensions.unit)}" data-split-strategy="${escapeHtml(contract.split_strategy)}" aria-labelledby="${escapeHtml(id)}-title"${landmarkLabel}><${headingTag} id="${escapeHtml(id)}-title">${escapeHtml(title)}</${headingTag}>${blocks}</${tag}>`;
}

module.exports = {
  APPROVED_BLOCK_KINDS,
  APPROVED_COMPONENT_KINDS,
  COMPONENT_CONTRACTS,
  renderBlock,
  renderComponent,
};
