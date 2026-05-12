"""Fennec Excel CLI — interactive REPL for headless usage.

Usage:
    python main.py --cli [file.xlsx]

Commands:
    /load <path>      Index an Excel file
    /sheet <name>     Switch to a different sheet
    /summary          Show current workspace summary
    /checkpoints      List saved checkpoints
    /undo             Restore most recent checkpoint
    /backend <name>   Switch LLM backend (nim / ollama)
    /model <name>     Change model name
    /help             Show available commands
    /quit             Exit

Any other input is sent to run_agent() as a natural-language query.
"""
from __future__ import annotations

from pathlib import Path

from ..agent.llm_client import create_client
from ..agent.runner import run_agent
from ..checkpoints.manager import CheckpointManager
from ..config.app_settings import load_settings, save_settings
from ..indexing.excel_reader import Workspace, get_workspace_summary, index_from_path

_BOLD = "\033[1m"
_DIM = "\033[2m"
_RED = "\033[31m"
_GREEN = "\033[32m"
_YELLOW = "\033[33m"
_CYAN = "\033[36m"
_RESET = "\033[0m"

_BANNER = f"""{_CYAN}{_BOLD}🦊 Fennec Excel — CLI Mode{_RESET}
Type natural language to query/modify your spreadsheet.
Use /help for commands, /quit to exit."""


def _fmt_workspace(ws: Workspace) -> str:
    if ws.error:
        return f"{_RED}Error: {ws.error}{_RESET}"
    name = ws.workbook_name or Path(ws.path).name
    lines = [
        f"{_BOLD}{name}{_RESET}  aba={ws.sheet_name}  "
        f"cols={len(ws.columns)}  rows={ws.indexed_rows}/{ws.row_count}"
        + (" (amostra)" if ws.truncated else "")
    ]
    if ws.columns:
        lines.append(f"  Colunas: {', '.join(ws.columns[:15])}" + ("..." if len(ws.columns) > 15 else ""))
    return "\n".join(lines)


