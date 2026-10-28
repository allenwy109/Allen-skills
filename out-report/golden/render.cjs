#!/usr/bin/env node
const fs = require("fs");
const path = require("path");
const crypto = require("crypto");
const cp = require("child_process");

const here = path.resolve(process.env.GOLDEN_DIR || __dirname);
const runtime = path.resolve(process.env.ALLEN_DEPENDENCY_RUNTIME || process.env.ALLEN_RUNTIME || path.join(here, "../.."));
const build = path.join(here, "build");
const files = {html: path.join(here, "golden.html"), css: path.join(here, "golden.css"), report: path.join(here, "golden-report.json"), baseline: path.join(here, "visual-baseline.json")};
const fontDir = path.join(runtime, "vendor/report-forge/assets/fonts");
const fonts = [
  {placeholder: "__FONT_NOTO_SANS_SC_400__", file: "noto-sans-sc-400.woff2", family: "NotoSansSC-400", hash: "758dff09a5625dd659ea4c529ffdb7741bdbc182b54957a7007f1cfcfd450820"},
  {placeholder: "__FONT_NOTO_SANS_SC_600__", file: "noto-sans-sc-600.woff2", family: "NotoSansSC-600", hash: "722d2f69f1b0f494148dd6a492f7efcfcc9ba9b6c0a203b39987feea076a6064"},
  {placeholder: "__FONT_NOTO_SERIF_SC_600__", file: "noto-serif-sc-600.woff2", family: "NotoSerifSC-600", hash: "f6e3c090225ed5372d7ca7175e4148b8f4fb676be73f932891f64a91512c7a5a"},
];
const shaBuffer = value => crypto.createHash("sha256").update(value).digest("hex");
const shaFile = value => shaBuffer(fs.readFileSync(value));
const count = (text, needle) => text.split(needle).length - 1;
const requireTool = name => { try { cp.execFileSync("which", [name], {stdio: "ignore"}); } catch (_) { throw new Error(`Required tool not found: ${name}`); } };
const replaceExact = (text, placeholder, value) => {
  if (count(text, placeholder) !== 1) throw new Error(`${placeholder} must occur exactly once`);
  return text.replace(placeholder, value);
};
const stablePageId = index => `page-${String(index + 1).padStart(3, "0")}`;
const canonicalJson = value => JSON.stringify(value, (_, current) => current && typeof current === 'object' && !Array.isArray(current)
  ? Object.fromEntries(Object.entries(current).sort(([left], [right]) => left.localeCompare(right))) : current);

// Resolve every dependency and validate every maintenance input before writing build output.
for (const value of Object.values(files)) if (!fs.existsSync(value)) throw new Error(`Missing source: ${value}`);
for (const tool of ["pdftoppm", "pdfinfo", "pdftotext"]) requireTool(tool);
let chromium;
for (const candidate of [path.join(runtime, "vendor/report-forge/node_modules/playwright"), path.join(runtime, "node_modules/playwright"), "playwright"]) {
  try { chromium = require(candidate).chromium; break; } catch (_) {}
}
if (!chromium) throw new Error("Playwright not found; set ALLEN_RUNTIME to the Allen-skills checkout");
for (const font of fonts) {
  const p = path.join(fontDir, font.file);
  if (!fs.existsSync(p)) throw new Error(`Missing font: ${p}`);
  if (shaFile(p) !== font.hash) throw new Error(`Font hash mismatch: ${font.file}`);
}
const report = JSON.parse(fs.readFileSync(files.report, "utf8"));
const baseline = JSON.parse(fs.readFileSync(files.baseline, "utf8"));
let css = fs.readFileSync(files.css, "utf8");
for (const font of fonts) css = replaceExact(css, font.placeholder, `data:font/woff2;base64,${fs.readFileSync(path.join(fontDir, font.file)).toString("base64")}`);
let html = replaceExact(fs.readFileSync(files.html, "utf8"), "__GOLDEN_CSS__", css);
if (/__[A-Z0-9_]+__/.test(html)) throw new Error("Compiled HTML contains unresolved placeholders");

