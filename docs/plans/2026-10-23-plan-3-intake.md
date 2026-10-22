# 计划 3：材料接收 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新增 core-intake，把 PDF、Word、PPT 处理成标准结构并登记为证据账里的用户来源；router 在判断场景之前先接收材料。

**Architecture:**
- `tools/lib/snapshot.py`：来源快照的读写，计划 6 的研究也用它。
- `tools/lib/office.py`：调用 LibreOffice，每次用临时配置目录并软链接系统中文字体。
- `core-intake/scripts/intake.py`：逐个处理文件，生成全文、页面图片、表格、快照，登记来源。Word 和 PPT 直接用标准库读 zip 包里的 XML，不依赖虚拟环境。
- doctor 的 LibreOffice 检查升级为"能转换并渲染中文"；selftest 和 CI 加跑各 skill 自己的测试。

**Tech Stack:** Python 3 标准库（zipfile、xml.etree、csv、subprocess）、Poppler、Tesseract、LibreOffice、Pandoc（只用于生成测试材料）。

**依据：** 设计 §4、§3.2（快照）、§9、§11、§12 第 3 步。

**写法：** 和计划 2 一样，代码先在临时副本里写好并跑通，计划只写任务、要点、测试和预期结果，代码以提交的文件为准。

## 开发中的重要发现

1. **macOS 上无头运行的 LibreOffice 看不到系统字体。** 它只能用自带的字体，中文整段渲染不出来：PDF 的文字层还在，但页面图片里没有中文，OCR 也因此认不出中文。和沙箱无关，在沙箱外运行结果相同。
   - 解决：每次转换用一个临时配置目录，在 `user/fonts` 下软链接系统中文字体（优先冬青黑体 `Hiragino Sans GB.ttc`，其次华文黑体）。实测中文完整渲染，OCR 正确识别。
2. **图表引擎（thinkcell）导出 PNG 时直接调用 `soffice`，用的是默认配置**，中文图表的 PNG 预览会有同样的问题。这个留到计划 4（out-chart）解决。

**本计划不做：**
- PDF 里的表格不单独抽成 CSV（按版面保留在正文中，并标"可能错位"）。设计 §4 写的是"能抽出来的表格"，Word 和 PPT 的表格能可靠抽出。
- router 文件夹树的其余调整、任务单模板的交付物措辞：放在计划 8。

---

## 文件结构

| 文件 | 职责 |
|---|---|
| `tools/lib/snapshot.py`（新建） | 快照的写（独占创建，不允许覆盖）与读；头部字段取自 schema 的 snapshot_fields |
| `tools/lib/office.py`（新建） | soffice 路径、系统中文字体、带临时配置目录的转换 |
| `tools/tests/test_snapshot.py`（新建） | 快照与中文字体选择的测试（6 个） |
| `core-intake/SKILL.md`（新建） | 先后顺序、调用方法、产物、各格式处理、质量标记、失败处理 |
| `core-intake/scripts/intake.py`（新建） | 材料接收脚本 |
| `core-intake/scripts/tests/test_intake.py`（新建） | 5 个单元测试和 11 个端到端测试（测试材料现场生成） |
| `router/SKILL.md`（修改） | 新增第 0 节"用户给了文件时，先接收材料"；文件夹树改为 `03_evidence/` |
| `router/assets/brief-template.md`（修改） | 新增"用户要求（原文）"一节 |
| `tools/doctor.py`、`tools/tests/test_doctor.py`（修改） | LibreOffice 检查改为"能转换文件并渲染中文" |
| `tools/selftest.sh`、`.github/workflows/validate.yml`（修改） | 加跑 `*/scripts/tests`；完整自检设置 `ALLEN_REQUIRE_TOOLS=1` |

---

### Task 1: 快照与 LibreOffice 调用

- [ ] **Step 1:** 写 `tools/tests/test_snapshot.py`，运行确认失败（ImportError）。
- [ ] **Step 2:** 写 `tools/lib/snapshot.py` 和 `tools/lib/office.py`，运行确认通过。

Run: `python3 -m unittest tools.tests.test_snapshot -v`
Expected: 6 个测试通过，覆盖：
- 往返读写保留值和字段顺序；
- 不允许覆盖已有快照；
- 拒绝快照头里出现未知字段、拒绝缺少 id；
- 空正文写入占位说明；
- 5 种读取错误；
- 中文字体按顺序选第一款存在的。

- [ ] **Step 3: 提交** `feat(lib): add snapshot files and LibreOffice wrapper with CJK fonts`

### Task 2: core-intake

