'use strict';

const { COMPONENT_CONTRACTS } = require('./components.cjs');

const PAGE = Object.freeze({ widthMm: 210, heightMm: 297, contentWidthMm: 173, contentHeightMm: 261 });

function reportError(code, detail) {
  const error = new Error(`${code}: ${detail}`);
  error.code = code;
  return error;
}

function chunks(values, size) {
  const result = [];
  for (let index = 0; index < values.length; index += size) result.push({ values: values.slice(index, index + size), start: index + 1 });
  return result;
}

function expandComponents(components) {
  const fragments = [];
  for (const component of components || []) {
    const contract = COMPONENT_CONTRACTS[component && component.kind];
    if (!contract) throw reportError('REPORT_UNSUPPORTED_COMPONENT', `unsupported component kind: ${component && component.kind}`);
    const payload = component.payload || {};
    const field = contract.capacity_dimensions.field;
    const values = Array.isArray(payload[field]) ? payload[field] : [];
    const mustSplit = values.length > contract.capacity_dimensions.hard;
    const splittable = new Set(['toc', 'references-appendix']);
    if (mustSplit && !splittable.has(component.kind)) {
      throw reportError('REPORT_COMPONENT_CAPACITY', `${component.kind} cannot split ${values.length} ${contract.capacity_dimensions.unit}`);
    }
    const parts = mustSplit ? chunks(values, contract.capacity_dimensions.hard) : [{ values, start: 1 }];
    for (let index = 0; index < parts.length; index += 1) {
      const part = parts[index];
      const copy = { ...payload, [field]: part.values };
      delete copy.capacity_count;
      copy.id = index ? `${payload.id}--continued-${index + 1}` : payload.id;
      copy.title = index ? `${payload.title}（续）` : payload.title;
      if (index && Array.isArray(payload.blocks)) {
        copy.blocks = payload.blocks.map(block => ({ ...block, id: `${block.id}--continued-${index + 1}` }));
      }
      fragments.push({
        kind: component.kind,
        originalId: payload.id,
        payload: copy,
        continuation: index > 0,
        table: component.kind === 'references-appendix',
        startRow: part.start,
        endRow: part.start + part.values.length - 1,
        rowCount: part.values.length,
        originalBlockIds: (payload.blocks || []).map(block => block.id),
        sourceBlocks: payload.blocks || [],
      });
    }
  }
  return fragments;
}

function newPage(number, intentionalBlank = false) {
  return { number, id: `page-${String(number).padStart(3, '0')}`, intentionalBlank, items: [], usedHeightPx: 0 };
}

function paginateMeasured(fragments, contentHeightPx) {
  const pages = [];
  let page = newPage(1);
  const flush = () => {
    if (page.items.length || page.intentionalBlank) pages.push(page);
    page = newPage(pages.length + 1);
  };
  for (const fragment of fragments) {
    if (fragment.kind === 'section-title') {
      if (page.items.length) flush();
      if (page.number % 2 === 0) {
        page.intentionalBlank = true;
        flush();
      }
    }
    if (fragment.heightPx > contentHeightPx + 1) {
      throw reportError('REPORT_PAGE_OVERFLOW', `${fragment.originalId} is ${fragment.heightPx}px, page content is ${contentHeightPx}px`);
    }
    const forceOwnPage = fragment.table;
    if (page.items.length && (forceOwnPage || page.usedHeightPx + fragment.heightPx > contentHeightPx + 1)) flush();
    page.items.push(fragment);
    page.usedHeightPx += fragment.heightPx;
    if (forceOwnPage) flush();
  }
  if (page.items.length || page.intentionalBlank) flush();
  return pages;
}

function resolveNavigation(pages) {
  const blockToPage = {};
  const anchorToPage = {};
  const componentToPage = {};
  for (const page of pages) {
    for (const item of page.items) {
      componentToPage[item.originalId] ??= page.number;
      for (const blockId of item.blockIds || []) blockToPage[blockId] ??= page.number;
      for (const blockId of item.originalBlockIds || []) blockToPage[blockId] ??= page.number;
      for (const anchorId of item.anchorIds || []) anchorToPage[anchorId] ??= page.number;
      for (const anchorId of item.originalAnchorIds || []) anchorToPage[anchorId] ??= page.number;
    }
  }
  return { blockToPage, anchorToPage, componentToPage };
}

module.exports = { PAGE, reportError, expandComponents, paginateMeasured, resolveNavigation };
