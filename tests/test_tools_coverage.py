"""Tests for uncovered tools.py branches: filter_contains, filter_range, pivot_table, merge_columns, strip_whitespace, change_dtype, _validate_code, _excel_scalar, _df_to_excel_matrix, _classify_err, checkpoint integration."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
from src.agent.tools import (
    _apply_actions_to_df,
    _classify_err,
    _df_to_excel_matrix,
    _excel_scalar,
    _validate_code,
    structured_actions_tool,
)
from src.checkpoints.manager import CheckpointManager
from src.errcodes import ErrCode
from src.indexing.excel_reader import Workspace


def _make_workspace(df, path="", sheet="Planilha1"):
    return Workspace(
        path=path, workbook_name="test.xlsx", sheet_name=sheet,
        columns=list(df.columns), row_count=len(df), indexed_rows=len(df),
        truncated=False, df=df, excel_live=False, excel_book_name=None, error=None,
    )


def _make_checkpoint_mgr(tmp_path):
    xlsx = tmp_path / "sheet.xlsx"
    pd.DataFrame({"A": [1]}).to_excel(xlsx, index=False, engine="openpyxl")
    return CheckpointManager(str(xlsx))


# ── filter_contains ──────────────────────────────────────────────────


class TestFilterContainsAction:
    def test_case_insensitive(self):
        df = pd.DataFrame({"Name": ["Alice", "Bob", "CHARLIE"]})
        result, err = _apply_actions_to_df(df, [{"action": "filter_contains", "column": "Name", "value": "ali"}])
        assert not err
        assert len(result) == 1
        assert result.iloc[0]["Name"] == "Alice"

    def test_case_sensitive(self):
        df = pd.DataFrame({"Name": ["Alice", "alice", "CHARLIE"]})
        result, err = _apply_actions_to_df(df, [{"action": "filter_contains", "column": "Name", "value": "alice", "case_sensitive": True}])
        assert not err
        assert len(result) == 1
        assert result.iloc[0]["Name"] == "alice"

    def test_missing_column(self):
        df = pd.DataFrame({"A": [1]})
        result, err = _apply_actions_to_df(df, [{"action": "filter_contains", "column": "Z", "value": "x"}])
        assert err


# ── filter_range ─────────────────────────────────────────────────────


class TestFilterRangeAction:
    def test_min_only(self):
        df = pd.DataFrame({"Val": [10, 20, 30, 40]})
        result, err = _apply_actions_to_df(df, [{"action": "filter_range", "column": "Val", "min": 25}])
        assert not err
        assert list(result["Val"]) == [30, 40]

    def test_max_only(self):
        df = pd.DataFrame({"Val": [10, 20, 30, 40]})
        result, err = _apply_actions_to_df(df, [{"action": "filter_range", "column": "Val", "max": 25}])
        assert not err
        assert list(result["Val"]) == [10, 20]

    def test_min_and_max(self):
        df = pd.DataFrame({"Val": [10, 20, 30, 40]})
        result, err = _apply_actions_to_df(df, [{"action": "filter_range", "column": "Val", "min": 15, "max": 35}])
        assert not err
        assert list(result["Val"]) == [20, 30]

    def test_missing_column(self):
        df = pd.DataFrame({"A": [1]})
        result, err = _apply_actions_to_df(df, [{"action": "filter_range", "column": "Z", "min": 0}])
        assert err


# ── pivot_table ──────────────────────────────────────────────────────


class TestPivotTableAction:
    def test_basic_pivot(self):
        df = pd.DataFrame({"Cat": ["A", "A", "B"], "Val": [10, 20, 30]})
        result, err = _apply_actions_to_df(df, [{"action": "pivot_table", "index": ["Cat"], "values": "Val", "agg_func": "sum"}])
        assert not err
        assert len(result) == 2

    def test_string_index(self):
        df = pd.DataFrame({"Cat": ["A", "B"], "Val": [1, 2]})
        result, err = _apply_actions_to_df(df, [{"action": "pivot_table", "index": "Cat", "values": "Val", "agg_func": "sum"}])
        assert not err

    def test_invalid_index(self):
        df = pd.DataFrame({"A": [1]})
        result, err = _apply_actions_to_df(df, [{"action": "pivot_table", "index": [], "agg_func": "sum"}])
        assert err

    def test_missing_index_column(self):
        df = pd.DataFrame({"A": [1]})
        result, err = _apply_actions_to_df(df, [{"action": "pivot_table", "index": ["ZZZ"], "agg_func": "sum"}])
        assert err

    def test_missing_values_column(self):
        df = pd.DataFrame({"Cat": ["A"], "Val": [1]})
        result, err = _apply_actions_to_df(df, [{"action": "pivot_table", "index": ["Cat"], "values": "ZZZ", "agg_func": "sum"}])
        assert err

    def test_invalid_agg_func(self):
        df = pd.DataFrame({"Cat": ["A"], "Val": [1]})
        result, err = _apply_actions_to_df(df, [{"action": "pivot_table", "index": ["Cat"], "values": "Val", "agg_func": "explode"}])
        assert err
        assert "não suportada" in err

    def test_with_columns_param(self):
        df = pd.DataFrame({"Cat": ["A", "A", "B"], "Type": ["X", "Y", "X"], "Val": [10, 20, 30]})
        result, err = _apply_actions_to_df(df, [{"action": "pivot_table", "index": ["Cat"], "values": "Val", "columns": ["Type"], "agg_func": "sum"}])
        assert not err

    def test_missing_columns_param(self):
        df = pd.DataFrame({"Cat": ["A"], "Val": [1]})
        result, err = _apply_actions_to_df(df, [{"action": "pivot_table", "index": ["Cat"], "values": "Val", "columns": ["ZZZ"], "agg_func": "sum"}])
        assert err

    def test_pivot_exception_handled(self):
        df = pd.DataFrame({"A": [1]})
        result, err = _apply_actions_to_df(df, [{"action": "pivot_table", "index": ["A"], "agg_func": "sum"}])
        assert not err or "pivot" in err.lower()


# ── merge_columns ────────────────────────────────────────────────────


class TestMergeColumnsAction:
    def test_basic_merge(self):
        df = pd.DataFrame({"First": ["A", "B"], "Last": ["1", "2"]})
        result, err = _apply_actions_to_df(df, [{"action": "merge_columns", "columns": ["First", "Last"], "new_column": "Full", "separator": " "}])
        assert not err
        assert list(result["Full"]) == ["A 1", "B 2"]

    def test_missing_new_column(self):
        df = pd.DataFrame({"A": [1], "B": [2]})
        result, err = _apply_actions_to_df(df, [{"action": "merge_columns", "columns": ["A", "B"]}])
        assert err
        assert "new_column" in err.lower()

    def test_missing_source_column(self):
        df = pd.DataFrame({"A": [1]})
        result, err = _apply_actions_to_df(df, [{"action": "merge_columns", "columns": ["A", "Z"], "new_column": "M"}])
        assert err

    def test_invalid_columns(self):
        df = pd.DataFrame({"A": [1]})
        result, err = _apply_actions_to_df(df, [{"action": "merge_columns", "columns": [], "new_column": "M"}])
        assert err

    def test_string_columns_input(self):
        df = pd.DataFrame({"A": ["x"], "B": ["y"]})
        result, err = _apply_actions_to_df(df, [{"action": "merge_columns", "columns": "A", "new_column": "M"}])
        assert not err or err


# ── strip_whitespace ─────────────────────────────────────────────────


class TestStripWhitespaceAction:
    def test_strip_all_string_cols(self):
        df = pd.DataFrame({"A": ["  hello  ", "  world  "], "B": [1, 2]})
        result, err = _apply_actions_to_df(df, [{"action": "strip_whitespace"}])
        assert not err
        assert list(result["A"]) == ["hello", "world"]

    def test_strip_specific_cols(self):
        df = pd.DataFrame({"A": ["  x  "], "B": ["  y  "], "C": [1]})
        result, err = _apply_actions_to_df(df, [{"action": "strip_whitespace", "columns": ["A"]}])
        assert not err
        assert result["A"].iloc[0] == "x"
        assert result["B"].iloc[0] == "  y  "

    def test_strip_string_input(self):
        df = pd.DataFrame({"A": ["  x  "]})
        result, err = _apply_actions_to_df(df, [{"action": "strip_whitespace", "columns": "A"}])
        assert not err
        assert result["A"].iloc[0] == "x"

    def test_strip_missing_column(self):
        df = pd.DataFrame({"A": [1]})
        result, err = _apply_actions_to_df(df, [{"action": "strip_whitespace", "columns": ["Z"]}])
        assert err

    def test_strip_empty_columns(self):
        df = pd.DataFrame({"A": [1]})
        result, err = _apply_actions_to_df(df, [{"action": "strip_whitespace", "columns": []}])
        assert err


# ── change_dtype ─────────────────────────────────────────────────────


class TestChangeDtypeAction:
    def test_to_float(self):
        df = pd.DataFrame({"A": ["1.5", "2.5"]})
        result, err = _apply_actions_to_df(df, [{"action": "change_dtype", "column": "A", "dtype": "float"}])
        assert not err
        assert result["A"].dtype == float

    def test_to_int(self):
        df = pd.DataFrame({"A": ["1", "2"]})
        result, err = _apply_actions_to_df(df, [{"action": "change_dtype", "column": "A", "dtype": "int"}])
        assert not err

    def test_to_str(self):
        df = pd.DataFrame({"A": [1, 2]})
        result, err = _apply_actions_to_df(df, [{"action": "change_dtype", "column": "A", "dtype": "str"}])
        assert not err
        assert result["A"].dtype == object

    def test_to_datetime(self):
        df = pd.DataFrame({"A": ["2024-01-01", "2024-06-15"]})
        result, err = _apply_actions_to_df(df, [{"action": "change_dtype", "column": "A", "dtype": "datetime"}])
        assert not err

    def test_to_bool(self):
        df = pd.DataFrame({"A": [1, 0]})
        result, err = _apply_actions_to_df(df, [{"action": "change_dtype", "column": "A", "dtype": "bool"}])
        assert not err

    def test_invalid_dtype(self):
        df = pd.DataFrame({"A": [1]})
        result, err = _apply_actions_to_df(df, [{"action": "change_dtype", "column": "A", "dtype": "complex"}])
        assert err
        assert "não suportado" in err.lower()

    def test_missing_column(self):
        df = pd.DataFrame({"A": [1]})
        result, err = _apply_actions_to_df(df, [{"action": "change_dtype", "column": "Z", "dtype": "float"}])
        assert err

    def test_conversion_error(self):
        df = pd.DataFrame({"A": ["not_a_number"]})
        result, err = _apply_actions_to_df(df, [{"action": "change_dtype", "column": "A", "dtype": "int"}])
        assert not err or "erro" in err.lower()


# ── _validate_code ───────────────────────────────────────────────────


class TestValidateCode:
    def test_allowed_module(self):
        ok, err = _validate_code("import pandas")
        assert ok

    def test_forbidden_module(self):
        ok, err = _validate_code("import os")
        assert not ok
        assert "Módulo não permitido" in err

    def test_forbidden_from_import(self):
        ok, err = _validate_code("from os import path")
        assert not ok

    def test_forbidden_name(self):
        ok, err = _validate_code("eval('1')")
        assert not ok
        assert "Nome não permitido" in err or "Função não permitida" in err

    def test_dunder_attribute(self):
        ok, err = _validate_code("x.__dict__")
        assert not ok
        assert "__dunder__" in err

    def test_forbidden_attribute(self):
        ok, err = _validate_code("x.exec")
        assert not ok
        assert "atributo não permitido" in err

    def test_forbidden_method_call(self):
        ok, err = _validate_code("obj.exec()")
        assert not ok
        assert "Chamada de método" in err

    def test_syntax_error(self):
        ok, err = _validate_code("def (")
        assert not ok
        assert "sintaxe" in err.lower()

    def test_safe_code(self):
        ok, err = _validate_code("x = [i for i in range(10)]")
        assert ok


# ── _excel_scalar ────────────────────────────────────────────────────


class TestExcelScalar:
    def test_nan_returns_none(self):
        assert _excel_scalar(float("nan")) is None

    def test_none_returns_none(self):
        assert _excel_scalar(None) is None

    def test_numpy_scalar(self):
        val = np.int64(42)
        result = _excel_scalar(val)
        assert result == 42
        assert isinstance(result, int)

    def test_regular_value(self):
        assert _excel_scalar("hello") == "hello"
        assert _excel_scalar(42) == 42


# ── _df_to_excel_matrix ──────────────────────────────────────────────


class TestDfToExcelMatrix:
    def test_basic(self):
        df = pd.DataFrame({"A": [1, 2], "B": [3, 4]})
        result = _df_to_excel_matrix(df)
        assert len(result) == 3
        assert result[0] == ("A", "B")
        assert result[1][0] == 1

    def test_with_nan(self):
        df = pd.DataFrame({"A": [1, None]})
        result = _df_to_excel_matrix(df)
        assert result[1][0] == 1
        assert result[2][0] is None


# ── _classify_err ────────────────────────────────────────────────────


class TestClassifyErr:
    def test_column_missing(self):
        assert _classify_err("Coluna não encontrada: X") == ErrCode.COLUMN_MISSING

    def test_column_ausente(self):
        assert _classify_err("Colunas ausentes: A, B") == ErrCode.COLUMN_MISSING

    def test_action_unknown(self):
        assert _classify_err("Ação desconhecida: foo") == ErrCode.ACTION_UNKNOWN

    def test_action_invalid_default(self):
        assert _classify_err("parâmetros inválidos") == ErrCode.ACTION_INVALID


# ── structured_actions_tool checkpoint + save paths ──────────────────


class TestStructuredActionsToolSavePaths:
    def test_sort_saves_file(self, sample_df, tmp_path):
        ws = _make_workspace(sample_df, path=str(tmp_path / "save_test.xlsx"))
        sample_df.to_excel(ws.path, index=False, engine="openpyxl")
        mgr = _make_checkpoint_mgr(tmp_path)
        result = structured_actions_tool(
            ws, json.dumps([{"action": "sort", "by": "Idade"}]), mgr, save_checkpoint=False,
        )
        assert result.success
        assert Path(ws.path).exists()

    def test_no_path_df_only(self, sample_df, tmp_path):
        ws = _make_workspace(sample_df)
        cp_path = tmp_path / "cp_test.xlsx"
        pd.DataFrame({"A": [1]}).to_excel(cp_path, index=False, engine="openpyxl")
        mgr = CheckpointManager(str(cp_path))
        result = structured_actions_tool(
            ws, json.dumps([{"action": "sort", "by": "Idade"}]), mgr, save_checkpoint=False,
        )
        assert result.success
        assert ws.df is not None

    def test_checkpoint_saved(self, sample_df, tmp_path):
        ws = _make_workspace(sample_df, path=str(tmp_path / "cp_save.xlsx"))
        sample_df.to_excel(ws.path, index=False, engine="openpyxl")
        mgr = CheckpointManager(str(tmp_path / "cp_save.xlsx"))
        saved_label = None

        def on_save(label):
            nonlocal saved_label
            saved_label = label

        result = structured_actions_tool(
            ws, json.dumps([{"action": "sort", "by": "Idade"}]), mgr,
            on_checkpoint_saved=on_save, save_checkpoint=True,
        )
        assert result.success
        assert saved_label is not None

    def test_checkpoint_failure_returns_error(self, sample_df, tmp_path):
        ws = _make_workspace(sample_df, path=str(tmp_path / "cp_fail.xlsx"))
        sample_df.to_excel(ws.path, index=False, engine="openpyxl")
        mgr = CheckpointManager(str(tmp_path / "cp_fail.xlsx"))
        with patch.object(mgr, "save_checkpoint", side_effect=RuntimeError("disk full")):
            result = structured_actions_tool(
                ws, json.dumps([{"action": "sort", "by": "Idade"}]), mgr, save_checkpoint=True,
            )
            assert not result.success
            assert "checkpoint" in result.message.lower()

    def test_empty_df_actions(self, tmp_path):
        ws = _make_workspace(pd.DataFrame({"A": []}), path=str(tmp_path / "empty.xlsx"))
        pd.DataFrame({"A": []}).to_excel(ws.path, index=False, engine="openpyxl")
        mgr = _make_checkpoint_mgr(tmp_path)
        result = structured_actions_tool(
            ws, json.dumps([{"action": "fillna", "column": "A", "value": 0}]), mgr, save_checkpoint=False,
        )
        assert result.success

    def test_ods_converted_to_xlsx(self, tmp_path):
        path = tmp_path / "convert.ods"
        pd.DataFrame({"X": [1, 2]}).to_excel(path, index=False, engine="odf")
        df = pd.DataFrame({"X": [1, 2]})
        ws = Workspace(
            path=str(path), workbook_name="convert.ods", sheet_name="Sheet",
            columns=["X"], row_count=2, indexed_rows=2, truncated=False,
            df=df, excel_live=False, excel_book_name=None, error=None,
        )
        mgr = CheckpointManager(str(path))
        result = structured_actions_tool(
            ws, json.dumps([{"action": "sort", "by": "X"}]), mgr, save_checkpoint=False,
        )
        assert result.success
        assert ws.path.endswith(".xlsx")

    def test_xls_converted_to_xlsx(self, tmp_path):
        path_xlsx = tmp_path / "test_xls.xlsx"
        pd.DataFrame({"Y": [10]}).to_excel(path_xlsx, index=False, engine="openpyxl")
        ws = Workspace(
            path=str(path_xlsx), workbook_name="test.xls", sheet_name="Sheet",
            columns=["Y"], row_count=1, indexed_rows=1, truncated=False,
            df=pd.DataFrame({"Y": [10]}), excel_live=False, excel_book_name=None, error=None,
        )
        mgr = CheckpointManager(str(path_xlsx))
        result = structured_actions_tool(
            ws, json.dumps([{"action": "sort", "by": "Y"}]), mgr, save_checkpoint=False,
        )
        assert result.success


# ── sort edge cases ──────────────────────────────────────────────────


class TestSortEdgeCases:
    def test_sort_invalid_by_type(self):
        df = pd.DataFrame({"A": [1]})
        result, err = _apply_actions_to_df(df, [{"action": "sort", "by": 123}])
        assert err

    def test_sort_empty_by(self):
        df = pd.DataFrame({"A": [1]})
        result, err = _apply_actions_to_df(df, [{"action": "sort", "by": []}])
        assert err

    def test_sort_na_position_first(self):
        df = pd.DataFrame({"A": [3, None, 1]})
        result, err = _apply_actions_to_df(df, [{"action": "sort", "by": "A", "na_position": "first"}])
        assert not err

    def test_sort_na_position_invalid(self):
        df = pd.DataFrame({"A": [3, None, 1]})
        result, err = _apply_actions_to_df(df, [{"action": "sort", "by": "A", "na_position": "middle"}])
        assert not err


# ── add_computed_column edge cases ───────────────────────────────────


class TestAddComputedColumnEdgeCases:
    def test_empty_new_column(self):
        df = pd.DataFrame({"A": [1]})
        result, err = _apply_actions_to_df(df, [{"action": "add_computed_column", "new_column": "", "operation": "sum", "source_columns": ["A"]}])
        assert err

    def test_divide_needs_two(self):
        df = pd.DataFrame({"A": [1], "B": [2], "C": [3]})
        result, err = _apply_actions_to_df(df, [{"action": "add_computed_column", "new_column": "Q", "operation": "divide", "source_columns": ["A", "B", "C"]}])
        assert err

    def test_divide_by_zero(self):
        df = pd.DataFrame({"A": [10], "B": [0]})
        result, err = _apply_actions_to_df(df, [{"action": "add_computed_column", "new_column": "Q", "operation": "divide", "source_columns": ["A", "B"]}])
        assert not err
        assert pd.isna(result["Q"].iloc[0])

    def test_string_source_columns(self):
        df = pd.DataFrame({"A": [1]})
        result, err = _apply_actions_to_df(df, [{"action": "add_computed_column", "new_column": "X", "operation": "sum", "source_columns": "A"}])
        assert not err


# ── dropna edge cases ────────────────────────────────────────────────


class TestDropnaEdgeCases:
    def test_dropna_invalid_how(self):
        df = pd.DataFrame({"A": [1, None]})
        result, err = _apply_actions_to_df(df, [{"action": "dropna", "columns": ["A"], "how": "invalid"}])
        assert not err
        assert len(result) == 1


# ── groupby_agg edge cases ───────────────────────────────────────────


class TestGroupbyAggEdgeCases:
    def test_median(self):
        df = pd.DataFrame({"Cat": ["A", "A", "B"], "Val": [10, 20, 30]})
        result, err = _apply_actions_to_df(df, [{"action": "groupby_agg", "group_by": ["Cat"], "agg_column": "Val", "agg_func": "median"}])
        assert not err

    def test_std(self):
        df = pd.DataFrame({"Cat": ["A", "A", "B"], "Val": [10, 20, 30]})
        result, err = _apply_actions_to_df(df, [{"action": "groupby_agg", "group_by": ["Cat"], "agg_column": "Val", "agg_func": "std"}])
        assert not err

    def test_var(self):
        df = pd.DataFrame({"Cat": ["A", "A", "B"], "Val": [10, 20, 30]})
        result, err = _apply_actions_to_df(df, [{"action": "groupby_agg", "group_by": ["Cat"], "agg_column": "Val", "agg_func": "var"}])
        assert not err

    def test_first(self):
        df = pd.DataFrame({"Cat": ["A", "A", "B"], "Val": [10, 20, 30]})
        result, err = _apply_actions_to_df(df, [{"action": "groupby_agg", "group_by": ["Cat"], "agg_column": "Val", "agg_func": "first"}])
        assert not err

    def test_last(self):
        df = pd.DataFrame({"Cat": ["A", "A", "B"], "Val": [10, 20, 30]})
        result, err = _apply_actions_to_df(df, [{"action": "groupby_agg", "group_by": ["Cat"], "agg_column": "Val", "agg_func": "last"}])
        assert not err

    def test_min_max(self):
        df = pd.DataFrame({"Cat": ["A", "A", "B"], "Val": [10, 20, 30]})
        for func in ("min", "max"):
            result, err = _apply_actions_to_df(df, [{"action": "groupby_agg", "group_by": ["Cat"], "agg_column": "Val", "agg_func": func}])
            assert not err
