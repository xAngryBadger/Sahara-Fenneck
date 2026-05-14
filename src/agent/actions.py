"""Ações estruturadas declarativas (sort, fillna, replace, etc.) — sem exec()."""
from __future__ import annotations

import json
import logging

from .result import ErrCode

log = logging.getLogger(__name__)

_QUERY_KINDS = {"groupby_agg", "pivot_table"}

_WB_KINDS = {"duplicate_sheet", "create_sheet", "delete_sheet", "rename_sheet"}

_DF_KINDS = {
    "sort", "fillna", "replace", "rename_column", "drop_columns",
    "add_computed_column", "filter_equals", "filter_contains", "filter_range",
    "dropna", "groupby_agg", "pivot_table", "merge_columns", "strip_whitespace",
    "change_dtype", "adjust_header", "request_more_rows",
}

KNOWN_ACTION_KINDS = _DF_KINDS | _WB_KINDS


def _normalize_actions(actions_payload: str) -> tuple[list[dict], str]:
    """Aceita JSON em formato lista ou objeto {"actions": [...]}.
    Retorna (actions, erro)."""
    try:
        raw = json.loads(actions_payload)
    except (ValueError, json.JSONDecodeError) as e:
        log.warning("JSON inválido em [ACTIONS]: %s", e)
        return [], f"JSON inválido em [ACTIONS]: {e!s}"

    if isinstance(raw, dict):
        actions = raw.get("actions", [])
    else:
        actions = raw

    if not isinstance(actions, list) or not actions:
        return [], "[ACTIONS] precisa conter uma lista não vazia de ações."

    for i, a in enumerate(actions, 1):
        if not isinstance(a, dict):
            return [], f"Ação #{i} inválida: precisa ser objeto JSON."
        if not str(a.get("action", "")).strip():
            return [], f"Ação #{i} sem campo 'action'."
    return actions, ""


def _require_column(df, col: str) -> tuple[bool, str]:
    if col not in df.columns:
        return False, f"Coluna não encontrada: {col}"
    return True, ""


