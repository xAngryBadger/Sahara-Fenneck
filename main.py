# -*- coding: utf-8 -*-
"""
Sahara Fennec – Agente de Planilhas
Entrypoint: inicia a janela de chat com persona Fennec.
"""
import sys
from pathlib import Path

# Garante que a raiz do projeto está no path
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.persona.persona_config import get_persona
from src.gui.main_window import MainWindow


def main():
    persona = get_persona("fennec")
    app = MainWindow(persona)
    app.run()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--smoke-test":
        # Smoke test: imports já rodaram; só confirma que o app carrega (usado pelo script de validação do instalador magro)
        sys.exit(0)
    main()
