from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..errcodes import ErrCode, err_str

__all__ = ["ErrCode", "ToolResult", "err_str"]


@dataclass
class ToolResult:
    success: bool
    message: str
    data: dict[str, Any] = field(default_factory=dict)
    error_code: ErrCode | None = None

    def __str__(self) -> str:
        return self.message

    @staticmethod
    def ok(message: str, **data: Any) -> ToolResult:
        return ToolResult(success=True, message=message, data=data)

    @staticmethod
    def err(message: str, code: ErrCode | None = None, **data: Any) -> ToolResult:
        return ToolResult(success=False, message=message, data=data, error_code=code)
