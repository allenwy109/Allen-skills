"""core-diligence 的单元测试：上市追溯与研报门槛、完成复核、语义检查、财务比率、评分、报告内容契约、检索计划、底稿。夹具全部虚构。"""
import copy
import json
import pathlib
import shutil
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import diligence_fixture as F  # noqa: E402
import daudit  # noqa: E402
import dcontent  # noqa: E402
import dcore  # noqa: E402
import diligence  # noqa: E402
import dplan  # noqa: E402
import dratios  # noqa: E402
import dscore  # noqa: E402
from tools.lib.ledger import Ledger  # noqa: E402

AS_OF = "2026-10-20"
TEMPLATE = tempfile.TemporaryDirectory()
F.make_diligence_task(pathlib.Path(TEMPLATE.name) / "task")


def ent(eid, listing="unlisted", status="resolved", **kw):
    return {"id": eid, "legal_name": eid, "entity_type": "legal_entity", "identity_status": status, "listing_status": listing, **kw}


def rel(rid, parent, child, kind="control", state="current", verification="verified", start="2020-01-01", end=None):
    return {"id": rid, "parent_id": parent, "child_id": child, "relation_type": kind, "control_basis": "持股", "effective_from": start,
            "effective_to": end, "state": state, "verification": verification}


def report(rid, entity, cats, date, access="full", reading="analyzed", relevance="direct", source="M001", **kw):
    return {"id": rid, "source_id": source, "publisher": kw.pop("publisher", "某证券"), "title": rid, "categories": cats,
            "category_relevance": {c: "直接" for c in cats}, "target_id": "ENT-0001", "coverage_entity_id": entity, "report_date": date,
            "version": "1", "access_status": access, "reading_status": reading, "relevance": relevance, **kw}


def base_data(**over):
    d = {"project": {"target_entity_id": "ENT-0001", "as_of_date": AS_OF, "control_chain_checked": True, "control_evidence_ids": ["ev-0001"]},
         "entities": [ent("ENT-0001"), ent("ENT-0002", listing="listed", exchange="SSE", security_code="600000", listing_start="2010-01-01")],
         "relations": [rel("REL-0001", "ENT-0002", "ENT-0001")], "research_reports": [], "coverage": [], "sources": [{"id": "M001", "time_scope": "as_of"}],
         "gaps": [], "claims": [], "claim_evidence": [], "evidence": [], "conflicts": [], "search_log": [], "scorecard": [], "risks": [], "reviews": []}
    d.update(over)
    return d


class ListingTest(unittest.TestCase):
    def test_verified_control_triggers(self):
        listed, status, _ = dcore.listed_entities(base_data())
        self.assertEqual((listed, status), (["ENT-0002"], "triggered"))

    def test_proposed_and_out_of_range_edges_do_not_trigger(self):
        for r in (rel("REL-0001", "ENT-0002", "ENT-0001", state="proposed"), rel("REL-0001", "ENT-0002", "ENT-0001", end=AS_OF),
                  rel("REL-0001", "ENT-0002", "ENT-0001", kind="minority")):
            self.assertEqual(dcore.listed_entities(base_data(relations=[r]))[1], "not_triggered", r)

    def test_pending_reasons(self):
        self.assertEqual(dcore.listed_entities(base_data(relations=[rel("REL-0001", "ENT-0002", "ENT-0001", verification="pending")]))[1], "pending")
        d = base_data()
        d["entities"][0]["identity_status"] = "pending"
        self.assertEqual(dcore.listed_entities(d)[1], "pending")
        d = base_data()
        d["project"]["control_chain_checked"] = False
        self.assertIn("控制链没有核对", "\n".join(dcore.listed_entities(d)[2]))

    def test_joint_control_is_configurable(self):
        d = base_data(relations=[rel("REL-0001", "ENT-0002", "ENT-0001", kind="joint_control")])
        listed, status, warnings = dcore.listed_entities(d)
        self.assertEqual(status, "not_triggered")
        self.assertIn("共同控制", warnings[0])
        d["project"]["joint_control_triggers"] = True
        self.assertEqual(dcore.listed_entities(d)[1], "triggered")

    def test_delisted_within_window(self):
        d = base_data()
        d["entities"][1].update(listing_status="delisted", listing_start="2010-01-01", listing_end="2027-01-01")
        self.assertEqual(dcore.listed_entities(d)[0], ["ENT-0002"])


