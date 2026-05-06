# Sahara Fennec - Agente de Planilhas

App desktop (Windows) com chat para otimizar planilhas Excel em portugues, com processamento local e checkpoints de seguranca.

## Principais recursos

- Interface compacta estilo assistente (Fennec)
- Indexacao de:
  - planilhas abertas no Excel
  - um ou multiplos arquivos locais (`.xlsx`, `.xlsm`, `.xls`)
  - uma aba ou todas as abas
- MultiPlanilhas: alternar/remover planilhas indexadas na sessao
- Checkpoints automaticos antes de cada alteracao aplicada
- Restauracao de checkpoint pelo botao `Check`
- Sessao limpa com botao `Nova` (evita acumular memoria)
- Integracoes v2 (opcionais por variaveis de ambiente):
  - Gmail (OAuth Google API ou SMTP fallback)
  - Microsoft Teams (webhook)
  - Google Agenda e Google Drive (OAuth guiado)
  - Outlook/Graph (email + calendario corporativo)
  - OneDrive/SharePoint (upload CSV)
  - Trello (API key/token)

## Rodar em modo dev

```bash
cd "e:\Sahara Fenneck"
pip install -r requirements.txt
python main.py
```

## Dependencias externas

- Excel Desktop (para indexacao de planilhas abertas via COM)
- Ollama (para o agente LLM local)

## Build e instalador

- Script de build: `scripts/build_installer.ps1`
- Script Inno Setup: `installer/FennecExcel.iss`
- Bootstrap pos-instalacao: `installer/bootstrap/postinstall.ps1`

Guia rapido em: `installer/README.md`
Integracoes v2: `docs/V2-INTEGRACOES.md`
