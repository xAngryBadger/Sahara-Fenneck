"""Tests for structured error codes (ErrCode / err_str)."""
from __future__ import annotations

from src.agent.result import ToolResult
from src.errcodes import ERR_MESSAGES, ErrCode, err_str


class TestErrCodeEnum:
    def test_all_codes_have_messages(self):
        for code in ErrCode:
            assert code in ERR_MESSAGES, f"{code} missing from ERR_MESSAGES"

    def test_code_values_are_unique(self):
        values = [c.value for c in ErrCode]
        assert len(values) == len(set(values))

    def test_code_format(self):
        for code in ErrCode:
            assert code.value[0] == "E", f"{code.value} doesn't start with E"
            assert len(code.value) == 4, f"{code.value} isn't 4 chars"


class TestErrStr:
    def test_basic_message(self):
        result = err_str(ErrCode.FILE_NOT_FOUND)
        assert "[E014]" in result
        assert "Arquivo não encontrado" in result

    def test_with_detail(self):
        result = err_str(ErrCode.COLUMN_MISSING, "Salário")
        assert "[E010]" in result
        assert "Salário" in result

    def test_no_detail(self):
        result = err_str(ErrCode.SHEET_EMPTY)
        assert result.endswith("Aba vazia")


class TestToolResultErrCode:
    def test_err_with_code(self):
        tr = ToolResult.err("test message", code=ErrCode.PARSE_ACTIONS)
        assert tr.error_code is ErrCode.PARSE_ACTIONS
        assert not tr.success

    def test_err_without_code(self):
        tr = ToolResult.err("generic error")
        assert tr.error_code is None
        assert not tr.success

    def test_ok_has_no_code(self):
        tr = ToolResult.ok("done")
        assert tr.error_code is None
        assert tr.success
