"""尽调报告内容契约（report-content.json，version 1.2）的校验（设计 §5.2；能力清单 G6、I4–I6 节与 H 节 report_model、
report_media、visual_review 的规则）。只用标准库。

- validate：顶层与章节结构、13 种内容块、11 个解释主题、各图型的真实性约束、图片安全、跨块规则；返回错误、警告和读者覆盖。
- visual_hints：可视化编排提示（只提示，不阻断）。
- after_split：core-storyline 拆页后，用 block_map.json 和 slides.json 复核每个内容块都落到页上、同章规则仍成立。
- manual_errors：22 条人工清单在证据账 reviews 表（type=diligence_manual）里都有记录且通过。

节点数上限（上游关系图最多 6 个节点）随渲染统一到 out-report 而取消（设计 §5.2 优化 9）。
"""
import base64
import hashlib
import pathlib
import re
from decimal import Decimal

TOPICS = ("identity", "history_team", "offering", "customers_markets", "transaction_flow", "operating_model", "revenue_costs",
          "differentiation", "financial_performance", "marketing", "competition")
TOPIC_QUESTIONS = {
    "identity": "这是一家什么公司，研究的是品牌、集团还是法人，三者关系如何",
    "history_team": "何时、由谁、因何创立，哪些团队和变化形成了今天的业务",
    "offering": "具体卖什么，客户得到什么",
    "customers_markets": "谁使用、谁选择、谁付款，在哪、经什么渠道；客户定位和已验证的客户分布有何区别",
    "transaction_flow": "一笔代表性业务如何从需求、下单走到交付、收款、售后",
    "operating_model": "公司自己做什么、合作方做什么，库存、质量、履约等责任归谁",
    "revenue_costs": "怎样收费，主要成本费用，利润和现金受什么机制影响，哪些未验证",
    "differentiation": "客户为何选它，哪些是已观察的特点、哪些是公司说法、哪些待验证",
    "financial_performance": "营收规模、构成、毛利率、净利率分别是多少或为何未知，属于谁、哪一期、什么来源",
    "marketing": "通过什么渠道、内容和品牌触达客户，如何获客、转化、复购；哪些效果有数据",
    "competition": "主要竞品和替代方案是谁、哪些维度可同口径比较、在什么条件下有差异或被替代",
}
BLOCK_FIELDS = {
    "text": ({"text"}, set()), "bullets": ({"items"}, set()), "callout": ({"title", "text"}, set()),
    "table": ({"title", "columns", "rows", "note"}, set()), "metrics": ({"items"}, set()),
    "chart": ({"chart_type", "title", "unit", "period", "entity_id", "kind", "evidence_ids", "note", "points"}, {"scale_max"}),
    "timeline": ({"title", "items"}, {"purpose"}), "process": ({"title", "items"}, {"purpose", "ordering"}),
    "people": ({"title", "profiles"}, set()),
    "image": ({"role", "path", "title", "alt", "caption", "source_url", "captured_at", "usage_note", "evidence_ids"}, set()),
    "matrix": ({"title", "columns", "rows", "note"}, {"purpose"}),
    "diagram": ({"title", "purpose", "period", "entity_id", "note", "nodes", "edges"}, set()),
    "explanation": ({"topic", "title", "text", "status", "evidence_ids", "limitations"}, set()),
}
KINDS = ("actual", "estimate", "forecast", "company_claim")
BASIS = ("evidence", "company_claim", "inference", "unknown")
PURPOSES = {"process": ("business_model", "recommendation", "other"), "timeline": ("company_history", "other"),
            "diagram": ("business_model", "ownership", "marketing", "other"), "matrix": ("competition", "marketing", "financial", "other")}
