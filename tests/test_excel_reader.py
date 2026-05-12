"""Unit tests for excel_reader — file-based indexing (no COM)."""
from __future__ import annotations

import pandas as pd
import pytest
from src.indexing.excel_reader import (
    Workspace,
    _normalize_limit,
    _rows_to_df,
    _safe_headers,
    get_workspace_summary,
    hydrate_workspace_full,
    index_file_multi,
    index_from_path,
    is_excel_file,
)


class TestIsExcelFile:
    @pytest.mark.parametrize("ext", [".xlsx", ".xlsm", ".xls"])
    def test_valid_extensions(self, ext):
        assert is_excel_file(f"planilha{ext}") is True

    def test_uppercase(self):
        assert is_excel_file("PLAN.XLSX") is True

    def test_csv_rejected(self):
        assert is_excel_file("dados.csv") is False

    def test_no_extension(self):
        assert is_excel_file("arquivo") is False


class TestNormalizeLimit:
    def test_positive(self):
        assert _normalize_limit(100) == 100

    def test_zero_means_none(self):
        assert _normalize_limit(0) is None

    def test_negative_means_none(self):
        assert _normalize_limit(-5) is None

    def test_minimum_1(self):
        assert _normalize_limit(1) == 1

    def test_invalid_string_returns_default(self):
        assert _normalize_limit("abc") == 5000


class TestSafeHeaders:
    def test_normal_headers(self):
        assert _safe_headers(["A", "B", "C"], 3) == ["A", "B", "C"]

    def test_none_fills_coln(self):
        assert _safe_headers([None, "B", None], 3) == ["Col1", "B", "Col3"]

    def test_empty_string_fills_coln(self):
        assert _safe_headers(["", "B", "  "], 3) == ["Col1", "B", "Col3"]

    def test_fewer_headers_than_cols(self):
        result = _safe_headers(["A"], 3)
        assert result == ["A", "Col2", "Col3"]

    def test_more_headers_than_cols_ignored(self):
        result = _safe_headers(["A", "B", "C", "D"], 2)
        assert result == ["A", "B"]


class TestRowsToDf:
    def test_with_rows(self):
        df = _rows_to_df(["A", "B"], [[1, 2], [3, 4]])
        assert len(df) == 2
        assert list(df.columns) == ["A", "B"]

    def test_empty_rows(self):
        df = _rows_to_df(["A", "B"], [])
        assert len(df) == 0
        assert list(df.columns) == ["A", "B"]


class TestIndexFileMulti:
    def test_single_sheet(self, sample_xlsx):
        results = index_file_multi(str(sample_xlsx))
        assert len(results) == 1
        ws = results[0]
        assert ws.error is None
        assert ws.sheet_name in ("Sheet", "Sheet1")
        assert ws.columns == ["Col1", "Col2", "Col3"]
        assert ws.row_count == 3
        assert ws.indexed_rows == 3
        assert ws.truncated is False
        assert ws.df is not None

    def test_multi_sheet(self, sample_xlsx_multi_sheet):
        results = index_file_multi(str(sample_xlsx_multi_sheet), include_all_sheets=True)
        assert len(results) == 3
        names = {ws.sheet_name for ws in results}
        assert names == {"Aba1", "Aba2", "Aba3"}

    def test_multi_sheet_first_only(self, sample_xlsx_multi_sheet):
        results = index_file_multi(str(sample_xlsx_multi_sheet), include_all_sheets=False)
        assert len(results) == 1

    def test_missing_file(self, tmp_path):
        results = index_file_multi(str(tmp_path / "nonexistent.xlsx"))
        assert len(results) == 1
        assert results[0].error is not None
        assert "não encontrado" in results[0].error.lower()

    def test_non_excel_file(self, tmp_path):
        txt = tmp_path / "data.txt"
        txt.write_text("hello")
        results = index_file_multi(str(txt))
        assert len(results) == 1
        assert results[0].error is not None
        assert "Formato inválido" in results[0].error

    def test_empty_sheet(self, empty_xlsx):
        results = index_file_multi(str(empty_xlsx))
        assert len(results) == 1
        ws = results[0]
        assert ws.row_count == 0

    def test_truncation(self, tmp_path):
        df = pd.DataFrame({"A": range(100)})
        xlsx = tmp_path / "big.xlsx"
        df.to_excel(xlsx, index=False, engine="openpyxl")
        results = index_file_multi(str(xlsx), max_rows=10)
        ws = results[0]
        assert ws.truncated is True
        assert ws.indexed_rows == 10
        assert ws.row_count == 100

    def test_no_limit(self, tmp_path):
        df = pd.DataFrame({"A": range(50)})
        xlsx = tmp_path / "full.xlsx"
        df.to_excel(xlsx, index=False, engine="openpyxl")
        results = index_file_multi(str(xlsx), max_rows=0)
        ws = results[0]
        assert ws.truncated is False
        assert ws.indexed_rows == 50

    def test_df_data_correct(self, sample_xlsx):
        results = index_file_multi(str(sample_xlsx))
        ws = results[0]
        assert ws.df["Col1"].tolist() == [1, 2, 3]
        assert ws.df["Col2"].tolist() == ["a", "b", "c"]


