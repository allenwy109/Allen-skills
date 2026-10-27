#!/usr/bin/env python3
"""Build a reproducible, blind same-input deck A/B review packet."""
import argparse
import collections
import contextlib
import hashlib
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "out-report/scripts/tests"))

import allen_compose  # noqa: E402
import out_deck  # noqa: E402
import synthetic  # noqa: E402
from tools.e2e.test_report_outputs import read_json, task_input_digest  # noqa: E402
from tools.lib import runtime  # noqa: E402
from tools.tests import fixtures as F  # noqa: E402

BUILD_ROOT = (ROOT / "out-deck/build").resolve()
MANAGED_MARKER = ".allen-visual-benchmark"


def benchmark_missing_tools():
    need = [name for name in ("node", "pdfinfo", "pdftoppm", "pdftotext") if not shutil.which(name)]
    try:
        need.extend(F.missing_tools())
        playwright = runtime.engine_dir("report-forge", skill_dir=ROOT / "out-deck") / "node_modules" / "playwright"
        if not playwright.is_dir():
            need.append("Playwright")
    except (OSError, runtime.RuntimeNotFound):
        need.append("Allen runtime with Playwright")
    return list(dict.fromkeys(need))


def require_benchmark_tools(test_case, missing=None):
    need = benchmark_missing_tools() if missing is None else missing
    if not need:
        return
    message = f"缺少工具：{', '.join(need)}"
    if os.environ.get("ALLEN_REQUIRE_TOOLS") == "1":
        test_case.fail(message)
    test_case.skipTest(message)


def sha(path):
    return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    pathlib.Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def validate_output(output):
    output = pathlib.Path(output).resolve()
    if output.parent != BUILD_ROOT or output == BUILD_ROOT:
        raise RuntimeError(f"BENCHMARK_OUTPUT_UNSAFE: {output}")
    if output.exists() and (not output.is_dir() or not (output / MANAGED_MARKER).is_file()):
        raise RuntimeError(f"BENCHMARK_OUTPUT_UNMANAGED: {output}")
    return output


def reset_output(output):
    output = validate_output(output)
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)
    (output / MANAGED_MARKER).write_text("managed visual benchmark output\n", encoding="utf-8")
    return output


@contextlib.contextmanager
def managed_staging(output):
    output = validate_output(output)
    staging = pathlib.Path(tempfile.mkdtemp(prefix=f".{output.name}-staging-", dir=BUILD_ROOT))
    (staging / MANAGED_MARKER).write_text("managed visual benchmark output\n", encoding="utf-8")
    backup = None
    try:
        yield staging
        if output.exists():
            backup = pathlib.Path(tempfile.mkdtemp(prefix=f".{output.name}-previous-", dir=BUILD_ROOT))
            backup.rmdir()
            output.replace(backup)
        staging.replace(output)
        if backup is not None:
            shutil.rmtree(backup)
    except Exception:
        if not output.exists() and backup is not None and backup.exists():
            backup.replace(output)
        raise
    finally:
        if staging.exists():
            shutil.rmtree(staging)
        if backup is not None and backup.exists():
            shutil.rmtree(backup)


def contact_sheet(out_dir, count):
    node = out_dir / "contact.cjs"
    playwright = runtime.engine_dir("report-forge", skill_dir=ROOT / "out-deck") / "node_modules" / "playwright"
    node.write_text("""const {chromium}=require(process.argv[2]),path=require('path'),fs=require('fs'),{pathToFileURL}=require('url');(async()=>{const b=await chromium.launch({headless:true});const p=await b.newPage({viewport:{width:1280,height:720},deviceScaleFactor:1});const dir=process.argv[3],n=Number(process.argv[4]),html=path.join(dir,'contact.html');fs.writeFileSync(html,'<style>body{margin:20px;background:#ddd;display:grid;grid-template-columns:repeat(3,384px);gap:12px}img{width:384px}</style>'+[...Array(n)].map((_,i)=>`<img src="${`page-${String(i+1).padStart(2,'0')}.png`}">`).join(''));await p.goto(pathToFileURL(html).href);await p.waitForLoadState('load');const loaded=await p.locator('img').evaluateAll(xs=>xs.every(x=>x.complete&&x.naturalWidth>0));if(!loaded)throw Error('contact sheet images did not load');await p.screenshot({path:path.join(dir,'contact-sheet.png'),fullPage:true});fs.unlinkSync(html);await b.close()})().catch(e=>{console.error(e);process.exit(1)})""", encoding="utf-8")
    subprocess.run(["node", str(node), str(playwright), str(out_dir), str(count)], check=True)
    node.unlink()


