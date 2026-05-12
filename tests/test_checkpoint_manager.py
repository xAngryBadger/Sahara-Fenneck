"""Tests for checkpoint manager: save, list, restore, index cleanup."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest
from src.checkpoints.manager import CheckpointManager
from src.indexing.excel_reader import Workspace


@pytest.fixture
def xlsx_file(tmp_path):
    path = tmp_path / "data.xlsx"
    pd.DataFrame({"A": [1, 2, 3]}).to_excel(path, index=False, engine="openpyxl")
    return path


@pytest.fixture
def mgr(xlsx_file):
    return CheckpointManager(str(xlsx_file))


@pytest.fixture
def ws(xlsx_file):
    df = pd.DataFrame({"A": [1, 2, 3]})
    return Workspace(
        path=str(xlsx_file), workbook_name="data.xlsx", sheet_name="Sheet",
        columns=["A"], row_count=3, indexed_rows=3, truncated=False,
        df=df, excel_live=False, excel_book_name=None, error=None,
    )


class TestCheckpointSave:
    def test_save_creates_file(self, mgr, ws, xlsx_file):
        info = mgr.save_checkpoint(ws)
        assert Path(info.path).exists()
        assert info.label

    def test_save_incremental_ids(self, mgr, ws):
        info1 = mgr.save_checkpoint(ws, label="first")
        info2 = mgr.save_checkpoint(ws, label="second")
        assert info2.interaction_id > info1.interaction_id

    def test_save_creates_dir(self, mgr, ws):
        mgr.save_checkpoint(ws)
        assert mgr.checkpoints_dir.exists()

    def test_save_excel_live_no_com(self, tmp_path, xlsx_file):
        path = tmp_path / "live.xlsx"
        pd.DataFrame({"X": [1]}).to_excel(path, index=False, engine="openpyxl")
        ws_live = Workspace(
            path=str(path), workbook_name="live.xlsx", sheet_name="Sheet",
            columns=["X"], row_count=1, indexed_rows=1, truncated=False,
            df=pd.DataFrame({"X": [1]}), excel_live=True, excel_book_name="live.xlsx", error=None,
        )
        mgr_live = CheckpointManager(str(path))
        info = mgr_live.save_checkpoint(ws_live)
        assert Path(info.path).exists()


class TestCheckpointList:
    def test_list_empty(self, mgr):
        assert mgr.list_checkpoints() == []

    def test_list_after_save(self, mgr, ws):
        mgr.save_checkpoint(ws, label="cp1")
        mgr.save_checkpoint(ws, label="cp2")
        cps = mgr.list_checkpoints()
        assert len(cps) == 2

    def test_list_filters_deleted_files(self, mgr, ws):
        info = mgr.save_checkpoint(ws, label="temp")
        Path(info.path).unlink()
        cps = mgr.list_checkpoints()
        assert len(cps) == 0

    def test_list_corrupted_index(self, mgr, ws):
        mgr.save_checkpoint(ws)
        mgr.index_file.write_text("not json{{{", encoding="utf-8")
        assert mgr.list_checkpoints() == []


class TestCheckpointRestore:
    def test_restore_overwrites_workspace(self, mgr, ws, xlsx_file):
        info = mgr.save_checkpoint(ws)
        pd.DataFrame({"CHANGED": [99]}).to_excel(xlsx_file, index=False, engine="openpyxl")
        result = mgr.restore(info.path)
        assert result is True
        df = pd.read_excel(xlsx_file, engine="openpyxl")
        assert "A" in df.columns

    def test_restore_missing_file(self, mgr):
        assert mgr.restore("/nonexistent/path.xlsx") is False

    def test_restore_no_workspace_path(self, tmp_path):
        mgr2 = CheckpointManager("", interaction_label="test")
        mgr2.workspace_path = Path("")
        assert mgr2.restore("/some/path") is False


class TestCheckpointIndex:
    def test_index_file_created(self, mgr, ws):
        mgr.save_checkpoint(ws)
        assert mgr.index_file.exists()
        data = json.loads(mgr.index_file.read_text(encoding="utf-8"))
        assert len(data) == 1

    def test_index_max_entries(self, mgr, ws):
        for i in range(5):
            mgr.save_checkpoint(ws, label=f"cp_{i}")
        data = json.loads(mgr.index_file.read_text(encoding="utf-8"))
        assert len(data) == 5

    def test_normalized_workspace_key(self, mgr):
        key = mgr._normalized_workspace_key()
        assert isinstance(key, str)
        assert len(key) > 0

    def test_normalized_workspace_key_none(self, mgr):
        key = mgr._normalized_workspace_key(None)
        assert isinstance(key, str)
