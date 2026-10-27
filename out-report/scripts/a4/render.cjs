#!/usr/bin/env node
'use strict';

const fs = require('fs');
const path = require('path');
const { escapeHtml } = require('./escape.cjs');
const { renderComponent } = require('./components.cjs');
const { PAGE, reportError, expandComponents, paginateMeasured, resolveNavigation } = require('./paginate.cjs');

const CSS = `
@page{size:210mm 297mm;margin:0}*{box-sizing:border-box}html,body{margin:0;color:#262d31;font-family:NotoSansSC,Arial,sans-serif;font-size:10.75pt;line-height:1.58}.page{width:210mm;height:297mm;padding:18mm 17mm 18mm 20mm;background:#f7f5ef;position:relative;break-after:page;overflow:hidden}.page__body{width:173mm;height:261mm;overflow:visible}.report-component{display:block;margin:0 0 6mm;border-top:.7pt solid #bdc5c3;padding-top:3mm}.report-component>h1{font:600 26pt/1.22 NotoSerifSC,serif;margin:0 0 7mm}.report-component>h2{font:600 20pt/1.35 NotoSerifSC,serif;margin:0 0 5mm}.report-block{display:block;margin:0 0 4mm}.report-block header{display:block}.report-block h3{font-size:12pt;line-height:1.45;margin:0 0 2mm}.report-block p{margin:0 0 2mm}.block-subtitle,.block-reason{color:#667176}.identity-key{display:inline-block;margin-right:2mm;font-size:8.5pt}.table-body,.source-table{width:100%;border-collapse:collapse;font-size:8.5pt;line-height:1.4}.table-body th,.table-body td,.source-table th,.source-table td{border-bottom:.35pt solid #bdc5c3;padding:1.6mm;text-align:left;vertical-align:top}.source-table .source-locator{font-size:7.5pt}.block-figure{margin:0}.block-figure svg{width:100%;height:38mm;stroke:#0b6b66;fill:#d8e7e3}.folio{position:absolute;right:17mm;bottom:3mm;font-size:7.5pt}.intentional-blank{display:grid;place-items:center;color:#667176;font-size:8.5pt}.toc-list{margin:0;padding-left:6mm}.toc-list a{color:inherit}.toc-page{float:right;min-width:3ch;text-align:right}.page-item,.measure-item{display:flow-root;width:173mm}.measure-root{width:173mm}`;

function playwright() {
  const runtime = path.resolve(process.env.ALLEN_RUNTIME || path.join(__dirname, '../../../..'));
  const modulePath = path.join(runtime, 'vendor/report-forge/node_modules/playwright');
  if (!fs.existsSync(modulePath)) throw reportError('REPORT_RUNTIME_MISSING', `locked Playwright not found: ${modulePath}`);
  return require(modulePath);
}

function sourceTable(fragment) {
  if (!fragment.table) return '';
  const rows = fragment.payload.references.map(reference => {
    const locators = (reference.locators || []).map(value => `<span data-source-locator="${escapeHtml(value)}">${escapeHtml(value)}</span>`).join('、');
    return `<tr data-source-record="${escapeHtml(reference.id || '')}"><th scope="row">${escapeHtml(reference.id || '')}</th><td>${escapeHtml(reference.title || '')}</td><td class="source-locator">${locators}</td></tr>`;
  }).join('');
  return `<table class="source-table"><thead><tr><th scope="col">编号</th><th scope="col">来源</th><th scope="col">定位</th></tr></thead><tbody>${rows}</tbody></table>`;
}

function tocList(fragment) {
  if (fragment.kind !== 'toc') return '';
  const entries = fragment.payload.entries.map(entry => `<li><a href="#${escapeHtml(entry.destination)}-title">${escapeHtml(entry.title || entry.destination)} <span class="toc-page">{{PAGE:${escapeHtml(entry.destination)}}}</span></a></li>`).join('');
  return `<ol class="toc-list">${entries}</ol>`;
}

