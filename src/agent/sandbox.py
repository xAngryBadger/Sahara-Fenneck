"""Validação de código seguro (legado — usado apenas por testes de segurança)."""
from __future__ import annotations

import ast

ALLOWED_MODULES = {"pandas", "openpyxl", "odf", "xlrd", "math", "datetime"}
FORBIDDEN_NAMES = {
    "__import__",
    "__build_class__",
    "__builtins__",
    "builtins",
    "eval",
    "exec",
    "open",
    "compile",
    "globals",
    "locals",
    "input",
    "object",
    "os",
    "sys",
    "subprocess",
    "getattr",
    "setattr",
    "delattr",
    "hasattr",
    "type",
    "vars",
    "dir",
    "breakpoint",
    "exit",
    "quit",
    "help",
    "memoryview",
    "bytearray",
    "classmethod",
    "staticmethod",
    "property",
    "super",
}
SAFE_BUILTINS = {
    "abs": abs,
    "all": all,
    "any": any,
    "bool": bool,
    "dict": dict,
    "enumerate": enumerate,
    "float": float,
    "int": int,
    "len": len,
    "list": list,
    "max": max,
    "min": min,
    "range": range,
    "round": round,
    "set": set,
    "sorted": sorted,
    "str": str,
    "sum": sum,
    "tuple": tuple,
    "zip": zip,
    "ValueError": ValueError,
    "TypeError": TypeError,
    "KeyError": KeyError,
    "IndexError": IndexError,
    "AttributeError": AttributeError,
    "RuntimeError": RuntimeError,
    "ZeroDivisionError": ZeroDivisionError,
    "StopIteration": StopIteration,
}


def _validate_code(code: str) -> tuple[bool, str]:
    """Verifica sintaxe e imports permitidos."""
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return False, f"Erro de sintaxe: {e}"

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] not in ALLOWED_MODULES:
                    return False, f"Módulo não permitido: {alias.name}"
        if isinstance(node, ast.ImportFrom):
            if node.module and node.module.split(".")[0] not in ALLOWED_MODULES:
                return False, f"Módulo não permitido: {node.module}"
        if isinstance(node, ast.Name) and node.id in FORBIDDEN_NAMES:
            return False, f"Nome não permitido: {node.id}"
        if isinstance(node, ast.Attribute):
            attr = str(node.attr)
            if attr.startswith("__"):
                return False, "Acesso a atributos internos (__dunder__) não é permitido."
            if attr in FORBIDDEN_NAMES:
                return False, f"Acesso a atributo não permitido: {attr}"
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in FORBIDDEN_NAMES:
            return False, f"Função não permitida: {node.func.id}"
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr in FORBIDDEN_NAMES:
                return False, f"Chamada de método não permitida: {node.func.attr}"

    return True, ""
