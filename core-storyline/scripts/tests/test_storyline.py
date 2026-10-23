"""storyline.py 的测试：完整故事线包通过，以及每条机器规则的拦截（设计 §5.3、能力清单 C–F、J 节）。夹具全部虚构。"""
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

SCRIPTS = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
import storyline as S  # noqa: E402
from tools.tests import fixtures as F  # noqa: E402

TEMPLATE = tempfile.TemporaryDirectory()
F.make_storyline_package(pathlib.Path(TEMPLATE.name) / "task")


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.task = pathlib.Path(self.tmp.name) / "task"
        shutil.copytree(pathlib.Path(TEMPLATE.name) / "task", self.task)
        self.s = self.task / "07_storyline"

    def tearDown(self):
        self.tmp.cleanup()

    def edit(self, name, old, new, count=1):
        p = self.s / name
        text = p.read_text(encoding="utf-8")
        self.assertEqual(text.count(old), count, f"{name} 里找不到：{old}")
        p.write_text(text.replace(old, new), encoding="utf-8")
        if name == "04_manuscript.md":
            S.main(["clean", str(self.task)])

    def slides(self, change):
        doc = json.loads((self.s / "slides.json").read_text(encoding="utf-8"))
        change(doc)
        (self.s / "slides.json").write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")

    def run_check(self, stage=6, numbers=True):
        return S.check(self.task, stage, numbers)

    def codes(self, r, kind="errors"):
        return [i["code"] for i in r[kind]]

    def messages(self, r, kind="errors"):
        return "\n".join(i["message"] for i in r[kind])


class PackageTest(Base):
    def test_complete_package_passes(self):
        r = self.run_check()
        self.assertEqual(r["errors"], [])
        self.assertEqual(r["info"]["coverage"]["a_placed"], 1)
        self.assertEqual(r["info"]["numbers"]["unknown"], 0)
        self.assertGreater(r["info"]["numbers"]["checked"], 10)
        self.assertEqual(self.codes(r, "warnings"), ["backup"])     # 阅读型备用页不足只提示

    def test_stage_gating(self):
        (self.s / "04_manuscript.md").unlink()
        self.assertNotIn("missing-file", self.codes(self.run_check(stage=3)))
        self.assertIn("缺少 04_manuscript.md", self.messages(self.run_check(stage=4)))

    def test_slides_without_storyboard(self):
        (self.s / "05_storyboard.md").unlink()
        self.assertIn("有 06_slides.md 但没有 05_storyboard.md", self.messages(self.run_check()))

    def test_manuscript_only_mode(self):
        for name in ("05_storyboard.md", "06_slides.md", "slides.json"):
            (self.s / name).unlink()
        r = self.run_check()
        self.assertEqual(r["info"]["mode"], "内容稿")
        self.assertEqual(r["errors"], [])

    def test_brief_materials_and_confirmation(self):
        self.edit("00_story-brief.md", "| 保密 | 内部使用 |\n", "")
        self.edit("01_materials_index.md", "读完（含附录）", "已读前 20 页")
        self.edit("01_materials_index.md", "| M001 |", "| M009 |")
        side = json.loads((self.s / "sidecar.json").read_text(encoding="utf-8"))
        side["confirmation_points"][0]["status"] = "pending"
        (self.s / "sidecar.json").write_text(json.dumps(side, ensure_ascii=False), encoding="utf-8")
        text = self.messages(self.run_check())
        self.assertIn("缺少「保密」", text)
        self.assertIn("长文档，处理状态要写读到哪", text)
        self.assertIn("M009 不在证据账的来源表里", text)
        self.assertIn("主线选择还没确认", text)

    def test_unprocessed_material(self):
        self.edit("01_materials_index.md", "读完（含附录）", "未处理")
        self.assertIn("还是「未处理」", self.messages(self.run_check()))


