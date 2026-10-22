import json
import pathlib
import subprocess
import tempfile
import unittest

from tools.lib import ledger as L

ROOT = pathlib.Path(__file__).resolve().parents[2]
SHA = "a" * 64


def source(**over):
    r = {"origin": "web", "title": "年报", "url": "https://example.com/a", "published_precision": "day", "published": "2026-03-01",
         "accessed": "2026-10-22T10:00:00+08:00", "tier": "primary", "grade": "S", "capture_method": "script", "access": "full",
         "original_files": [{"path": "raw/files/M001-a.pdf", "sha256": SHA}]}
    r.update(over)
    return r


def evidence(**over):
    r = {"source_id": "M001", "locator": "p12", "excerpt": "收入 120 万元", "attribute": "actual", "numeric": False}
    r.update(over)
    return r


def claim(**over):
    r = {"kind": "fact", "statement": "公司收入为 120 万元", "scope": "consolidated", "period": "2025 全年", "population": "公司",
         "unit": "万元", "denominator": "不适用：单值", "calculation": "不适用：原文", "inference": "不证明利润增加",
         "limitation": "只有一份年报", "verification": "verified", "confidence": "high", "confidence_reason": "一手来源",
         "affects_conclusion": True, "materiality": "major"}
    r.update(over)
    return r


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.task = pathlib.Path(self.tmp.name) / "task"
        self.led = L.Ledger(self.task)
        self.led.init()

    def tearDown(self):
        self.tmp.cleanup()

    def basic(self):
        self.led.add("sources", source(), line="M")
        self.led.add("evidence", evidence())
        self.led.add("claims", claim())
        self.led.add("claim_evidence", {"claim_id": "cl-0001", "evidence_id": "ev-0001", "relation": "supports", "applicable_scope": "合并口径"})

    def messages(self):
        return "\n".join(f"{i['table']}:{i['id']}:{i['message']}" for i in self.led.check())

    def errors(self):
        return [i for i in self.led.check() if i["level"] == "error"]


class WriteTest(Base):
    def test_init_creates_layout_and_project(self):
        for sub in ("ledger", "raw/sources", "raw/user", "data/curated", "analysis", "notes", "search-logs"):
            self.assertTrue((self.task / "03_evidence" / sub).is_dir(), sub)
        self.assertEqual(self.led.get("project", "project"), {"id": "project"})
        self.led.init()
        self.assertEqual(len(self.led.read("project")), 1)

    def test_add_assigns_ids(self):
        self.assertEqual(self.led.add("sources", source(), line="M"), "M001")
        self.assertEqual(self.led.add("sources", source(url="https://example.com/b"), line="M"), "M002")
        self.assertEqual(self.led.add("sources", source(origin="user", url=None), line="U"), "U001")
        self.assertEqual(self.led.add("evidence", evidence()), "ev-0001")
        self.assertEqual(self.led.next_id("evidence"), "ev-0002")

    def test_source_needs_valid_line(self):
        with self.assertRaises(L.LedgerError):
            self.led.add("sources", source())
        with self.assertRaises(L.LedgerError):
            self.led.add("sources", source(), line="C")

    def test_invalid_record_is_rejected_and_file_unchanged(self):
        self.basic()
        before = self.led.path("claims").read_text(encoding="utf-8")
        with self.assertRaises(L.LedgerError) as cm:
            self.led.add("claims", claim(kind="estimate"))
        self.assertIn("assumptions", str(cm.exception))
        self.assertEqual(self.led.path("claims").read_text(encoding="utf-8"), before)

    def test_duplicate_id_rejected(self):
        self.basic()
        with self.assertRaises(L.LedgerError):
            self.led.add("evidence", evidence(id="ev-0001"))

    def test_patch_keeps_other_fields(self):
        self.basic()
        merged = self.led.patch("claims", "cl-0001", {"confidence": "medium"})
        self.assertEqual(merged["confidence"], "medium")
        self.assertEqual(merged["statement"], "公司收入为 120 万元")
        self.assertEqual(self.led.get("claims", "cl-0001")["confidence"], "medium")

    def test_patch_none_removes_field_and_validates(self):
        self.basic()
        with self.assertRaises(L.LedgerError):
            self.led.patch("claims", "cl-0001", {"statement": None})
        self.led.patch("sources", "M001", {"revised_date": "2026-04-01"})
        self.led.patch("sources", "M001", {"revised_date": None})
        self.assertNotIn("revised_date", self.led.get("sources", "M001"))

    def test_patch_cannot_change_id_or_missing_record(self):
        self.basic()
        with self.assertRaises(L.LedgerError):
            self.led.patch("claims", "cl-0001", {"id": "cl-0009"})
        with self.assertRaises(L.LedgerError):
            self.led.patch("claims", "cl-0099", {"confidence": "low"})

    def test_backups_are_kept_and_capped(self):
        self.basic()
        for i in range(25):
            self.led.patch("claims", "cl-0001", {"confidence_reason": f"r{i}"})
        backups = list((self.led.dir / ".backup").glob("claims-*.jsonl"))
        self.assertEqual(len(backups), L.KEEP_BACKUPS)

    def test_unknown_table(self):
        with self.assertRaises(L.LedgerError):
            self.led.read("nope")

    def test_corrupt_file_is_reported(self):
        self.led.path("claims").write_text("{bad\n", encoding="utf-8")
        with self.assertRaises(L.LedgerError):
            self.led.read("claims")
        self.assertIn("不是合法 JSON", self.messages())


