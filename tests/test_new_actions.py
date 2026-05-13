"""Tests for new Excel actions: filter_contains, filter_range, pivot_table,
merge_columns, strip_whitespace, change_dtype."""
from __future__ import annotations

import pandas as pd
import pytest
from src.agent.tools import _apply_actions_to_df


@pytest.fixture
def df():
    return pd.DataFrame(
        {
            "Nome": ["  Ana Silva  ", " Bruno Costa ", "Carla Dias", " DANIEL Souza ", "Elena Ferreira"],
            "Idade": [28, 35, 42, 19, 31],
            "Salario": [8500.0, 12000.0, 9800.0, 4200.0, 15000.0],
            "Departamento": ["Vendas", "TI", "RH", "Vendas", "TI"],
            "CEP": [12345678, 23456789, 34567890, 45678901, 56789012],
        }
    )


class TestFilterContains:
    def test_case_insensitive(self, df):
        result, err = _apply_actions_to_df(df, [{"action": "filter_contains", "column": "Nome", "value": "silva"}])
        assert err == ""
        assert len(result) == 1
        assert "Ana" in result.iloc[0]["Nome"]

    def test_case_sensitive(self, df):
        result, err = _apply_actions_to_df(df, [{"action": "filter_contains", "column": "Nome", "value": "DANIEL", "case_sensitive": True}])
        assert err == ""
        assert len(result) == 1

    def test_case_sensitive_no_match(self, df):
        result, err = _apply_actions_to_df(df, [{"action": "filter_contains", "column": "Nome", "value": "daniel", "case_sensitive": True}])
        assert err == ""
        assert len(result) == 0

    def test_missing_column(self, df):
        _, err = _apply_actions_to_df(df, [{"action": "filter_contains", "column": "ZZZ", "value": "x"}])
        assert "não encontrada" in err

    def test_no_match(self, df):
        result, err = _apply_actions_to_df(df, [{"action": "filter_contains", "column": "Nome", "value": "zzznotfound"}])
        assert err == ""
        assert len(result) == 0


class TestFilterRange:
    def test_min_and_max(self, df):
        result, err = _apply_actions_to_df(df, [{"action": "filter_range", "column": "Salario", "min": 8000, "max": 12000}])
        assert err == ""
        assert len(result) == 3

    def test_min_only(self, df):
        result, err = _apply_actions_to_df(df, [{"action": "filter_range", "column": "Salario", "min": 10000}])
        assert err == ""
        assert all(result["Salario"] >= 10000)

    def test_max_only(self, df):
        result, err = _apply_actions_to_df(df, [{"action": "filter_range", "column": "Idade", "max": 30}])
        assert err == ""
        assert all(result["Idade"] <= 30)

    def test_missing_column(self, df):
        _, err = _apply_actions_to_df(df, [{"action": "filter_range", "column": "ZZZ", "min": 0}])
        assert "não encontrada" in err

    def test_no_match(self, df):
        result, err = _apply_actions_to_df(df, [{"action": "filter_range", "column": "Salario", "min": 999999}])
        assert err == ""
        assert len(result) == 0


class TestPivotTable:
    def test_basic_pivot(self, df):
        result, err = _apply_actions_to_df(df, [{"action": "pivot_table", "index": ["Departamento"], "values": "Salario", "agg_func": "mean"}])
        assert err == ""
        assert "Departamento" in result.columns
        assert len(result) == 3

    def test_sum_agg(self, df):
        result, err = _apply_actions_to_df(df, [{"action": "pivot_table", "index": ["Departamento"], "values": "Salario", "agg_func": "sum"}])
        assert err == ""
        ti_sum = result[result["Departamento"] == "TI"]["Salario"].iloc[0]
        assert ti_sum == pytest.approx(27000.0)

    def test_missing_index(self, df):
        _, err = _apply_actions_to_df(df, [{"action": "pivot_table", "index": [], "values": "Salario", "agg_func": "sum"}])
        assert "inválido" in err

    def test_missing_value_column(self, df):
        _, err = _apply_actions_to_df(df, [{"action": "pivot_table", "index": ["Departamento"], "values": "ZZZ", "agg_func": "sum"}])
        assert "não encontrada" in err