RESERVED_IDS = ("main", "overview", "sources", "evidence", "report-data", "toc-toggle")
RESERVED_PREFIX = ("chart-", "ref-", "topic-")
PROCESS_TITLES = ("检索日志", "模块适用", "研究完成范围", "评分覆盖", "完整声明核验", "访谈提纲", "资料请求清单", "research coverage", "search log")
FLOWS = ("product", "money", "information", "relationship")
IMAGE_LIMIT, IMAGES_LIMIT = 5 * 1024 * 1024, 15 * 1024 * 1024
ANALYTICAL = ("chart", "diagram", "process", "timeline", "matrix")
PROSE = ("explanation", "text", "bullets", "callout")
EV_CITE = re.compile(r"\[(ev-\d{4,})\]")
# 22 条人工清单（由作者在出报告前逐条执行，结果写进 reviews 表 type=diligence_manual 的 checks）
MANUAL_ITEMS = {
    "D01": "关键句与所引证据逐条核对：证据确实直接支持原句",
    "D02": "主体、期间、口径（合并/单体/分部、币种、单位）与证据一致",
    "D03": "集团或母公司数据用于子公司时有桥接说明并标为推断",
    "D04": "同源转载已识别，独立印证的说法成立",
    "D05": "关键解释写了替代解释和能区分它们的证据",
    "D06": "反证检索做过；没找到反证时写清查过的范围",
    "D07": "样本来源和选择偏差已说明，没有把管理层挑选的案例外推到总体",
    "D08": "预测、估算、公司口径没有被写成实际数据",
    "D09": "主体身份和控制链的结论与原件一致；拟议或未核实的关系没有写成控制",
    "D10": "上市关联研报：最新报告已取得并读完，或缺口和障碍已写在首页",
    "D11": "财务指标的定义和分母清楚；缺失没有补 0，代理口径已标注",
    "D12": "图表的单位、期间、主体、属性齐全；零基线；null 显示为未披露",
    "D13": "预测用虚线或空心点；区间只画上下界；比例图注明灰色只是量尺",
    "D14": "堆叠图分类一致、带免责说明；瀑布图首尾闭合",
    "D15": "业务模式图的 basis 如实；推断和未知用虚线；示意没有冒充真实订单",
    "D16": "时间线区分宣布、签约、完成、到账；计划事件没有写成已完成",
    "D17": "人物章的贡献有事件、期间和依据，没有把多人的经历归到一个人身上",
    "D18": "矩阵逐格写依据，没有用空白、问号或颜色暗示优劣",
    "D19": "图片有来源、取得日期、权利说明；没有生成或改造的 Logo、人物、门店图",
    "D20": "会改变决策的反证和限制放在相关分析旁边，没有全部折叠到附录",
    "D21": "约定范围没有事后缩小；首页如实说明资料覆盖的限制",
    "D22": "只读正文复述：不看底稿的读者能用自己的话回答 11 个主题问题，未知主题能说出什么未知、有什么影响",
}


def text_ok(v):
    return isinstance(v, str) and v.strip() and "{{" not in v and "}}" not in v


def block_ids(content):
    """内容块 ID：<章节 ID>-<序号>（从 1 开始）。转母版和拆页复核都用它。"""
    return [(f"{s['id']}-{i}", s, b) for s in content.get("sections") or [] for i, b in enumerate(s.get("blocks") or [], 1)]


class Checker:
    def __init__(self, data, base_dir, as_of):
        self.errors, self.warnings = [], []
        self.data, self.base, self.as_of = data, pathlib.Path(base_dir), as_of
        self.evidence = {e["id"]: e for e in data.get("evidence") or []}
        self.entities = {e["id"] for e in data.get("entities") or []}
        self.used, self.images_total = set(), 0

    def e(self, where, msg):
        self.errors.append(f"{where}：{msg}")

    def w(self, where, msg):
        self.warnings.append(f"{where}：{msg}")

    def text(self, where, value, field):
        if not text_ok(value):
            self.e(where, f"{field} 必须是非空文字，且不能残留 {{{{ }}}} 占位")
            return
        for ev in EV_CITE.findall(value):
            self.cite(where, [ev])

    def cite(self, where, ids, allow_empty=False):
        if not isinstance(ids, list) or (not ids and not allow_empty):
            self.e(where, "evidence_ids 要列出支持证据")
            return []
        for i in ids:
            if i not in self.evidence:
                self.e(where, f"引用了不存在的证据 {i}")
            else:
                self.used.add(i)
        return ids

    def attrs(self, ids):
        return {self.evidence[i].get("attribute") for i in ids if i in self.evidence}


