# -*- coding: utf-8 -*-
"""
Gerencia checkpoints da planilha: um checkpoint é salvo antes de cada alteração
que o agente aplicar, permitindo restaurar a qualquer momento.
"""
from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from ..indexing.excel_reader import Workspace


@dataclass
class CheckpointInfo:
    path: str
    timestamp: str
    label: str
    interaction_id: Optional[int] = None


class CheckpointManager:
    """Salva cópia da planilha antes de cada alteração; lista e restaura checkpoints."""

    def __init__(self, workspace_path: str, interaction_label: Optional[str] = None):
        self.workspace_path = Path(workspace_path).resolve() if workspace_path else Path(".").resolve()
        self.root_dir = self.workspace_path.parent
        self.checkpoints_dir = self.root_dir / "_fennec_checkpoints"
        self.index_file = self.checkpoints_dir / "index.json"
        self._interaction = 0
        self._interaction_label = interaction_label or "alteração"

    def _normalized_workspace_key(self, value: str | Path | None = None) -> str:
        raw = value if value is not None else self.workspace_path
        try:
            return str(Path(raw).resolve()).lower()
        except Exception:
            return str(raw or "").strip().lower()

    def _ensure_dir(self) -> None:
        self.checkpoints_dir.mkdir(parents=True, exist_ok=True)

    def _next_id(self) -> int:
        self._interaction += 1
        return self._interaction

    def _save_copy_from_excel_live(self, workspace: Workspace, dest: Path) -> bool:
        """Tenta SaveCopyAs no workbook aberto via COM (quando excel_live=True)."""
        pythoncom = None
        try:
            import pythoncom  # type: ignore
            import win32com.client  # type: ignore

            pythoncom.CoInitialize()
            excel = win32com.client.GetActiveObject("Excel.Application")
            if excel is None or excel.Workbooks.Count == 0:
                return False

            target = None
            for wb in excel.Workbooks:
                wb_name = str(getattr(wb, "Name", ""))
                wb_full = str(getattr(wb, "FullName", ""))
                if workspace.path and wb_full and wb_full.lower() == workspace.path.lower():
                    target = wb
                    break
                if workspace.excel_book_name and wb_name.lower() == workspace.excel_book_name.lower():
                    target = wb
                    break

            if target is None:
                return False

            target.SaveCopyAs(str(dest))
            return True
        except Exception:
            return False
        finally:
            if pythoncom is not None:
                try:
                    pythoncom.CoUninitialize()
                except Exception:
                    pass

    def save_checkpoint(self, workspace: Workspace, label: Optional[str] = None) -> CheckpointInfo:
        """
        Salva um checkpoint da planilha atual (antes ou depois de uma alteração).
        Prioridade:
        1) Excel aberto (SaveCopyAs) quando excel_live=True.
        2) Cópia de arquivo da path no disco.
        """
        self._ensure_dir()
        cid = self._next_id()
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        name = f"checkpoint_{ts}_{cid}.xlsx"
        dest = self.checkpoints_dir / name
        label = label or f"{self._interaction_label} #{cid}"

        saved = False
        if getattr(workspace, "excel_live", False):
            saved = self._save_copy_from_excel_live(workspace, dest)

        if not saved and workspace.path and Path(workspace.path).exists():
            shutil.copy2(workspace.path, dest)
            saved = True

        if not saved:
            raise RuntimeError("Não foi possível salvar checkpoint desta planilha.")

        info = CheckpointInfo(path=str(dest), timestamp=ts, label=label, interaction_id=cid)
        self._append_to_index(info)
        return info

    def _append_to_index(self, info: CheckpointInfo) -> None:
        self._ensure_dir()
        data = []
        if self.index_file.exists():
            try:
                data = json.loads(self.index_file.read_text(encoding="utf-8"))
            except Exception:
                data = []

        data.append(
            {
                "workspace_path": self._normalized_workspace_key(),
                "path": info.path,
                "timestamp": info.timestamp,
                "label": info.label,
                "interaction_id": info.interaction_id,
            }
        )
        self.index_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def list_checkpoints(self) -> List[CheckpointInfo]:
        """Lista checkpoints da planilha atual."""
        if not self.index_file.exists():
            return []
        try:
            data = json.loads(self.index_file.read_text(encoding="utf-8"))
        except Exception:
            return []

        key = self._normalized_workspace_key()
        out = []
        for item in data:
            if self._normalized_workspace_key(item.get("workspace_path", "")) != key:
                continue
            path = item.get("path", "")
            p = Path(path)
            if p.exists():
                out.append(
                    CheckpointInfo(
                        path=path,
                        timestamp=item.get("timestamp", ""),
                        label=item.get("label", p.name),
                        interaction_id=item.get("interaction_id"),
                    )
                )
        return out[-50:]

    def restore(self, checkpoint_path: str) -> bool:
        """
        Restaura a planilha atual a partir de um checkpoint (copia o arquivo
        do checkpoint sobre o arquivo da workspace).
        """
        src = Path(checkpoint_path)
        if not src.exists() or not self.workspace_path:
            return False
        try:
            shutil.copy2(src, self.workspace_path)
            return True
        except Exception:
            return False
