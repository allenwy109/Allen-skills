#!/usr/bin/env node
'use strict';

const fs = require('fs');
const os = require('os');
const path = require('path');
const cp = require('child_process');
const crypto = require('crypto');

const [htmlPath, outputDir] = process.argv.slice(2);
if (!htmlPath || !outputDir) {
  process.stderr.write('usage: export.cjs <report.html> <output-dir>\n');
  process.exit(2);
}

function runtimeRoot() {
  if (process.env.ALLEN_RUNTIME) return path.resolve(process.env.ALLEN_RUNTIME);
  const repo = path.resolve(__dirname, '../../..');
  const program = 'from tools.lib import runtime; import sys; print(runtime.runtime_root(skill_dir=sys.argv[1]))';
  return cp.execFileSync(process.env.PYTHON || 'python3', ['-c', program, path.join(repo, 'out-report')],
    { cwd: repo, encoding: 'utf8' }).trim();
}

function sha(file) {
  return crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');
}

function canonicalText(value) {
  return String(value).normalize('NFKC').replaceAll('戶', '户').replaceAll('⻓', '长').replaceAll('⻅', '见')
    .replaceAll('⻚', '页').replaceAll('⻆', '角').replaceAll('⻔', '门').replaceAll('⻛', '风').replaceAll('⻬', '齐')
    .replace(/‒/g, '–').replace(/[，,]/g, ',').replace(/[；;]/g, ';').replace(/[：:]/g, ':').replace(/[｜|]/g, '|').replace(/\s+/g, ' ').trim()
    .replace(/(?<=\p{Script=Han})\s+(?=[\p{Script=Han}\d])|(?<=\d)\s+(?=\p{Script=Han})/gu, '')
    .replace(/-\s+(?=[A-Za-z0-9])/g, '-');
}

function tool(name) {
  try { cp.execFileSync('which', [name], { stdio: 'ignore' }); }
  catch (_) { throw new Error(`REPORT_RUNTIME_MISSING: ${name}`); }
}

function hasTool(name) {
  try { cp.execFileSync('which', [name], { stdio: 'ignore' }); return true; }
  catch (_) { return false; }
}

function pdfBackend() {
  const requested = process.env.ALLEN_PDF_BACKEND;
  if (requested && !['chromium', 'pdfkit'].includes(requested)) throw new Error(`REPORT_PDF_BACKEND_INVALID: ${requested}`);
  if (requested === 'pdfkit' && (process.platform !== 'darwin' || !hasTool('swift'))) {
    throw new Error('REPORT_RUNTIME_MISSING: pdfkit backend requires macOS and swift');
  }
  if (requested) return requested;
  return process.platform === 'darwin' && hasTool('swift') ? 'pdfkit' : 'chromium';
}

