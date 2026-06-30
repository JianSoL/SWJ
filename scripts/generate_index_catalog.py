import argparse
import ast
import hashlib
import json
import re
from pathlib import Path


ENUM_SPECS = (
    ("var", "enSysVar", "system_variable", "系统变量", "read_write"),
    ("var", "enBcuVar", "bcu_variable", "BCU变量", "read_write"),
    ("var", "enLecuVar", "lecu_variable", "LECU变量", "read_write"),
    ("var", "enLecu_CellVar", "lecu_cell_variable", "LECU单体变量", "read_write"),
    ("var", "enVMSVar", "vms_variable", "VMS变量", "read_write"),
    ("var", "enChrVar", "charger_variable", "充电机变量", "read_only"),
    ("par", "enCoefPar", "coefficient_parameter", "系数参数", "read_write"),
    ("par", "enSysPar", "system_parameter", "系统参数", "read_write"),
    ("par", "enRealTimePar", "runtime_parameter", "运行参数", "read_write"),
    ("par", "enRealTimeCellPar", "runtime_cell_parameter", "运行单体参数", "read_write"),
    ("par", "enLecuPar", "lecu_parameter", "LECU参数", "read_write"),
    ("par", "enByteInfoPar", "byte_parameter", "字节信息参数", "read_only"),
    ("par", "enAlarmPar", "alarm_parameter", "告警参数", "read_write"),
    ("par", "enRtcPar", "rtc_parameter", "RTC参数", "read_write"),
)


UNIT_PATTERNS = (
    (r"0\.01\s*KWH", 0.01, "kWh"),
    (r"0\.1\s*KWH", 0.1, "kWh"),
    (r"0\.01\s*AH", 0.01, "Ah"),
    (r"0\.1\s*AH", 0.1, "Ah"),
    (r"0\.1\s*WH", 0.1, "Wh"),
    (r"0\.1\s*V", 0.1, "V"),
    (r"0\.1\s*A", 0.1, "A"),
    (r"0\.1\s*S", 0.1, "s"),
    (r"0\.1\s*%", 0.1, "%"),
    (r"0\.1\s*℃", 0.1, "℃"),
    (r"10\s*W", 10.0, "W"),
    (r"10\s*uΩ", 10.0, "uΩ"),
    (r"mV", 1.0, "mV"),
    (r"mA", 1.0, "mA"),
    (r"KΩ", 1.0, "kΩ"),
    (r"1K", 1.0, "kΩ"),
    (r"Hz", 1.0, "Hz"),
    (r"毫秒", 1.0, "ms"),
    (r"分钟", 1.0, "min"),
    (r"秒", 1.0, "s"),
    (r"%", 1.0, "%"),
)


def read_text(path):
    raw = Path(path).read_bytes()
    for encoding in ("utf-8-sig", "gb18030", "gbk"):
        try:
            return raw.decode(encoding), raw
        except UnicodeDecodeError:
            continue
    return raw.decode("latin1"), raw


def _normalize_c_expression(expression):
    expression = re.sub(
        r"\b(0[xX][0-9A-Fa-f]+|\d+)[uUlL]+\b",
        lambda match: match.group(1),
        expression,
    )
    return expression.replace("/", "//").strip()


def evaluate_expression(expression, symbols):
    expression = _normalize_c_expression(expression)
    tree = ast.parse(expression, mode="eval")

    def visit(node):
        if isinstance(node, ast.Expression):
            return visit(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, int):
            return int(node.value)
        if isinstance(node, ast.Name) and node.id in symbols:
            return int(symbols[node.id])
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub, ast.Invert)):
            value = visit(node.operand)
            if isinstance(node.op, ast.UAdd):
                return value
            if isinstance(node.op, ast.USub):
                return -value
            return ~value
        if isinstance(node, ast.BinOp):
            left = visit(node.left)
            right = visit(node.right)
            operators = {
                ast.Add: lambda: left + right,
                ast.Sub: lambda: left - right,
                ast.Mult: lambda: left * right,
                ast.FloorDiv: lambda: left // right,
                ast.LShift: lambda: left << right,
                ast.RShift: lambda: left >> right,
                ast.BitOr: lambda: left | right,
                ast.BitAnd: lambda: left & right,
                ast.BitXor: lambda: left ^ right,
            }
            operation = operators.get(type(node.op))
            if operation is not None:
                return operation()
        raise ValueError(f"Unsupported C expression: {expression}")

    return int(visit(tree))


