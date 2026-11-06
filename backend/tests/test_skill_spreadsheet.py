import shutil
import zipfile

import pytest
from openpyxl import Workbook, load_workbook
from openpyxl.styles import PatternFill

from app.skill_evolution import spreadsheet


@pytest.fixture
def workbook_case(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    baseline = tmp_path / "reference.xlsx"
    book = Workbook()
    sheet = book.active
    sheet.title = "Data"
    sheet["I12"] = "January"
    sheet["A1"] = "Preserve this"
    sheet["A1"].fill = PatternFill("solid", fgColor="FFAA11")
    sheet.merge_cells("B3:C3")
    book.create_sheet("Untouched")["C2"] = 42
    book.save(baseline)
    book.close()
    shutil.copyfile(baseline, workspace / "input.xlsx")
    book = load_workbook(baseline)
    book["Data"]["J23"] = "January"
    book.save(workspace / "output.xlsx")
    book.close()
    return workspace, baseline


def test_actual_cells_and_preserved_workbook(workbook_case):
    workspace, baseline = workbook_case
    score, details = spreadsheet.grade(workspace, "J23=January\nK23=<NONE>\nL23=<NONE>", baseline_path=baseline)
    assert score == 100 and details["passed"]
    assert details["source"] == "spreadsheet_artifact"


def test_wrong_value_partial_score(workbook_case):
    workspace, baseline = workbook_case
    score, details = spreadsheet.grade(workspace, {"sheet": "Data", "cells": {"J23": "February", "K23": None}}, baseline_path=baseline)
    assert score == 50 and not details["passed"]


def test_unrelated_sheet_tampering_cannot_be_hidden_by_editing_input(workbook_case):
    workspace, baseline = workbook_case
    for name in ("output.xlsx", "input.xlsx"):
        book = load_workbook(workspace / name)
        book["Untouched"]["C2"] = 99
        book.save(workspace / name)
        book.close()
    score, details = spreadsheet.grade(workspace, "Data!J23=January", baseline_path=baseline)
    assert score == 0
    assert "Untouched!C2" in details["preservation_issues"][0]


def test_missing_formula_cache_is_not_blank(workbook_case):
    workspace, baseline = workbook_case
    book = load_workbook(workspace / "output.xlsx")
    book["Data"]["K23"] = '=IF(I12="","",I12)'
    book.save(workspace / "output.xlsx")
    book.close()
    score, details = spreadsheet.grade(workspace, "J23=January\nK23=<NONE>", baseline_path=baseline)
    assert score == 50
    assert "缓存" in details["cells"][1]["error"]


def test_missing_output_cannot_pass_from_final_answer(workbook_case):
    workspace, baseline = workbook_case
    (workspace / "output.xlsx").unlink()
    score, details = spreadsheet.grade(workspace, "J23=January", baseline_path=baseline)
    assert score == 0 and "error" in details


@pytest.mark.parametrize("expected", ["", "J0=x", "XFE1=x", "A1048577=x", "J23=x\nJ23=y", {"A1": []}, "not cell syntax"])
def test_reject_invalid_targets(expected):
    with pytest.raises(ValueError):
        spreadsheet.validate_expectation(expected)


def test_workbook_expansion_limit(workbook_case, monkeypatch):
    workspace, baseline = workbook_case
    monkeypatch.setattr(spreadsheet, "MAX_EXPANDED_BYTES", 100)
    score, details = spreadsheet.grade(workspace, "J23=January", baseline_path=baseline)
    assert score == 0 and "超限" in details["error"]


def test_unrelated_style_change_fails(workbook_case):
    workspace, baseline = workbook_case
    book = load_workbook(workspace / "output.xlsx")
    book["Data"]["A1"].fill = PatternFill("solid", fgColor="112233")
    book.save(workspace / "output.xlsx")
    book.close()
    score, details = spreadsheet.grade(workspace, "J23=January", baseline_path=baseline)
    assert score == 0 and details["preservation_issues"]


def test_duplicate_default_and_explicit_target_rejected(workbook_case):
    workspace, baseline = workbook_case
    score, details = spreadsheet.grade(workspace, "J23=January\nData!J23=January", baseline_path=baseline)
    assert score == 0 and "重复" in details["error"]
