"""
Constantes compartilhadas do GUI (versao, modelo padrao).
"""
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def _read_version() -> str:
    try:
        import importlib.metadata

        return importlib.metadata.version("sahara-fennec")
    except Exception:
        toml = _PROJECT_ROOT / "pyproject.toml"
        if toml.exists():
            for line in toml.read_text(encoding="utf-8").splitlines():
                if line.startswith("version"):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
        return "2.0"


APP_VERSION = _read_version()
DEFAULT_MODEL = "qwen2.5:7b"
