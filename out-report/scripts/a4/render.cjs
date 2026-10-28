#!/usr/bin/env node
'use strict';

const fs = require('fs');
const path = require('path');
const cp = require('child_process');
const crypto = require('crypto');
const { escapeHtml } = require('./escape.cjs');
const { renderComponent } = require('./components.cjs');
const { PAGE, reportError, expandComponents, paginateMeasured, resolveNavigation } = require('./paginate.cjs');

const CSS = `
@page{size:210mm 297mm;margin:0}*{box-sizing:border-box}html,body{margin:0;color:#262d31;font-family:NotoSansSC,Arial,sans-serif;font-size:10.75pt;line-height:1.58}.page{width:210mm;height:297mm;padding:18mm 17mm 18mm 20mm;background:#f7f5ef;position:relative;break-after:page;overflow:hidden}.page__body{width:173mm;height:261mm;overflow:visible}.report-component{display:block;margin:0 0 6mm;border-top:.7pt solid #bdc5c3;padding-top:3mm}.report-component>h1{font:600 26pt/1.22 NotoSerifSC,serif;margin:0 0 7mm}.report-component>h2{font:600 20pt/1.35 NotoSerifSC,serif;margin:0 0 5mm}.report-block{display:block;margin:0 0 4mm}.report-block header{display:block}.report-block h3{font-size:12pt;line-height:1.45;margin:0 0 2mm}.report-block p{margin:0 0 2mm}.block-subtitle,.block-reason{color:#667176}.citation-markers{margin-left:1mm}.citation-marker{color:#0b6b66;text-decoration:none;margin-right:.5mm}.identity-key{display:inline-block;margin-right:2mm;font-size:8.5pt}.table-body,.source-table{width:100%;border-collapse:collapse;font-size:8.5pt;line-height:1.4}.table-body th,.table-body td,.source-table th,.source-table td{border-bottom:.35pt solid #bdc5c3;padding:1.6mm;text-align:left;vertical-align:top}.source-table .source-locator{font-size:7.5pt}.block-figure{margin:0}.block-figure svg{width:100%;height:38mm;stroke:#0b6b66;fill:#d8e7e3}.folio{position:absolute;right:17mm;bottom:3mm;font-size:7.5pt}.intentional-blank{display:grid;place-items:center;color:#667176;font-size:8.5pt}.toc-list{margin:0;padding-left:0;list-style:none}.toc-list a{color:inherit}.toc-page{float:right;min-width:3ch;text-align:right}.page-item,.measure-item{display:flow-root;width:173mm}.measure-root{width:173mm}`;

