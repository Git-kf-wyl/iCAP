"""Deterministic grading of real spreadsheet artifacts produced by Hermes.

References are kept outside the agent sandbox. No workbook macros or formulas
are executed by this evaluator, and a missing formula cache is never a blank.
"""
from __future__ import annotations

import copy
import math
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree

MAX_FILE_BYTES = 64 * 1024 * 1024
MAX_EXPANDED_BYTES = 128 * 1024 * 1024
MAX_CELLS = 200_000
MAX_TARGETS = 5_000
CELL_RE = re.compile(r"\$?([A-Za-z]{1,3})\$?([1-9][0-9]{0,6})$")


def _targets(data):
    from openpyxl.utils.cell import column_index_from_string

    default_sheet = None
    if isinstance(data, str):
        if len(data) > 200_000:
            raise ValueError("表格预期结果超过 200 KB")
        entries = []
        for line in data.splitlines():
            if not line.strip():
                continue
            if "=" not in line:
                raise ValueError("表格结果须逐行填写 A1=预期值 或 Sheet!A1=预期值")
            key, value = line.split("=", 1)
            entries.append((key.strip(), value.strip()))
    elif isinstance(data, dict):
        if "cells" in data:
            if set(data) - {"sheet", "cells"} or not isinstance(data["cells"], dict):
                raise ValueError("表格结果对象只支持 sheet 和 cells 字段")
            default_sheet = data.get("sheet")
            if default_sheet is not None and (not isinstance(default_sheet, str) or not default_sheet.strip()):
                raise ValueError("表格 sheet 必须是非空工作表名称")
            entries = list(data["cells"].items())
        else:
            entries = list(data.items())
    else:
        raise ValueError("表格结果须是单元格=值的文本或单元格映射对象")
    if not 0 < len(entries) <= MAX_TARGETS:
        raise ValueError(f"表格结果须包含 1 至 {MAX_TARGETS} 个目标单元格")
    targets, seen = [], set()
    for key, value in entries:
        if not isinstance(key, str) or len(key) > 256:
            raise ValueError("表格单元格地址不合法")
        sheet, address = (key.rsplit("!", 1) if "!" in key else (default_sheet, key))
        if sheet is not None:
            sheet = sheet.strip()
            if sheet.startswith("'") and sheet.endswith("'"):
                sheet = sheet[1:-1].replace("''", "'")
            if not sheet or len(sheet) > 31 or any(c in sheet for c in "[]:*?/\\"):
                raise ValueError("表格工作表名称不合法")
        match = CELL_RE.fullmatch(address)
        if not match or column_index_from_string(match[1]) > 16384 or int(match[2]) > 1048576:
            raise ValueError(f"表格单元格地址不合法：{key}")
        coordinate = match[1].upper() + match[2]
        if (sheet, coordinate) in seen:
            raise ValueError(f"表格目标单元格重复：{key}")
        seen.add((sheet, coordinate))
        if type(value) not in (str, bool, int, float, type(None)) or isinstance(value, float) and not math.isfinite(value):
            raise ValueError("表格预期值只支持文本、数字、布尔值或 null")
        targets.append((sheet, coordinate, None if value == "<NONE>" else value))
    return targets


def validate_expectation(data):
    """Validate configuration before running a paid model, without opening files."""
    _targets(data)


def _workbook(path: Path, *, cached_values=True):
    """Bound both compressed and expanded XLSX data before openpyxl parses it."""
    from openpyxl import load_workbook

    if path.is_symlink() or not path.is_file():
        raise ValueError("表格文件不存在或为符号链接")
    if path.stat().st_size > MAX_FILE_BYTES:
        raise ValueError("表格文件超过 64 MB")
    with zipfile.ZipFile(path) as archive:
        members = archive.infolist()
        if len(members) > 10000 or sum(m.file_size for m in members) > MAX_EXPANDED_BYTES:
            raise ValueError("表格解压大小或成员数超限")
        if len({m.filename for m in members}) != len(members):
            raise ValueError("表格压缩包含重复成员")
        cells = 0
        for member in members:
            if member.flag_bits & 1:
                raise ValueError("不支持加密表格")
            if member.filename.startswith("xl/worksheets/") and member.filename.endswith(".xml"):
                with archive.open(member) as stream:
                    for _, element in ElementTree.iterparse(stream, events=("end",)):
                        if element.tag.rsplit("}", 1)[-1] == "c":
                            cells += 1
                            if cells > MAX_CELLS:
                                raise ValueError("表格非空/格式单元格数超过安全上限")
                        element.clear()
    formulas = load_workbook(path, data_only=False, keep_links=False)
    if not cached_values:
        return formulas, None
    try:
        return formulas, load_workbook(path, data_only=True, keep_links=False)
    except Exception:
        formulas.close()
        raise


def _value_matches(actual, expected):
    if expected is None:
        return actual is None
    if isinstance(expected, bool):
        return type(actual) is bool and actual == expected
    if isinstance(actual, bool):
        return isinstance(expected, str) and expected.casefold() == str(actual).casefold()
    if type(actual) in (int, float):
        try:
            return math.isfinite(float(expected)) and math.isclose(float(actual), float(expected), rel_tol=1e-9, abs_tol=1e-9)
        except (ValueError, TypeError, OverflowError):
            return False
    if hasattr(actual, "isoformat"):
        return str(expected) in {str(actual), actual.isoformat()}
    return actual is not None and str(actual) == str(expected)


