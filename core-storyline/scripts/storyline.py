#!/usr/bin/env python3
"""故事线工具（设计 §5.3）。所有文件在 <任务>/07_storyline/，卡片真源是 <任务>/03_evidence/ledger/cards.jsonl。

子命令：
  cards   从证据账渲染 02_info_cards.md（卡片、主题聚类、A 级清单、冲突清单、术语口径对照）；不要手改这个文件
  clean   由 04_manuscript.md 机械生成 04_manuscript_clean.md：只删追溯标注〔…〕，保留推断标注和【待补充】
  sync    由 06_slides.md 同步 slides.json 的文字字段（页面类型、行动标题、章节、正文、讲者备注、来源、追溯）
          和 sidecar.json 的讲者备注、备用页；引擎字段（page_role、panels 等）不动
  impact  一张卡改了会影响哪些段落、页面和报告页
  check   机器检查（--stage 0–6 只查到该阶段；--json；--titles 只列行动标题；--no-numbers 跳过数字检查）

退出码：check 有错误时为 1（警告不影响）；其余子命令出错为 1，参数或环境错误为 2。
"""
import argparse
import json
import os
import pathlib
import re
import sys
from decimal import ROUND_HALF_UP, Decimal

SKILL_DIR = pathlib.Path(__file__).resolve().parents[1]


def _bootstrap():
    for c in (os.environ.get("ALLEN_RUNTIME"), SKILL_DIR.parent / "_allen-runtime", SKILL_DIR.parent):
        if c and (pathlib.Path(c) / "tools" / "lib" / "runtime.py").is_file():
            sys.path.insert(0, str(pathlib.Path(c)))
            return
    raise SystemExit("找不到运行时（tools/lib），请先运行 ./install.sh")


_bootstrap()
from tools.lib import metrics as M  # noqa: E402
from tools.lib import schema_check  # noqa: E402
from tools.lib.ledger import Ledger  # noqa: E402

SLIDES_SCHEMA = schema_check.load("slides.schema.json")
LEDGER_SCHEMA = schema_check.load("ledger.schema.json")
PAGE_TYPE = {v: k for k, v in SLIDES_SCHEMA["enums"]["page_type"]["labels"].items()}
STORY_MODE = SLIDES_SCHEMA["enums"]["story_mode"]
CARD_TYPE = LEDGER_SCHEMA["enums"]["card_type"]["labels"]
CONFIDENCE = LEDGER_SCHEMA["enums"]["confidence"]["labels"]
NATURE_BY_KIND = {"fact": "事实", "data": "事实", "estimate": "推断", "forecast": "推断", "judgment": "推断", "recommendation": "推断",
                  "third_party_view": "观点", "assumption": "假设"}
NATURE = LEDGER_SCHEMA["enums"]["card_nature"]["labels"]

# 研究类型 → arc 与必备章节（设计 §5.3 对照表）。所有类型都要有"方法与局限"。
MODE_RULES = {
    "problem_to_solution": ("problem-to-fix", []),
    "option_comparison": ("opportunity-to-choice", ["维持现状"]),
    "request_approval": ("opportunity-to-choice", ["不批的后果"]),
    "opportunity": ("opportunity-to-choice", ["止损线"]),
    "industry_research": ("evidence-to-view", ["分歧与不确定性", "未解问题"]),
    "company_research": ("evidence-to-view", ["风险与未知", "补齐路径"]),
    "diligence_conclusion": ("uncertainty-to-bet", ["风险与红旗", "补齐路径"]),
    "progress_report": ("other", ["请求"]),
    "retrospective": ("other", ["要改的机制"]),
}
STAGE_FILES = [("00_story-brief.md",), ("01_materials_index.md",), ("02_info_cards.md",), ("03_storyline.md",),
               ("04_manuscript.md", "04_manuscript_clean.md"), ("05_storyboard.md", "06_slides.md", "slides.json", "sidecar.json"),
               ("07_audit_report.md",)]
BRIEF_ITEMS = ("受众", "目的", "场景", "语言风格", "保密", "外部知识", "验收标准")
JUDGMENT = ("推断", "建议", "假设", "估算", "测算", "预测", "目标", "预计", "拟", "计划", "上限", "下限", "不超过", "不低于", "至少", "至多")
CLICHES = ("赋能", "抓手", "闭环", "打通", "拉通", "颗粒度", "沉淀", "组合拳", "全方位", "多维度", "深度融合", "持续发力", "助力", "痛点",
           "显著", "大幅", "有所", "进一步", "极大", "业内普遍认为", "据了解", "众所周知")
PLACED_FIELDS = ("正文", "可视化建议", "讲者备注")

