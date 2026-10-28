"""按 tools/lib/schema/*.schema.json 校验数据（只用标准库）。

schema 文件格式：
  {"version": "...", "enums": {名称: {"values": [...], "labels": {值: 中文}}},
   "tables": {表名: {"file", "id_pattern", "fields", "require_if", ...}}   # 证据账
   或 "root": 字段规格}                                                    # slides、sidecar

字段规格：
  type      string / integer / number / boolean / date / datetime / array / object / map
  required  true 时必须存在且非空（字符串不能是空白；数组可以为空，除非另有 min_items）
  enum      引用 enums 里的名称
  pattern   正则（用于 string）
  min / max 数值范围（integer、number）
  items     数组元素的规格；min_items 最少元素数
  fields    object 的字段；出现未登记的字段就报错
  values    map 的值规格；key_pattern 限定键名
  ref       引用另一张表的 id（只由 ledger.py 做引用检查，这里不查）
缺失与 null 等价。date 允许 YYYY、YYYY-MM、YYYY-MM-DD；datetime 必须带时区。

require_if：{"if": {"field": 名, "equals": 值 | "in": [值] | "present": true}, "then": [字段], "message": 说明}
"""
import json
import math
import pathlib
import re
from datetime import date, datetime

SCHEMA_DIR = pathlib.Path(__file__).resolve().parent / "schema"
TYPES = {"string", "integer", "number", "boolean", "date", "datetime", "array", "object", "map"}
DATE_RE = re.compile(r"^(\d{4})(?:-(\d{2})(?:-(\d{2}))?)?$")


def load(name):
    """name 可以是 schema 目录下的文件名（如 ledger.schema.json），也可以是路径。"""
    p = pathlib.Path(name)
    if not p.is_file():
        p = SCHEMA_DIR / name
    return json.loads(p.read_text(encoding="utf-8"))


def empty(v):
    return v is None or (isinstance(v, str) and not v.strip())


def valid_date(s):
    m = DATE_RE.match(s)
    if not m:
        return False
    y, mo, d = int(m.group(1)), m.group(2), m.group(3)
    try:
        date(y, int(mo) if mo else 1, int(d) if d else 1)
        return True
    except ValueError:
        return False


def valid_datetime(s):
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return False
    return dt.tzinfo is not None


def check_value(schema, spec, value, path):
    """校验一个值；返回错误列表。value 为 None 表示缺失。"""
    errors = []
    if value is None:
        if spec.get("required"):
            errors.append(f"{path}：必填")
        return errors
    t = spec["type"]
    if t == "string":
        if not isinstance(value, str):
            return [f"{path}：应为字符串"]
        if spec.get("required") and not value.strip():
            return [f"{path}：必填，不能为空白"]
        if "pattern" in spec and not re.search(spec["pattern"], value):
            errors.append(f"{path}：格式不符（{spec['pattern']}）")
    elif t in ("integer", "number"):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return [f"{path}：应为数值"]
        if t == "integer" and not isinstance(value, int):
            return [f"{path}：应为整数"]
        if isinstance(value, float) and not math.isfinite(value):
            return [f"{path}：不能是 NaN 或无穷大"]
        if "min" in spec and value < spec["min"]:
            errors.append(f"{path}：不能小于 {spec['min']}")
        if "max" in spec and value > spec["max"]:
            errors.append(f"{path}：不能大于 {spec['max']}")
    elif t == "boolean":
        if not isinstance(value, bool):
            return [f"{path}：应为 true 或 false"]
    elif t == "date":
        if not isinstance(value, str) or not valid_date(value):
            return [f"{path}：日期应为 YYYY、YYYY-MM 或 YYYY-MM-DD"]
    elif t == "datetime":
        if not isinstance(value, str) or not valid_datetime(value):
            return [f"{path}：时间应为带时区的 ISO 8601"]
    elif t == "array":
        if not isinstance(value, list):
            return [f"{path}：应为数组"]
        if len(value) < spec.get("min_items", 0):
            errors.append(f"{path}：至少需要 {spec['min_items']} 项")
        if "max_items" in spec and len(value) > spec["max_items"]:
            errors.append(f"{path}：最多允许 {spec['max_items']} 项")
        for i, item in enumerate(value):
            if item is None:
                errors.append(f"{path}[{i}]：不能为 null")
            else:
                errors += check_value(schema, spec["items"], item, f"{path}[{i}]")
    elif t == "object":
        if not isinstance(value, dict):
            return [f"{path}：应为对象"]
        errors += check_fields(schema, spec["fields"], value, path)
        for rule in spec.get("require_if", []):
            if condition_holds(rule["if"], value):
                missing = [field for field in rule["then"] if empty(value.get(field)) or value.get(field) == []]
                if missing:
                    errors.append(f"{path}：{rule['message']}（缺 {'、'.join(missing)}）")
    elif t == "map":
        if not isinstance(value, dict):
            return [f"{path}：应为对象"]
        for k, v in value.items():
            if "key_pattern" in spec and not re.search(spec["key_pattern"], k):
                errors.append(f"{path}.{k}：键名格式不符（{spec['key_pattern']}）")
            errors += check_value(schema, spec["values"], v, f"{path}.{k}")
    if "enum" in spec and isinstance(value, str):
        allowed = schema["enums"][spec["enum"]]["values"]
        if value not in allowed:
            errors.append(f"{path}：取值 {value!r} 不在 {spec['enum']} 枚举中")
    return errors


