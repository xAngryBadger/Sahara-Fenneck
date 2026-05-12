"""Shared fixtures for fennec-excel test suite."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

ROOT = Path(__file__).resolve().parent.parent
# Add the parent of src/ so that 'src' is a package we can import from
sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402
import src.agent.result as _ar  # noqa: E402
import src.checkpoints.manager as _cm  # noqa: E402
import src.indexing.excel_reader as _ier  # noqa: E402

Workspace = _ier.Workspace
ToolResult = _ar.ToolResult
CheckpointManager = _cm.CheckpointManager


@pytest.fixture
def tmp_dir(tmp_path):
    """Temporary directory for test artifacts."""
    return tmp_path


@pytest.fixture
def sample_df():
    """Small DataFrame for testing structured actions."""
    return pd.DataFrame(
        {
            "Nome": ["Alice", "Bob", "Carlos", "Diana", "Eve"],
            "Idade": [30, 25, 35, 28, 22],
            "Cidade": ["São Paulo", "Rio", "Belo Horizonte", "Curitiba", "Salvador"],
            "Salário": [5000.0, 4500.0, 6000.0, 4800.0, 3800.0],
        }
    )


@pytest.fixture
def workspace(sample_df):
    """In-memory Workspace with sample_df — no file on disk."""
    return Workspace(
        path="",
        workbook_name="test.xlsx",
        sheet_name="Planilha1",
        columns=list(sample_df.columns),
        row_count=len(sample_df),
        indexed_rows=len(sample_df),
        truncated=False,
        df=sample_df,
        excel_live=False,
        excel_book_name=None,
        error=None,
    )


@pytest.fixture
def workspace_with_path(sample_df, tmp_path):
    """Workspace backed by a real .xlsx file."""
    xlsx = tmp_path / "test.xlsx"
    sample_df.to_excel(xlsx, index=False, engine="openpyxl")
    return Workspace(
        path=str(xlsx),
        workbook_name="test.xlsx",
        sheet_name="Planilha1",
        columns=list(sample_df.columns),
        row_count=len(sample_df),
        indexed_rows=len(sample_df),
        truncated=False,
        df=sample_df,
        excel_live=False,
        excel_book_name=None,
        error=None,
    )


@pytest.fixture
def checkpoint_manager(tmp_path):
    """CheckpointManager pointing at a temp directory."""
    xlsx = tmp_path / "sheet.xlsx"
    pd.DataFrame({"A": [1, 2, 3]}).to_excel(xlsx, index=False, engine="openpyxl")
    return CheckpointManager(str(xlsx))


@pytest.fixture
def fake_ollama():
    """Mock OllamaClient that returns scripted responses."""
    client = MagicMock()
    client.model = "test-model"
    client.base_url = "http://localhost:11434"
    client.is_available.return_value = True
    return client


@pytest.fixture
def sample_xlsx(tmp_path):
    """Create a sample .xlsx file and return its path."""
    df = pd.DataFrame(
        {
            "Col1": [1, 2, 3],
            "Col2": ["a", "b", "c"],
            "Col3": [10.0, 20.0, 30.0],
        }
    )
    path = tmp_path / "sample.xlsx"
    df.to_excel(path, index=False, engine="openpyxl")
    return path


@pytest.fixture
def sample_xlsx_multi_sheet(tmp_path):
    """Create a .xlsx with multiple sheets and return its path."""
    path = tmp_path / "multi.xlsx"
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        pd.DataFrame({"X": [1, 2]}).to_excel(writer, sheet_name="Aba1", index=False)
        pd.DataFrame({"Y": [3, 4]}).to_excel(writer, sheet_name="Aba2", index=False)
        pd.DataFrame({"Z": [5, 6]}).to_excel(writer, sheet_name="Aba3", index=False)
    return path


@pytest.fixture
def empty_xlsx(tmp_path):
    """Create an .xlsx with headers only (no data rows)."""
    df = pd.DataFrame(columns=["Col1", "Col2", "Col3"])
    path = tmp_path / "empty.xlsx"
    df.to_excel(path, index=False, engine="openpyxl")
    return path
