"""Unit tests for structured_actions_tool — all 10 action types."""
from __future__ import annotations

import json

import pandas as pd
from src.agent.tools import _apply_actions_to_df, _normalize_actions, structured_actions_tool
from src.checkpoints.manager import CheckpointManager
from src.indexing.excel_reader import Workspace


def _make_workspace(df, path="", sheet="Planilha1"):
    return Workspace(
        path=path,
        workbook_name="test.xlsx",
        sheet_name=sheet,
        columns=list(df.columns),
        row_count=len(df),
        indexed_rows=len(df),
        truncated=False,
        df=df,
        excel_live=False,
    )


def _make_checkpoint_mgr(tmp_path):
    xlsx = tmp_path / "sheet.xlsx"
    pd.DataFrame({"A": [1]}).to_excel(xlsx, index=False, engine="openpyxl")
    return CheckpointManager(str(xlsx))


# ── _normalize_actions ──────────────────────────────────────────────


class TestNormalizeActions:
    def test_valid_list(self):
        actions, err = _normalize_actions(json.dumps([{"action": "sort", "by": "A"}]))
        assert not err
        assert len(actions) == 1

    def test_valid_dict_wrapper(self):
        actions, err = _normalize_actions(json.dumps({"actions": [{"action": "sort", "by": "A"}]}))
        assert not err
        assert len(actions) == 1

    def test_invalid_json(self):
        actions, err = _normalize_actions("not json{{{")
        assert err
        assert actions == []

    def test_empty_list(self):
        actions, err = _normalize_actions("[]")
        assert err
        assert actions == []

    def test_non_dict_action(self):
        actions, err = _normalize_actions(json.dumps([42]))
        assert err

    def test_missing_action_key(self):
        actions, err = _normalize_actions(json.dumps([{"by": "A"}]))
        assert err


# ── sort ─────────────────────────────────────────────────────────────


class TestSortAction:
    def test_sort_ascending(self, sample_df):
        result, err = _apply_actions_to_df(sample_df, [{"action": "sort", "by": "Idade"}])
        assert not err
        assert list(result["Idade"]) == [22, 25, 28, 30, 35]

    def test_sort_descending(self, sample_df):
        result, err = _apply_actions_to_df(sample_df, [{"action": "sort", "by": "Idade", "ascending": False}])
        assert not err
        assert list(result["Idade"]) == [35, 30, 28, 25, 22]

    def test_sort_missing_column(self, sample_df):
        result, err = _apply_actions_to_df(sample_df, [{"action": "sort", "by": "Inexistente"}])
        assert err
        assert result is None

    def test_sort_multiple_columns(self):
        df = pd.DataFrame({"A": [1, 1, 2], "B": [3, 1, 2]})
        result, err = _apply_actions_to_df(df, [{"action": "sort", "by": ["A", "B"]}])
        assert not err
        assert list(result["B"]) == [1, 3, 2]


# ── fillna ───────────────────────────────────────────────────────────


class TestFillnaAction:
    def test_fillna_numeric(self):
        df = pd.DataFrame({"A": [1, None, 3], "B": [4, 5, 6]})
        result, err = _apply_actions_to_df(df, [{"action": "fillna", "column": "A", "value": 0}])
        assert not err
        assert result["A"].isna().sum() == 0
        assert result["A"].iloc[1] == 0

    def test_fillna_string(self):
        df = pd.DataFrame({"A": ["x", None, "z"]})
        result, err = _apply_actions_to_df(df, [{"action": "fillna", "column": "A", "value": "MISSING"}])
        assert not err
        assert result["A"].iloc[1] == "MISSING"

    def test_fillna_missing_column(self):
        df = pd.DataFrame({"A": [1, 2]})
        result, err = _apply_actions_to_df(df, [{"action": "fillna", "column": "Z", "value": 0}])
        assert err


# ── replace ──────────────────────────────────────────────────────────


