#!/usr/bin/env node
const fs = require("fs");
const path = require("path");
const crypto = require("crypto");
const cp = require("child_process");

const here = __dirname;
const root = path.resolve(here, "../..");
const runtime = process.env.ALLEN_RUNTIME || root;
const build = path.join(here, "build");
const htmlPath = path.join(here, "golden.html");
const cssPath = path.join(here, "golden.css");
const baselinePath = path.join(here, "visual-baseline.json");
const fontDir = path.join(runtime, "vendor/report-forge/assets/fonts");
const sha = (p) => crypto.createHash("sha256").update(fs.readFileSync(p)).digest("hex");
const dataFont = (name) => `data:font/woff2;base64,${fs.readFileSync(path.join(fontDir, name)).toString("base64")}`;

let css = fs.readFileSync(cssPath, "utf8")
  .replace(/(?:__FONT_SANS_400__|data:font\/woff2;base64,[A-Za-z0-9+/=]+)(?="\) format\("woff2"\);font-weight:400)/, dataFont("noto-sans-sc-400.woff2"))
  .replace(/(?:__FONT_SANS_600__|data:font\/woff2;base64,[A-Za-z0-9+/=]+)(?="\) format\("woff2"\);font-weight:600)/, dataFont("noto-sans-sc-600.woff2"))
  .replace(/(?:__FONT_SERIF_600__|data:font\/woff2;base64,[A-Za-z0-9+/=]+)(?="\) format\("woff2"\);font-weight:600)/, dataFont("noto-serif-sc-600.woff2"));
fs.writeFileSync(cssPath, css);
let html = fs.readFileSync(htmlPath, "utf8");
html = html.replace(/<style id="golden-css">[\s\S]*?<\/style>/, `<style id="golden-css">${css}</style>`);
fs.writeFileSync(htmlPath, html);
fs.mkdirSync(build, {recursive: true});

let chromium;
for (const candidate of [
  path.join(runtime, "vendor/report-forge/node_modules/playwright"),
  path.join(runtime, "node_modules/playwright"),
  "playwright"
]) {
  try { chromium = require(candidate).chromium; break; } catch (_) {}
}
if (!chromium) throw new Error("Playwright not found; set ALLEN_RUNTIME to the Allen-skills checkout");

(async () => {
  const browser = await chromium.launch({headless: true});
  const page = await browser.newPage({viewport: {width: 1191, height: 1684}, deviceScaleFactor: 1});
  const requests = [];
  page.on("request", req => { if (/^https?:/.test(req.url())) requests.push(req.url()); });
  await page.goto(`file://${htmlPath}`, {waitUntil: "networkidle"});
  await page.emulateMedia({media: "print"});
  await page.pdf({path: path.join(build, "golden-report.pdf"), format: "A4", printBackground: true, preferCSSPageSize: true, margin: {top: "0", right: "0", bottom: "0", left: "0"}});
  if (requests.length) throw new Error(`External requests detected: ${requests.join(", ")}`);
  const version = browser.version();
  await browser.close();
  cp.execFileSync("pdftoppm", ["-png", "-r", "144", path.join(build, "golden-report.pdf"), path.join(build, "page")]);
  fs.copyFileSync(htmlPath, path.join(build, "golden-report.html"));
  const pngs = fs.readdirSync(build).filter(f => /^page-\d+\.png$/.test(f)).sort();
  const baseline = JSON.parse(fs.readFileSync(baselinePath, "utf8"));
  baseline.environment.chromiumRevision = version;
  baseline.artifacts.htmlSha256 = sha(htmlPath);
  baseline.artifacts.pdfSha256 = sha(path.join(build, "golden-report.pdf"));
  baseline.artifacts.pagePngSha256 = Object.fromEntries(pngs.map(f => [f, sha(path.join(build, f))]));
  fs.writeFileSync(baselinePath, JSON.stringify(baseline, null, 2) + "\n");
  console.log(`Rendered ${pngs.length} pages with ${version}; external requests: 0`);
})().catch(err => { console.error(err.stack || err); process.exit(1); });