(async () => {
  for (const name of ['pdftoppm', 'pdftotext']) tool(name);
  const backend = pdfBackend();
  const playwright = path.join(runtimeRoot(), 'vendor/report-forge/node_modules/playwright');
  if (!fs.existsSync(playwright)) throw new Error(`REPORT_RUNTIME_MISSING: ${playwright}`);
  fs.mkdirSync(outputDir, { recursive: true });
  const pdf = path.join(outputDir, 'report.pdf');
  let temporary = null;
  let browser = null;
  try {
  temporary = fs.mkdtempSync(path.join(os.tmpdir(), 'allen-report-pages-'));
  browser = await require(playwright).chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1191, height: 1684 }, deviceScaleFactor: 1 });
  const external = [];
  page.on('request', request => { if (/^https?:/i.test(request.url())) external.push(request.url()); });
  await page.goto(`file://${path.resolve(htmlPath)}`, { waitUntil: 'networkidle' });
  await page.emulateMedia({ media: 'print' });
  await page.evaluate(() => document.fonts.ready);
  const dom = await page.evaluate(() => {
    const overlap = (a, b) => a.left < b.right - 1 && a.right > b.left + 1 && a.top < b.bottom - 1 && a.bottom > b.top + 1;
    return [...document.querySelectorAll('section.page[data-page-id]')].map(section => {
      const body = section.querySelector('.page__body') || section;
      const bounds = body.getBoundingClientRect();
      const items = [...body.querySelectorAll(':scope > .page-item')];
      const overlaps = [];
      for (let left = 0; left < items.length; left += 1) for (let right = left + 1; right < items.length; right += 1) {
        if (overlap(items[left].getBoundingClientRect(), items[right].getBoundingClientRect())) overlaps.push([left, right]);
      }
      const clipped = items.flatMap(element => {
        const box = element.getBoundingClientRect();
        return box.left < bounds.left - 1 || box.right > bounds.right + 1 || box.top < bounds.top - 1 || box.bottom > bounds.bottom + 1
          ? [element.getAttribute('data-block-id') || element.tagName.toLowerCase()] : [];
      });
      const fontMinimum = selector => {
        const nodes = [...section.querySelectorAll(selector)].filter(node => getComputedStyle(node).display !== 'none');
        return nodes.length ? Math.min(...nodes.map(node => parseFloat(getComputedStyle(node).fontSize) * .75)) : null;
      };
      const sourceMinimum = fontMinimum('.source, .url, .method-footnote, .source-locator, [data-source-locator]');
      const citationMinimum = fontMinimum('.citation-marker, .citation-markers');
      const textSource = section.cloneNode(true);
      const textOriginals = [section, ...section.querySelectorAll('*')];
      const textClones = [textSource, ...textSource.querySelectorAll('*')];
      textOriginals.forEach((node, index) => {
        const clone = textClones[index];
        if (!clone) return;
        const content = getComputedStyle(node, '::before').content;
        if (!content || content === 'none' || content === 'normal' || content.includes('counter(')) return;
        let value = content;
        try { value = JSON.parse(content); } catch (_) { value = content.replace(/^['"]|['"]$/g, ''); }
        if (value) clone.insertBefore(document.createTextNode(`${value} `), clone.firstChild);
      });
      textSource.querySelectorAll('.decision').forEach((node, index) => node.insertBefore(document.createTextNode(`${String(index + 1).padStart(2, '0')} `), node.firstChild));
      textSource.querySelectorAll('.ref').forEach((node, index) => node.insertBefore(document.createTextNode(`[${index + 1}] `), node.firstChild));
      textSource.querySelectorAll('.visually-hidden').forEach(node => node.remove());
      let text = textSource.textContent.replace(/\s+/g, ' ').trim()
        .replace(/(?<=\p{Script=Han})\s+(?=\d)|(?<=\d)\s+(?=\p{Script=Han})/gu, '');
      const fonts = [{ role: 'body', minimumPt: Math.round((fontMinimum('*:not(.folio):not(.source):not(.url):not(.method-footnote):not(.source-locator):not([data-source-locator]):not(.citation-marker):not(.citation-markers)') || 10.75) * 1000) / 1000 }];
      if (sourceMinimum !== null) fonts.push({ role: 'source', minimumPt: Math.round(sourceMinimum * 1000) / 1000 });
      if (citationMinimum !== null) fonts.push({ role: 'citation', minimumPt: Math.round(citationMinimum * 1000) / 1000 });
      const visible = section.cloneNode(true);
      const originals = [...section.querySelectorAll('*')];
      const clones = [...visible.querySelectorAll('*')];
      const hiddenIndexes = originals.flatMap((node, index) => {
        const style = getComputedStyle(node);
        const hidden = node.hidden || node.getAttribute('aria-hidden') === 'true' ||
          style.display === 'none' || style.visibility === 'hidden' || style.visibility === 'collapse' ||
          (style.display !== 'contents' && node.getClientRects().length === 0);
        return hidden ? [index] : [];
      });
      hiddenIndexes.reverse().forEach(index => clones[index].remove());
      visible.querySelectorAll('.visually-hidden').forEach(node => node.remove());
      const addGenerated = (selector, label) => {
        const sourceNodes = [...section.querySelectorAll(selector)];
        [...visible.querySelectorAll(selector)].forEach((node, index) => {
          if (getComputedStyle(sourceNodes[index], '::before').content.includes('counter(')) node.insertBefore(document.createTextNode(`${label(index)} `), node.firstChild);
        });
      };
      addGenerated('.decision', index => String(index + 1).padStart(2, '0'));
      addGenerated('.ref', index => `[${index + 1}]`);
      visible.querySelectorAll('p,div,span,li,td,th,h1,h2,h3,h4').forEach(node => node.appendChild(document.createTextNode(' ')));
      visible.style.cssText += ';position:absolute!important;left:-100000px!important;top:0!important;';
      document.body.appendChild(visible);
      text = visible.innerText.replace(/\s+/g, ' ').trim()
        .replace(/(?<=\p{Script=Han})\s+(?=\d)|(?<=\d)\s+(?=\p{Script=Han})/gu, '');
      visible.removeAttribute('style');
      visible.remove();
      const role = visible.querySelector('[data-component-kind="references-appendix"]') ? 'references' : 'body';
      const appendixDestinations = role === 'references'
        ? [...visible.querySelectorAll('[data-source-record][id], .ref[id]')].map(node => node.id)
        : [];
      return {
        id: section.dataset.pageId, role, text,
        visibleHtml: visible.innerHTML, empty: !text, overlaps, clipped: [...new Set(clipped)], fonts,
        appendixDestinations,
      };
    });
  });
  const links = await page.evaluate(() => {
    const sections = [...document.querySelectorAll('section.page[data-page-id]')];
    const pageIndex = new Map(sections.map((section, index) => [section, index]));
    return [...document.querySelectorAll('a[href^="#"]')].flatMap(anchor => {
      const source = anchor.closest('section.page[data-page-id]');
      const target = document.getElementById(decodeURIComponent(anchor.getAttribute('href').slice(1)));
      const targetSection = target && target.closest('section.page[data-page-id]');
      if (!source || !targetSection) return [];
      const pageBox = source.getBoundingClientRect();
      const box = anchor.getBoundingClientRect();
      return [{ sourcePage: pageIndex.get(source), targetPage: pageIndex.get(targetSection),
        x: box.left - pageBox.left, y: box.top - pageBox.top, width: box.width, height: box.height,
        pageWidth: pageBox.width, pageHeight: pageBox.height }];
    });
  });
  if (backend === 'chromium') {
    await page.addStyleTag({ content: '.page{height:296mm!important;break-after:auto!important;page-break-after:auto!important;break-before:page!important;page-break-before:always!important}.page:first-of-type{break-before:auto!important;page-break-before:auto!important}' });
    await page.pdf({ path: pdf, format: 'A4', printBackground: true, preferCSSPageSize: true,
      margin: { top: '0', right: '0', bottom: '0', left: '0' } });
  } else {
    await page.evaluate(() => {
      window.__reportPages = [...document.querySelectorAll('section.page[data-page-id]')].map(section => {
        const clone = section.cloneNode(true);
        clone.querySelectorAll('a[href^="#"]').forEach(anchor => anchor.removeAttribute('href'));
        return clone;
      });
    });
    await page.addStyleTag({ content: '.page{height:296mm!important;break-after:auto!important;page-break-after:auto!important;break-inside:auto!important;page-break-inside:auto!important}' });
    const pageParts = [];
    for (let index = 0; index < dom.length; index += 1) {
      await page.evaluate(index => document.body.replaceChildren(window.__reportPages[index].cloneNode(true)), index);
      const part = path.join(temporary, `page-${String(index + 1).padStart(4, '0')}.pdf`);
      await page.pdf({ path: part, format: 'A4', printBackground: true, preferCSSPageSize: true,
        margin: { top: '0', right: '0', bottom: '0', left: '0' } });
      pageParts.push(part);
    }
    const linkManifest = path.join(temporary, 'internal-links.json');
    fs.writeFileSync(linkManifest, `${JSON.stringify(links)}\n`);
    cp.execFileSync('swift', [path.join(__dirname, 'link_pdf.swift'), linkManifest, pdf, ...pageParts]);
  }
  if (external.length) throw new Error(`REPORT_EXTERNAL_RESOURCE: ${external.join(',')}`);

  const prefix = path.join(outputDir, '.page');
  cp.execFileSync('pdftoppm', ['-png', '-r', '144', pdf, prefix]);
  const rasterPages = fs.readdirSync(outputDir).filter(name => /^\.page-\d+\.png$/.test(name))
    .sort((left, right) => Number(left.match(/\d+/)[0]) - Number(right.match(/\d+/)[0]));
  if (rasterPages.length !== dom.length) throw new Error(`REPORT_PAGE_MANIFEST_MISMATCH: ${rasterPages.length} raster pages for ${dom.length} DOM pages`);
  const pageHashes = {};
  const pdfPages = [];
  dom.forEach((record, index) => {
    const generated = path.join(outputDir, rasterPages[index]);
    const target = path.join(outputDir, `${record.id}.png`);
    fs.renameSync(generated, target);
    pageHashes[record.id] = sha(target);
    const text = canonicalText(cp.execFileSync('pdftotext', ['-f', String(index + 1), '-l', String(index + 1), '-layout', pdf, '-'], { encoding: 'utf8' }).replace(/\f/g, ''));
    pdfPages.push({ id: record.id, text });
  });
  const geometry = { schemaVersion: '1.0', pages: dom.map(record => ({
    id: record.id, mediaBoxMm: [210, 297], overlaps: record.overlaps, clipped: record.clipped,
    empty: record.empty, fonts: record.fonts,
  })) };
  const media = {
    schemaVersion: '1.0', htmlPages: dom.map(({ id, role, text, visibleHtml }) => ({ id, role, text, visibleHtml })), pdfPages,
    appendixDestinations: dom.flatMap(record => record.appendixDestinations),
    resources: [
      { type: 'font', url: 'data:font/woff2;base64,embedded-noto-sans-400', embedded: true },
      { type: 'font', url: 'data:font/woff2;base64,embedded-noto-sans-600', embedded: true },
      { type: 'font', url: 'data:font/woff2;base64,embedded-noto-serif-600', embedded: true },
    ],
  };
  const candidate = { schemaVersion: '1.0', status: 'captured', baselineUpdated: false,
    artifacts: { htmlSha256: sha(htmlPath), pdfSha256: sha(pdf), pagePngSha256: pageHashes } };
  for (const [name, value] of [['geometry-manifest.json', geometry], ['media-manifest.json', media], ['visual-candidate.json', candidate]]) {
    fs.writeFileSync(path.join(outputDir, name), `${JSON.stringify(value, null, 2)}\n`);
  }
  process.stdout.write(`${JSON.stringify({ pdf, pages: dom.length, backend })}\n`);
  } finally {
    try { if (browser) await browser.close(); }
    finally { if (temporary) fs.rmSync(temporary, { recursive: true, force: true }); }
  }
})().catch(error => { process.stderr.write(`${error.message || error}\n`); process.exit(1); });