class TestReplaceAction:
    def test_replace_value(self, sample_df):
        result, err = _apply_actions_to_df(sample_df, [{"action": "replace", "column": "Cidade", "from": "Rio", "to": "Rio de Janeiro"}])
        assert not err
        assert "Rio de Janeiro" in result["Cidade"].values

    def test_replace_missing_column(self, sample_df):
        result, err = _apply_actions_to_df(sample_df, [{"action": "replace", "column": "ZZZ", "from": "a", "to": "b"}])
        assert err


# ── rename_column ────────────────────────────────────────────────────


class TestRenameColumnAction:
    def test_rename(self, sample_df):
        result, err = _apply_actions_to_df(sample_df, [{"action": "rename_column", "from": "Nome", "to": "Pessoa"}])
        assert not err
        assert "Pessoa" in result.columns
        assert "Nome" not in result.columns

    def test_rename_missing_column(self, sample_df):
        result, err = _apply_actions_to_df(sample_df, [{"action": "rename_column", "from": "ZZZ", "to": "YYY"}])
        assert err

    def test_rename_empty_names(self, sample_df):
        result, err = _apply_actions_to_df(sample_df, [{"action": "rename_column", "from": "", "to": ""}])
        assert err


# ── drop_columns ─────────────────────────────────────────────────────


class TestDropColumnsAction:
    def test_drop_single(self, sample_df):
        result, err = _apply_actions_to_df(sample_df, [{"action": "drop_columns", "columns": ["Salário"]}])
        assert not err
        assert "Salário" not in result.columns
        assert "Nome" in result.columns

    def test_drop_multiple(self, sample_df):
        result, err = _apply_actions_to_df(sample_df, [{"action": "drop_columns", "columns": ["Salário", "Idade"]}])
        assert not err
        assert len(result.columns) == 2

    def test_drop_string_input(self, sample_df):
        result, err = _apply_actions_to_df(sample_df, [{"action": "drop_columns", "columns": "Salário"}])
        assert not err
        assert "Salário" not in result.columns

    def test_drop_missing_column(self, sample_df):
        result, err = _apply_actions_to_df(sample_df, [{"action": "drop_columns", "columns": ["NONEXISTENT"]}])
        assert err

    def test_drop_empty_list(self, sample_df):
        result, err = _apply_actions_to_df(sample_df, [{"action": "drop_columns", "columns": []}])
        assert err


# ── add_computed_column ──────────────────────────────────────────────


class TestAddComputedColumnAction:
    def test_sum(self):
        df = pd.DataFrame({"A": [10, 20], "B": [5, 15]})
        result, err = _apply_actions_to_df(df, [{"action": "add_computed_column", "new_column": "Total", "operation": "sum", "source_columns": ["A", "B"]}])
        assert not err
        assert list(result["Total"]) == [15.0, 35.0]

    def test_concat(self):
        df = pd.DataFrame({"First": ["A", "B"], "Last": ["1", "2"]})
        result, err = _apply_actions_to_df(df, [{"action": "add_computed_column", "new_column": "Full", "operation": "concat", "source_columns": ["First", "Last"], "separator": "-"}])
        assert not err
        assert list(result["Full"]) == ["A-1", "B-2"]

    def test_subtract(self):
        df = pd.DataFrame({"A": [10, 20], "B": [3, 5]})
        result, err = _apply_actions_to_df(df, [{"action": "add_computed_column", "new_column": "Diff", "operation": "subtract", "source_columns": ["A", "B"]}])
        assert not err
        assert list(result["Diff"]) == [7.0, 15.0]

    def test_divide(self):
        df = pd.DataFrame({"A": [10, 20], "B": [2, 4]})
        result, err = _apply_actions_to_df(df, [{"action": "add_computed_column", "new_column": "Quot", "operation": "divide", "source_columns": ["A", "B"]}])
        assert not err
        assert list(result["Quot"]) == [5.0, 5.0]

    def test_multiply(self):
        df = pd.DataFrame({"A": [3, 4], "B": [5, 6]})
        result, err = _apply_actions_to_df(df, [{"action": "add_computed_column", "new_column": "Prod", "operation": "multiply", "source_columns": ["A", "B"]}])
        assert not err
        assert list(result["Prod"]) == [15.0, 24.0]

    def test_unknown_operation(self):
        df = pd.DataFrame({"A": [1], "B": [2]})
        result, err = _apply_actions_to_df(df, [{"action": "add_computed_column", "new_column": "X", "operation": "modulo", "source_columns": ["A", "B"]}])
        assert err
        assert "operação não suportada" in err.lower() or "modulo" in err.lower()

    def test_missing_source_column(self):
        df = pd.DataFrame({"A": [1]})
        result, err = _apply_actions_to_df(df, [{"action": "add_computed_column", "new_column": "X", "operation": "sum", "source_columns": ["A", "Z"]}])
        assert err

    def test_subtract_needs_two(self):
        df = pd.DataFrame({"A": [1], "B": [2], "C": [3]})
        result, err = _apply_actions_to_df(df, [{"action": "add_computed_column", "new_column": "X", "operation": "subtract", "source_columns": ["A", "B", "C"]}])
        assert err