class FennecREPL:
    def __init__(self, initial_file: str | None = None) -> None:
        self.workspace: Workspace | None = None
        self.settings = load_settings()
        self._messages: list[str] = []

        if initial_file:
            self._cmd_load(initial_file)

    def _current_client(self):
        return create_client(self.settings)

    def _on_message(self, text: str) -> None:
        self._messages.append(text)

    def _on_confirm_change(self, preview: str) -> bool:
        print(f"\n{_YELLOW}--- Alteração proposta ---{_RESET}")
        print(preview)
        print()
        while True:
            answer = input(f"{_YELLOW}Aplicar? [s/N]: {_RESET}").strip().lower()
            if answer in ("s", "sim", "y", "yes"):
                return True
            if answer in ("n", "no", "nao", "não", ""):
                print(f"{_DIM}Operação cancelada.{_RESET}")
                return False
            print("  Responda s ou n")

    def _on_checkpoint(self, label: str) -> None:
        print(f"{_DIM}  Checkpoint salvo: {label}{_RESET}")

    def _cmd_load(self, path: str) -> None:
        from ..indexing.excel_reader import is_excel_file

        p = Path(path).expanduser().resolve()
        if not p.exists():
            print(f"{_RED}Arquivo não encontrado: {p}{_RESET}")
            return
        if not is_excel_file(str(p)):
            print(f"{_RED}Formato não suportado: {p.suffix} (use .xlsx, .xlsm, .xls ou .ods){_RESET}")
            return
        print(f"{_DIM}Indexando {p.name}...{_RESET}")
        ws = index_from_path(str(p))
        self.workspace = ws
        print(_fmt_workspace(ws))

    def _cmd_sheet(self, name: str) -> None:
        if not self.workspace or not self.workspace.path:
            print(f"{_RED}Nenhuma planilha carregada. Use /load <caminho>{_RESET}")
            return
        ws = index_from_path(self.workspace.path, sheet_name=name)
        if ws.error:
            print(f"{_RED}Erro ao trocar para aba '{name}': {ws.error}{_RESET}")
            return
        self.workspace = ws
        print(_fmt_workspace(ws))

    def _cmd_summary(self) -> None:
        if not self.workspace:
            print(f"{_RED}Nenhuma planilha carregada.{_RESET}")
            return
        print(get_workspace_summary(self.workspace))

    def _cmd_checkpoints(self) -> None:
        if not self.workspace or not self.workspace.path:
            print(f"{_RED}Nenhuma planilha carregada.{_RESET}")
            return
        cp = CheckpointManager(self.workspace.path)
        checkpoints = cp.list_checkpoints()
        if not checkpoints:
            print(f"{_DIM}Nenhum checkpoint salvo.{_RESET}")
            return
        for i, c in enumerate(checkpoints, 1):
            print(f"  {i}. {c.label}  ({c.timestamp})")

    def _cmd_undo(self) -> None:
        if not self.workspace or not self.workspace.path:
            print(f"{_RED}Nenhuma planilha carregada.{_RESET}")
            return
        cp = CheckpointManager(self.workspace.path)
        checkpoints = cp.list_checkpoints()
        if not checkpoints:
            print(f"{_DIM}Nenhum checkpoint para restaurar.{_RESET}")
            return
        last = checkpoints[-1]
        if cp.restore(last.path):
            print(f"{_GREEN}Restaurado: {last.label}{_RESET}")
            self.workspace = index_from_path(self.workspace.path, sheet_name=self.workspace.sheet_name)
            print(_fmt_workspace(self.workspace))
        else:
            print(f"{_RED}Falha ao restaurar checkpoint.{_RESET}")

    def _cmd_backend(self, name: str) -> None:
        name = name.strip().lower()
        if name not in ("nim", "ollama"):
            print(f"{_RED}Backend desconhecido: {name}. Use 'nim' ou 'ollama'.{_RESET}")
            return
        self.settings["llm_backend"] = name
        save_settings(self.settings)
        print(f"Backend alterado para {_BOLD}{name}{_RESET}")

    def _cmd_model(self, name: str) -> None:
        name = name.strip()
        if not name:
            print(f"{_RED}Uso: /model <nome_do_modelo>{_RESET}")
            return
        backend = self.settings.get("llm_backend", "ollama")
        if backend == "nim":
            self.settings["nim_model"] = name
        else:
            self.settings["model"] = name
        save_settings(self.settings)
        print(f"Modelo alterado para {_BOLD}{name}{_RESET}")

    def _cmd_help(self) -> None:
        print(f"""{_CYAN}Comandos disponíveis:{_RESET}
  /load <caminho>    Carregar arquivo Excel
  /sheet <nome>      Trocar para outra aba
  /summary           Resumo da planilha atual
  /checkpoints       Listar checkpoints salvos
  /undo              Restaurar último checkpoint
  /backend <nome>    Trocar backend LLM (nim / ollama)
  /model <nome>      Trocar modelo LLM
  /help              Mostrar esta ajuda
  /quit              Sair

Qualquer outro texto é enviado como pergunta ao agente Fennec.""")

    def _handle_command(self, line: str) -> bool:
        parts = line.split(maxsplit=1)
        cmd = parts[0].lower()
        arg = parts[1].strip() if len(parts) > 1 else ""

        if cmd == "/quit":
            return False
        if cmd == "/load":
            self._cmd_load(arg)
        elif cmd == "/sheet":
            self._cmd_sheet(arg)
        elif cmd == "/summary":
            self._cmd_summary()
        elif cmd == "/checkpoints":
            self._cmd_checkpoints()
        elif cmd == "/undo":
            self._cmd_undo()
        elif cmd == "/backend":
            self._cmd_backend(arg)
        elif cmd == "/model":
            self._cmd_model(arg)
        elif cmd == "/help":
            self._cmd_help()
        else:
            print(f"{_RED}Comando desconhecido: {cmd}. Use /help para ver os disponíveis.{_RESET}")
        return True

    def _handle_query(self, query: str) -> None:
        if not self.workspace:
            print(f"{_RED}Nenhuma planilha carregada. Use /load <caminho>{_RESET}")
            return
        client = self._current_client()
        self._messages.clear()
        print(f"{_DIM}Processando...{_RESET}", end="", flush=True)

        def _on_progress(status: str):
            print(f"\r{_DIM}{status}{_RESET}", end="", flush=True)

        result = run_agent(
            query=query,
            workspace=self.workspace,
            client=client,
            on_message=self._on_message,
            on_checkpoint=self._on_checkpoint,
            on_confirm_change=self._on_confirm_change,
            on_progress=_on_progress,
        )

        print(f"\r{' ' * 20}\r", end="")
        for msg in self._messages:
            print(msg)
        if not self._messages:
            print(result)

    def run(self) -> None:
        print(_BANNER)
        backend = self.settings.get("llm_backend", "ollama")
        model = self.settings.get("nim_model" if backend == "nim" else "model", "")
        print(f"{_DIM}Backend: {backend} | Modelo: {model}{_RESET}")
        if self.workspace:
            print(_fmt_workspace(self.workspace))
        print()

        while True:
            try:
                line = input(f"{_BOLD}fennec> {_RESET}").strip()
            except (EOFError, KeyboardInterrupt):
                print(f"\n{_DIM}Até logo!{_RESET}")
                break

            if not line:
                continue

            if line.startswith("/"):
                if not self._handle_command(line):
                    break
            else:
                self._handle_query(line)
