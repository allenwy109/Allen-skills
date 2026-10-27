#!/usr/bin/env python3
"""Build a reproducible, blind same-input deck A/B review packet."""
import argparse
import hashlib
import json
import os
import pathlib
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


def sha(path):
    return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    pathlib.Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def contact_sheet(out_dir, count):
    node = out_dir / "contact.cjs"
    playwright = runtime.engine_dir("report-forge", skill_dir=ROOT / "out-deck") / "node_modules" / "playwright"
    node.write_text("""const {chromium}=require(process.argv[2]),path=require('path'),fs=require('fs'),{pathToFileURL}=require('url');(async()=>{const b=await chromium.launch({headless:true});const p=await b.newPage({viewport:{width:1280,height:720},deviceScaleFactor:1});const dir=process.argv[3],n=Number(process.argv[4]),html=path.join(dir,'contact.html');fs.writeFileSync(html,'<style>body{margin:20px;background:#ddd;display:grid;grid-template-columns:repeat(3,384px);gap:12px}img{width:384px}</style>'+[...Array(n)].map((_,i)=>`<img src="${`page-${String(i+1).padStart(2,'0')}.png`}">`).join(''));await p.goto(pathToFileURL(html).href);await p.waitForLoadState('load');const loaded=await p.locator('img').evaluateAll(xs=>xs.every(x=>x.complete&&x.naturalWidth>0));if(!loaded)throw Error('contact sheet images did not load');await p.screenshot({path:path.join(dir,'contact-sheet.png'),fullPage:true});fs.unlinkSync(html);await b.close()})().catch(e=>{console.error(e);process.exit(1)})""", encoding="utf-8")
    subprocess.run(["node", str(node), str(playwright), str(out_dir), str(count)], check=True)
    node.unlink()


def build(output):
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
        reference_work, _, reference_audit = prepare("reference")
        digest = sha(candidate_work / "deck-blueprint.json")
        if digest != sha(reference_work / "deck-blueprint.json"):
            raise RuntimeError("benchmark variants did not receive the same blueprint")
        shutil.rmtree(output, ignore_errors=True); output.mkdir(parents=True)
        labels = ["Atlas", "Juniper"]
        mapping = {labels[0]: "candidate", labels[1]: "reference"} if int(digest[0], 16) % 2 == 0 else {labels[0]: "reference", labels[1]: "candidate"}
        for label, identity in mapping.items():
            directory = output / label; directory.mkdir()
            work, audit_file = ((candidate_work, candidate_audit) if identity == "candidate" else (reference_work, reference_audit))
            audit = read_json(audit_file)
            if audit.get("geometryStatus") != "PASS" or audit.get("errors"):
                raise RuntimeError(f"{identity} QA failed: {audit.get('errors')}")
            html_file = pathlib.Path(audit["htmlArtifact"]["path"])
            shutil.copy2(html_file, directory / "deck.html")
            shutil.copy2(audit_file, directory / "qa-audit.json")
            base = audit_file.parent
            pdf = pathlib.Path(audit["pdfArtifact"]["path"])
            shutil.copy2(pdf, directory / "deck.pdf")
            for index, row in enumerate(audit["rows"], 1):
                shutil.copy2(base / row["screenshot"], directory / f"page-{index:02d}.png")
            contact_sheet(directory, len(audit["rows"]))
        packet = {"version": 1, "inputSha256": config["materializedInputSha256"], "blueprintSha256": digest,
                  "labels": labels, "pageCount": len(candidate["pages"]), "compositionContract": candidate,
                  "referenceProvenance": author,
                  "files": {p.relative_to(output).as_posix(): sha(p) for p in sorted(output.rglob("*")) if p.is_file()}}
        write_json(output / "anonymous-manifest.json", packet)
        mapping_file = pathlib.Path(tempfile.gettempdir()) / f"allen-deck-benchmark-map-{digest[:12]}.json"
        write_json(mapping_file, mapping)
        return packet, mapping_file


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--output", default=str(ROOT / "out-deck/build/visual-benchmark")); args = parser.parse_args()
    packet, mapping = build(pathlib.Path(args.output).resolve())
    print(json.dumps({"packet": str(pathlib.Path(args.output).resolve()), "mapping": str(mapping), "manifest": packet}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
