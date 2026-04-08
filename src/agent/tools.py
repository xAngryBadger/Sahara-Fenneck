# -*- coding: utf-8 -*-
"""
Tools do agente:
- GetData: resumo da planilha indexada
- Optimize: executa código validado e aplica em tempo real com checkpoint prévio
"""
from __future__ import annotations

import ast
import json
from typing import Optional, Callable

from ..indexing.excel_reader import Workspace, get_workspace_summary
from ..checkpoints.manager import CheckpointManager

ALLOWED_MODULES = {"pandas", "openpyxl", "math", "datetime"}
FORBIDDEN_NAMES = {
    "__import__",
    "eval",
    "exec",
    "open",
    "compile",
    "globals",
    "locals",
    "input",
    "os",
    "sys",
    "subprocess",
}
SAFE_BUILTINS = {
    "abs": abs,
    "all": all,
    "any": any,
    "bool": bool,
    "dict": dict,
    "enumerate": enumerate,
    "float": float,
    "int": int,
    "len": len,
    "list": list,
    "max": max,
    "min": min,
    "range": range,
    "round": round,
    "set": set,
    "sorted": sorted,
    "str": str,
    "sum": sum,
    "tuple": tuple,
    "zip": zip,
    "Exception": Exception,
    "ValueError": ValueError,
    "TypeError": TypeError,
}


def get_data_tool(workspace: Workspace) -> str:
    """Retorna resumo da planilha para o LLM."""
    return get_workspace_summary(workspace)


def _normalize_actions(actions_payload: str) -> tuple[list[dict], str]:
    """Aceita JSON em formato lista ou objeto {"actions": [...]}.
    Retorna (actions, erro)."""
    try:
        raw = json.loads(actions_payload)
    except Exception as e:
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

        else:
            return None, f"Ação #{idx} desconhecida: {kind}"

    return out, ""


def _validate_code(code: str) -> tuple[bool, str]:
    """Verifica sintaxe e imports permitidos."""
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return False, f"Erro de sintaxe: {e}"

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] not in ALLOWED_MODULES:
                    return False, f"Módulo não permitido: {alias.name}"
        if isinstance(node, ast.ImportFrom):
            if node.module and node.module.split(".")[0] not in ALLOWED_MODULES:
                return False, f"Módulo não permitido: {node.module}"
        if isinstance(node, ast.Name) and node.id in FORBIDDEN_NAMES:
            return False, f"Nome não permitido: {node.id}"
        if isinstance(node, ast.Attribute) and str(node.attr).startswith("__"):
            return False, "Acesso a atributos internos (__dunder__) não é permitido."
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in FORBIDDEN_NAMES:
            return False, f"Função não permitida: {node.func.id}"

    return True, ""


def _resolve_excel_wb(workspace: Workspace):
    """Resolve workbook COM aberto por path/nome (para alteração em tempo real)."""
    pythoncom = None
    try:
        import pythoncom  # type: ignore
        import win32com.client  # type: ignore

        pythoncom.CoInitialize()
        excel = win32com.client.GetActiveObject("Excel.Application")
        if excel is None or excel.Workbooks.Count == 0:
            return None, pythoncom

        for wb in excel.Workbooks:
            wb_name = str(getattr(wb, "Name", ""))
            wb_full = str(getattr(wb, "FullName", ""))
            if workspace.path and wb_full and wb_full.lower() == workspace.path.lower():
                return wb, pythoncom
            if workspace.excel_book_name and wb_name.lower() == workspace.excel_book_name.lower():
                return wb, pythoncom

        return None, pythoncom
    except Exception:
        return None, pythoncom


def _excel_scalar(value):
    """Converte valores pandas/numpy para tipos seguros para COM do Excel."""
    try:
        import pandas as pd  # type: ignore
        if pd.isna(value):
            return None
    except Exception:
        pass

    try:
        import numpy as np  # type: ignore
        if isinstance(value, np.generic):
            return value.item()
    except Exception:
        pass

    return value


def _df_to_excel_matrix(df):
    rows = [tuple(str(c) for c in df.columns)]
    for row in df.itertuples(index=False, name=None):
        rows.append(tuple(_excel_scalar(v) for v in row))
    return tuple(rows)