**要点：**
- **编号**：来源编号由证据账分配（U001……）；`--no-ledger` 时扫描 `raw/user/` 目录取下一个编号。
- **PDF**：
  - 逐页用 `pdftotext -layout` 抽文字，用 `pdftoppm` 转图片；
  - 字少于 20 个的页，用 300 dpi 渲染后让 Tesseract（chi_sim+eng）识别，识别出更多文字就采用 OCR 结果；
  - OCR 后仍少于 3 个字的页才算低文字页，此时访问程度为 partial。封面等字少的页属于正常，不会被误判。
- **Word**：转 PDF 后取页码和图片；表格直接从 `word/document.xml` 读出，存为 CSV。
- **PPT**：
  - 按 `presentation.xml` 的放映顺序读每张幻灯片的文字、表格、演讲者备注（备注页里 type=body 的占位符）；
  - 文件里没有文字的幻灯片，对渲染出的那一页做 OCR；
  - 幻灯片数与渲染页数不一致时打质量标记。
- **老格式**：`.doc`、`.ppt` 先转成 `.docx`、`.pptx`。
- **读不出来的文件**（加密、损坏、所有页都没有文字）：不伪造正文，登记为 unreadable。
- **不支持的格式、不存在的文件**：直接报错，不登记。
- **快照**：头部写 snapshot_fields，正文与 text.md 一致；证据账里的来源记录和快照头的同名字段一致；`original_files` 登记目录下全部文件及其 sha256。

- [ ] **Step 1:** 写 `core-intake/scripts/tests/test_intake.py`，运行确认失败（ImportError）。
- [ ] **Step 2:** 写 `intake.py`，运行端到端测试。

Run: `ALLEN_REQUIRE_TOOLS=1 python3 -m unittest discover -s core-intake/scripts/tests -t core-intake/scripts/tests -v`
Expected: 16 个测试通过（约 12 秒）。测试材料用 Pandoc 和 LibreOffice 现场生成，包括：
- 文字版 PDF、扫描版 PDF（确认它本身抽不出文字）；
- Word、带备注和表格的 PPT、有一页整页是图片的 PPT；
- 加密 PDF、损坏文件、老格式 .doc。

- [ ] **Step 3: 变异检查**：把 PDF 的 OCR 分支改成 `if False:`，应有 2 个测试失败（扫描件、汇总），复原后通过。
- [ ] **Step 4: 跳过逻辑检查**：
  - 用 `env -i PATH=/usr/bin:/bin` 运行（缺少 pandoc 等工具）：默认应显示 `OK (skipped=11)`；
  - 加上 `ALLEN_REQUIRE_TOOLS=1`：应有 11 个失败。
- [ ] **Step 5:** 写 `core-intake/SKILL.md`。
- [ ] **Step 6: 提交** `feat(core-intake): add intake for PDF, Word and PPT materials`

### Task 3: router 衔接

- [ ] **Step 1:** router/SKILL.md 新增第 0 节，文件夹树里的 `03_evidence.md` 改为 `03_evidence/`；任务单模板新增"用户要求（原文）"。
- [ ] **Step 2:** `python3 tools/validate.py | tail -1` → `共 14 个 skill …；错误 0 个`
- [ ] **Step 3: 提交** `docs(router): receive user materials before choosing the scene`

### Task 4: doctor、selftest、CI

- [ ] **Step 1:** `office.convert` 增加 `soffice` 参数，并捕获无法运行的错误。doctor 的 LibreOffice 检查改为：把一段中文转成 PDF，再用 `pdffonts` 确认用上了中文字体。测试中同步改检查名。
- [ ] **Step 2:** selftest 加跑 `*/scripts/tests`，完整自检时设置 `ALLEN_REQUIRE_TOOLS=1`；CI 加一步跑 skill 脚本测试。
- [ ] **Step 3:** Run: `python3 tools/doctor.py | grep LibreOffice` → `[通过] LibreOffice（能转换文件并渲染中文）：…中文字体：HiraginoSansGB`；`tools/selftest.sh --quick` → 单元测试 100 个、core-intake 16 个都通过，validate 0 个错误。
- [ ] **Step 4: 提交** `feat(doctor): verify LibreOffice renders Chinese; run skill tests in selftest and CI`

### Task 5: 收尾

- [ ] **Step 1:** 完整自检 `tools/selftest.sh`（含三个引擎的测试）全部通过。
- [ ] **Step 2:** 写审查记录 `2026-10-23-plan-3-review.md`，更新路线图（含把 thinkcell 中文 PNG 的问题记到计划 4）。
- [ ] **Step 3: 提交** `docs(plans): complete plan 3 intake`
