"""Bygger Laksen-malerier: datapack + resource pack fra bildene i malerier/.

Filnavn = navnet på maleriet. Undermappe = kunstner.
    malerier/Solnedgang over fjorden.jpg          -> tittel, størrelse velges automatisk
    malerier/Jonathan/Laksen (3x2).png            -> 3 blokker bredt, 2 høyt, kunstner "Jonathan"

Kjør:  .venv/bin/python build.py   (eller dobbeltklikk "Bygg malerier.command" på Mac)
"""

from __future__ import annotations

import hashlib
import io
import json
import re
import sys
import unicodedata
import zipfile
from pathlib import Path

from PIL import Image, ImageOps

NAMESPACE = "laksen"
# Vanilla er 16 px per blokk. 256 gir skarpe bilder; atlaset blir ~4600² (ca. 85 MB VRAM).
PX_PER_BLOCK = 256
AUTO_LONGEST_SIDE = 4  # blokker, når filnavnet ikke sier noe annet
MAX_SIDE = 16  # Minecraft sin grense for malerier
# True: tilfeldig plasserte malerier (vanlig painting-item) blir bare deres egne.
ONLY_OWN_PAINTINGS_WHEN_RANDOM = True

DATA_PACK_FORMAT = 121  # Minecraft 26.3
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tif", ".tiff"}

ROOT = Path(__file__).resolve().parent
PAINTINGS_DIR = ROOT / "malerier"
BASE_RESOURCE_PACK = ROOT / "base-resourcepack"
LOCK_FILE = ROOT / "malerier.lock.json"
# Every variant the old datapacks (Splotch of Paint, REPO Paintings) registered. Kept so paintings
# already hanging in the world survive after those datapacks are removed.
OLD_VARIANTS_FILE = ROOT / "gamle-malerier.json"
DIST = ROOT / "dist"
DATAPACK_ZIP = DIST / "laksen-malerier-datapack.zip"
RESOURCE_PACK_ZIP = DIST / "laksen-ressurspakke.zip"

SIZE_SUFFIX = re.compile(r"^(?P<title>.*?)\s*\(\s*(?P<w>\d+)\s*[xX×]\s*(?P<h>\d+)\s*\)$")


def slugify(text: str) -> str:
    text = text.lower().replace("æ", "ae").replace("ø", "o").replace("å", "aa")
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", text).strip("_") or "maleri"


def auto_size(width_px: int, height_px: int) -> tuple[int, int]:
    ratio = width_px / height_px
    if ratio >= 1:
        return AUTO_LONGEST_SIDE, max(1, round(AUTO_LONGEST_SIDE / ratio))
    return max(1, round(AUTO_LONGEST_SIDE * ratio)), AUTO_LONGEST_SIDE


def file_sha1(path: Path) -> str:
    return hashlib.sha1(path.read_bytes()).hexdigest()


def collect_paintings() -> list[dict]:
    found = []
    for path in sorted(PAINTINGS_DIR.rglob("*")):
        if not path.is_file() or path.name.startswith("."):
            continue
        if path.suffix.lower() not in IMAGE_SUFFIXES:
            print(f"  hopper over {path.relative_to(ROOT)} (ikke et bildeformat jeg kan lese; bruk png/jpg)")
            continue
        relative = path.relative_to(PAINTINGS_DIR)
        author = relative.parts[0] if len(relative.parts) > 1 else None
        match = SIZE_SUFFIX.match(path.stem)
        title = (match["title"] if match else path.stem).strip()
        size = (int(match["w"]), int(match["h"])) if match else None
        found.append({"path": path, "file": relative.as_posix(), "title": title, "author": author, "size": size})
    return found


def assign_stable_ids(paintings: list[dict]) -> None:
    """Placed paintings reference the variant id, so an id must never change.
    Match by image content first (survives renames), then by file path (survives edits).
    Ids are full "namespace:name": old paintings keep the ids their original datapacks gave them."""
    lock = json.loads(LOCK_FILE.read_text()) if LOCK_FILE.exists() else []
    by_sha = {entry["sha1"]: entry for entry in lock}
    by_file = {entry["file"]: entry for entry in lock}
    used_ids = {entry["id"] for entry in lock} | {a["id"] for entry in lock for a in entry.get("aliases", [])}
    claimed: set[str] = set()

    for painting in paintings:
        painting["sha1"] = file_sha1(painting["path"])
        previous = by_sha.get(painting["sha1"]) or by_file.get(painting["file"])
        if previous and previous["id"] not in claimed:
            painting["id"] = previous["id"]
            painting["aliases"] = previous.get("aliases", [])
        else:
            base = slugify(painting["title"])
            candidate, n = f"{NAMESPACE}:{base}", 2
            while candidate in used_ids or candidate in claimed:
                candidate, n = f"{NAMESPACE}:{base}_{n}", n + 1
            painting["id"], painting["aliases"] = candidate, []
        claimed.add(painting["id"])

    current = []
    for p in paintings:
        entry = {"id": p["id"], "file": p["file"], "sha1": p["sha1"]}
        if p["aliases"]:
            entry["aliases"] = p["aliases"]
        current.append(entry)
    # Keep entries for deleted images so their ids are never handed to a different painting.
    gone = [dict(entry, removed=True) for entry in lock if entry["id"] not in claimed]
    for entry in lock:
        if entry["id"] not in claimed and not entry.get("removed"):
            print(f"  ADVARSEL: {entry['file']} er borte. Slike malerier som allerede henger i verden forsvinner.")
    LOCK_FILE.write_text(json.dumps(current + gone, indent=2, ensure_ascii=False) + "\n")


