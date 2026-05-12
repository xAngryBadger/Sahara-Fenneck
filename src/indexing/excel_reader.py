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


def _is_nontabular(ws: Workspace) -> bool:
    """Detecta abas com layout não-tabular (células mescladas, formatação livre).

    Heurística: >50% das colunas são "Unnamed" ou "ColN" (auto-geradas) E poucas linhas.
    """
    if ws.df is None or ws.df.empty:
        return False
    auto_names = 0
    for col in ws.columns:
        c = str(col)
        if c.startswith("Unnamed") or c.startswith("Col") and c[3:].isdigit():
            auto_names += 1
    if len(ws.columns) == 0:
        return False
    ratio = auto_names / len(ws.columns)
    return ratio > 0.5 and ws.row_count < 50


def _fmt_number(value: object) -> str:
    """Formata número para resumo: 2 casas decimais se float, int se inteiro."""
    try:
        f = float(str(value))
        if f != f:
            return "NaN"
        if f == int(f) and abs(f) < 1e15:
            return str(int(f))
        return f"{f:.2f}"
    except Exception:
        return str(value)


def _build_column_stats(ws: Workspace) -> list[str]:
    """Estatísticas por coluna para o contexto do LLM."""
    if ws.df is None or ws.df.empty:
        return []
    import pandas as pd

    lines: list[str] = []
    for col in ws.columns:
        series = ws.df[col]
        nulls = int(series.isna().sum())
        dtype_str = str(series.dtype)

        if pd.api.types.is_numeric_dtype(series):
            non_na = series.dropna()
            if len(non_na) == 0:
                lines.append(f"  {col} ({dtype_str}): {nulls} nulos (100%)")
                continue
            parts = [f"{col} ({dtype_str}):"]
            parts.append(f"min={_fmt_number(non_na.min())}")
            parts.append(f"max={_fmt_number(non_na.max())}")
            if len(non_na) > 1:
                parts.append(f"mean={_fmt_number(non_na.mean())}")
            parts.append(f"{nulls} nulos" if nulls else "0 nulos")
            lines.append("  " + ", ".join(parts))
        else:
            unique_count = series.nunique(dropna=True)
            parts = [f"{col} ({dtype_str}):"]
            parts.append(f"{unique_count} únicos")
            if nulls:
                parts.append(f"{nulls} nulos")
            else:
                parts.append("0 nulos")
            if unique_count <= 15 and unique_count > 0:
                top = series.value_counts(dropna=True).head(5)
                top_str = ", ".join(f"{v} ({c}x)" for v, c in top.items())
                parts.append(f"mais comuns: {top_str}")
            lines.append("  " + ", ".join(parts))
    return lines


def _build_sample_block(ws: Workspace, head_n: int = 5, tail_n: int = 5) -> str:
    """Bloco de amostra head+tail para o contexto do LLM."""
    if ws.df is None or ws.df.empty:
        return ""

    parts: list[str] = []
    if len(ws.df) <= head_n + tail_n:
        parts.append(ws.df.to_string())
    else:
        head = ws.df.head(head_n)
        parts.append(f"Primeiras {head_n} linhas:")
        parts.append(head.to_string())
        tail = ws.df.tail(tail_n)
        parts.append(f"Últimas {tail_n} linhas:")
        parts.append(tail.to_string())
    return "\n".join(parts)


def _build_categorical_values(ws: Workspace, max_unique: int = 15) -> list[str]:
    """Lista valores únicos de colunas categóricas com poucos valores."""
    if ws.df is None or ws.df.empty:
        return []
    import pandas as pd

    lines: list[str] = []
    for col in ws.columns:
        series = ws.df[col]
        if pd.api.types.is_numeric_dtype(series):
            continue
        nunique = series.nunique(dropna=True)
        if nunique == 0 or nunique > max_unique:
            continue
        vals = series.dropna().unique()
        val_str = ", ".join(str(v) for v in vals[:max_unique])
        lines.append(f"  {col}: {val_str}")
    return lines


def _col_letter(idx: int) -> str:
    result = ""
    idx += 1
    while idx > 0:
        idx, rem = divmod(idx - 1, 26)
        result = chr(65 + rem) + result
    return result


def _build_a1_map(ws: Workspace) -> str:
    if not ws.columns:
        return ""
    parts = []
    for i, col in enumerate(ws.columns[:26]):
        parts.append(f"{_col_letter(i)}={col}")
    text = ", ".join(parts)
    if len(ws.columns) > 26:
        text += "..."
    return f"Referência A1: {text}"