const SEMANTIC_CSS = `
.page{height:297mm;break-after:page;page-break-after:always;break-inside:avoid;page-break-inside:avoid}.page__body{height:259mm}.report-component>h1,.report-component>h2{padding-top:1.5mm}.report-block{margin-bottom:3mm}.executive-answer{font:600 16pt/1.45 NotoSerifSC,serif;border-left:1.2mm solid #0b6b66;padding-left:4mm}.summary-list{display:grid;grid-template-columns:1fr 1fr;gap:4mm;padding:0;list-style:none}.summary-item{background:#fff;border-top:1mm solid #0b6b66;padding:3mm}.summary-item strong,.summary-meta{display:block}.summary-meta{color:#667176;font-size:8.5pt;margin:1mm 0}.claim-detail{border-left:1.2mm solid #0b6b66;padding:2.5mm 0 2.5mm 4mm;margin:0 0 3mm}.claim-statement{font:600 12pt/1.45 NotoSerifSC,serif}.claim-meta{display:grid;grid-template-columns:1fr 2fr;gap:2mm;margin:0 0 2mm}.claim-meta div{display:grid;grid-template-columns:25mm 1fr}.claim-meta dt,.pain-group dt{color:#667176}.claim-meta dd,.pain-group dd{margin:0}.claim-evidence-pair{display:grid;grid-template-columns:1fr 1fr;gap:4mm}.claim-evidence-pair h4{margin:0;font-size:9pt}.claim-evidence-pair ul{margin:1mm 0 2mm;padding-left:5mm}.evidence-locator,.evidence-more,.evidence-empty{color:#667176;font-size:8.5pt}.claim-limitation{background:#e8ece8;padding:2mm}.pain-groups{display:grid;grid-template-columns:1fr 1fr;gap:4mm}.pain-group{border-top:1mm solid #0b6b66;background:#fff;padding:3mm}.pain-group h4{font:600 11pt/1.4 NotoSerifSC,serif;margin:0 0 2mm}.pain-group dl{margin:0}.pain-group dl div{display:grid;grid-template-columns:20mm 1fr;border-top:.35pt solid #d6dbd8;padding:1.2mm 0}.pain-group dd{line-height:1.4}.competition-matrix{table-layout:fixed}.competition-matrix th:first-child{width:33mm}.competition-matrix th,.competition-matrix td{padding:1.2mm;overflow-wrap:anywhere}.competition-layer{display:block;color:#0b6b66;font-size:8.5pt;text-transform:uppercase}.native-exhibit{margin:0;background:#fff;border-top:1mm solid #0b6b66;padding:3mm}.native-exhibit table{width:100%;border-collapse:collapse}.native-exhibit th,.native-exhibit td{border-bottom:.35pt solid #bdc5c3;padding:1.6mm;text-align:left}.native-exhibit svg{display:block;width:100%;height:42mm}.native-exhibit rect{fill:#d8e7e3;stroke:#0b6b66}.native-exhibit text{fill:#262d31;font:4px NotoSansSC,Arial,sans-serif;text-anchor:middle}.native-exhibit--paired-scenarios{display:grid;grid-template-columns:1fr 1fr;gap:4mm}.roadmap-stages{display:grid;grid-template-columns:repeat(3,1fr);gap:4mm;padding:0;list-style:none}.roadmap-stages time,.roadmap-stages span{display:block}.exhibit-answer{font:600 15pt/1.4 NotoSerifSC,serif}`;

const CONNECTOR_CSS = `.native-exhibit line{stroke:#0b6b66;stroke-width:1.2}.native-exhibit text{font-size:8.5pt}`;

const FONTS = Object.freeze([
  { family: 'NotoSansSC', weight: 400, file: 'noto-sans-sc-400.woff2', hash: '758dff09a5625dd659ea4c529ffdb7741bdbc182b54957a7007f1cfcfd450820' },
  { family: 'NotoSansSC', weight: 600, file: 'noto-sans-sc-600.woff2', hash: '722d2f69f1b0f494148dd6a492f7efcfcc9ba9b6c0a203b39987feea076a6064' },
  { family: 'NotoSerifSC', weight: 600, file: 'noto-serif-sc-600.woff2', hash: 'f6e3c090225ed5372d7ca7175e4148b8f4fb676be73f932891f64a91512c7a5a' },
]);

function runtimeRoot() {
  const repoRoot = path.resolve(__dirname, '../../..');
  const skillDir = path.join(repoRoot, 'out-report');
  const program = 'from tools.lib import runtime; import sys; print(runtime.runtime_root(skill_dir=sys.argv[1]))';
  try {
    return cp.execFileSync(process.env.PYTHON || 'python3', ['-c', program, skillDir], { cwd: repoRoot, env: process.env, encoding: 'utf8' }).trim();
  } catch (error) {
    throw reportError('REPORT_RUNTIME_MISSING', `tools.lib.runtime could not resolve runtime: ${error.stderr || error.message}`);
  }
}

function lockedRuntime() {
  const runtime = runtimeRoot();
  const modulePath = path.join(runtime, 'vendor/report-forge/node_modules/playwright');
  if (!fs.existsSync(modulePath)) throw reportError('REPORT_RUNTIME_MISSING', `locked Playwright not found: ${modulePath}`);
  const fontDir = path.join(runtime, 'vendor/report-forge/assets/fonts');
  const fontCss = FONTS.map(font => {
    const file = path.join(fontDir, font.file);
    if (!fs.existsSync(file)) throw reportError('REPORT_RUNTIME_MISSING', `locked font not found: ${file}`);
    const bytes = fs.readFileSync(file);
    const digest = crypto.createHash('sha256').update(bytes).digest('hex');
    if (digest !== font.hash) throw reportError('REPORT_FONT_MISMATCH', `${font.file} hash ${digest}`);
    return `@font-face{font-family:${font.family};src:url("data:font/woff2;base64,${bytes.toString('base64')}") format("woff2");font-weight:${font.weight};font-style:normal}`;
  }).join('');
  return { chromium: require(modulePath).chromium, fontCss };
}