# ── filter_equals ────────────────────────────────────────────────────


class TestFilterEqualsAction:
    def test_filter_string(self, sample_df):
        result, err = _apply_actions_to_df(sample_df, [{"action": "filter_equals", "column": "Cidade", "value": "Rio"}])
        assert not err
        assert len(result) == 1
        assert result.iloc[0]["Nome"] == "Bob"

    def test_filter_numeric(self, sample_df):
        result, err = _apply_actions_to_df(sample_df, [{"action": "filter_equals", "column": "Idade", "value": 30}])
        assert not err
        assert len(result) == 1
        assert result.iloc[0]["Nome"] == "Alice"

    def test_filter_no_match(self, sample_df):
        result, err = _apply_actions_to_df(sample_df, [{"action": "filter_equals", "column": "Cidade", "value": "Tokyo"}])
        assert not err
        assert len(result) == 0

    def test_filter_missing_column(self, sample_df):
        result, err = _apply_actions_to_df(sample_df, [{"action": "filter_equals", "column": "ZZZ", "value": 1}])
        assert err


# ── dropna ───────────────────────────────────────────────────────────


class TestDropnaAction:
    def test_dropna_all_columns(self):
        df = pd.DataFrame({"A": [1, None, 3], "B": [4, 5, None]})
        result, err = _apply_actions_to_df(df, [{"action": "dropna"}])
        assert not err
        assert len(result) == 1

    def test_dropna_specific_columns(self):
        df = pd.DataFrame({"A": [1, None, 3], "B": [4, 5, None]})
        result, err = _apply_actions_to_df(df, [{"action": "dropna", "columns": ["A"]}])
        assert not err
        assert len(result) == 2

    def test_dropna_how_all(self):
        df = pd.DataFrame({"A": [None, None, 3], "B": [None, 5, 6]})
        result, err = _apply_actions_to_df(df, [{"action": "dropna", "how": "all"}])
        assert not err
        assert len(result) == 2

    def test_dropna_string_columns(self):
        df = pd.DataFrame({"A": [1, None, 3], "B": [4, 5, 6]})
        result, err = _apply_actions_to_df(df, [{"action": "dropna", "columns": "A"}])
        assert not err
        assert len(result) == 2

    def test_dropna_missing_column(self):
        df = pd.DataFrame({"A": [1, 2]})
        result, err = _apply_actions_to_df(df, [{"action": "dropna", "columns": ["Z"]}])
        assert err

    def test_dropna_empty_columns_list(self):
        df = pd.DataFrame({"A": [1, None]})
        result, err = _apply_actions_to_df(df, [{"action": "dropna", "columns": []}])
        assert err


# ── groupby_agg ──────────────────────────────────────────────────────