class CardsTest(Base):
    def test_cards_view_must_match_ledger(self):
        F.Ledger(self.task).patch("cards", "card-0002", {"content": "改过的内容"})
        self.assertIn("cards-view", self.codes(self.run_check()))
        S.main(["cards", str(self.task)])
        self.assertNotIn("cards-view", self.codes(self.run_check()))
        self.assertIn("### card-0002", (self.s / "02_info_cards.md").read_text(encoding="utf-8"))

    def test_rendered_view_derives_nature_from_claim(self):
        view = (self.s / "02_info_cards.md").read_text(encoding="utf-8")
        self.assertIn("- 性质：事实（取自主张 cl-0001）", view)
        self.assertIn("| 收入 | 营业收入（合并口径） | 收入 | 不含其他收益 |", view)                # 术语表并入

    def test_calibration_and_id_gap(self):
        led = F.Ledger(self.task)
        for i in range(17):
            led.add("cards", {"type": "fact", "content": f"事实 {i}", "meaning": "支撑主线", "value_tier": "A", "topic": "收入", "claim_id": "cl-0001"})
        led.patch("cards", "card-0004", {"value_tier": "C"})
        S.main(["cards", str(self.task)])
        self.assertIn("grade-calibration", self.codes(self.run_check(), "warnings"))
        rows = [json.loads(x) for x in (self.task / "03_evidence/ledger/cards.jsonl").read_text(encoding="utf-8").splitlines()]
        (self.task / "03_evidence/ledger/cards.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows if r["id"] != "card-0005") + "\n",
                                                                 encoding="utf-8")
        S.main(["cards", str(self.task)])
        self.assertIn("card-0005", self.messages(self.run_check(), "warnings"))

    def test_derived_card_needs_estimate_claim(self):
        F.Ledger(self.task).patch("cards", "card-0003", {"derived_from": ["card-0001"]})
        S.main(["cards", str(self.task)])
        self.assertIn("derived-card", self.codes(self.run_check()))


class CoverageTest(Base):
    def test_a_card_without_placement(self):
        self.edit("04_manuscript.md", "card-0001", "card-0003", count=2)
        self.edit("06_slides.md", "〔card-0001｜M001 p12〕", "")
        self.edit("06_slides.md", "增长 77.8%〔card-0001〕", "增长 77.8%")
        r = self.run_check(numbers=False)
        self.assertIn("A 级 card-0001 只在审计报告里登记", self.messages(r))

    def test_planned_only_and_nowhere(self):
        self.edit("04_manuscript.md", "〔card-0003〕", "", count=2)
        self.edit("06_slides.md", "〔card-0003〕", "")
        r = self.run_check(numbers=False)
        self.assertIn("B 级 card-0003 只在故事线里挂名", self.messages(r, "warnings"))   # 来源字段不算安置
        self.edit("03_storyline.md", "card-0003", "—")
        self.assertIn("B 级 card-0003 没有去向", self.messages(self.run_check(numbers=False), "warnings"))

    def test_c_card_and_dangling_reference(self):
        self.edit("04_manuscript.md", "只使用公司年报；", "只使用公司年报〔card-0004〕；〔card-0099〕")
        text = self.messages(self.run_check(numbers=False))
        self.assertIn("card-0004 是 C 级卡片", text)
        self.assertIn("不存在的卡片 card-0099", text)


