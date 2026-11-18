#!/usr/bin/env python3
"""Erzeugt aus den Vorlagen in assets/intermac/ alle Icon- und Logo-Dateien, die apply-intermac-branding.py einsetzt.

Nur nach einer Änderung der Vorlagen nötig. Lokal auf macOS ausführen (braucht Pillow und iconutil) und das Ergebnis
in assets/intermac/generated/ committen; der Build selbst erzeugt nichts:

  python3 .github/scripts/make-intermac-assets.py

Vorlagen (512 px bzw. Wortmarke auf einfarbigem Grund; weiße Ecken bzw. Hintergrund werden freigestellt):
  icon-dark.png   App-Icon, Quelle für alle Icons
  icon-light.png  helle Variante; RustDesk unterscheidet Hell/Dunkel beim Tray nicht, sie wird nur freigestellt
  logo-dark.png   Wortmarke für das dunkle Theme (heller Schriftzug)
  logo-light.png  Wortmarke für das helle Theme (dunkler Schriftzug)
"""
import shutil
import subprocess
import sys
import tempfile
from collections import deque
from pathlib import Path

from PIL import Image

SRC = Path("assets/intermac")
OUT = SRC / "generated"
LANCZOS = Image.Resampling.LANCZOS

# Linkes Feld im Hauptfenster: 200 px breit, Logo mit 12 px Rand -> 176 px; doppelte Auflösung für HiDPI.
LOGO_WIDTH = 352
# Apple-Raster: 824 px Körper auf 1024 px Fläche.
MAC_BODY = 824 / 1024


def fail(message: str) -> None:
    print(f"Fehler: {message}", file=sys.stderr)
    sys.exit(1)


def project(p, a, b) -> float:
    """Lage von p auf der Strecke a->b (0 = a, 1 = b), begrenzt auf [0, 1]."""
    d = [b[i] - a[i] for i in range(3)]
    n = sum(x * x for x in d)
    t = sum((p[i] - a[i]) * d[i] for i in range(3)) / n
    return min(1.0, max(0.0, t))


def flood(w: int, h: int, seeds, passable) -> set:
    seen = set(s for s in seeds if passable(*s))
    queue = deque(seen)
    while queue:
        x, y = queue.popleft()
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= nx < w and 0 <= ny < h and (nx, ny) not in seen and passable(nx, ny):
                seen.add((nx, ny))
                queue.append((nx, ny))
    return seen


def dilate(points: set, w: int, h: int, r: int) -> set:
    out = set(points)
    for x, y in points:
        for dx in range(-r, r + 1):
            for dy in range(-r, r + 1):
                if 0 <= x + dx < w and 0 <= y + dy < h:
                    out.add((x + dx, y + dy))
    return out


def icon_mask(im: Image.Image) -> Image.Image:
    """Alpha-Maske des abgerundeten Quadrats; weiße Ecken werden mit Kantenglättung transparent."""
    w, h = im.size
    px = im.load()
    if px[0, 0][3] == 0:
        return im.getchannel("A")
    white, bg = (255, 255, 255), px[w // 2, 2][:3]
    t = {(x, y): project(px[x, y][:3], white, bg) for y in range(h) for x in range(w)}
    corners = [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)]
    outside = flood(w, h, corners, lambda x, y: t[(x, y)] < 0.5)
    edge = dilate(outside, w, h, 2)
    mask = Image.new("L", (w, h), 255)
    m = mask.load()
    for x, y in edge:
        m[x, y] = round(255 * t[(x, y)])
    return mask


