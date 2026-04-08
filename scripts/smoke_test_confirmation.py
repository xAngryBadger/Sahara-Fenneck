from pathlib import Path
import sys
import tempfile
import openpyxl

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
    ws.title = "Vendas"
    ws.append(["Valor"])
    ws.append([10])
    wb.save(path)


class FakeOllamaActions:
    def is_available(self):
        return True

    def generate(self, prompt: str, system: str = None, max_tokens: int = 2048):
        return (
            "Vou aplicar a alteração.\n"
            "[ACTIONS]\n"
            '{"actions":[{"action":"add_computed_column","new_column":"Triplo","operation":"multiply","source_columns":["Valor","Valor","Valor"]}]}'
            "\n[/ACTIONS]"
        )


with tempfile.TemporaryDirectory() as tmp:
    xlsx = Path(tmp) / "confirm.xlsx"
    make_file(xlsx)
    ws = index_from_path(str(xlsx))
    previews = []
    msgs = []

    out = run_agent(
        "crie a coluna triplo",
        ws,
        ollama=FakeOllamaActions(),
        on_message=lambda m: msgs.append(m),
        on_confirm_change=lambda preview: previews.append(preview) or False,
    )

    wb = openpyxl.load_workbook(xlsx, data_only=True)
    headers = [c.value for c in wb["Vendas"][1]]
    wb.close()

    assert_true(len(previews) == 1, "preview nao foi exibido")
    assert_true("Triplo" in previews[0], "preview nao descreveu a alteracao esperada")
    assert_true("Triplo" not in headers, "alteracao foi aplicada mesmo apos cancelamento")
    assert_true("cancelada" in out.lower(), "mensagem final deveria indicar cancelamento")

print("SMOKE_CONFIRMATION_OK")