class NumbersTest(Base):
    def chapter(self, sentence):
        """把第一章的第二句换成 sentence（每次都从原始母版换），返回检查结果。"""
        original = (pathlib.Path(TEMPLATE.name) / "task/07_storyline/04_manuscript.md").read_text(encoding="utf-8")
        (self.s / "04_manuscript.md").write_text(original.replace("增长主要发生在 2025 年。", sentence), encoding="utf-8")
        S.main(["clean", str(self.task)])
        return self.run_check()

    def test_unknown_number(self):
        r = self.chapter("另一渠道收入 3300 万元〔card-0001｜M001 p12〕。")
        self.assertIn("3300万元 不在事实库里", self.messages(r))

    def test_rounding_magnitude_and_sign(self):
        self.assertNotIn("number-unknown", self.codes(self.chapter("合计约 0.32 亿元，增长 77.78%〔card-0001｜M001 p12〕。")))
        self.assertIn("number-unknown", self.codes(self.chapter("增长 -77.8%〔card-0001｜M001 p12〕。")))

    def test_judgment_marker_must_be_adjacent_with_basis(self):
        r = self.chapter("2027 年预计 5000 万元（推断｜依据 card-0002）〔card-0002｜M001 p30〕。")
        self.assertIn("number-judgment", self.codes(r, "warnings"))
        self.assertEqual(self.codes(r), [])
        self.assertIn("判断类标记要紧挨数字并写明依据", self.messages(self.chapter("预计明年继续增长，规模到 5000 万元〔card-0002｜M001 p30〕。")))

    def test_mismatch_and_uncited(self):
        r = self.chapter("2026 年约 4100 万元〔card-0001｜M001 p12〕。另有 2600 万元订单。")
        self.assertIn("number-mismatch", self.codes(r, "warnings"))
        self.assertIn("2600万元 没有引用卡片", self.messages(r, "warnings"))

    def test_appendix_numbers_are_not_flagged_as_uncited(self):
        self.edit("04_manuscript.md", "| M001 | 星河数据科技 2025 年年报 |", "| M001 | 星河数据科技 2025 年年报 |\n\n共 1 份来源，合计 86 页。")
        self.assertNotIn("number-uncited", self.codes(self.run_check(), "warnings"))

    def test_dates_ranges_and_small_integers(self):
        self.assertEqual(self.codes(self.chapter("2025 年 3 月起加速，第 2 季度最快〔card-0001｜M001 p12〕。")), [])
        self.assertIn("number-unknown", self.codes(self.chapter("区间为 1200–1500 万元〔card-0001｜M001 p12〕。")))
        self.assertIn("number-unknown", self.codes(self.chapter("来自 3 家客户〔card-0001｜M001 p12〕。")))

    def test_meaning_numbers_do_not_enter_library(self):
        F.Ledger(self.task).patch("cards", "card-0001", {"meaning": "相当于新增 1400 万元"})
        S.main(["cards", str(self.task)])
        self.assertIn("1400万元 不在事实库里", self.messages(self.chapter("新增 1400 万元〔card-0001｜M001 p12〕。")))

    def test_number_check_on_pages_and_switch(self):
        self.edit("06_slides.md", "- 收入从 1800 万元增至 3200 万元", "- 收入从 1800 万元增至 3300 万元")
        S.main(["sync", str(self.task)])
        self.assertIn("06_slides.md 第 2 页", self.messages(self.run_check()))
        self.assertNotIn("number-unknown", self.codes(self.run_check(numbers=False)))

    def test_units(self):
        found = [(raw, unit) for _, raw, unit, _ in S.numbers_in("下降 25bp，坏账率 3‰，单价 12000 元/平方米，营收 2.5 bn")]
        self.assertEqual(found, [("25", "bp"), ("3", "‰"), ("12000", "元/平方米"), ("2.5", "bn")])


class ManuscriptTest(Base):
    def test_clean_version(self):
        master = "收入 3200 万元〔card-0001｜M001 p12〕，预计增长（推断｜依据 card-0002）【待补充：留存数据】。"
        self.assertEqual(S.clean_text(master), "收入 3200 万元，预计增长（推断｜依据 card-0002）【待补充：留存数据】。")
        p = self.s / "04_manuscript_clean.md"
        p.write_text(p.read_text(encoding="utf-8").replace("3200 万元", "3300 万元", 1), encoding="utf-8")
        self.assertIn("clean-drift", self.codes(self.run_check()))

    def test_summary_rules(self):
        self.edit("04_manuscript.md", "我们建议先核实", "【待补充：留存】我们建议先核实")
        self.assertIn("执行摘要里不能出现【待补充】", self.messages(self.run_check()))
        text = (self.s / "04_manuscript.md").read_text(encoding="utf-8")
        start, end = text.index("## 执行摘要") + 8, text.index("## 一、")
        (self.s / "04_manuscript.md").write_text(text[:start] + "\n收入增长很快〔card-0001｜M001 p12〕。\n\n" + text[end:], encoding="utf-8")
        S.main(["clean", str(self.task)])
        self.assertIn("要在 200–400 字之间", self.messages(self.run_check()))

    def test_required_chapters_and_cliches(self):
        self.edit("04_manuscript.md", "## 补齐路径", "## 后续工作")
        self.edit("04_manuscript.md", "只使用公司年报；", "只使用公司年报，进一步赋能判断；")
        r = self.run_check()
        self.assertIn("缺少「补齐路径」一节", self.messages(r))
        self.assertIn("「赋能」", self.messages(r, "warnings"))


