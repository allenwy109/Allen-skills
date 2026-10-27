#!/usr/bin/env python3
"""Build a reproducible, blind same-input deck A/B review packet."""
import argparse
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


def contact_sheet(out_dir, count):
    node = out_dir / "contact.cjs"
    playwright = runtime.engine_dir("report-forge", skill_dir=ROOT / "out-deck") / "node_modules" / "playwright"
    node.write_text("""const {chromium}=require(process.argv[2]),path=require('path'),fs=require('fs'),{pathToFileURL}=require('url');(async()=>{const b=await chromium.launch({headless:true});const p=await b.newPage({viewport:{width:1280,height:720},deviceScaleFactor:1});const dir=process.argv[3],n=Number(process.argv[4]),html=path.join(dir,'contact.html');fs.writeFileSync(html,'<style>body{margin:20px;background:#ddd;display:grid;grid-template-columns:repeat(3,384px);gap:12px}img{width:384px}</style>'+[...Array(n)].map((_,i)=>`<img src="${`page-${String(i+1).padStart(2,'0')}.png`}">`).join(''));await p.goto(pathToFileURL(html).href);await p.waitForLoadState('load');const loaded=await p.locator('img').evaluateAll(xs=>xs.every(x=>x.complete&&x.naturalWidth>0));if(!loaded)throw Error('contact sheet images did not load');await p.screenshot({path:path.join(dir,'contact-sheet.png'),fullPage:true});fs.unlinkSync(html);await b.close()})().catch(e=>{console.error(e);process.exit(1)})""", encoding="utf-8")
    subprocess.run(["node", str(node), str(playwright), str(out_dir), str(count)], check=True)
    node.unlink()


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
            if identity == "candidate":
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
        original_base = candidate_audit.parent
        layout_file = candidate_work / "obs/layout-plan.json"
        layout_doc = read_json(layout_file)
        layout_doc["layoutDecisions"][0]["layout"] = "L04"
        layout_doc["layoutDecisions"][0]["reason"] = "benchmark visible layout mutation"
        write_json(layout_file, layout_doc)
        cli("plan", candidate_work.parents[1], "layout-plan", layout_file, "--reviewer", "benchmark mutation reviewer",
            "--basis", "verify visible plan effect")
        module_file = candidate_work / "obs/module-fill-plan.json"
        module_doc = read_json(module_file)
        module_doc["modulePlans"][0]["regions"][0]["whitespace"] = "保留重点留白"
        module_doc["modulePlans"][0]["regions"][0]["layout"] = "居中放置"
        write_json(module_file, module_doc)
        cli("plan", candidate_work.parents[1], "module-fill-plan", module_file, "--reviewer", "benchmark mutation reviewer",
            "--basis", "verify visible module effect")
        allen_compose.compose(candidate_work)
        cli("step", candidate_work.parents[1], "assemble")
        before_hashes = [sha(original_base / row["screenshot"]) for row in original_audit["rows"]]
        changed_refs = read_json(candidate_work / "execution-plan.json")["productionRefs"]
        changed_html = candidate_work / changed_refs["assemble"]["files"]["html"]["record"]
        after_hashes = render_hashes(changed_html, len(original_audit["rows"]))
        changed_pages = [index + 1 for index, pair in enumerate(zip(before_hashes, after_hashes)) if pair[0] != pair[1]]
        if changed_pages != [2]:
            raise RuntimeError(f"plan mutation changed unexpected pages: {changed_pages}")
        reference_work, _, reference_audit = prepare("reference")
        digest = sha(candidate_work / "deck-blueprint.json")
        if digest != sha(reference_work / "deck-blueprint.json"):
            raise RuntimeError("benchmark variants did not receive the same blueprint")
        reset_output(output)
        labels = ["Cobalt", "Saffron"]
        mapping = {labels[0]: "candidate", labels[1]: "reference"} if int(digest[0], 16) % 2 == 0 else {labels[0]: "reference", labels[1]: "candidate"}
        variants = {}
        for label, identity in mapping.items():
            directory = output / label; directory.mkdir()
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
            contact_sheet(directory, len(audit["rows"]))
            qa_status = {"acceptance": audit["acceptance"]["complete"], "errors": len(audit["errors"]),
                         "geometry": audit["geometryStatus"], "htmlPages": audit["pages"],
                         "pdfPages": audit["pdfPages"], "tier": audit["tier"]}
            write_json(directory / "qa-status.json", qa_status)
            variants[label] = {"pageCount": len(audit["rows"]), "qa": qa_status,
                               "files": {p.name: sha(p) for p in sorted(directory.iterdir()) if p.is_file()}}
        packet = {"version": 1, "inputSha256": config["materializedInputSha256"], "blueprintSha256": digest,
                  "labels": labels, "pageCount": len(candidate["pages"]), "variants": variants}
        write_json(output / "anonymous-manifest.json", packet)
        label_key = "-".join(label.lower() for label in labels)
        mapping_file = pathlib.Path(tempfile.gettempdir()) / f"allen-deck-benchmark-map-{label_key}-{digest[:12]}.json"
        write_json(mapping_file, {"identities": mapping, "releaseEvidence": {
            "candidateStrategy": config["candidateStrategy"], "referenceStrategy": config["referenceStrategy"],
            "referenceProvenance": author, "compositionContract": candidate,
            "reviewerSanitization": {"pages": len(candidate["pages"]), "pixelIdentical": True},
            "planMutation": {"changedPages": changed_pages, "unchangedPages": [1, 3, 4, 5]}}})
        return packet, mapping_file


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--output", default=str(ROOT / "out-deck/build/visual-benchmark-v2")); args = parser.parse_args()
    packet, mapping = build(pathlib.Path(args.output).resolve())
    print(json.dumps({"packet": str(pathlib.Path(args.output).resolve()), "mapping": str(mapping), "manifest": packet}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