class TestMergeColumns:
    def test_basic_merge(self, df):
        result, err = _apply_actions_to_df(df, [{"action": "merge_columns", "columns": ["Nome", "Departamento"], "new_column": "Display", "separator": " - "}])
        assert err == ""
        assert "Display" in result.columns
        assert " - " in result.iloc[0]["Display"]

    def test_custom_separator(self, df):
        result, err = _apply_actions_to_df(df, [{"action": "merge_columns", "columns": ["Nome", "Departamento"], "new_column": "Combo", "separator": ", "}])
        assert err == ""
        assert ", " in result.iloc[0]["Combo"]

    def test_missing_column(self, df):
        _, err = _apply_actions_to_df(df, [{"action": "merge_columns", "columns": ["Nome", "ZZZ"], "new_column": "X"}])
        assert "não encontrada" in err

    def test_no_new_column_name(self, df):
        _, err = _apply_actions_to_df(df, [{"action": "merge_columns", "columns": ["Nome"], "new_column": ""}])
        assert "obrigatório" in err

    def test_empty_columns_list(self, df):
        _, err = _apply_actions_to_df(df, [{"action": "merge_columns", "columns": [], "new_column": "X"}])
        assert "inválido" in err


class TestStripWhitespace:
    def test_specific_columns(self, df):
        result, err = _apply_actions_to_df(df, [{"action": "strip_whitespace", "columns": ["Nome"]}])
        assert err == ""
        assert result.iloc[0]["Nome"] == "Ana Silva"
        assert result.iloc[1]["Nome"] == "Bruno Costa"

    def test_all_string_columns(self, df):
        result, err = _apply_actions_to_df(df, [{"action": "strip_whitespace"}])
        assert err == ""
        assert result.iloc[0]["Nome"] == "Ana Silva"
        assert result.iloc[3]["Nome"] == "DANIEL Souza"

    def test_missing_column(self, df):
        _, err = _apply_actions_to_df(df, [{"action": "strip_whitespace", "columns": ["ZZZ"]}])
        assert "não encontrada" in err

    def test_empty_columns_list(self, df):
        _, err = _apply_actions_to_df(df, [{"action": "strip_whitespace", "columns": []}])
        assert "inválido" in err


class TestChangeDtype:
    def test_to_str(self, df):
        result, err = _apply_actions_to_df(df, [{"action": "change_dtype", "column": "CEP", "dtype": "str"}])
        assert err == ""
        assert pd.api.types.is_string_dtype(result["CEP"])
        assert result.iloc[0]["CEP"] == "12345678"

    def test_to_float(self, df):
        result, err = _apply_actions_to_df(df, [{"action": "change_dtype", "column": "Idade", "dtype": "float"}])
        assert err == ""
        assert str(result["Idade"].dtype).startswith("float")

    def test_to_int(self, df):
        df2 = df.copy()
        df2["Idade"] = df2["Idade"].astype(float)
        result, err = _apply_actions_to_df(df2, [{"action": "change_dtype", "column": "Idade", "dtype": "int"}])
        assert err == ""
        assert str(result["Idade"].dtype) == "Int64"

    def test_to_datetime(self):
        df2 = pd.DataFrame({"Data": ["2024-01-15", "2024-06-30"]})
        result, err = _apply_actions_to_df(df2, [{"action": "change_dtype", "column": "Data", "dtype": "datetime"}])
        assert err == ""
        assert pd.api.types.is_datetime64_any_dtype(result["Data"])

    def test_invalid_dtype(self, df):
        _, err = _apply_actions_to_df(df, [{"action": "change_dtype", "column": "Idade", "dtype": "bytes"}])
        assert "não suportado" in err

    def test_missing_column(self, df):
        _, err = _apply_actions_to_df(df, [{"action": "change_dtype", "column": "ZZZ", "dtype": "str"}])
        assert "não encontrada" in err