CARD_ID = re.compile(r"card-\d{4,}")
IDS = re.compile(r"\b(?:[A-Z]{1,4}-\d{3,}|(?:cl|m|ev|card)-\d{4,}|[ABD-Z]\d{3,4})\b")   # 主体、主张、证据、来源等编号不当数字
CITE = re.compile(r"〔([^〔〕]*)〕")
INFER = re.compile(r"[（(]推断[｜|][^）)]*[）)]")
BRACKET = re.compile(r"【[^】]*】")
UNITS = sorted(["万亿元", "亿元", "万元", "千元", "元/平方米", "元", "亿美元", "万美元", "美元", "万人", "人", "万台", "台", "万吨", "吨", "家", "个",
                "项", "次", "倍", "个月", "小时", "分钟", "天", "平方米", "公里", "万", "亿", "%", "‰", "bp", "pp", "个百分点",
                "USD", "RMB", "CNY", "bn", "mn", "GW", "MW", "kWh", "x"], key=len, reverse=True)
NUM = re.compile(r"(?<![\w.])(-?\d[\d,]*(?:\.\d+)?)\s*(" + "|".join(re.escape(u) for u in UNITS) + r")?")
MAGNITUDE = (("万亿", 1e12), ("亿", 1e8), ("万", 1e4), ("千", 1e3))
FULLWIDTH = str.maketrans("０１２３４５６７８９％．－−", "0123456789%.--")


def story(task):
    return pathlib.Path(task) / "07_storyline"


def read(path):
    p = pathlib.Path(path)
    return p.read_text(encoding="utf-8") if p.is_file() else None


def ledger(task):
    led = Ledger(task)
    return led, {n: led.read(n) for n in ("cards", "claims", "metrics", "sources", "conflicts")}


# ---------- 卡片视图 ----------

def card_nature(card, claims):
    c = claims.get(card.get("claim_id"))
    if c:
        return NATURE_BY_KIND[c["kind"]], CONFIDENCE.get(c.get("confidence"), "未知"), c.get("confidence_reason") or "", f"（取自主张 {c['id']}）"
    return NATURE.get(card.get("nature"), "未填"), CONFIDENCE.get(card.get("confidence"), "未填"), card.get("confidence_reason") or "", ""


def render_cards(task):
    _, data = ledger(task)
    cards, claims = data["cards"], {c["id"]: c for c in data["claims"]}
    out = ["# 信息卡片", "", "> 由 `storyline.py cards` 从证据账生成，不要手改；改卡片请改 03_evidence/ledger/cards.jsonl 后重新生成。", ""]
    topics = {}
    for c in cards:
        topics.setdefault(c["topic"], []).append(c)
    out += ["## 主题聚类", "", "| 主题 | 卡片数 | A 级卡片 |", "|---|---|---|"]
    out += [f"| {t} | {len(cs)} | {'、'.join(c['id'] for c in cs if c['value_tier'] == 'A') or '—'} |" for t, cs in topics.items()]
    out += ["", "## A 级卡片清单", ""]
    out += [f"- {c['id']}：{c['content']}" for c in cards if c["value_tier"] == "A"] or ["- 无"]
    out += ["", "## 卡片", ""]
    for c in cards:
        nature, conf, reason, note = card_nature(c, claims)
        src = "；".join(f"{r['source_id']} {r['locator']}" for r in c.get("source_refs") or [])
        if c.get("derived_from"):
            src = "派生自 " + "、".join(c["derived_from"]) + (f"；{src}" if src else "")
        out += [f"### {c['id']}", f"- 类型：{CARD_TYPE[c['type']]}", f"- 内容：{c['content']}", f"- 含义：{c.get('meaning') or ''}",
                f"- 来源：{src or '—'}", f"- 性质：{nature}{note}", f"- 可信度：{conf} ｜ 依据：{reason or '—'}", f"- 价值：{c['value_tier']}",
                f"- 主题：{c['topic']}"]
        if c.get("claim_id"):
            out.append(f"- 主张：{c['claim_id']}")
        for k, label in (("external_supplement", "外部补充"), ("note", "备注")):
            if c.get(k):
                out.append(f"- {label}：{c[k]}")
        out.append("")
    out += ["## 冲突清单", ""]
    if data["conflicts"]:
        out += ["| 编号 | 主张 | 一方口径 | 另一方口径 | 状态 | 采信理由 |", "|---|---|---|---|---|---|"]
        out += [f"| {x['id']} | {'、'.join(x.get('claim_ids') or [])} | {x.get('left_value_scope') or ''} | {x.get('right_value_scope') or ''} | "
                f"{x.get('status') or ''} | {x.get('accepted_reason') or ''} |" for x in data["conflicts"]]
    else:
        out.append("- 无")
    terms = read(story(task) / "02_terms.md")
    out += ["", "## 术语口径对照", "", terms.strip() if terms else "（尚未建立：在 07_storyline/02_terms.md 里写对照表）", ""]
    return "\n".join(out)


