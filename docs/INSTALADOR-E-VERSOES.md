# Instalador e versões (Sahara Fennec)

## Resumo: o que instala o quê

| O que o usuário clica | O que acontece |
|------------------------|----------------|
| **SaharaFennec-Setup.exe** (instalador) | Instala o app (copia arquivos, cria atalhos), roda o pós-instalação que **detecta RAM/VRAM**, escolhe o modelo Ollama recomendado, grava a config e pode baixar o modelo. Ou seja: o usuário não mexe em nada técnico; tudo é baseado no hardware. |
| **FennecExcel.exe** (dentro de `dist\FennecExcel\` ou após instalar) | Só **abre o aplicativo**. Não instala nada. |

Conclusão: ao clicar no **instalador**, o app (já empacotado com Python e bibliotecas dentro) é copiado para o PC e configurado com base no hardware. O executável sozinho (FennecExcel.exe) é apenas o app.

**Por que o instalador tem ~2 GB?** Hoje o app é um **pacote autocontido** (PyInstaller): Python + todas as dependências (incluindo torch, transformers, etc.) vêm *dentro* do FennecExcel. O instalador só compacta e copia isso. Uma alternativa futura seria um instalador “magro” que, como admin, instala Python no sistema, roda `pip install -r requirements.txt` e baixa o código — instalador pequeno, mas exige rede e permissão de admin na primeira execução.

---

## Como gerar e rodar o instalador

### Pré-requisito

- **Inno Setup 6** instalado (para gerar o Setup.exe).  
  Download: <https://jrsoftware.org/isinfo.php>  

### Gerar o instalador

No PowerShell, na raiz do projeto:

```powershell
Set-Location "e:\Sahara Fenneck"
.\scripts\build_installer.ps1
```

(Use `.\scripts\build_installer.ps1 -SkipPip` se não quiser atualizar o PyInstaller.)

Saídas:

- `dist\FennecExcel\` — app empacotado (FennecExcel.exe e dependências).
- `build\installer\SaharaFennec-Setup.exe` — instalador (música, botão Mutar/Desmutar, pós-instalação).

### Ver a música e o instalador

1. Gere o instalador (comando acima).
2. Abra a pasta: `e:\Sahara Fenneck\build\installer\`.
3. Dê duplo clique em **SaharaFennec-Setup.exe**.

Você verá o assistente com a música e o botão **Mutar música** / **Ouvir música** à esquerda (não sobrepõe Avançar).

### Rodar o instalador “dentro” do Docker

O instalador é um **setup Windows com interface gráfica e som**. Para “rodar o instalador no Docker” você teria que:

- Usar uma **imagem Windows** (Windows Server Core ou similar).
- Ter um jeito de **ver a tela** (RDP para o container ou ambiente com GUI).

Isso é pesado e pouco comum para só “ver como está o instalador”. O caminho prático é rodar o **SaharaFennec-Setup.exe** direto no seu Windows (ou numa VM Windows).

Se no futuro quiser usar Docker só para **construir** o instalador (gerar o .exe), isso exigiria um container Windows com Inno Setup e o script de build; o resultado seria o mesmo SaharaFennec-Setup.exe que você pode abrir no seu PC para testar música e fluxo.

---

## Plano de instalações: v1.0 (backup) e v2.0 (complementos)

### 1) Backup da versão 1.0

Antes de começar a v2.0, guardar a versão atual como “1.0”:

- **Opção A (recomendada se usar Git):**  
  Criar tag e branch de release:

  ```text
  git tag v1.0.0
  git branch release/1.0
  git push origin v1.0.0 release/1.0   # se usar remoto
  ```

- **Opção B (cópia física):**  
  Copiar o projeto inteiro para uma pasta de backup, por exemplo:

  ```text
  releases\SaharaFennec-1.0\
  ```

  ou

  ```text
  backup-SaharaFennec-1.0-YYYYMMDD\
  ```

- **Opção C:**  
  Gerar o instalador da v1.0 e guardar o **SaharaFennec-Setup.exe** (e, se quiser, a pasta `dist\FennecExcel\`) em um lugar fixo (ex.: `releases\v1.0\`).

Assim você sempre tem a “versão 1.0 que fizemos” disponível.

### 2) Versão 2.0 com complementos

- **Complementos** = integrações/recursos extras (ex.: Google Calendar, Microsoft Teams, Gmail, etc.).
- A **instalação** pode ser:
  - **Um único instalador v2.0** que já inclui o app + complementos (tudo no mesmo SaharaFennec-Setup.exe), ou
  - **Instalador base (v2.0) + pacotes opcionais** (ex.: “Sahara Fennec + Integrações”) escolhidos na instalação.

Sugestão de passos:

1. **Backup v1.0** (tag + branch ou cópia + guardar instalador da v1.0).
2. **Criar branch ou pasta de desenvolvimento v2.0** (ex.: `develop` ou `release/2.0`).
3. **Implementar complementos** na v2.0 (APIs, OAuth, etc.).
4. **Manter um único script de build** (`build_installer.ps1`) que:
   - Gera o app (PyInstaller) e
   - Gera o instalador (Inno Setup) com a versão correta (1.0 ou 2.0) no nome/numero (ex.: `SaharaFennec-Setup-2.0.exe`).
5. **Instalações que teremos:**
   - **v1.0:** instalador e/ou zip da pasta `dist` guardados em `releases\v1.0\` (ou equivalente).
   - **v2.0:** novo instalador (e opcionalmente pacotes extras) gerado pelo mesmo pipeline, com versão 2.0 no Inno Setup e no app.

Resumo: o app “funciona” no sentido de que **quem instala é o SaharaFennec-Setup.exe**; ele instala tudo e usa o hardware para configurar o Ollama. Para ver a música e o instalador, gere o Setup com o script e abra o exe na pasta `build\installer`. Para as instalações futuras, faça backup da v1.0 (tag + cópia/instalador) e planeje a v2.0 como um único instalador (ou base + complementos opcionais) gerado pelo mesmo processo de build.
