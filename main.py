# -*- coding: utf-8 -*-
"""Sahara Fennec – Agente de Planilhas
Entrypoint: inicia a janela de chat com persona Fennec.
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.logging_config import setup_logging


def main():
    parser = argparse.ArgumentParser(description="Sahara Fennec – Agente de Planilhas")
    parser.add_argument("--cli", nargs="?", const="__no_file__", default=None, metavar="FILE",
                        help="Modo CLI interativo. Opcionalmente passe um arquivo .xlsx para abrir.")
    parser.add_argument("--smoke-test", action="store_true",
                        help="Valida imports e sai (usado pelo instalador magro)")
    args = parser.parse_args()

    setup_logging()

    if args.smoke_test:
        sys.exit(0)

    if args.cli is not None:
        from src.cli.repl import FennecREPL

        initial_file = None if args.cli == "__no_file__" else args.cli
        repl = FennecREPL(initial_file=initial_file)
        repl.run()
        return

    from src.persona.persona_config import get_persona
    from src.gui.main_window import MainWindow

    persona = get_persona("fennec")
    app = MainWindow(persona)
    app.run()


if __name__ == "__main__":
    main()
