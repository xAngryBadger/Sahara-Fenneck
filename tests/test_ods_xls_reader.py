"""Tests for ODS and .xls format support in excel_reader and runner."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from src.agent.runner import _cached_sheet_names
from src.indexing.excel_reader import (
    EXCEL_EXTENSIONS,
    _engine_for_suffix,
    index_file_multi,
    index_from_path,
    is_excel_file,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def ods_single(tmp_path: Path) -> Path:
    p = tmp_path / "single.ods"
    pd.DataFrame({"Nome": ["Alice", "Bob"], "Idade": [30, 25]}).to_excel(
        p, index=False, engine="odf", sheet_name="Dados"
    )
    return p


@pytest.fixture
def ods_multi(tmp_path: Path) -> Path:
    p = tmp_path / "multi.ods"
    with pd.ExcelWriter(p, engine="odf") as w:
        pd.DataFrame({"X": [1, 2, 3]}).to_excel(w, sheet_name="Aba1", index=False)
        pd.DataFrame({"Y": [10, 20]}).to_excel(w, sheet_name="Aba2", index=False)
    return p


@pytest.fixture
def xls_single(tmp_path: Path) -> Path:
    import xlwt

    p = tmp_path / "legacy.xls"
    wb = xlwt.Workbook()
    ws = wb.add_sheet("Plan1")
    for c, h in enumerate(["Nome", "Idade"]):
        ws.write(0, c, h)
    for r, (nome, idade) in enumerate([("Alice", 30), ("Bob", 25)], start=1):
        ws.write(r, 0, nome)
        ws.write(r, 1, idade)
    wb.save(str(p))
    return p


@pytest.fixture
def xls_multi(tmp_path: Path) -> Path:
    import xlwt

    p = tmp_path / "legacy_multi.xls"
    wb = xlwt.Workbook()
    ws1 = wb.add_sheet("Vendas")
    ws1.write(0, 0, "Valor")
    ws1.write(1, 0, 100)
    ws2 = wb.add_sheet("RH")
    ws2.write(0, 0, "Nome")
    ws2.write(1, 0, "Carlos")
    wb.save(str(p))
    return p


# ---------------------------------------------------------------------------
# EXCEL_EXTENSIONS / is_excel_file / _engine_for_suffix
# ---------------------------------------------------------------------------

class TestExtensionsAndDispatch:
    def test_ods_in_extensions(self):
        assert ".ods" in EXCEL_EXTENSIONS

    def test_xls_in_extensions(self):
        assert ".xls" in EXCEL_EXTENSIONS

    def test_is_excel_file_ods(self):
        assert is_excel_file("planilha.ods")

    def test_is_excel_file_xls(self):
        assert is_excel_file("legacy.xls")

    def test_is_excel_file_xlsx(self):
        assert is_excel_file("data.xlsx")

    def test_is_excel_file_csv_rejected(self):
        assert not is_excel_file("data.csv")

    def test_engine_for_suffix_xlsx(self):
        assert _engine_for_suffix(".xlsx") == "openpyxl"

    def test_engine_for_suffix_xlsm(self):
        assert _engine_for_suffix(".xlsm") == "openpyxl"

    def test_engine_for_suffix_xls(self):
        assert _engine_for_suffix(".xls") == "xlrd"

    def test_engine_for_suffix_ods(self):
        assert _engine_for_suffix(".ods") == "odf"

    def test_engine_for_suffix_unknown(self):
        assert _engine_for_suffix(".csv") is None


# ---------------------------------------------------------------------------
# ODS indexing
# ---------------------------------------------------------------------------

class TestODSIndexing:
    def test_single_sheet(self, ods_single: Path):
        ws = index_from_path(str(ods_single))
        assert ws.error is None
        assert ws.sheet_name == "Dados"
        assert ws.columns == ["Nome", "Idade"]
        assert ws.row_count == 2
        assert ws.indexed_rows == 2
        assert ws.df is not None
        assert list(ws.df["Nome"]) == ["Alice", "Bob"]

    def test_multi_sheet_first(self, ods_multi: Path):
        ws = index_from_path(str(ods_multi))
        assert ws.error is None
        assert ws.sheet_name == "Aba1"

    def test_multi_sheet_specific(self, ods_multi: Path):
        ws = index_from_path(str(ods_multi), sheet_name="Aba2")
        assert ws.error is None
        assert ws.sheet_name == "Aba2"
        assert ws.columns == ["Y"]
        assert ws.row_count == 2

    def test_multi_sheet_all(self, ods_multi: Path):
        items = index_file_multi(str(ods_multi), include_all_sheets=True)
        assert len(items) == 2
        names = [i.sheet_name for i in items]
        assert "Aba1" in names
        assert "Aba2" in names

    def test_nonexistent(self, tmp_path: Path):
        ws = index_from_path(str(tmp_path / "nope.ods"))
        assert ws.error is not None

    def test_cached_sheet_names(self, ods_multi: Path):
        _cached_sheet_names.cache_clear()
        names = _cached_sheet_names(str(ods_multi))
        assert "Aba1" in names
        assert "Aba2" in names


# ---------------------------------------------------------------------------
# .xls indexing
# ---------------------------------------------------------------------------

class TestXLSIndexing:
    def test_single_sheet(self, xls_single: Path):
        ws = index_from_path(str(xls_single))
        assert ws.error is None
        assert ws.sheet_name == "Plan1"
        assert ws.columns == ["Nome", "Idade"]
        assert ws.row_count == 2
        assert ws.df is not None
        assert list(ws.df["Nome"]) == ["Alice", "Bob"]

    def test_multi_sheet_first(self, xls_multi: Path):
        ws = index_from_path(str(xls_multi))
        assert ws.error is None
        assert ws.sheet_name == "Vendas"

    def test_multi_sheet_specific(self, xls_multi: Path):
        ws = index_from_path(str(xls_multi), sheet_name="RH")
        assert ws.error is None
        assert ws.sheet_name == "RH"
        assert ws.columns == ["Nome"]

    def test_multi_sheet_all(self, xls_multi: Path):
        items = index_file_multi(str(xls_multi), include_all_sheets=True)
        assert len(items) == 2
        names = [i.sheet_name for i in items]
        assert "Vendas" in names
        assert "RH" in names

    def test_cached_sheet_names(self, xls_multi: Path):
        _cached_sheet_names.cache_clear()
        names = _cached_sheet_names(str(xls_multi))
        assert "Vendas" in names
        assert "RH" in names


# ---------------------------------------------------------------------------
# Cross-format consistency
# ---------------------------------------------------------------------------

class TestCrossFormat:
    def test_same_data_xlsx_vs_ods(self, tmp_path: Path):
        df = pd.DataFrame({"A": [1, 2, 3], "B": ["x", "y", "z"]})
        xlsx = tmp_path / "d.xlsx"
        ods = tmp_path / "d.ods"
        df.to_excel(xlsx, index=False, engine="openpyxl")
        df.to_excel(ods, index=False, engine="odf")

        ws_xlsx = index_from_path(str(xlsx))
        ws_ods = index_from_path(str(ods))
        assert ws_xlsx.columns == ws_ods.columns
        assert ws_xlsx.row_count == ws_ods.row_count
        assert list(ws_xlsx.df["A"]) == list(ws_ods.df["A"])

    def test_same_data_xlsx_vs_xls(self, tmp_path: Path):
        import xlwt

        df = pd.DataFrame({"A": [1, 2], "B": ["x", "y"]})
        xlsx = tmp_path / "d.xlsx"
        df.to_excel(xlsx, index=False, engine="openpyxl")

        xls = tmp_path / "d.xls"
        wb = xlwt.Workbook()
        ws = wb.add_sheet("Sheet1")
        for c, h in enumerate(df.columns):
            ws.write(0, c, h)
        for r in range(len(df)):
            for c in range(len(df.columns)):
                val = df.iloc[r, c]
                if hasattr(val, "item"):
                    val = val.item()
                ws.write(r + 1, c, val)
        wb.save(str(xls))

        ws_xlsx = index_from_path(str(xlsx))
        ws_xls = index_from_path(str(xls))
        assert ws_xlsx.columns == ws_xls.columns
        assert ws_xlsx.row_count == ws_xls.row_count


# ---------------------------------------------------------------------------
# ODS/.xls save path (structured_actions_tool)
# ---------------------------------------------------------------------------

class TestODSSavePath:
    def test_ods_sort_saves_as_xlsx(self, ods_single: Path):
        from src.agent.tools import _apply_actions_to_df

        ws = index_from_path(str(ods_single))
        assert ws.error is None
        assert ws.df is not None

        new_df, err = _apply_actions_to_df(ws.df, [{"action": "sort", "by": ["Idade"], "ascending": True}])
        assert err == ""
        assert list(new_df["Nome"]) == ["Bob", "Alice"]

    def test_ods_workbook_actions_blocked(self, ods_single: Path):
        from src.agent.tools import structured_actions_tool
        from src.checkpoints.manager import CheckpointManager

        ws = index_from_path(str(ods_single))
        cp = CheckpointManager(str(ods_single))
        result = structured_actions_tool(
            ws,
            '{"actions": [{"action": "create_sheet", "name": "Nova"}]}',
            cp,
            save_checkpoint=False,
        )
        assert not result.success
        assert ".ods" in result.message or ".xls" in result.message or "xlsx" in result.message