def _apply_actions_to_df(df, actions: list[dict]):
    """Aplica ações estruturadas (sem exec) sobre um DataFrame."""
    import pandas as pd

    out = df.copy()
    for idx, a in enumerate(actions, 1):
        kind = str(a.get("action", "")).strip().lower()

        if kind == "sort":
            by = a.get("by")
            if isinstance(by, str):
                by = [by]
            if not isinstance(by, list) or not by:
                return None, f"Ação #{idx} sort: campo 'by' inválido."
            for c in by:
                ok, err = _require_column(out, str(c))
                if not ok:
                    return None, f"Ação #{idx} sort: {err}"

            asc = a.get("ascending", True)
            na_pos = str(a.get("na_position", "last")).lower()
            if na_pos not in {"first", "last"}:
                na_pos = "last"
            out = out.sort_values(by=by, ascending=asc, na_position=na_pos, kind="mergesort").reset_index(drop=True)

        elif kind == "fillna":
            col = str(a.get("column", "")).strip()
            ok, err = _require_column(out, col)
            if not ok:
                return None, f"Ação #{idx} fillna: {err}"
            out[col] = out[col].fillna(a.get("value"))

        elif kind == "replace":
            col = str(a.get("column", "")).strip()
            ok, err = _require_column(out, col)
            if not ok:
                return None, f"Ação #{idx} replace: {err}"
            out[col] = out[col].replace(a.get("from"), a.get("to"))

        elif kind == "rename_column":
            old = str(a.get("from", "")).strip()
            new = str(a.get("to", "")).strip()
            if not old or not new:
                return None, f"Ação #{idx} rename_column: campos 'from' e 'to' são obrigatórios."
            ok, err = _require_column(out, old)
            if not ok:
                return None, f"Ação #{idx} rename_column: {err}"
            out = out.rename(columns={old: new})

        elif kind == "drop_columns":
            cols = a.get("columns")
            if isinstance(cols, str):
                cols = [cols]
            if not isinstance(cols, list) or not cols:
                return None, f"Ação #{idx} drop_columns: campo 'columns' inválido."
            missing = [c for c in cols if c not in out.columns]
            if missing:
                return None, f"Ação #{idx} drop_columns: colunas ausentes: {', '.join(map(str, missing))}"
            out = out.drop(columns=cols)

        elif kind == "add_computed_column":
            new_col = str(a.get("new_column", "")).strip()
            op = str(a.get("operation", "")).strip().lower()
            src = a.get("source_columns") or []
            if isinstance(src, str):
                src = [src]
            if not new_col or not isinstance(src, list) or not src:
                return None, f"Ação #{idx} add_computed_column: parâmetros inválidos."
            for c in src:
                ok, err = _require_column(out, str(c))
                if not ok:
                    return None, f"Ação #{idx} add_computed_column: {err}"

            if op == "concat":
                sep = str(a.get("separator", ""))
                out[new_col] = out[src].astype(str).agg(sep.join, axis=1)
            elif op in {"sum", "add"}:
                out[new_col] = out[src].apply(pd.to_numeric, errors="coerce").sum(axis=1)
            elif op == "multiply":
                out[new_col] = out[src].apply(pd.to_numeric, errors="coerce").prod(axis=1)
            elif op == "subtract":
                if len(src) != 2:
                    return None, f"Ação #{idx} add_computed_column/subtract: requer 2 colunas."
                nums = out[src].apply(pd.to_numeric, errors="coerce")
                out[new_col] = nums[src[0]] - nums[src[1]]
            elif op == "divide":
                if len(src) != 2:
                    return None, f"Ação #{idx} add_computed_column/divide: requer 2 colunas."
                nums = out[src].apply(pd.to_numeric, errors="coerce")
                denom = nums[src[1]].replace(0, pd.NA)
                out[new_col] = nums[src[0]] / denom
            else:
                return None, f"Ação #{idx} add_computed_column: operação não suportada: {op}"

        elif kind == "filter_equals":
            col = str(a.get("column", "")).strip()
            ok, err = _require_column(out, col)
            if not ok:
                return None, f"Ação #{idx} filter_equals: {err}"
            out = out[out[col] == a.get("value")].reset_index(drop=True)

        elif kind == "dropna":
            cols = a.get("columns")
            if cols is None:
                out = out.dropna(how=a.get("how", "any"))
            else:
                if isinstance(cols, str):
                    cols = [cols]
                if not isinstance(cols, list) or not cols:
                    return None, f"Ação #{idx} dropna: campo 'columns' inválido."
                missing = [c for c in cols if c not in out.columns]
                if missing:
                    return None, f"Ação #{idx} dropna: colunas ausentes: {', '.join(map(str, missing))}"
                how = str(a.get("how", "any")).lower()
                if how not in {"any", "all"}:
                    how = "any"
                out = out.dropna(subset=cols, how=how).reset_index(drop=True)

        elif kind == "groupby_agg":
            group_by = a.get("group_by")
            if isinstance(group_by, str):
                group_by = [group_by]
            if not isinstance(group_by, list) or not group_by:
                return None, f"Ação #{idx} groupby_agg: campo 'group_by' inválido."
            for c in group_by:
                ok, err = _require_column(out, str(c))
                if not ok:
                    return None, f"Ação #{idx} groupby_agg: {err}"
            agg_col = str(a.get("agg_column", "")).strip()
            ok, err = _require_column(out, agg_col)
            if not ok:
                return None, f"Ação #{idx} groupby_agg: {err}"
            agg_func = str(a.get("agg_func", "mean")).strip().lower()
            valid_funcs = {"mean", "sum", "min", "max", "count", "median", "std", "var", "first", "last"}
            if agg_func not in valid_funcs:
                return None, f"Ação #{idx} groupby_agg: função de agregação não suportada: {agg_func}. Use: {', '.join(sorted(valid_funcs))}"
            grouped = out.groupby(group_by, sort=False)[agg_col].agg(agg_func).reset_index()
            grouped.columns = list(group_by) + [agg_col]
            out = grouped

        elif kind == "filter_contains":
            col = str(a.get("column", "")).strip()
            ok, err = _require_column(out, col)
            if not ok:
                return None, f"Ação #{idx} filter_contains: {err}"
            value = str(a.get("value", ""))
            case = a.get("case_sensitive", False)
            if case:
                mask = out[col].astype(str).str.contains(value, regex=False, na=False)
            else:
                mask = out[col].astype(str).str.contains(value, regex=False, na=False, case=False)
            out = out[mask].reset_index(drop=True)

        elif kind == "filter_range":
            col = str(a.get("column", "")).strip()
            ok, err = _require_column(out, col)
            if not ok:
                return None, f"Ação #{idx} filter_range: {err}"
            nums = pd.to_numeric(out[col], errors="coerce")
            lo = a.get("min")
            hi = a.get("max")
            if lo is not None:
                nums = nums.where(nums >= float(lo))
            if hi is not None:
                nums = nums.where(nums <= float(hi))
            out = out[nums.notna()].reset_index(drop=True)

        elif kind == "pivot_table":
            index_cols = a.get("index")
            if isinstance(index_cols, str):
                index_cols = [index_cols]
            if not isinstance(index_cols, list) or not index_cols:
                return None, f"Ação #{idx} pivot_table: campo 'index' inválido (lista de colunas para agrupar)."
            for c in index_cols:
                ok, err = _require_column(out, str(c))
                if not ok:
                    return None, f"Ação #{idx} pivot_table: {err}"
            values_col = str(a.get("values", "")).strip()
            if values_col:
                ok, err = _require_column(out, values_col)
                if not ok:
                    return None, f"Ação #{idx} pivot_table: {err}"
            columns_col = a.get("columns")
            if isinstance(columns_col, str):
                columns_col = [columns_col]
            if columns_col:
                for c in columns_col:
                    if isinstance(c, str):
                        ok, err = _require_column(out, c)
                        if not ok:
                            return None, f"Ação #{idx} pivot_table: {err}"
            agg_func = str(a.get("agg_func", "sum")).strip().lower()
            valid_pv_funcs = {"mean", "sum", "min", "max", "count", "median", "std", "var", "first", "last"}
            if agg_func not in valid_pv_funcs:
                return None, f"Ação #{idx} pivot_table: agg_func não suportada: {agg_func}. Use: {', '.join(sorted(valid_pv_funcs))}"
            pv_kwargs: dict = {"index": index_cols, "aggfunc": agg_func}
            if values_col:
                pv_kwargs["values"] = values_col
            if columns_col:
                pv_kwargs["columns"] = columns_col
            try:
                pv = out.pivot_table(**pv_kwargs).reset_index()
            except (ValueError, TypeError, KeyError) as e:
                return None, f"Ação #{idx} pivot_table: erro ao gerar pivot: {e!s}"
            out = pv

        elif kind == "merge_columns":
            cols = a.get("columns")
            if isinstance(cols, str):
                cols = [cols]
            if not isinstance(cols, list) or not cols:
                return None, f"Ação #{idx} merge_columns: campo 'columns' inválido."
            for c in cols:
                ok, err = _require_column(out, str(c))
                if not ok:
                    return None, f"Ação #{idx} merge_columns: {err}"
            new_col = str(a.get("new_column", "")).strip()
            if not new_col:
                return None, f"Ação #{idx} merge_columns: campo 'new_column' é obrigatório."
            sep = str(a.get("separator", " "))
            out[new_col] = out[cols].astype(str).agg(sep.join, axis=1)

        elif kind == "strip_whitespace":
            cols = a.get("columns")
            if cols is None:
                str_cols = [c for c in out.columns if pd.api.types.is_string_dtype(out[c])]
            else:
                if isinstance(cols, str):
                    cols = [cols]
                if not isinstance(cols, list) or not cols:
                    return None, f"Ação #{idx} strip_whitespace: campo 'columns' inválido."
                str_cols = [str(c) for c in cols]
                for c in str_cols:
                    ok, err = _require_column(out, c)
                    if not ok:
                        return None, f"Ação #{idx} strip_whitespace: {err}"
            for c in str_cols:
                if c in out.columns and pd.api.types.is_string_dtype(out[c]):
                    out[c] = out[c].astype(str).str.strip()

        elif kind == "change_dtype":
            col = str(a.get("column", "")).strip()
            ok, err = _require_column(out, col)
            if not ok:
                return None, f"Ação #{idx} change_dtype: {err}"
            dtype = str(a.get("dtype", "")).strip().lower()
            valid_dtypes = {"int", "float", "str", "bool", "datetime"}
            if dtype not in valid_dtypes:
                return None, f"Ação #{idx} change_dtype: tipo não suportado: {dtype}. Use: {', '.join(sorted(valid_dtypes))}"
            try:
                if dtype == "int":
                    out[col] = pd.to_numeric(out[col], errors="coerce").astype("Int64")
                elif dtype == "float":
                    out[col] = pd.to_numeric(out[col], errors="coerce").astype(float)
                elif dtype == "str":
                    out[col] = out[col].astype(str)
                elif dtype == "bool":
                    out[col] = out[col].astype(bool)
                elif dtype == "datetime":
                    out[col] = pd.to_datetime(out[col], errors="coerce")
            except (ValueError, TypeError) as e:
                return None, f"Ação #{idx} change_dtype: erro ao converter coluna '{col}' para {dtype}: {e!s}"

        elif kind == "adjust_header":
            from ..indexing.excel_reader import _detect_header_offset

            offset = _detect_header_offset(out)
            if offset <= 0:
                return None, f"Ação #{idx} adjust_header: não foi possível detectar um cabeçalho alternativo."
            return out, f"__ADJUST_HEADER__{offset}"

        elif kind == "request_more_rows":
            return out, "__REQUEST_MORE_ROWS__"

        else:
            return None, f"Ação #{idx} desconhecida: {kind}"

    return out, ""


def _classify_err(msg: str) -> ErrCode:
    if "Coluna" in msg and ("não encontrada" in msg or "ausente" in msg):
        return ErrCode.COLUMN_MISSING
    if "desconhecida" in msg:
        return ErrCode.ACTION_UNKNOWN
    return ErrCode.ACTION_INVALID
