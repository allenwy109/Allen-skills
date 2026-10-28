'use strict';

const fs = require('fs');
const path = require('path');
const { escapeHtml } = require('./escape.cjs');
const EXHIBIT_LAYOUTS = new Map(JSON.parse(fs.readFileSync(path.join(__dirname, '../../assets/a4-layout-catalog.json'), 'utf8')).exhibits.map(item => [item.kind, item]));
const SEMANTIC_LAYOUTS = new Map([...EXHIBIT_LAYOUTS.values()].flatMap(item => item.semantic_types.map(semantic => [semantic, item])));

const APPROVED_BLOCK_KINDS = Object.freeze(['chart', 'text', 'metric', 'table']);
const APPROVED_COMPONENT_KINDS = Object.freeze([
  'cover',
  'toc',
  'executive-summary',
  'section-title',
  'native-exhibit',
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
    { soft: 1, hard: 1, unit: 'title groups', field: 'title_groups' }, 'Never split the cover.',
    ['More than one title group', 'Analytical exhibits on the cover'], ['title', 'title_groups'], ['single_title_group'],
  ),
  toc: componentContract(
    ['text'], ['title', 'chapter list', 'page reference'], ['full-evidence'],
    { soft: 8, hard: 12, unit: 'entries', field: 'entries' }, 'Continue the entry list with the heading repeated.',
    ['Entry without a destination', 'More than twelve entries on one page'], ['entries'], ['entry_destination'],
  ),
  'executive-summary': componentContract(
    ['text', 'metric', 'chart'], ['answer', 'decisions', 'evidence chain'], ['overview-detail', 'small-multiples'],
    { soft: 3, hard: 4, unit: 'decisions or metrics', field: 'summary_items' }, 'Move supporting analysis to dedicated evidence pages.',
    ['More than one governing answer', 'Metric without qualification'],
    ['answers', 'summary_items', 'decision_level', 'decisive_reasons', 'largest_upside', 'largest_risk', 'immediate_actions', 'thresholds'],
    ['single_answer', 'qualified_summary_item', 'complete_decision_summary'],
  ),
  'section-title': componentContract(
    ['text'], ['chapter number', 'chapter claim', 'reading cue'], ['overview-detail'],
    { soft: 1, hard: 1, unit: 'chapter claims', field: 'chapter_claims' }, 'Never split a chapter opener.',
    ['More than one chapter claim', 'Evidence table on a chapter opener'], ['title', 'chapter_claims'], ['single_chapter_claim'],
  ),
  'native-exhibit': componentContract(
    ['text', 'table', 'chart', 'metric'], ['decision claim', 'native exhibit', 'qualification', 'compact sources'], ['full-evidence'],
    { soft: 1, hard: 1, unit: 'native exhibits', field: 'exhibits' }, 'Keep the native exhibit intact; move supporting detail to another component.',
    ['Missing structured exhibit', 'More than one exhibit in a component'], ['blocks', 'exhibits'], ['native_exhibit_block'],
  ),
  'claim-evidence': componentContract(
    ['text', 'table', 'chart'], ['claim', 'primary evidence', 'limitation', 'source'], ['full-evidence', 'prose-aside'],
    { soft: 4, hard: 6, unit: 'evidence groups', field: 'evidence_groups' }, 'Split after the primary exhibit and repeat the claim context.',
    ['Evidence without a claim', 'Source detached from evidence'], ['claim', 'evidence_groups'], ['evidence_source_locator'],
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
    { soft: 4, hard: 6, unit: 'pain or evidence groups', field: 'pain_groups' }, 'Keep one pain cluster per page and carry limitations forward.',
    ['Anonymous evidence without limitation', 'Demand strength without observable behavior'], ['pain_groups'], ['observable_behavior'],
  ),
  'market-trend': componentContract(
    ['chart', 'table', 'text', 'metric'], ['market claim', 'trend exhibit', 'drivers', 'uncertainty'], ['chart-sidebar', 'full-evidence', 'small-multiples'],
    { soft: 4, hard: 6, unit: 'series or drivers', field: 'series_or_drivers' }, 'Split by horizon or driver while repeating unit and period.',
    ['Mixed units without normalization', 'Forecast shown as actual'], ['unit', 'period', 'series_or_drivers'], ['unit_period', 'series_or_driver_nonempty'],
  ),
  'risk-boundary': componentContract(
    ['chart', 'table', 'text'], ['risk claim', 'risk field', 'counter-evidence', 'boundary'], ['decision-matrix', 'full-evidence'],
    { soft: 5, hard: 8, unit: 'risks', field: 'risks' }, 'Move lower-priority risks to a continued register.',
    ['Risk without response priority', 'Qualitative position presented as measured probability'], ['risks'], ['risk_priority'],
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

function citationMarkers(block, context) {
  if (context && context.renderCitations === false) return '';
  const registry = new Map(list(context && context.citationRegistry).map(item => [item.source_id, item]));
  const seen = new Set();
  const markers = list(block.source_ids).filter(sourceId => {
    if (seen.has(sourceId)) return false;
    seen.add(sourceId);
    return true;
  }).map(sourceId => {
    const citation = registry.get(sourceId);
    if (!citation) return '';
    return `<a class="citation-marker" href="#${escapeHtml(citation.appendix_anchor)}">[${escapeHtml(citation.number)}]</a>`;
  }).join(' ');
  return markers ? `<sup class="citation-markers" aria-label="Sources">${markers}</sup>` : '';
}

function identityLegend(block, context) {
  const encodings = context && context.identityEncodings ? context.identityEncodings : DEFAULT_IDENTITY_ENCODINGS;
  return list(block.identity).map(identity => {
    const encoding = encodings[identity] || DEFAULT_IDENTITY_ENCODINGS[identity] || {
      line: 'solid', fill: 'outline', marker: 'circle', text: identity,
    };
    return `<span class="identity-key" data-identity="${escapeHtml(identity)}" data-line="${escapeHtml(encoding.line)}" data-fill="${escapeHtml(encoding.fill)}" data-marker="${escapeHtml(encoding.marker)}">${escapeHtml(encoding.text)}</span>`;
  }).join(' ');
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
  if (list((block.content || {}).claims).length) return claimBody(block);
  const label = escapeHtml((block.content || {}).visual || (block.content || {}).title || 'Chart');
  return `<figure class="block-figure"><svg aria-hidden="true" viewBox="0 0 120 48" focusable="false"><line x1="8" y1="40" x2="112" y2="40"></line><rect x="18" y="22" width="20" height="18"></rect><rect x="50" y="12" width="20" height="28"></rect><rect x="82" y="6" width="20" height="34"></rect></svg><figcaption>${label}</figcaption></figure>`;
}

function textBody(block) {
  return `<div class="text-body">${claimBody(block)}</div>`;
}

function metricBody(block) {
  const content = block.content || {};
  return `<dl class="metric-body"><div><dt>${escapeHtml(content.relationship)}</dt><dd>${escapeHtml(content.visual || content.purpose)}</dd></div></dl>`;
}

function tableBody(block) {
  const content = block.content || {};
  if (content.semantic_type === 'pain-demand' && list(content.pain_groups).length) return painBody(content.pain_groups);
  if (content.semantic_type === 'competition' && content.comparison) return comparisonBody(content.comparison);
  if (list(content.claims).length) return claimBody(block);
  return `<table class="table-body"><thead><tr><th scope="col">Relationship</th><th scope="col">Evidence</th></tr></thead><tbody><tr><th scope="row">${escapeHtml(content.relationship)}</th><td>${escapeHtml(content.purpose)}</td></tr></tbody></table>`;
}

function evidenceList(items, emptyText) {
  const values = list(items);
  const rows = values.slice(0, 1).map(item => `<li>${escapeHtml(item.excerpt)} <span class="evidence-locator">${escapeHtml(item.source_id)} · ${escapeHtml(item.locator)}</span></li>`).join('');
  const remainder = values.length > 1 ? `<li class="evidence-more">另 ${values.length - 1} 条见来源附录</li>` : '';
  return rows + remainder || `<li class="evidence-empty">${escapeHtml(emptyText)}</li>`;
}

function claimBody(block) {
  const claims = list((block.content || {}).claims);
  if (!claims.length) return commonBody(block);
  return `<div class="claim-details">${claims.map(claim => `<section class="claim-detail"><p class="claim-statement">${escapeHtml(claim.statement)}</p><dl class="claim-meta"><div><dt>身份 / 置信度</dt><dd>${escapeHtml(claim.identity)} · ${escapeHtml(claim.confidence)}</dd></div><div><dt>适用范围</dt><dd>${escapeHtml(claim.scope)}</dd></div></dl><div class="claim-evidence-pair"><div><h4>${claim.support_label === 'indirect_lead' ? '间接线索（不直接证明主张）' : '支持'}</h4><ul>${evidenceList(claim.support, '尚无支持证据')}</ul></div><div><h4>反证 / 反向检索</h4><ul>${evidenceList(claim.counter, '未取得结构化反证；这是验证缺口，不是反证结果')}</ul></div></div><p class="claim-limitation"><strong>边界：</strong>${escapeHtml(claim.limitation)}</p></section>`).join('')}</div>`;
}

function painBody(groups) {
  return `<div class="pain-groups">${list(groups).map(group => `<article class="pain-group"><h4>${escapeHtml(group.segment)}</h4><dl><div><dt>触发</dt><dd>${escapeHtml(group.trigger)}</dd></div><div><dt>当前替代</dt><dd>${escapeHtml(group.workaround)}</dd></div><div><dt>后果</dt><dd>${escapeHtml(group.consequence)}</dd></div><div><dt>购买信号</dt><dd>${escapeHtml(group.purchase_signal)}</dd></div><div><dt>证据强度</dt><dd>${escapeHtml(group.evidence_strength)}</dd></div><div><dt>反证 / 边界</dt><dd>${escapeHtml(group.counter)}</dd></div><div><dt>验证缺口</dt><dd>${escapeHtml(group.validation_gap)}</dd></div></dl></article>`).join('')}</div>`;
}

function comparisonBody(comparison) {
  const criteria = list(comparison.criteria);
  const headers = criteria.map(criterion => `<th scope="col">${escapeHtml(criterion)}</th>`).join('');
  const rows = list(comparison.alternatives).map(alternative => `<tr><th scope="row"><span class="competition-layer">${escapeHtml(alternative.layer)}</span>${escapeHtml(alternative.name)}</th>${criteria.map(criterion => `<td>${escapeHtml((alternative.values || {})[criterion] || '未提供')}</td>`).join('')}</tr>`).join('');
  return `<table class="table-body competition-matrix"><thead><tr><th scope="col">层级 / 选项</th>${headers}</tr></thead><tbody>${rows}</tbody></table>`;
}

function exhibitShell(block, exhibit, structure, body, tag = 'div') {
  const id = `${block.id}-exhibit`;
  return `<${tag} id="${escapeHtml(id)}" class="native-exhibit native-exhibit--${escapeHtml(exhibit.kind)}" data-exhibit-kind="${escapeHtml(exhibit.kind)}" data-exhibit-family="${escapeHtml(exhibit.family)}" data-exhibit-form="${escapeHtml(exhibit.form)}" data-structure="${escapeHtml(structure)}" aria-label="${escapeHtml(exhibit.kind)}">${body}</${tag}>`;
}

function itemList(values, className) {
  return `<ol class="${className}">${list(values).map(value => `<li>${escapeHtml(typeof value === 'string' ? value : value.label)}</li>`).join('')}</ol>`;
}

function answerExhibit(block, exhibit) {
  if (exhibit.kind === 'executive-summary') {
    const reasons = list(exhibit.reasons).map(reason => `<div><dt>关键理由</dt><dd>${escapeHtml(reason)}</dd></div>`).join('');
    return exhibitShell(block, exhibit, 'executive-answer-dl', `<p class="exhibit-answer">${escapeHtml(exhibit.answer)}</p><dl>${reasons}</dl>`, 'section');
  }
  return exhibitShell(block, exhibit, 'answer-reasons-list', `<h4>${escapeHtml(exhibit.answer)}</h4>${itemList(exhibit.reasons, 'exhibit-reasons')}`, 'section');
}

function matrixExhibit(block, exhibit) {
  const columns = list(exhibit.columns);
  const head = columns.map(column => `<th scope="col">${escapeHtml(column)}</th>`).join('');
  const rows = list(exhibit.rows).map(row => `<tr><th scope="row">${escapeHtml(row.label)}</th>${columns.map((_, index) => `<td>${escapeHtml(list(row.values)[index])}</td>`).join('')}</tr>`).join('');
  if (exhibit.kind === 'pain-comparison') {
    const groups = list(exhibit.rows).map(row => `<section><h4>${escapeHtml(row.label)}</h4><dl>${columns.map((column, index) => `<div><dt>${escapeHtml(column)}</dt><dd>${escapeHtml(list(row.values)[index])}</dd></div>`).join('')}</dl></section>`).join('');
    return exhibitShell(block, exhibit, 'pain-before-after-dl', groups, 'div');
  }
  return exhibitShell(block, exhibit, 'competitor-criteria-table', `<table><thead><tr><th scope="col">比较项</th>${head}</tr></thead><tbody>${rows}</tbody></table>`, 'figure');
}

function decisionTreeExhibit(block, exhibit) {
  const nodes = list(exhibit.nodes);
  const ids = nodes.map(node => node.id);
  if (new Set(ids).size !== ids.length) throw reportError('REPORT_EXHIBIT_MISMATCH', `${block.id} has duplicate decision-tree node IDs`);
  const nodeIds = new Set(nodes.map(node => node.id));
  const invalid = list(exhibit.edges).find(edge => !nodeIds.has(edge.from) || !nodeIds.has(edge.to));
  if (invalid) throw reportError('REPORT_EXHIBIT_MISMATCH', `${block.id} edge ${invalid.from} -> ${invalid.to} does not resolve`);
  const incoming = new Map(ids.map(id => [id, 0]));
  const outgoing = new Map(ids.map(id => [id, []]));
  for (const edge of exhibit.edges) { incoming.set(edge.to, incoming.get(edge.to) + 1); outgoing.get(edge.from).push(edge.to); }
  const roots = ids.filter(id => incoming.get(id) === 0);
  if (roots.length !== 1) throw reportError('REPORT_EXHIBIT_MISMATCH', `${block.id} decision tree requires one root and no cycles`);
  if (ids.some(id => id !== roots[0] && incoming.get(id) !== 1)) throw reportError('REPORT_EXHIBIT_MISMATCH', `${block.id} decision tree non-root nodes require exactly one incoming edge`);
  const queue = [roots[0]];
  const depth = new Map([[roots[0], 0]]);
  const visited = [];
  while (queue.length) {
    const id = queue.shift(); visited.push(id);
    for (const next of outgoing.get(id)) { depth.set(next, Math.max(depth.get(next) || 0, depth.get(id) + 1)); incoming.set(next, incoming.get(next) - 1); if (incoming.get(next) === 0) queue.push(next); }
  }
  if (visited.length !== nodes.length) throw reportError('REPORT_EXHIBIT_MISMATCH', `${block.id} decision tree contains a cycle or unreachable node`);
  const lanes = new Map();
  const positions = new Map(nodes.map(node => { const level = depth.get(node.id); const lane = lanes.get(level) || 0; lanes.set(level, lane + 1); return [node.id, { x: 8 + level * 110, y: 12 + lane * 55 }]; }));
  const labels = nodes.map(node => { const point = positions.get(node.id); return `<g id="${escapeHtml(block.id)}-node-${escapeHtml(node.id)}"><rect x="${point.x}" y="${point.y}" width="90" height="30"></rect><text x="${point.x + 45}" y="${point.y + 19}">${escapeHtml(node.label)}</text></g>`; }).join('');
  const edges = list(exhibit.edges).map((edge, index) => { const from = positions.get(edge.from); const to = positions.get(edge.to); const x1 = from.x + 90; const x2 = to.x; const y1 = from.y + 15; const y2 = to.y + 15; return `<line id="${escapeHtml(block.id)}-edge-${index + 1}" data-from="${escapeHtml(block.id)}-node-${escapeHtml(edge.from)}" data-to="${escapeHtml(block.id)}-node-${escapeHtml(edge.to)}" x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}"></line><text x="${(x1 + x2) / 2}" y="${(y1 + y2) / 2 - 5}">${escapeHtml(edge.label)}</text>`; }).join('');
  const width = Math.max(...[...positions.values()].map(point => point.x + 98));
  const height = Math.max(...[...positions.values()].map(point => point.y + 42));
  return exhibitShell(block, exhibit, 'decision-branch-svg', `<svg role="img" aria-labelledby="${escapeHtml(block.id)}-tree-title" viewBox="0 0 ${width} ${height}"><title id="${escapeHtml(block.id)}-tree-title">决策树</title>${edges}${labels}</svg>`, 'figure');
}

function processExhibit(block, exhibit) {
  const steps = list(exhibit.steps);
  const groups = steps.map((step, index) => `<g id="${escapeHtml(block.id)}-step-${index + 1}"><rect x="${6 + index * 105}" y="8" width="90" height="30"></rect><text x="${51 + index * 105}" y="27">${escapeHtml(step.label)}</text></g>`).join('');
  const connectors = steps.slice(1).map((_, index) => `<line class="process-connector" x1="${96 + index * 105}" y1="23" x2="${111 + index * 105}" y2="23"></line>`).join('');
  return exhibitShell(block, exhibit, 'mechanism-flow-svg', `<svg role="img" aria-labelledby="${escapeHtml(block.id)}-process-title" viewBox="0 0 ${Math.max(210, steps.length * 105 + 6)} 46"><title id="${escapeHtml(block.id)}-process-title">机制与流程</title>${connectors}${groups}</svg>`, 'figure');
}

function scenariosExhibit(block, exhibit) {
  const scenarios = list(exhibit.scenarios).map((scenario, index) => `<section id="${escapeHtml(block.id)}-scenario-${index + 1}"><h4>${escapeHtml(scenario.label)}</h4><p>${escapeHtml(scenario.outcome)}</p></section>`).join('');
  return exhibitShell(block, exhibit, 'paired-scenario-sections', scenarios, 'div');
}

function roadmapExhibit(block, exhibit) {
  const stages = list(exhibit.stages).map((stage, index) => `<li id="${escapeHtml(block.id)}-stage-${index + 1}"><time>${escapeHtml(stage.label)}</time><span>${escapeHtml(stage.output)}</span></li>`).join('');
  return exhibitShell(block, exhibit, 'thirty-sixty-ninety-list', `<ol class="roadmap-stages">${stages}</ol>`, 'section');
}

function methodsExhibit(block, exhibit) {
  return exhibitShell(block, exhibit, 'methods-limitations-aside', `<section><h4>方法</h4>${itemList(exhibit.methods, 'methods-list')}</section><section><h4>限制</h4>${itemList(exhibit.limitations, 'limitations-list')}</section>`, 'aside');
}

const EXHIBIT_RENDERERS = Object.freeze({
  'executive-summary': answerExhibit,
  'answer-and-reasons': answerExhibit,
  'pain-comparison': matrixExhibit,
  'competitor-matrix': matrixExhibit,
  'decision-tree': decisionTreeExhibit,
  'mechanism-process': processExhibit,
  'paired-scenarios': scenariosExhibit,
  '30-60-90-roadmap': roadmapExhibit,
  'methods-limitations': methodsExhibit,
});

function semanticBody(block) {
  const content = block.content || {};
  const semanticType = content.semantic_type;
  const selectedLayout = SEMANTIC_LAYOUTS.get(semanticType);
  const expectedKind = selectedLayout && selectedLayout.kind;
  if (semanticType === 'point_evidence') return null;
  if (!Object.hasOwn(EXHIBIT_RENDERERS, expectedKind)) throw reportError('REPORT_EXHIBIT_MISSING', `${block.id} requires explicit point_evidence or a supported exhibit`);
  if (!content.exhibit) throw reportError('REPORT_EXHIBIT_MISSING', `${block.id} declares ${semanticType} without exhibit content`);
  if (content.exhibit.kind !== expectedKind) throw reportError('REPORT_EXHIBIT_MISMATCH', `${block.id} declares ${semanticType} but provides ${content.exhibit.kind}`);
  const layout = EXHIBIT_LAYOUTS.get(expectedKind);
  const missing = layout.required_fields.filter(field => !content.exhibit[field] || content.exhibit[field].length === 0);
  if (missing.length) throw reportError('REPORT_EXHIBIT_MISSING', `${block.id} missing ${missing.join(', ')}`);
  if (content.exhibit.family !== layout.family || !layout.forms.includes(content.exhibit.form) || content.form !== content.exhibit.form) {
    throw reportError('REPORT_EXHIBIT_MISMATCH', `${block.id} kind/family/form does not match catalog`);
  }
  const count = content.exhibit[layout.capacity.field].length;
  if (count > layout.capacity.hard) throw reportError('REPORT_EXHIBIT_MISMATCH', `${block.id} exceeds hard capacity`);
  const capacityState = count > layout.capacity.soft ? 'soft-exceeded' : 'within-soft';
  if (content.exhibit.capacity_state && content.exhibit.capacity_state !== capacityState) throw reportError('REPORT_EXHIBIT_MISMATCH', `${block.id} supplied capacity state is incorrect`);
  if (layout.family === 'matrix' && content.exhibit.rows.some(row => list(row.values).length !== content.exhibit.columns.length)) {
    throw reportError('REPORT_EXHIBIT_MISMATCH', `${block.id} matrix row width does not match columns`);
  }
  return EXHIBIT_RENDERERS[expectedKind](block, content.exhibit);
}

const BLOCK_RENDERERS = Object.freeze({ chart: chartBody, text: textBody, metric: metricBody, table: tableBody });

function present(value) {
  return typeof value === 'string' ? value.trim().length > 0 : value !== undefined && value !== null;
}

const COMPONENT_PREDICATES = Object.freeze({
  single_title_group(payload) {
    return present(payload.title) && Array.isArray(payload.title_groups) && payload.title_groups.length === 1 && present(payload.title_groups[0] && payload.title_groups[0].title);
  },
  entry_destination(payload) {
    return Array.isArray(payload.entries) && payload.entries.length > 0 && payload.entries.every(entry => entry && present(entry.destination));
  },
  unit_period(payload) {
    return present(payload.unit) && present(payload.period);
  },
  single_answer(payload) {
    return Array.isArray(payload.answers) && payload.answers.length === 1 && present(payload.answers[0]);
  },
  qualified_summary_item(payload) {
    return Array.isArray(payload.summary_items) && payload.summary_items.length > 0 && payload.summary_items.every(item => item && present(item.text) && present(item.qualification));
  },
  complete_decision_summary(payload) {
    return present(payload.decision_level) && Array.isArray(payload.decisive_reasons) && payload.decisive_reasons.length === 3 && payload.decisive_reasons.every(present) &&
      present(payload.largest_upside) && present(payload.largest_risk) && Array.isArray(payload.immediate_actions) && payload.immediate_actions.length > 0 && payload.immediate_actions.every(present) &&
      payload.thresholds && present(payload.thresholds.continue) && present(payload.thresholds.stop);
  },
  single_chapter_claim(payload) {
    return present(payload.title) && Array.isArray(payload.chapter_claims) && payload.chapter_claims.length === 1 && present(payload.chapter_claims[0]);
  },
  native_exhibit_block(payload) {
    return Array.isArray(payload.blocks) && payload.blocks.length === 1 && Array.isArray(payload.exhibits) && payload.exhibits.length === 1 &&
      payload.blocks.every(block => block && block.content && block.content.semantic_type !== 'point_evidence' && block.content.exhibit) &&
      payload.blocks[0].content.exhibit.kind === payload.exhibits[0].kind;
  },
  evidence_source_locator(payload) {
    return present(payload.claim) && Array.isArray(payload.evidence_groups) && payload.evidence_groups.length > 0 && payload.evidence_groups.every(group =>
      group && present(group.source_id) && Array.isArray(group.locators) && group.locators.length > 0 && group.locators.every(present)
    );
  },
  shared_criteria(payload) {
    if (!Array.isArray(payload.criteria) || payload.criteria.length === 0 || !Array.isArray(payload.alternatives) || payload.alternatives.length === 0) return false;
    return payload.criteria.every(present) && payload.alternatives.every(alternative => {
      const values = alternative && alternative.values;
      return values && payload.criteria.every(criterion => Object.hasOwn(values, criterion));
    });
  },
  observable_behavior(payload) {
    return Array.isArray(payload.pain_groups) && payload.pain_groups.length > 0 && payload.pain_groups.every(group =>
      group && ((present(group.pain) && present(group.observable_behavior)) ||
        (present(group.segment) && present(group.trigger) && present(group.purchase_signal) && present(group.validation_gap)))
    );
  },
  series_or_driver_nonempty(payload) {
    return Array.isArray(payload.series_or_drivers) && payload.series_or_drivers.length > 0 && payload.series_or_drivers.every(item => item && present(item.name));
  },
  risk_priority(payload) {
    return Array.isArray(payload.risks) && payload.risks.length > 0 && payload.risks.every(risk => risk && present(risk.name) && present(risk.priority));
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
  const semantic = semanticBody(block);
  return `<article class="report-block report-block--${escapeHtml(block.kind)}" data-block-id="${escapeHtml(block.id)}" data-block-kind="${escapeHtml(block.kind)}" data-form="${escapeHtml(content.form)}" data-role="${escapeHtml(content.role)}" data-semantic-type="${escapeHtml(content.semantic_type)}" data-exhibit-required="${content.semantic_type === 'point_evidence' ? 'false' : 'true'}" aria-labelledby="${escapeHtml(block.id)}-title"${anchor}>${blockHeader(block)}${semantic === null ? BLOCK_RENDERERS[block.kind](block) : semantic}${citationMarkers(block, context)}${bindings(block, context)}</article>`;
}

function executiveSummaryBody(payload) {
  const answer = `<p class="executive-answer">${escapeHtml(payload.answers[0])}</p>`;
  const items = list(payload.summary_items).map(item =>
    `<li class="summary-item"><strong>${escapeHtml(item.text)}</strong>` +
    `<span class="summary-meta">${escapeHtml(item.identity || 'claim')} · ${escapeHtml(item.confidence || 'unspecified')}</span>` +
    `<p>${escapeHtml(item.qualification)}</p></li>`
  ).join('');
  const reasons = list(payload.decisive_reasons).map(reason => `<li>${escapeHtml(reason)}</li>`).join('');
  const actions = list(payload.immediate_actions).map(action => `<li>${escapeHtml(action)}</li>`).join('');
  return `${answer}<div class="executive-decision" data-decision-level="${escapeHtml(payload.decision_level)}"><strong>${escapeHtml(payload.decision_level)}</strong><ul class="decisive-reasons">${reasons}</ul><dl><div><dt>Largest upside</dt><dd>${escapeHtml(payload.largest_upside)}</dd></div><div><dt>Largest risk</dt><dd>${escapeHtml(payload.largest_risk)}</dd></div><div><dt>Continue threshold</dt><dd>${escapeHtml(payload.thresholds.continue)}</dd></div><div><dt>Stop threshold</dt><dd>${escapeHtml(payload.thresholds.stop)}</dd></div></dl><h3>Immediate actions</h3><ul>${actions}</ul></div><ol class="summary-list">${items}</ol>`;
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
  const componentBody = kind === 'executive-summary' ? executiveSummaryBody(payload) : blocks;
  return `<${tag} class="report-component report-component--${escapeHtml(kind)}" data-component-kind="${escapeHtml(kind)}" data-component-id="${escapeHtml(id)}" data-layout-id="${escapeHtml(layoutId)}" data-capacity-count="${capacityCount}" data-capacity-soft="${contract.capacity_dimensions.soft}" data-capacity-hard="${contract.capacity_dimensions.hard}" data-capacity-unit="${escapeHtml(contract.capacity_dimensions.unit)}" data-split-strategy="${escapeHtml(contract.split_strategy)}" aria-labelledby="${escapeHtml(id)}-title"${landmarkLabel}><${headingTag} id="${escapeHtml(id)}-title">${escapeHtml(title)}</${headingTag}>${componentBody}</${tag}>`;
}

module.exports = {
  APPROVED_BLOCK_KINDS,
  APPROVED_COMPONENT_KINDS,
  COMPONENT_CONTRACTS,
  renderBlock,
  renderComponent,
};