def check_fields(schema, fields, obj, path):
    errors = []
    for k in obj:
        if k not in fields:
            errors.append(f"{path}.{k}：未登记的字段")
    for k, spec in fields.items():
        errors += check_value(schema, spec, obj.get(k), f"{path}.{k}")
    return errors


def condition_holds(cond, obj):
    v = obj.get(cond["field"])
    if "equals" in cond:
        return v == cond["equals"]
    if "in" in cond:
        return v in cond["in"]
    if cond.get("present"):
        return not empty(v)
    return False


def check_record(schema, table, record):
    spec = schema["tables"][table]
    if not isinstance(record, dict):
        return [f"{table}：记录应为对象"]
    path = f"{table}:{record.get('id', '?')}"
    errors = check_fields(schema, spec["fields"], record, path)
    rid = record.get("id")
    if isinstance(rid, str) and not re.search(spec["id_pattern"], rid):
        errors.append(f"{path}：id 格式不符（{spec['id_pattern']}）")
    for rule in spec.get("require_if", []):
        if condition_holds(rule["if"], record):
            missing = [f for f in rule["then"] if empty(record.get(f)) or record.get(f) == []]
            if missing:
                errors.append(f"{path}：{rule['message']}（缺 {'、'.join(missing)}）")
    return errors


def check_document(schema, doc, path="$"):
    return check_value(schema, schema["root"], doc, path)


def self_check(schema):
    """检查 schema 文件本身：类型合法、枚举存在、引用的表存在。"""
    errors = []
    tables = schema.get("tables", {})

    def walk(spec, where):
        t = spec.get("type")
        if t not in TYPES:
            errors.append(f"{where}：未知类型 {t!r}")
            return
        if "enum" in spec and spec["enum"] not in schema.get("enums", {}):
            errors.append(f"{where}：引用了不存在的枚举 {spec['enum']}")
        if "ref" in spec and spec["ref"] not in tables:
            errors.append(f"{where}：引用了不存在的表 {spec['ref']}")
        if t == "array":
            if "items" not in spec:
                errors.append(f"{where}：数组缺少 items")
            else:
                walk(spec["items"], where + "[]")
        if t == "object":
            for k, s in spec.get("fields", {}).items():
                walk(s, f"{where}.{k}")
        if t == "map":
            walk(spec.get("values", {}), where + ".*")

    for name, e in schema.get("enums", {}).items():
        if not e.get("values"):
            errors.append(f"枚举 {name} 没有取值")
        missing = [v for v in e.get("values", []) if v not in e.get("labels", {})]
        if missing:
            errors.append(f"枚举 {name} 缺少中文名：{missing}")
    for tname, t in tables.items():
        for key in ("file", "id_pattern", "fields", "upstream", "changes"):
            if key not in t:
                errors.append(f"表 {tname} 缺少 {key}")
        if "id" not in t.get("fields", {}):
            errors.append(f"表 {tname} 缺少 id 字段")
        for k, s in t.get("fields", {}).items():
            walk(s, f"{tname}.{k}")
        for rule in t.get("require_if", []):
            for f in [rule["if"]["field"], *rule["then"]]:
                if f not in t["fields"]:
                    errors.append(f"表 {tname} 的 require_if 引用了不存在的字段 {f}")
        for f in t.get("snapshot_fields", []):
            if f not in t["fields"]:
                errors.append(f"表 {tname} 的 snapshot_fields 引用了不存在的字段 {f}")
    if "root" in schema:
        walk(schema["root"], "root")
    return errors
