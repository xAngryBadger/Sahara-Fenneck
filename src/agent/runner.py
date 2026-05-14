"""
Loop ReAct do agente: chama o LLM com prompt + tools; interpreta resposta e executa
GetData ou Optimize; repete até resposta final. Cada Optimize gera um checkpoint.
"""
from __future__ import annotations

import json
import logging
import re
import time
from collections.abc import Callable
from functools import lru_cache

from ..checkpoints.manager import CheckpointManager
from ..errcodes import ErrCode, err_str
from ..indexing.excel_reader import (
    Workspace,
    apply_header_offset,
    get_workbook_overview,
    get_workspace_summary,
    hydrate_workspace_full,
    index_from_path,
)
from ..integrations import handle_integration_query
from .llm_client import LLMClient, create_client
from .ollama_client import OllamaClient
from .tools import structured_actions_tool

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Intent classifier — keyword check to reduce spurious [ACTIONS] on read-only queries.
# ---------------------------------------------------------------------------
_MODIFY_SIGNALS = re.compile(
    r"\b(ordena|ordene|sort|filtra|filtre|filter|preenche|preencha|renomeia|renomeie|"
    r"remove|remova|apaga|apague|deleta|delete|cria|crie|adiciona|adicione|"
    r"insere|insira|substitui|substitua|troca|troque|muda|mude|altera|altere|"
    r"duplica|duplique|duplicate|limpa|limpe|formata|formate|coloca|coloque|"
    r"nova aba|nova coluna|nova planilha|nova linha|aplica|aplique|"
    r"faz isso|execute|executa|calcule|calcula|agrupa|agrupe|"
    r"pivot|resuma|resumir|converta|converte)\b",
    re.IGNORECASE,
)


def _is_read_only_intent(query: str) -> bool:
    """Returns True when query contains no explicit modification keyword."""
    return not bool(_MODIFY_SIGNALS.search(query))


_WORKBOOK_BROAD = re.compile(
    r"\b(workbook|planilha inteira|todas as abas|resumo do arquivo|"
    r"visão geral|overview|o que tem|conteúdo|conteudo|"
    r"descreva o arquivo|descreva a planilha|resumo completo)\b",
    re.IGNORECASE,
)


def _is_workbook_broad_query(query: str, workspace: Workspace) -> bool:
    """Returns True when query is about the workbook as a whole, not a specific sheet."""
    if not workspace.path:
        return False
    if _detect_sheet_name(query, workspace):
        return False
    return bool(_WORKBOOK_BROAD.search(query))


# ---------------------------------------------------------------------------
# Sheet-name detection — "aba Vendas" => switch workspace to that sheet.
# ---------------------------------------------------------------------------
@lru_cache(maxsize=32)
def _cached_sheet_names(file_path: str) -> list[str]:
    engine = "?"
    try:
        from pathlib import Path

        import pandas as pd

        suffix = Path(file_path).suffix.lower()
        if suffix in (".xlsx", ".xlsm"):
            engine = "openpyxl"
        elif suffix == ".xls":
            engine = "xlrd"
        elif suffix == ".ods":
            engine = "odf"
        else:
            return []
        xl = pd.ExcelFile(file_path, engine=engine)
        try:
            return list(xl.sheet_names)
        finally:
            xl.close()
    except Exception:
        log.exception("Falha ao listar abas (cached, engine=%s)", engine)
        return []


def _detect_sheet_name(query: str, workspace: Workspace) -> str | None:
    m = re.search(
        r"(?:aba|planilha|sheet|guia)(?:\s+(?:chamada|nomeada|nome|de nome))?\s+['\"]?([A-Za-z\u00C0-\u00FF0-9_\- ]{1,40})['\"]?",
        query,
        re.IGNORECASE,
    )
    if not m or not workspace.path:
        return None
    candidate = m.group(1).strip()
    names = _cached_sheet_names(workspace.path)
    if not names:
        return None
    names_lower = {n.lower(): n for n in names}
    return names_lower.get(candidate.lower())