def optimize_tool(
    workspace: Workspace,
    code: str,
    checkpoint_manager: CheckpointManager,
    on_checkpoint_saved: Optional[Callable[[str], None]] = None,
    save_checkpoint: bool = True,
) -> str:
    """
    Valida código, salva checkpoint, executa e aplica alterações.
    """
    ok, err = _validate_code(code)
    if not ok:
        return err

    checkpoint_suffix = ""
    # 1) Checkpoint antes da alteração (uma vez por ordem, controlado pelo caller)
    if save_checkpoint:
        try:
            info = checkpoint_manager.save_checkpoint(workspace, label="Antes da ordem")
            if on_checkpoint_saved:
                on_checkpoint_saved(info.label)
            checkpoint_suffix = " Checkpoint salvo antes da ordem."
        except Exception as cp_err:
            return f"Erro ao salvar checkpoint: {cp_err!s}"

    # 2) Preparar ambiente local para execução
    import pandas as pd
    import openpyxl

    df = workspace.df
    if df is None:
        df = pd.DataFrame(columns=workspace.columns or [])

    wb_openpyxl = None
    if workspace.path and not workspace.excel_live:
        try:
            wb_openpyxl = openpyxl.load_workbook(workspace.path)
        except Exception:
            wb_openpyxl = None

    local = {
        "df": df,
        "pd": pd,
        "openpyxl": openpyxl,
        "wb": wb_openpyxl,
        "workspace": workspace,
    }

    # 3) Executar código do agente
    try:
        exec(code, {"__builtins__": SAFE_BUILTINS, "pd": pd, "openpyxl": openpyxl}, local)
    except Exception as e:
        return f"Erro ao executar código: {e!s}"

    new_df = local.get("df")
    new_wb = local.get("wb")

    # 4) Aplicar alterações
    if workspace.excel_live:
        wb, pycom = _resolve_excel_wb(workspace)
        try:
            if wb is None:
                return "Excel aberto não encontrado para atualização em tempo real."
            ws = wb.Worksheets(workspace.sheet_name) if workspace.sheet_name else wb.ActiveSheet

            if new_df is not None and not new_df.empty:
                ws.UsedRange.ClearContents()
                nrows, ncols = new_df.shape[0] + 1, new_df.shape[1]
                rows = _df_to_excel_matrix(new_df)
                ws.Range(ws.Cells(1, 1), ws.Cells(nrows, ncols)).Value = rows
            elif new_df is not None and new_df.empty:
                ws.UsedRange.ClearContents()
                if workspace.columns:
                    header = tuple(str(c) for c in workspace.columns)
                    ws.Range(ws.Cells(1, 1), ws.Cells(1, len(header))).Value = (header,)

            wb.Save()
        except Exception as e:
            return f"Erro ao escrever no Excel: {e!s}"
        finally:
            if pycom is not None:
                try:
                    pycom.CoUninitialize()
                except Exception:
                    pass
    else:
        if new_wb is not None and workspace.path:
            try:
                # Se alterou somente df, reflete df na aba ativa do workbook.
                if new_df is not None and not new_df.empty:
                    ws = new_wb[workspace.sheet_name] if workspace.sheet_name in new_wb.sheetnames else new_wb.active
                    ws.delete_rows(1, ws.max_row)
                    ws.append(list(new_df.columns))
                    for row in new_df.itertuples(index=False):
                        ws.append(list(row))
                new_wb.save(workspace.path)
            except Exception as e:
                return f"Erro ao salvar arquivo: {e!s}"
        elif new_df is not None and not new_df.empty and workspace.path:
            try:
                new_df.to_excel(workspace.path, index=False, engine="openpyxl")
            except Exception as e:
                return f"Erro ao salvar arquivo: {e!s}"

    # 5) Atualizar workspace em memória (sessão atual)
    if new_df is not None:
        workspace.df = new_df
        workspace.columns = list(new_df.columns)
        workspace.row_count = int(len(new_df))
        workspace.indexed_rows = int(len(new_df))
        workspace.truncated = False

    return f"Otimização aplicada com sucesso.{checkpoint_suffix}"


