"""来源快照文件：元数据头 + 正文（设计 §3.2；格式沿用 deep-research 的快照）。

文件位于 03_evidence/raw/sources/<来源ID>-<slug>.md：
  ---
  id: "U001"
  title: "某公司 BP"
  ...
  ---
  正文

头部每行 `键: 值`，值一律写成 JSON（字符串用双引号转义，中文不转义；列表和对象写成行内 JSON；空值写 null）。
头部字段及顺序取自 ledger.schema.json 里 sources 表的 snapshot_fields；这些字段以快照头为真源，写入后不可修改。
快照用独占方式创建，已存在就拒绝覆盖（一个来源 ID 永远对应一份不变的快照）。
"""
import json
import pathlib

from tools.lib import schema_check

EMPTY_BODY = "（正文为空：无法抽取文字，原件见 original_files）\n"


class SnapshotError(Exception):
    pass


def fields():
    return schema_check.load("ledger.schema.json")["tables"]["sources"]["snapshot_fields"]


def write(path, meta, body):
    path = pathlib.Path(path)
    unknown = set(meta) - set(fields())
    if unknown:
        raise SnapshotError(f"快照头不能包含这些字段：{sorted(unknown)}")
    if not meta.get("id"):
        raise SnapshotError("快照头必须有 id")
    lines = ["---"] + [f"{k}: {json.dumps(meta.get(k), ensure_ascii=False)}" for k in fields()] + ["---", ""]
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(path, "x", encoding="utf-8") as f:
            f.write("\n".join(lines) + (body if body.strip() else EMPTY_BODY))
    except FileExistsError:
        raise SnapshotError(f"快照已存在，不能覆盖：{path}")


def read(path):
    text = pathlib.Path(path).read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise SnapshotError(f"{path}：缺少元数据头")
    end = text.find("\n---\n", 4)
    if end < 0:
        raise SnapshotError(f"{path}：元数据头没有结束标记")
    meta = {}
    for n, line in enumerate(text[4:end].splitlines(), 2):
        if not line.strip():
            continue
        key, sep, value = line.partition(": ")
        if not sep:
            raise SnapshotError(f"{path} 第 {n} 行：无法识别")
        if key in meta:
            raise SnapshotError(f"{path} 第 {n} 行：重复的键 {key}")
        try:
            meta[key] = json.loads(value)
        except ValueError:
            raise SnapshotError(f"{path} 第 {n} 行：值不是合法 JSON")
    body = text[end + len("\n---\n"):]
    if body.startswith("\n"):
        body = body[1:]
    return meta, body