def validate(content, data, base_dir, as_of=None):
    """返回 {"errors", "warnings", "used_evidence", "chart_count", "reader_coverage", "counts"}。"""
    c = Checker(data, base_dir, as_of or (data.get("project") or {}).get("as_of_date"))
    top = {"version", "title", "subtitle", "language", "summary", "scope_note", "sections"}
    if not isinstance(content, dict):
        return {"errors": ["report-content.json 顶层必须是对象"], "warnings": []}
    extra = set(content) - top
    if extra:
        c.e("顶层", f"不允许的字段 {sorted(extra)}")
    if content.get("version") != "1.2":
        c.e("顶层", "version 必须是 \"1.2\"（旧版本只读诊断，先升级）")
    for k in ("title", "subtitle", "summary", "scope_note"):
        c.text("顶层", content.get(k), k)
    if content.get("language") not in ("zh-CN", "en"):
        c.e("顶层", "language 只能是 zh-CN 或 en")
    sections = content.get("sections")
    if not isinstance(sections, list) or not sections:
        c.e("顶层", "sections 不能为空")
        sections = []
    ids, topics, counts = set(), {}, {"charts": 0, "business_model": 0, "timelines": 0, "people": 0, "images": 0, "matrices": 0, "diagrams": 0}
    identity_section, history = None, []
    for s in sections:
        sid = s.get("id", "")
        where = f"章节 {sid or '（无 ID）'}"
        extra = set(s) - {"id", "title", "summary", "blocks"}
        if extra:
            c.e(where, f"不允许的字段 {sorted(extra)}")
        if not re.fullmatch(r"[a-z][a-z0-9-]*", sid) or sid in ids:
            c.e(where, "id 要以小写字母开头、只含小写字母数字连字符，且全文唯一")
        if sid in RESERVED_IDS or sid.startswith(RESERVED_PREFIX):
            c.e(where, "id 用了保留名或保留前缀")
        ids.add(sid)
        c.text(where, s.get("title"), "title")
        if any(t.lower() in str(s.get("title", "")).lower() for t in PROCESS_TITLES):
            c.e(where, "章节标题不能是过程性标题（检索日志、资料请求清单等放底稿）")
        if "summary" in s:
            c.text(where, s["summary"], "summary")
        for n, b in enumerate(s.get("blocks") or [], 1):
            check_block(c, f"{where} 第 {n} 块", b, s, topics, counts, history)
            if b.get("type") == "explanation" and b.get("topic") == "identity":
                identity_section = sid
    for t in TOPICS:
        found = topics.get(t, [])
        if len(found) != 1:
            c.e("主题", f"{t} 要恰好出现一次（现在 {len(found)} 次）")
    status = {t: topics[t][0][1] for t in TOPICS if len(topics.get(t, [])) == 1}
    if status.get("transaction_flow") not in (None, "unknown") and counts["business_model"] == 0:
        c.e("跨块", "transaction_flow 不是 unknown 时，至少要有一张业务模式图（purpose=business_model 的 process 或 diagram）")
    history_tl = [h for h in history if h[0] == "company_history"]
    if history_tl:
        for _, sec, items in history_tl:
            if sec != identity_section:
                c.e("跨块", "公司时间线（company_history）要和 identity 放在同一章")
            if len(items) < 2:
                c.e("跨块", "公司时间线至少要有 2 个事件")
    else:
        if status.get("history_team") == "supported":
            c.e("跨块", "没有公司时间线时，history_team 必须是 partial 或 unknown，并写明限制")
        c.w("跨块", "没有公司时间线（company_history）")
    for s in sections:
        for b in s.get("blocks") or []:
            if b.get("type") == "people" and s["id"] == identity_section:
                c.e("跨块", "人物卡不能和 identity 在同一章（人物章要独立）")
    if counts["people"] == 0:
        c.w("跨块", "没有人物卡")
    if counts["images"] == 0:
        c.w("跨块", "没有真实图片")
    if counts["charts"] == 0:
        c.w("跨块", "没有定量图")
    if status and all(v == "unknown" for v in status.values()):
        c.w("跨块", "11 个主题全部是 unknown")
    coverage = {t: {"status": topics[t][0][1], "section": topics[t][0][0]} for t in TOPICS if topics.get(t)}
    return {"errors": c.errors, "warnings": c.warnings, "used_evidence": sorted(c.used), "chart_count": counts["charts"],
            "reader_coverage": coverage, "counts": counts}