def _list_sheet_names(workspace: Workspace) -> list[str]:
    if workspace.path:
        cached = _cached_sheet_names(workspace.path)
        if cached:
            return cached

    if workspace.excel_live and workspace.excel_book_name:
        try:
            from ..com_utils import COMContext

            with COMContext() as ctx:
                wb = ctx.resolve_workbook(path=workspace.path, name=workspace.excel_book_name)
                if wb is not None:
                    return [str(s.Name) for s in wb.Worksheets]
        except Exception:
            log.exception("Falha ao listar abas via COM/Excel")

    return []


def _handle_sheet_query(query: str, workspace: Workspace) -> str | None:
    q = (query or "").lower()
    if not any(word in q for word in ("aba", "abas", "sheet", "planilha", "guia")):
        return None

    names = _list_sheet_names(workspace)
    if not names:
        return None

    target = _detect_sheet_name(query, workspace)
    names_lower = {n.lower(): n for n in names}

    if any(word in q for word in ("quais", "listar", "liste", "nomes", "quantas")):
        return f"Este arquivo possui {len(names)} aba(s): {', '.join(names)}."

    if target and any(word in q for word in ("existe", "tem", "há", "ha")):
        if target.lower() in names_lower:
            return f"Sim. Existe uma aba chamada '{names_lower[target.lower()]}' neste arquivo."
        return f"Não. As abas disponíveis são: {', '.join(names)}."

    if "duas abas" in q or "2 abas" in q or "todas as abas" in q:
        return f"Este arquivo tem {len(names)} aba(s): {', '.join(names)}. Posso trabalhar em uma aba por vez, mas consigo alternar para qualquer uma delas quando você citar o nome exato."

    return None


def _switch_workspace_to_sheet(query: str, workspace: Workspace) -> Workspace:
    """If user references a different sheet by name, switch context to it."""
    target = _detect_sheet_name(query, workspace)
    if target and target != workspace.sheet_name and workspace.path:
        try:
            alt = index_from_path(workspace.path, sheet_name=target)
            if not alt.error:
                return alt
        except Exception:
            log.exception("Falha ao trocar contexto para aba alternativa")
    return workspace


SYSTEM = """Você é o Fennec, assistente de planilhas Excel. Responda SEMPRE em português.

IMPORTANTE: Use blocos de ferramenta SOMENTE quando o usuário pedir para MODIFICAR a planilha.
Para perguntas, análises, cálculos ou conversa, responda apenas em texto — sem [ACTIONS] nem [OPTIMIZE].
Exemplos que NÃO precisam de ferramenta: "o que é X?", "quantos registros?", "mostre o resumo", "qual a soma de Y?".

Para aplicar mudanças, use:
[ACTIONS]
{"actions": [{"action": "NOME", ...parâmetros...}]}
[/ACTIONS]

Ações disponíveis:
- sort: {"action":"sort","by":["Coluna"],"ascending":true}
- fillna: {"action":"fillna","column":"Col","value":0}
- replace: {"action":"replace","column":"Col","from":"X","to":"Y"}
- rename_column: {"action":"rename_column","from":"Antigo","to":"Novo"}
- drop_columns: {"action":"drop_columns","columns":["Col1"]}
- add_computed_column: {"action":"add_computed_column","new_column":"Total","operation":"sum","source_columns":["A","B"]}
- filter_equals: {"action":"filter_equals","column":"Col","value":"X"}
- filter_contains: {"action":"filter_contains","column":"Col","value":"texto","case_sensitive":false}
- filter_range: {"action":"filter_range","column":"Col","min":10,"max":100}
- dropna: {"action":"dropna","columns":["Col1"],"how":"any"} ou {"action":"dropna"} (todas as colunas)
- groupby_agg: {"action":"groupby_agg","group_by":["Categoria"],"agg_column":"Valor","agg_func":"sum"}
- pivot_table: {"action":"pivot_table","index":["Cat"],"columns":["Ano"],"values":"Vendas","agg_func":"sum"}
- merge_columns: {"action":"merge_columns","columns":["Nome","Sobrenome"],"new_column":"Nome Completo","separator":" "}
- strip_whitespace: {"action":"strip_whitespace","columns":["Col1"]} ou {"action":"strip_whitespace"} (todas as colunas texto)
- change_dtype: {"action":"change_dtype","column":"CEP","dtype":"str"} (tipos: int, float, str, bool, datetime)
- duplicate_sheet: {"action":"duplicate_sheet","name":"Nome da nova aba"}
- create_sheet: {"action":"create_sheet","name":"Nome da nova aba"}
- delete_sheet: {"action":"delete_sheet","name":"Nome da aba a excluir"}
- rename_sheet: {"action":"rename_sheet","from":"NomeAtual","to":"NomeNovo"}

Use os nomes exatos das colunas fornecidas. Nunca invente colunas. Apenas uma ferramenta por resposta."""


