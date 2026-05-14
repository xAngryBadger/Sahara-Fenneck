"""Unit tests for excel_reader — file-based indexing (no COM)."""
from __future__ import annotations

import pandas as pd
import pytest
from src.indexing.excel_reader import (
    Workspace,
    _build_categorical_values,
    _build_column_stats,
    _build_sample_block,
    _fmt_number,
    _is_nontabular,
    _normalize_limit,
    _rows_to_df,
    _safe_headers,
    _trim_summary,
    get_workbook_overview,
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
    def test_rich_summary_has_dtypes(self, workspace):
        text = get_workspace_summary(workspace)
        assert "Tipos:" in text
        assert "int64" in text or "float64" in text

    def test_rich_summary_has_stats(self, workspace):
        text = get_workspace_summary(workspace)
        assert "Estatísticas por coluna:" in text
        assert "min=" in text
        assert "max=" in text

    def test_rich_summary_has_head_tail(self, workspace):
        text = get_workspace_summary(workspace)
        assert "Alice" in text

    def test_rich_summary_has_categorical_values(self, workspace):
        text = get_workspace_summary(workspace)
        assert "Valores únicos" in text
        assert "Cidade" in text

    def test_error_summary(self):
        ws = Workspace(path="", workbook_name="", sheet_name="", columns=[], row_count=0, indexed_rows=0, error="Falha")
        text = get_workspace_summary(ws)
        assert text == "Falha"

    def test_nontabular_warning(self, tmp_path):
        df = pd.DataFrame({"Unnamed: 0": [1], "Unnamed: 1": ["x"], "Unnamed: 2": [3.0]})
        xlsx = tmp_path / "nontab.xlsx"
        df.to_excel(xlsx, index=False, engine="openpyxl")
        ws = index_from_path(str(xlsx))
        text = get_workspace_summary(ws)
        assert "não-tabular" in text

    def test_token_budget_trimming(self, workspace):
        text_full = get_workspace_summary(workspace)
        short = get_workspace_summary(workspace, max_context_chars=200)
        assert len(short) <= 203
        assert len(short) < len(text_full)

    def test_null_counts_in_stats(self, tmp_path):
        df = pd.DataFrame({"A": [1, None, 3], "B": ["x", None, None]})
        xlsx = tmp_path / "nulls.xlsx"
        df.to_excel(xlsx, index=False, engine="openpyxl")
        ws = index_from_path(str(xlsx))
        text = get_workspace_summary(ws)
        assert "nulo" in text


class TestIsNontabular:
    def test_unnamed_columns_flagged(self):
        ws = Workspace(
            path="f.xlsx", workbook_name="f.xlsx", sheet_name="MENU",
            columns=["Unnamed: 0", "Unnamed: 1", "Unnamed: 2"],
            row_count=5, indexed_rows=5,
            df=pd.DataFrame({"Unnamed: 0": [1], "Unnamed: 1": ["a"], "Unnamed: 2": [3.0]}),
        )
        assert _is_nontabular(ws) is True

    def test_normal_columns_not_flagged(self, workspace):
        assert _is_nontabular(workspace) is False

    def test_empty_df_not_flagged(self):
        ws = Workspace(path="", workbook_name="", sheet_name="", columns=[], row_count=0, indexed_rows=0)
        assert _is_nontabular(ws) is False

    def test_many_rows_not_flagged(self):
        df = pd.DataFrame({"Unnamed: 0": range(100), "Unnamed: 1": range(100)})
        ws = Workspace(
            path="f.xlsx", workbook_name="f.xlsx", sheet_name="S",
            columns=["Unnamed: 0", "Unnamed: 1"],
            row_count=100, indexed_rows=100, df=df,
        )
        assert _is_nontabular(ws) is False


class TestFmtNumber:
    def test_integer(self):
        assert _fmt_number(5) == "5"

    def test_float_whole(self):
        assert _fmt_number(5.0) == "5"

    def test_float_fractional(self):
        assert _fmt_number(3.14) == "3.14"

    def test_nan(self):
        assert _fmt_number(float("nan")) == "NaN"

    def test_string(self):
        assert _fmt_number("abc") == "abc"


class TestBuildColumnStats:
    def test_numeric_stats(self, workspace):
        lines = _build_column_stats(workspace)
        assert any("min=" in ln for ln in lines)
        assert any("mean=" in ln for ln in lines)

    def test_categorical_stats(self, workspace):
        lines = _build_column_stats(workspace)
        assert any("únicos" in ln for ln in lines)

    def test_empty_df(self):
        ws = Workspace(path="", workbook_name="", sheet_name="", columns=[], row_count=0, indexed_rows=0)
        assert _build_column_stats(ws) == []


class TestBuildSampleBlock:
    def test_small_df_shows_all(self, workspace):
        text = _build_sample_block(workspace)
        assert "Alice" in text

    def test_large_df_shows_head_tail(self, tmp_path):
        df = pd.DataFrame({"A": range(100)})
        xlsx = tmp_path / "big.xlsx"
        df.to_excel(xlsx, index=False, engine="openpyxl")
        ws = index_from_path(str(xlsx))
        text = _build_sample_block(ws)
        assert "Primeiras" in text
        assert "Últimas" in text

    def test_empty_df(self):
        ws = Workspace(path="", workbook_name="", sheet_name="", columns=[], row_count=0, indexed_rows=0)
        assert _build_sample_block(ws) == ""


class TestBuildCategoricalValues:
    def test_low_unique_shown(self, workspace):
        lines = _build_categorical_values(workspace)
        assert any("Cidade" in ln for ln in lines)

    def test_numeric_skipped(self, workspace):
        lines = _build_categorical_values(workspace)
        assert not any("Idade" in ln for ln in lines)

    def test_empty_df(self):
        ws = Workspace(path="", workbook_name="", sheet_name="", columns=[], row_count=0, indexed_rows=0)
        assert _build_categorical_values(ws) == []


class TestTrimSummary:
    def test_no_trim_needed(self, workspace):
        text = get_workspace_summary(workspace)
        trimmed = _trim_summary(text, workspace, max_chars=len(text) + 100)
        assert trimmed == text

    def test_trim_removes_categorical_first(self, workspace):
        text = get_workspace_summary(workspace)
        trimmed = _trim_summary(text, workspace, max_chars=len(text) - 100)
        assert len(trimmed) < len(text)

    def test_hard_truncate(self, workspace):
        text = get_workspace_summary(workspace)
        trimmed = _trim_summary(text, workspace, max_chars=50)
        assert len(trimmed) <= 53
        assert trimmed.endswith("...")


class TestGetWorkbookOverview:
    def test_multi_sheet_overview(self, sample_xlsx_multi_sheet):
        text = get_workbook_overview(str(sample_xlsx_multi_sheet))
        assert "Workbook:" in text
        assert "3 aba(s)" in text
        assert "Aba1" in text
        assert "Aba2" in text

    def test_missing_file(self, tmp_path):
        text = get_workbook_overview(str(tmp_path / "nope.xlsx"))
        assert "não encontrado" in text.lower() or "E0" in text

    def test_single_sheet(self, sample_xlsx):
        text = get_workbook_overview(str(sample_xlsx))
        assert "1 aba(s)" in text


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


class TestEngineForSuffix:
    def test_xlsx(self):
        from src.indexing.excel_reader import _engine_for_suffix
        assert _engine_for_suffix(".xlsx") == "openpyxl"

    def test_xlsm(self):
        from src.indexing.excel_reader import _engine_for_suffix
        assert _engine_for_suffix(".xlsm") == "openpyxl"

    def test_xls(self):
        from src.indexing.excel_reader import _engine_for_suffix
        assert _engine_for_suffix(".xls") == "xlrd"

    def test_ods(self):
        from src.indexing.excel_reader import _engine_for_suffix
        assert _engine_for_suffix(".ods") == "odf"

    def test_unknown(self):
        from src.indexing.excel_reader import _engine_for_suffix
        assert _engine_for_suffix(".csv") is None

    def test_uppercase(self):
        from src.indexing.excel_reader import _engine_for_suffix
        assert _engine_for_suffix(".XLSX") == "openpyxl"


class TestIndexFileMultiEdgeCases:
    def test_ods_file(self, tmp_path):
        ods = tmp_path / "test.ods"
        pd.DataFrame({"X": [1, 2]}).to_excel(ods, index=False, engine="odf")
        items = index_file_multi(str(ods))
        assert len(items) >= 1
        assert items[0].error is None
        assert items[0].columns == ["X"]

    def test_xls_file(self, tmp_path):
        xlsx = tmp_path / "fake_xls.xlsx"
        pd.DataFrame({"Y": [10, 20]}).to_excel(xlsx, index=False, engine="openpyxl")
        items = index_file_multi(str(xlsx))
        assert len(items) >= 1
        assert items[0].error is None

    def test_corrupt_file(self, tmp_path):
        bad = tmp_path / "bad.xlsx"
        bad.write_text("this is not an excel file")
        items = index_file_multi(str(bad))
        assert len(items) == 1
        assert items[0].error is not None

    def test_empty_sheet_error(self, tmp_path):
        xlsx = tmp_path / "empty_sheet.xlsx"
        pd.DataFrame({"A": [1]}).to_excel(xlsx, index=False, engine="openpyxl")
        items = index_file_multi(str(xlsx))
        assert len(items) >= 1

    def test_all_sheets_flag(self, tmp_path):
        xlsx = tmp_path / "multi_flag.xlsx"
        with pd.ExcelWriter(xlsx, engine="openpyxl") as writer:
            pd.DataFrame({"A": [1]}).to_excel(writer, sheet_name="S1", index=False)
            pd.DataFrame({"B": [2]}).to_excel(writer, sheet_name="S2", index=False)
        items = index_file_multi(str(xlsx), include_all_sheets=True)
        assert len(items) == 2

    def test_max_rows_truncation(self, tmp_path):
        xlsx = tmp_path / "big.xlsx"
        pd.DataFrame({"A": range(100)}).to_excel(xlsx, index=False, engine="openpyxl")
        items = index_file_multi(str(xlsx), max_rows=10)
        assert items[0].truncated is True
        assert items[0].indexed_rows == 10
        assert items[0].row_count == 100


class TestIndexFromPathEdgeCases:
    def test_specific_sheet_found(self, tmp_path):
        xlsx = tmp_path / "specific.xlsx"
        with pd.ExcelWriter(xlsx, engine="openpyxl") as writer:
            pd.DataFrame({"A": [1]}).to_excel(writer, sheet_name="Alpha", index=False)
            pd.DataFrame({"B": [2]}).to_excel(writer, sheet_name="Beta", index=False)
        ws = index_from_path(str(xlsx), sheet_name="Beta")
        assert ws.sheet_name == "Beta"

    def test_missing_sheet_returns_first(self, tmp_path):
        xlsx = tmp_path / "miss_sheet.xlsx"
        with pd.ExcelWriter(xlsx, engine="openpyxl") as writer:
            pd.DataFrame({"A": [1]}).to_excel(writer, sheet_name="Only", index=False)
        ws = index_from_path(str(xlsx), sheet_name="Ghost")
        assert ws.sheet_name == "Only"

    def test_file_not_found(self, tmp_path):
        ws = index_from_path(str(tmp_path / "nonexistent.xlsx"))
        assert ws.error is not None


class TestSafeHeadersMoreCases:
    def test_all_none(self):
        from src.indexing.excel_reader import _safe_headers
        result = _safe_headers([None, None, None], 3)
        assert result == ["Col1", "Col2", "Col3"]

    def test_mixed_valid_and_none(self):
        from src.indexing.excel_reader import _safe_headers
        result = _safe_headers(["Name", None, "Age"], 3)
        assert result == ["Name", "Col2", "Age"]


class TestRowsToDfEdgeCases:
    def test_none_pd(self):
        from src.indexing import excel_reader as er
        original_pd = er.pd
        try:
            er.pd = None
            result = _rows_to_df(["A", "B"], [[1, 2]])
            assert result is None
        finally:
            er.pd = original_pd


class TestWorkspaceSummaryOneLine:
    def test_basic(self, workspace):
        line = workspace.summary_one_line()
        assert "test.xlsx" in line
        assert "Planilha1" in line

    def test_with_error(self):
        ws = Workspace(path="", workbook_name="", sheet_name="", columns=[], row_count=0, indexed_rows=0, error="Some error")
        assert ws.summary_one_line() == "Some error"

    def test_truncated(self, workspace):
        workspace.truncated = True
        line = workspace.summary_one_line()
        assert "amostra" in line


class TestGetWorkbookOverviewEdgeCases:
    def test_many_sheets(self, tmp_path):
        xlsx = tmp_path / "many_sheets.xlsx"
        with pd.ExcelWriter(xlsx, engine="openpyxl") as writer:
            for i in range(25):
                pd.DataFrame({"C": [1]}).to_excel(writer, sheet_name=f"Sheet{i}", index=False)
        overview = get_workbook_overview(str(xlsx))
        assert "25 aba(s)" in overview
        assert "aba" in overview

    def test_nontabular_sheet_in_overview(self, tmp_path):
        xlsx = tmp_path / "nontab_overview.xlsx"
        df = pd.DataFrame({"Unnamed: 0": [1], "Unnamed: 1": [2], "Col3": [3]})
        df.to_excel(xlsx, index=False, engine="openpyxl")
        overview = get_workbook_overview(str(xlsx))
        assert "não-tabular" in overview

    def test_invalid_format_overview(self, tmp_path):
        bad = tmp_path / "bad.csv"
        bad.write_text("a,b\n1,2")
        overview = get_workbook_overview(str(bad))
        assert "formato" in overview.lower() or "invalid" in overview.lower() or "Err" in overview

    def test_no_sheets_overview(self, tmp_path):
        xlsx = tmp_path / "nosheets.xlsx"
        pd.DataFrame({"A": [1]}).to_excel(xlsx, index=False, engine="openpyxl")
        overview = get_workbook_overview(str(xlsx))
        assert "aba" in overview.lower() or "A" in overview

    def test_many_columns_truncated(self, tmp_path):
        xlsx = tmp_path / "wide.xlsx"
        cols = {f"Col{i}": [1] for i in range(25)}
        pd.DataFrame(cols).to_excel(xlsx, index=False, engine="openpyxl")
        overview = get_workbook_overview(str(xlsx))
        assert "..." in overview


class TestBuildColumnStatsEdgeCases:
    def test_all_null_numeric(self, workspace):
        import numpy as np
        from src.indexing.excel_reader import _build_column_stats
        workspace.df = pd.DataFrame({"A": [np.nan, np.nan, np.nan]})
        workspace.columns = ["A"]
        lines = _build_column_stats(workspace)
        assert len(lines) == 1
        assert "100%" in lines[0]

    def test_many_columns_display(self, workspace):
        cols = [f"Col{i}" for i in range(25)]
        df = pd.DataFrame({c: [1] for c in cols})
        workspace.df = df
        workspace.columns = cols
        workspace.row_count = 1
        workspace.indexed_rows = 1
        summary = get_workspace_summary(workspace)
        assert "..." in summary


class TestBuildCategoricalEdgeCases:
    def test_zero_unique_values(self, workspace):
        from src.indexing.excel_reader import _build_categorical_values
        workspace.df = pd.DataFrame({"X": [None, None, None]})
        workspace.columns = ["X"]
        lines = _build_categorical_values(workspace)
        assert len(lines) == 0

    def test_more_than_max_unique(self, workspace):
        from src.indexing.excel_reader import _build_categorical_values
        workspace.df = pd.DataFrame({"Y": [str(i) for i in range(20)]})
        workspace.columns = ["Y"]
        lines = _build_categorical_values(workspace, max_unique=15)
        assert len(lines) == 0


class TestIndexFileMultiSheetReadError:
    def test_sheet_read_error(self, tmp_path):
        from unittest.mock import patch
        xlsx = tmp_path / "sheet_err.xlsx"
        pd.DataFrame({"A": [1, 2]}).to_excel(xlsx, index=False, engine="openpyxl")
        with patch("pandas.read_excel", side_effect=RuntimeError("boom")):
            items = index_file_multi(str(xlsx))
        assert len(items) == 1
        assert items[0].error is not None

    def test_empty_sheet_no_columns(self, tmp_path):
        from unittest.mock import patch
        xlsx = tmp_path / "empty_sheet.xlsx"
        pd.DataFrame({"A": [1]}).to_excel(xlsx, index=False, engine="openpyxl")
        empty_df = pd.DataFrame()
        with patch("pandas.read_excel", return_value=empty_df):
            items = index_file_multi(str(xlsx))
        assert len(items) == 1
        assert items[0].error is not None


class TestHydrateWithExcelLive:
    def test_excel_live_truncated_returns_self(self):
        ws = Workspace(
            path="", workbook_name="wb", sheet_name="s1",
            columns=[], row_count=0, indexed_rows=0,
            truncated=True, excel_live=True,
        )
        result = hydrate_workspace_full(ws)
        assert result is ws or result.error is not None


class TestTrimSummaryTailRemoval:
    def test_trim_removes_tail(self, workspace):
        workspace.df = pd.DataFrame({f"Col{i}": range(100) for i in range(10)})
        workspace.columns = list(workspace.df.columns)
        workspace.row_count = 100
        workspace.indexed_rows = 100
        workspace.truncated = False
        summary = get_workspace_summary(workspace, max_context_chars=500)
        assert len(summary) <= 510


class TestIsNontabularEdgeCases:
    def test_operator_precedence(self):
        ws = Workspace(
            path="", workbook_name="", sheet_name="",
            columns=["ColABC", "RealCol"], row_count=10, indexed_rows=10,
            df=pd.DataFrame({"ColABC": [1, 2], "RealCol": [3, 4]}),
        )
        from src.indexing.excel_reader import _is_nontabular
        assert _is_nontabular(ws) is False

    def test_exactly_50_rows_not_flagged(self):
        ws = Workspace(
            path="", workbook_name="", sheet_name="",
            columns=["Unnamed: 0", "Unnamed: 1"], row_count=50, indexed_rows=50,
            df=pd.DataFrame({"Unnamed: 0": range(50), "Unnamed: 1": range(50)}),
        )
        from src.indexing.excel_reader import _is_nontabular
        assert _is_nontabular(ws) is False


class TestWorkbookOverviewDeepCoverage:
    def test_invalid_format_returns_error(self, tmp_path):
        txt = tmp_path / "data.txt"
        txt.write_text("hello")
        result = get_workbook_overview(str(txt))
        assert "Err" in result or "formato" in result.lower() or "invalid" in result.lower()

    def test_corrupt_file_open_error(self, tmp_path):
        bad = tmp_path / "corrupt.xlsx"
        bad.write_bytes(b"PK\x03\x04" + b"\x00" * 100)
        result = get_workbook_overview(str(bad))
        assert result.startswith("[E") or "índex" in result.lower() or "zip" in result.lower()

    def test_sheet_read_error_in_overview(self, tmp_path):
        from unittest.mock import patch
        xlsx = tmp_path / "sheet_err_ov.xlsx"
        pd.DataFrame({"A": [1]}).to_excel(xlsx, index=False, engine="openpyxl")
        call_count = [0]
        original_read = pd.read_excel

        def flaky_read(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1 and "nrows" in kwargs:
                raise RuntimeError("sheet error")
            return original_read(*args, **kwargs)

        with patch("pandas.read_excel", side_effect=flaky_read):
            result = get_workbook_overview(str(xlsx))
        assert "erro de leitura" in result

    def test_empty_sheet_no_cols_in_overview(self, tmp_path):
        from unittest.mock import patch
        xlsx = tmp_path / "empty_overview.xlsx"
        pd.DataFrame({"A": [1]}).to_excel(xlsx, index=False, engine="openpyxl")
        empty_df = pd.DataFrame()
        call_count = [0]
        original_read = pd.read_excel

        def patched_read(*args, **kwargs):
            call_count[0] += 1
            if "nrows" in kwargs:
                return empty_df
            return original_read(*args, **kwargs)

        with patch("pandas.read_excel", side_effect=patched_read):
            result = get_workbook_overview(str(xlsx))
        assert "vazia" in result

    def test_more_than_6_columns_in_overview(self, tmp_path):
        xlsx = tmp_path / "wide_ov.xlsx"
        cols = {f"Col{i}": [1] for i in range(8)}
        pd.DataFrame(cols).to_excel(xlsx, index=False, engine="openpyxl")
        result = get_workbook_overview(str(xlsx))
        assert "..." in result

    def test_total_rows_read_error(self, tmp_path):
        from unittest.mock import patch
        xlsx = tmp_path / "row_err.xlsx"
        pd.DataFrame({"A": range(10)}).to_excel(xlsx, index=False, engine="openpyxl")
        call_count = [0]
        original_read = pd.read_excel
        original_load = __import__("openpyxl").load_workbook

        def patched_read(*args, **kwargs):
            call_count[0] += 1
            if "nrows" not in kwargs and call_count[0] > 1:
                raise RuntimeError("can't count rows")
            return original_read(*args, **kwargs)

        load_count = [0]

        def patched_load(*args, **kwargs):
            load_count[0] += 1
            if load_count[0] > 1:
                raise RuntimeError("can't count rows")
            return original_load(*args, **kwargs)

        with patch("pandas.read_excel", side_effect=patched_read), \
             patch("openpyxl.load_workbook", side_effect=patched_load):
            result = get_workbook_overview(str(xlsx))
        assert "?" in result

    def test_not_found(self, tmp_path):
        result = get_workbook_overview(str(tmp_path / "nonexistent.xlsx"))
        assert "Err" in result or "não encontrad" in result.lower()


class TestColLetter:
    def test_single_letters(self):
        from src.indexing.excel_reader import _col_letter
        assert _col_letter(0) == "A"
        assert _col_letter(1) == "B"
        assert _col_letter(25) == "Z"

    def test_double_letters(self):
        from src.indexing.excel_reader import _col_letter
        assert _col_letter(26) == "AA"
        assert _col_letter(27) == "AB"
        assert _col_letter(51) == "AZ"
        assert _col_letter(52) == "BA"


class TestBuildA1Map:
    def test_basic(self):
        from src.indexing.excel_reader import _build_a1_map
        ws = Workspace(
            path="/t.xlsx", workbook_name="t", sheet_name="S",
            columns=["Nome", "Idade", "Cidade"],
            row_count=3, indexed_rows=3,
            df=pd.DataFrame({"Nome": ["a"], "Idade": [1], "Cidade": ["x"]}),
            excel_live=False, excel_book_name=None, error=None,
        )
        result = _build_a1_map(ws)
        assert "A=Nome" in result
        assert "B=Idade" in result
        assert "C=Cidade" in result

    def test_empty_columns(self):
        from src.indexing.excel_reader import _build_a1_map
        ws = Workspace(
            path="/t.xlsx", workbook_name="t", sheet_name="S",
            columns=[], row_count=0, indexed_rows=0, df=None,
            excel_live=False, excel_book_name=None, error=None,
        )
        assert _build_a1_map(ws) == ""

    def test_many_columns(self):
        from src.indexing.excel_reader import _build_a1_map
        cols = [f"Col{i}" for i in range(30)]
        ws = Workspace(
            path="/t.xlsx", workbook_name="t", sheet_name="S",
            columns=cols, row_count=1, indexed_rows=1,
            df=pd.DataFrame({c: [0] for c in cols}),
            excel_live=False, excel_book_name=None, error=None,
        )
        result = _build_a1_map(ws)
        assert "..." in result


class TestDetectHeaderOffset:
    def test_detects_header_row(self):
        from src.indexing.excel_reader import _detect_header_offset
        df = pd.DataFrame({
            "0": ["title", "Alice", "Bob"],
            "1": ["name", 25, 30],
            "2": ["city", "SP", "RJ"],
        })
        ws = Workspace(
            path="/t.xlsx", workbook_name="t", sheet_name="S",
            columns=["0", "1", "2"], row_count=3, indexed_rows=3, df=df,
            excel_live=False, excel_book_name=None, error=None,
        )
        offset = _detect_header_offset(ws)
        assert offset >= 1

    def test_no_good_header(self):
        from src.indexing.excel_reader import _detect_header_offset
        df = pd.DataFrame({"A": [1, 2, 3], "B": [4, 5, 6]})
        ws = Workspace(
            path="/t.xlsx", workbook_name="t", sheet_name="S",
            columns=["A", "B"], row_count=3, indexed_rows=3, df=df,
            excel_live=False, excel_book_name=None, error=None,
        )
        offset = _detect_header_offset(ws)
        assert offset == 0

    def test_empty_df(self):
        from src.indexing.excel_reader import _detect_header_offset
        ws = Workspace(
            path="/t.xlsx", workbook_name="t", sheet_name="S",
            columns=[], row_count=0, indexed_rows=0, df=pd.DataFrame(),
            excel_live=False, excel_book_name=None, error=None,
        )
        assert _detect_header_offset(ws) == 0


class TestApplyHeaderOffset:
    def test_shifts_header(self):
        from src.indexing.excel_reader import apply_header_offset
        df = pd.DataFrame({
            "0": ["Nome", "Alice", "Bob"],
            "1": ["Idade", 25, 30],
        })
        ws = Workspace(
            path="/t.xlsx", workbook_name="t", sheet_name="S",
            columns=["0", "1"], row_count=3, indexed_rows=3, df=df,
            excel_live=False, excel_book_name=None, error=None,
        )
        new_ws = apply_header_offset(ws, 1)
        assert "Nome" in new_ws.columns
        assert "Idade" in new_ws.columns
        assert len(new_ws.df) == 2

    def test_zero_offset_noop(self):
        from src.indexing.excel_reader import apply_header_offset
        ws = Workspace(
            path="/t.xlsx", workbook_name="t", sheet_name="S",
            columns=["A", "B"], row_count=2, indexed_rows=2,
            df=pd.DataFrame({"A": [1, 2], "B": [3, 4]}),
            excel_live=False, excel_book_name=None, error=None,
        )
        result = apply_header_offset(ws, 0)
        assert result is ws

    def test_duplicate_headers_get_suffix(self):
        from src.indexing.excel_reader import apply_header_offset
        df = pd.DataFrame({
            "0": ["X", "a", "b"],
            "1": ["X", "c", "d"],
        })
        ws = Workspace(
            path="/t.xlsx", workbook_name="t", sheet_name="S",
            columns=["0", "1"], row_count=3, indexed_rows=3, df=df,
            excel_live=False, excel_book_name=None, error=None,
        )
        new_ws = apply_header_offset(ws, 1)
        assert "X" in new_ws.columns
        assert "X_2" in new_ws.columns


class TestA1MapInSummary:
    def test_a1_map_appears(self):
        ws = Workspace(
            path="/t.xlsx", workbook_name="t", sheet_name="S",
            columns=["Nome", "Idade"],
            row_count=2, indexed_rows=2,
            df=pd.DataFrame({"Nome": ["Alice"], "Idade": [25]}),
            excel_live=False, excel_book_name=None, error=None,
        )
        result = get_workspace_summary(ws)
        assert "Referência A1" in result

    def test_header_hint_when_detected(self):
        df = pd.DataFrame({
            "0": ["Nome", "Alice"],
            "1": ["Idade", 25],
        })
        ws = Workspace(
            path="/t.xlsx", workbook_name="t", sheet_name="S",
            columns=["0", "1"], row_count=2, indexed_rows=2, df=df,
            excel_live=False, excel_book_name=None, error=None,
        )
        result = get_workspace_summary(ws)
        assert "cabeçalho" in result.lower() or "adjust_header" in result.lower()
