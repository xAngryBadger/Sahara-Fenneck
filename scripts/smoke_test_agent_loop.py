from pathlib import Path
import sys
import tempfile
import json
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
    ws.append(["Valor"])
    ws.append([10])
    wb.save(path)


class FakeOllama:
    def __init__(self):
        self.n = 0

    def is_available(self):
        return True

    def generate(self, prompt: str, system: str = None, max_tokens: int = 2048):
        self.n += 1
        if self.n == 1:
            return "Vou aplicar uma otimização.\n[OPTIMIZE]\ndf['Valor2'] = df['Valor'] * 3\n[/OPTIMIZE]"
        return "Concluído: coluna Valor2 criada com sucesso."


with tempfile.TemporaryDirectory() as tmp:
    xlsx = Path(tmp) / "agent.xlsx"
    make_file(xlsx)
    ws = index_from_path(str(xlsx))
    msgs = []
    cps = []
    out = run_agent(
        "crie coluna triplo",
        ws,
        ollama=FakeOllama(),
        on_message=lambda m: msgs.append(m),
        on_checkpoint=lambda c: cps.append(c),
    )

    wb = openpyxl.load_workbook(xlsx, data_only=True)
    headers = [c.value for c in wb.active[1]]
    wb.close()

    ck_dir = xlsx.parent / "_fennec_checkpoints"
    idx = ck_dir / "index.json"
    assert_true("Valor2" in headers, "agente nao aplicou alteracao no arquivo")
    assert_true(len(cps) >= 1, "agente nao reportou checkpoint")
    assert_true(idx.exists(), "index de checkpoint nao foi criado")
    assert_true("sucesso" in out.lower(), "saida final inesperada")

print("SMOKE_AGENT_LOOP_OK")