def _extract_optimize(code_text: str) -> str | None:
    m = re.search(r"\[OPTIMIZE\]\s*(.*?)\s*\[/OPTIMIZE\]", code_text, re.DOTALL | re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return None


def _extract_actions(code_text: str) -> str | None:
    m = re.search(r"\[ACTIONS\]\s*(.*?)\s*\[/ACTIONS\]", code_text, re.DOTALL | re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return None


_KNOWN_ACTION_KINDS = {
    "sort", "fillna", "replace", "rename_column", "drop_columns",
    "add_computed_column", "filter_equals", "filter_contains", "filter_range",
    "dropna", "groupby_agg", "pivot_table", "merge_columns", "strip_whitespace",
    "change_dtype", "adjust_header", "request_more_rows",
    "duplicate_sheet", "create_sheet", "delete_sheet", "rename_sheet",
}


def _extract_loose_actions(code_text: str) -> str | None:
    """Accept raw/fenced JSON when smaller models forget [ACTIONS] tags."""
    text = (code_text or "").strip()
    if not text:
        return None

    candidates = [text]

    fence = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
    if fence:
        candidates.append(fence.group(1).strip())

    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace != -1 and last_brace > first_brace:
        candidates.append(text[first_brace:last_brace + 1].strip())

    first_bracket = text.find("[")
    last_bracket = text.rfind("]")
    if first_bracket != -1 and last_bracket > first_bracket:
        candidates.append(text[first_bracket:last_bracket + 1].strip())

    seen: set[str] = set()
    for candidate in candidates:
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        try:
            raw = json.loads(candidate)
        except Exception:
            log.debug("Falha ao analisar JSON de acoes soltas")
            continue

        if isinstance(raw, dict) and isinstance(raw.get("actions"), list) and raw.get("actions"):
            actions = raw["actions"]
            if any(str(a.get("action", "")).strip().lower() in _KNOWN_ACTION_KINDS for a in actions if isinstance(a, dict)):
                return candidate
        if isinstance(raw, list) and raw and all(isinstance(a, dict) and a.get("action") for a in raw):
            if any(str(a.get("action", "")).strip().lower() in _KNOWN_ACTION_KINDS for a in raw):
                return candidate

    return None


def _strip_tool_payload_from_response(response: str, payload: str, tool_name: str) -> str:
    """Removes tool payload from visible text, supporting tagged or raw JSON/code output."""
    text = response or ""

    if f"[{tool_name}]" in text:
        base = text.split(f"[{tool_name}]", 1)[0]
        return re.sub(r"\[/?(?:ACTIONS|OPTIMIZE)\]", "", base).strip()

    stripped = text
    if payload:
        stripped = stripped.replace(payload, "")
    stripped = re.sub(r"```(?:json)?\s*```", "", stripped, flags=re.DOTALL | re.IGNORECASE)
    stripped = re.sub(r"```(?:json)?\s*", "", stripped, flags=re.IGNORECASE)
    stripped = stripped.replace("```", "")
    return stripped.strip()


def _summarize_actions(actions_payload: str, workspace: Workspace) -> str:
    try:
        raw = json.loads(actions_payload)
        actions = raw.get("actions", []) if isinstance(raw, dict) else raw
    except Exception:
        log.exception("Falha ao analisar JSON do bloco ACTIONS para resumo")
        return (
            f"A planilha `{workspace.workbook_name}` / aba `{workspace.sheet_name}` sera alterada.\n\n"
            "Nao foi possivel montar a previa detalhada das acoes, mas o agente tentou executar um bloco [ACTIONS]."
        )

    if not isinstance(actions, list):
        actions = []

    lines = [
        f"Planilha: {workspace.workbook_name or workspace.path}",
        f"Aba ativa: {workspace.sheet_name}",
        "",
        "Acoes propostas:",
    ]

    labels = {
        "sort": "Ordenar linhas",
        "fillna": "Preencher valores vazios",
        "replace": "Substituir valores",
        "rename_column": "Renomear coluna",
        "drop_columns": "Remover colunas",
        "add_computed_column": "Criar coluna calculada",
        "filter_equals": "Filtrar linhas por valor exato",
        "filter_contains": "Filtrar linhas por texto",
        "filter_range": "Filtrar linhas por intervalo",
        "dropna": "Remover linhas com valores vazios",
        "groupby_agg": "Agrupar e agregar",
        "pivot_table": "Tabela dinâmica",
        "merge_columns": "Mesclar colunas",
        "strip_whitespace": "Remover espaços extras",
        "change_dtype": "Alterar tipo de dados",
        "duplicate_sheet": "Duplicar aba",
        "create_sheet": "Criar nova aba",
        "delete_sheet": "Excluir aba",
        "rename_sheet": "Renomear aba",
    }

    for idx, action in enumerate(actions, 1):
        if not isinstance(action, dict):
            lines.append(f"{idx}. Acao invalida recebida do modelo")
            continue
        kind = str(action.get("action", "")).strip().lower()
        title = labels.get(kind, kind or "acao")
        details = []
        for key, value in action.items():
            if key == "action":
                continue
            details.append(f"{key}={value}")
        suffix = f" ({', '.join(details)})" if details else ""
        lines.append(f"{idx}. {title}{suffix}")

    lines.append("")
    lines.append("Ao confirmar, o Fennec criara um checkpoint antes da primeira alteracao.")
    return "\n".join(lines)


def run_agent(
    query: str,
    workspace: Workspace,
    client: LLMClient | None = None,
    settings: dict | None = None,
    on_message: Callable[[str], None] | None = None,
    on_checkpoint: Callable[[str], None] | None = None,
    on_confirm_change: Callable[[str], bool] | None = None,
    on_progress: Callable[[str], None] | None = None,
    max_steps: int = 5,
) -> str:
    """
    Executa o agente: envia a query ao LLM, interpreta ACTIONS/Optimize,
    executa tools (com checkpoint antes da primeira alteração) e retorna a resposta final.
    """
    direct_sheet_reply = _handle_sheet_query(query, workspace)
    if direct_sheet_reply is not None:
        if on_message:
            on_message(direct_sheet_reply)
        return direct_sheet_reply

    if _is_read_only_intent(query) and not workspace.error:
        t0 = time.monotonic()
        switched = _switch_workspace_to_sheet(query, workspace)
        if switched is not workspace:
            workspace.sheet_name = switched.sheet_name
            workspace.df = switched.df
            workspace.columns = switched.columns
            workspace.row_count = switched.row_count
            workspace.indexed_rows = switched.indexed_rows
            workspace.truncated = switched.truncated
            workspace = switched
        client = client or (create_client(settings) if settings else OllamaClient())
        if client.is_available():
            context_parts: list[str] = []
            if _is_workbook_broad_query(query, workspace):
                overview = get_workbook_overview(workspace.path)
                context_parts.append(overview)
            data_summary = get_workspace_summary(workspace)
            context_parts.append(f"Dados da aba ativa:\n{data_summary}")
            context_text = "\n\n".join(context_parts)
            ro_prompt = f"{context_text}\n\nPergunta do usuário: {query}\n\nResponda e, se for aplicar alterações na planilha, prefira [ACTIONS]...[/ACTIONS].\nUse [OPTIMIZE] apenas se a tarefa não puder ser representada pelas ações estruturadas."
            try:
                response = client.generate(ro_prompt, system=SYSTEM)
            except RuntimeError as e:
                final_answer = str(e)
                if on_message:
                    on_message(final_answer)
                return final_answer
            log.info("[perf] read-only path: %.2fs", time.monotonic() - t0)
            actions_payload = _extract_actions(response) or _extract_loose_actions(response)
            if actions_payload:
                cp = CheckpointManager(workspace.path, interaction_label="Otimização")
                result = structured_actions_tool(
                    workspace, actions_payload, cp, save_checkpoint=False,
                )
                if result.success:
                    clean_text = _strip_tool_payload_from_response(response, actions_payload, "ACTIONS")
                    final_answer = (clean_text + "\n\n" + result.message).strip()
                    if on_message:
                        on_message(final_answer)
                    return final_answer
            clean = re.sub(r"\[/?(?:ACTIONS|OPTIMIZE)\]", "", response).strip()
            if clean:
                if on_message:
                    on_message(clean)
                return clean

    if workspace.error:
        msg = err_str(ErrCode.WORKSPACE_ERROR, workspace.error or "")
        if on_message:
            on_message(msg)
        return msg

    t_start = time.monotonic()

    refreshed = hydrate_workspace_full(workspace)
    t_hydrate = time.monotonic() - t_start
    if refreshed is not workspace and not refreshed.error:
        workspace.df = refreshed.df
        workspace.columns = refreshed.columns
        workspace.row_count = refreshed.row_count
        workspace.indexed_rows = refreshed.indexed_rows
        workspace.truncated = refreshed.truncated
        workspace = refreshed

    switched = _switch_workspace_to_sheet(query, workspace)
    if switched is not workspace:
        workspace.sheet_name = switched.sheet_name
        workspace.df = switched.df
        workspace.columns = switched.columns
        workspace.row_count = switched.row_count
        workspace.indexed_rows = switched.indexed_rows
        workspace.truncated = switched.truncated
        workspace = switched

    client = client or OllamaClient()
    if not client.is_available():
        if not _MODIFY_SIGNALS.search(query):
            integration_reply = handle_integration_query(query, workspace)
            if integration_reply is not None:
                if on_message:
                    on_message(integration_reply)
                return integration_reply
        msg = err_str(ErrCode.OLLAMA_UNAVAILABLE, "Verifique se o Ollama está instalado e tente abrir o Fennec novamente.")
        if on_message:
            on_message(msg)
        return msg

    cp = CheckpointManager(workspace.path, interaction_label="Otimização")

    context_block = ""
    if _is_workbook_broad_query(query, workspace):
        overview = get_workbook_overview(workspace.path)
        context_block = overview + "\n\n"
    data_summary = get_workspace_summary(workspace)
    prompt = f"""{context_block}Dados atuais da aba ativa:
{data_summary}

Pergunta do usuário: {query}

Responda e, se for aplicar alterações na planilha, prefira [ACTIONS]...[/ACTIONS].
Use [OPTIMIZE] apenas se a tarefa não puder ser representada pelas ações estruturadas."""

    messages = [prompt]
    final_answer = ""
    checkpoint_saved_for_order = False
    t_llm_elapsed = 0.0
    t_tool_elapsed = 0.0
    last_step = 0

    for step in range(max_steps):
        last_step = step
        if on_progress:
            on_progress(f"Pensando... etapa {step + 1}/{max_steps}")
        t_llm = time.monotonic()
        try:
            response = client.generate("\n\n".join(messages), system=SYSTEM)
        except RuntimeError as e:
            final_answer = str(e)
            if on_message:
                on_message(final_answer)
            break
        t_llm_elapsed = time.monotonic() - t_llm

        actions_payload = _extract_actions(response) or _extract_loose_actions(response)
        if actions_payload:
            # Validate actions payload before showing confirmation
            try:
                _raw = json.loads(actions_payload)
                _acts = _raw.get("actions", []) if isinstance(_raw, dict) else _raw
                if isinstance(_acts, list) and not _acts:
                    # Empty actions list — skip confirmation and tell user
                    if on_message:
                        on_message("O modelo não gerou ações válidas. Tente reformular seu pedido.")
                    messages.append(response)
                    messages.append("Resultado: A lista de ações estava vazia. Gere ações válidas.")
                    continue
            except Exception:
                log.exception("Falha ao validar lista de acoes")
                pass

            if on_confirm_change:
                preview = _summarize_actions(actions_payload, workspace)
                approved = on_confirm_change(preview)
                if not approved:
                    final_answer = "Operacao cancelada. Nenhuma alteracao foi aplicada na planilha."
                    if on_message:
                        on_message(final_answer)
                    break

            save_checkpoint_now = not checkpoint_saved_for_order
            if on_progress:
                on_progress("Aplicando alterações na planilha...")
            t_tool = time.monotonic()
            result = structured_actions_tool(
                workspace,
                actions_payload,
                cp,
                on_checkpoint_saved=on_checkpoint if save_checkpoint_now else None,
                save_checkpoint=save_checkpoint_now,
            )
            t_tool_elapsed = time.monotonic() - t_tool
            if save_checkpoint_now and result.success:
                checkpoint_saved_for_order = True

            if result.success:
                _cached_sheet_names.cache_clear()
                if result.message == "__REQUEST_MORE_ROWS__":
                    if on_progress:
                        on_progress("Carregando mais dados...")
                    refreshed = hydrate_workspace_full(workspace)
                    if refreshed is not workspace and not refreshed.error:
                        workspace.df = refreshed.df
                        workspace.row_count = refreshed.row_count
                        workspace.indexed_rows = refreshed.indexed_rows
                        workspace.truncated = refreshed.truncated
                    data_summary = get_workspace_summary(workspace)
                    messages.append(response)
                    messages.append(f"Mais dados carregados. Dados atuais:\n{data_summary}\nResponda novamente com base nos dados completos.")
                    continue

                if result.message.startswith("__ADJUST_HEADER__"):
                    try:
                        offset = int(result.message.split("__ADJUST_HEADER__")[1])
                    except (ValueError, IndexError):
                        offset = 0
                    if offset > 0:
                        workspace = apply_header_offset(workspace, offset)
                    data_summary = get_workspace_summary(workspace)
                    messages.append(response)
                    messages.append(f"Cabeçalho ajustado para linha {offset + 1}. Novos dados:\n{data_summary}\nResponda novamente com os cabeçalhos corrigidos.")
                    continue

                clean_text = _strip_tool_payload_from_response(response, actions_payload, "ACTIONS")
                final_answer = (clean_text + "\n\n" + result.message).strip()
                if on_message:
                    on_message(final_answer)
                break

            # Tool failed — let LLM retry with the error
            if on_message:
                on_message(f"Não foi possível aplicar: {result.message}")
            messages.append(response)
            messages.append(f"Resultado da ferramenta ACTIONS: {result.message}")
            continue

        code = _extract_optimize(response)
        if code:
            final_answer = err_str(
                ErrCode.OPTIMIZE_DEPRECATED,
                "A ferramenta [OPTIMIZE] foi removida por questões de segurança (exec()). "
                "Por favor, reformule a operação usando [ACTIONS] com ações declarativas "
                "(sort, fillna, replace, rename_column, drop_columns, add_computed_column, "
                "filter_equals, dropna, groupby_agg, etc.).",
            )
            if on_message:
                on_message(final_answer)
            break

        # No tool block: this is the final answer
        final_answer = response
        if on_message:
            on_message(response)
        break

    if not final_answer:
        final_answer = "Nenhuma resposta gerada."
        if on_message:
            on_message(final_answer)

    log.info(
        "[perf] run_agent total=%.2fs hydrate=%.2fs llm=%.2fs tool=%.2fs step=%d",
        time.monotonic() - t_start, t_hydrate, t_llm_elapsed, t_tool_elapsed, last_step,
    )

    return final_answer
