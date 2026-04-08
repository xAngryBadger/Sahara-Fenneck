"""
Remove fundo preto da cabecinha do Fennec e regenera o .ico.
"""
from pathlib import Path
from PIL import Image
import numpy as np

ASSETS = Path(__file__).resolve().parent.parent / "assets"
SRC = ASSETS / "fennec_head_icon.png"
OUT_PNG = ASSETS / "fennec_head_clean.png"
OUT_ICO = ASSETS / "fennec_head_icon.ico"


def remove_dark_bg(img: Image.Image, threshold: int = 40) -> Image.Image:
    """Torna transparentes pixels escuros (fundo preto/quase preto)."""
    img = img.convert("RGBA")
    data = np.array(img)
    r, g, b, a = data[:, :, 0], data[:, :, 1], data[:, :, 2], data[:, :, 3]
    mask = (r < threshold) & (g < threshold) & (b < threshold)
    data[mask, 3] = 0
    # Suavizar bordas: pixels quase pretos ficam semi-transparentes
    near_mask = (r < threshold + 30) & (g < threshold + 30) & (b < threshold + 30) & ~mask
    brightness = (r[near_mask].astype(int) + g[near_mask].astype(int) + b[near_mask].astype(int)) // 3
    data[near_mask, 3] = np.clip(brightness * 3, 0, 255).astype(np.uint8)
    return Image.fromarray(data)


def main():
    if not SRC.exists():
        print(f"Nao encontrado: {SRC}")
        return
    img = Image.open(SRC).convert("RGBA")
    clean = remove_dark_bg(img)
    # Crop para remover excesso de transparencia ao redor
    bbox = clean.getbbox()
    if bbox:
        clean = clean.crop(bbox)
    clean.save(OUT_PNG, "PNG")
    print(f"Salvo: {OUT_PNG}")
    # Gerar .ico
    clean.save(OUT_ICO, format="ICO", sizes=[(256, 256), (48, 48), (32, 32), (16, 16)])
    print(f"Salvo: {OUT_ICO}")
    # Substituir o original
    clean.save(SRC, "PNG")
    print(f"Atualizado original: {SRC}")


if __name__ == "__main__":
    main()
