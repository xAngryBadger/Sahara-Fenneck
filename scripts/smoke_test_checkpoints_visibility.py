from pathlib import Path
import sys
import tempfile
import openpyxl

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.indexing.excel_reader import index_from_path
from src.checkpoints.manager import CheckpointManager


def assert_true(cond, msg):
    if not cond:
        raise AssertionError(msg)


def make_file(path: Path):
    wb = openpyxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = "Dados"
    ws.append(["Valor"])
    ws.append([1])
    wb.save(path)


with tempfile.TemporaryDirectory() as tmp:
    xlsx = Path(tmp) / "CaseTest.xlsx"
    make_file(xlsx)
    ws = index_from_path(str(xlsx))

    cp1 = CheckpointManager(str(xlsx))
    info = cp1.save_checkpoint(ws, label="Teste")
    assert_true(Path(info.path).exists(), "checkpoint nao foi criado")

    cp2 = CheckpointManager(str(xlsx).upper())
    cps = cp2.list_checkpoints()
    assert_true(len(cps) >= 1, "checkpoint nao apareceu com variacao de case no path")

print("SMOKE_CHECKPOINTS_VISIBILITY_OK")
