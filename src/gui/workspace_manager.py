"""
WorkspaceManager — estado de workspaces indexados na sessao.
"""
import logging
import threading
from pathlib import Path

from ..indexing import Workspace

log = logging.getLogger(__name__)


class WorkspaceManager:
    def __init__(self):
        self._workspaces: dict[str, Workspace] = {}
        self._workspaces_lock = threading.Lock()
        self._active_key: str | None = None

    @staticmethod
    def workspace_key(ws: Workspace) -> str:
        book = ws.workbook_name or Path(ws.path).name or "Planilha"
        return f"{book} :: {ws.sheet_name}"

    def active(self) -> Workspace | None:
        with self._workspaces_lock:
            if not self._workspaces:
                return None
            if self._active_key and self._active_key in self._workspaces:
                return self._workspaces[self._active_key]
            self._active_key = next(iter(self._workspaces.keys()))
            return self._workspaces[self._active_key]

    def set_active(self, key: str):
        with self._workspaces_lock:
            if key in self._workspaces:
                self._active_key = key

    def status_text(self) -> str:
        active = self.active()
        if not active:
            return "Pronto | Nenhuma planilha indexada"
        with self._workspaces_lock:
            count = len(self._workspaces)
        return f"{active.summary_one_line()} | sessão: {count} item(ns)"

    def add(self, ws: Workspace) -> tuple[str, bool]:
        key = self.workspace_key(ws)
        with self._workspaces_lock:
            self._workspaces[key] = ws
            self._active_key = key
        return key, bool(ws.error)

    def remove(self, key: str) -> bool:
        with self._workspaces_lock:
            if key not in self._workspaces:
                return False
            del self._workspaces[key]
            if self._active_key == key:
                self._active_key = None
        return True

    def items(self) -> list[tuple[str, Workspace]]:
        with self._workspaces_lock:
            return list(self._workspaces.items())

    @property
    def active_key(self) -> str | None:
        return self._active_key

    @property
    def count(self) -> int:
        with self._workspaces_lock:
            return len(self._workspaces)

    def clear(self):
        with self._workspaces_lock:
            self._workspaces.clear()
            self._active_key = None