class MergeTest(Base):
    def stage(self, line, table, records):
        d = self.led.dir / "staging" / line
        d.mkdir(parents=True, exist_ok=True)
        with open(d / self.led.schema["tables"][table]["file"], "a", encoding="utf-8") as f:
            for r in records:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

    def test_merge_renumbers_and_rewrites_refs(self):
        self.basic()
        self.stage("A", "sources", [dict(source(url="https://example.com/z", research_line="A"), id="A001")])
        self.stage("A", "evidence", [dict(evidence(source_id="A001", research_line="A"), id="ev-0001")])
        self.stage("A", "claims", [dict(claim(statement="另一条"), id="cl-0001")])
        self.stage("A", "claim_evidence", [{"id": "ce-0001", "claim_id": "cl-0001", "evidence_id": "ev-0001", "relation": "supports", "applicable_scope": "x"}])
        counts = self.led.merge("A")
        self.assertEqual(counts, {"sources": 1, "evidence": 1, "claims": 1, "claim_evidence": 1})
        self.assertEqual(self.led.get("evidence", "ev-0002")["source_id"], "A001")
        self.assertEqual(self.led.get("claim_evidence", "ce-0002"), {"id": "ce-0002", "claim_id": "cl-0002", "evidence_id": "ev-0002", "relation": "supports", "applicable_scope": "x"})
        self.assertFalse((self.led.dir / "staging" / "A").exists())
        self.assertEqual(self.errors(), [])

    def test_merge_marks_duplicate_sources(self):
        self.basic()
        self.stage("A", "sources", [dict(source(research_line="A"), id="A001")])
        self.led.merge("A")
        self.assertEqual(self.led.get("sources", "A001")["duplicate_of"], "M001")

    def test_merge_rejects_reused_source_id(self):
        self.basic()
        self.stage("A", "sources", [dict(source(url="https://example.com/q"), id="M001")])
        with self.assertRaises(L.LedgerError):
            self.led.merge("A")
        self.assertTrue((self.led.dir / "staging" / "A").exists())

    def test_merge_without_staging(self):
        with self.assertRaises(L.LedgerError):
            self.led.merge("B")


