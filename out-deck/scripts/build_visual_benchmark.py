#!/usr/bin/env python3
"""Build a reproducible, blind same-input deck A/B review packet."""
import argparse
import hashlib
import html
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

import allen_compose  # noqa: E402
from tools.bridge import to_forge  # noqa: E402
from tools.e2e.test_report_outputs import make_case_task, read_json, task_input_digest  # noqa: E402
from tools.lib import runtime  # noqa: E402


def sha(path):
    return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    pathlib.Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def decisions(blueprint):
    chart, layout, modules = [], [], []
    layouts = ("chart-sidebar", "comparison-columns", "process-roadmap", "prose-aside")
    for index, slide in enumerate(s for s in blueprint["slides"] if s["pageRole"] not in ("cover", "close")):
        comp = slide["exhibit"]["semantics"]["composition"]
        anchor = comp["panels"][comp["anchorPanel"]]
        relationship = anchor["selection"]["relationship"]
        form = ("trend-bars" if anchor["form"] == "svg.custom" else "evidence-quote" if anchor["form"] == "html.text"
                else "roadmap" if relationship in ("sequence", "roadmap") else "comparison-matrix")
        chosen_layout = layouts[index % len(layouts)]
        chart.append({"pageId": slide["id"], "form": form, "relationship": relationship, "reason": "锁定关系选择"})
        layout.append({"pageId": slide["id"], "layout": chosen_layout, "readingPath": slide["visual"]["readingPath"],
                       "regions": [r["slot"] for r in slide["visual"]["regions"]], "reason": "锁定布局选择"})
        modules.append({"pageId": slide["id"], "regions": [{"id": r["slot"], "content": "蓝图绑定内容完整呈现",
                          "layout": chosen_layout, "whitespace": "保留来源与收束句安全区"} for r in slide["visual"]["regions"]]})
    return chart, layout, modules


def reference_pages(blueprint):
    claims = {claim["id"]: claim for claim in blueprint.get("claims", [])}
    sources = blueprint.get("sources", {})
    pages = []
    for slide in blueprint["slides"]:
        role = slide["pageRole"]
        if role in ("cover", "close"):
            page_role = "cover" if role == "cover" else "back-cover"
            pages.append(f'<section class="slide ref-bookend" data-page-role="{page_role}"><h1>{html.escape(slide["title"])}</h1><p>{html.escape(slide.get("subtitle", ""))}</p></section>')
            continue
        rows = []
        source_ids = []
        for ref in slide.get("claimRefs", []):
            claim = claims[ref]
            rows.append(f'<tr><td>{html.escape(claim["kind"])}</td><td>{html.escape(claim["statement"])}</td><td>{html.escape(claim.get("limitation", ""))}</td></tr>')
            source_ids.extend(s for s in claim.get("sourceKeys", []) if s not in source_ids)
        source = "；".join(f'{sources[s]["label"]} · {sources[s]["locator"]}' for s in source_ids)
        pages.append(f'<section class="slide ref-body"><h1>{html.escape(slide["title"])}</h1><p>{html.escape(slide.get("subtitle", ""))}</p>'
                     f'<table><thead><tr><th>身份</th><th>证据</th><th>边界</th></tr></thead><tbody>{"".join(rows)}</tbody></table>'
                     f'<footer>{html.escape(source)}</footer></section>')
    if sources:
        items = "".join(f'<li><strong>{html.escape(source["label"])}</strong><span>{html.escape(source["locator"])}</span></li>'
                        for source in sources.values())
        references = f'<section class="slide ref-body" data-page-role="references"><h1>Sources / 来源与定位</h1><ol>{items}</ol></section>'
        pages.insert(max(0, len(pages) - 1), references)
    return "\n".join(pages)


def standalone(pages, css):
    base = ".slide{position:relative;width:1280px;height:720px;box-sizing:border-box;page-break-after:always;overflow:hidden}.slide:last-child{page-break-after:auto}body{margin:0;background:#ddd}.ref-bookend,.ref-body{padding:64px;background:#f7f4ed;font-family:sans-serif}.ref-bookend{display:flex;flex-direction:column;justify-content:center}.ref-bookend h1{font-size:50px}.ref-body h1{font-size:32px}.ref-body table{width:100%;border-collapse:collapse;margin-top:40px;background:white}.ref-body th,.ref-body td{padding:18px;border-bottom:1px solid #ccd4d2;text-align:left}.ref-body footer{position:absolute;bottom:35px;font-size:12px;color:#566}"
    return f"<!doctype html><meta charset='utf-8'><style>{base}\n{css}</style><body>{pages}</body>"


