"""
Gera fennec_head_icon.ico a partir do PNG para o ícone da janela no Windows
(evita quadrado azul quando só PNG é usado).
"""
from pathlib import Path

ASSETS = Path(__file__).resolve().parent.parent / "assets"
PNG = ASSETS / "fennec_head_icon.png"
ICO = ASSETS / "fennec_head_icon.ico"


def main():
    if not PNG.exists():
        print(f"Não encontrado: {PNG}")
        return
    try:
        from PIL import Image
        img = Image.open(PNG).convert("RGBA")
        # ICO com vários tamanhos para Windows
        sizes = [(256, 256), (48, 48), (32, 32), (16, 16)]
        img.save(ICO, format="ICO", sizes=sizes)
        print(f"Salvo: {ICO}")
    except Exception as e:
        print(f"Erro: {e}")


if __name__ == "__main__":
    main()
