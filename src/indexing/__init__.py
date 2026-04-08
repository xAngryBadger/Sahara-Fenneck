# -*- coding: utf-8 -*-
"""Indexação de planilhas Excel (Excel aberto e arquivos locais)."""
from .excel_reader import (
    Workspace,
    DEFAULT_MAX_ROWS,
    is_excel_file,
    index_from_excel,
    index_open_excel_workbooks,
    index_from_path,
    index_file_multi,
    get_workspace_summary,
    hydrate_workspace_full,
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
