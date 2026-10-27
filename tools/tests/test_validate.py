import pathlib
import shutil
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]


def copy_repo(dst):
    shutil.copytree(ROOT, dst, ignore=shutil.ignore_patterns(".git", "node_modules", ".font-venv", "__pycache__", ".probe-task"))


class ValidateTest(unittest.TestCase):
    def run_validate(self, root):
        return subprocess.run(["python3", str(root / "tools" / "validate.py")], capture_output=True, text=True)

    def test_repo_passes(self):
        p = self.run_validate(ROOT)
        self.assertEqual(p.returncode, 0, p.stdout)

    def test_tampered_vendor_file_fails(self):
        with tempfile.TemporaryDirectory() as t:
            copy = pathlib.Path(t) / "repo"
            copy_repo(copy)
            with open(copy / "vendor" / "onepager" / "LICENSE.txt", "a", encoding="utf-8") as f:
                f.write("tamper\n")
            p = self.run_validate(copy)
            self.assertEqual(p.returncode, 1)
            self.assertIn("vendor：文件被改动：onepager/LICENSE.txt", p.stdout)

    def test_missing_lock_fails(self):
        with tempfile.TemporaryDirectory() as t:
            copy = pathlib.Path(t) / "repo"
            copy_repo(copy)
            (copy / "vendor" / "vendor.lock").unlink()
            p = self.run_validate(copy)
            self.assertEqual(p.returncode, 1)
            self.assertIn("vendor：缺少", p.stdout)

    def test_unknown_token_in_core_evidence_docs_fails(self):
        with tempfile.TemporaryDirectory() as t:
            copy = pathlib.Path(t) / "repo"
            copy_repo(copy)
            with open(copy / "core-evidence" / "references" / "source-tiers.md", "a", encoding="utf-8") as f:
                f.write("\n多余的 `foo_bar` 词\n")
            p = self.run_validate(copy)
            self.assertEqual(p.returncode, 1)
            self.assertIn("`foo_bar` 不是 ledger schema 里的字段、表名或枚举值", p.stdout)

    def test_broken_schema_fails(self):
        with tempfile.TemporaryDirectory() as t:
            copy = pathlib.Path(t) / "repo"
            copy_repo(copy)
            f = copy / "tools" / "lib" / "schema" / "sidecar.schema.json"
            f.write_text(f.read_text(encoding="utf-8").replace('"enum": "confirmation_stage"', '"enum": "nope"'), encoding="utf-8")
            p = self.run_validate(copy)
            self.assertEqual(p.returncode, 1)
            self.assertIn("引用了不存在的枚举 nope", p.stdout)

    def test_does_not_need_zerox_lock(self):
        self.assertFalse((ROOT / "zerox.lock").exists())

    def test_reference_to_zerox_skill_fails(self):
        with tempfile.TemporaryDirectory() as t:
            copy = pathlib.Path(t) / "repo"
            copy_repo(copy)
            with open(copy / "scene-company" / "SKILL.md", "a", encoding="utf-8") as f:
                f.write("\n若已安装 `../zerox-storyline/`，先用它。\n")
            p = self.run_validate(copy)
            self.assertEqual(p.returncode, 1)
            self.assertIn("引用了不存在的 skill ../zerox-storyline/", p.stdout)

    def test_missing_application_entry_fails(self):
        with tempfile.TemporaryDirectory() as t:
            copy = pathlib.Path(t) / "repo"
            copy_repo(copy)
            (copy / "commands" / "codex" / "allen-idea.md").unlink()
            p = self.run_validate(copy)
            self.assertEqual(p.returncode, 1)
            self.assertIn("allen-idea：缺少 Codex 入口", p.stdout)

    def test_invalid_application_metadata_fails(self):
        with tempfile.TemporaryDirectory() as t:
            copy = pathlib.Path(t) / "repo"
            copy_repo(copy)
            meta = copy / "allen-idea" / "assets" / "app.json"
            meta.write_text('{"id":"wrong","title":"创业点子评估","scene":"missing","report_title":"报告"}', encoding="utf-8")
            p = self.run_validate(copy)
            self.assertEqual(p.returncode, 1)
            self.assertIn("allen-idea/assets/app.json：id 必须等于 allen-idea", p.stdout)
            self.assertIn("allen-idea/assets/app.json：scene 指向不存在的 skill missing", p.stdout)

    def test_formal_reports_default_to_out_report_and_decks_are_explicit(self):
        routed_skills = [
            "router/SKILL.md",
            "core-storyline/SKILL.md",
            "scene-idea/SKILL.md",
            "scene-company/SKILL.md",
            "scene-topic/SKILL.md",
            "scene-bp-review/SKILL.md",
        ]
        for relative in routed_skills:
            text = (ROOT / relative).read_text(encoding="utf-8")
            with self.subTest(skill=relative):
                self.assertIn("默认正式报告：`out-report`", text)
                self.assertIn("路演或演示稿：`out-deck`", text)
                self.assertIn("同一任务可以同时交付两种媒介，二者不互相替代", text)
                self.assertNotIn("pages.html", text)
                self.assertNotIn("forge-work", text)

        storyline_description = (ROOT / "core-storyline/SKILL.md").read_text(encoding="utf-8").split("---", 2)[1]
        self.assertIn("out-report 正式阅读报告", storyline_description)
        self.assertIn("用户明确要求的 out-deck 演示稿", storyline_description)

    def test_scene_delivery_steps_execute_the_selected_media_route(self):
        for relative in ["scene-company/SKILL.md", "scene-topic/SKILL.md", "scene-bp-review/SKILL.md"]:
            text = (ROOT / relative).read_text(encoding="utf-8")
            with self.subTest(skill=relative):
                self.assertIn("`out-report` → `08_deliverables/report/`", text)
                self.assertIn("`out-deck` → `08_deliverables/deck/`", text)
                self.assertIn("需要两种媒介时分别执行两条输出链", text)
                self.assertNotIn("`08_deliverables/report/`（HTML + PDF）和讲者备注", text)

    def test_architecture_and_readme_describe_separate_outputs(self):
        for relative in ["ARCHITECTURE.md", "README.md"]:
            text = (ROOT / relative).read_text(encoding="utf-8")
            with self.subTest(document=relative):
                self.assertIn("out-report", text)
                self.assertIn("out-deck", text)
                self.assertIn("正式阅读报告", text)
                self.assertIn("路演或演示稿", text)


if __name__ == "__main__":
    unittest.main()