function sourceTable(fragment, context) {
  if (!fragment.table) return '';
  const citations = new Map(context.citationRegistry.map(item => [item.source_id, item]));
  const rows = fragment.payload.references.map(reference => {
    const citation = citations.get(reference.id);
    const locators = (reference.locators || []).map(value => `<span data-source-locator="${escapeHtml(value)}">${escapeHtml(value)}</span>`).join('、');
    const byline = [reference.author, reference.publisher, reference.published || reference.accessed].filter(Boolean).map(escapeHtml).join(' · ');
    const audit = [reference.grade && `Grade ${reference.grade}`, reference.conflict_of_interest].filter(Boolean).map(escapeHtml).join(' · ');
    const safeHref = typeof reference.url === 'string' && /^https?:\/\//i.test(reference.url);
    const url = reference.url ? (safeHref ? `<a href="${escapeHtml(reference.url)}">${escapeHtml(reference.url)}</a>` : escapeHtml(reference.url)) : '';
    return `<tr id="${escapeHtml(citation.appendix_anchor)}" data-source-record="${escapeHtml(reference.id || '')}"><th scope="row">[${escapeHtml(citation.number)}]</th><td>${escapeHtml(reference.title || '')}${byline ? `<br>${byline}` : ''}${url ? `<br>${url}` : ''}<br><span class="source-locator">${locators}</span>${audit ? `<br>${audit}` : ''}</td></tr>`;
  }).join('');
  const continuation = fragment.continuation ? '<caption data-table-continuation="true">来源（续）</caption>' : '';
  return `<table class="source-table"><colgroup><col style="width:12mm"><col></colgroup>${continuation}<thead><tr><th scope="col">编号</th><th scope="col">完整来源与定位</th></tr></thead><tbody>${rows}</tbody></table>`;
}

function tocList(fragment) {
  if (fragment.kind !== 'toc') return '';
  const entries = fragment.payload.entries.map(entry => `<li><a href="#${escapeHtml(entry.destination)}-title">${escapeHtml(entry.title || entry.destination)} <span class="toc-page">{{PAGE:${escapeHtml(entry.destination)}}}</span></a></li>`).join('');
  return `<ol class="toc-list">${entries}</ol>`;
}

function fragmentHtml(fragment, context) {
  const renderContext = fragment.kind === 'references-appendix' ? { ...context, renderCitations: false } : context;
  const base = renderComponent(fragment.kind, fragment.payload, renderContext);
  return base.replace(/<\/(section|nav|aside)>$/, `${tocList(fragment)}${sourceTable(fragment, context)}</$1>`);
}

