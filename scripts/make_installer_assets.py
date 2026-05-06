# -*- coding: utf-8 -*-
"""Gera imagens BMP para o Inno Setup a partir do PNG do Fennec."""
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
SRC = ASSETS / "installer_fennec.png"
WIZARD_BMP = ASSETS / "installer_wizard.bmp"
SMALL_BMP = ASSETS / "installer_small.bmp"


def fit_cover(img: Image.Image, size: tuple[int, int]) -> Image.Image:
    sw, sh = size
    ratio = max(sw / img.width, sh / img.height)
    nw, nh = int(img.width * ratio), int(img.height * ratio)
    resized = img.resize((nw, nh), Image.Resampling.LANCZOS)
    left = (nw - sw) // 2
    top = (nh - sh) // 2
    return resized.crop((left, top, left + sw, top + sh))


def main():
    if not SRC.exists():
        raise SystemExit(f"Imagem não encontrada: {SRC}")

    img = Image.open(SRC).convert("RGB")
    fit_cover(img, (164, 314)).save(WIZARD_BMP, format="BMP")
    fit_cover(img, (55, 55)).save(SMALL_BMP, format="BMP")
    print(f"Gerado: {WIZARD_BMP}")
    print(f"Gerado: {SMALL_BMP}")


if __name__ == "__main__":
    main()