def html_page_texts(html_file, count):
    playwright = runtime.engine_dir("report-forge", skill_dir=ROOT / "out-deck") / "node_modules" / "playwright"
    page_probe = runtime.engine_dir("report-forge", skill_dir=ROOT / "out-deck") / "scripts" / "page_probe.cjs"
    script = """const {chromium}=require(process.argv[1]),probe=require(process.argv[2]),{pathToFileURL}=require('url');(async()=>{const b=await chromium.launch({channel:process.env.CHROME_CHANNEL||'chrome',headless:true});const p=await b.newPage({viewport:{width:1400,height:820}});await p.goto(pathToFileURL(process.argv[3]).href,{waitUntil:'networkidle'});await p.evaluate(()=>window.deckReady||document.fonts.ready);const out=[];for(let i=0;i<Number(process.argv[4]);i++){await probe.activate(p,i);out.push((await p.locator('.slide.active').innerText()).replace(/\\s+/g,' ').trim())}console.log(JSON.stringify(out));await b.close()})().catch(e=>{console.error(e);process.exit(1)})"""
    env = dict(os.environ, CHROME_CHANNEL=runtime.chrome_channel())
    result = subprocess.run(["node", "-e", script, str(playwright), str(page_probe), str(html_file), str(count)],
                            capture_output=True, text=True, env=env, check=True)
    return json.loads(result.stdout)


def pdf_page_texts(pdf_file, count):
    texts = []
    for index in range(1, count + 1):
        result = subprocess.run(["pdftotext", "-f", str(index), "-l", str(index), "-layout", str(pdf_file), "-"],
                                capture_output=True, text=True, check=True)
        texts.append(re.sub(r"\s+", " ", result.stdout.replace("\f", " ")).strip())
    return texts


def text_similarity(left, right):
    clean = lambda value: collections.Counter(re.findall(r"[\w\u3400-\u9fff]", value.lower()))
    a, b = clean(left), clean(right)
    shared = sum((a & b).values())
    return 1.0 if not a and not b else (2 * shared / (sum(a.values()) + sum(b.values())))


def verify_variant_media(directory, count):
    directory = pathlib.Path(directory)
    manifest = read_json(directory / "cross-media.json")
    html_texts = html_page_texts(directory / "deck.html", count)
    pdf_texts = pdf_page_texts(directory / "deck.pdf", count)
    rendered = render_hashes(directory / "deck.html", count)
    actual_pngs = [sha(directory / f"page-{index:02d}.png") for index in range(1, count + 1)]
    if rendered != actual_pngs or actual_pngs != manifest.get("pngSha256"):
        raise RuntimeError("BENCHMARK_MEDIA_PNG_MISMATCH: packaged PNGs are not fresh renders of this HTML")
    pages = manifest.get("pages") or []
    if len(pages) != count:
        raise RuntimeError("BENCHMARK_MEDIA_TEXT_MISMATCH: page count changed")
    for index, (html_text, pdf_text, recorded) in enumerate(zip(html_texts, pdf_texts, pages), 1):
        similarity = text_similarity(html_text, pdf_text)
        if (sha_text(html_text) != recorded.get("htmlTextSha256") or
                sha_text(pdf_text) != recorded.get("pdfTextSha256") or similarity < 0.93):
            raise RuntimeError(f"BENCHMARK_MEDIA_TEXT_MISMATCH: page {index}")
    if manifest.get("contactInputSha256") != actual_pngs:
        raise RuntimeError("BENCHMARK_CONTACT_MISMATCH: contact sheet inputs changed")
    return manifest