class RequirementsTest(unittest.TestCase):
    def test_categories_events_peer_and_exemptions(self):
        d = base_data()
        reqs, errors = dcore.requirements(d, ["ENT-0002"])
        self.assertEqual([c for _, c, _, _ in reqs], list(dcore.BASE_CATEGORIES))
        d["project"].update(events=[{"date": "2026-09-01", "entity_id": "ENT-0002", "event_type": "重组", "description": "重大重组"}], peer_required=True,
                            category_exemptions=[{"entity_id": "ENT-0002", "category": "official_interim", "reason": "尚无该期", "evidence_ids": ["ev-0001"]},
                                                 {"entity_id": "ENT-0002", "category": "industry", "reason": "不想读"}])
        reqs, errors = dcore.requirements(d, ["ENT-0002"])
        cats = [c for _, c, _, _ in reqs]
        self.assertNotIn("official_interim", cats)
        self.assertIn("event_update", cats)
        self.assertIn("peer", cats)
        self.assertIn("豁免只允许 official_interim", errors[0])


class CoverageTest(unittest.TestCase):
    def data(self, reports, cov=None):
        d = base_data(research_reports=reports)
        d["coverage"] = [cov or {"id": "RC-0001", "target_id": "ENT-0001", "research_entity_id": "ENT-0002", "category": "company_update", "required": True,
                                 "reason": "必读", "search_status": "found", "search_ids": ["SL-0001"], "latestness_checked_at": "2026-10-19T10:00:00+08:00",
                                 "event_coverage": "not_applicable", "gate_status": "incomplete"}]
        return d

    def test_complete_partial_incomplete(self):
        d = self.data([report("RR-0001", "ENT-0002", ["company_update"], "2026-09-30")])
        cands = dcore.candidates(d, "ENT-0002", "company_update")
        self.assertEqual(dcore.coverage_state(d["coverage"][0], cands, d), "complete")
        d = self.data([report("RR-0001", "ENT-0002", ["company_update"], "2026-09-30"),
                       report("RR-0002", "ENT-0002", ["company_update"], "2026-10-10", access="partial", reading="partial")])
        self.assertEqual(dcore.coverage_state(d["coverage"][0], dcore.candidates(d, "ENT-0002", "company_update"), d), "partial")
        d = self.data([report("RR-0001", "ENT-0002", ["company_update"], "2026-10-10", access="metadata_only", reading="unread")])
        self.assertEqual(dcore.coverage_state(d["coverage"][0], dcore.candidates(d, "ENT-0002", "company_update"), d), "incomplete")

    def test_same_day_reports_all_count_and_superseded_or_late_excluded(self):
        d = self.data([report("RR-0001", "ENT-0002", ["company_update"], "2026-10-10"),
                       report("RR-0002", "ENT-0002", ["company_update"], "2026-10-10", reading="partial"),
                       report("RR-0003", "ENT-0002", ["company_update"], "2026-10-25"),
                       report("RR-0004", "ENT-0002", ["company_update"], "2026-10-12", supersedes_id=None),
                       report("RR-0005", "ENT-0002", ["company_update"], "2026-10-12", supersedes_id="RR-0004")])
        cands = dcore.candidates(d, "ENT-0002", "company_update")
        self.assertEqual([r["id"] for r in cands], ["RR-0005", "RR-0001", "RR-0002"])  # 基准日后的 RR-0003、被替代的 RR-0004 排除
        d = self.data([report("RR-0001", "ENT-0002", ["company_update"], "2026-10-10"), report("RR-0002", "ENT-0002", ["company_update"], "2026-10-10")])
        self.assertEqual(dcore.pointers(dcore.candidates(d, "ENT-0002", "company_update"))["read"], ["RR-0001", "RR-0002"])

    def test_retrospective_source_and_event_coverage(self):
        d = self.data([report("RR-0001", "ENT-0002", ["company_update"], "2026-09-30", source="M002")])
        d["sources"].append({"id": "M002", "time_scope": "retrospective"})
        self.assertEqual(dcore.candidates(d, "ENT-0002", "company_update"), [])
        d = self.data([report("RR-0001", "ENT-0002", ["company_update"], "2026-08-30")])
        self.assertEqual(dcore.coverage_state(d["coverage"][0], dcore.candidates(d, "ENT-0002", "company_update"), d, ["2026-09-01"]), "partial")

    def test_gate_does_not_depend_on_network(self):
        reqs = [("ENT-0002", "company_update", "", [])]
        self.assertEqual(dcore.research_gate({}, reqs, {("ENT-0002", "company_update"): "complete"}, "triggered"), "complete")
        self.assertEqual(dcore.research_gate({}, [], {}, "pending"), "incomplete")
        self.assertEqual(dcore.research_gate({}, [], {}, "not_triggered"), "not_applicable")
        self.assertEqual(dcore.research_gate({}, reqs, {("ENT-0002", "company_update"): "partial"}, "triggered"), "partial")


class LedgerBackedTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.task = pathlib.Path(self.tmp.name) / "task"
        shutil.copytree(pathlib.Path(TEMPLATE.name) / "task", self.task)
        self.led = Ledger(self.task)

    def tearDown(self):
        self.tmp.cleanup()

    def errors(self, mode="completed"):
        return "\n".join(diligence.check(self.task, mode)["errors"])

    def test_fixture_passes_completed_mode(self):
        r = diligence.check(self.task, "completed")
        self.assertEqual((r["status"], r["research_gate"], r["listing_trigger"]), ("structure_passed", "not_applicable", "not_triggered"))

    def test_sync_creates_coverage_for_listed_parent(self):
        parent = {k: v for k, v in ent("ENT-0002", listing="listed", exchange="SSE", security_code="600000", registration_id="X",
                                       evidence_ids=["ev-0001"]).items() if k != "id"}
        self.led.add("entities", parent)
        edge = {k: v for k, v in rel("x", "ENT-0002", "ENT-0001").items() if k not in ("id", "effective_to")}
        self.led.add("relations", {**edge, "evidence_ids": ["ev-0001"]})
        r = dcore.sync_coverage(self.task)
        self.assertEqual((r["listing_trigger"], r["research_gate"], len(r["created"])), ("triggered", "incomplete", 5))
        self.assertEqual([i for i in self.led.check() if i["level"] == "error"], [])
        text = self.errors("draft")
        self.assertNotIn("覆盖", text)                              # 同步后的覆盖行、缺口、指针都一致
        self.assertIn("研报门槛", "\n".join(diligence.check(self.task)["warnings"]))

    def test_completion_rules(self):
        self.led.patch("claims", "cl-0002", {"verification": "single_source"})
        self.led.add("gaps", {"description": "关键客户合同未取得", "reason": "access_restricted", "materiality": "critical", "priority": "P0", "route": "user",
                              "blocking_scope": "task", "acquisition_path": "请公司提供", "owner_role": "研究负责人", "status": "open"})
        text = self.errors()
        self.assertIn("关键主张 cl-0002：要已核实", text)
        self.assertIn("开放缺口 G-0002 没有在 completion_review 里评估影响", text)

    def test_completed_mode_requires_module_files_and_refresh(self):
        (self.task / "03d_diligence" / "modules" / "05-module.md").unlink()
        self.led.patch("project", "project", {"last_refresh_at": None})
        text = self.errors()
        self.assertIn("适用模块 05", text)
        self.assertIn("last_refresh_at", text)

    def test_semantic_errors(self):
        self.led.patch("sources", "U002", {"accessed": "2026-05-01T10:00:00+08:00"})
        self.led.patch("sources", "U003", {"published": "2026-10-25"})
        self.led.patch("entities", "ENT-0001", {"identity_status": "pending", "registration_id": None, "evidence_ids": None})
        text = self.errors("draft")
        self.assertIn("访问日 2026-05-01 早于published", text)
        self.assertIn("发布于基准日 2026-10-20 之后", text)
        self.assertIn("身份没有锁定，不能形成已核实", text)

    def test_identity_status_mismatch(self):
        self.led.patch("project", "project", {"identity_status": "pending"})
        self.assertIn("身份状态不一致", self.errors("draft"))