# ---------- 清洁版 ----------

def clean_text(master):
    """删除追溯标注〔…〕（连同前面的空格）；推断标注（推断｜依据 …）和【待补充】【外部补充】保留。"""
    return re.sub(r"[ \t]*〔[^〔〕]*〕", "", master)


# ---------- 逐页稿解析与同步 ----------

PAGE_HEAD = re.compile(r"^##\s*P(\d+)\s*[｜|]\s*(.*?)\s*[｜|]\s*(.+?)\s*$")
FIELD = re.compile(r"^\*\*(.+?)\*\*[：:]\s*(.*)$")


def parse_slides_md(text):
    pages, cur, field = [], None, None
    for line in (text or "").splitlines():
        m = PAGE_HEAD.match(line)
        if m:
            cur = {"page": int(m.group(1)), "section": m.group(2).strip(), "type_label": m.group(3).strip(), "fields": {}}
            pages.append(cur)
            field = None
            continue
        if cur is None:
            continue
        f = FIELD.match(line)
        if f:
            field = f.group(1).strip()
            cur["fields"][field] = f.group(2).strip()
        elif field and line.strip():
            cur["fields"][field] = (cur["fields"][field] + "\n" + line.strip()).strip()
    return pages


def _cards_with_locators(text):
    out = []
    for part in re.split(r"[；;\n]", text or ""):
        ids = CARD_ID.findall(part)
        if ids:
            loc = re.split(r"[｜|]", part, maxsplit=1)
            out.append({"card_id": ids[0], **({"locator": loc[1].strip()} if len(loc) > 1 and loc[1].strip() else {})})
    return out


def synced(task):
    """返回 (新 slides.json, 新 sidecar.json, 问题列表)。"""
    s = story(task)
    pages = parse_slides_md(read(s / "06_slides.md"))
    slides = json.loads(read(s / "slides.json") or "null")
    sidecar = json.loads(read(s / "sidecar.json") or "null") or {"speaker_notes": [], "backup_pages": [], "confirmation_points": []}
    problems = []
    if slides is None:
        return None, None, ["没有 slides.json：先按 06_slides.md 写好每页的引擎字段（page_role、story_beat、panels 等）"]
    by_page = {sl["page"]: sl for sl in slides["slides"]}
    md_pages = {p["page"] for p in pages}
    for page in sorted(set(by_page) - md_pages):
        problems.append(f"slides.json 第 {page} 页在 06_slides.md 里没有")
    notes, backups = [], []
    for p in pages:
        f = p["fields"]
        sl = by_page.get(p["page"])
        if sl is None:
            problems.append(f"06_slides.md 第 {p['page']} 页在 slides.json 里没有：先补上这一页的引擎字段")
            continue
        if p["type_label"] not in PAGE_TYPE:
            problems.append(f"第 {p['page']} 页的页面类型「{p['type_label']}」不在 15+2 种页面类型里")
            continue
        sl["type"] = PAGE_TYPE[p["type_label"]]
        sl["action_title"] = f.get("行动标题", "")
        if p["section"] and p["section"] not in ("—", "-"):
            sl["section"] = p["section"]
        else:
            sl.pop("section", None)
        body = [ln.lstrip("-•* ").strip() for ln in (f.get("正文") or "").splitlines() if ln.strip()]
        if body:
            sl["body"] = [{"text": clean_text(b), **({"card_ids": CARD_ID.findall(b)} if CARD_ID.search(b) else {})} for b in body]
        else:
            sl.pop("body", None)
        if f.get("讲者备注"):
            sl["notes"] = clean_text(f["讲者备注"])
        else:
            sl.pop("notes", None)
        sources = _cards_with_locators(f.get("来源"))
        if sources:
            sl["sources"] = sources
        trace = f.get("追溯") or ""
        if trace:
            head = CARD_ID.split(trace)[0].strip(" ；;、,")
            sl["traceback"] = {**({"manuscript_section": head} if head else {}), "card_ids": CARD_ID.findall(trace)}
        if f.get("讲者备注"):
            notes.append({"page": p["page"], "text": clean_text(f["讲者备注"])})
        if sl["type"] == "backup":
            item = {"page": p["page"], "question": f.get("行动标题", ""), "trigger": f.get("触发", ""), "return_path": f.get("拉回", "")}
            ids = [x["card_id"] for x in sources]
            if ids:
                item["card_ids"] = ids
            if not item["trigger"] or not item["return_path"]:
                problems.append(f"第 {p['page']} 页是备用页，要写「触发」（什么情况下翻到）和「拉回」（答完怎么回到主线）")
            backups.append(item)
    sidecar = {"speaker_notes": notes, "backup_pages": backups, "confirmation_points": sidecar.get("confirmation_points") or []}
    return slides, sidecar, problems