function citationContext(document) {
  const hasAppendix = document.components.some(item => item.kind === 'references-appendix');
  if (!document.citation_registry && !hasAppendix && document.citation_mode !== 'evidence_package') return { citationRegistry: [] };
  const bodyIds = [];
  const seen = new Set();
  for (const component of document.components) {
    if (component.kind === 'references-appendix') continue;
    for (const block of (component.payload.blocks || [])) {
      const declared = new Set(block.source_ids || []);
      const bound = new Set((block.source_bindings || []).map(binding => binding.source_id));
      const mismatch = [...declared].some(sourceId => !bound.has(sourceId)) || [...bound].some(sourceId => !declared.has(sourceId));
      if (mismatch) {
        throw reportError('REPORT_CITATION_MISMATCH', `block ${block.id || '<unknown>'} source_ids and source_bindings differ`);
      }
      for (const sourceId of (block.source_ids || [])) {
        if (!seen.has(sourceId)) {
          seen.add(sourceId);
          bodyIds.push(sourceId);
        }
      }
    }
  }
  const references = document.components.filter(item => item.kind === 'references-appendix')
    .flatMap(item => item.payload.references || []);
  const referenceIds = references.map(item => item.id);
  const counts = new Map();
  for (const sourceId of referenceIds) counts.set(sourceId, (counts.get(sourceId) || 0) + 1);
  if (hasAppendix && (bodyIds.some(sourceId => counts.get(sourceId) !== 1) || referenceIds.some(sourceId => counts.get(sourceId) !== 1))) {
    throw reportError('REPORT_CITATION_MISMATCH', 'body sources and appendix targets must match, with one target per source');
  }
  const ordered = hasAppendix ? [...bodyIds, ...[...new Set(referenceIds.filter(sourceId => !seen.has(sourceId)))].sort()] : bodyIds;
  const generated = ordered.map((source_id, index) => ({ source_id, number: index + 1, appendix_anchor: `source-${source_id}` }));
  if (document.citation_registry) {
    const supplied = document.citation_registry;
    const matches = supplied.length === generated.length && supplied.every((item, index) =>
      item.source_id === generated[index].source_id && item.number === generated[index].number &&
      item.appendix_anchor === generated[index].appendix_anchor
    );
    if (!matches) throw reportError('REPORT_CITATION_MISMATCH', 'citation registry does not match body and appendix order');
  }
  return { citationRegistry: generated };
}

function blockMetadata(fragment) {
  fragment.blockIds = (fragment.payload.blocks || []).map(block => block.id);
  fragment.anchorIds = (fragment.payload.blocks || []).filter(block => block.content && block.content.anchor).map(block => block.id);
  fragment.originalAnchorIds = (fragment.originalBlockIds || []).filter((_, index) => {
    const block = (fragment.payload.blocks || [])[index];
    return block && block.content && block.content.anchor;
  });
  return fragment;
}

async function measure(fragments, css, chromium) {
  const browser = await chromium.launch({ headless: true });
  try {
    const page = await browser.newPage({ viewport: { width: 1191, height: 1684 }, deviceScaleFactor: 1 });
    const body = fragments.map((fragment, index) => `<div class="measure-item" data-index="${index}">${fragment.html}</div>`).join('');
    await page.setContent(`<!doctype html><html><head><meta charset="utf-8"><style>${css}</style></head><body><main class="measure-root">${body}</main></body></html>`, { waitUntil: 'load' });
    const result = await page.evaluate(async () => {
      await document.fonts.ready;
      await Promise.all([
        document.fonts.load('400 12px NotoSansSC', '报告'),
        document.fonts.load('600 12px NotoSansSC', '报告'),
        document.fonts.load('600 12px NotoSerifSC', '报告'),
      ]);
      const pxPerMm = 96 / 25.4;
      const items = [...document.querySelectorAll('.measure-item')].map(element => ({
        heightPx: Math.ceil(element.getBoundingClientRect().height * 1000) / 1000,
        minimumFontPt: Math.min(...[...element.querySelectorAll('*')].filter(node => getComputedStyle(node).display !== 'none').map(node => parseFloat(getComputedStyle(node).fontSize) * .75)),
      }));
      const loadedFonts = [...document.fonts].filter(face => face.status === 'loaded').map(face => `${face.family.replaceAll('"', '')}:${face.weight}`).filter(value => value.startsWith('Noto')).sort();
      return { items, contentHeightPx: Math.round(259 * pxPerMm * 1000) / 1000, loadedFonts };
    });
    const expected = FONTS.map(font => `${font.family}:${font.weight}`).sort();
    if (JSON.stringify(result.loadedFonts) !== JSON.stringify(expected)) throw reportError('REPORT_FONT_FALLBACK', `locked fonts not loaded: ${result.loadedFonts.join(',')}`);
    return result;
  } finally {
    await browser.close();
  }
}

