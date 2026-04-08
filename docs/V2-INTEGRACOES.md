# Integracoes v2 - Sahara Fennec

Este documento descreve a base da v2 com OAuth guiado e integracoes.

## Legado v1.0 (backup funcional)

- Instalador pesado (legado): `build\installer\SaharaFennec-Setup-Legacy.exe`
- Script para snapshot local da v1: `scripts\create_v1_backup.ps1`

Uso:

```powershell
Set-Location "e:\Sahara Fenneck"
.\scripts\create_v1_backup.ps1
```

Isso gera uma copia versionada em `releases\v1.0-backup-<timestamp>\`.

## Integracoes v2 implementadas

As integracoes sao roteadas em `src\integrations\router.py` e acionadas por linguagem natural no chat:

- **Google OAuth guiado no app** (Configuracoes > Conectar Google)
  - Gmail API (envio de e-mail)
  - Google Agenda (leitura de eventos)
  - Google Drive (upload CSV da planilha ativa)
- **Microsoft OAuth guiado no app** (Configuracoes > Conectar Microsoft)
  - Outlook/Graph: envio de e-mail
  - Outlook/Graph: calendario corporativo
  - OneDrive: upload CSV da planilha ativa
  - SharePoint: upload CSV (com `site_id`)
- **Teams** via webhook (`FENNEC_TEAMS_WEBHOOK_URL`)
- **Trello** via API key/token (sem custo)

O roteador eh chamado no fluxo do agente em `src\agent\runner.py`, antes do LLM.

## Configuracao

### OAuth guiado (sem token manual)

Defina os Client IDs em **Configurações**:

- `google_client_id`
- `microsoft_client_id`

Depois clique em:

- **Conectar Google**
- **Conectar Microsoft**

Os tokens sao guardados em arquivo local protegido por DPAPI no Windows (`oauth_tokens.json` criptografado).

### Variaveis opcionais

- Teams:
  - `FENNEC_TEAMS_WEBHOOK_URL`
- Trello:
  - `FENNEC_TRELLO_KEY`
  - `FENNEC_TRELLO_TOKEN`
  - `FENNEC_TRELLO_LIST_ID` (default para criar card)
- SharePoint (Graph):
  - `FENNEC_SHAREPOINT_SITE_ID`
  - `FENNEC_SHAREPOINT_DRIVE_ID` (opcional)
- Fallback Gmail SMTP (se nao usar Gmail API):
  - `FENNEC_GMAIL_USER`
  - `FENNEC_GMAIL_APP_PASSWORD`
  - `FENNEC_GMAIL_TO` (opcional)

## Exemplos de prompt

- "Mostre a lista de integracoes disponiveis"
- "Envie um resumo desta planilha no Teams"
- "Envie um resumo desta planilha por e-mail para `financeiro@empresa.com`"
- "Traga os proximos compromissos da minha agenda"
- "Veja meu calendario do Outlook"
- "Faça upload desta planilha no Google Drive"
- "Suba esta planilha para o OneDrive"
- "Envie essa planilha para SharePoint"
- "Crie um card no Trello para esta planilha"

## Checklist de seguranca aplicado

- OAuth com **PKCE + state** e callback loopback local.
- Tokens em repouso com **DPAPI** no Windows.
- Nenhum token hardcoded no codigo.
- `exec` de otimizacao com **builtins restritos** (sem `__import__`, `open`, etc).
- Checkpoint por ordem (um checkpoint antes da primeira alteracao da ordem).

## Backlog de integracoes interessantes (gratis / baixo custo)

1. Slack webhook/bot
2. Notion API
3. Jira Cloud (free tier) / Trello aprofundado (listas e boards)
4. GitHub Issues/Projects para gerar tarefas a partir da planilha
