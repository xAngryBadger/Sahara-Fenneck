# Análise Completa do Instalador Slim - Sahara Fennec

## Compatibilidade

| Requisito | Status |
|-----------|--------|
| Windows 10 (10.0) | ✅ MinVersion no Inno Setup |
| Windows 11 | ✅ Compatível |
| 64-bit | ✅ ArchitecturesInstallIn64BitMode=x64 |
| Admin | ✅ PrivilegesRequired=admin (UAC solicita automaticamente) |

## Fluxo do Usuário (Zero Interação)

1. **Baixa** o SaharaFennec-Setup.exe
2. **Executa** → Windows pede admin (UAC) → usuário clica Sim
3. **Avançar** → escolhe pasta (ou mantém padrão) → Avançar
4. **Aguarda** → setup_slim.ps1 roda (Miniconda + pip + opcional Ollama)
5. **Concluir** → app abre

Nenhuma pergunta técnica. Nenhum comando manual.

## O Que o Setup Faz (setup_slim.ps1)

1. **Python**: Miniconda em `%LOCALAPPDATA%\SaharaFennec\Miniconda3` ou Python do sistema
2. **Conda ToS**: Aceita termos automaticamente (pkgs/main, pkgs/r, pkgs/msys2)
3. **Ambiente**: `conda create -n fennec python=3.12` ou `python -m venv venv`
4. **Dependências**: `pip install -r requirements-slim.txt`
5. **Launcher**: Salva path do Python em `%APPDATA%\SaharaFennec\launcher_config.txt` (não precisa de admin para escrever)
6. **Ollama** (opcional): Se marcado, baixa modelos. Em falha, remove parcial com `ollama rm`

## Rollback em Falha

| Falha | Limpeza |
|-------|---------|
| Download Miniconda | Remove `%TEMP%\SaharaFennec\` |
| Instalação Miniconda | Remove `%TEMP%\SaharaFennec\` |
| Criação env conda | Remove Miniconda + temp |
| Ollama pull | `ollama rm <modelo>` para o que falhou |
| Sucesso | Remove `%TEMP%\SaharaFennec\` |

## Desinstalação

- Remove app de Programas e Recursos
- Remove `%TEMP%\SaharaFennec\` (arquivos temporários)
- **Não remove**: Miniconda em %LOCALAPPDATA%, modelos Ollama, settings em %APPDATA%

(O usuário pode deletar manualmente `%LOCALAPPDATA%\SaharaFennec` e `%APPDATA%\SaharaFennec` se quiser limpeza total.)

## Arquivos Críticos

| Arquivo | Função |
|---------|--------|
| `run_fennec.bat` | Inicia app. Se ambiente ausente, chama setup_slim |
| `configurar_ambiente.bat` | Setup manual (se run_fennec falhar) |
| `bootstrap\setup_slim.ps1` | Miniconda + venv + pip |
| `bootstrap\postinstall.ps1` | Ollama + modelos (opcional) |

## Launcher (run_fennec.bat)

Ordem de busca do Python:

1. `venv\Scripts\pythonw.exe` (local)
2. `%LOCALAPPDATA%\SaharaFennec\Miniconda3\envs\fennec\pythonw.exe`
3. `%APPDATA%\SaharaFennec\launcher_config.txt` (path salvo)

Se nenhum existir → executa setup_slim automaticamente.

## Correções Aplicadas (esta sessão)

- **Path com aspas**: AppDir sem barra final no Inno (evita escape)
- **Conda ToS**: Aceita termos antes de `conda create`
- **Launcher em APPDATA**: Não precisa de admin para escrever em Program Files
- **Rollback**: Limpa temp e Miniconda parcial em falha
- **Ollama**: `ollama rm` em falha de pull
- **MinVersion**: Windows 10+
- **UninstallRun**: Limpa temp na desinstalação
- **Python 3.11**: Adicionado à busca de Python do sistema