class CheckTest(Base):
    def test_clean_ledger(self):
        self.basic()
        self.assertEqual(self.led.check(), [])

    def test_dangling_reference(self):
        self.basic()
        self.led.add("evidence", evidence(source_id="M001", cross_sources=["M009"]))
        self.assertIn("cross_sources 引用了不存在的 sources:M009", self.messages())

    def test_record_errors_and_duplicates_found_in_files(self):
        self.basic()
        with open(self.led.path("claims"), "a", encoding="utf-8") as f:
            f.write(json.dumps(dict(claim(), id="cl-0001")) + "\n")
            f.write(json.dumps({"id": "cl-0003", "kind": "fact"}) + "\n")
        m = self.messages()
        self.assertIn("claims:cl-0001:id 重复", m)
        self.assertIn("statement：必填", m)

    def test_kind_must_match_evidence_attribute(self):
        self.basic()
        self.led.add("evidence", evidence(attribute="forecast"))
        self.led.add("claims", claim(kind="data"))
        self.led.add("claim_evidence", {"claim_id": "cl-0002", "evidence_id": "ev-0002", "relation": "supports", "applicable_scope": "x"})
        self.assertIn("kind=data 的主张不能由 attribute=forecast", self.messages())

    def test_unreadable_source_cannot_be_evidence(self):
        self.basic()
        self.led.patch("sources", "M001", {"access": "metadata_only"})
        self.assertIn("无法读取（metadata_only）", self.messages())

    def test_retrospective_source_in_historical_study(self):
        self.basic()
        self.led.patch("project", "project", {"historical": True})
        self.led.patch("sources", "M001", {"time_scope": "retrospective"})
        self.assertIn("不能用事后资料", self.messages())

    def test_cross_entity_support_needs_bridge_and_estimate(self):
        self.basic()
        for name in ("集团", "子公司"):
            self.led.add("entities", {"legal_name": name, "entity_type": "legal_entity", "identity_status": "pending", "listing_status": "unknown"})
        self.led.patch("evidence", "ev-0001", {"entity_id": "ENT-0001"})
        self.led.patch("claims", "cl-0001", {"entity_id": "ENT-0002"})
        self.assertIn("必须写 bridge 且主张 kind=estimate", self.messages())
        self.led.patch("claims", "cl-0001", {"kind": "estimate", "assumptions": "按持股比例推算"})
        self.led.patch("claim_evidence", "ce-0001", {"bridge": "集团合并口径，子公司占比约 60%"})
        self.assertNotIn("bridge", self.messages())

    def test_refuted_needs_contradicting_evidence(self):
        self.basic()
        self.led.patch("claims", "cl-0001", {"verification": "refuted", "counterevidence": "审计报告不同"})
        self.assertIn("至少有一条 contradicts 证据", self.messages())

    def test_conflicting_needs_conflict_record(self):
        self.basic()
        self.led.patch("claims", "cl-0001", {"verification": "conflicting"})
        self.assertIn("必须在 conflicts 表里登记", self.messages())
        self.led.add("conflicts", {"claim_ids": ["cl-0001"], "evidence_ids": ["ev-0001"], "left_value_scope": "120 万元，合并", "right_value_scope": "100 万元，单体",
                                   "analysis": "口径不同", "status": "open", "decision_changing": False, "decision_impact": "无"})
        self.assertNotIn("conflicts 表", self.messages())

    def test_major_claim_must_affect_conclusion(self):
        self.basic()
        self.led.patch("claims", "cl-0001", {"affects_conclusion": False})
        self.assertIn("必须 affects_conclusion=true", self.messages())

    def test_card_rules(self):
        self.basic()
        self.led.add("cards", {"type": "data", "content": "收入 120 万元", "value_tier": "A", "topic": "收入", "meaning": "规模小"})
        self.led.add("cards", {"type": "case", "content": "案例", "value_tier": "B", "topic": "案例"})
        self.led.add("cards", {"type": "background", "content": "行业通识", "value_tier": "C", "topic": "背景", "nature": "fact",
                               "confidence": "low", "confidence_reason": "通识", "placement": [{"where": "chapter"}]})
        self.led.add("claims", claim(materiality="minor", affects_conclusion=False))
        self.led.add("cards", {"type": "fact", "content": "x", "value_tier": "A", "topic": "t", "meaning": "m", "claim_id": "cl-0002",
                               "placement": [{"where": "not_used"}]})
        m = self.messages()
        self.assertIn("cards:card-0001:A/B 级的数据、事实、观点、洞察、风险、建议类卡片必须关联主张", m)
        self.assertIn("cards:card-0002:A/B 级卡片必须填写含义", m)
        self.assertIn("cards:card-0002:没有关联主张的卡片应填写性质", m)
        self.assertIn("cards:card-0003:C 级卡片不能进入交付物", m)
        self.assertIn("cards:card-0004:A 级卡片关联的主张 cl-0002 必须 affects_conclusion=true", m)
        self.assertIn("cards:card-0004:A 级卡片不能“确认不用”", m)
        warnings = [i for i in self.led.check() if i["level"] == "warning"]
        self.assertTrue(all(i["table"] == "cards" for i in warnings))

    def test_metric_rules(self):
        self.led.add("metrics", {"unit": "万元", "decimals": 0, "status": "present"})
        self.led.add("metrics", {"unit": "万元", "decimals": 0, "status": "present", "value": 1, "formula": {"op": "sum", "args": ["m-0001"]}})
        self.led.add("metrics", {"unit": "万元", "decimals": 0, "status": "missing", "status_reason": "未披露", "value": 0})
        self.led.add("metrics", {"unit": "%", "decimals": 1, "status": "present", "formula": {"op": "divide", "args": ["m-0005", "m-0001"]}})
        self.led.add("metrics", {"unit": "%", "decimals": 1, "status": "present", "formula": {"op": "sum", "args": ["m-0004"]}})
        m = self.messages()
        self.assertIn("metrics:m-0001:有值的指标必须有 value 或 formula", m)
        self.assertIn("metrics:m-0002:value 和 formula 只能二选一", m)
        self.assertIn("metrics:m-0003:缺失的指标不能填值", m)
        self.assertIn("指标公式存在循环引用", m)

    def entity(self, name):
        return self.led.add("entities", {"legal_name": name, "entity_type": "legal_entity", "identity_status": "pending", "listing_status": "unknown"})

    def relation(self, parent, child, rtype="control", **over):
        r = {"parent_id": parent, "child_id": child, "relation_type": rtype, "control_basis": "持股", "effective_from": "2020-01-01",
             "state": "current", "verification": "verified", "evidence_ids": ["ev-0001"]}
        r.update(over)
        return self.led.add("relations", r)

    def test_relation_rules(self):
        self.basic()
        a, b = self.entity("甲"), self.entity("乙")
        self.relation(a, a)
        self.relation(a, b, effective_to="2019-01-01")
        m = self.messages()
        self.assertIn("不能自己控制自己", m)
        self.assertIn("effective_to 必须晚于 effective_from", m)

    def test_control_cycle_and_joint_control_option(self):
        self.basic()
        a, b = self.entity("甲"), self.entity("乙")
        self.relation(a, b)
        self.relation(b, a, rtype="joint_control")
        self.assertNotIn("存在环", self.messages())
        self.led.patch("project", "project", {"joint_control_triggers": True})
        self.assertIn("现行且已核实的控制关系存在环", self.messages())

    def test_coverage_pointer_consistency(self):
        self.basic()
        ent = self.entity("甲")
        rr = self.led.add("research_reports", {"source_id": "M001", "publisher": "某券商", "title": "深度", "categories": ["company_deep"],
                                                "category_relevance": {"company_deep": "直接"}, "target_id": ent, "coverage_entity_id": ent,
                                                "report_date": "2026-09-01", "version": "1", "access_status": "full", "reading_status": "unread",
                                                "relevance": "direct"})
        self.led.add("coverage", {"target_id": ent, "research_entity_id": ent, "category": "company_deep", "required": True, "reason": "上市",
                                  "search_status": "found", "latest_read_ids": [rr], "event_coverage": "not_applicable", "gate_status": "partial"})
        self.assertIn("latest_read_ids 指向 RR-0001，但对方的 latest_read_for 没有反向登记", self.messages())
        self.led.patch("research_reports", rr, {"latest_read_for": ["RC-0001"], "latest_fulltext_for": ["RC-0001"]})
        m = self.messages()
        self.assertNotIn("latest_read", m)
        self.assertIn("latest_fulltext_for 指向 RC-0001，但对方的 latest_fulltext_ids 没有登记", m)

    def test_date_order_and_self_reference(self):
        self.basic()
        self.led.patch("sources", "M001", {"revised_date": "2026-01-01", "supersedes": "M001"})
        self.led.add("evidence", evidence(numeric=True, value=1, unit="万元", period_start="2025-12-31", period_end="2025-01-01",
                                         geography="中国", currency="CNY", accounting_basis="CAS", scope="consolidated"))
        m = self.messages()
        self.assertIn("published 不能晚于 revised_date", m)
        self.assertIn("supersedes 不能指向自己", m)
        self.assertIn("period_start 不能晚于 period_end", m)

    def test_has_cycle(self):
        self.assertFalse(L.has_cycle([("a", "b"), ("b", "c")]))
        self.assertTrue(L.has_cycle([("a", "b"), ("b", "c"), ("c", "a")]))
        self.assertFalse(L.has_cycle([]))


