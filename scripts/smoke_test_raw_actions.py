from pathlib import Path
import sys
import tempfile
import openpyxl
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.indexing.excel_reader import index_from_path
from src.agent.runner import run_agent


def assert_true(cond, msg):
    if not cond:
        raise AssertionError(msg)


def make_file(path: Path):
    wb = openpyxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = "Dados"
    ws.append(["Col2", "Col3"])
    ws.append([None, None])
    wb.save(path)


class FakeOllamaRawActions:
    def is_available(self):
        return True

    def generate(self, prompt: str, system: str | None = None, max_tokens: int = 2048):
        return (
            'Vou preencher as celulas em branco.\n\n'
            '{"actions": ['
            '{"action": "fillna", "column": "Col2", "value": 0}, '
            '{"action": "fillna", "column": "Col3", "value": 0}'
            ']}'
        )


with tempfile.TemporaryDirectory() as tmp:
    xlsx = Path(tmp) / "raw_actions.xlsx"
    make_file(xlsx)
    ws = index_from_path(str(xlsx))
    msgs = []

    out = run_agent(
        "preencha as celulas em branco com 0",
        ws,
        ollama=FakeOllamaRawActions(),  # type: ignore[arg-type]
        on_message=lambda m: msgs.append(m),
        on_confirm_change=lambda preview: True,
    )

    wb = openpyxl.load_workbook(xlsx, data_only=True)
    ws2 = wb["Dados"]
    values = [c.value for c in ws2[2]]
    wb.close()

    assert_true(values == [0, 0], f"alteracao nao aplicada: {values}")
    assert_true("sucesso" in out.lower(), "saida final inesperada")
    assert_true(all('"actions"' not in m for m in msgs), "payload cru vazou para o usuario")

print("SMOKE_RAW_ACTIONS_OK")