def parse_numeric_macros(text, initial=None):
    values = dict(initial or {})
    pending = []
    pattern = re.compile(r"^\s*#define\s+([A-Za-z_]\w*)\s+([^/\r\n]+)", re.MULTILINE)
    for match in pattern.finditer(text):
        name = match.group(1)
        expression = match.group(2).strip()
        if "(" not in name and expression:
            pending.append((name, expression))
    for _ in range(len(pending) + 1):
        next_pending = []
        changed = False
        for name, expression in pending:
            try:
                values[name] = evaluate_expression(expression, values)
                changed = True
            except (SyntaxError, ValueError, ZeroDivisionError):
                next_pending.append((name, expression))
        pending = next_pending
        if not changed:
            break
    return values


def _description_name(description, symbol):
    text = re.sub(r"^\s*\(\d+\)\s*", "", description or "").strip()
    if not text:
        return symbol
    for separator in ("[", "【", "，", ",", "。", "（", "("):
        if separator in text:
            text = text.split(separator, 1)[0].strip()
    return text or symbol


def _unit_metadata(description):
    for pattern, scale, display_unit in UNIT_PATTERNS:
        match = re.search(pattern, description or "", flags=re.IGNORECASE)
        if match:
            return re.sub(r"\s+", "", match.group(0)), scale, display_unit
    return "", 1.0, ""


def parse_enum(text, enum_name, source_file):
    match = re.search(
        rf"\benum\s+{re.escape(enum_name)}\s*\{{(?P<body>.*?)\}}\s*;",
        text,
        flags=re.DOTALL,
    )
    if match is None:
        raise ValueError(f"Enum {enum_name} was not found in {source_file}")
    body = match.group("body")
    first_line = text[: match.start("body")].count("\n") + 1
    symbols = {}
    entries = []
    current_value = -1
    seen_symbols = set()
    for offset, raw_line in enumerate(body.splitlines(), start=1):
        code, marker, comment = raw_line.partition("///<")
        if not marker:
            code, marker, comment = raw_line.partition("//")
        code = re.sub(r"/\*.*?\*/", "", code).strip()
        if not code or code.startswith("#"):
            continue
        item = re.match(r"^([A-Za-z_]\w*)\s*(?:=\s*([^,]+?))?\s*,?\s*$", code)
        if item is None or item.group(1) in seen_symbols:
            continue
        symbol = item.group(1)
        expression = item.group(2)
        if expression:
            try:
                current_value = evaluate_expression(expression, symbols)
            except (SyntaxError, ValueError):
                current_value += 1
        else:
            current_value += 1
        symbols[symbol] = current_value
        seen_symbols.add(symbol)
        description = comment.strip()
        unit, scale, display_unit = _unit_metadata(description)
        entries.append(
            {
                "offset": current_value,
                "symbol": symbol,
                "name": _description_name(description, symbol),
                "description": description,
                "unit": unit,
                "scale": scale,
                "display_unit": display_unit,
                "signed": "有符号" in description,
                "reserved": "预留" in description or "RESERVED" in symbol,
                "source_file": source_file,
                "source_line": first_line + offset,
            }
        )
    return entries, symbols


def _without_sentinels(entries):
    return [
        entry
        for entry in entries
        if not entry["symbol"].endswith(("_NUM", "_MAX_NUM", "_END"))
    ]