def apply_mask(im: Image.Image, mask: Image.Image) -> Image.Image:
    """Setzt die Maske; Kantenpixel bekommen die reine Grundfarbe, damit kein heller Saum bleibt."""
    w, h = im.size
    out = im.copy()
    px, m = out.load(), mask.load()
    bg = px[w // 2, 2][:3]
    for y in range(h):
        for x in range(w):
            a = m[x, y]
            px[x, y] = (*bg, a) if a < 255 else (*px[x, y][:3], 255)
    return out


def clean_logo(im: Image.Image) -> Image.Image:
    """Stellt die Wortmarke frei: Schrift und Quadratkante werden halbtransparent in Schriftfarbe,
    das Innere des Icon-Quadrats (Stern, Strich) bleibt wie gezeichnet."""
    w, h = im.size
    px = im.load()
    bg = px[0, 0][:3]
    right = im.crop((w // 2, 0, w, h)).getcolors(1 << 20)
    ink = max((c for c in right if sum(abs(c[1][i] - bg[i]) for i in range(3)) > 150), key=lambda c: c[0])[1][:3]
    t = {(x, y): project(px[x, y][:3], bg, ink) for y in range(h) for x in range(w)}
    border = [(x, 0) for x in range(w)] + [(x, h - 1) for x in range(w)] + [(0, y) for y in range(h)] + [(w - 1, y) for y in range(h)]
    outside = flood(w, h, border, lambda x, y: t[(x, y)] < 0.5)
    # Größte zusammenhängende Fläche in Schriftfarbe = Icon-Quadrat.
    inked = {p for p, v in t.items() if v >= 0.5}
    best = None
    while inked:
        comp = flood(w, h, [next(iter(inked))], lambda x, y: (x, y) in inked)
        inked -= comp
        xs, ys = [p[0] for p in comp], [p[1] for p in comp]
        box = (min(xs), min(ys), max(xs), max(ys))
        area = (box[2] - box[0]) * (box[3] - box[1])
        if not best or area > best[0]:
            best = (area, box)
    x0, y0, x1, y1 = best[1]
    square = px[x0 + (x1 - x0) // 8, (y0 + y1) // 2][:3]
    near_outside = dilate(outside, w, h, 2)
    out = Image.new("RGBA", (w, h))
    o = out.load()
    for y in range(h):
        for x in range(w):
            in_box = x0 <= x <= x1 and y0 <= y <= y1
            if in_box and (x, y) not in near_outside:
                o[x, y] = (*px[x, y][:3], 255)
            else:
                o[x, y] = (*(square if in_box else ink), round(255 * t[(x, y)]))
    return out.crop(out.getchannel("A").point(lambda a: 255 if a > 8 else 0).getbbox())


def fit(im: Image.Image, size, box=None) -> Image.Image:
    """Skaliert proportional in box (Standard: ganze Fläche) und zentriert auf transparenter Fläche."""
    bw, bh = box or size
    scale = min(bw / im.width, bh / im.height)
    scaled = im.resize((max(1, round(im.width * scale)), max(1, round(im.height * scale))), LANCZOS)
    canvas = Image.new("RGBA", size)
    canvas.paste(scaled, ((size[0] - scaled.width) // 2, (size[1] - scaled.height) // 2), scaled)
    return canvas


def mac_icon(icon: Image.Image, size: int) -> Image.Image:
    body = round(size * MAC_BODY)
    return fit(icon, (size, size), (body, body))


def tray_template(icon: Image.Image) -> Image.Image:
    """macOS-Menüleiste: Template-Bild (nur Alpha zählt). Quadrat deckend, Stern und Strich ausgespart."""
    w, h = icon.size
    px = icon.load()
    bg = px[w // 2, h // 2 + h // 3][:3] if px[w // 2, 2][3] == 0 else px[w // 2, 2][:3]
    lum = lambda c: 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]
    lb = lum(bg)
    out = Image.new("RGBA", (w, h))
    o = out.load()
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            cut = min(1.0, max(0.0, (lum((r, g, b)) - lb) / (170 - lb)))
            o[x, y] = (0, 0, 0, round(a * (1 - cut)))
    # Wie das Upstream-Template: 60 px mit 6 px Rand.
    return fit(out, (60, 60), (48, 48))


def white_wordmark(logo: Image.Image) -> Image.Image:
    """Splash des portablen Windows-Packers: weißer Schriftzug, 96 x 32 px wie das Original."""
    w, h = logo.size
    a = logo.getchannel("A")
    # Schriftzug = alles rechts der ersten vollständig transparenten Spalte nach dem Icon-Quadrat.
    cols = [any(a.getpixel((x, y)) > 8 for y in range(h)) for x in range(w)]
    start = next(x for x in range(cols.index(True), w) if not cols[x])
    text = logo.crop((start, 0, w, h))
    text = text.crop(text.getchannel("A").getbbox())
    white = Image.new("RGBA", text.size, (255, 255, 255, 0))
    white.putalpha(text.getchannel("A"))
    canvas = Image.new("RGBA", (96, 32))
    scaled = fit(white, (88, 18))
    canvas.paste(scaled, (3, 9), scaled)
    return canvas


def icon_svg() -> str:
    """Kleines App-Icon der Flutter-Oberfläche (Tab-Leiste, Verbindungsfenster) als Vektor.
    Maße aus icon-dark.png vermessen; bei einem neuen Icon-Entwurf hier nachziehen.
    Ein assets/icon.png ginge auch, würde aber auf macOS den Tray ersetzen (dort als Template eingefärbt)."""
    import math

    cx, cy, outer = 255.5, 140.0, 63.0
    inner = outer * 0.382
    points = []
    for i in range(10):
        r = outer if i % 2 == 0 else inner
        a = math.radians(-90 + 36 * i)
        points.append(f"{cx + r * math.cos(a):.2f},{cy + r * math.sin(a):.2f}")
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">'
        '<rect width="512" height="512" rx="112" fill="#1A1D2B"/>'
        f'<polygon points="{" ".join(points)}" fill="#8FE9DF"/>'
        '<rect x="220" y="224" width="72" height="184" rx="36" fill="#FFFFFF"/>'
        "</svg>\n"
    )


def save_icns(icon: Image.Image, path: Path) -> None:
    if not shutil.which("iconutil"):
        fail("iconutil fehlt (Skript auf macOS ausführen).")
    with tempfile.TemporaryDirectory() as tmp:
        iconset = Path(tmp) / "AppIcon.iconset"
        iconset.mkdir()
        for base in (16, 32, 128, 256, 512):
            mac_icon(icon, base).save(iconset / f"icon_{base}x{base}.png")
            mac_icon(icon, base * 2).save(iconset / f"icon_{base}x{base}@2x.png")
        subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", str(path)], check=True)


def main() -> None:
    for name in ("icon-dark.png", "icon-light.png", "logo-dark.png", "logo-light.png"):
        if not (SRC / name).is_file():
            fail(f"{SRC / name} fehlt.")
    dark = Image.open(SRC / "icon-dark.png").convert("RGBA")
    light = Image.open(SRC / "icon-light.png").convert("RGBA")
    if dark.size != (512, 512) or light.size != (512, 512):
        fail("Die Icon-Vorlagen müssen 512 x 512 px groß sein.")
    mask = icon_mask(dark)
    icon = apply_mask(dark, mask)
    icon_light = apply_mask(light, mask)

    if OUT.exists():
        shutil.rmtree(OUT)
    for sub in ("windows", "macos", "res", "flutter", "portable"):
        (OUT / sub).mkdir(parents=True)

    icon.save(OUT / "icon-dark.png")
    icon_light.save(OUT / "icon-light.png")

    sizes = [16, 20, 24, 32, 40, 48, 64, 96, 128, 256]
    frames = [icon.resize((s, s), LANCZOS) for s in sizes]
    frames[-1].save(OUT / "windows/app_icon.ico", sizes=[(s, s) for s in sizes], append_images=frames[:-1])
    icon.resize((32, 32), LANCZOS).save(OUT / "windows/tray-icon.ico", sizes=[(32, 32)])

    save_icns(icon, OUT / "macos/AppIcon.icns")
    tray_template(icon).save(OUT / "macos/mac-tray-x2.png")

    for name, size in (("32x32.png", 32), ("64x64.png", 64), ("128x128.png", 128), ("128x128@2x.png", 256)):
        icon.resize((size, size), LANCZOS).save(OUT / "res" / name)
    icon.resize((1024, 1024), LANCZOS).save(OUT / "res/icon.png")
    mac_icon(icon, 1024).save(OUT / "res/mac-icon.png")

    logo_dark = clean_logo(Image.open(SRC / "logo-dark.png").convert("RGBA"))
    logo_light = clean_logo(Image.open(SRC / "logo-light.png").convert("RGBA"))
    # Beide Varianten exakt gleich groß, damit ein Theme-Wechsel das Layout nicht verschiebt.
    w = max(logo_dark.width, logo_light.width)
    h = max(logo_dark.height, logo_light.height)
    size = (LOGO_WIDTH, round(LOGO_WIDTH * h / w))
    fit(logo_dark, size).save(OUT / "flutter/logo_dark.png")
    fit(logo_light, size).save(OUT / "flutter/logo_light.png")

    (OUT / "flutter/icon.svg").write_text(icon_svg(), encoding="utf-8")
    white_wordmark(logo_dark).save(OUT / "portable/label.png")
    print(f"Erzeugt in {OUT}/ (Logo {size[0]} x {size[1]} px).")


if __name__ == "__main__":
    main()