def split_id(painting_id: str) -> tuple[str, str]:
    namespace, path = painting_id.split(":", 1)
    return namespace, path


def render_texture(painting: dict) -> Image.Image:
    with Image.open(painting["path"]) as source:
        image = ImageOps.exif_transpose(source).convert("RGB")
    width, height = painting["size"] or auto_size(*image.size)
    if not (1 <= width <= MAX_SIDE and 1 <= height <= MAX_SIDE):
        sys.exit(f"FEIL: {painting['file']}: størrelse {width}x{height} er utenfor 1-{MAX_SIDE} blokker.")
    painting["width"], painting["height"] = width, height
    # Stretch, never crop: nothing in the picture disappears, and it matches how Minecraft drew the old ones.
    return image.resize((width * PX_PER_BLOCK, height * PX_PER_BLOCK), Image.Resampling.LANCZOS)


ICON_SIZE = 64
FRAME_COLOR = (92, 60, 32, 255)


def render_icon(texture: Image.Image, width: int, height: int) -> bytes:
    """Square item icon: the painting in its own proportions, in a thin wooden frame."""
    longest = ICON_SIZE - 4
    frame_w = longest if width >= height else max(8, round(longest * width / height))
    frame_h = longest if height >= width else max(8, round(longest * height / width))
    framed = Image.new("RGBA", (frame_w, frame_h), FRAME_COLOR)
    framed.paste(texture.resize((frame_w - 4, frame_h - 4), Image.Resampling.LANCZOS), (2, 2))
    icon = Image.new("RGBA", (ICON_SIZE, ICON_SIZE), (0, 0, 0, 0))
    icon.paste(framed, ((ICON_SIZE - frame_w) // 2, (ICON_SIZE - frame_h) // 2))
    return png_bytes(icon)


def png_bytes(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, "PNG", optimize=True)
    return buffer.getvalue()


def stonecutter_entries(paintings: list[dict]) -> list[tuple[str, str, int, int, dict]]:
    """(variant id, recipe name, width, height, painting) for every painting with its own picture,
    including the old duplicate ids, which are separate paintings with their own size."""
    entries = []
    for p in paintings:
        entries.append((p["id"], slugify(p["title"]), p["width"], p["height"], p))
        for alias in p["aliases"]:
            entries.append((alias["id"], f"{slugify(p['title'])}_{alias['width']}x{alias['height']}",
                            alias["width"], alias["height"], p))
    return entries


def write_file(archive: zipfile.ZipFile, name: str, data: bytes | str) -> None:
    # Fixed timestamp: identical input gives an identical zip, so the sha1 only changes when content does.
    info = zipfile.ZipInfo(name, date_time=(2020, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    archive.writestr(info, data)


def write_json(archive: zipfile.ZipFile, name: str, data: dict) -> None:
    write_file(archive, name, json.dumps(data, indent=2, ensure_ascii=False))


def check_old_sizes(paintings: list[dict], old_variants: dict) -> None:
    for p in paintings:
        old = old_variants.get(p["id"])
        if old and (p["width"], p["height"]) != (old["width"], old["height"]):
            sys.exit(f"FEIL: {p['file']} må være {old['width']}x{old['height']}, ellers endrer malerier som "
                     f"allerede henger størrelse. Sett ({old['width']}x{old['height']}) i filnavnet.")


def build_datapack(paintings: list[dict], old_variants: dict) -> None:
    defined = {p["id"] for p in paintings} | {a["id"] for p in paintings for a in p["aliases"]}
    with zipfile.ZipFile(DATAPACK_ZIP, "w", zipfile.ZIP_DEFLATED) as archive:
        for old_id, variant in old_variants.items():
            if old_id not in defined:
                namespace, path = split_id(old_id)
                write_json(archive, f"data/{namespace}/painting_variant/{path}.json", variant)
        write_json(archive, "pack.mcmeta", {"pack": {
            "description": f"Laksen malerier ({len(paintings)} stk). Legg et maleri i en stonecutter.",
            "min_format": DATA_PACK_FORMAT,
            "max_format": 999,
        }})
        recipe_names: set[str] = set()
        for p in paintings:
            variant = {
                "asset_id": p["id"],
                "width": p["width"],
                "height": p["height"],
                "title": {"text": p["title"], "color": "yellow"},
            }
            if p["author"]:
                variant["author"] = {"text": p["author"], "color": "gray"}
            namespace, path = split_id(p["id"])
            write_json(archive, f"data/{namespace}/painting_variant/{path}.json", variant)
            # Aliases: duplicate ids from the old datapacks. Registered so placed ones survive,
            # but left out of the stonecutter and random placement.
            for alias in p["aliases"]:
                alias_namespace, alias_path = split_id(alias["id"])
                write_json(archive, f"data/{alias_namespace}/painting_variant/{alias_path}.json",
                           dict(variant, width=alias["width"], height=alias["height"]))
        # Recipe ids follow the title: the stonecutter lists recipes in id order, so this keeps it alphabetical.
        for variant_id, recipe_name, _, _, _ in stonecutter_entries(paintings):
            name, n = recipe_name, 2
            while name in recipe_names:
                name, n = f"{recipe_name}_{n}", n + 1
            recipe_names.add(name)
            write_json(archive, f"data/{NAMESPACE}/recipe/maleri/{name}.json", {
                "type": "minecraft:stonecutting",
                "ingredient": "minecraft:painting",
                "result": {
                    "id": "minecraft:painting",
                    "count": 1,
                    "components": {"minecraft:painting/variant": variant_id},
                },
            })
        ids = [p["id"] for p in paintings]
        write_json(archive, f"data/{NAMESPACE}/tags/painting_variant/alle.json", {"values": ids})
        write_json(archive, "data/minecraft/tags/painting_variant/placeable.json",
                   {"replace": ONLY_OWN_PAINTINGS_WHEN_RANDOM, "values": ids})


def build_resource_pack(paintings: list[dict], textures: dict[str, Image.Image]) -> None:
    with zipfile.ZipFile(RESOURCE_PACK_ZIP, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(BASE_RESOURCE_PACK.rglob("*")):
            if path.is_file() and path.name != ".DS_Store":
                write_file(archive, path.relative_to(BASE_RESOURCE_PACK).as_posix(), path.read_bytes())
        for painting_id, texture in sorted(textures.items()):
            namespace, path = split_id(painting_id)
            write_file(archive, f"assets/{namespace}/textures/painting/{path}.png", png_bytes(texture))

        # Each painting item shows its own picture, so the stonecutter is a visual picker.
        cases = []
        for variant_id, _, width, height, p in stonecutter_entries(paintings):
            namespace, path = split_id(variant_id)
            icon = f"maleri/{namespace}/{path}"
            write_file(archive, f"assets/{NAMESPACE}/textures/item/{icon}.png",
                       render_icon(textures[p["id"]], width, height))
            write_json(archive, f"assets/{NAMESPACE}/models/item/{icon}.json",
                       {"parent": "minecraft:item/generated", "textures": {"layer0": f"{NAMESPACE}:item/{icon}"}})
            cases.append({"when": variant_id, "model": {"type": "minecraft:model", "model": f"{NAMESPACE}:item/{icon}"}})
        write_json(archive, "assets/minecraft/items/painting.json", {"model": {
            "type": "minecraft:select",
            "property": "minecraft:component",
            "component": "minecraft:painting/variant",
            "cases": cases,
            "fallback": {"type": "minecraft:model", "model": "minecraft:item/painting"},
        }})


def main() -> None:
    DIST.mkdir(exist_ok=True)
    paintings = collect_paintings()
    if not paintings:
        sys.exit("Fant ingen bilder i malerier/.")
    print(f"Fant {len(paintings)} malerier. Skalerer bilder ...")
    assign_stable_ids(paintings)
    textures = {p["id"]: render_texture(p) for p in paintings}
    paintings.sort(key=lambda p: p["title"].lower())

    old_variants = json.loads(OLD_VARIANTS_FILE.read_text()) if OLD_VARIANTS_FILE.exists() else {}
    check_old_sizes(paintings, old_variants)
    build_datapack(paintings, old_variants)
    build_resource_pack(paintings, textures)

    resource_sha1 = file_sha1(RESOURCE_PACK_ZIP)
    (DIST / "ressurspakke-sha1.txt").write_text(resource_sha1 + "\n")
    size_mb = RESOURCE_PACK_ZIP.stat().st_size / 1_000_000
    print(f"\nFerdig.\n  Datapack:      {DATAPACK_ZIP.relative_to(ROOT)}")
    print(f"  Resource pack: {RESOURCE_PACK_ZIP.relative_to(ROOT)} ({size_mb:.1f} MB)")
    print(f"  SHA-1:         {resource_sha1}  (lim inn som resource-pack-sha1 i server.properties)")


if __name__ == "__main__":
    main()
