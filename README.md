# Sahara Fennec — Agente de Planilhas

App desktop com chat para otimizar planilhas Excel, com processamento local (Ollama) ou em nuvem (NVIDIA NIM) e checkpoints de segurança.

## Recursos

- Interface desert-themed estilo assistente (Fennec)
- Indexação de planilhas abertas no Excel (COM) ou arquivos locais (`.xlsx`, `.xlsm`, `.xls`, `.ods`)
- MultiPlanilhas: alternar/remover planilhas indexadas na sessão
- Checkpoints automáticos antes de cada alteração + restauração
- **LLM duplo**: Ollama (local) ou NVIDIA NIM (nuvem, build.nvidia.com)
- 19 ações estruturadas sem `exec()` (sort, fillna, replace, rename, filter, filter_contains, filter_range, pivot_table, merge_columns, strip_whitespace, change_dtype, duplicate_sheet, etc.)
- **CLI REPL** (`python main.py --cli`) para uso headless/automação
- Integrações v2 (opcionais): Gmail, Teams, Google Calendar/Drive, Outlook/Graph, OneDrive/SharePoint, Trello

## Arquitetura

```
main.py ──► MainWindow (GUI) ou FennecREPL (CLI)
│
├── Agent Loop (ReAct)
│   ├── LLMClient protocol
│   │   ├── OllamaClient (localhost:11434)
│   │   └── NimClient (api.nvidia.com/v1)
│   ├── structured_actions_tool (19 ações, sem exec)
│   └── IntegrationRouter (8 backends OAuth)
│
├── Indexer (COM / openpyxl / xlrd / odfpy)
│   └── COMContext (context manager)
│
└── CheckpointManager (SaveCopyAs / file copy)
```

- **`LLMClient`** protocol: `is_available()` + `generate(prompt, system, max_tokens)`
- **`COMContext`**: context manager para `CoInitialize/CoUninitialize` + workbook resolution
- **`structured_actions_tool`**: aplica ações JSON declarativas no DataFrame/COM — 19 ações, nenhum `exec()`
- **Formatos suportados**: `.xlsx`/`.xlsm` (openpyxl), `.xls` (xlrd), `.ods` (odfpy) — escrita sempre converte para `.xlsx`
- **`ErrCode`** enum: erros machine-parseáveis (`[E018] Ollama não disponível`)

## Quick Start

### 1. Instalar dependências

```bash
pip install -r requirements.txt
```

### 2. Escolher backend LLM

**Ollama (local, padrão):**

```bash
# Instalar Ollama: https://ollama.com
ollama pull qwen2.5:7b
```

**NVIDIA NIM (nuvem):**

1. Obter API key em https://build.nvidia.com → Settings → API Keys
2. Configurar no app: Settings → Backend → NIM → colar API key
3. Ou definir `NVIDIA_API_KEY` no ambiente (ver `.env.example`)

### 3. Rodar

```bash
python main.py          # GUI
python main.py --cli    # CLI REPL
```

No Windows, abra o Excel com as planilhas desejadas antes de indexar.

## Configuração

Copie `.env.example` para `.env` e ajuste as variáveis:

| Variável | Descrição |
|----------|-----------|
| `NVIDIA_API_KEY` | API key do NVIDIA NIM (build.nvidia.com) |
| `FENNEC_GMAIL_USER` | Email Gmail para fallback SMTP |
| `FENNEC_GMAIL_APP_PASSWORD` | App password do Gmail |
| `FENNEC_TEAMS_WEBHOOK_URL` | Webhook do Microsoft Teams |
| `FENNEC_TRELLO_KEY` / `FENNEC_TRELLO_TOKEN` | Credenciais Trello |
| `FENNEC_GOOGLE_CLIENT_ID` | OAuth client ID Google |
| `FENNEC_MICROSOFT_CLIENT_ID` | OAuth client ID Microsoft |

Veja `.env.example` para a lista completa.

## Segurança

- **Sandbox**: `structured_actions_tool` nunca usa `exec()` — ações são aplicadas declarativamente
- **Tokens OAuth**: criptografados com DPAPI (Windows) ou Fernet (fallback), nunca em plaintext
- **Chave Fernet**: derivada de `USERNAME@COMPUTERNAME` via SHA-256
- **COM isolado**: `COMContext` garante `CoUninitialize()` em `finally`
- **ErrCodes**: todos os erros são machine-parseáveis (`[E0xx] descrição: detalhe`)

## Testes

```bash
pytest          # 311 testes, 76% cobertura
ruff check src/ # lint
mypy src/       # type check
```

## Build e Instalador

```powershell
# Build PyInstaller + Inno Setup
scripts/build_installer.ps1

# Apenas Inno Setup (após build manual)
scripts/build_installer.ps1 -InnoOnly
```

## Integrações

8 backends com OAuth guiado (PKCE + loopback local):

| Integração | Auth | Documentação |
|-----------|------|-------------|
| Gmail | OAuth Google / SMTP | `docs/V2-INTEGRACOES.md` |
| Google Calendar | OAuth Google | `docs/V2-INTEGRACOES.md` |
| Google Drive | OAuth Google | `docs/V2-INTEGRACOES.md` |
| Outlook | OAuth Microsoft | `docs/V2-INTEGRACOES.md` |
| OneDrive | OAuth Microsoft | `docs/V2-INTEGRACOES.md` |
| SharePoint | OAuth Microsoft | `docs/V2-INTEGRACOES.md` |
| Teams | Webhook URL | `docs/V2-INTEGRACOES.md` |
| Trello | API key + token | `docs/V2-INTEGRACOES.md` |

## Licença

Veja `LICENSE`.