# ---------- 数字 ----------

def _decimals(raw):
    return len(raw.split(".")[1]) if "." in raw else 0


def _split_unit(unit):
    unit = unit or ""
    for prefix, mag in MAGNITUDE:
        if unit.startswith(prefix) and unit not in ("个月",):
            return unit[len(prefix):], mag
    return unit, 1.0


def numbers_in(text, cited=False):
    """返回 [(起点, 数值文本, 单位, 是否像数据)]；年份、月日、序号除外。"""
    t = text.translate(FULLWIDTH)
    out = []
    for m in NUM.finditer(t):
        raw, unit = m.group(1).replace(",", ""), m.group(2) or ""
        if raw in ("-", ""):
            continue
        after = t[m.end():m.end() + 2]
        before = t[max(0, m.start() - 1):m.start()]
        intpart = raw.lstrip("-").split(".")[0]
        if re.fullmatch(r"(19|20|21)\d\d", raw) and "," not in m.group(1) and unit in ("", "年"):
            continue                                         # 年份
        if not unit and (after[:1] in ("月", "日", "号") or after[:2] in ("季度",) or after[:1] == "季" or before == "第"):
            continue                                         # 月日、季度、序号
        if unit in ("个", "次", "天") and before == "第":
            continue
        datalike = bool(unit) or "." in raw or len(intpart) >= 4 or cited
        out.append((m.start(), raw, unit, datalike))
    return out


def _round(v, d):
    return Decimal(repr(v)).quantize(Decimal(1).scaleb(-d), rounding=ROUND_HALF_UP)


def same_number(a_raw, a_unit, b_raw, b_unit):
    """a 是稿件里的数，b 是事实库里的数。符号不同不算相同；量级换算只在两边都写了单位时做。"""
    a, b = float(a_raw), float(b_raw)
    if (a < 0) != (b < 0):
        return False                                         # 符号翻转
    if not a_unit or not b_unit:
        d = min(_decimals(a_raw), _decimals(b_raw))
        return _round(a, d) == _round(b, d)
    ua, ma = _split_unit(a_unit)
    ub, mb = _split_unit(b_unit)
    if ua != ub:
        return False
    if ma == mb:
        d = min(_decimals(a_raw), _decimals(b_raw))
        return _round(a, d) == _round(b, d)
    d = _decimals(a_raw)                                     # 换算后按稿件的精度比较
    return _round(a, d) == _round(b * mb / ma, d)


def library(data):
    """事实库：卡片"内容"里的数字，加上卡片所关联主张的指标显示值。"含义"里的数字不进入。"""
    metrics = {m["id"]: m for m in data["metrics"]}
    claims = {c["id"]: c for c in data["claims"]}
    lib = {}
    for card in data["cards"]:
        nums = [(raw, unit) for _, raw, unit, _ in numbers_in(card["content"], cited=True)]
        claim = claims.get(card.get("claim_id"))
        for mid in (claim or {}).get("metric_refs") or []:
            try:
                nums.append((M.display(M.evaluate(metrics, mid), metrics[mid]["decimals"]), metrics[mid]["unit"]))
            except (M.MetricError, KeyError):
                pass
        lib[card["id"]] = nums
    return lib


def check_numbers(text, where, lib, errors, warnings, stats, skip_uncited=False):
    """逐句检查：带引用的句子，数字必须在事实库里，且应在所引卡片里；未引用但有数据的句子提示。"""
    every = [n for nums in lib.values() for n in nums]
    uncited = 0
    for lineno, line in enumerate(text.splitlines(), 1):
        if line.lstrip().startswith(("#", "|", ">")):
            continue
        for sentence in re.split(r"(?<=[。！？])", line):
            cites = CITE.findall(sentence)
            ids = [i for c in cites for i in CARD_ID.findall(c)]
            body = IDS.sub(" ", BRACKET.sub(" ", INFER.sub(" ", CITE.sub(" ", sentence))))
            basis = "依据" in sentence
            for pos, raw, unit, datalike in numbers_in(body, cited=bool(ids)):
                if not datalike:
                    continue
                stats["checked"] += 1
                marker = any(w in body[max(0, pos - 8):pos] for w in JUDGMENT)
                if not ids:
                    if not marker and not skip_uncited:
                        uncited += 1
                        if uncited <= 15:
                            warnings.append(_issue("number-uncited", f"{where} 第 {lineno} 行：{raw}{unit} 没有引用卡片"))
                    continue
                if any(same_number(raw, unit, r, u) for r, u in every):
                    if not any(same_number(raw, unit, r, u) for i in ids for r, u in lib.get(i, [])):
                        warnings.append(_issue("number-mismatch", f"{where} 第 {lineno} 行：{raw}{unit} 不在所引卡片 {'、'.join(ids)} 里"))
                    continue
                if marker and basis:
                    warnings.append(_issue("number-judgment", f"{where} 第 {lineno} 行：{raw}{unit} 不在事实库，按判断类数字处理（已标记并写依据）"))
                    continue
                stats["unknown"] += 1
                some_marker = any(w in body for w in JUDGMENT)
                why = "判断类标记要紧挨数字并写明依据" if some_marker else "事实数字必须来自卡片；推断、建议类数字要加标记并写依据；没有就写【待补充】"
                errors.append(_issue("number-unknown", f"{where} 第 {lineno} 行：{raw}{unit} 不在事实库里（{why}）"))


