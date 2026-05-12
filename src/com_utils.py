"""COM context manager for Windows Excel automation.

Provides a ``with COMContext() as ctx:`` pattern that handles
``pythoncom.CoInitialize()`` / ``CoUninitialize()`` lifecycle and
offers a shared workbook-by-name resolver.
"""
from __future__ import annotations

import logging
from typing import Any

log = logging.getLogger(__name__)


class COMContext:
    """Context manager that initializes/uninitializes the COM apartment.

    Usage::

        with COMContext() as ctx:
            excel = ctx.excel_app
            wb = ctx.resolve_workbook(path="C:\\data.xlsm", name="data")
    """

    def __init__(self) -> None:
        self._pycom: Any = None
        self._excel: Any = None

    def __enter__(self) -> COMContext:
        try:
            import pythoncom  # type: ignore
            import win32com.client  # type: ignore

            self._pycom = pythoncom
            self._pycom.CoInitialize()  # type: ignore[attr-defined]
            self._excel = win32com.client.GetActiveObject("Excel.Application")
        except Exception:
            log.exception("Falha ao inicializar contexto COM")
            raise
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self._pycom is not None:
            try:
                self._pycom.CoUninitialize()  # type: ignore[attr-defined]
            except Exception:
                log.warning("Falha ao chamar CoUninitialize")

    @property
    def excel_app(self) -> Any:
        """The running Excel.Application COM object (may be None)."""
        return self._excel

    def resolve_workbook(self, path: str | None = None, name: str | None = None) -> Any:
        """Find an open workbook by FullName (path) or Name.

        Returns the COM workbook object or None.
        """
        if self._excel is None or self._excel.Workbooks.Count == 0:
            return None
        for wb in self._excel.Workbooks:
            wb_name = str(getattr(wb, "Name", ""))
            wb_full = str(getattr(wb, "FullName", "")) if getattr(wb, "FullName", None) else wb_name
            if path and wb_full and wb_full.lower() == path.lower():
                return wb
            if name and wb_name.lower() == name.lower():
                return wb
        return None

    @property
    def has_workbooks(self) -> bool:
        return self._excel is not None and self._excel.Workbooks.Count > 0
