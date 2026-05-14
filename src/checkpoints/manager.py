"""
Gerencia checkpoints da planilha: um checkpoint é salvo antes de cada alteração
que o agente aplicar, permitindo restaurar a qualquer momento.
"""
from __future__ import annotations

import json
import logging
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from ..indexing.excel_reader import Workspace

log = logging.getLogger(__name__)


@dataclass
class CheckpointInfo:
    path: str
    timestamp: str
    label: str
    interaction_id: int | None = None


_MAX_INDEX_ENTRIES_PER_WORKSPACE = 200


class CheckpointManager:
    """Salva cópia da planilha antes de cada alteração; lista e restaura checkpoints."""

    def __init__(self, workspace_path: str, interaction_label: str | None = None):
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
            log.warning("Falha ao normalizar caminho do workspace: %s", raw)
            return str(raw or "").strip().lower()

    def _ensure_dir(self) -> None:
        self.checkpoints_dir.mkdir(parents=True, exist_ok=True)

    def _next_id(self) -> int:
        self._interaction += 1
        return self._interaction

    def _save_copy_from_excel_live(self, workspace: Workspace, dest: Path) -> bool:
        """Tenta SaveCopyAs no workbook aberto via COM (quando excel_live=True)."""
        try:
            from ..com_utils import COMContext

            with COMContext() as ctx:
                wb = ctx.resolve_workbook(path=workspace.path, name=workspace.excel_book_name)
                if wb is None:
                    return False
                wb.SaveCopyAs(str(dest))
                return True
        except Exception:
            log.exception("Falha ao salvar cópia via COM SaveCopyAs")
            return False

    def save_checkpoint(self, workspace: Workspace, label: str | None = None) -> CheckpointInfo:
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
        data: list[dict] = []
        if self.index_file.exists():
            try:
                data = json.loads(self.index_file.read_text(encoding="utf-8"))
            except Exception:
                log.warning("Falha ao ler índice de checkpoints; iniciando com lista vazia")
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

        key = self._normalized_workspace_key()
        workspace_entries = [e for e in data if self._normalized_workspace_key(e.get("workspace_path", "")) == key]
        other_entries = [e for e in data if self._normalized_workspace_key(e.get("workspace_path", "")) != key]
        if len(workspace_entries) > _MAX_INDEX_ENTRIES_PER_WORKSPACE:
            keep = workspace_entries[-_MAX_INDEX_ENTRIES_PER_WORKSPACE:]
            stale_entries = workspace_entries[: len(workspace_entries) - _MAX_INDEX_ENTRIES_PER_WORKSPACE]
            stale_paths = {e.get("path", "") for e in stale_entries}
            for sp in stale_paths:
                try:
                    Path(sp).unlink(missing_ok=True)
                except Exception:
                    pass
            workspace_entries = keep
        data = other_entries + workspace_entries

        self.index_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def list_checkpoints(self) -> list[CheckpointInfo]:
        """Lista checkpoints da planilha atual."""
        if not self.index_file.exists():
            return []
        try:
            data = json.loads(self.index_file.read_text(encoding="utf-8"))
        except Exception:
            log.warning("Falha ao ler índice de checkpoints em list_checkpoints")
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
            log.exception("Falha ao restaurar checkpoint")
            return False