def sha_text(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def write_cross_media(directory, count):
    html_texts = html_page_texts(directory / "deck.html", count)
    pdf_texts = pdf_page_texts(directory / "deck.pdf", count)
    pngs = [sha(directory / f"page-{index:02d}.png") for index in range(1, count + 1)]
    pages = []
    for index, (html_text, pdf_text) in enumerate(zip(html_texts, pdf_texts), 1):
        similarity = text_similarity(html_text, pdf_text)
        if similarity < 0.93:
            raise RuntimeError(f"BENCHMARK_MEDIA_TEXT_MISMATCH: page {index}")
        pages.append({"page": index, "htmlTextSha256": sha_text(html_text),
                      "pdfTextSha256": sha_text(pdf_text), "textSimilarity": round(similarity, 6)})
    value = {"version": 1, "pages": pages, "pngSha256": pngs, "contactInputSha256": pngs}
    write_json(directory / "cross-media.json", value)
    return value


def render_hashes(html_file, count):
    with tempfile.TemporaryDirectory() as tmp:
        tmp = pathlib.Path(tmp)
        node = tmp / "verify.cjs"
        playwright = runtime.engine_dir("report-forge", skill_dir=ROOT / "out-deck") / "node_modules" / "playwright"
        page_probe = runtime.engine_dir("report-forge", skill_dir=ROOT / "out-deck") / "scripts" / "page_probe.cjs"
        node.write_text("""const {chromium}=require(process.argv[2]),probe=require(process.argv[3]),path=require('path'),{pathToFileURL}=require('url');(async()=>{const b=await chromium.launch({channel:process.env.CHROME_CHANNEL||'chrome',headless:true});const p=await b.newPage({viewport:{width:1400,height:820}});await p.goto(pathToFileURL(process.argv[4]).href,{waitUntil:'networkidle'});await p.evaluate(()=>window.deckReady||document.fonts.ready);const n=Number(process.argv[6]);for(let i=0;i<n;i++){await probe.activate(p,i);await p.locator('.slide.active').screenshot({path:path.join(process.argv[5],`page-${String(i+1).padStart(2,'0')}.png`)});}await b.close()})().catch(e=>{console.error(e);process.exit(1)})""", encoding="utf-8")
        env = dict(os.environ, CHROME_CHANNEL=runtime.chrome_channel())
        subprocess.run(["node", str(node), str(playwright), str(page_probe), str(html_file), str(tmp), str(count)],
                       check=True, env=env)
        return [sha(tmp / f"page-{index:02d}.png") for index in range(1, count + 1)]


def inspect_evidence_geometry(html_file):
    playwright = runtime.engine_dir("report-forge", skill_dir=ROOT / "out-deck") / "node_modules" / "playwright"
    page_probe = runtime.engine_dir("report-forge", skill_dir=ROOT / "out-deck") / "scripts" / "page_probe.cjs"
    script = r"""const {chromium}=require(process.argv[1]),probe=require(process.argv[2]),{pathToFileURL}=require('url');(async()=>{const b=await chromium.launch({channel:process.env.CHROME_CHANNEL||'chrome',headless:true});const p=await b.newPage({viewport:{width:1400,height:820}});await p.goto(pathToFileURL(process.argv[3]).href,{waitUntil:'networkidle'});await p.evaluate(()=>window.deckReady||document.fonts.ready);const out=[];for(const i of [1,2]){await probe.activate(p,i);out.push(await p.locator('.slide.active').evaluate(s=>{const body=s.querySelector('.slide__body').getBoundingClientRect(),panels=[...s.querySelectorAll('[data-panel-id]')].map(e=>{const r=e.getBoundingClientRect(),cs=getComputedStyle(e),text=[...e.querySelectorAll('p')];return {w:r.width/body.width,h:r.height/body.height,bottom:(body.bottom-r.bottom)/body.height,border:parseFloat(cs.borderTopWidth)||0,bg:cs.backgroundColor,textMin:text.length?Math.min(...text.map(x=>parseFloat(getComputedStyle(x).fontSize))):null,textUse:text.reduce((n,x)=>n+x.getBoundingClientRect().height,0)/r.height}}),k=s.querySelector('.kpi-card'),ks=k?getComputedStyle(k):null,src=s.querySelector('.evidence-source,.mature-source');return {panels,periods:[...s.querySelectorAll('.chart-label,svg text')].map(e=>e.textContent.trim()).filter(x=>/^(19|20)\d{2}$/.test(x)),pills:s.querySelectorAll('.metric-strip span').length,source:src?parseFloat(getComputedStyle(src).fontSize):0,limitations:[...s.querySelectorAll('.limitation,[data-content-key^="limitation:"]')].map(e=>+getComputedStyle(e).fontSize.replace('px','')),kpi:k?{border:parseFloat(ks.borderTopWidth)||0,bg:ks.backgroundColor}:null}}));}console.log(JSON.stringify(out));await b.close()})().catch(e=>{console.error(e);process.exit(1)})"""
    env = dict(os.environ, CHROME_CHANNEL=runtime.chrome_channel())
    result = subprocess.run(["node", "-e", script, str(playwright), str(page_probe), str(html_file)], capture_output=True, text=True, env=env, check=True)
    return json.loads(result.stdout)


def sanitize_reviewer_html(source, destination, expected_screens):
    """Remove implementation identity tokens without changing rendered pixels."""
    text = pathlib.Path(source).read_text(encoding="utf-8")
    sanitized = re.sub(r"(?i)allen-", "review-", text)
    pathlib.Path(destination).write_text(sanitized, encoding="utf-8")
    if render_hashes(destination, len(expected_screens)) != [sha(path) for path in expected_screens]:
        raise RuntimeError("sanitized reviewer HTML changed rendered pixels")


def build(output):
    output = validate_output(output)
    config = read_json(ROOT / "out-deck/benchmarks/semantic-benchmark.json")
    author = config["referenceAuthor"]
    for key in ("html", "css"):
        if sha(ROOT / author[key]) != author[f"{key}Sha256"]:
            raise RuntimeError(f"locked reference author {key} changed")
    with tempfile.TemporaryDirectory() as tmp:
        source_task = pathlib.Path(tmp) / "source-task"
        F.make_storyline_package(source_task)
        if task_input_digest(source_task) != config["materializedInputSha256"]:
            raise RuntimeError("materialized benchmark input changed")
        env = dict(os.environ, ALLEN_RUNTIME=str(runtime.runtime_root(skill_dir=ROOT / "out-deck")), ALLEN_REQUIRE_TOOLS="1")
        def cli(*args):
            result = subprocess.run([sys.executable, str(ROOT / "out-deck/scripts/out_deck.py"), *map(str, args)],
                                    cwd=ROOT, env=env, capture_output=True, text=True)
            if result.returncode:
                raise RuntimeError(result.stdout + result.stderr)

        def prepare(identity):
            task = pathlib.Path(tmp) / f"{identity}-task"
            shutil.copytree(source_task, task)
            cli("init", task)
            work = out_deck.forge_dir(task)
            for item, requirement in (("chart-plan", "chart-diversity"), ("layout-plan", "layout-diversity"), ("module-fill-plan", "module-fill")):
                evidence = synthetic.planning(work, item, requirement)
                cli("plan", task, item, evidence, "--reviewer", "benchmark planning reviewer",
                    "--basis", "accepted against locked blueprint")
            cli("step", task, "ready")
            cli("step", task, "compile")
            if identity.startswith("candidate"):
                composition = allen_compose.compose(work)
            else:
                parts = [work / "bookend-cover.html", ROOT / author["html"],
                         work / "bookend-references.html", work / "bookend-back.html"]
                (work / "pages.html").write_text("\n".join(path.read_text(encoding="utf-8") for path in parts), encoding="utf-8")
                shutil.copy2(ROOT / author["css"], work / "page.css")
                composition = None
            cli("step", task, "assemble")
            cli("step", task, "smoke")
            refs = read_json(work / "execution-plan.json")["productionRefs"]
            smoke = read_json(work / ".allen/runs.json")["smoke"]
            cli("plan", task, "representatives", synthetic.representatives(work, smoke),
                "--reviewer", "benchmark visual reviewer", "--basis", "accepted from actual smoke screenshots")
            assembled = work / refs["assemble"]["files"]["html"]["record"]
            cli("plan", task, "production", synthetic.production(work, assembled),
                "--reviewer", "benchmark production reviewer", "--basis", "accepted assembled artifact")
            cli("step", task, "acceptance")
            refs = read_json(work / "execution-plan.json")["productionRefs"]
            return work, composition, work / refs["qa"]["files"]["audit"]["record"]

        candidate_work, candidate, candidate_audit = prepare("candidate")
        original_audit = read_json(candidate_audit)
        geometry = inspect_evidence_geometry(pathlib.Path(original_audit["htmlArtifact"]["path"]))
        trend, comparison = geometry
        if not (0.58 <= trend["panels"][0]["w"] <= 0.62 and 0.38 <= trend["panels"][1]["w"] <= 0.42):
            raise RuntimeError(f"trend evidence geometry failed: {trend}")
        if trend["periods"] != ["2024", "2025"] or trend["pills"] or trend["source"] < 13 or min(trend["limitations"] or [0]) < 13:
            raise RuntimeError(f"trend readability failed: {trend}")
        if any(panel["border"] > 1 for panel in trend["panels"]) or trend["panels"][1]["textMin"] < 14 or trend["panels"][1]["textUse"] < 0.15:
            raise RuntimeError(f"trend editorial panel failed: {trend}")
        if not (0.38 <= comparison["panels"][0]["w"] <= 0.42 and 0.58 <= comparison["panels"][1]["w"] <= 0.62):
            raise RuntimeError(f"comparison evidence geometry failed: {comparison}")
        if comparison["panels"][1]["bottom"] > 0.05 or comparison["pills"] or comparison["source"] < 13:
            raise RuntimeError(f"comparison functional whitespace failed: {comparison}")
        if comparison["kpi"]["border"]:
            raise RuntimeError(f"comparison KPI card styling failed: {comparison}")
        mutation_work, _, mutation_audit = prepare("candidate-mutation")
        mutation_task = mutation_work.parents[1]
        layout_file = mutation_work / "obs/layout-plan.json"
        layout_doc = read_json(layout_file)
        layout_doc["layoutDecisions"][0]["reason"] = "benchmark visible layout mutation"
        write_json(layout_file, layout_doc)
        cli("plan", mutation_task, "layout-plan", layout_file, "--reviewer", "benchmark mutation reviewer",
            "--basis", "verify visible plan effect")
        module_file = mutation_work / "obs/module-fill-plan.json"
        module_doc = read_json(module_file)
        module_doc["modulePlans"][0]["regions"][0]["whitespace"] = "保留重点留白"
        module_doc["modulePlans"][0]["regions"][0]["layout"] = "居中放置"
        write_json(module_file, module_doc)
        cli("plan", mutation_task, "module-fill-plan", module_file, "--reviewer", "benchmark mutation reviewer",
            "--basis", "verify visible module effect")
        allen_compose.compose(mutation_work)
        cli("step", mutation_task, "assemble")
        mutation_original_audit = read_json(mutation_audit)
        before_hashes = [sha(mutation_audit.parent / row["screenshot"]) for row in mutation_original_audit["rows"]]
        changed_refs = read_json(mutation_work / "execution-plan.json")["productionRefs"]
        changed_html = mutation_work / changed_refs["assemble"]["files"]["html"]["record"]
        after_hashes = render_hashes(changed_html, len(original_audit["rows"]))
        changed_pages = [index + 1 for index, pair in enumerate(zip(before_hashes, after_hashes)) if pair[0] != pair[1]]
        if changed_pages != [2]:
            raise RuntimeError(f"plan mutation changed unexpected pages: {changed_pages}")
        reference_work, _, reference_audit = prepare("reference")
        reference_geometry = inspect_evidence_geometry(pathlib.Path(read_json(reference_audit)["htmlArtifact"]["path"]))
        for candidate_page, reference_page in zip(geometry, reference_geometry):
            for candidate_panel, reference_panel in zip(candidate_page["panels"], reference_page["panels"]):
                if abs(candidate_panel["w"] - reference_panel["w"]) > 0.02 or abs(candidate_panel["h"] - reference_panel["h"]) > 0.05:
                    raise RuntimeError(f"candidate geometry diverges from locked reference: {candidate_page} / {reference_page}")
        if geometry[1]["kpi"] != reference_geometry[1]["kpi"]:
            raise RuntimeError("candidate KPI styling diverges from locked reference")
        digest = sha(candidate_work / "deck-blueprint.json")
        if digest != sha(reference_work / "deck-blueprint.json"):
            raise RuntimeError("benchmark variants did not receive the same blueprint")
        labels = ["Cinder", "Willow"]
        mapping = {labels[0]: "candidate", labels[1]: "reference"} if int(digest[0], 16) % 2 == 0 else {labels[0]: "reference", labels[1]: "candidate"}
        variants = {}
        with managed_staging(output) as staging:
            for label, identity in mapping.items():
                directory = staging / label; directory.mkdir()
                work, audit_file = ((candidate_work, candidate_audit) if identity == "candidate" else (reference_work, reference_audit))
                audit = read_json(audit_file)
                if audit.get("geometryStatus") != "PASS" or audit.get("errors"):
                    raise RuntimeError(f"{identity} QA failed: {audit.get('errors')}")
                html_file = pathlib.Path(audit["htmlArtifact"]["path"])
                base = audit_file.parent
                pdf = pathlib.Path(audit["pdfArtifact"]["path"])
                shutil.copy2(pdf, directory / "deck.pdf")
                for index, row in enumerate(audit["rows"], 1):
                    shutil.copy2(base / row["screenshot"], directory / f"page-{index:02d}.png")
                expected_screens = [directory / f"page-{index:02d}.png" for index in range(1, len(audit["rows"]) + 1)]
                sanitize_reviewer_html(html_file, directory / "deck.html", expected_screens)
                write_cross_media(directory, len(audit["rows"]))
                contact_sheet(directory, len(audit["rows"]))
                verify_variant_media(directory, len(audit["rows"]))
                qa_status = {"acceptance": audit["acceptance"]["complete"], "errors": len(audit["errors"]),
                             "geometry": audit["geometryStatus"], "htmlPages": audit["pages"],
                             "pdfPages": audit["pdfPages"], "tier": audit["tier"]}
                write_json(directory / "qa-status.json", qa_status)
                variants[label] = {"pageCount": len(audit["rows"]), "qa": qa_status,
                                   "files": {p.name: sha(p) for p in sorted(directory.iterdir()) if p.is_file()}}
            packet = {"version": 1, "inputSha256": config["materializedInputSha256"], "blueprintSha256": digest,
                      "labels": labels, "pageCount": len(candidate["pages"]), "variants": variants}
            write_json(staging / "anonymous-manifest.json", packet)
        label_key = "-".join(label.lower() for label in labels)
        mapping_file = pathlib.Path(tempfile.gettempdir()) / f"allen-deck-benchmark-map-{label_key}-{digest[:12]}.json"
        write_json(mapping_file, {"identities": mapping, "releaseEvidence": {
            "candidateStrategy": config["candidateStrategy"], "referenceStrategy": config["referenceStrategy"],
            "referenceProvenance": author, "compositionContract": candidate,
            "reviewerSanitization": {"pages": len(candidate["pages"]), "pixelIdentical": True},
            "planMutation": {"changedPages": changed_pages, "unchangedPages": [1, 3, 4, 5]},
            "evidenceGeometry": geometry, "referenceGeometry": reference_geometry}})
        return packet, mapping_file


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--output", default=str(ROOT / "out-deck/build/visual-benchmark-final")); args = parser.parse_args()
    packet, mapping = build(pathlib.Path(args.output).resolve())
    print(json.dumps({"packet": str(pathlib.Path(args.output).resolve()), "mapping": str(mapping), "manifest": packet}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