def structured_actions_tool(
    workspace: Workspace,
    actions_payload: str,
    checkpoint_manager: CheckpointManager,
    on_checkpoint_saved: Optional[Callable[[str], None]] = None,
    save_checkpoint: bool = True,
) -> str:
    """
    Executa ações estruturadas (JSON) sobre a planilha sem usar exec arbitrário.
    """
    actions, parse_err = _normalize_actions(actions_payload)
    if parse_err:
        return parse_err

    checkpoint_suffix = ""
    if save_checkpoint:
        try:
            info = checkpoint_manager.save_checkpoint(workspace, label="Antes da ordem")
            if on_checkpoint_saved:
                on_checkpoint_saved(info.label)
            checkpoint_suffix = " Checkpoint salvo antes da ordem."
        except Exception as cp_err:
            return f"Erro ao salvar checkpoint: {cp_err!s}"

    import pandas as pd
    import openpyxl

    df = workspace.df
    if df is None:
        df = pd.DataFrame(columns=workspace.columns or [])

    # Separate workbook-level actions (sheet ops) from df-level actions
    _WB_KINDS = {"duplicate_sheet", "create_sheet", "delete_sheet", "rename_sheet"}
    wb_actions = [a for a in actions if str(a.get("action", "")).strip().lower() in _WB_KINDS]
    df_actions = [a for a in actions if str(a.get("action", "")).strip().lower() not in _WB_KINDS]

    if df_actions:
        new_df, err = _apply_actions_to_df(df, df_actions)
        if err:
            return err
    else:
        new_df = df.copy() if df is not None else pd.DataFrame(columns=workspace.columns or [])

    # Persistência segue a mesma estratégia do optimize_tool.
    wb_openpyxl = None
    if workspace.path and not workspace.excel_live:
        try:
            wb_openpyxl = openpyxl.load_workbook(workspace.path)
        except Exception:
            wb_openpyxl = None

    new_wb = wb_openpyxl
    if workspace.excel_live:
        wb, pycom = _resolve_excel_wb(workspace)
        try:
            if wb is None:
                return "Excel aberto não encontrado para atualização em tempo real."
            ws = wb.Worksheets(workspace.sheet_name) if workspace.sheet_name else wb.ActiveSheet

            # Apply workbook-level actions (COM)
            for a in wb_actions:
                kind = str(a.get("action", "")).strip().lower()
                base = workspace.sheet_name or "Aba"
                new_name = str(a.get("name", f"{base} Cópia")).strip() or f"{base} Cópia"
                if kind == "duplicate_sheet":
                    src = wb.Worksheets(workspace.sheet_name) if workspace.sheet_name else wb.ActiveSheet
                    src.Copy(After=wb.Worksheets(wb.Worksheets.Count))
                    wb.Worksheets(wb.Worksheets.Count).Name = new_name
                elif kind == "create_sheet":
                    wb.Worksheets.Add(After=wb.Worksheets(wb.Worksheets.Count)).Name = new_name
                elif kind == "delete_sheet":
                    target_name = str(a.get("name", "")).strip()
                    if target_name and wb.Worksheets.Count > 1:
                        excel_app = wb.Application
                        old_alerts = excel_app.DisplayAlerts
                        excel_app.DisplayAlerts = False
                        try:
                            wb.Worksheets(target_name).Delete()
                        finally:
                            excel_app.DisplayAlerts = old_alerts
                elif kind == "rename_sheet":
                    old_name = str(a.get("from", "")).strip()
                    new_n = str(a.get("to", "")).strip()
                    if old_name and new_n:
                        wb.Worksheets(old_name).Name = new_n

            if df_actions and new_df is not None:
                ws.UsedRange.ClearContents()
                if not new_df.empty:
                    nrows, ncols = new_df.shape[0] + 1, new_df.shape[1]
                    rows = _df_to_excel_matrix(new_df)
                    ws.Range(ws.Cells(1, 1), ws.Cells(nrows, ncols)).Value = rows
                elif len(new_df.columns) > 0:
                    header = tuple(str(c) for c in new_df.columns)
                    ws.Range(ws.Cells(1, 1), ws.Cells(1, len(header))).Value = (header,)

            wb.Save()
        except Exception as e:
            return f"Erro ao escrever no Excel: {e!s}"
        finally:
            if pycom is not None:
                try:
                    pycom.CoUninitialize()
                except Exception:
                    pass
    else:
        if new_wb is not None and workspace.path:
            try:
                # Apply workbook-level actions (file)
                for a in wb_actions:
                    kind = str(a.get("action", "")).strip().lower()
                    base = workspace.sheet_name or "Aba"
                    new_name = str(a.get("name", f"{base} Cópia")).strip() or f"{base} Cópia"
                    if kind == "duplicate_sheet":
                        src_ws = new_wb[workspace.sheet_name] if workspace.sheet_name and workspace.sheet_name in new_wb.sheetnames else new_wb.active
                        copy_ws = new_wb.copy_worksheet(src_ws)
                        copy_ws.title = new_name
                    elif kind == "create_sheet":
                        new_wb.create_sheet(title=new_name)
                    elif kind == "delete_sheet":
                        target_name = str(a.get("name", "")).strip()
                        if target_name and target_name in new_wb.sheetnames and len(new_wb.sheetnames) > 1:
                            del new_wb[target_name]
                    elif kind == "rename_sheet":
                        old_name = str(a.get("from", "")).strip()
                        new_n = str(a.get("to", "")).strip()
                        if old_name and new_n and old_name in new_wb.sheetnames:
                            new_wb[old_name].title = new_n

                if df_actions and new_df is not None:
                    ws = new_wb[workspace.sheet_name] if workspace.sheet_name in new_wb.sheetnames else new_wb.active
                    ws.delete_rows(1, ws.max_row)
                    ws.append(list(new_df.columns))
                    for row in new_df.itertuples(index=False):
                        ws.append(list(row))
                new_wb.save(workspace.path)
            except Exception as e:
                return f"Erro ao salvar arquivo: {e!s}"
        elif df_actions and new_df is not None and workspace.path:
            try:
                new_df.to_excel(workspace.path, index=False, engine="openpyxl")
            except Exception as e:
                return f"Erro ao salvar arquivo: {e!s}"

    if df_actions and new_df is not None:
        workspace.df = new_df
        workspace.columns = list(new_df.columns)
        workspace.row_count = int(len(new_df))
        workspace.indexed_rows = int(len(new_df))
        workspace.truncated = False

    return f"Otimização estruturada aplicada com sucesso.{checkpoint_suffix}"
