# Sahara Fennec — Agente de Planilhas

O **Sahara Fennec** é um assistente desktop com inteligência artificial que conversa com você em linguagem natural para ler, analisar e modificar planilhas Excel. Basta abrir uma planilha e pedir — o Fennec entende o que você quer e faz na hora, com segurança: antes de cada alteração, ele cria automaticamente uma cópia de segurança (checkpoint) para que você possa voltar atrás se precisar. Funciona offline (com Ollama) ou na nuvem (com NVIDIA NIM).

---

## O que este projeto faz?

Imagine ter um assistente que conhece sua planilha inteira e entende português. Você pode pedir coisas como:

- "Ordene por salário do maior para o menor"
- "Filtre só os clientes de São Paulo"
- "Preencha as células vazias com zero"
- "Crie uma tabela dinâmica por região"
- "Renomeie a coluna 'Nome' para 'Nome Completo'"

O Fennec lê sua planilha, entende a estrutura (colunas, tipos de dados, estatísticas), e aplica as alterações que você pediu — sem usar código arbitrário, sem risco de executar algo perigoso. Tudo é feito através de ações declarativas validadas, nunca com `exec()`. Além disso, ele pode integrar com Gmail, Outlook, Teams, Google Calendar/Drive, OneDrive, SharePoint e Trello para enviar resumos, criar tarefas ou fazer upload de dados — tudo conversando.

---

## Funcionalidades

- **Chat com IA** — Converse em português para ler e modificar planilhas
- **Interface desert-themed** — Visual temático com mascote Fennec (raposa-do-deserto)
- **19 ações estruturadas** — sort, fillna, replace, rename, filter, pivot_table, merge_columns, strip_whitespace, change_dtype, duplicate_sheet, create_sheet, delete_sheet, rename_sheet e mais
- **Zero `exec()`** — Nunca executa código arbitrário; todas as ações são declarativas e validadas
- **Checkpoints automáticos** — Cópia de segurança antes de cada alteração, com restauração a um clique
- **Dois backends de IA** — Ollama (local, privado, offline) ou NVIDIA NIM (nuvem, modelos maiores)
- **MultiPlanilhas** — Alterne entre abas e arquivos indexados na mesma sessão
- **Leitura de Excel aberto** — Indexa planilhas abertas no Excel Desktop via COM (Windows)
- **Suporte a múltiplos formatos** — `.xlsx`, `.xlsm`, `.xls` (legado), `.ods` (LibreOffice)
- **CLI interativo** — Modo terminal para automação e uso headless
- **8 integrações** — Gmail, Google Calendar, Google Drive, Outlook, OneDrive, SharePoint, Teams, Trello
- **OAuth guiado** — Login com Google/Microsoft via PKCE (sem copiar/colar tokens)
- **Criptografia de tokens** — DPAPI (Windows) ou Fernet (Linux/macOS) para proteger credenciais
- **Erros machine-parseáveis** — Todos os erros seguem o formato `[E0xx] descrição: detalhe`
- **Drag-and-drop** — Arraste arquivos Excel direto para a janela do app

---

## Tecnologias Utilizadas

| Categoria | Tecnologia |
|---|---|
| **Linguagem** | Python 3.11+ |
| **Interface gráfica** | CustomTkinter (tema desert), Tkinter, Pillow |
| **Processamento de dados** | Pandas, openpyxl, xlrd, odfpy |
| **IA local** | Ollama (qwen2.5:7b padrão) |
| **IA na nuvem** | NVIDIA NIM (meta/llama-3.1-70b-instruct padrão) via OpenAI SDK |
| **Automação Excel** | pywin32 / COM (Windows) |
| **Segurança** | cryptography (Fernet), win32crypt (DPAPI) |
| **OAuth** | PKCE + loopback local (RFC 7636) |
| **Build/Instalador** | PyInstaller, Inno Setup 6 |
| **Testes** | pytest, pytest-cov |
| **Lint/Type check** | Ruff, mypy |
| **CI/CD** | GitHub Actions (lint + test + mypy) |

---

## Pré-requisitos

### Para usuários (instalador)

