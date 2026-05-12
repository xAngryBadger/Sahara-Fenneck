"""Indexação de planilhas Excel (Excel aberto e arquivos locais)."""
from .excel_reader import (
    DEFAULT_MAX_ROWS,
    Workspace,
    get_workspace_summary,
    hydrate_workspace_full,
    index_file_multi,
    index_from_excel,
    index_from_path,
    index_open_excel_workbooks,
    is_excel_file,
)

__all__ = [
    "Workspace",
    "DEFAULT_MAX_ROWS",
    "is_excel_file",
    "index_from_excel",
    "index_open_excel_workbooks",
    "index_from_path",
    "index_file_multi",
    "get_workspace_summary",
    "hydrate_workspace_full",
]