def export(html_file, out_dir):
    node = out_dir / "export.cjs"
    playwright = runtime.engine_dir("report-forge", skill_dir=ROOT / "out-deck") / "node_modules" / "playwright"
    node.write_text("""const {chromium}=require(process.argv[2]),fs=require('fs'),path=require('path');(async()=>{const b=await chromium.launch({headless:true});const p=await b.newPage({viewport:{width:1280,height:720},deviceScaleFactor:1});await p.goto('file://'+path.resolve(process.argv[3]));await p.pdf({path:process.argv[4],width:'13.333in',height:'7.5in',printBackground:true});const slides=p.locator('.slide');for(let i=0;i<await slides.count();i++)await slides.nth(i).screenshot({path:path.join(process.argv[5],`page-${String(i+1).padStart(2,'0')}.png`)});await p.setContent('<style>body{margin:20px;background:#ddd;display:grid;grid-template-columns:repeat(3,384px);gap:12px}img{width:384px}</style>'+[...Array(await slides.count())].map((_,i)=>`<img src="file://${path.join(process.argv[5],`page-${String(i+1).padStart(2,'0')}.png`)}">`).join(''));await p.screenshot({path:path.join(process.argv[5],'contact-sheet.png'),fullPage:true});await b.close()})().catch(e=>{console.error(e);process.exit(1)})""", encoding="utf-8")
    subprocess.run(["node", str(node), str(playwright), str(html_file), str(out_dir / "deck.pdf"), str(out_dir)], check=True)
    node.unlink()


def build(output):
    config = read_json(ROOT / "out-deck/benchmarks/semantic-benchmark.json")
    fixture = ROOT / config["fixture"]
    if sha(fixture) != config["fixtureSha256"]:
        raise RuntimeError("benchmark fixture hash changed")
    case = next(c for c in read_json(ROOT / "tests/report-output-cases.json") if c["input_snapshot"]["path"] == config["fixture"])
    with tempfile.TemporaryDirectory() as tmp:
        task = make_case_task(tmp, case)
        if task_input_digest(task) != config["materializedInputSha256"]:
            raise RuntimeError("materialized benchmark input changed")
        slides = read_json(task / "07_storyline/slides.json")
        sidecar = read_json(task / "07_storyline/sidecar.json")
        blueprint = to_forge.build(task, slides, sidecar, [])["blueprint"]
        work = pathlib.Path(tmp) / "work"; (work / "obs").mkdir(parents=True)
        write_json(work / "deck-blueprint.json", blueprint)
        digest = sha(work / "deck-blueprint.json")
        chart, layout, modules = decisions(blueprint)
        common = {"kind": "planning", "reviewer": "benchmark builder", "basis": "locked same-input benchmark",
                  "alternatives": [{"pageId": s["id"], "considered": "locked", "decision": "locked"} for s in blueprint["slides"]],
                  "files": [{"record": "../deck-blueprint.json", "sha256": digest}]}
        write_json(work / "obs/chart-plan.json", {**common, "chartDecisions": chart})
        write_json(work / "obs/layout-plan.json", {**common, "layoutDecisions": layout})
        write_json(work / "obs/module-fill-plan.json", {**common, "modulePlans": modules})
        candidate = allen_compose.compose(work)
        shutil.rmtree(output, ignore_errors=True); output.mkdir(parents=True)
        candidates = {"candidate": standalone((work / "pages.html").read_text(), (work / "page.css").read_text()),
                      "reference": standalone(reference_pages(blueprint), "")}
        labels = ["Atlas", "Juniper"]
        mapping = {labels[0]: "candidate", labels[1]: "reference"} if int(digest[0], 16) % 2 == 0 else {labels[0]: "reference", labels[1]: "candidate"}
        for label, identity in mapping.items():
            directory = output / label; directory.mkdir()
            html_file = directory / "deck.html"; html_file.write_text(candidates[identity], encoding="utf-8")
            export(html_file, directory)
        packet = {"version": 1, "inputSha256": config["materializedInputSha256"], "blueprintSha256": digest,
                  "labels": labels, "pageCount": len(candidate["pages"]), "compositionContract": candidate,
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
