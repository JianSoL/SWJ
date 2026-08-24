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

POWER_10W_SYMBOLS = {
    "VAR_SYS_ALLOW_DSCH_2SPOWER",
    "VAR_SYS_ALLOW_CHRG_2SPOWER",
    "VAR_SYS_ALLOW_DSCH_10SPOWER",
    "VAR_SYS_ALLOW_CHRG_10SPOWER",
    "VAR_SYS_ALLOW_DSCH_60SPOWER",
    "VAR_SYS_ALLOW_CHRG_60SPOWER",
}

ALARM_ID_OVERRIDES = {
    46: {
        "symbol": "ALARM_BCU_ID_47",
        "name": "电池簇充电电池模块电压极差",
        "description": "(047)电池簇充电电池模块电压极差",
    },
    47: {
        "symbol": "ALARM_BCU_ID_48",
        "name": "电池簇放电电池模块电压极差",
        "description": "(048)电池簇放电电池模块电压极差",
    },
    48: {
        "symbol": "ALARM_BCU_ID_49",
        "name": "高压箱风扇故障",
        "description": "(049)高压箱风扇故障",
    },
}


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
    expression = expression.replace("/", "//")
    return expression.strip()


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
        if "(" in name or not expression:
            continue
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


def _description_unit(description):
    patterns = (
        r"0\.01\s*KWH",
        r"0\.1\s*KWH",
        r"0\.01\s*AH",
        r"0\.1\s*AH",
        r"0\.1\s*WH",
        r"0\.1\s*V",
        r"0\.1\s*A",
        r"0\.1\s*S",
        r"0\.1\s*%",
        r"0\.1\s*℃",
        r"10\s*uΩ",
        r"mV",
        r"mA",
        r"KΩ",
        r"1K",
        r"Hz",
        r"毫秒",
        r"分钟",
        r"秒",
        r"%",
    )
    for pattern in patterns:
        match = re.search(pattern, description or "", flags=re.IGNORECASE)
        if match:
            return re.sub(r"\s+", "", match.group(0))
    return ""


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
        if item is None:
            continue
        symbol = item.group(1)
        if symbol in seen_symbols:
            continue
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
        entries.append(
            {
                "offset": current_value,
                "symbol": symbol,
                "name": _description_name(description, symbol),
                "description": description,
                "unit": _description_unit(description),
                "signed": "有符号" in description,
                "reserved": "预留" in description or "RESERVED" in symbol,
                "source_file": source_file,
                "source_line": first_line + offset,
            }
        )
    return entries, symbols


def _without_sentinels(entries):
    if not entries:
        return []

    # Firmware enums use the final item as their capacity/boundary marker.
    # Business fields can legitimately end in _NUM or _END, so suffix-based
    # filtering would hide valid protocol indexes such as PAR_SYS_LECU_NUM.
    final_symbol = entries[-1]["symbol"]
    if final_symbol.endswith(("_NUM", "_MAX_NUM", "_END")):
        return entries[:-1]
    return list(entries)


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
        relative_path = str(files[source_key].relative_to(source_root)).replace("\\", "/")
        entries, symbols = parse_enum(texts[source_key], enum_name, relative_path)
        for entry in entries:
            entry["category"] = category
            entry["category_label"] = category_label
            entry["access"] = access
            if entry["symbol"] in POWER_10W_SYMBOLS:
                entry["unit"] = "10W"
                entry["description"] = (
                    f"{entry['description']}；协议存储精度 10W/bit"
                )
        enums[category] = _without_sentinels(entries)
        enum_symbols[enum_name] = symbols

    alarm_id_file = str(files["par_macro"].relative_to(source_root)).replace("\\", "/")
    alarm_ids, _alarm_symbols = parse_enum(texts["par_macro"], "enAlarmID", alarm_id_file)
    alarm_ids = _without_sentinels(alarm_ids)
    alarm_override_records = []
    for alarm_entry in alarm_ids:
        alarm_offset = int(alarm_entry["offset"])
        override = ALARM_ID_OVERRIDES.get(alarm_offset)
        if override is None:
            continue
        alarm_override_records.append(
            {
                "name": f"alarm_id_{alarm_offset + 1:03d}",
                "source_symbol": alarm_entry["symbol"],
                "effective_symbol": override["symbol"],
                "reason": "Upper-computer protocol alarm-field replacement",
            }
        )
        alarm_entry.update(override)
        alarm_entry["reserved"] = False

    source_cell_var_count = int(macro_values["VAR_LECU_CELL_MAX_NUM"])
    effective_cell_var_count = int(
        source_cell_var_count if lecu_cell_var_count is None else lecu_cell_var_count
    )
    bcu_stride = int(enum_symbols["enBcuVar"].get("VAR_BCU_UINT_NUM", 64))
    constants = {
        "ID_VAR_LECU_START": int(macro_values["ID_VAR_LECU_SRATR"]),
        "ID_VAR_BCU_START": int(macro_values["ID_VAR_BCU_SRATR"]),
        "ID_VAR_VMS_START": int(macro_values["ID_VAR_VMS_SRATR"]),
        "ID_VAR_CHR_START": int(macro_values["ID_VAR_CHR_SRATR"]),
        "ID_VAR_OTHER_START": int(macro_values["ID_VAR_OTHER_SRATR"]),
        "LECU_CELL_MAX_NUM": int(macro_values["LECU_CELL_MAX_NUM"]),
        "VAR_LECU_UINT_MAX_NUM": int(macro_values["VAR_LECU_UINT_MAX_NUM"]),
        "VAR_LECU_CELL_MAX_NUM": effective_cell_var_count,
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
    if effective_cell_var_count != source_cell_var_count:
        overrides.append(
            {
                "name": "VAR_LECU_CELL_MAX_NUM",
                "source_value": source_cell_var_count,
                "effective_value": effective_cell_var_count,
                "reason": "Upper computer protocol compatibility override",
            }
        )
    overrides.extend(alarm_override_records)

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
    parser = argparse.ArgumentParser(description="Generate the DCBMS index catalog from firmware headers.")
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--lecu-cell-var-count", type=int)
    args = parser.parse_args()

    catalog = generate_catalog(args.source_root, args.lecu_cell_var_count)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"Generated {args.output}: "
        f"{sum(len(entries) for entries in catalog['enums'].values())} definitions, "
        f"source={catalog['source']['sha256'][:12]}"
    )


if __name__ == "__main__":
    main()