# ---------- 检查 ----------

def _issue(code, message):
    return {"code": code, "message": message}


def _sections(md):
    """[(标题, 级别, 正文)]。"""
    out, cur = [], ("", 0, [])
    for line in (md or "").splitlines():
        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m:
            out.append((cur[0], cur[1], "\n".join(cur[2])))
            cur = (m.group(2).strip(), len(m.group(1)), [])
        else:
            cur[2].append(line)
    out.append((cur[0], cur[1], "\n".join(cur[2])))
    return out


def _section_text(md, keyword):
    secs = _sections(md)
    for i, (title, level, body) in enumerate(secs):
        if keyword in title:
            parts = [body]
            for t2, l2, b2 in secs[i + 1:]:
                if l2 <= level:
                    break
                parts.append(b2)
            return "\n".join(parts)
    return None


def _story_mode(text):
    m = re.search(r"故事线模式[：:]\s*(\S+)", text or "")
    if not m:
        return None
    word = m.group(1)
    for key, label in STORY_MODE["labels"].items():
        if word in (key, label) or word.startswith(label):
            return key
    return word


def _table_rows(md, header_word):
    rows, header = [], None
    for line in (md or "").splitlines():
        if not line.strip().startswith("|"):
            header = None if not rows else header
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if header is None:
            if header_word in cells:
                header = cells
            continue
        if set("".join(cells)) <= set("-: "):
            continue
        rows.append(dict(zip(header, cells)))
    return rows


