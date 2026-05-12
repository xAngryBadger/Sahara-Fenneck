"""
Leitura de planilhas (Excel aberto via COM e arquivos .xlsx/.xlsm/.xls/.ods).
Suporta indexação de múltiplas planilhas/abas e limites por aba para desempenho.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from ..errcodes import ErrCode, err_str

log = logging.getLogger(__name__)

try:
    import pandas as pd
except ImportError:  # pragma: no cover
    pd = None

EXCEL_EXTENSIONS = {".xlsx", ".xlsm", ".xls", ".ods"}
DEFAULT_MAX_ROWS = 5000


def _normalize_limit(max_rows: int) -> int | None:
    """Normaliza limite de linhas: <=0 significa sem limite."""
    try:
        value = int(max_rows)
    except Exception:
        log.warning("Falha ao normalizar limite de linhas, usando valor padrão: %s", max_rows)
        value = DEFAULT_MAX_ROWS
    if value <= 0:
        return None
    return max(1, value)


@dataclass
class Workspace:
    """Representa uma aba indexada para uso do agente."""

    path: str
    workbook_name: str
    sheet_name: str
    columns: list[str]
    row_count: int  # total de linhas de dados na aba
    indexed_rows: int  # linhas efetivamente carregadas para o contexto
    truncated: bool = False
    df: pd.DataFrame | None = None
    excel_live: bool = False  # True quando veio de Excel aberto (COM)
    excel_book_name: str | None = None
    error: str | None = None

    def summary_one_line(self) -> str:
        if self.error:
            return self.error
        extra = " (amostra)" if self.truncated else ""
        name = self.workbook_name or Path(self.path).name
        return (
            f"{name} | aba: {self.sheet_name} | {len(self.columns)} colunas | "
            f"{self.indexed_rows}/{self.row_count} linhas{extra}"
        )


def is_excel_file(path: str) -> bool:
    return Path(path).suffix.lower() in EXCEL_EXTENSIONS


def _safe_headers(raw_headers: list[object], col_count: int) -> list[str]:
    headers = []
    for i in range(col_count):
        v = raw_headers[i] if i < len(raw_headers) else None
        text = str(v).strip() if v is not None else ""
        headers.append(text if text else f"Col{i + 1}")
    return headers


def _rows_to_df(headers: list[str], rows: list[list[object]]) -> pd.DataFrame | None:
    if pd is None:
        return None
    if not rows:
        return pd.DataFrame(columns=headers)
    return pd.DataFrame(rows, columns=headers)


def index_from_path(file_path: str, sheet_name: str | None = None, max_rows: int = DEFAULT_MAX_ROWS) -> Workspace:
    """Indexa uma aba única de arquivo Excel (por padrão aba ativa/primeira)."""
    need_all = sheet_name is not None
    all_items = index_file_multi(file_path, include_all_sheets=need_all, max_rows=max_rows)
    if not all_items:
        return Workspace(
            path=str(Path(file_path).resolve()),
            workbook_name=Path(file_path).name,
            sheet_name="",
            columns=[],
            row_count=0,
            indexed_rows=0,
            error=err_str(ErrCode.INDEX_FAILED),
        )
    if sheet_name:
        for item in all_items:
            if item.sheet_name == sheet_name:
                return item
    return all_items[0]


def _engine_for_suffix(suffix: str) -> str | None:
    """Return the pandas ExcelFile engine name for a given file suffix, or None."""
    suffix = suffix.lower()
    if suffix in (".xlsx", ".xlsm"):
        return "openpyxl"
    if suffix == ".xls":
        return "xlrd"
    if suffix == ".ods":
        return "odf"
    return None


def index_file_multi(file_path: str, include_all_sheets: bool = False, max_rows: int = DEFAULT_MAX_ROWS) -> list[Workspace]:
    """Indexa um arquivo e retorna uma Workspace por aba."""
    p = Path(file_path).resolve()
    if not p.exists():
        return [
            Workspace(
                path=str(p),
                workbook_name=p.name,
                sheet_name="",
                columns=[],
                row_count=0,
                indexed_rows=0,
                error=err_str(ErrCode.FILE_NOT_FOUND),
            )
        ]
    if not is_excel_file(str(p)):
        return [
            Workspace(
                path=str(p),
                workbook_name=p.name,
                sheet_name="",
                columns=[],
                row_count=0,
                indexed_rows=0,
                error=err_str(ErrCode.FILE_INVALID_FORMAT),
            )
        ]

    engine = _engine_for_suffix(p.suffix)
    if engine is None:
        return [
            Workspace(
                path=str(p),
                workbook_name=p.name,
                sheet_name="",
                columns=[],
                row_count=0,
                indexed_rows=0,
                error=err_str(ErrCode.FILE_INVALID_FORMAT),
            )
        ]

    try:
        xl = pd.ExcelFile(str(p), engine=engine)
    except Exception as e:
        log.exception("Erro ao abrir arquivo com pandas ExcelFile (engine=%s): %s", engine, e)
        return [
            Workspace(
                path=str(p),
                workbook_name=p.name,
                sheet_name="",
                columns=[],
                row_count=0,
                indexed_rows=0,
                error=err_str(ErrCode.INDEX_FAILED, f"Arquivo: {e!s}"),
            )
        ]

    all_names: list[str] = list(xl.sheet_names)
    selected_names = all_names if include_all_sheets else [all_names[0]] if all_names else []
    workspaces: list[Workspace] = []
    limit = _normalize_limit(max_rows)

    for name in selected_names:
        try:
            df = pd.read_excel(xl, sheet_name=name)
        except Exception as sheet_err:
            log.warning("Erro ao ler aba '%s': %s", name, sheet_err)
            workspaces.append(
                Workspace(
                    path=str(p),
                    workbook_name=p.name,
                    sheet_name=name,
                    columns=[],
                    row_count=0,
                    indexed_rows=0,
                    error=err_str(ErrCode.SHEET_EMPTY),
                )
            )
            continue

        if df.empty and df.columns.empty:
            workspaces.append(
                Workspace(
                    path=str(p),
                    workbook_name=p.name,
                    sheet_name=name,
                    columns=[],
                    row_count=0,
                    indexed_rows=0,
                    error=err_str(ErrCode.SHEET_EMPTY),
                )
            )
            continue

        headers = [str(c).strip() or f"Col{i + 1}" for i, c in enumerate(df.columns)]
        total_rows = len(df)
        take_rows = total_rows if limit is None else min(total_rows, limit)

        if take_rows < total_rows:
            sampled = df.head(take_rows)
        else:
            sampled = df

        sampled.columns = headers
        workspaces.append(
            Workspace(
                path=str(p),
                workbook_name=p.name,
                sheet_name=name,
                columns=headers,
                row_count=total_rows,
                indexed_rows=len(sampled),
                truncated=total_rows > len(sampled),
                df=sampled,
                excel_live=False,
                excel_book_name=None,
                error=None,
            )
        )

    xl.close()
    return workspaces


def index_from_excel(include_all_sheets: bool = False, max_rows: int = DEFAULT_MAX_ROWS) -> Workspace:
    """Indexa uma única aba do Excel aberto (por padrão, aba ativa do workbook ativo)."""
    items = index_open_excel_workbooks(include_all_sheets=include_all_sheets, max_rows=max_rows)
    if not items:
        return Workspace(
            path="",
            workbook_name="",
            sheet_name="",
            columns=[],
            row_count=0,
            indexed_rows=0,
            error=err_str(ErrCode.EXCEL_NOT_FOUND),
        )
    return items[0]


def index_open_excel_workbooks(include_all_sheets: bool = False, max_rows: int = DEFAULT_MAX_ROWS) -> list[Workspace]:
    """
    Indexa workbooks abertos no Excel Desktop via COM.
    Se include_all_sheets=False, indexa apenas a aba ativa de cada workbook.
    """
    workspaces: list[Workspace] = []
    limit = _normalize_limit(max_rows)

    try:
        from ..com_utils import COMContext

        with COMContext() as ctx:
            if not ctx.has_workbooks:
                return [
                    Workspace(
                        path="",
                        workbook_name="",
                        sheet_name="",
                        columns=[],
                        row_count=0,
                        indexed_rows=0,
                        error=err_str(ErrCode.EXCEL_NOT_FOUND),
                    )
                ]

            excel = ctx.excel_app
            for wb in excel.Workbooks:
                try:
                    wb_name = str(wb.Name)
                    wb_path = str(wb.FullName) if getattr(wb, "FullName", None) else wb_name
                    sheet_names = [str(s.Name) for s in wb.Worksheets] if include_all_sheets else [str(wb.ActiveSheet.Name)]

                    for sname in sheet_names:
                        ws = wb.Worksheets(sname)
                        used = ws.UsedRange
                        rows_count = int(getattr(used.Rows, "Count", 0) or 0)
                        cols_count = int(getattr(used.Columns, "Count", 0) or 0)

                        if rows_count <= 0 or cols_count <= 0:
                            workspaces.append(
                                Workspace(
                                    path=wb_path,
                                    workbook_name=wb_name,
                                    sheet_name=sname,
                                    columns=[],
                                    row_count=0,
                                    indexed_rows=0,
                                    excel_live=True,
                                    excel_book_name=wb_name,
                                    error=err_str(ErrCode.SHEET_EMPTY),
                                )
                            )
                            continue

                        raw_headers = [ws.Cells(1, c).Value for c in range(1, cols_count + 1)]
                        headers = _safe_headers(raw_headers, cols_count)

                        total_rows = max(0, rows_count - 1)
                        take_rows = total_rows if limit is None else min(total_rows, limit)
                        data_rows: list[list[object]] = []

                        for r in range(2, take_rows + 2):
                            data_rows.append([ws.Cells(r, c).Value for c in range(1, cols_count + 1)])

                        workspaces.append(
                            Workspace(
                                path=wb_path,
                                workbook_name=wb_name,
                                sheet_name=sname,
                                columns=headers,
                                row_count=total_rows,
                                indexed_rows=len(data_rows),
                                truncated=total_rows > len(data_rows),
                                df=_rows_to_df(headers, data_rows),
                                excel_live=True,
                                excel_book_name=wb_name,
                                error=None,
                            )
                        )

                except Exception as wb_err:
                    log.warning("Erro ao processar workbook via COM: %s", wb_err)
                    workspaces.append(
                        Workspace(
                            path="",
                            workbook_name=getattr(wb, "Name", ""),
                            sheet_name="",
                            columns=[],
                            row_count=0,
                            indexed_rows=0,
                            excel_live=True,
                            excel_book_name=getattr(wb, "Name", ""),
                            error=err_str(ErrCode.INDEX_FAILED, f"Workbook com erro: {wb_err!s}"),
                        )
                    )

            if not workspaces:
                workspaces.append(
                    Workspace(
                        path="",
                        workbook_name="",
                        sheet_name="",
                        columns=[],
                        row_count=0,
                        indexed_rows=0,
                        error=err_str(ErrCode.INDEX_FAILED, "Nenhuma aba indexada do Excel."),
                    )
                )

            return workspaces

    except Exception as e:
        log.exception("Erro ao indexar workbooks abertos no Excel: %s", e)
        return [
            Workspace(
                path="",
                workbook_name="",
                sheet_name="",
                columns=[],
                row_count=0,
                indexed_rows=0,
                error=err_str(ErrCode.INDEX_FAILED, f"Excel: {e!s}"),
            )
        ]


def get_workspace_summary(ws: Workspace) -> str:
    """Texto resumido da workspace para o LLM (GetData)."""
    if ws.error:
        return ws.error

    lines = [
        f"Arquivo: {ws.workbook_name}",
        f"Aba: {ws.sheet_name}",
        f"Colunas ({len(ws.columns)}): {', '.join(ws.columns[:20])}{'...' if len(ws.columns) > 20 else ''}",
        f"Linhas totais: {ws.row_count}",
        f"Linhas indexadas: {ws.indexed_rows}{' (amostra)' if ws.truncated else ''}",
    ]
    if ws.df is not None and not ws.df.empty:
        lines.append("Amostra (5 primeiras linhas):")
        lines.append(ws.df.head().to_string())
    return "\n".join(lines)


def hydrate_workspace_full(ws: Workspace) -> Workspace:
    """
    Garante que a workspace contenha todas as linhas da aba.
    Se já estiver completa, retorna sem alterações.
    """
    if ws.error:
        return ws
    if not ws.truncated:
        return ws

    if ws.excel_live:
        refreshed = index_open_excel_workbooks(include_all_sheets=True, max_rows=0)
        for item in refreshed:
            if item.error:
                continue
            if (item.workbook_name == ws.workbook_name) and (item.sheet_name == ws.sheet_name):
                return item
        return ws

    refreshed_ws = index_from_path(ws.path, sheet_name=ws.sheet_name, max_rows=0)
    if not refreshed_ws.error:
        return refreshed_ws
    return ws