class RatiosTest(unittest.TestCase):
    def doc(self, **values):
        base = {"revenue": 1000.0, "cost": 600.0, "net_profit": 100.0, "operating_profit": 150.0, "depreciation": 20.0, "amortization": 10.0,
                "interest_expense": 30.0, "income_tax": 25.0, "profit_before_tax": 125.0, "operating_cashflow": 120.0, "current_assets": 500.0,
                "current_liabilities": 250.0, "inventory": 100.0, "prepayments": 50.0, "assets_begin": 900.0, "assets_end": 1100.0, "equity_begin": 400.0,
                "equity_end": 600.0, "receivables_begin": 100.0, "receivables_end": 140.0, "inventory_begin": 80.0, "inventory_end": 100.0,
                "payables_begin": 60.0, "payables_end": 80.0, "credit_sales": 900.0, "purchases": 650.0, "capex": 40.0, "total_debt": 300.0,
                "total_assets": 1100.0, "cash_and_equivalents": 100.0, "invested_capital_begin": 700.0, "invested_capital_end": 900.0}
        base.update(values)
        base = {k: v for k, v in base.items() if v is not None}
        return {"synthetic": True, "entity_id": "ENT-0001", "scope": "consolidated", "period_start": "2025-01-01", "period_end": "2025-12-31", "days": 365,
                "currency": "CNY", "unit": "万元", "accounting_basis": "CAS", "attribute": "actual", "audited": True, "source_ids": ["U003"],
                "values": base, "input_evidence": {k: ["ev-0007"] for k in base}, "prior": None}

    def m(self, doc, name):
        return dratios.calculate(doc)["metrics"][name]

    def test_core_ratios(self):
        d = self.doc()
        self.assertAlmostEqual(self.m(d, "gross_margin")["value"], 0.4)
        self.assertAlmostEqual(self.m(d, "quick_ratio")["value"], 1.4)
        self.assertAlmostEqual(self.m(d, "roa")["value"], 0.1)
        self.assertAlmostEqual(self.m(d, "roe_annualized")["value"], 0.2)
        self.assertAlmostEqual(self.m(d, "receivable_days")["value"], 120 / 900 * 365)
        self.assertAlmostEqual(self.m(d, "simplified_fcf")["value"], 80)

    def test_added_ratios(self):
        d = self.doc()
        self.assertAlmostEqual(self.m(d, "operating_margin")["value"], 0.15)
        self.assertAlmostEqual(self.m(d, "ebitda")["value"], 180)
        self.assertAlmostEqual(self.m(d, "net_debt_to_ebitda")["value"], 200 / 180)
        self.assertAlmostEqual(self.m(d, "interest_coverage")["value"], 5)
        self.assertAlmostEqual(self.m(d, "roic")["value"], 150 * 0.8 / 800)
        self.assertAlmostEqual(self.m(d, "debt_to_assets")["value"], 300 / 1100)

    def test_missing_not_applicable_and_approximate(self):
        self.assertEqual(self.m(self.doc(revenue=None), "gross_margin")["status"], "missing")
        self.assertEqual(self.m(self.doc(revenue=0.0, cost=0.0), "net_margin")["status"], "not_applicable")
        self.assertEqual(self.m(self.doc(prepayments=None), "quick_ratio")["status"], "missing")
        d = self.doc(assets_begin=None)
        self.assertEqual(self.m(d, "roa")["status"], "missing")
        d["options"] = {"allow_end_balance": True}
        self.assertEqual(self.m(d, "roa")["status"], "approximate")
        d = self.doc(credit_sales=None)
        d["options"] = {"allow_revenue_proxy": True}
        self.assertEqual(self.m(d, "receivable_days")["status"], "approximate")
        self.assertEqual(self.m(d, "cash_conversion_cycle")["status"], "approximate")
        self.assertEqual(self.m(self.doc(net_profit=0.005), "cash_profit_ratio")["status"], "not_applicable")

    def test_runway_rules(self):
        d = self.doc(available_cash=600.0, monthly_net_burn=50.0)
        with self.assertRaises(dratios.InputError):
            dratios.calculate(d)                                # 四个口径没写清
        d["cash_burn_basis"] = {"basis": "经营与资本开支", "cash_excludes_restricted": False, "includes_capex": True, "includes_debt_service": False,
                                "includes_committed_spend": False}
        self.assertEqual(self.m(d, "cash_runway_months")["status"], "missing")
        d["cash_burn_basis"]["cash_excludes_restricted"] = True
        r = self.m(d, "cash_runway_months")
        self.assertEqual((r["value"], r["attribute"]), (12, "estimate"))
        d["values"]["monthly_net_burn"] = 0.0
        self.assertIn("不代表永久安全", self.m(d, "cash_runway_months")["reason"])

    def test_growth_comparability_series_segments_thresholds(self):
        d = self.doc()
        prior = copy.deepcopy(d)
        prior.update(period_start="2024-01-01", period_end="2024-12-31", days=366)
        prior["values"]["revenue"] = 800.0
        d["prior"] = prior
        self.assertAlmostEqual(self.m(d, "revenue_growth")["value"], 0.25)
        prior["unit"] = "元"
        self.assertEqual(self.m(d, "revenue_growth")["status"], "not_applicable")
        quarters = []
        for q, (s, e) in enumerate((("2025-01-01", "2025-03-31"), ("2025-04-01", "2025-06-30"), ("2025-07-01", "2025-09-30"), ("2025-10-01", "2025-12-31")), 1):
            p = copy.deepcopy(self.doc())
            p.update(period_start=s, period_end=e, days=(dratios._date(e) - dratios._date(s)).days + 1)
            p["values"] = {"revenue": 100.0 * q}
            p["input_evidence"] = {"revenue": ["ev-0007"]}
            quarters.append(p)
        d = self.doc()
        d["series"] = quarters
        d["segments"] = {"values": {"设备": 600.0, "订阅": 300.0}, "evidence_ids": ["ev-0007"]}
        d["thresholds"] = [{"metric": "gross_margin", "operator": "lt", "value": 0.5, "scope": "consolidated", "source": "内部线索"}]
        r = dratios.calculate(d)
        self.assertAlmostEqual(r["series"][1]["qoq"], 1.0)
        self.assertEqual(r["series"][-1]["ttm_revenue"], 1000.0)
        self.assertAlmostEqual(r["segments"]["unexplained"], 100.0)
        self.assertEqual(len(r["alerts"]), 1)

    def test_input_validation(self):
        d = self.doc()
        d["days"] = 300
        with self.assertRaises(dratios.InputError):
            dratios.calculate(d)
        d = self.doc()
        d["values"]["gmv"] = 1.0
        with self.assertRaises(dratios.InputError):
            dratios.calculate(d)
        d = self.doc()
        d["input_evidence"].pop("revenue")
        with self.assertRaises(dratios.InputError):
            dratios.calculate(d)
        d = self.doc(capex=-40.0)
        with self.assertRaises(dratios.InputError):
            dratios.calculate(d)