def check_block(c, where, b, section, topics, counts, history):
    t = b.get("type")
    if t not in BLOCK_FIELDS:
        c.e(where, f"未知内容块类型 {t}")
        return
    required, optional = BLOCK_FIELDS[t]
    missing = required - set(b)
    extra = set(b) - required - optional - {"type"}
    if missing:
        c.e(where, f"{t} 缺少字段 {sorted(missing)}")
        return
    if extra:
        c.e(where, f"{t} 不允许的字段 {sorted(extra)}")
    if t in PURPOSES and "purpose" in b and b["purpose"] not in PURPOSES[t]:
        c.e(where, f"{t}.purpose 只能是 {'/'.join(PURPOSES[t])}")
    for k in ("title", "text", "note", "caption", "alt", "usage_note"):
        if k in b and k in required:
            c.text(where, b[k], k)
    if t == "bullets":
        if not b["items"] or not all(text_ok(x) for x in b["items"]):
            c.e(where, "bullets.items 要是非空文字列表")
        for x in b["items"]:
            c.text(where, x, "items")
    elif t == "table":
        cols = b["columns"]
        if not cols or not all(text_ok(x) for x in cols):
            c.e(where, "table.columns 要是非空文字列表")
        for r in b["rows"]:
            if len(r) != len(cols) or not all(text_ok(str(x)) for x in r):
                c.e(where, "table 每行要和表头等长，单元格不能为空")
    elif t == "metrics":
        for m in b["items"]:
            for k in ("label", "value", "unit", "period", "entity_id", "kind", "evidence_ids", "note"):
                if k not in m:
                    c.e(where, f"metrics 项缺少 {k}")
            if m.get("kind") not in KINDS:
                c.e(where, "metrics 的 kind 只能是 actual/estimate/forecast/company_claim（不能 mixed）")
            c.cite(where, m.get("evidence_ids"), allow_empty=m.get("value") is None)
            entity(c, where, m.get("entity_id"))
    elif t == "chart":
        counts["charts"] += 1
        check_chart(c, where, b)
    elif t == "timeline":
        counts["timelines"] += 1
        for it in b["items"]:
            if it.get("status") not in ("completed", "planned") or not re.fullmatch(r"\d{4}(-\d{2}(-\d{2})?)?", str(it.get("date", ""))):
                c.e(where, "时间线事件要有 date（只知道年份就只写年份）和 status（completed/planned）")
            c.text(where, it.get("title"), "title")
            c.text(where, it.get("text"), "text")
            ids = c.cite(where, it.get("evidence_ids"))
            if b.get("purpose") == "company_history" and it.get("status") == "completed" and "forecast" in c.attrs(ids):
                c.e(where, f"已完成的事件「{it.get('title')}」不能引用预测证据")
        history.append((b.get("purpose", "other"), section["id"], b["items"]))
    elif t == "process":
        if b.get("ordering", "sequence") not in ("sequence", "conceptual"):
            c.e(where, "process.ordering 只能是 sequence 或 conceptual")
        if b.get("purpose") == "business_model":
            counts["business_model"] += 1
        for it in b["items"]:
            c.text(where, it.get("title"), "title")
            c.text(where, it.get("text"), "text")
            basis(c, where, it)
    elif t == "people":
        counts["people"] += 1
        for pr in b["profiles"]:
            for k in ("name", "role", "period", "background", "contribution", "limitations"):
                c.text(where, pr.get(k), k)
            c.cite(where, pr.get("evidence_ids"))
    elif t == "image":
        counts["images"] += 1
        check_image(c, where, b)
    elif t == "matrix":
        counts["matrices"] += 1
        if len(b["columns"]) < 2:
            c.e(where, "矩阵至少 2 列")
        for r in b["rows"]:
            c.text(where, r.get("label"), "label")
            if len(r.get("cells") or []) != len(b["columns"]):
                c.e(where, "矩阵每行的格数要等于列数")
            for cell in r.get("cells") or []:
                c.text(where, cell.get("text"), "text")
                basis(c, where, cell)
    elif t == "diagram":
        counts["diagrams"] += 1
        if b["purpose"] == "business_model":
            counts["business_model"] += 1
        if b["purpose"] not in PURPOSES["diagram"]:
            c.e(where, f"diagram.purpose 只能是 {'/'.join(PURPOSES['diagram'])}")
        entity(c, where, b.get("entity_id"))
        check_diagram(c, where, b)
    elif t == "explanation":
        topic, st = b["topic"], b["status"]
        if topic not in TOPICS:
            c.e(where, f"未知主题 {topic}")
        if st not in ("supported", "partial", "unknown"):
            c.e(where, "explanation.status 只能是 supported/partial/unknown")
        ids = b["evidence_ids"] if isinstance(b["evidence_ids"], list) else []
        if st in ("supported", "partial"):
            c.cite(where, ids)
        else:
            c.cite(where, ids, allow_empty=True)
        if st in ("partial", "unknown") and not text_ok(b["limitations"]):
            c.e(where, f"{st} 的主题要写具体的限制")
        if st == "supported" and b["limitations"] not in ("", None) and not text_ok(b["limitations"]):
            c.e(where, "limitations 要么为空，要么写清楚")
        topics.setdefault(topic, []).append((section["id"], st))