class TestGroupbyAggAction:
    def test_mean(self):
        df = pd.DataFrame({"Cat": ["A", "A", "B", "B"], "Val": [10, 20, 30, 40]})
        result, err = _apply_actions_to_df(df, [{"action": "groupby_agg", "group_by": ["Cat"], "agg_column": "Val", "agg_func": "mean"}])
        assert not err
        assert len(result) == 2
        assert result.iloc[0]["Val"] == 15.0

    def test_sum(self):
        df = pd.DataFrame({"Cat": ["A", "A", "B"], "Val": [10, 20, 30]})
        result, err = _apply_actions_to_df(df, [{"action": "groupby_agg", "group_by": ["Cat"], "agg_column": "Val", "agg_func": "sum"}])
        assert not err
        assert result.iloc[0]["Val"] == 30

    def test_count(self):
        df = pd.DataFrame({"Cat": ["A", "A", "B"], "Val": [1, 2, 3]})
        result, err = _apply_actions_to_df(df, [{"action": "groupby_agg", "group_by": ["Cat"], "agg_column": "Val", "agg_func": "count"}])
        assert not err
        assert result.iloc[0]["Val"] == 2

    def test_string_group_by(self):
        df = pd.DataFrame({"Cat": "A", "Val": [10, 20]})
        result, err = _apply_actions_to_df(df, [{"action": "groupby_agg", "group_by": "Cat", "agg_column": "Val", "agg_func": "sum"}])
        assert not err

    def test_missing_group_by(self):
        df = pd.DataFrame({"Cat": ["A"], "Val": [1]})
        result, err = _apply_actions_to_df(df, [{"action": "groupby_agg", "group_by": [], "agg_column": "Val", "agg_func": "mean"}])
        assert err

    def test_missing_agg_column(self):
        df = pd.DataFrame({"Cat": ["A"], "Val": [1]})
        result, err = _apply_actions_to_df(df, [{"action": "groupby_agg", "group_by": ["Cat"], "agg_column": "ZZZ", "agg_func": "mean"}])
        assert err

    def test_invalid_agg_func(self):
        df = pd.DataFrame({"Cat": ["A", "B"], "Val": [1, 2]})
        result, err = _apply_actions_to_df(df, [{"action": "groupby_agg", "group_by": ["Cat"], "agg_column": "Val", "agg_func": "explode"}])
        assert err
        assert "não suportada" in err.lower()


# ── unknown action ───────────────────────────────────────────────────


class TestUnknownAction:
    def test_unknown_kind(self, sample_df):
        result, err = _apply_actions_to_df(sample_df, [{"action": "explode_everything"}])
        assert err
        assert "desconhecida" in err.lower()


# ── structured_actions_tool (integration) ────────────────────────────


class TestStructuredActionsTool:
    def test_sort_via_tool(self, sample_df, tmp_path):
        ws = _make_workspace(sample_df, path=str(tmp_path / "test.xlsx"))
        sample_df.to_excel(ws.path, index=False, engine="openpyxl")
        mgr = _make_checkpoint_mgr(tmp_path)
        result = structured_actions_tool(
            ws,
            json.dumps([{"action": "sort", "by": "Idade"}]),
            mgr,
            save_checkpoint=False,
        )
        assert result.success
        assert ws.df is not None
        assert list(ws.df["Idade"]) == [22, 25, 28, 30, 35]

    def test_invalid_json_via_tool(self, workspace, checkpoint_manager):
        result = structured_actions_tool(workspace, "bad{json", checkpoint_manager, save_checkpoint=False)
        assert not result.success

    def test_multiple_actions(self, sample_df, tmp_path):
        ws = _make_workspace(sample_df, path=str(tmp_path / "test.xlsx"))
        sample_df.to_excel(ws.path, index=False, engine="openpyxl")
        mgr = _make_checkpoint_mgr(tmp_path)
        actions = [
            {"action": "sort", "by": "Idade"},
            {"action": "rename_column", "from": "Nome", "to": "Pessoa"},
        ]
        result = structured_actions_tool(ws, json.dumps(actions), mgr, save_checkpoint=False)
        assert result.success
        assert "Pessoa" in ws.df.columns
