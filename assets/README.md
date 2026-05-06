# Assets – Sahara Fennec

## Fundo

- **desert_bg.png** – Imagem de fundo (deserto, dunas, gradiente). Se existir, o app usa em vez do gradiente colorido; senao usa gradiente suave.

## Mascote (Fennec)

- **fennec_mascot_original.png** – Imagem original da mascote (fundo creme).
- **fennec_mascot_transparent.png** – Mesma imagem com fundo removido (PNG transparente), ideal para sobrepor na janela do app.
- **fennec_icon.png** – Ícone 64×64 com transparência para a barra superior da aplicação.
- **fennec_head_icon.png** – Cabecinha do Fennec (PNG transparente): avatar no chat e ícone do app.
- **fennec_head_icon.ico** – Ícone da janela no Windows (gerado a partir do PNG; ver `scripts/make_fennec_ico.py`).

Para gerar de novo a partir da original (após editar a imagem):

```bash
python scripts/remove_bg_mascot.py
```

Requer: `pip install Pillow`