def check(task, stage=6, numbers=True):
    s = story(task)
    errors, warnings, info = [], [], {}
    if not s.is_dir():
        return {"target": str(s), "errors": [_issue("dir", f"{s} 不存在")], "warnings": [], "info": {}, "titles": [], "passed": False}
    has_slides = (s / "06_slides.md").is_file() or (s / "05_storyboard.md").is_file()
    mode = "分页" if has_slides else ("内容稿" if (s / "04_manuscript.md").is_file() else "未知")
    info["mode"] = mode
    for st, names in enumerate(STAGE_FILES[:stage + 1]):
        if st == 5 and mode == "内容稿":
            continue
        for name in names:
            if not (s / name).is_file():
                errors.append(_issue("missing-file", f"缺少 {name}（阶段 {st} 的产出）"))
    if (s / "06_slides.md").is_file() and not (s / "05_storyboard.md").is_file():
        errors.append(_issue("missing-file", "有 06_slides.md 但没有 05_storyboard.md：先做故事板和横纵检查再写逐页"))

    led, data = ledger(task)
    cards = data["cards"]
    claims = {c["id"]: c for c in data["claims"]}
    by_id = {c["id"]: c for c in cards}
    for i in led.check():
        if i["level"] == "error":
            errors.append(_issue("ledger", f"证据账 {i['table']}:{i['id']}：{i['message']}"))
    if stage >= 2 and not cards:
        errors.append(_issue("missing-file", "证据账里没有卡片（03_evidence/ledger/cards.jsonl）"))

    # 阶段 0：简报
    brief = read(s / "00_story-brief.md")
    if brief is not None:
        for item in BRIEF_ITEMS:
            if item not in brief:
                errors.append(_issue("brief", f"00_story-brief.md 缺少「{item}」：简报 7 项要齐，没说的推断并标「假设」"))

    # 阶段 1：材料索引
    index = read(s / "01_materials_index.md")
    if index is not None and stage >= 1:
        rows = _table_rows(index, "处理状态")
        if not rows:
            errors.append(_issue("materials", "01_materials_index.md 没有带「处理状态」列的材料清单"))
        ids_in_index = set()
        for r in rows:
            sid = r.get("来源 ID") or r.get("来源ID") or ""
            ids_in_index.add(sid)
            status = r.get("处理状态", "")
            if "未处理" in status:
                errors.append(_issue("materials", f"材料 {sid} 还是「未处理」"))
            if "长" in r.get("体量", "") and not re.search(r"读至|读完|全文", status):
                errors.append(_issue("materials", f"材料 {sid} 是长文档，处理状态要写读到哪（读至…／读完）"))
        known = {x["id"] for x in data["sources"]}
        for sid in sorted(ids_in_index - known - {""}):
            errors.append(_issue("materials", f"材料清单里的 {sid} 不在证据账的来源表里"))
        for x in data["sources"]:
            if x.get("origin") == "user" and x["id"] not in ids_in_index:
                warnings.append(_issue("materials", f"用户材料 {x['id']}（{x['title']}）没有登记在材料清单里"))

    # 阶段 2：卡片
    tiers = {t: sum(c["value_tier"] == t for c in cards) for t in "ABC"}
    info["cards_total"], info["cards_by_tier"] = len(cards), tiers
    info["a_ratio"] = round(tiers["A"] / len(cards), 3) if cards else 0
    if len(cards) >= 20 and tiers["A"] / len(cards) >= 0.35:
        warnings.append(_issue("grade-calibration", f"A 级占 {tiers['A']}/{len(cards)}（≥35%）：判据可能用宽了，按「抽掉会不会改口」重刷，拿不准先判 B"))
    nums = sorted(int(c["id"].split("-")[1]) for c in cards)
    gaps = [n for n in range(nums[0], nums[-1] + 1) if n not in set(nums)] if nums else []
    if gaps:
        warnings.append(_issue("card-id-gap", "卡片编号跳号：" + "、".join(f"card-{n:04d}" for n in gaps[:10]) + "（删除的卡片留空号即可，确认不是漏了）"))
    for c in cards:
        if c.get("derived_from"):
            cl = claims.get(c.get("claim_id"))
            if not cl or cl["kind"] != "estimate" or schema_check.empty(cl.get("calculation")) or cl["calculation"].startswith("不适用"):
                errors.append(_issue("derived-card", f"{c['id']} 是派生卡：要关联一条 kind=estimate、calculation 写明算式的主张"))
    if stage >= 2 and cards:
        current = read(s / "02_info_cards.md")
        if current is not None and current != render_cards(task):
            errors.append(_issue("cards-view", "02_info_cards.md 和证据账不一致：运行 storyline.py cards 重新生成"))
        if not (s / "02_terms.md").is_file():
            warnings.append(_issue("terms", "还没有术语口径对照表（07_storyline/02_terms.md）"))

    # 阶段 3：故事线
    line = read(s / "03_storyline.md")
    mode_key = _story_mode(line)
    if line is not None and stage >= 3:
        for word in ("结构树", "压力测试"):
            if word not in line:
                errors.append(_issue("storyline", f"03_storyline.md 缺少「{word}」"))
        if mode_key not in MODE_RULES:
            errors.append(_issue("storyline", "03_storyline.md 要写「故事线模式：」，取值见设计 §5.3 对照表"))
        side = json.loads(read(s / "sidecar.json") or "null")
        points = [p for p in (side or {}).get("confirmation_points") or [] if p["stage"] == "storyline"]
        if not points or all(p["status"] == "pending" for p in points):
            errors.append(_issue("confirmation", "主线选择还没确认：sidecar.json 的 confirmation_points 要有 stage=storyline 且不是 pending（快速模式写 auto_adopted）"))

    lib = library(data) if cards else {}
    stats = {"checked": 0, "unknown": 0}

    # 阶段 4：内容稿
    master = read(s / "04_manuscript.md")
    if master is not None and stage >= 4:
        if read(s / "04_manuscript_clean.md") not in (None, clean_text(master)):
            errors.append(_issue("clean-drift", "04_manuscript_clean.md 不是由母版机械生成的：运行 storyline.py clean，不要手改清洁版"))
        summary = _section_text(master, "执行摘要")
        if summary is None:
            errors.append(_issue("summary", "04_manuscript.md 没有「执行摘要」一节"))
        else:
            n = len(re.sub(r"\s|[#*>\-|]", "", CITE.sub("", summary)))
            if not 200 <= n <= 400:
                errors.append(_issue("summary", f"执行摘要 {n} 字，要在 200–400 字之间"))
            if "【待补充" in summary:
                errors.append(_issue("summary", "执行摘要里不能出现【待补充】（可以写「证据见第 X 章」）"))
        titles = [t for t, _, _ in _sections(master)]
        required = ["方法与局限"] + (MODE_RULES.get(mode_key, (None, []))[1])
        for word in required:
            if not any(word in t for t in titles):
                errors.append(_issue("chapter", f"04_manuscript.md 缺少「{word}」一节（{STORY_MODE['labels'].get(mode_key, mode_key)}必备）"))
        if numbers:
            body_parts = [(t, b) for t, _, b in _sections(master)]
            for title, body in body_parts:
                skip = any(k in title for k in ("附录", "来源清单", "术语"))
                check_numbers(body, f"04_manuscript.md「{title or '开头'}」", lib, errors, warnings, stats, skip_uncited=skip)
        for word in CLICHES:
            k = clean_text(master).count(word)
            if k:
                warnings.append(_issue("cliche", f"04_manuscript.md 出现「{word}」{k} 次：划掉后话仍成立就删掉，程度词要有数字支撑"))

    # 阶段 5：拆页
    pages = parse_slides_md(read(s / "06_slides.md"))
    titles_out = [{"page": p["page"], "title": p["fields"].get("行动标题", "")} for p in pages]
    info["slide_count"] = len(pages)
    slides_doc = json.loads(read(s / "slides.json") or "null")
    if pages and stage >= 5:
        for p in pages:
            title = p["fields"].get("行动标题", "")
            if not title:
                warnings.append(_issue("titles", f"第 {p['page']} 页解析不到「**行动标题**：」"))
            elif len(title) > 30:
                warnings.append(_issue("title-length", f"第 {p['page']} 页行动标题 {len(title)} 字（建议 ≤30 字；太长通常是两个结论，考虑拆页）"))
            if p["type_label"] not in PAGE_TYPE:
                errors.append(_issue("page-type", f"第 {p['page']} 页页面类型「{p['type_label']}」无效"))
            if numbers:
                text = "\n".join(p["fields"].get(f, "") for f in PLACED_FIELDS)
                check_numbers(text, f"06_slides.md 第 {p['page']} 页", lib, errors, warnings, stats,
                              skip_uncited=False)
        types = [PAGE_TYPE.get(p["type_label"]) for p in pages]
        main = [t for t in types if t not in ("backup", "appendix")]
        closing = [t for t in main if t != "close"]
        if closing and closing[-1] not in ("recommendation", "next_steps"):
            errors.append(_issue("closing", "主 deck 最后一页（封底之前）必须是建议或下一步页"))
        backups = types.count("backup")
        kind = (slides_doc or {}).get("deck", {}).get("kind")
        if backups < 3:
            (errors if kind == "presentation" else warnings).append(
                _issue("backup", f"备用页 {backups} 页：演讲型至少 3 页（用没进主线的 A/B 卡回答预判的追问）"))
        limit = (slides_doc or {}).get("deck", {}).get("page_limit")
        if limit and len(main) > limit:
            errors.append(_issue("page-limit", f"主 deck {len(main)} 页，超过上限 {limit} 页：按合并同级次要页 → 移入备用页 → 进附录处置，不删内容、不缩字号"))
    if slides_doc is not None and stage >= 5:
        for e in schema_check.check_document(SLIDES_SCHEMA, slides_doc, "slides.json"):
            errors.append(_issue("slides-schema", e))
        deck = slides_doc.get("deck", {})
        if deck.get("story_mode") and mode_key and deck["story_mode"] != mode_key:
            errors.append(_issue("story-mode", f"slides.json 的 story_mode={deck['story_mode']} 与 03_storyline.md 的故事线模式不一致"))
        expected = MODE_RULES.get(deck.get("story_mode"), (None,))[0]
        if expected and deck.get("arc") != expected:
            errors.append(_issue("arc", f"{STORY_MODE['labels'].get(deck['story_mode'])}的 arc 应为 {expected}，现在是 {deck.get('arc')}"))
        if deck.get("arc") == "other" and not deck.get("arc_reason"):
            errors.append(_issue("arc", "arc=other 要写 arc_reason"))
        new_slides, new_side, problems = synced(task)
        errors += [_issue("sync", p) for p in problems]
        if new_slides is not None and (new_slides != slides_doc or new_side != json.loads(read(s / "sidecar.json") or "null")):
            errors.append(_issue("sync", "slides.json 或 sidecar.json 和 06_slides.md 不一致：运行 storyline.py sync"))

    # 去向：只认 04 正文和 06 的正文、可视化建议、讲者备注
    placed = set(CARD_ID.findall(master or "")) | {i for p in pages for f in PLACED_FIELDS for i in CARD_ID.findall(p["fields"].get(f, ""))}
    planned = set(CARD_ID.findall(line or ""))
    audited = set(CARD_ID.findall(read(s / "07_audit_report.md") or ""))
    for cid in sorted(placed | planned | audited):
        if cid not in by_id:
            errors.append(_issue("dangling-ref", f"引用了不存在的卡片 {cid}"))
    cov = {"ab_total": 0, "placed": 0, "only_in_audit": 0, "planned_only": 0, "nowhere": 0, "a_total": tiers["A"], "a_placed": 0}
    if stage >= 4:
        for c in cards:
            if c["value_tier"] == "C":
                if c["id"] in placed:
                    errors.append(_issue("c-in-deliverable", f"{c['id']} 是 C 级卡片，不能进入内容稿或页面（真影响决策说明分级错了）"))
                continue
            cov["ab_total"] += 1
            level = errors if c["value_tier"] == "A" else warnings
            if c["id"] in placed:
                cov["placed"] += 1
                cov["a_placed"] += c["value_tier"] == "A"
            elif c["id"] in audited:
                cov["only_in_audit"] += 1
                level.append(_issue("coverage", f"{c['value_tier']} 级 {c['id']} 只在审计报告里登记，没有实际安置"))
            elif c["id"] in planned:
                cov["planned_only"] += 1
                level.append(_issue("coverage", f"{c['value_tier']} 级 {c['id']} 只在故事线里挂名，内容稿和页面里没有"))
            else:
                cov["nowhere"] += 1
                level.append(_issue("coverage", f"{c['value_tier']} 级 {c['id']} 没有去向（{c['content']}）"))
    info["coverage"], info["numbers"] = cov, stats
    return {"target": str(s), "stage": stage, "info": info, "errors": errors, "warnings": warnings, "titles": titles_out,
            "passed": not errors}