def entity(c, where, eid):
    if eid != "industry" and eid not in c.entities:
        c.e(where, f"entity_id={eid} 不在主体表里（行业数据写 industry）")


def basis(c, where, item):
    b = item.get("basis", "evidence")
    if b not in BASIS:
        c.e(where, f"basis 只能是 {'/'.join(BASIS)}")
    c.cite(where, item.get("evidence_ids") or [], allow_empty=b == "unknown")


def check_chart(c, where, b):
    ct, pts, kind = b["chart_type"], b["points"], b["kind"]
    entity(c, where, b["entity_id"])
    ids = c.cite(where, b["evidence_ids"])
    if kind not in KINDS + ("mixed",):
        c.e(where, "chart.kind 只能是 actual/estimate/forecast/company_claim/mixed")
    if "scale_max" in b and ct != "proportion":
        c.e(where, "只有 proportion 允许 scale_max")
    if not isinstance(pts, list) or not pts:
        c.e(where, "points 不能为空")
        return
    labels = [p.get("label") for p in pts]
    if len(set(labels)) != len(labels) or not all(text_ok(x) for x in labels):
        c.e(where, "点标签要非空且唯一")
    for p in pts:
        pk = p.get("kind", kind)
        if kind == "mixed" and "kind" not in p:
            c.e(where, "图级 kind=mixed 时每个点都要自带 kind")
        if kind != "mixed" and "kind" in p and p["kind"] != kind:
            c.e(where, f"点「{p.get('label')}」的 kind 与图级 {kind} 不一致")
        pids = p.get("evidence_ids") or ids
        if pk == "actual" and c.attrs(pids) & {"forecast", "estimate"}:
            c.e(where, f"实际数据点「{p.get('label')}」不能引用预测或估算证据")
    num = lambda x: isinstance(x, (int, float)) and not isinstance(x, bool)  # noqa: E731
    vals = [p.get("value") for p in pts]
    known = [v for v in vals if v is not None]
    if any(v is not None and not num(v) for v in vals):
        c.e(where, "数值要么是数字，要么是 null（缺失显示为未披露，不能写 0）")
        return
    if ct in ("bar", "line", "column"):
        if not 2 <= len(pts) <= 24 or len(known) < 2:
            c.e(where, f"{ct} 要 2–24 个点，且至少 2 个已知值")
        if ct != "column" and any(v < 0 for v in known):
            c.e(where, f"{ct} 不允许负值（需要负值用 column）")
    elif ct == "donut":
        if not 2 <= len(pts) <= 6 or len(known) != len(pts) or any(v < 0 for v in known) or sum(known) <= 0:
            c.e(where, "donut 要 2–6 项，不能缺失或为负，总和大于 0")
    elif ct == "range":
        ok = 0
        for p in pts:
            lo, hi = p.get("low"), p.get("high")
            if (lo is None) != (hi is None) or (lo is not None and (not num(lo) or not num(hi) or lo > hi)):
                c.e(where, f"区间「{p.get('label')}」的 low/high 要同为 null 或同为数字且 low ≤ high")
            elif lo is not None:
                ok += 1
            if p.get("value") is not None:
                c.e(where, "区间图不画中点（不要写 value）")
        if ok == 0:
            c.e(where, "区间图至少要有 1 组已知上下界")
    elif ct == "proportion":
        sm = b.get("scale_max")
        if not num(sm) or sm <= 0:
            c.e(where, "proportion 要写 scale_max > 0")
        elif any(u in b["unit"] for u in ("%", "％", "百分比")) and sm != 100:
            c.e(where, "单位是百分比时 scale_max 必须是 100")
        elif any(v < 0 or v > sm for v in known):
            c.e(where, "比例值要在 0 到 scale_max 之间")
        if len(pts) > 8 or not known:
            c.e(where, "proportion 最多 8 点，至少 1 个已知值")
    elif ct == "waterfall":
        roles = [p.get("role") for p in pts]
        if not 2 <= len(pts) <= 12 or roles[0] != "start" or roles[-1] != "total" or "start" in roles[1:] or any(r not in ("start", "delta", "total") for r in roles):
            c.e(where, "瀑布图 2–12 点，首点 start、末点 total、中间只能是 delta 或 total")
        elif None in vals:
            c.e(where, "瀑布图不能有缺失值")
        else:
            acc = Decimal(repr(vals[0]))
            for p, v in zip(pts[1:], vals[1:]):
                if p["role"] == "delta":
                    acc += Decimal(repr(v))
                elif abs(Decimal(repr(v)) - acc) > Decimal("1e-9"):
                    c.e(where, f"瀑布图没有闭合：「{p.get('label')}」应为 {acc}，写的是 {v}")
    elif ct == "stacked_bar":
        groups = [p.get("parts") or [] for p in pts]
        names = [[x.get("label") for x in g] for g in groups]
        if not 2 <= len(pts) <= 8 or any(not 2 <= len(g) <= 6 for g in groups) or sum(len(g) for g in groups) > 24:
            c.e(where, "堆叠图 2–8 组，每组 2–6 个分项，全图最多 24 段")
        elif any(n != names[0] for n in names):
            c.e(where, "堆叠图各组的分项标签和顺序要一致")
        elif any(not num(x.get("value")) or x["value"] < 0 for g in groups for x in g):
            c.e(where, "堆叠图分项要非负且不缺失")
    else:
        c.e(where, f"未知图型 {ct}（bar/line/donut/column/proportion/range/waterfall/stacked_bar）")


