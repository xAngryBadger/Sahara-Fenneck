# Installer do Sahara Fennec

Este projeto já inclui um pipeline para distribuir o app para testadores sem exigir Python manual.

## Pré-requisitos para gerar instalador

1. Python 3.11+ no ambiente de build
2. Inno Setup 6 (para compilar o setup final)

## Gerar build e setup

No PowerShell:

```powershell
Set-Location "e:\Sahara Fenneck"
.\scripts\build_installer.ps1
```

Saídas esperadas:

- `dist\FennecExcel\` (app standalone; só existe após build completo)
- **`build\installer\SaharaFennec-Setup.exe`** — **instalador magro** (~alguns MB). **Use este para divulgar.** Instala o código e, na hora, Python + dependências (como qualquer app normal). Exige admin.
- **`build\installer\SaharaFennec-Setup-Legacy.exe`** — instalador pesado (~2 GB). Tudo já embutido; não exige Python no PC. Geração só ocorre se `dist\FennecExcel` existir (build completo).

Para gerar **só os instaladores** (sem rodar PyInstaller de novo):  
`.\scripts\build_installer.ps1 -InnoOnly`  
(Slim é sempre gerado; Legacy só se `dist\FennecExcel` já existir.)

## Smoke test do instalador magro

Antes de divulgar o Slim, rode o smoke test (simula instalação + venv + pip e verifica se o app carrega):

```powershell
Set-Location "e:\Sahara Fenneck"
.\scripts\smoke_test_slim.ps1
```

Requer Python no PATH (`py -3` ou `python`). Se passar, o Slim está consistente com o código e as dependências atuais.

## Ver o instalador (Legacy: música e assistente)

1. Gere o instalador: `.\scripts\build_installer.ps1` ou `-InnoOnly` se dist já existir.
2. Abra `build\installer\`. Para **Legacy** (com música): **SaharaFennec-Setup-Legacy.exe**. Para **magro**: **SaharaFennec-Setup.exe**.
3. No Legacy, a música toca ao abrir; use o botão **Mutar música** à esquerda.

Detalhes e plano de versões (v1.0 backup, v2.0 complementos): ver `docs\INSTALADOR-E-VERSOES.md`.

## Como testar o FennecExcel.exe

- **Sem instalador:** execute direto a pasta do build:  
  `dist\FennecExcel\FennecExcel.exe` (duplo clique ou pelo terminal).
- **Depois de instalar:** use o atalho criado pelo instalador (menu Iniciar ou área de trabalho, conforme escolhido na instalação).

No instalador magro atual, o fluxo padrão já faz a configuração da IA automaticamente: instala o Ollama (se necessário), inicia em background e baixa pelo menos o modelo recomendado para o hardware.

## Desinstalador

O Inno Setup gera um **desinstalador** automaticamente:

- **Menu Iniciar** → Sahara Fennec → **Desinstalar Sahara Fennec**
- **Configurações** → Aplicativos → Sahara Fennec → Desinstalar

Ele remove o app e atalhos; a config em `%APPDATA%\SaharaFennec\` e o Ollama/modelos ficam no PC (podem ser apagados manualmente se quiser).

## Pós-instalação e modelos

O instalador sempre executa o pós-instalação de IA para deixar o app pronto para uso.

Se na instalação a opção **"Escolher modelos adicionais do assistente na próxima tela"** estiver marcada, o assistente mostra uma página **"Modelos Ollama"** com checkboxes:

- **qwen2.5:7b** (recomendado para 16 GB+ RAM) — marcado por padrão
- **qwen2.5:14b** (24 GB+ RAM, ~10 GB VRAM)
- **qwen2.5:3b** (máquinas mais modestas)
- **phi3:mini** (alternativa leve)

O script `installer\bootstrap\postinstall.ps1`:

- detecta RAM/VRAM e grava o modelo **recomendado** em `%APPDATA%\SaharaFennec\settings.json`
- instala o Ollama automaticamente se ele não existir
- inicia o Ollama em background (`localhost:11434`)
- baixa o modelo recomendado automaticamente (e também os modelos extras marcados na tela, se houver)

## Branding do instalador

- `assets\installer_wizard.bmp`
- `assets\installer_small.bmp`
- `assets\fennec_head_icon.ico`

As imagens BMP são geradas por `scripts\make_installer_assets.py` a partir de `assets\installer_fennec.png`.