def generate_catalog(source_root, lecu_cell_var_count=None):
    source_root = Path(source_root).resolve()
    files = {
        "var_macro": source_root / "Sources" / "Service" / "Var_Manage" / "Var_Macro.h",
        "var_manage": source_root / "Sources" / "Service" / "Var_Manage" / "Var_Manage.h",
        "par_macro": source_root / "Sources" / "Service" / "Par_Manage" / "Par_Macro.h",
        "par_manage": source_root / "Sources" / "Service" / "Par_Manage" / "Par_Manage.h",
    }
    texts = {}
    digest = hashlib.sha256()
    for key, path in files.items():
        text, raw = read_text(path)
        texts[key] = text
        digest.update(str(path.relative_to(source_root)).encode("utf-8"))
        digest.update(raw)

    macro_values = {}
    for key in ("var_macro", "var_manage", "par_macro", "par_manage"):
        macro_values = parse_numeric_macros(texts[key], macro_values)

    enums = {}
    enum_symbols = {}
    for file_key, enum_name, category, category_label, access in ENUM_SPECS:
        source_key = "var_macro" if file_key == "var" else "par_macro"
        source_file = str(files[source_key].relative_to(source_root)).replace("\\", "/")
        entries, symbols = parse_enum(texts[source_key], enum_name, source_file)
        for entry in entries:
            entry.update(category=category, category_label=category_label, access=access)
        enums[category] = _without_sentinels(entries)
        enum_symbols[enum_name] = symbols

    alarm_source = str(files["par_macro"].relative_to(source_root)).replace("\\", "/")
    alarm_ids, _alarm_symbols = parse_enum(texts["par_macro"], "enAlarmID", alarm_source)
    alarm_ids = _without_sentinels(alarm_ids)

    source_cell_count = int(macro_values["VAR_LECU_CELL_MAX_NUM"])
    cell_field_count = source_cell_count if lecu_cell_var_count is None else int(lecu_cell_var_count)
    bcu_stride = int(enum_symbols["enBcuVar"].get("VAR_BCU_UINT_NUM", 64))
    constants = {
        "ID_VAR_LECU_START": int(macro_values["ID_VAR_LECU_SRATR"]),
        "ID_VAR_BCU_START": int(macro_values["ID_VAR_BCU_SRATR"]),
        "ID_VAR_VMS_START": int(macro_values["ID_VAR_VMS_SRATR"]),
        "ID_VAR_CHR_START": int(macro_values["ID_VAR_CHR_SRATR"]),
        "ID_VAR_OTHER_START": int(macro_values["ID_VAR_OTHER_SRATR"]),
        "LECU_CELL_MAX_NUM": int(macro_values["LECU_CELL_MAX_NUM"]),
        "VAR_LECU_UINT_MAX_NUM": int(macro_values["VAR_LECU_UINT_MAX_NUM"]),
        "VAR_LECU_CELL_MAX_NUM": cell_field_count,
        "BCU_DATA_LENGTH": bcu_stride,
        "ID_PAR_COEF_START": int(macro_values["ID_PAR_COEF_SRATR"]),
        "ID_PAR_SYS_START": int(macro_values["ID_PAR_SYS_SRATR"]),
        "ID_PAR_RUN_START": int(macro_values["ID_PAR_RUN_SRATR"]),
        "ID_PAR_RUN_CELL_START": int(macro_values["ID_PAR_RUN_CELL_SRATR"]),
        "ID_PAR_LECU_START": int(macro_values["ID_PAR_LECU_SRATR"]),
        "ID_PAR_BYTE_START": int(macro_values["ID_PAR_BYTE_SRATR"]),
        "ID_PAR_ALARM_START": int(macro_values["ID_PAR_ALARM_SRATR"]),
        "ID_PAR_OTHER_START": int(macro_values["ID_PAR_OTHER_SRATR"]),
        "ID_PAR_RTC_START": int(macro_values["ID_PAR_RTC_SRATR"]),
        "ID_PAR_RTC_END": int(macro_values["ID_PAR_RTC_END"]),
        "PAR_COEF_MAX_NUM": int(macro_values["PAR_COEF_MAX_NUM"]),
        "PAR_SYS_MAX_NUM": int(macro_values["PAR_SYS_MAX_NUM"]),
        "PAR_RUN_MAX_NUM": int(macro_values["PAR_RUN_MAX_NUM"]),
        "PAR_RUN_CELL_MAX_NUM": int(macro_values["PAR_RUN_CELL_MAX_NUM"]),
        "PAR_LECU_MAX_NUM": int(macro_values["PAR_LECU_MAX_NUM"]),
        "PAR_BYTE_MAX_NUM": int(macro_values["PAR_BYTE_MAX_NUM"]),
        "PAR_ALM_MAX_NUM": int(macro_values["PAR_ALM_MAX_NUM"]),
    }
    constants["LECU_DATA_LENGTH"] = (
        constants["LECU_CELL_MAX_NUM"] * constants["VAR_LECU_CELL_MAX_NUM"]
        + constants["VAR_LECU_UINT_MAX_NUM"]
    )
    overrides = []
    if cell_field_count != source_cell_count:
        overrides.append(
            {
                "name": "VAR_LECU_CELL_MAX_NUM",
                "source_value": source_cell_count,
                "effective_value": cell_field_count,
                "reason": "Upper computer protocol compatibility override",
            }
        )
    return {
        "schema_version": 1,
        "source": {
            "name": source_root.name,
            "files": [str(path.relative_to(source_root)).replace("\\", "/") for path in files.values()],
            "sha256": digest.hexdigest(),
            "overrides": overrides,
        },
        "constants": constants,
        "enums": enums,
        "alarm_ids": alarm_ids,
    }


def main():
    parser = argparse.ArgumentParser(description="Generate the AIDC index catalog from firmware headers.")
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--lecu-cell-var-count", type=int)
    args = parser.parse_args()
    catalog = generate_catalog(args.source_root, args.lecu_cell_var_count)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    total = sum(len(entries) for entries in catalog["enums"].values())
    print(f"Generated {args.output}: {total} definitions, source={catalog['source']['sha256'][:12]}")


if __name__ == "__main__":
    main()