def check_diagram(c, where, b):
    nodes, edges = b["nodes"], b["edges"]
    if len(nodes) < 2 or not edges:
        c.e(where, "关系图至少 2 个节点、1 条边")
        return
    ids = [n.get("id") for n in nodes]
    if len(set(ids)) != len(ids) or not all(re.fullmatch(r"[a-z][a-z0-9-]*", str(i)) for i in ids):
        c.e(where, "节点 id 要小写且唯一")
    for n in nodes:
        c.text(where, n.get("label"), "label")
        c.text(where, n.get("text"), "text")
        basis(c, where, n)
    seen, linked = set(), set()
    for e in edges:
        key = (e.get("source"), e.get("target"), e.get("flow"), e.get("label"))
        if e.get("source") not in ids or e.get("target") not in ids or e.get("source") == e.get("target"):
            c.e(where, "边的两端要是已有节点，且不能自连接")
        if e.get("flow") not in FLOWS:
            c.e(where, f"边的 flow 只能是 {'/'.join(FLOWS)}")
        if not text_ok(e.get("label")):
            c.e(where, "边要写 label")
        if key in seen:
            c.e(where, "有完全重复的边")
        seen.add(key)
        linked |= {e.get("source"), e.get("target")}
        basis(c, where, e)
    for i in ids:
        if i not in linked:
            c.e(where, f"节点 {i} 是孤立节点")