def _detect_header_offset(ws: Workspace | pd.DataFrame) -> int:
    if isinstance(ws, pd.DataFrame):
        df = ws
    else:
        df = ws.df
    if df is None or df.empty or len(df) < 2:
        return 0
    best_score = -1
    best_offset = 0
    limit = min(5, len(df))
    for offset in range(1, limit + 1):
        row = df.iloc[offset - 1]
        total = 0
        good = 0
        for val in row:
            total += 1
            if isinstance(val, str) and val.strip() and len(val.strip()) < 50:
                good += 1
            elif pd.notna(val) and not isinstance(val, (int, float)):
                good += 1
        if total == 0:
            continue
        score = good / total
        if score > best_score:
            best_score = score
            best_offset = offset
    if best_score < 0.5:
        return 0
    return best_offset


def apply_header_offset(ws: Workspace, offset: int) -> Workspace:
    if ws.df is None or ws.df.empty or offset <= 0:
        return ws
    new_df = ws.df.copy()
    header_row = new_df.iloc[offset - 1]
    new_cols = []
    for val in header_row:
        label = str(val).strip() if pd.notna(val) and str(val).strip() != "nan" else None
        new_cols.append(label)
    for i, c in enumerate(new_cols):
        if not c:
            new_cols[i] = f"Col{i + 1}"
    seen: dict[str, int] = {}
    final_cols: list[str] = []
    for c in new_cols:
        seen[c] = seen.get(c, 0) + 1
        if seen[c] > 1:
            final_cols.append(f"{c}_{seen[c]}")
        else:
            final_cols.append(c)
    new_df = new_df.iloc[offset:].reset_index(drop=True)
    new_df.columns = final_cols
    return Workspace(
        path=ws.path,
        workbook_name=ws.workbook_name,
        sheet_name=ws.sheet_name,
        columns=final_cols,
        row_count=max(0, ws.row_count - offset),
        indexed_rows=len(new_df),
        truncated=ws.truncated,
        df=new_df,
        excel_live=ws.excel_live,
        excel_book_name=ws.excel_book_name,
        error=ws.error,
    )


def get_workspace_summary(ws: Workspace, max_context_chars: int = 6000) -> str:
    """Contexto rico da workspace para o LLM — dtypes, stats, amostra head+tail, valores categóricos.

    Parâmetro max_context_chars: limite de caracteres (~2K tokens). Se excedido,
    trima progressivamente: valores categóricos → tail → reduz head → remove stats.
    """
    if ws.error:
        return ws.error

    lines: list[str] = []

    lines.append(f"Arquivo: {ws.workbook_name}")
    lines.append(f"Aba: {ws.sheet_name}")

    if _is_nontabular(ws):
        lines.append("")
        lines.append("⚠ Esta aba parece ter layout não-tabular (células mescladas ou formatação livre).")
        lines.append("Colunas detectadas automaticamente podem não representar os dados corretamente.")
        lines.append("Considere usar \"aba [Nome]\" para navegar para uma aba mais estruturada.")

    col_display = ", ".join(ws.columns[:20])
    if len(ws.columns) > 20:
        col_display += "..."
    lines.append(f"Colunas ({len(ws.columns)}): {col_display}")

    a1_map = _build_a1_map(ws)
    if a1_map:
        lines.append(a1_map)

    if ws.df is not None and not ws.df.empty:
        hint_offset = _detect_header_offset(ws)
        if hint_offset > 0:
            lines.append(f"⚠ O cabeçalho parece estar na linha {hint_offset + 1}. Considere usar adjust_header para corrigir.")

    if ws.df is not None and not ws.df.empty:

        dtype_parts = []
        for col in ws.columns:
            dtype_parts.append(f"{col}={str(ws.df[col].dtype)}")
        lines.append(f"Tipos: {', '.join(dtype_parts[:20])}")

    lines.append(f"Linhas: {ws.indexed_rows}{'/' + str(ws.row_count) if ws.truncated else ''}")

    if ws.df is not None and not ws.df.empty:
        lines.append("")
        lines.append("Estatísticas por coluna:")
        col_stats = _build_column_stats(ws)
        lines.extend(col_stats)

        cat_lines = _build_categorical_values(ws)
        if cat_lines:
            lines.append("")
            lines.append("Valores únicos (categóricas com ≤15 únicos):")
            lines.extend(cat_lines)

        sample = _build_sample_block(ws)
        if sample:
            lines.append("")
            lines.append(sample)

    text = "\n".join(lines)

    if len(text) <= max_context_chars:
        return text

    return _trim_summary(text, ws, max_context_chars)


