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
    ws1 = wb.active
    assert ws1 is not None
    ws1.title = "Parcela-01"
    ws1.append(["A"])
    ws1.append([1])
    ws2 = wb.create_sheet(title="Espécies")
    ws2.append(["B"])
    ws2.append([2])
    wb.save(path)


class FailIfCalledOllama:
    def is_available(self):
        raise AssertionError("Ollama nao deveria ser chamado para consulta direta de abas")


with tempfile.TemporaryDirectory() as tmp:
    xlsx = Path(tmp) / "abas.xlsx"
    make_file(xlsx)
    ws = index_from_path(str(xlsx), sheet_name="Parcela-01")
    msgs = []

    out = run_agent(
        "Existe outra aba chamada Espécies?",
        ws,
        ollama=FailIfCalledOllama(),  # type: ignore[arg-type]
        on_message=lambda m: msgs.append(m),
    )

    assert_true("espécies" in out.lower() or "especies" in out.lower(), f"resposta inesperada: {out}")
    assert_true("sim" in out.lower(), f"deveria confirmar a aba existente: {out}")
    assert_true(len(msgs) == 1, "deveria retornar uma unica resposta direta")

print("SMOKE_SHEET_QUERIES_OK")