- **Windows 10 ou superior** (o instalador cuida de tudo: Python, dependências, Ollama e modelo de IA)
- **Para IA local**: ~8 GB de RAM (modelo 7B) ou ~16 GB (modelo 14B)
- **Para IA na nuvem**: conta em [build.nvidia.com](https://build.nvidia.com) e API key

### Para desenvolvedores

- **Python 3.11 ou superior**
- **Git**
- **Ollama** (opcional, para IA local) — [ollama.com](https://ollama.com)
- **Inno Setup 6** (opcional, para gerar instalador Windows)
- **pywin32** (opcional, apenas no Windows, para integração com Excel aberto)

---

## Instalação

### 1. Clone o repositório

```bash
git clone https://github.com/seu-usuario/fennec-excel.git
cd fennec-excel
```

### 2. Crie um ambiente virtual

```bash
python -m venv .venv

# Linux/macOS:
source .venv/bin/activate

# Windows:
.venv\Scripts\activate
```

### 3. Instale as dependências

**Instalação completa (recomendada):**

```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt  # ferramentas de desenvolvimento
```

**Instalação mínima (sem OpenAI/NIM, sem pywin32):**

```bash
pip install -r requirements-slim.txt
```

**Instalação via pyproject.toml:**

```bash
pip install -e ".[dev]"
```

### 4. Configure as variáveis de ambiente

Copie o arquivo de exemplo e preencha os valores:

```bash
cp .env.example .env
```

Edite `.env` com suas credenciais (veja a seção [Configuração](#configuração) para detalhes).

Para OAuth (Google/Microsoft), copie também:

```bash
cp oauth_defaults.example.json oauth_defaults.json
```

Preencha com seus Client IDs OAuth (veja `docs/OAUTH-SETUP.md`).

### 5. Configure o backend de IA

**Ollama (local, padrão):**

```bash
# Instale o Ollama: https://ollama.com
ollama pull qwen2.5:7b
```

**NVIDIA NIM (nuvem):**

1. Obtenha uma API key em [build.nvidia.com](https://build.nvidia.com) → Settings → API Keys
2. Defina `NVIDIA_API_KEY` no arquivo `.env` ou configure na interface: Settings → Backend → NIM

---

## Uso

### Interface gráfica (GUI)

```bash
python main.py
```

Ao abrir:

1. Clique em **"Indexar planilha"** (ou arraste um arquivo `.xlsx`/`.xlsm`/`.xls`/`.ods` para a janela)
2. No Windows, você também pode indexar planilhas já abertas no Excel
3. Converse com o Fennec no chat — ele responde e aplica alterações
4. Antes de cada alteração, o Fennec mostra uma prévia e pede confirmação
5. Use o botão de **Checkpoint** para restaurar versões anteriores

### Linha de comando (CLI REPL)

```bash
# Modo interativo sem arquivo:
python main.py --cli

# Abrindo com um arquivo:
python main.py --cli planilha.xlsx
```

Comandos disponíveis no REPL:

| Comando | Descrição |
|---|---|
| `/load <caminho>` | Carregar arquivo Excel |
| `/sheet <nome>` | Trocar para outra aba |
| `/summary` | Resumo da planilha atual |
| `/checkpoints` | Listar checkpoints salvos |
| `/undo` | Restaurar último checkpoint |
| `/backend <nome>` | Trocar backend LLM (`nim` / `ollama`) |
| `/model <nome>` | Trocar modelo LLM |
| `/help` | Mostrar ajuda |
| `/quit` | Sair |

Qualquer outro texto é enviado como pergunta ao agente Fennec em linguagem natural.

### Verificação rápida de imports

```bash
python main.py --smoke-test
```

Útil para verificar se todas as dependências estão instaladas corretamente (usado pelo instalador Slim).

---

## Comandos Disponíveis

| Comando | Descrição |
|---|---|
| `python main.py` | Inicia a interface gráfica |
| `python main.py --cli [arquivo]` | Inicia o modo CLI interativo |
| `python main.py --smoke-test` | Verifica imports e sai (diagnóstico) |
| `pytest` | Executa os testes (311 testes) |
| `pytest --cov --cov-report=term-missing` | Testes com relatório de cobertura |
| `ruff check src/` | Verifica lint com Ruff |
| `ruff check src/ --fix` | Correção automática de lint |
| `mypy src/` | Verificação de tipos estáticos |
| `python scripts/bench.py` | Benchmark de performance |
| `python scripts/bench.py --iterations 10 --file planilha.xlsx` | Benchmark customizado |
| `scripts\build_installer.ps1` | Build completo (PyInstaller + Inno Setup) |
| `scripts\build_installer.ps1 -InnoOnly` | Rebuild só dos instaladores |
| `scripts\build_installer.ps1 -SkipInno` | Build PyInstaller sem Inno Setup |
| `scripts\smoke_test_slim.ps1` | Smoke test do instalador Slim |

---

## Estrutura do Projeto

```
fennec-excel/
├── main.py                        # Ponto de entrada (GUI ou CLI)
├── pyproject.toml                 # Config do projeto, pytest, ruff, mypy
├── requirements.txt               # Dependências completas
├── requirements-slim.txt          # Dependências mínimas (instalador magro)
├── requirements-dev.txt           # Ferramentas de desenvolvimento
├── .env.example                   # Template de variáveis de ambiente
├── oauth_defaults.example.json    # Template de Client IDs OAuth
├── FennecExcel.spec               # Config do PyInstaller
├── LICENSE                        # Licença MIT
├── CHANGELOG.md                   # Histórico de mudanças
│
├── src/                           # Código-fonte principal
│   ├── __init__.py
│   ├── errcodes.py                # Códigos de erro machine-parseáveis (E001–E024)
│   ├── com_utils.py               # Context manager COM (Windows Excel)
│   ├── logging_config.py          # Logging rotativo em arquivo
│   │
│   ├── agent/                     # Agente ReAct + LLM
│   │   ├── runner.py              # Loop ReAct principal (run_agent)
│   │   ├── llm_client.py          # Protocol LLMClient + factory create_client()
│   │   ├── ollama_client.py       # Cliente Ollama (localhost:11434)
│   │   ├── nim_client.py          # Cliente NVIDIA NIM (api.nvidia.com)
│   │   ├── actions.py             # 19 ações estruturadas declarativas
│   │   ├── excel_write.py         # Escrita no Excel (COM ou openpyxl)
│   │   ├── sandbox.py             # Validação de código seguro (legado)
│   │   ├── tools.py               # Re-exports para compatibilidade
│   │   └── result.py              # ToolResult + ErrCode re-export
│   │
│   ├── indexing/                  # Indexação de planilhas
│   │   └── excel_reader.py        # Leitura COM / openpyxl / xlrd / odfpy
│   │
│   ├── checkpoints/               # Sistema de checkpoints
│   │   └── manager.py             # Save/restore com índice JSON (max 200)
│   │
│   ├── gui/                       # Interface gráfica CustomTkinter
│   │   ├── main_window.py         # Janela principal (MainWindow)
│   │   ├── chat_controller.py     # Dispatch do agente + bubbles
│   │   ├── settings_controller.py # Diálogo de configurações e OAuth
│   │   ├── workspace_manager.py   # Gestão de workspaces indexadas
│   │   ├── indexer_window.py      # Janela de indexação
│   │   ├── input_bar.py           # Barra de input do chat
│   │   ├── instruct_panel.py      # Painel de instruções
│   │   ├── side_buttons.py        # Botões laterais
│   │   ├── chat_bubbles.py        # Balões de chat (Fennec + Usuário)
│   │   ├── gradient.py            # Desenho de gradiente vertical
│   │   ├── styles.py              # Estilos e cores do tema desert
│   │   └── constants.py           # Versão do app (via pyproject.toml)
│   │
│   ├── cli/                       # Interface de linha de comando
│   │   └── repl.py                # REPL interativo (FennecREPL)
│   │
│   ├── config/                    # Configurações persistentes
│   │   └── app_settings.py        # Settings JSON com cache LRU
│   │
│   ├── integrations/              # Integrações externas
│   │   ├── router.py              # Roteador de integrações (despacho por palavras)
│   │   ├── oauth.py               # OAuth PKCE para Google e Microsoft
│   │   ├── oauth_defaults.py      # Client IDs OAuth (embutidos, env ou JSON)
│   │   ├── token_store.py         # Armazenamento criptografado de tokens
│   │   └── backends/              # Backends de integração
│   │       ├── gmail.py
│   │       ├── google_calendar.py
│   │       ├── google_drive.py
│   │       ├── outlook.py
│   │       ├── outlook_calendar.py
│   │       ├── onedrive.py
│   │       ├── sharepoint.py
│   │       ├── teams.py
│   │       ├── trello.py
│   │       └── _utils.py
│   │
│   └── persona/                   # Persona do assistente
│       └── persona_config.py      # Config do Fennec (avatar, welcome, etc.)
│
├── tests/                         # 311 testes automatizados
│   ├── conftest.py                # Fixtures compartilhadas
│   ├── fixtures/                  # Arquivos de teste
│   ├── test_agent_loop.py
│   ├── test_structured_actions.py
│   ├── test_new_actions.py
│   ├── test_checkpoints.py
│   ├── test_checkpoint_manager.py
│   ├── test_excel_reader.py
│   ├── test_ods_xls_reader.py
│   ├── test_cli_repl.py
│   ├── test_nim_client.py
│   ├── test_ollama_client.py
│   ├── test_llm_client.py
│   ├── test_errcodes.py
│   ├── test_token_store.py
│   ├── test_oauth.py
│   ├── test_router.py
│   ├── test_integration_backends.py
│   ├── test_sandbox.py
│   ├── test_fennec_safety.py
│   ├── test_workbook_actions.py
│   ├── test_tools_coverage.py
│   ├── test_runner_utils.py
│   ├── test_runner_edge.py
│   └── test_app_settings.py
│
├── installer/                     # Pipeline de instalador Windows
│   ├── FennecExcel.iss            # Inno Setup Legacy (com PyInstaller bundle)
│   ├── FennecExcel-Slim.iss       # Inno Setup Slim (com bootstrap)
│   ├── run_fennec.bat             # Launcher que configura venv automaticamente
│   ├── configurar_ambiente.bat    # Script de reparo de ambiente
│   ├── bootstrap/
│   │   ├── postinstall.ps1        # Pós-instalação (Ollama + modelos)
│   │   └── setup_slim.ps1         # Setup de venv + pip (instalador magro)
│   └── sounds/
│       └── installer_music.mp3    # Música do instalador
│
├── scripts/                       # Scripts de build e utilidade
│   ├── build_installer.ps1        # Build PyInstaller + Inno Setup
│   ├── smoke_test_slim.ps1        # Smoke test do instalador magro
│   ├── bench.py                   # Benchmark de performance
│   ├── make_installer_assets.py   # Gera BMPs do instalador
│   ├── make_fennec_ico.py         # Gera ícone .ico
│   ├── fix_head_icon.py           # Utilidade de ícone
│   └── remove_bg_mascot.py        # Remove fundo da mascote
│
├── assets/                        # Recursos visuais
│   ├── desert_bg.png
│   ├── fennec_icon.png
│   ├── fennec_head_icon.png
│   ├── fennec_head_icon.ico
│   ├── fennec_mascot_transparent.png
│   ├── installer_wizard.bmp
│   ├── installer_small.bmp
│   └── installer_fennec.png
│
├── docs/                          # Documentação
│   ├── V2-INTEGRACOES.md          # Guia de integrações
│   ├── OAUTH-SETUP.md             # Setup OAuth passo a passo
│   ├── INSTALADOR-E-VERSOES.md    # Documentação do instalador
│   ├── INSTALADOR-ANALISE.md      # Análise técnica do instalador
│   ├── STATUS.md                  # Status do projeto
│   └── SUPERCHARGE_PLAN.md        # Plano de melhorias
│
└── .github/
    └── workflows/
        └── ci.yml                 # CI: lint + test + mypy
```

---

## Arquitetura

```
main.py ──► MainWindow (GUI) ou FennecREPL (CLI)
  │
  ├── Agent Loop (ReAct)
  │   ├── LLMClient (protocol)
  │   │   ├── OllamaClient ──► localhost:11434 (IA local)
  │   │   └── NimClient ──► api.nvidia.com/v1 (IA na nuvem)
  │   │
  │   ├── structured_actions_tool (19 ações declarativas, sem exec)
  │   │   ├── _apply_actions_to_df() ──► Pandas DataFrame
  │   │   └── _df_to_excel_matrix() ──► COM ou openpyxl write
  │   │
  │   └── IntegrationRouter (8 backends OAuth)
  │
  ├── Indexer (COM / openpyxl / xlrd / odfpy)
  │   └── COMContext (context manager para CoInitialize/CoUninitialize)
  │
  ├── CheckpointManager (SaveCopyAs / file copy, max 200 por workspace)
  ├── Config (settings.json com cache LRU + mtime invalidation)
  └── TokenStore (DPAPI / Fernet encryption)
```

**Fluxo principal:**

1. O usuário indexa uma planilha (arquivo ou Excel aberto)
2. O `Indexer` lê os dados e cria um `Workspace` (DataFrame + metadados)
3. O usuário envia uma mensagem no chat
4. O `ChatController` (ou REPL) chama `run_agent()`
5. O **Agente ReAct** monta um prompt com o resumo da planilha e a pergunta
6. O **LLM** (Ollama ou NIM) gera uma resposta, possivelmente com bloco `[ACTIONS]`
7. Se houver ações, o `structured_actions_tool` aplica no DataFrame, salva checkpoint, e escreve no Excel
8. A resposta final é exibida ao usuário

**Conceitos-chave:**

- **`LLMClient`** — Protocol com `is_available()` + `generate(prompt, system, max_tokens)`. Qualquer backend de IA implementa esta interface.
- **`COMContext`** — Context manager para inicializar/finalizar o COM do Windows. Garante `CoUninitialize()` em `finally`.
- **`structured_actions_tool`** — Aplica ações JSON declarativas no DataFrame/COM. 19 ações, nenhuma usa `exec()`.
- **`_MODIFY_SIGNALS`** — Classificador de intenção por palavras-chave que evita acionar ações de modificação em perguntas de somente leitura.
- **`ErrCode`** — Enum com 24 códigos de erro machine-parseáveis (`[E001]` a `[E024]`).

---

## Configuração

### Variáveis de ambiente

Copie `.env.example` para `.env` e ajuste:

| Variável | Descrição | Obrigatória? |
|---|---|---|
| `NVIDIA_API_KEY` | API key do NVIDIA NIM (build.nvidia.com) | Apenas se usar NIM |
| `FENNEC_GOOGLE_CLIENT_ID` | OAuth Client ID do Google Cloud | Para integrações Google |
| `FENNEC_MICROSOFT_CLIENT_ID` | OAuth Client ID do Azure (Microsoft) | Para integrações Microsoft |
| `FENNEC_GMAIL_USER` | Email Gmail para fallback SMTP | Opcional (se sem OAuth Google) |
| `FENNEC_GMAIL_APP_PASSWORD` | App password do Gmail | Opcional (SMTP fallback) |
| `FENNEC_GMAIL_TO` | Email destinatário padrão | Opcional |
| `FENNEC_TEAMS_WEBHOOK_URL` | Webhook do Microsoft Teams | Para integração Teams |
| `FENNEC_TRELLO_KEY` | API key do Trello | Para integração Trello |
| `FENNEC_TRELLO_TOKEN` | Token do Trello | Para integração Trello |
| `FENNEC_TRELLO_LIST_ID` | ID da lista do Trello para criar cards | Opcional |
| `FENNEC_SHAREPOINT_SITE_ID` | ID do site SharePoint | Opcional |
| `FENNEC_SHAREPOINT_DRIVE_ID` | ID do drive SharePoint | Opcional |
| `FENNEC_OUTLOOK_TO` | Email destinatário padrão do Outlook | Opcional |
| `FENNEC_GOOGLE_ACCESS_TOKEN` | Token direto do Google (avançado) | Apenas para debug |
| `FENNEC_MICROSOFT_ACCESS_TOKEN` | Token direto da Microsoft (avançado) | Apenas para debug |

### OAuth Client IDs

Copie `oauth_defaults.example.json` para `oauth_defaults.json` e preencha:

```json
{
  "google_client_id": "SEU_CLIENT_ID.apps.googleusercontent.com",
  "microsoft_client_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
}
```

Guia completo de setup OAuth: `docs/OAUTH-SETUP.md`

### Settings do aplicativo

As configurações são salvas em `%APPDATA%\SaharaFennec\settings.json` (Windows) ou `~/.sahara_fennec/SaharaFennec/settings.json` (Linux/macOS):

| Chave | Padrão | Descrição |
|---|---|---|
| `llm_backend` | `ollama` | Backend de IA (`ollama` ou `nim`) |
| `model` | `qwen2.5:7b` | Modelo Ollama |
| `nim_model` | `meta/llama-3.1-70b-instruct` | Modelo NVIDIA NIM |
| `nim_base_url` | `https://integrate.api.nvidia.com/v1` | URL base da API NIM |
| `index_all_sheets` | `false` | Indexar todas as abas ou só a ativa |
| `max_rows_per_sheet` | `0` | Limite de linhas por aba (0 = sem limite) |
| `google_client_id` | `""` | Client ID Google (sobrepõe env/json) |
| `microsoft_client_id` | `""` | Client ID Microsoft (sobrepõe env/json) |

Também editáveis pela interface: Settings (ícone de engrenagem).

### Arquivos de dados em runtime

| Caminho | Descrição |
|---|---|
| `%APPDATA%/SaharaFennec/settings.json` | Configurações do app |
| `%APPDATA%/SaharaFennec/oauth_tokens.json` | Tokens OAuth criptografados |
| `%APPDATA%/SaharaFennec/.enc_key` | Chave de criptografia Fernet |
| `%APPDATA%/SaharaFennec/sahara_fennec.log` | Log rotativo (10 MB, 3 backups) |
| `<dir da planilha>/_fennec_checkpoints/` | Checkpoints (max 200 por planilha) |

---

## Testes

```bash
# Executar todos os testes:
pytest

# Com cobertura:
pytest --cov --cov-report=term-missing

# Testes verbosos:
pytest -v --tb=short

# Apenas um módulo:
pytest tests/test_structured_actions.py
```

O projeto possui **311 testes** com cobertura mínima de 60% no código core (definido em `pyproject.toml`). Cobertura omitida (por design): GUI, CLI, COM, logging, persona, backends de integração e OAuth — módulos que dependem de interface gráfica, sistema operacional ou serviços externos.

---

## Build e Instalador

### Requisitos para build

- Python 3.11+
- PyInstaller (`pip install pyinstaller`)
- Inno Setup 6 (para gerar o `.exe` do instalador)

### Build completo

```powershell
# No PowerShell, na raiz do projeto:
.\scripts\build_installer.ps1
```

Saídas:

- `dist\FennecExcel\` — App standalone (PyInstaller bundle)
- `build\installer\SaharaFennec-Setup.exe` — **Instalador Slim** (~poucos MB, recomendado para distribuição). Instala o código e configura Python + dependências + Ollama automaticamente.
- `build\installer\SaharaFennec-Setup-Legacy.exe` — Instalador Legacy (~2 GB, tudo embutido). Só gerado se `dist\FennecExcel` existir.

### Apenas instaladores (sem PyInstaller)

```powershell
.\scripts\build_installer.ps1 -InnoOnly
```

### Smoke test do instalador Slim

```powershell
.\scripts\smoke_test_slim.ps1
```

Simula a instalação completa: cópia de arquivos, criação de venv, pip install, e verificação de que o app carrega.

### Benchmark de performance

```bash
python scripts/bench.py
python scripts/bench.py --iterations 10 --file planilha.xlsx
```

Mede: load_settings(), indexação, resumo de workspace, cache de sheet names, e disponibilidade NIM.

---

## Integrações

8 backends com autenticação OAuth guiada (PKCE + loopback local):

| Integração | Autenticação | Documentação |
|---|---|---|
| Gmail | OAuth Google API / SMTP fallback | `docs/V2-INTEGRACOES.md` |
| Google Calendar | OAuth Google | `docs/V2-INTEGRACOES.md` |
| Google Drive | OAuth Google | `docs/V2-INTEGRACOES.md` |
| Outlook | OAuth Microsoft | `docs/V2-INTEGRACOES.md` |
| OneDrive | OAuth Microsoft | `docs/V2-INTEGRACOES.md` |
| SharePoint | OAuth Microsoft | `docs/V2-INTEGRACOES.md` |
| Teams | Webhook URL | `docs/V2-INTEGRACOES.md` |
| Trello | API key + token | `docs/V2-INTEGRACOES.md` |

---

## Segurança

- **Sem `exec()`** — O antigo `optimize_tool` foi permanentemente removido. Todas as ações usam `structured_actions_tool` com JSON declarativo.
- **Sandbox de validação** — Módulos permitidos limitados a `pandas`, `openpyxl`, `odf`, `xlrd`, `math`, `datetime`. Nomes perigosos como `exec`, `eval`, `open`, `os`, `subprocess` são bloqueados.
- **Tokens OAuth criptografados** — DPAPI no Windows, Fernet no Linux/macOS. Chave Fernet derivada de arquivo aleatório persistente com permissões 0600.
- **COM isolado** — `COMContext` garante `CoUninitialize()` em `finally`, evitando vazamentos de apartment COM.
- **Erros parseáveis** — Todos os erros seguem o formato `[E0xx] descrição: detalhe`, facilitando diagnóstico automatizado.
- **Confirmação de alterações** — Antes de modificar a planilha, o Fennec mostra prévia das ações e pede confirmação.
- **`.env` nunca commitado** — O `.gitignore` bloqueia `.env`, `oauth_defaults.json`, chaves e credenciais.

---

## Solução de Problemas

| Problema | Solução |
|---|---|
| `[E018] Ollama não disponível` | Instale o Ollama ([ollama.com](https://ollama.com)) e execute `ollama serve`. No Windows, o app tenta iniciar o Ollama automaticamente. |
| `[E022] NVIDIA NIM não disponível` | Verifique se a API key está configurada (`.env` ou Settings → NIM). Instale o pacote: `pip install openai`. |
| `[E023] Falha na autenticação NIM` | API key inválida ou ausente. Gere uma nova em [build.nvidia.com](https://build.nvidia.com) → Settings → API Keys. |
| `[E006] Excel aberto não encontrado` | Abra o Excel com a planilha antes de indexar. Funciona apenas no Windows com `pywin32` instalado. |
| `[E015] Formato inválido` | Formatos suportados: `.xlsx`, `.xlsm`, `.xls`, `.ods`. Outros formatos não são aceitos. |
| `[E010] Coluna não encontrada` | O nome da coluna deve ser exato (incluindo maiúsculas/minúsculas). Peça ao Fennec para listar as colunas primeiro. |
| Arquivo `.ods` ou `.xls` não salva | Esses formatos são convertidos para `.xlsx` automaticamente ao salvar. O caminho do arquivo é atualizado. |
| `pip install` falha no Linux | `pywin32` é excluído em não-Windows automaticamente. Se falhar, use `requirements-slim.txt`. |
| App não abre após instalar (Slim) | Execute `configurar_ambiente.bat` na pasta de instalação como administrador. |
| Música do instalador não para | Clique no botão **"Mutar música"** no canto inferior esquerdo do instalador. |
| Checkpoints ocupam muito espaço | Limite de 200 por planilha, com limpeza automática dos mais antigos. Pasta: `<dir da planilha>/_fennec_checkpoints/`. |

---

## Contribuindo

1. Faça um fork do repositório
2. Crie uma branch para sua feature: `git checkout -b feature/nova-funcionalidade`
3. Faça commit das suas mudanças: `git commit -m "Adiciona nova funcionalidade"`
4. Envie para o fork: `git push origin feature/nova-funcionalidade`
5. Abra um Pull Request

**Antes de enviar:**

```bash
pytest           # testes
ruff check src/  # lint
mypy src/        # type check
```

**Padrões:**

- Python 3.11+ (use type hints)
- Line length: 120 caracteres
- Lint: Ruff (regras E, F, W, I, UP)
- Commits em português ou inglês, mensagens claras
- Nunca commite `.env`, `oauth_defaults.json`, chaves ou credenciais

---

## Licença

Este projeto está licenciado sob a **Licença MIT**. Veja o arquivo [LICENSE](LICENSE) para detalhes.

```
MIT License
Copyright (c) 2025 Isaac Nathan da Silva Barbosa
```