class ScoreTest(unittest.TestCase):
    def data(self, scores=None, **project):
        ov = dscore.default_override("investment")
        rows = []
        for i, (dim, w) in enumerate(ov["weights"].items()):
            s = (scores or {}).get(dim)
            rows.append({"id": f"SC-{i + 1:04d}", "purpose": "investment", "dimension": dim, "weight": w, "applicability": "applicable",
                         "confidence": "high" if s else "unknown", "coverage_status": "sufficient" if s else "missing",
                         **({"score": s, "anchor": "锚点", "evidence_ids": ["ev-0001"]} if s else {"reason": "证据不足"})})
        p = {"purpose": "investment", "scoring_enabled": True, "scoring_override": {"reason": "用户确认", **ov}, **project}
        return base_data(project=p, scorecard=rows)

    def test_states(self):
        self.assertEqual(dscore.score(base_data(project={}))["status"], "purpose_pending")
        self.assertEqual(dscore.score(base_data(project={"purpose": "company_research", "scoring_enabled": True}))["errors"],
                         ["公司研究不能启用评分或发布分数"])
        self.assertEqual(dscore.score(base_data(project={"purpose": "investment"}))["status"], "disabled")
        self.assertEqual(dscore.score(base_data(project={"purpose": "investment", "scoring_enabled": True}))["status"], "criteria_pending")

    def test_publish_and_insufficient(self):
        full = {d: 4 for d in dscore.DIMENSIONS}
        r = dscore.score(self.data(full))
        self.assertEqual((r["status"], r["overall_score"]), ("complete", 4.0))
        r = dscore.score(self.data({"business": 4, "growth": 4, "governance": 4, "compliance": 4, "technology": 4, "operations": 4, "deal": 4}))
        self.assertEqual((r["status"], r["missing_critical"]), ("insufficient_evidence", ["financial"]))
        d = self.data(full)
        d["gaps"] = [{"id": "G-0001", "status": "open", "materiality": "critical"}]
        self.assertEqual(dscore.score(d)["status"], "insufficient_evidence")

    def test_invalid_rows_and_published_mismatch(self):
        d = self.data({d: 4 for d in dscore.DIMENSIONS})
        d["scorecard"][0]["confidence"] = "low"
        self.assertIn("置信度为高或中", "\n".join(dscore.score(d)["errors"]))
        d = self.data({d: 4 for d in dscore.DIMENSIONS}, published_score=3.5)
        self.assertIn("published_score", "\n".join(dscore.score(d)["errors"]))


class ContentTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.task = pathlib.Path(self.tmp.name) / "task"
        shutil.copytree(pathlib.Path(TEMPLATE.name) / "task", self.task)
        _, self.data = dcore.load(self.task)
        self.content = copy.deepcopy(F.CONTENT)

    def tearDown(self):
        self.tmp.cleanup()

    def errors(self, content=None):
        return "\n".join(dcontent.validate(content or self.content, self.data, self.task)["errors"])

    def block(self, sid, n):
        return next(s for s in self.content["sections"] if s["id"] == sid)["blocks"][n - 1]

    def chart(self, **kw):
        c = self.block("financial-performance", 2)
        c.update(kw)
        return self.errors()

    def test_fixture_passes(self):
        self.assertEqual(self.errors(), "")

    def test_chart_rules(self):
        self.assertIn("没有闭合", self.chart(chart_type="waterfall", points=[{"label": "期初", "value": 100, "role": "start"}, {"label": "增加", "value": 50, "role": "delta"},
                                                                        {"label": "期末", "value": 160, "role": "total"}]))
        self.assertIn("不画中点", self.chart(chart_type="range", points=[{"label": "价格带", "low": 1, "high": 3, "value": 2}]))
        self.assertIn("scale_max 必须是 100", self.chart(chart_type="proportion", unit="%", scale_max=50, points=[{"label": "占比", "value": 30}]))
        self.assertIn("分项标签和顺序要一致", self.chart(chart_type="stacked_bar", points=[
            {"label": "2024", "parts": [{"label": "设备", "value": 1}, {"label": "订阅", "value": 2}]},
            {"label": "2025", "parts": [{"label": "订阅", "value": 1}, {"label": "设备", "value": 2}]}]))
        self.assertIn("不能写 0", self.chart(points=[{"label": "2024", "value": "未披露"}, {"label": "2025", "value": 5600}]))

    def test_kind_and_evidence_attributes(self):
        Ledger(self.task).patch("evidence", "ev-0007", {"attribute": "forecast"})
        _, self.data = dcore.load(self.task)
        self.assertIn("实际数据点「2024」不能引用预测或估算证据", self.errors())
        self.assertIn("每个点都要自带 kind", self.chart(kind="mixed"))

    def test_diagram_rules(self):
        self.block("business-model", 2).clear()
        self.block("business-model", 2).update({"type": "diagram", "title": "业务模式图", "purpose": "business_model", "period": "2025", "entity_id": "ENT-0001",
                                                "note": "示意", "nodes": [{"id": "a", "label": "公司", "text": "设备", "evidence_ids": ["ev-0006"]},
                                                                         {"id": "b", "label": "客户", "text": "代工厂", "evidence_ids": ["ev-0005"]},
                                                                         {"id": "c", "label": "孤立", "text": "x", "basis": "unknown"}],
                                                "edges": [{"source": "a", "target": "b", "flow": "product", "label": "设备", "evidence_ids": ["ev-0006"]},
                                                          {"source": "a", "target": "a", "flow": "money", "label": "自连", "evidence_ids": ["ev-0006"]}]})
        text = self.errors()
        self.assertIn("不能自连接", text)
        self.assertIn("节点 c 是孤立节点", text)

    def test_image_rules(self):
        imgs = self.task / "03d_diligence" / "materials" / "images"
        (imgs / "logo.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 10)
        (imgs / "fake.png").write_bytes(b"<svg></svg>")
        outside = pathlib.Path(self.tmp.name) / "outside.png"
        outside.write_bytes(b"\x89PNG\r\n\x1a\n")
        (imgs / "link.png").symlink_to(outside)
        def img(path, captured="2026-10-18"):
            return {"type": "image", "role": "logo", "path": path, "title": "Logo", "alt": "公司 Logo", "caption": "官网 Logo", "source_url": "",
                    "captured_at": captured, "usage_note": "仅内部研究", "evidence_ids": ["ev-0001"]}
        sec = self.content["sections"][0]["blocks"]
        sec.append(img("03d_diligence/materials/images/logo.png", captured="2026-10-25"))
        sec.append(img("03d_diligence/materials/images/fake.png"))
        sec.append(img("03d_diligence/materials/images/link.png"))
        sec.append(img("../outside.png"))
        r = dcontent.validate(self.content, self.data, self.task)
        text = "\n".join(r["errors"])
        self.assertIn("只能是 PNG、JPEG 或 WebP", text)
        self.assertIn("符号链接逃逸", text)
        self.assertIn("不能含 ..", text)
        self.assertIn("图片取得日期晚于基准日", "\n".join(r["warnings"]))

    def test_cross_block_rules(self):
        self.content["sections"][1]["blocks"].append(copy.deepcopy(self.block("products-customers", 1)))      # offering 出现两次
        self.block("business-model", 2)["purpose"] = "other"                                                 # 没有业务模式图了
        people = self.content["sections"][1]["blocks"].pop(0)
        self.content["sections"][0]["blocks"].append(people)                                                 # 人物卡进了 identity 那章
        text = self.errors()
        self.assertIn("offering 要恰好出现一次", text)
        self.assertIn("至少要有一张业务模式图", text)
        self.assertIn("人物卡不能和 identity 在同一章", text)

    def test_structure_rules(self):
        c = copy.deepcopy(self.content)
        c["sections"][0]["id"] = "overview"
        c["sections"][1]["title"] = "资料请求清单"
        c["summary"] = "{{待填写}}"
        c["version"] = "1.1"
        text = self.errors(c)
        for word in ("保留名", "过程性标题", "占位", "1.2"):
            self.assertIn(word, text)

    def test_visual_hints(self):
        c = copy.deepcopy(self.content)
        c["sections"][-1]["blocks"] = [{"type": "text", "text": "很长的文字。" * 120}]
        for i in range(2):
            c["sections"][4]["blocks"].append(dict(copy.deepcopy(self.block("financial-performance", 2)), title=f"图{i}"))
        rules = {h["rule"] for h in dcontent.visual_hints(c)}
        self.assertIn("long_prose_run", rules)
        self.assertIn("single_chart_type", rules)

    def test_after_split_and_manual(self):
        bm = [{"block_id": bid} for bid, _, _ in dcontent.block_ids(self.content)]
        slides = {"slides": [{"page": 2, "section": "01", "block_ids": ["company-profile-1", "company-profile-3", "nonexistent-1"]},
                             {"page": 3, "section": "02", "block_ids": ["company-profile-2", "founders-team-1"]}]}
        text = "\n".join(dcontent.after_split(self.content, bm, slides, self.data, self.task))
        self.assertIn("不存在的内容块 nonexistent-1", text)
        self.assertIn("内容块 business-model-1 没有落到任何页上", text)
        self.assertIn("公司时间线 company-profile-2 不再和 identity 同章", text)
        data = dict(self.data, reviews=[])
        self.assertIn("没有 22 条人工清单的记录", dcontent.manual_errors(data)[0])


class PlanAuditTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.task = pathlib.Path(self.tmp.name) / "task"
        shutil.copytree(pathlib.Path(TEMPLATE.name) / "task", self.task)
        self.led = Ledger(self.task)

    def tearDown(self):
        self.tmp.cleanup()

    def test_plan_trimming_by_depth(self):
        _, data = dcore.load(self.task)
        quick = dplan.build(data)
        data["project"]["diligence_depth"] = "Deep"
        deep = dplan.build(data)
        self.assertLess(len(quick["tasks"]), len(deep["tasks"]))
        self.assertTrue(all(t["status"] == "not_executed" for t in quick["tasks"]))
        types = [t["type"] for t in quick["tasks"]]
        self.assertEqual(types[:1], ["claim_verification"])
        self.assertEqual(types.count("official_site_page"), 8)
        queries = [t.get("query") for t in deep["tasks"] if t.get("query")]
        self.assertEqual(len(queries), len(set(queries)))

    def test_audit_sections_and_module_errors(self):
        _, data = dcore.load(self.task)
        d = dcore.derive(data)
        text, errors = daudit.build(self.task, data, d, F.CONTENT)
        self.assertEqual(text.count("\n## "), 10)                 # Quick 10 节
        for word in ("元信息", "执行摘要", "研究完成范围", "研报覆盖", "信息缺口", "下一步", "证据附录"):
            self.assertIn(word, text)
        data["project"]["diligence_depth"] = "Standard"
        (self.task / "03d_diligence" / "modules" / "01-extra.md").write_text("重复", encoding="utf-8")
        (self.task / "03d_diligence" / "modules" / "02-module.md").unlink()
        text, errors = daudit.build(self.task, data, d, F.CONTENT)
        self.assertEqual(text.count("\n## "), 20)
        self.assertIn("模块 01 有多个文件", errors[0])
        self.assertIn("【缺口：模块 02 还没有分析文件】", text)


if __name__ == "__main__":
    unittest.main()