class SlidesTest(Base):
    def test_titles_types_and_closing(self):
        self.edit("06_slides.md", "## P03 ｜ 02 建议 ｜ 建议", "## P03 ｜ 02 建议 ｜ 观点+证据")
        self.edit("06_slides.md", "**行动标题**：收入两年增长 77.8%，规模仍小",
                  "**行动标题**：收入两年增长 77.8%，规模仍小，而且客户集中度较高，需要关注续约")
        r = self.run_check()
        self.assertIn("主 deck 最后一页（封底之前）必须是建议或下一步页", self.messages(r))
        self.assertIn("title-length", self.codes(r, "warnings"))
        self.edit("06_slides.md", "｜ 观点+证据", "｜ 观点页")
        self.assertIn("page-type", self.codes(self.run_check()))

    def test_presentation_backup_and_page_limit(self):
        def change(doc):
            doc["deck"]["kind"] = "presentation"
            doc["deck"]["page_limit"] = 3
        self.slides(change)
        r = self.run_check()
        self.assertIn("backup", self.codes(r))
        self.assertIn("超过上限 3 页", self.messages(r))

    def test_arc_and_story_mode(self):
        self.slides(lambda d: d["deck"].update(arc="problem-to-fix"))
        self.assertIn("arc 应为 evidence-to-view", self.messages(self.run_check()))
        self.slides(lambda d: d["deck"].update(story_mode="industry_research", arc="evidence-to-view"))
        self.assertIn("与 03_storyline.md 的故事线模式不一致", self.messages(self.run_check()))

    def test_sync_drift_and_fix(self):
        self.edit("06_slides.md", "**行动标题**：谢谢", "**行动标题**：谢谢阅读")
        self.assertIn("运行 storyline.py sync", self.messages(self.run_check()))
        self.assertEqual(S.main(["sync", str(self.task)]), 0)
        self.assertEqual(self.run_check()["errors"], [])
        self.assertEqual(json.loads((self.s / "slides.json").read_text(encoding="utf-8"))["slides"][3]["action_title"], "谢谢阅读")

    def test_backup_page_needs_trigger_and_return(self):
        self.edit("06_slides.md", "## P04 ｜ — ｜ 结尾", "## P05 ｜ — ｜ 备用\n**行动标题**：客户集中度高吗？\n**正文**：\n- 年报没有披露\n\n## P04 ｜ — ｜ 结尾")
        self.slides(lambda d: d["slides"].append({"page": 5, "type": "backup", "action_title": "客户集中度高吗？", "page_role": "appendix", "story_beat": "risk"}))
        self.assertEqual(S.main(["sync", str(self.task)]), 1)
        self.assertIn("要写「触发」", self.messages(self.run_check()))


class CliTest(Base):
    def test_cli_outputs(self):
        cmd = [sys.executable, str(SCRIPTS / "storyline.py")]
        titles = subprocess.run(cmd + ["check", str(self.task), "--titles"], capture_output=True, text=True)
        self.assertEqual(titles.returncode, 0)
        self.assertIn("P02 收入两年增长 77.8%，规模仍小", titles.stdout)
        ok = subprocess.run(cmd + ["check", str(self.task), "--json"], capture_output=True, text=True)
        self.assertTrue(json.loads(ok.stdout)["passed"])
        self.edit("00_story-brief.md", "| 受众 |", "| 读者 |")
        self.assertEqual(subprocess.run(cmd + ["check", str(self.task)], capture_output=True, text=True).returncode, 1)

    def test_impact(self):
        r = S.impact(self.task, "card-0002")
        self.assertEqual(r["report_pages"], [3])
        self.assertEqual(r["pages"][0]["page"], 3)
        self.assertEqual(len(r["manuscript"]), 2)


if __name__ == "__main__":
    unittest.main()
