"""Backward-compat re-exports — code lives in sandbox.py, actions.py, excel_write.py."""
from __future__ import annotations

from .actions import (
    _QUERY_KINDS,
    _WB_KINDS,
    KNOWN_ACTION_KINDS,
    _apply_actions_to_df,
    _classify_err,
    _normalize_actions,
    _require_column,
)
from .excel_write import _df_to_excel_matrix, _excel_scalar, structured_actions_tool
from .sandbox import ALLOWED_MODULES, FORBIDDEN_NAMES, SAFE_BUILTINS, _validate_code

__all__ = [
    "ALLOWED_MODULES",
    "FORBIDDEN_NAMES",
    "KNOWN_ACTION_KINDS",
    "SAFE_BUILTINS",
    "_QUERY_KINDS",
    "_WB_KINDS",
    "_apply_actions_to_df",
    "_classify_err",
    "_df_to_excel_matrix",
    "_excel_scalar",
    "_normalize_actions",
    "_require_column",
    "_validate_code",
    "structured_actions_tool",
]