def check_image(c, where, b):
    if b["role"] not in ("logo", "website", "product", "store", "people", "other"):
        c.e(where, "image.role 只能是 logo/website/product/store/people/other")
    c.cite(where, b["evidence_ids"])
    url = b["source_url"]
    if url and (not re.match(r"https?://[^/@\s]+(/|$)", url) or "@" in url.split("/")[2]):
        c.e(where, "source_url 要么为空（本地材料），要么是不带用户名密码的 http(s) 网址")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(b["captured_at"])):
        c.e(where, "captured_at 要写本次取得日期 YYYY-MM-DD")
    elif c.as_of and b["captured_at"] > c.as_of:
        c.w(where, "图片取得日期晚于基准日")
    path = b["path"]
    if not isinstance(path, str) or not path or path.startswith(("/", "\\")) or re.match(r"[A-Za-z]:", path) or ".." in pathlib.PurePosixPath(path).parts or "\x00" in path:
        c.e(where, "图片 path 要是项目内的相对路径（不能绝对路径、不能含 ..）")
        return
    real = (c.base / path).resolve()
    try:
        real.relative_to(c.base.resolve())
    except ValueError:
        c.e(where, "图片路径解析后在项目目录之外（可能是符号链接逃逸）")
        return
    if not real.is_file():
        c.e(where, f"图片文件不存在：{path}")
        return
    with open(real, "rb") as f:
        data = f.read(IMAGE_LIMIT + 1)
    if len(data) > IMAGE_LIMIT:
        c.e(where, "单张图片超过 5 MiB")
        return
    c.images_total += len(data)
    if c.images_total > IMAGES_LIMIT:
        c.e(where, "图片合计超过 15 MiB")
    if not (data.startswith(b"\x89PNG\r\n\x1a\n") or data.startswith(b"\xff\xd8\xff") or (data[:4] == b"RIFF" and data[8:12] == b"WEBP")):
        c.e(where, "图片只能是 PNG、JPEG 或 WebP（按文件头判断；SVG 不行）")


def media_bundle(content, base_dir):
    """把图片读成 data: URI 用的 {path: {mime, base64, sha256}}（out-report 页面内嵌用）。调用前要先通过 validate。"""
    out = {}
    for _, _, b in block_ids(content):
        if b.get("type") != "image":
            continue
        data = (pathlib.Path(base_dir) / b["path"]).read_bytes()
        mime = "image/png" if data.startswith(b"\x89PNG") else "image/jpeg" if data.startswith(b"\xff\xd8") else "image/webp"
        out[b["path"]] = {"mime": mime, "base64": base64.b64encode(data).decode("ascii"), "sha256": hashlib.sha256(data).hexdigest()}
    return out


# ---------- 可视化编排提示（只提示） ----------

def _numbers(text):
    t = EV_CITE.sub("", text or "")
    t = re.sub(r"https?://\S+|\b(?:ENT|REL|S|E|C|G|R|RR|RC|SC)-\d+\b|\b(19|20|21)\d\d\b|\d{4}-\d{2}-\d{2}|^\s*\d+[.、]", "", t, flags=re.M)
    return re.findall(r"\d+(?:\.\d+)?", t)