fs.mkdirSync(build, {recursive: true});
fs.rmSync(path.join(build, "current-review"), {recursive: true, force: true});
for (const name of fs.readdirSync(build)) {
  if (["golden-report.html", "golden-report.pdf", "visual-candidate.json", "golden-report.txt"].includes(name) || /^page-\d+\.png$/.test(name)) fs.rmSync(path.join(build, name));
}
const compiledHtml = path.join(build, "golden-report.html");
const pdfPath = path.join(build, "golden-report.pdf");
fs.writeFileSync(compiledHtml, html);

(async () => {
  const browser = await chromium.launch({headless: true});
  const page = await browser.newPage({viewport: {width: 1191, height: 1684}, deviceScaleFactor: 1});
  const requests = [];
  page.on("request", req => { if (/^https?:/.test(req.url())) requests.push(req.url()); });
  await page.goto(`file://${compiledHtml}`, {waitUntil: "networkidle"});
  const loadFonts = () => page.evaluate(async () => {
    await Promise.all([
      document.fonts.load('400 10.75pt "NotoSansSC"'),
      document.fonts.load('600 10.75pt "NotoSansSC"'),
      document.fonts.load('600 10.75pt "NotoSerifSC"'),
    ]);
    await document.fonts.ready;
  });
  await loadFonts();
  await page.reload({waitUntil: "networkidle"});
  await loadFonts();
  await page.emulateMedia({media: "print"});
  const layoutQa = await page.evaluate(() => {
    const pages = [...document.querySelectorAll("section.page[data-page-id]")];
    const overflowPageIds = [];
    const sourceFooterOverlapPageIds = [];
    for (const page of pages) {
      const pageBox = page.getBoundingClientRect();
      const descendants = [...page.querySelectorAll("*")].filter(el => getComputedStyle(el).position !== "fixed");
      if (descendants.some(el => { const b = el.getBoundingClientRect(); return b.right > pageBox.right + 1 || b.bottom > pageBox.bottom + 1 || b.left < pageBox.left - 1 || b.top < pageBox.top - 1; })) overflowPageIds.push(page.dataset.pageId);
      const source = page.querySelector(".source"), folio = page.querySelector(".folio"), takeaway = page.querySelector(".takeaway:last-of-type");
      const overlap = (a, b) => a && b && a.left < b.right && a.right > b.left && a.top < b.bottom && a.bottom > b.top;
      if ((source && folio && overlap(source.getBoundingClientRect(), folio.getBoundingClientRect())) || (source && takeaway && overlap(source.getBoundingClientRect(), takeaway.getBoundingClientRect()))) sourceFooterOverlapPageIds.push(page.dataset.pageId);
    }
    return {pageCount: pages.length, pageIds: pages.map(p => p.dataset.pageId), overflowPageIds, sourceFooterOverlapPageIds,
      pages: pages.map((p, index) => {
        const box = p.getBoundingClientRect(), style = getComputedStyle(p);
        const top = box.top + parseFloat(style.paddingTop), contentHeight = box.height - parseFloat(style.paddingTop) - parseFloat(style.paddingBottom);
        const flow = [...p.children].filter(node => !node.matches('.folio,.source,.citation-markers') && !['absolute', 'fixed'].includes(getComputedStyle(node).position));
        const used = flow.length ? Math.max(...flow.map(node => node.getBoundingClientRect().bottom)) - top : 0;
        const role = p.dataset.pageRole;
        const whitespaceJustification = role === 'cover' ? 'cover-identity' : role === 'toc' ? 'toc-navigation' : undefined;
        return {id: `page-${String(index + 1).padStart(3, '0')}`, number: index + 1, intentionalBlank: false,
          usedHeightPx: Math.max(0, Math.ceil(used * 1000) / 1000), contentHeightPx: Math.ceil(contentHeight * 1000) / 1000,
          role: role === 'cover' ? 'cover' : role === 'toc' ? 'toc' : role === 'section' ? 'section-divider' : role === 'references' ? 'references' : 'body',
          ...(whitespaceJustification ? {whitespaceJustification} : {}), geometry: {widthMm: 210, heightMm: 297}};
      })};
  });
  const expectedIds = report.pages.map(p => p.id);
  if (JSON.stringify(layoutQa.pageIds) !== JSON.stringify(expectedIds)) throw new Error("DOM page IDs differ from manifest");
  if (layoutQa.overflowPageIds.length || layoutQa.sourceFooterOverlapPageIds.length) throw new Error(`Layout QA failed: ${JSON.stringify(layoutQa)}`);
  await page.pdf({path: pdfPath, format: "A4", printBackground: true, preferCSSPageSize: true, margin: {top: "0", right: "0", bottom: "0", left: "0"}});
  if (requests.length) throw new Error(`External requests detected: ${requests.join(", ")}`);
  const chromiumRevision = browser.version();
  await browser.close();

  const info = cp.execFileSync("pdfinfo", [pdfPath], {encoding: "utf8"});
  const pdfPages = Number(info.match(/^Pages:\s+(\d+)/m)?.[1]);
  const size = info.match(/^Page size:\s+([\d.]+) x ([\d.]+) pts/m);
  if (pdfPages !== report.pages.length || !size) throw new Error("PDF page count or geometry is invalid");
  cp.execFileSync("pdftoppm", ["-png", "-r", "144", pdfPath, path.join(build, "page")]);
  const pngs = fs.readdirSync(build).filter(name => /^page-\d+\.png$/.test(name)).sort();
  const expectedPngs = report.pages.map((_, i) => `page-${String(i + 1).padStart(2, "0")}.png`);
  if (JSON.stringify(pngs) !== JSON.stringify(expectedPngs)) throw new Error(`PNG set mismatch: ${pngs.join(",")}`);
  const text = cp.execFileSync("pdftotext", ["-layout", pdfPath, "-"], {encoding: "utf8"});
  const textPages = text.split("\f").filter(part => part.trim()).length;
  if (textPages !== report.pages.length) throw new Error(`PDF text pages ${textPages} != ${report.pages.length}`);

  const candidate = {
    schemaVersion: "1.0", status: "captured", approvalStatus: baseline.status,
    environment: {chromiumRevision, viewport: {width: 1191, height: 1684}, deviceScaleFactor: 1, rasterDpi: 144, fontHashes: Object.fromEntries(fonts.map(f => [f.family, f.hash])), pdf: {format: "A4", printBackground: true, preferCSSPageSize: true}},
    artifacts: {htmlSha256: shaFile(compiledHtml), pagePngSha256: Object.fromEntries(pngs.map(name => [name, shaFile(path.join(build, name))]))},
    pdfSummary: {pages: pdfPages, pageSize: "A4", textPages, geometry: `${size[1]}x${size[2]}pt`},
    layoutQa,
    accessibility: {htmlSemanticLandmarks: true, chartsHaveAccessibleTablesOrLabels: true, pdfTagged: false, limitation: "Chromium PDF export does not provide a reliable tagged-PDF contract."},
  };
  const digestInput = {
    environment: candidate.environment,
    artifacts: candidate.artifacts,
    pdfSummary: candidate.pdfSummary,
    layoutQa: candidate.layoutQa,
    accessibility: candidate.accessibility,
  };
  candidate.candidateDigest = shaBuffer(JSON.stringify(digestInput));
  const qaExport = path.join(build, "qa-export");
  fs.rmSync(qaExport, {recursive: true, force: true});
  const a4Scripts = [path.join(here, "../scripts/a4"), path.join(process.cwd(), "out-report/scripts/a4"), path.join(runtime, "out-report/scripts/a4")]
    .find(candidate => fs.existsSync(path.join(candidate, "export.cjs")));
  if (!a4Scripts) throw new Error("A4 QA scripts not found");
  cp.execFileSync("node", [path.join(a4Scripts, "export.cjs"), compiledHtml, qaExport], {
    env: {...process.env, ALLEN_RUNTIME: runtime}, stdio: "pipe",
  });
  const geometry = JSON.parse(fs.readFileSync(path.join(qaExport, "geometry-manifest.json"), "utf8"));
  const media = JSON.parse(fs.readFileSync(path.join(qaExport, "media-manifest.json"), "utf8"));
  const remapPages = pages => pages.map((page, index) => ({...page, id: stablePageId(index)}));
  geometry.pages = remapPages(geometry.pages);
  media.htmlPages = remapPages(media.htmlPages);
  media.pdfPages = remapPages(media.pdfPages);
  media.htmlPages.forEach((page, index) => { const role = report.pages[index].role; page.role = role === 'cover' ? 'cover' : role === 'toc' ? 'toc' : role === 'section' ? 'section-divider' : role === 'references' ? 'references' : 'body'; });
  media.appendixDestinations = [...html.matchAll(/class="ref"\s+id="([^"]+)"/g)].map(match => match[1]);
  const approvedPages = JSON.parse(fs.readFileSync(path.join(here, "approved-page-baseline.json"), "utf8")).artifacts.pagePngSha256;
  const candidatePages = Object.fromEntries(pngs.map((name, index) => [stablePageId(index), shaFile(path.join(build, name))]));
  const pageSequence = value => Object.entries(value).map(([id, digest]) => ({id, digest}));
  const differences = [...new Set([...Object.keys(approvedPages), ...Object.keys(candidatePages)])].sort().flatMap(pageId => {
    const before = approvedPages[pageId] ?? null, after = candidatePages[pageId] ?? null;
    return before === after ? [] : [{page: pageId, kind: before === null ? "added" : after === null ? "removed" : "changed", baseline: before, candidate: after}];
  });
  const regression = {
    status: differences.length ? "different" : "identical",
    baselineDigest: shaBuffer(canonicalJson(approvedPages)), candidateDigest: shaBuffer(canonicalJson(candidatePages)),
    baselinePages: pageSequence(approvedPages), candidatePages: pageSequence(candidatePages), differences,
    differenceDigest: shaBuffer(canonicalJson(differences)), baselineUpdated: false,
  };
  const emptyCoverage = Object.fromEntries(["claims", "a_cards", "panels", "relations", "metrics", "sources"].map(key => [key, []]));
  const qaEvidence = {pagination: {pageCount: layoutQa.pageCount, maximumUnusedRatio: .56, pages: layoutQa.pages}, geometry,
    coverage: {input: emptyCoverage, output: emptyCoverage}, media, regression};
  const qaProcess = cp.spawnSync("node", [path.join(a4Scripts, "qa.cjs")], {input: JSON.stringify(qaEvidence), encoding: "utf8"});
  if (qaProcess.status !== 0) throw new Error(`Golden QA execution failed: ${qaProcess.stderr}`);
  const qaResult = JSON.parse(qaProcess.stdout);
  fs.writeFileSync(path.join(here, "qa-evidence.json"), JSON.stringify(qaEvidence, null, 2) + "\n");
  fs.writeFileSync(path.join(here, "qa-result.json"), JSON.stringify(qaResult, null, 2) + "\n");
  fs.rmSync(qaExport, {recursive: true, force: true});
  if (baseline.status === "approved" && qaResult.status !== "passed") throw new Error(`Approved golden must pass QA: ${JSON.stringify(qaResult.blocking)}`);
  if (baseline.status === "approved" && baseline.candidateDigest !== candidate.candidateDigest) {
    console.error(`approved baseline does not match the rendered candidate (approved=${baseline.candidateDigest}; rendered=${candidate.candidateDigest}); approval was not overwritten`);
    process.exit(2);
  }

  const reviewDir = path.join(build, "current-review");
  const reviewPagesDir = path.join(reviewDir, "pages");
  const sheetDir = path.join(reviewDir, "contact-sheets");
  fs.mkdirSync(reviewPagesDir, {recursive: true});
  fs.mkdirSync(sheetDir, {recursive: true});
  fs.copyFileSync(compiledHtml, path.join(reviewDir, "golden-report.html"));
  fs.copyFileSync(pdfPath, path.join(reviewDir, "golden-report.pdf"));
  for (const name of pngs) fs.copyFileSync(path.join(build, name), path.join(reviewPagesDir, name));

  const sheetGroups = [
    {id: "whole-book", pages: report.pages.map(page => page.id)},
    {id: "chapter-1", pages: ["p01", "p02", "p03", "p04", "p05"]},
    {id: "chapter-2", pages: ["p06", "p07", "p08", "p09"]},
    {id: "chapter-3", pages: ["p10", "p11", "p12", "p13", "p14"]},
    {id: "chapter-4", pages: ["p15", "p16"]},
  ];
  const sheetBrowser = await chromium.launch({headless: true});
  const reviewPage = await sheetBrowser.newPage({viewport: {width: 1400, height: 1000}, deviceScaleFactor: 1});
  const contactSheets = [];
  for (const group of sheetGroups) {
    const entries = group.pages.map(pageId => {
      const name = `page-${pageId.slice(1)}.png`;
      const data = fs.readFileSync(path.join(build, name)).toString("base64");
      return `<figure><img src="data:image/png;base64,${data}" alt="${pageId}"><figcaption>${pageId}</figcaption></figure>`;
    }).join("");
    await reviewPage.setContent(`<!doctype html><meta charset="utf-8"><style>*{box-sizing:border-box}body{margin:0;padding:28px;background:#d9dddb;color:#263034;font:600 18px Arial,sans-serif}h1{margin:0 0 20px;font-size:24px}.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:18px}figure{margin:0;background:#fff;padding:8px;border:1px solid #aeb7b4}img{display:block;width:100%;height:auto}figcaption{padding:7px 2px 1px;text-align:center}</style><h1>${group.id} · ${candidate.candidateDigest.slice(0, 12)}</h1><div class="grid">${entries}</div>`, {waitUntil: "load"});
    const relative = `contact-sheets/${group.id}.png`;
    const output = path.join(reviewDir, relative);
    await reviewPage.screenshot({path: output, fullPage: true});
    contactSheets.push({
      id: group.id,
      path: relative,
      pageIds: group.pages,
      inputPageSha256: Object.fromEntries(group.pages.map(pageId => {
        const name = `page-${pageId.slice(1)}.png`;
        return [name, candidate.artifacts.pagePngSha256[name]];
      })),
      sha256: shaFile(output),
    });
  }
  await sheetBrowser.close();
  const reviewManifest = {
    schemaVersion: "1.0",
    status: baseline.status,
    candidateDigest: candidate.candidateDigest,
    sourcePageHashes: candidate.artifacts.pagePngSha256,
    reportHtmlSha256: shaFile(compiledHtml),
    reportPdfSha256: shaFile(pdfPath),
    contactSheets,
  };
  fs.writeFileSync(path.join(reviewDir, "manifest.json"), JSON.stringify(reviewManifest, null, 2) + "\n");
  fs.writeFileSync(path.join(build, "visual-candidate.json"), JSON.stringify(candidate, null, 2) + "\n");
  console.log(`Rendered ${pngs.length} pages with ${chromiumRevision}; external requests: 0; approval: ${baseline.status}`);
})().catch(error => { console.error(error.stack || error); process.exit(1); });
