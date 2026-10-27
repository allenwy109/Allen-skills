#!/usr/bin/env node
const fs = require("fs");
const path = require("path");
const crypto = require("crypto");
const cp = require("child_process");

const here = path.resolve(process.env.GOLDEN_DIR || __dirname);
const runtime = path.resolve(process.env.ALLEN_RUNTIME || path.join(here, "../.."));
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
    return {pageCount: pages.length, pageIds: pages.map(p => p.dataset.pageId), overflowPageIds, sourceFooterOverlapPageIds};
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
  if (baseline.status === "approved" && baseline.candidateDigest !== candidate.candidateDigest) {
    console.error("approved baseline does not match the rendered candidate; approval was not overwritten");
    process.exit(2);
  }
  fs.writeFileSync(path.join(build, "visual-candidate.json"), JSON.stringify(candidate, null, 2) + "\n");
  console.log(`Rendered ${pngs.length} pages with ${chromiumRevision}; external requests: 0; approval: ${baseline.status}`);
})().catch(error => { console.error(error.stack || error); process.exit(1); });
