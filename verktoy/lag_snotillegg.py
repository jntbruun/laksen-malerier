"""Lager ressurspakker/4 Laksen snøtillegg: snø på løv som Snowy Better Leaves mangler, og på mose.

Snowy Better Leaves dekker bare åtte løvtyper. Her lages de samme filene for asalea,
blomstrende asalea, pale oak og de tre poppeltypene, med snøen lagt på nøyaktig de pikslene
der patchen har snø på eik. Mose og pale moss får snøtoppen og snøkanten fra Winter Pack.

Kjør:  .venv/bin/python verktoy/lag_snotillegg.py
"""

import json
import shutil
from pathlib import Path

from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parent.parent
PACKS = ROOT / "ressurspakker"
BETTER_LEAVES = PACKS / "1 Better Leaves 9.6" / "assets" / "minecraft"
WINTER = PACKS / "2 Winter Pack" / "assets" / "minecraft"
SNOWY = PACKS / "3 Snowy Better Leaves Patch" / "assets" / "minecraft"
OUT = PACKS / "4 Laksen snøtillegg"
ASSETS = OUT / "assets" / "minecraft"

LEAVES = ["azalea_leaves", "flowering_azalea_leaves", "pale_oak_leaves",
          "red_poplar_leaves", "orange_poplar_leaves", "yellow_poplar_leaves"]
TEMPLATE = "oak_leaves"  # the patch's oak files are the pattern for every new type


def rgba(path: Path) -> Image.Image:
    return Image.open(path).convert("RGBA")


def is_snow(pixel) -> bool:
    r, g, b, a = pixel
    return a > 0 and min(r, g, b) >= 190 and max(r, g, b) - min(r, g, b) <= 45


def add_snow(base: Image.Image, snowy_template: Image.Image) -> Image.Image:
    """Copy the template's snow pixels onto the base texture, same positions."""
    out = base.copy()
    for y in range(base.height):
        for x in range(base.width):
            p = snowy_template.getpixel((x, y))
            if is_snow(p):
                out.putpixel((x, y), p)
    return out


def full_snow(template: Image.Image, side: Image.Image) -> Image.Image:
    """Mostly snow (the top tile): keep the snow, show this leaf's own colour through the gaps."""
    out = template.copy()
    for y in range(template.height):
        for x in range(template.width):
            if not is_snow(template.getpixel((x, y))):
                out.putpixel((x, y), side.getpixel((x, y)))
    return out


def dusted(side: Image.Image, amount: float = 0.55) -> Image.Image:
    """Fallback top without Continuity: the leaves lightened towards snow white."""
    white = Image.new("RGBA", side.size, (240, 248, 252, 255))
    out = Image.blend(side, white, amount)
    out.putalpha(side.getchannel("A"))
    return out


def save(image: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, optimize=True)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def make_leaves(name: str) -> None:
    bush = rgba(BETTER_LEAVES / "textures/block" / f"{name}.png")           # 32x32 round Better Leaves texture
    side = bush.crop((8, 8, 24, 24))                                       # its centre is the plain leaf texture
    t = SNOWY / "textures/block"
    ctm_t = SNOWY / "optifine/ctm" / TEMPLATE

    tex = ASSETS / "textures/block"
    save(side, tex / f"{name}_snowy_side.png")
    save(side, tex / f"{name}_snowy_bottom.png")
    save(dusted(side), tex / f"{name}_snowy_top.png")
    save(add_snow(bush, rgba(t / f"{TEMPLATE}_snowy_bush.png")), tex / f"{name}_snowy_bush.png")

    ctm = ASSETS / "optifine/ctm" / name
    save(side, ctm / "0.png")
    save(ImageOps.mirror(side), ctm / "1.png")
    save(add_snow(side, rgba(ctm_t / "2.png")), ctm / "2.png")
    save(add_snow(ImageOps.mirror(side), rgba(ctm_t / "3.png")), ctm / "3.png")
    save(full_snow(rgba(ctm_t / "4.png"), side), ctm / "4.png")
    save(bush, ctm / "5.png")
    save(add_snow(bush, rgba(ctm_t / "6.png")), ctm / "6.png")

    # Same models, blockstate and Continuity rules as oak, with the names swapped.
    for src in list((SNOWY / "models/block").glob(f"{TEMPLATE}*.json")) + [SNOWY / "blockstates" / f"{TEMPLATE}.json"]:
        kind = "models/block" if "models" in src.parts else "blockstates"
        write_text(ASSETS / kind / src.name.replace(TEMPLATE, name), src.read_text().replace(TEMPLATE, name))
    for src in ctm_t.glob("*.properties"):
        write_text(ctm / src.name.replace(TEMPLATE, name), src.read_text().replace(TEMPLATE, name))


def make_moss() -> None:
    import io, zipfile
    jar = zipfile.ZipFile(Path.home() / "Library/Application Support/minecraft/versions/26.3/26.3.jar")
    snow_top = "minecraft:block/grass_block/grass_block_top"                  # Winter Pack's snow top
    winter_side = rgba(WINTER / "textures/block/grass_block/grass_block_side.png")  # dirt with a snow cap
    for block in ["moss_block", "pale_moss_block"]:
        moss = Image.open(io.BytesIO(jar.read(f"assets/minecraft/textures/block/{block}.png"))).convert("RGBA")
        save(add_snow(moss, winter_side), ASSETS / "textures/block" / f"{block}_snowy_side.png")
        model = {"parent": "minecraft:block/cube_bottom_top",
                 "textures": {"top": snow_top, "bottom": f"minecraft:block/{block}",
                              "side": f"minecraft:block/{block}_snowy_side"}}
        write_text(ASSETS / "models/block" / f"{block}.json", json.dumps(model, indent=2))
    # Carpets: snow on top, moss on the thin sides.
    for carpet, block in [("moss_carpet", "moss_block"), ("pale_moss_carpet", "pale_moss_block")]:
        model = {"parent": "minecraft:block/thin_block",
                 "textures": {"particle": f"minecraft:block/{block}", "top": snow_top,
                              "side": f"minecraft:block/{block}"},
                 "elements": [{"from": [0, 0, 0], "to": [16, 1, 16], "faces": {
                     "down": {"uv": [0, 0, 16, 16], "texture": "#side", "cullface": "down"},
                     "up": {"uv": [0, 0, 16, 16], "texture": "#top"},
                     "north": {"uv": [0, 15, 16, 16], "texture": "#side", "cullface": "north"},
                     "south": {"uv": [0, 15, 16, 16], "texture": "#side", "cullface": "south"},
                     "west": {"uv": [0, 15, 16, 16], "texture": "#side", "cullface": "west"},
                     "east": {"uv": [0, 15, 16, 16], "texture": "#side", "cullface": "east"}}}]}
        write_text(ASSETS / "models/block" / f"{carpet}.json", json.dumps(model, indent=2))


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    for name in LEAVES:
        make_leaves(name)
    make_moss()
    write_text(OUT / "LESMEG.txt", "Laget av verktoy/lag_snotillegg.py. Ikke rediger for hånd; endre skriptet og kjør det på nytt.\n")
    print(f"Laget {sum(1 for p in OUT.rglob('*') if p.is_file())} filer i {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
