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


def _get_default_model() -> str:
    try:
        from ..agent.llm_client import DEFAULT_OLLAMA_MODEL

        return DEFAULT_OLLAMA_MODEL
    except Exception:
        return "qwen2.5:7b"


DEFAULT_MODEL = _get_default_model()