class TestIndexFromPath:
    def test_first_sheet(self, sample_xlsx):
        ws = index_from_path(str(sample_xlsx))
        assert ws.error is None
        assert ws.columns == ["Col1", "Col2", "Col3"]

    def test_specific_sheet(self, sample_xlsx_multi_sheet):
        ws = index_from_path(str(sample_xlsx_multi_sheet), sheet_name="Aba2")
        assert ws.sheet_name == "Aba2"
        assert ws.columns == ["Y"]

    def test_missing_sheet_returns_first(self, sample_xlsx_multi_sheet):
        ws = index_from_path(str(sample_xlsx_multi_sheet), sheet_name="NonExistent")
        assert ws.sheet_name == "Aba1"


class TestWorkspaceSummary:
    def test_summary_ok(self, workspace):
        s = workspace.summary_one_line()
        assert "test.xlsx" in s
        assert "Planilha1" in s
        assert "4 colunas" in s

    def test_summary_error(self):
        ws = Workspace(path="", workbook_name="", sheet_name="", columns=[], row_count=0, indexed_rows=0, error="Erro!")
        assert ws.summary_one_line() == "Erro!"

    def test_summary_truncated(self):
        ws = Workspace(path="f.xlsx", workbook_name="f.xlsx", sheet_name="S", columns=["A"], row_count=100, indexed_rows=10, truncated=True)
        assert "amostra" in ws.summary_one_line()


class TestGetWorkspaceSummary:
    def test_full_summary(self, workspace):
        text = get_workspace_summary(workspace)
        assert "Arquivo:" in text
        assert "Colunas" in text
        assert "Amostra" in text

    def test_error_summary(self):
        ws = Workspace(path="", workbook_name="", sheet_name="", columns=[], row_count=0, indexed_rows=0, error="Falha")
        text = get_workspace_summary(ws)
        assert text == "Falha"


class TestHydrateWorkspaceFull:
    def test_not_truncated_returns_same(self, workspace):
        result = hydrate_workspace_full(workspace)
        assert result is workspace

    def test_error_returns_same(self):
        ws = Workspace(path="", workbook_name="", sheet_name="", columns=[], row_count=0, indexed_rows=0, error="Err", truncated=True)
        result = hydrate_workspace_full(ws)
        assert result is ws

    def test_truncated_file_reindexes(self, tmp_path):
        df = pd.DataFrame({"A": range(50)})
        xlsx = tmp_path / "hydr.xlsx"
        df.to_excel(xlsx, index=False, engine="openpyxl")
        ws_trunc = index_from_path(str(xlsx), max_rows=5)
        assert ws_trunc.truncated is True
        ws_full = hydrate_workspace_full(ws_trunc)
        assert ws_full.truncated is False
        assert ws_full.indexed_rows == 50