function renderPages(pages, navigation, title, css, citationContext, citationMode) {
  const compactAnchors = citationMode === 'evidence_package' ? citationContext.citationRegistry.map(citation =>
    `<span hidden class="compact-source-anchor" id="${escapeHtml(citation.appendix_anchor)}" data-source-record="${escapeHtml(citation.source_id)}"></span>`).join('') : '';
  let html = `<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><title>${escapeHtml(title || 'Report')}</title><style>${css}</style></head><body>${pages.map((page, index) => {
    if (page.intentionalBlank) return `<section class="page intentional-blank" data-page-id="${page.id}" aria-label="Intentionally blank page"><span>本页有意留白</span><span class="folio">${page.number}</span></section>`;
    const content = page.items.map(item => `<div class="page-item">${item.html}</div>`).join('');
    return `<section class="page" data-page-id="${page.id}">${index === 0 ? compactAnchors : ''}<div class="page__body">${content}</div><span class="folio">${page.number}</span></section>`;
  }).join('')}</body></html>`;
  html = html.replace(/\{\{PAGE:([^}]+)\}\}/g, (_, id) => {
    const number = navigation.anchorToPage[id] || navigation.componentToPage[id];
    if (!number) throw reportError('REPORT_NAVIGATION_TARGET', `unknown navigation destination: ${id}`);
    return `<span data-cross-reference="${escapeHtml(id)}">${number}</span>`;
  });
  return html;
}

function pageRole(items) {
  const kinds = [...new Set(items.map(item => item.kind))];
  if (kinds.includes('cover') && kinds.every(kind => ['cover', 'toc'].includes(kind))) return kinds.includes('toc') ? 'cover-toc' : 'cover';
  if (kinds.length === 1 && kinds[0] === 'toc') return 'toc';
  if (kinds.length === 1 && kinds[0] === 'section-title') return 'section-divider';
  if (kinds.length === 1 && kinds[0] === 'references-appendix') return 'references';
  return 'body';
}

function whitespaceJustification(role) {
  return ({ cover: 'cover-identity', 'cover-toc': 'cover-identity', toc: 'toc-navigation', 'section-divider': 'section-transition' })[role];
}

