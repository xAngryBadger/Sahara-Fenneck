"""
Remove fundo claro (branco/creme) da imagem da mascote Fennec e salva PNG com transparência.
Requer: pip install Pillow
"""
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    raise SystemExit("Instale Pillow: pip install Pillow")

# Caminho da imagem original
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
ASSETS = PROJECT_ROOT / "assets"
SOURCE_IMAGE = ASSETS / "fennec_mascot_original.png"

OUTPUT_TRANSPARENT = ASSETS / "fennec_mascot_transparent.png"
OUTPUT_ICON = ASSETS / "fennec_icon.png"  # versão menor para ícone da barra


def remove_light_background(img: Image.Image, threshold: int = 245) -> Image.Image:
    """
    Torna transparentes pixels de fundo claro (branco/creme).
    threshold: R, G e B acima desse valor (0-255) são considerados fundo.
    """
    img = img.convert("RGBA")
    data = img.getdata()
    new_data = []
    for item in data:
        r, g, b, a = item
        # Fundo: tons muito claros e pouco saturados (branco/creme)
        if r >= threshold and g >= threshold and b >= threshold:
            new_data.append((255, 255, 255, 0))
        else:
            new_data.append(item)
    img.putdata(new_data)
    return img


def main():
    ASSETS.mkdir(parents=True, exist_ok=True)
    if not SOURCE_IMAGE.exists():
        print(f"Imagem não encontrada: {SOURCE_IMAGE}")
        print("Coloque a imagem da mascote em assets/fennec_mascot_original.png")
        return
    img = Image.open(SOURCE_IMAGE).convert("RGBA")
    # Threshold 245 preserva o bege claro do fennec e remove só o fundo mais claro
    out = remove_light_background(img, threshold=245)
    out.save(OUTPUT_TRANSPARENT, "PNG")
    print(f"Salvo: {OUTPUT_TRANSPARENT}")

    # Ícone menor (ex.: 64x64) para barra do app
    size = (64, 64)
    icon = out.resize(size, Image.Resampling.LANCZOS)
    icon.save(OUTPUT_ICON, "PNG")
    print(f"Salvo ícone: {OUTPUT_ICON}")


if __name__ == "__main__":
    main()