class RenderAndCliTest(Base):
    def test_render_outputs(self):
        self.basic()
        self.led.add("search_log", {"searched_at": "2026-10-22T09:00:00+08:00", "tool": "WebSearch", "query": "示例 年报", "research_line": "M",
                                    "status": "found", "opened_source_ids": ["M001"], "discarded": [{"target": "https://x", "reason": "irrelevant"}]})
        self.led.render()
        ev = self.task / "03_evidence"
        self.assertIn("| cl-0001 | 事实 | 已核实 | 是 |", (ev / "ledger.md").read_text(encoding="utf-8"))
        note = (ev / "notes" / "M.md").read_text(encoding="utf-8")
        self.assertIn("- 来源: `M001` · 定位: p12", note)
        self.assertIn("  > 收入 120 万元", note)
        log = (ev / "search-logs" / "M.md").read_text(encoding="utf-8")
        self.assertIn("- 查询原文: `示例 年报`", log)
        self.assertIn("https://x（无关）", log)

    def cli(self, *args):
        return subprocess.run(["python3", str(ROOT / "tools" / "lib" / "ledger.py"), str(self.task), *args], capture_output=True, text=True)

    def test_cli(self):
        self.basic()
        p = self.cli("check")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("错误 0 个", p.stdout)
        self.assertEqual(self.cli("next-id", "claims").stdout.strip(), "cl-0002")
        self.assertEqual(self.cli("next-id", "sources", "--line", "A").stdout.strip(), "A001")
        self.led.patch("claims", "cl-0001", {"verification": "conflicting"})
        p = self.cli("check", "--json")
        self.assertEqual(p.returncode, 1)
        self.assertEqual(json.loads(p.stdout)["errors"], 1)
        self.assertEqual(self.cli("merge", "Z").returncode, 2)


class RuleConstantsTest(unittest.TestCase):
    """ledger.py 规则里写到的枚举值必须都在 schema 里（设计 §8.2：枚举来自 schema）。"""

    def test_constants_are_schema_values(self):
        enums = L.schema_check.load("ledger.schema.json")["enums"]
        values = lambda name: set(enums[name]["values"])
        self.assertLessEqual(L.CONTROL_TYPES | {"joint_control"}, values("relation_type"))
        self.assertLessEqual(L.CLAIM_CARD_TYPES, values("card_type"))
        self.assertLessEqual(L.DELIVERABLE_PLACEMENTS | {"not_used"}, values("placement"))
        self.assertLessEqual(L.UNREADABLE_ACCESS, values("access"))
        self.assertLessEqual(set(L.KIND_ATTRIBUTES), values("claim_kind"))
        self.assertLessEqual(set().union(*L.KIND_ATTRIBUTES.values()), values("attribute"))

if __name__ == "__main__":
    unittest.main()