def visual_hints(content):
    findings, chart_types = [], []
    unknown_topics = set()
    for s in content.get("sections") or []:
        blocks = s.get("blocks") or []
        unknown_topics |= {b.get("topic") for b in blocks if b.get("type") == "explanation" and b.get("status") == "unknown"}
        run, explanations_before, first_analytic = 0, 0, None
        quant = any(b.get("type") == "chart" and any(p.get("value") is not None or p.get("low") is not None or p.get("parts") for p in b.get("points") or [])
                    for b in blocks)
        prose_numbers = 0
        for i, b in enumerate(blocks):
            t = b.get("type")
            text = " ".join(str(b.get(k, "")) for k in ("text", "title")) + " ".join(map(str, b.get("items") or [] if t == "bullets" else []))
            if t in PROSE:
                run += len(re.findall(r"[一-鿿]", text)) + len(re.findall(r"[A-Za-z]+", text)) * 5
                if run >= 600:
                    findings.append({"section": s["id"], "rule": "long_prose_run", "message": "连续文字块累计超过 600 字，考虑用图或表拆开"})
                    run = -10**9
                if not (t == "explanation" and b.get("status") == "unknown"):
                    prose_numbers += len(_numbers(text))
            else:
                run = 0
            if t == "explanation" and b.get("status") != "unknown" and first_analytic is None:
                explanations_before += 1
            if t in ANALYTICAL and first_analytic is None:
                first_analytic = i
                if explanations_before >= 3:
                    findings.append({"section": s["id"], "rule": "late_analytical_visual", "message": "本章第一张分析图之前已有 3 段以上解释，主视觉放前面"})
            if t == "chart":
                chart_types.append(b.get("chart_type"))
            if t == "table" and (len(b.get("rows") or []) >= 5 or sum(len(r) for r in b.get("rows") or []) >= 16) and not any(x.get("type") in ANALYTICAL for x in blocks):
                findings.append({"section": s["id"], "rule": "dense_table_without_synthesis", "message": "表格较密但本章没有分析图，补一张图或一句结论"})
        topics_here = {b.get("topic"): b.get("status") for b in blocks if b.get("type") == "explanation"}
        needs = {"financial_performance": ("chart", "matrix"), "marketing": ANALYTICAL, "competition": ("chart", "diagram", "matrix")}
        flagged = False
        for topic, kinds in needs.items():
            if topic in topics_here and topics_here[topic] != "unknown" and not any(b.get("type") in kinds for b in blocks):
                findings.append({"section": s["id"], "rule": "topic_without_analytical_visual", "message": f"{topic} 所在章没有合适的图"})
                flagged = True
        if prose_numbers >= 3 and not quant and not flagged:
            findings.append({"section": s["id"], "rule": "numbers_only_in_prose", "message": "数字只在文字里，没有定量图"})
    if len(chart_types) >= 3 and len(set(chart_types)) == 1:
        findings.append({"section": "全稿", "rule": "single_chart_type", "message": f"{len(chart_types)} 张定量图全是 {chart_types[0]}"})
    return findings


# ---------- 拆页后复核 ----------

def after_split(content, block_map, slides_doc, data, base_dir):
    errors = []
    current = [bid for bid, _, _ in block_ids(content)]
    mapped = [m["block_id"] for m in block_map]
    if mapped != current:
        errors.append("block_map.json 与当前 report-content.json 的内容块不一致：内容改过要重新运行 diligence_to_manuscript")
    by_block = {}
    for sl in slides_doc.get("slides") or []:
        for bid in sl.get("block_ids") or []:
            by_block.setdefault(bid, []).append(sl)
    for bid in sorted(set(by_block) - set(current)):
        errors.append(f"slides.json 引用了不存在的内容块 {bid}")
    for bid in current:
        if bid not in by_block:
            errors.append(f"内容块 {bid} 没有落到任何页上（slides.json 的 block_ids）")
    sec = lambda bid: {sl.get("section") for sl in by_block.get(bid, [])}  # noqa: E731
    identity = [bid for bid, _, b in block_ids(content) if b.get("type") == "explanation" and b.get("topic") == "identity"]
    id_secs = sec(identity[0]) if identity else set()
    if identity and (None in id_secs or not id_secs):
        errors.append("identity 所在页要写 section（章节），才能核对同章规则")
    for bid, _, b in block_ids(content):
        if b.get("type") == "timeline" and b.get("purpose") == "company_history" and id_secs and not (sec(bid) & id_secs):
            errors.append(f"拆页后公司时间线 {bid} 不再和 identity 同章")
        if b.get("type") == "people" and id_secs and sec(bid) & id_secs:
            errors.append(f"拆页后人物卡 {bid} 和 identity 同章了")
    errors += validate(content, data, base_dir)["errors"]
    return errors


def manual_errors(data):
    rows = [r for r in data.get("reviews") or [] if r.get("type") == "diligence_manual"]
    if not rows:
        return ["没有 22 条人工清单的记录（reviews 表 type=diligence_manual）"]
    checks = rows[-1].get("checks") or {}
    out = []
    for k, text in MANUAL_ITEMS.items():
        item = checks.get(k)
        if not item or not str(item.get("evidence") or "").strip():
            out.append(f"人工清单 {k}（{text}）没有记录")
        elif not item.get("passed"):
            out.append(f"人工清单 {k}（{text}）没有通过：{item['evidence']}")
    return out

