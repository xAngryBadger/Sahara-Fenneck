from __future__ import annotations

from enum import StrEnum


class ErrCode(StrEnum):
    CHECKPOINT_SAVE = "E001"
    CHECKPOINT_RESTORE = "E002"
    PARSE_ACTIONS = "E003"
    SANDBOX_VIOLATION = "E004"
    OPTIMIZE_DEPRECATED = "E005"
    EXCEL_NOT_FOUND = "E006"
    EXCEL_WRITE_COM = "E007"
    EXCEL_SAVE_OPENPYXL = "E008"
    EXCEL_SAVE_DF = "E009"
    COLUMN_MISSING = "E010"
    ACTION_INVALID = "E011"
    ACTION_UNKNOWN = "E012"
    OAUTH_STATE_MISMATCH = "E013"
    FILE_NOT_FOUND = "E014"
    FILE_INVALID_FORMAT = "E015"
    SHEET_EMPTY = "E016"
    INDEX_FAILED = "E017"
    OLLAMA_UNAVAILABLE = "E018"
    WORKSPACE_ERROR = "E019"
    ENCRYPTION_FAILED = "E020"
    OAUTH_UNAVAILABLE = "E021"
    NIM_UNAVAILABLE = "E022"
    NIM_AUTH_FAILED = "E023"
    NIM_REQUEST_FAILED = "E024"


ERR_MESSAGES: dict[ErrCode, str] = {
    ErrCode.CHECKPOINT_SAVE: "Erro ao salvar checkpoint",
    ErrCode.CHECKPOINT_RESTORE: "Erro ao restaurar checkpoint",
    ErrCode.PARSE_ACTIONS: "Erro ao interpretar ações JSON",
    ErrCode.SANDBOX_VIOLATION: "Código rejeitado pelo sandbox de segurança",
    ErrCode.OPTIMIZE_DEPRECATED: "optimize_tool removido — use structured_actions_tool",
    ErrCode.EXCEL_NOT_FOUND: "Excel aberto não encontrado",
    ErrCode.EXCEL_WRITE_COM: "Erro ao escrever no Excel via COM",
    ErrCode.EXCEL_SAVE_OPENPYXL: "Erro ao salvar arquivo com openpyxl",
    ErrCode.EXCEL_SAVE_DF: "Erro ao salvar arquivo via DataFrame",
    ErrCode.COLUMN_MISSING: "Coluna não encontrada",
    ErrCode.ACTION_INVALID: "Ação inválida",
    ErrCode.ACTION_UNKNOWN: "Tipo de ação desconhecido",
    ErrCode.OAUTH_STATE_MISMATCH: "State OAuth inválido — possível ataque",
    ErrCode.FILE_NOT_FOUND: "Arquivo não encontrado",
    ErrCode.FILE_INVALID_FORMAT: "Formato inválido — selecione apenas planilhas",
    ErrCode.SHEET_EMPTY: "Aba vazia",
    ErrCode.INDEX_FAILED: "Não foi possível indexar arquivo",
    ErrCode.OLLAMA_UNAVAILABLE: "Ollama não disponível",
    ErrCode.WORKSPACE_ERROR: "Nenhuma planilha indexada",
    ErrCode.ENCRYPTION_FAILED: "Falha na criptografia dos tokens",
    ErrCode.OAUTH_UNAVAILABLE: "OAuth não disponível",
    ErrCode.NIM_UNAVAILABLE: "NVIDIA NIM não disponível",
    ErrCode.NIM_AUTH_FAILED: "Falha na autenticação NIM — API key ausente ou inválida",
    ErrCode.NIM_REQUEST_FAILED: "Erro na requisição ao NVIDIA NIM",
}


def err_str(code: ErrCode, detail: str = "") -> str:
    msg = f"[{code.value}] {ERR_MESSAGES[code]}"
    if detail:
        msg += f": {detail}"
    return msg
