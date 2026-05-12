# Status do projeto – Sahara Fennec

## Estado atual

### Frontend
- Janela única com tema deserto, avatar do Fennec, bolhas de chat, input com botão de patinha, ações principais e botões laterais.
- Barra superior com Pin, Check e Config.
- Fundo por imagem (`assets/desert_bg.png`) com fallback para gradiente.

### Backend
- `src/indexing/excel_reader.py`
  - `index_from_excel()` para Excel aberto via `pywin32`.
  - `index_from_path()` para `.xlsx` via `openpyxl` + `pandas`.
- `src/checkpoints/manager.py`
  - Salva checkpoint antes de cada alteração do agente.
  - Lista e restaura checkpoints por planilha.
- `src/agent/`
  - `ollama_client.py` para chamadas ao Ollama local.
  - `tools.py` com GetData + Optimize (validação de código, aplicação em tempo real, checkpoint).
  - `runner.py` com loop ReAct básico por bloco `[OPTIMIZE]...[/OPTIMIZE]`.
- `src/gui/main_window.py`
  - Indexação em thread (Excel aberto ou arquivo).
  - Envio de query em thread para o agente.
  - Tela de checkpoints com ação de restauração.

## Testes executados (smoke)
- Compilação de módulos (`compileall`) sem erro de sintaxe.
- Import de módulos críticos com warnings habilitados.
- Fluxo backend validado:
  - indexação de `.xlsx`
  - optimize com alteração real no arquivo
  - criação e restauração de checkpoint
- Fluxo do agente validado com cliente Ollama simulado:
  - bloco `[OPTIMIZE]` aplicado
  - checkpoint criado
  - resultado final retornado

## Próximos passos recomendados
1. Implementar Config/Ajuda na GUI.
2. Melhorar sandbox de execução de código do Optimize.
3. Adicionar testes automatizados formais (pytest).
4. Empacotar com PyInstaller + instalador (Inno Setup/NSIS).