# ---------- 影响分析 ----------

def impact(task, cid):
    s = story(task)
    out = {"card": cid, "storyline": [], "manuscript": [], "pages": [], "report_pages": []}
    for key, name in (("storyline", "03_storyline.md"), ("manuscript", "04_manuscript.md")):
        for n, line in enumerate((read(s / name) or "").splitlines(), 1):
            if cid in line:
                out[key].append({"line": n, "text": line.strip()[:80]})
    for p in parse_slides_md(read(s / "06_slides.md")):
        fields = [f for f, v in p["fields"].items() if cid in v]
        if fields:
            out["pages"].append({"page": p["page"], "fields": fields})
    _, data = ledger(task)
    card = next((c for c in data["cards"] if c["id"] == cid), None)
    if card is None:
        raise SystemExit(f"证据账里没有 {cid}")
    slides = json.loads(read(s / "slides.json") or "null")
    if card.get("claim_id") and slides:
        out["claim"] = card["claim_id"]
        out["report_pages"] = [sl["page"] for sl in slides["slides"] if card["claim_id"] in (sl.get("claim_refs") or [])]
    return out


# ---------- 命令行 ----------

def main(argv=None):
    ap = argparse.ArgumentParser(description="故事线工具")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("cards", "clean", "sync"):
        sub.add_parser(name).add_argument("task")
    p = sub.add_parser("impact")
    p.add_argument("task")
    p.add_argument("card")
    p = sub.add_parser("check")
    p.add_argument("task")
    p.add_argument("--stage", type=int, default=6, choices=range(7))
    p.add_argument("--json", action="store_true")
    p.add_argument("--titles", action="store_true")
    p.add_argument("--no-numbers", action="store_true")
    a = ap.parse_args(argv)
    s = story(a.task)
    if a.cmd == "cards":
        s.mkdir(parents=True, exist_ok=True)
        (s / "02_info_cards.md").write_text(render_cards(a.task), encoding="utf-8")
        print(f"已生成 {s / '02_info_cards.md'}")
        return 0
    if a.cmd == "clean":
        master = read(s / "04_manuscript.md")
        if master is None:
            print("没有 04_manuscript.md", file=sys.stderr)
            return 2
        (s / "04_manuscript_clean.md").write_text(clean_text(master), encoding="utf-8")
        print(f"已生成 {s / '04_manuscript_clean.md'}")
        return 0
    if a.cmd == "sync":
        slides, side, problems = synced(a.task)
        for p in problems:
            print(f"- {p}", file=sys.stderr)
        if slides is None:
            return 1
        (s / "slides.json").write_text(json.dumps(slides, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        (s / "sidecar.json").write_text(json.dumps(side, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"已同步 slides.json 和 sidecar.json（{len(slides['slides'])} 页）")
        return 1 if problems else 0
    if a.cmd == "impact":
        print(json.dumps(impact(a.task, a.card), ensure_ascii=False, indent=1))
        return 0
    r = check(a.task, a.stage, not a.no_numbers)
    if a.titles:
        for t in r["titles"]:
            print(f"P{t['page']:02d} {t['title']}")
        return 0
    if a.json:
        print(json.dumps(r, ensure_ascii=False, indent=1))
    else:
        print(f"故事线检查（阶段 0–{a.stage}，{r['info'].get('mode', '未知')}）：错误 {len(r['errors'])} 个，警告 {len(r['warnings'])} 个")
        for e in r["errors"]:
            print(f"[错误] {e['code']}：{e['message']}")
        for w in r["warnings"]:
            print(f"[警告] {w['code']}：{w['message']}")
        print("脚本查不了的：结构是否结论先行、以上统下、MECE；SCQA 是否有效；因果强度和范围词；讲者备注是否可口述——按审计清单人工检查。")
    return 0 if r["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