async function renderDocument(document) {
  if (!document || !Array.isArray(document.components)) throw reportError('REPORT_DOCUMENT_INVALID', 'components must be an array');
  const componentIds = document.components.map(component => component && component.payload && component.payload.id);
  const blockIds = document.components.flatMap(component => ((component && component.payload && component.payload.blocks) || []).map(block => block.id));
  for (const [label, ids] of [['component', componentIds], ['block', blockIds]]) {
    const seen = new Set();
    for (const id of ids) {
      if (!id || seen.has(id)) throw reportError('REPORT_DUPLICATE_ID', `${label} id is missing or duplicated: ${id}`);
      seen.add(id);
    }
  }
  for (const [label, titles] of [
    ['section', document.components.filter(component => component && component.kind === 'section-title').map(component => component.payload && component.payload.title)],
  ]) {
    const seen = new Set();
    for (const title of titles.map(value => String(value || '').trim()).filter(Boolean)) {
      const key = title.normalize('NFKC').toLocaleLowerCase();
      if (seen.has(key)) throw reportError('REPORT_DUPLICATE_TITLE', `${label} title is duplicated: ${title}`);
      seen.add(key);
    }
  }
  {
    const seen = new Set();
    for (const title of document.components.flatMap(component => ((component && component.payload && component.payload.blocks) || [])
      .map(block => String(block && block.content && block.content.title || '').trim())).filter(Boolean)) {
      const key = title.normalize('NFKC').toLocaleLowerCase();
      if (seen.has(key)) throw reportError('REPORT_DUPLICATE_TITLE', `block title is duplicated: ${title}`);
      seen.add(key);
    }
  }
  let seenStructures = new Map();
  for (let index = 0; index < document.components.length; index += 1) {
    const currentComponent = document.components[index];
    const current = currentComponent.payload || {};
    const currentStructure = `${currentComponent.kind}:${current.layout_id || ''}`;
    if (currentComponent.kind === 'section-title') seenStructures = new Map();
    if (seenStructures.has(currentStructure) && !(current.repeat_approved === true && String(current.repeat_reason || '').trim().length >= 24)) {
      throw reportError('REPORT_REPEATED_PRIMARY_STRUCTURE', `${current.id || index} repeats ${currentStructure} without a specific reason`);
    }
    seenStructures.set(currentStructure, current.id || index);
  }
  const context = citationContext(document);
  const runtime = lockedRuntime();
  const css = `${runtime.fontCss}${CSS}${SEMANTIC_CSS}${CONNECTOR_CSS}`;
  let fragments = expandComponents(document.components).map(blockMetadata).map(fragment => ({ ...fragment, html: fragmentHtml(fragment, context) }));
  let measured;
  for (;;) {
    measured = await measure(fragments, css, runtime.chromium);
    measured.items.forEach((item, index) => Object.assign(fragments[index], item));
    const overflowing = fragments.findIndex(fragment => fragment.table && fragment.heightPx > measured.contentHeightPx + 1 && fragment.rowCount > 1);
    if (overflowing < 0) break;
    const fragment = fragments[overflowing];
    const midpoint = Math.ceil(fragment.rowCount / 2);
    const makePart = (records, startRow) => {
      const continued = startRow > 1;
      const suffix = continued ? `--continued-${startRow}` : '';
      const payload = {
        ...fragment.payload,
        id: `${fragment.originalId}${suffix}`,
        title: continued ? `${String(fragment.payload.title).replace(/（续）$/, '')}（续）` : String(fragment.payload.title).replace(/（续）$/, ''),
        references: records,
        blocks: fragment.sourceBlocks.map(block => ({ ...block, id: `${block.id}${suffix}` })),
      };
      const part = blockMetadata({ ...fragment, payload, continuation: continued, startRow, endRow: startRow + records.length - 1, rowCount: records.length });
      return { ...part, html: fragmentHtml(part, context) };
    };
    const records = fragment.payload.references;
    fragments.splice(overflowing, 1,
      makePart(records.slice(0, midpoint), fragment.startRow),
      makePart(records.slice(midpoint), fragment.startRow + midpoint));
  }
  const pages = paginateMeasured(fragments, measured.contentHeightPx);
  const navigation = resolveNavigation(pages);
  const html = renderPages(pages, navigation, document.title, css, context, document.citation_mode);
  const tableContinuations = pages.flatMap(page => page.items.filter(item => item.table).map(item => ({
    componentId: item.originalId, page: page.number, startRow: item.startRow, endRow: item.endRow, rowCount: item.rowCount,
  })));
  const minimumFontPt = measured.items.length ? Math.min(...measured.items.map(item => item.minimumFontPt)) : 10.75;
  const manifestPages = pages.map(page => {
    const role = pageRole(page.items);
    const justification = whitespaceJustification(role);
    return {
      id: page.id, number: page.number, intentionalBlank: page.intentionalBlank, role,
      ...(justification ? { whitespaceJustification: justification } : {}),
      usedHeightPx: Math.round(page.usedHeightPx * 1000) / 1000,
      contentHeightPx: measured.contentHeightPx,
      geometry: PAGE,
    };
  });
  const pagesWithTable = pages.filter(page => page.items.some(item => item.table)).map(page => ({
    page: page.number, tableHeaderCount: page.items.filter(item => item.table).length,
  }));
  return { html, manifest: { pageCount: pages.length, blockToPage: navigation.blockToPage, anchorToPage: navigation.anchorToPage, tableContinuations, pages: manifestPages, pagesWithTable, minimumFontPt: Math.round(minimumFontPt * 1000) / 1000, loadedFonts: measured.loadedFonts } };
}

async function main() {
  const inputPath = process.argv[2];
  const outputDir = process.argv[3];
  const input = fs.readFileSync(inputPath || 0, 'utf8');
  const result = await renderDocument(JSON.parse(input));
  if (outputDir) {
    fs.mkdirSync(outputDir, { recursive: true });
    fs.writeFileSync(path.join(outputDir, 'report.html'), result.html);
    fs.writeFileSync(path.join(outputDir, 'pagination-manifest.json'), `${JSON.stringify(result.manifest, null, 2)}\n`);
  }
  process.stdout.write(`${JSON.stringify(result)}\n`);
}

if (require.main === module) main().catch(error => { process.stderr.write(`${error.code || 'REPORT_RENDER_FAILED'}: ${error.message}\n`); process.exit(1); });

module.exports = { CSS, renderDocument };