def _trim_summary(text: str, ws: Workspace, max_chars: int) -> str:
    """Trima o resumo progressivamente até caber no orçamento de caracteres."""
    if len(text) <= max_chars:
        return text

    lines = text.split("\n")

    def _find_block_end(start_idx: int, lines_list: list[str]) -> int:
        for i in range(start_idx + 1, len(lines_list)):
            line = lines_list[i]
            if line and not line.startswith("  ") and not line[0].isdigit():
                return i
        return len(lines_list)

    categorical_start = None
    for i, line in enumerate(lines):
        if "Valores únicos (categóricas" in line:
            categorical_start = i
            break

    if categorical_start is not None:
        block_end = _find_block_end(categorical_start, lines)
        lines = lines[:categorical_start] + lines[block_end:]
        text = "\n".join(lines)
        if len(text) <= max_chars:
            return text

    tail_marker = "Últimas"
    tail_idx = None
    for i, line in enumerate(lines):
        if line.startswith(tail_marker):
            tail_idx = i
            break
    if tail_idx is not None:
        block_end = _find_block_end(tail_idx, lines)
        lines = lines[:tail_idx] + lines[block_end:]
        text = "\n".join(lines)
        if len(text) <= max_chars:
            return text

    stats_start = None
    for i, line in enumerate(lines):
        if "Estatísticas por coluna:" in line:
            stats_start = i
            break
    if stats_start is not None:
        block_end = _find_block_end(stats_start, lines)
        lines = lines[:stats_start] + lines[block_end:]
        text = "\n".join(lines)
        if len(text) <= max_chars:
            return text

    if len(text) > max_chars:
        text = text[:max_chars - 3] + "..."

    return text

    tail_marker = "Últimas"
    tail_idx = None
    for i, line in enumerate(lines):
        if line.startswith(tail_marker):
            tail_idx = i
            break
    if tail_idx is not None:
        end = tail_idx + 1
        for i in range(end, len(lines)):
            if lines[i] and not lines[i].startswith(" "):
                end = i
                break
        else:
            end = len(lines)
        lines = lines[:tail_idx] + lines[end:]
        text = "\n".join(lines)
        if len(text) <= max_chars:
            return text

    stats_start = None
    for i, line in enumerate(lines):
        if "Estatísticas por coluna:" in line:
            stats_start = i
            break
    if stats_start is not None:
        next_section = None
        for i in range(stats_start + 1, len(lines)):
            if lines[i] and not lines[i].startswith("  "):
                next_section = i
                break
        if next_section is None:
            next_section = len(lines)
        lines = lines[:stats_start] + lines[next_section:]
        text = "\n".join(lines)
        if len(text) <= max_chars:
            return text

    if len(text) > max_chars:
        text = text[:max_chars - 3] + "..."

    return text


def get_workbook_overview(file_path: str, max_rows_per_sheet: int = 3) -> str:
    """Visão compacta de todas as abas do workbook para o LLM.

    Lê apenas as primeiras linhas de cada aba para gerar um índice com:
    nome da aba, colunas, contagem de linhas, e flag de não-tabular.
    """
    p = Path(file_path).resolve()
    if not p.exists():
        return err_str(ErrCode.FILE_NOT_FOUND)

    engine = _engine_for_suffix(p.suffix)
    if engine is None:
        return err_str(ErrCode.FILE_INVALID_FORMAT)

    import pandas as pd

    try:
        xl = pd.ExcelFile(str(p), engine=engine)
    except Exception as e:
        log.exception("Erro ao abrir workbook para overview (engine=%s): %s", engine, e)
        return err_str(ErrCode.INDEX_FAILED, str(e))

    all_names: list[str] = list(xl.sheet_names)
    if not all_names:
        xl.close()
        return f"Workbook: {p.name} — nenhuma aba encontrada."

    lines = [f"Workbook: {p.name} ({len(all_names)} aba(s))", "", "Resumo das abas:"]

    for idx, name in enumerate(all_names, 1):
        try:
            df = pd.read_excel(xl, sheet_name=name, nrows=max_rows_per_sheet)
        except Exception:
            lines.append(f"  {idx}. {name} — ⚠ erro de leitura")
            continue

        if df.empty and df.columns.empty:
            lines.append(f"  {idx}. {name} — vazia")
            continue

        headers = [str(c).strip() for c in df.columns]
        auto_count = sum(
            1 for h in headers
            if h.startswith("Unnamed") or (h.startswith("Col") and h[3:].isdigit())
        )
        nontabular = auto_count > len(headers) * 0.5

        total_rows: int | str = "?"
        try:
            full_df = pd.read_excel(xl, sheet_name=name)
            total_rows = len(full_df)
        except Exception:
            pass

        col_preview = ", ".join(headers[:6])
        if len(headers) > 6:
            col_preview += "..."
        nontab_marker = " ⚠ não-tabular" if nontabular else ""
        lines.append(f"  {idx}. {name}{nontab_marker} — {len(headers)} col, {total_rows} linhas [{col_preview}]")

    xl.close()

    if len(all_names) > 20:
        lines.append("")
        lines.append(f"Exibindo {len(all_names)} abas. Use \"aba [nome]\" para detalhar uma aba específica.")

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
