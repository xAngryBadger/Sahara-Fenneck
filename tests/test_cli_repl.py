"""Tests for CLI REPL: command parsing and workspace management."""
from __future__ import annotations

from src.cli.repl import FennecREPL


class TestFennecREPLInit:
    def test_no_file(self):
        repl = FennecREPL()
        assert repl.workspace is None

    def test_with_file(self, tmp_path):
        import pandas as pd
        xlsx = tmp_path / "test.xlsx"
        pd.DataFrame({"A": [1, 2]}).to_excel(xlsx, index=False, engine="openpyxl")
        repl = FennecREPL(initial_file=str(xlsx))
        assert repl.workspace is not None

    def test_file_not_found(self):
        repl = FennecREPL(initial_file="/nonexistent/file.xlsx")
        assert repl.workspace is None


class TestREPLCommands:
    def test_help_runs(self):
        repl = FennecREPL()
        repl._cmd_help()

    def test_load_nonexistent(self):
        repl = FennecREPL()
        repl._cmd_load("/nonexistent.xlsx")
        assert repl.workspace is None

    def test_load_wrong_extension(self, tmp_path):
        txt = tmp_path / "data.txt"
        txt.write_text("hello")
        repl = FennecREPL()
        repl._cmd_load(str(txt))
        assert repl.workspace is None

    def test_backend_invalid(self):
        repl = FennecREPL()
        repl._cmd_backend("invalid_backend")

    def test_model_empty(self):
        repl = FennecREPL()
        repl._cmd_model("")

    def test_summary_no_workspace(self):
        repl = FennecREPL()
        repl._cmd_summary()

    def test_checkpoints_no_workspace(self):
        repl = FennecREPL()
        repl._cmd_checkpoints()

    def test_undo_no_workspace(self):
        repl = FennecREPL()
        repl._cmd_undo()


class TestREPLHandleCommand:
    def test_quit_returns_false(self):
        repl = FennecREPL()
        assert repl._handle_command("/quit") is False

    def test_unknown_command(self):
        repl = FennecREPL()
        assert repl._handle_command("/unknown") is True

    def test_help_command(self):
        repl = FennecREPL()
        assert repl._handle_command("/help") is True
