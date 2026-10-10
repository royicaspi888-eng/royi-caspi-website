#!/usr/bin/env python3
"""Create smaller portfolio previews and zoom versions, preserving original files."""
from pathlib import Path
from PIL import Image, ImageOps
import hashlib, json, re

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "index.html"
html = PAGE.read_text(encoding="utf-8")
out = ROOT / "assets" / "optimized"
out.mkdir(parents=True, exist_ok=True)
first = html.find("const works = [")
last = html.find("];", first)
if first < 0 or last < 0:
    raise RuntimeError("Cannot locate gallery list")
section = html[first:last]
originals = list(dict.fromkeys(re.findall(r'"([^"]+\.(?:jpg|jpeg))"', section, flags=re.I)))
# Avoid running the conversion again once references have already been updated.
originals = [name for name in originals if not name.startswith("assets/optimized/")]

def make_webp(source, path, max_edge, quality):
    with Image.open(source) as raw:
        im = ImageOps.exif_transpose(raw)
        if im.mode not in ("RGB", "RGBA"):
            im = im.convert("RGB")
        im.thumbnail((max_edge, max_edge), Image.Resampling.LANCZOS)
        im.save(path, "WEBP", quality=quality, method=5)
    return path.stat().st_size

mapping = {}
total_before = total_after = 0
for name in originals:
    source = ROOT / name
    if not source.is_file():
        raise FileNotFoundError(f"Referenced picture missing: {name}")
    digest = hashlib.sha1(name.encode("utf-8")).hexdigest()[:12]
    stem = f"picture-{digest}"
    full = out / (stem + "-full.webp")
    thumb = out / (stem + "-thumb.webp")
    total_before += source.stat().st_size
    total_after += make_webp(source, full, 2400, 85)
    make_webp(source, thumb, 980, 78)
    full_rel = full.relative_to(ROOT).as_posix()
    thumb_rel = thumb.relative_to(ROOT).as_posix()
    mapping[full_rel] = thumb_rel
    html = html.replace(json.dumps(name, ensure_ascii=False), json.dumps(full_rel))

# Optimize large static photos too.
static_photos = [
    ("IMG_1319.jpeg", "hero.webp", 1900, 82),
    ("F4B07A57-4F89-4424-A0A4-8B516A1B9FB4.jpeg", "about.webp", 1500, 84),
]
for source_name, dest_name, size, quality in static_photos:
    source = ROOT / source_name
    if not source.exists():
        continue
    target = out / dest_name
    make_webp(source, target, size, quality)
    html = html.replace(source_name, target.relative_to(ROOT).as_posix())

marker = '/* RENDER GALLERY */'
if marker not in html:
    raise RuntimeError("Cannot locate gallery renderer")
lookup = "const optimizedThumbnails=" + json.dumps(mapping, ensure_ascii=False, separators=(",", ":")) + ";\n"
html = html.replace(marker, lookup + marker, 1)
old = '    img.src = work.photos[0];'
if old not in html:
    raise RuntimeError("Cannot locate thumbnail image assignment")
html = html.replace(old, '    img.src = optimizedThumbnails[work.photos[0]] || work.photos[0];', 1)
PAGE.write_text(html, encoding="utf-8")
print(f"Optimized {len(originals)} gallery originals: {total_before / 1048576:.1f}MB original -> {total_after / 1048576:.1f}MB zoom images + small thumbnails")