def _cell_signature(cell):
    # Style IDs are local to each workbook and may be renumbered on save.
    return (cell.value, cell.data_type, cell.number_format,
            *(copy.copy(getattr(cell, key)) for key in ("font", "fill", "border", "alignment", "protection")),
            (cell.hyperlink.target, cell.hyperlink.location) if cell.hyperlink else None,
            (cell.comment.author, cell.comment.text) if cell.comment else None)


def _unchanged(original, actual, target_keys):
    issues = []
    if original.sheetnames != actual.sheetnames:
        return ["工作表名称或顺序被修改"]
    for before, after in zip(original.worksheets, actual.worksheets):
        if {str(r) for r in before.merged_cells.ranges} != {str(r) for r in after.merged_cells.ranges}:
            issues.append(f"{before.title} 的合并单元格结构被修改")
        if before.sheet_state != after.sheet_state:
            issues.append(f"{before.title} 的可见性被修改")
        if before.freeze_panes != after.freeze_panes or before.auto_filter.ref != after.auto_filter.ref:
            issues.append(f"{before.title} 的冻结或筛选区域被修改")
        for field, attributes in (("row_dimensions", ("height", "hidden", "outlineLevel", "collapsed")),
                                  ("column_dimensions", ("width", "hidden", "outlineLevel", "collapsed", "min", "max"))):
            left, right = getattr(before, field), getattr(after, field)
            for index in left.keys() | right.keys():
                if index not in left or index not in right or any(getattr(left[index], a) != getattr(right[index], a) for a in attributes):
                    issues.append(f"{before.title} 的行列布局被修改")
                    break
        # Work on physical sparse cells, never iterate a forged 1M-row dimension.
        for row, column in before._cells.keys() | after._cells.keys():
            cell = before.cell(row, column)
            if (before.title, cell.coordinate) in target_keys:
                continue
            if _cell_signature(cell) != _cell_signature(after.cell(row, column)):
                issues.append(f"非目标单元格 {before.title}!{cell.coordinate} 被修改")
                if len(issues) >= 20:
                    return issues
    return issues


def grade(workspace: Path, expected, input_name="input.xlsx", *, baseline_path: Path | None = None):
    """Read output.xlsx and compare actual values; failures cannot pass by text.

    Production callers must supply baseline_path from the immutable task assets,
    outside the writable Hermes sandbox, to detect unrelated-cell tampering.
    """
    books = []
    try:
        targets = _targets(expected)
        root = Path(workspace).resolve()
        output = root / "output.xlsx"
        if output.is_symlink() or output.resolve().parent != root:
            raise ValueError("输出表格路径越界或为符号链接")
        if baseline_path is None:
            baseline = root / input_name
            if baseline.is_symlink() or baseline.resolve().parent != root:
                raise ValueError("输入表格路径越界或为符号链接")
        else:
            baseline = Path(baseline_path)
        original, _ = _workbook(baseline, cached_values=False)
        books.append(original)
        actual, values = _workbook(output)
        books.extend((actual, values))
        default_sheet = original.sheetnames[0]
        resolved = [(sheet or default_sheet, address, value) for sheet, address, value in targets]
        if len({(s, a) for s, a, _ in resolved}) != len(resolved):
            raise ValueError("表格默认工作表和显式工作表的目标单元格重复")
        cells = []
        for sheet, address, value in resolved:
            detail = {"cell": f"{sheet}!{address}", "expected": value, "passed": False}
            if sheet not in actual.sheetnames:
                detail["error"] = "输出缺少目标工作表"
            else:
                raw = actual[sheet][address]
                current = values[sheet][address].value
                detail["actual"] = current if type(current) in (str, int, float, bool, type(None)) else str(current)
                if raw.data_type == "f" and current is None:
                    detail["error"] = "目标单元格是没有缓存值的公式，请写入计算后的实际值"
                else:
                    detail["passed"] = _value_matches(current, value)
            cells.append(detail)
        changes = _unchanged(original, actual, {(sheet, address) for sheet, address, _ in resolved})
        matched = sum(c["passed"] for c in cells)
        score = 0.0 if changes else round(100 * matched / len(cells), 2)
        return score, {"source": "spreadsheet_artifact", "score": score, "passed": score == 100,
                       "output_file": "output.xlsx", "cells": cells, "preservation_issues": changes,
                       "analysis": "实际表格目标值与非目标区域均通过校验" if score == 100 else
                           f"目标单元格通过 {matched}/{len(cells)}；非目标区域问题 {len(changes)} 项"}
    except (ValueError, OSError, KeyError, zipfile.BadZipFile, ElementTree.ParseError) as exc:
        return 0.0, {"source": "spreadsheet_artifact", "score": 0.0, "passed": False,
                     "analysis": "无法验证实际输出表格", "error": str(exc)[:500]}
    finally:
        for book in books:
            book.close()
