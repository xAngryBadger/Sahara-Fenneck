"""Unit tests for CheckpointManager."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from src.checkpoints.manager import CheckpointManager
from src.indexing.excel_reader import Workspace


def _create_xlsx(path: Path, df=None):
    if df is None:
        df = pd.DataFrame({"A": [1, 2, 3], "B": ["x", "y", "z"]})
    df.to_excel(path, index=False, engine="openpyxl")


class TestCheckpointSave:
    def test_save_creates_copy(self, tmp_path):
        src = tmp_path / "data.xlsx"
        _create_xlsx(src)
        mgr = CheckpointManager(str(src))
        info = mgr.save_checkpoint(Workspace(
            path=str(src), workbook_name="data.xlsx", sheet_name="Sheet",
            columns=["A", "B"], row_count=3, indexed_rows=3,
        ))
        assert Path(info.path).exists()
        assert Path(info.path) != src

    def test_save_updates_index(self, tmp_path):
        src = tmp_path / "data.xlsx"
        _create_xlsx(src)
        mgr = CheckpointManager(str(src))
        mgr.save_checkpoint(Workspace(
            path=str(src), workbook_name="data.xlsx", sheet_name="Sheet",
            columns=["A"], row_count=1, indexed_rows=1,
        ))
        assert mgr.index_file.exists()
        data = json.loads(mgr.index_file.read_text(encoding="utf-8"))
        assert len(data) >= 1

    def test_save_with_label(self, tmp_path):
        src = tmp_path / "data.xlsx"
        _create_xlsx(src)
        mgr = CheckpointManager(str(src))
        info = mgr.save_checkpoint(Workspace(
            path=str(src), workbook_name="data.xlsx", sheet_name="Sheet",
            columns=["A"], row_count=1, indexed_rows=1,
        ), label="Antes da ordenação")
        assert "ordenação" in info.label


class TestCheckpointRestore:
    def test_restore_overwrites_file(self, tmp_path):
        src = tmp_path / "data.xlsx"
        _create_xlsx(src, pd.DataFrame({"A": [1, 2, 3]}))
        mgr = CheckpointManager(str(src))
        mgr.save_checkpoint(Workspace(
            path=str(src), workbook_name="data.xlsx", sheet_name="Sheet",
            columns=["A"], row_count=3, indexed_rows=3,
        ))
        # Modify the original
        _create_xlsx(src, pd.DataFrame({"A": [99, 99]}))
        # Restore
        checkpoints = mgr.list_checkpoints()
        mgr.restore(checkpoints[0].path)
        # Verify original content restored
        restored = pd.read_excel(src, engine="openpyxl")
        assert list(restored["A"]) == [1, 2, 3]

    def test_restore_missing_checkpoint_fails(self, tmp_path):
        src = tmp_path / "data.xlsx"
        _create_xlsx(src)
        mgr = CheckpointManager(str(src))
        result = mgr.restore("/nonexistent/checkpoint.xlsx")
        assert result is False


class TestCheckpointList:
    def test_list_returns_checkpoints(self, tmp_path):
        src = tmp_path / "data.xlsx"
        _create_xlsx(src)
        mgr = CheckpointManager(str(src))
        mgr.save_checkpoint(Workspace(
            path=str(src), workbook_name="data.xlsx", sheet_name="Sheet",
            columns=["A"], row_count=1, indexed_rows=1,
        ), label="cp1")
        mgr.save_checkpoint(Workspace(
            path=str(src), workbook_name="data.xlsx", sheet_name="Sheet",
            columns=["A"], row_count=1, indexed_rows=1,
        ), label="cp2")
        cps = mgr.list_checkpoints()
        assert len(cps) == 2

    def test_list_empty(self, tmp_path):
        src = tmp_path / "data.xlsx"
        _create_xlsx(src)
        mgr = CheckpointManager(str(src))
        assert mgr.list_checkpoints() == []


class TestCheckpointIndexPersistence:
    def test_index_persists_across_instances(self, tmp_path):
        src = tmp_path / "data.xlsx"
        _create_xlsx(src)
        mgr1 = CheckpointManager(str(src))
        mgr1.save_checkpoint(Workspace(
            path=str(src), workbook_name="data.xlsx", sheet_name="Sheet",
            columns=["A"], row_count=1, indexed_rows=1,
        ), label="from_mgr1")
        # New instance pointing at same file
        mgr2 = CheckpointManager(str(src))
        cps = mgr2.list_checkpoints()
        assert len(cps) == 1
        assert cps[0].label == "from_mgr1"

    def test_corrupted_index_handled_gracefully(self, tmp_path):
        src = tmp_path / "data.xlsx"
        _create_xlsx(src)
        mgr = CheckpointManager(str(src))
        mgr._ensure_dir()
        mgr.index_file.write_text("NOT VALID JSON{{{", encoding="utf-8")
        # Should not crash, return empty list
        cps = mgr.list_checkpoints()
        assert isinstance(cps, list)


class TestCheckpointMax:
    def test_max_50_enforced(self, tmp_path):
        src = tmp_path / "data.xlsx"
        _create_xlsx(src)
        mgr = CheckpointManager(str(src))
        for i in range(55):
            mgr.save_checkpoint(Workspace(
                path=str(src), workbook_name="data.xlsx", sheet_name="Sheet",
                columns=["A"], row_count=1, indexed_rows=1,
            ), label=f"cp_{i}")
        cps = mgr.list_checkpoints()
        assert len(cps) <= 50