function fragmentHtml(fragment) {
  const base = renderComponent(fragment.kind, fragment.payload, {});
  return base.replace(/<\/(section|nav|aside)>$/, `${tocList(fragment)}${sourceTable(fragment)}</$1>`);
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

async function measure(fragments) {
  const { chromium } = playwright();
  const browser = await chromium.launch({ headless: true });
  try {
    const page = await browser.newPage({ viewport: { width: 1191, height: 1684 }, deviceScaleFactor: 1 });
    const body = fragments.map((fragment, index) => `<div class="measure-item" data-index="${index}">${fragment.html}</div>`).join('');
    await page.setContent(`<!doctype html><html><head><meta charset="utf-8"><style>${CSS}</style></head><body><main class="measure-root">${body}</main></body></html>`, { waitUntil: 'load' });
    const result = await page.evaluate(() => {
      const pxPerMm = 96 / 25.4;
      const items = [...document.querySelectorAll('.measure-item')].map(element => ({
        heightPx: Math.ceil(element.getBoundingClientRect().height * 1000) / 1000,
        minimumFontPt: Math.min(...[...element.querySelectorAll('*')].filter(node => getComputedStyle(node).display !== 'none').map(node => parseFloat(getComputedStyle(node).fontSize) * .75)),
      }));
      return { items, contentHeightPx: Math.round(261 * pxPerMm * 1000) / 1000 };
    });
    return result;
  } finally {
    await browser.close();
  }
}

function renderPages(pages, navigation, title) {
  let html = `<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><title>${escapeHtml(title || 'Report')}</title><style>${CSS}</style></head><body>${pages.map(page => {
    if (page.intentionalBlank) return `<section class="page intentional-blank" data-page-id="${page.id}" aria-label="Intentionally blank page"><span>本页有意留白</span><span class="folio">${page.number}</span></section>`;
    const content = page.items.map(item => `<div class="page-item">${item.html}</div>`).join('');
    return `<section class="page" data-page-id="${page.id}"><div class="page__body">${content}</div><span class="folio">${page.number}</span></section>`;
  }).join('')}</body></html>`;
  html = html.replace(/\{\{PAGE:([^}]+)\}\}/g, (_, id) => {
    const number = navigation.anchorToPage[id] || navigation.componentToPage[id];
    if (!number) throw reportError('REPORT_NAVIGATION_TARGET', `unknown navigation destination: ${id}`);
    return `<span data-cross-reference="${escapeHtml(id)}">${number}</span>`;
  });
  return html;
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
  const fragments = expandComponents(document.components).map(blockMetadata).map(fragment => ({ ...fragment, html: fragmentHtml(fragment) }));
  const measured = await measure(fragments);
  measured.items.forEach((item, index) => Object.assign(fragments[index], item));
  const pages = paginateMeasured(fragments, measured.contentHeightPx);
  const navigation = resolveNavigation(pages);
  const html = renderPages(pages, navigation, document.title);
  const tableContinuations = pages.flatMap(page => page.items.filter(item => item.table).map(item => ({
    componentId: item.originalId, page: page.number, startRow: item.startRow, endRow: item.endRow, rowCount: item.rowCount,
  })));
  const minimumFontPt = measured.items.length ? Math.min(...measured.items.map(item => item.minimumFontPt)) : 10.75;
  const manifestPages = pages.map(page => ({
    id: page.id, number: page.number, intentionalBlank: page.intentionalBlank,
    usedHeightPx: Math.round(page.usedHeightPx * 1000) / 1000,
    contentHeightPx: measured.contentHeightPx,
    geometry: PAGE,
  }));
  const pagesWithTable = pages.filter(page => page.items.some(item => item.table)).map(page => ({
    page: page.number, tableHeaderCount: page.items.filter(item => item.table).length,
  }));
  return { html, manifest: { pageCount: pages.length, blockToPage: navigation.blockToPage, anchorToPage: navigation.anchorToPage, tableContinuations, pages: manifestPages, pagesWithTable, minimumFontPt: Math.round(minimumFontPt * 1000) / 1000 } };
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
