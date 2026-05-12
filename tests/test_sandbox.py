"""Adversarial sandbox bypass tests — 20+ attempts to break _validate_code."""
from __future__ import annotations

from src.agent.tools import _validate_code


class TestSandboxBypass:
    """Each test documents the bypass technique being tested."""

    def test_getattr_os_system(self):
        """getattr(os, 'system') — classic sandbox escape."""
        ok, err = _validate_code("getattr(os, 'system')('rm -rf /')")
        assert not ok
        assert "não permitido" in err.lower() or "getattr" in err.lower()

    def test_dunder_class_bases_subclasses(self):
        """().__class__.__bases__[0].__subclasses__() — Python MRO escape."""
        ok, err = _validate_code("x = ().__class__.__bases__[0].__subclasses__()")
        assert not ok
        assert "dunder" in err.lower() or "não permitido" in err.lower()

    def test_dunder_class_base(self):
        """[].__class__.__base__ — simpler MRO variant."""
        ok, err = _validate_code("x = [].__class__.__base__")
        assert not ok

    def test_eval_call(self):
        """eval('os.system(\"ls\")') — direct eval."""
        ok, err = _validate_code("eval('os.system(\"ls\")')")
        assert not ok
        assert "eval" in err.lower()

    def test_exec_call(self):
        """exec('import os') — direct exec."""
        ok, err = _validate_code("exec('import os')")
        assert not ok
        assert "exec" in err.lower()

    def test_compile_call(self):
        """compile + eval combo."""
        ok, err = _validate_code("compile('1+1', '<>', 'eval')")
        assert not ok
        assert "compile" in err.lower()

    def test_import_os(self):
        """import os — forbidden module."""
        ok, err = _validate_code("import os")
        assert not ok
        assert "Módulo não permitido" in err

    def test_import_subprocess(self):
        """import subprocess — forbidden module."""
        ok, err = _validate_code("import subprocess")
        assert not ok

    def test_from_os_import_system(self):
        """from os import system — forbidden module via from."""
        ok, err = _validate_code("from os import system")
        assert not ok
        assert "Módulo não permitido" in err

    def test_open_call(self):
        """open('/etc/passwd') — file access."""
        ok, err = _validate_code("open('/etc/passwd').read()")
        assert not ok
        assert "open" in err.lower()

    def test_breakpoint_call(self):
        """breakpoint() — debugger escape."""
        ok, err = _validate_code("breakpoint()")
        assert not ok
        assert "breakpoint" in err.lower()

    def test_exit_call(self):
        """exit() — process termination."""
        ok, err = _validate_code("exit()")
        assert not ok
        assert "exit" in err.lower()

    def test_quit_call(self):
        """quit() — process termination."""
        ok, err = _validate_code("quit()")
        assert not ok
        assert "quit" in err.lower()

    def test_help_call(self):
        """help() — interactive help escape."""
        ok, err = _validate_code("help()")
        assert not ok
        assert "help" in err.lower()

    def test_type_call(self):
        """type(x) — type introspection."""
        ok, err = _validate_code("type(42)")
        assert not ok
        assert "type" in err.lower()

    def test_vars_call(self):
        """vars() — local variable access."""
        ok, err = _validate_code("vars()")
        assert not ok
        assert "vars" in err.lower()

    def test_dir_call(self):
        """dir() — namespace enumeration."""
        ok, err = _validate_code("dir()")
        assert not ok
        assert "dir" in err.lower()

    def test_globals_call(self):
        """globals() — global namespace access."""
        ok, err = _validate_code("globals()")
        assert not ok
        assert "globals" in err.lower()

    def test_locals_call(self):
        """locals() — local namespace access."""
        ok, err = _validate_code("locals()")
        assert not ok
        assert "locals" in err.lower()

    def test_hasattr_call(self):
        """hasattr(os, 'system') — attribute introspection."""
        ok, err = _validate_code("hasattr(os, 'system')")
        assert not ok
        assert "hasattr" in err.lower()

    def test_setattr_call(self):
        """setattr(x, '__class__', ...) — attribute manipulation."""
        ok, err = _validate_code("setattr(x, 'y', 1)")
        assert not ok
        assert "setattr" in err.lower()

    def test_delattr_call(self):
        """delattr(x, 'y') — attribute deletion."""
        ok, err = _validate_code("delattr(x, 'y')")
        assert not ok
        assert "delattr" in err.lower()

    def test_dunder_builtins_attribute(self):
        """pd.__builtins__ — access builtins through module attribute."""
        ok, err = _validate_code("x = pd.__builtins__")
        assert not ok
        assert "dunder" in err.lower() or "não permitido" in err.lower()

    def test_wrap_close_escape(self):
        """[x for x in [].__class__.__base__.__subclasses__() if 'wrap_close' in x.__name__]"""
        ok, err = _validate_code("[x for x in [].__class__.__base__.__subclasses__() if 'wrap_close' in x.__name__]")
        assert not ok

    def test_syntax_error(self):
        """Invalid Python syntax should be rejected."""
        ok, err = _validate_code("def foo(:")
        assert not ok
        assert "sintaxe" in err.lower()

    def test_safe_code_passes(self):
        """Valid safe code should pass validation."""
        ok, err = _validate_code("df = df.sort_values(by='A')")
        assert ok
        assert err == ""

    def test_pandas_import_allowed(self):
        """import pandas should be allowed."""
        ok, err = _validate_code("import pandas as pd")
        assert ok

    def test_openpyxl_import_allowed(self):
        """import openpyxl should be allowed."""
        ok, err = _validate_code("import openpyxl")
        assert ok

    def test_math_import_allowed(self):
        """import math should be allowed."""
        ok, err = _validate_code("import math")
        assert ok

    def test_datetime_import_allowed(self):
        """import datetime should be allowed."""
        ok, err = _validate_code("import datetime")
        assert ok

    def test_input_call_blocked(self):
        """input() — interactive input should be blocked."""
        ok, err = _validate_code("input('prompt')")
        assert not ok
        assert "input" in err.lower()

    def test_memoryview_blocked(self):
        """memoryview — low-level memory access."""
        ok, err = _validate_code("memoryview(b'x')")
        assert not ok

    def test_bytearray_blocked(self):
        """bytearray — low-level memory manipulation."""
        ok, err = _validate_code("bytearray(b'x')")
        assert not ok

    def test_super_blocked(self):
        """super() — MRO traversal."""
        ok, err = _validate_code("super()")
        assert not ok
