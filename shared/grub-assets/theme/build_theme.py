#!/usr/bin/env python3
"""Build the GNOME edition's live GRUB theme (themes/bigcommunity-live).

Only bigcommunity/gnome ships this theme; the other editions keep the one in
shared/live-overlay. The theme follows comm-welcome: Adwaita Sans, the purple palette of its
style.css and the snowy owl of the "Olhar" wallpaper. Every static text
(wordmark, key hints) is an antialiased bitmap; only the menu rows and the
countdown use the 1-bit PF2 font, because GRUB cannot antialias fonts.

Usage: build_theme.py [theme_dir]
Needs rsvg-convert, ImageMagick 7 (magick), grub-mkfont, python fontTools and
the Adwaita Sans / Adwaita Mono fonts in /usr/share/fonts/Adwaita.
The output is committed; the ISO build only copies the theme folder.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
GNOME_THEME = REPO / "bigcommunity/gnome/live-overlay/usr/share/grub/themes/bigcommunity-live"
THEME = Path(sys.argv[1]) if len(sys.argv) > 1 else GNOME_THEME
CFG = REPO / "shared/live-overlay/usr/share/grub/cfg"
ADWAITA = Path("/usr/share/fonts/Adwaita/AdwaitaSans-Regular.ttf")  # variable font (wght, opsz)

FG = "#efe9fb"
FG_DIM = "#b6abcf"
ACCENT = "#c9a2ff"      # comm-welcome accent
ACCENT_BG = "#8b3ff0"   # comm-welcome suggested-action purple
ITEM = "#d6cceb"
ICON = "#d8cdee"
SANS = "Adwaita Sans"
MONO = "Adwaita Mono"
FONT_NAME = "Adwaita Sans SemiBold Regular 18"
PF2 = "adwaita-sans-semibold-18.pf2"
# Latin, Greek, Cyrillic, punctuation and arrows. Hebrew and CJK fall back to
# unicode.pf2, which cfg/grub.cfg loads first.
PF2_RANGES = "0x20-0x7E,0xA0-0x24F,0x370-0x3FF,0x400-0x4FF,0x2010-0x2027,0x2190-0x21FF"
NOCHUNK = ["-define", "png:exclude-chunks=date,time"]
TMP = Path(tempfile.mkdtemp())

# Line icons on a 24 px grid, one colour, after the Lucide set (ISC licence).
ICONS = {
    "back": '<path d="M12 19l-7-7 7-7"/><path d="M19 12H5"/>',
    "restart": '<path d="M21 12a9 9 0 1 1-9-9c2.52 0 4.93 1 6.74 2.74L21 8"/><path d="M21 3v5h-5"/>',
    "language": '<circle cx="12" cy="12" r="10"/><path d="M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20"/><path d="M2 12h20"/>',
    "advanced": '<path d="M21 4h-7"/><path d="M10 4H3"/><path d="M21 12h-9"/><path d="M8 12H3"/><path d="M21 20h-5"/><path d="M12 20H3"/><path d="M14 2v4"/><path d="M8 10v4"/><path d="M16 18v4"/>',
    "display": '<rect x="2" y="3" width="20" height="14" rx="2"/><path d="M8 21h8"/><path d="M12 17v4"/>',
    "storage": '<path d="M22 12H2"/><path d="M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z"/><path d="M6 16h.01"/><path d="M10 16h.01"/>',
    "firmware": '<rect x="4" y="4" width="16" height="16" rx="2"/><rect x="9" y="9" width="6" height="6" rx="1"/><path d="M15 2v2"/><path d="M15 20v2"/><path d="M2 15h2"/><path d="M2 9h2"/><path d="M20 15h2"/><path d="M20 9h2"/><path d="M9 2v2"/><path d="M9 20v2"/>',
    "memtest": '<path d="M6 19v-3"/><path d="M10 19v-3"/><path d="M14 19v-3"/><path d="M18 19v-3"/><path d="M8 11V9"/><path d="M16 11V9"/><path d="M12 11V9"/><path d="M2 15h20"/><path d="M2 7a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v1.1a2 2 0 0 0 0 3.84V17a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2v-5.06a2 2 0 0 0 0-3.84Z"/>',
    "performance": '<path d="m12 14 4-4"/><path d="M3.34 19a10 10 0 1 1 17.32 0"/>',
    "diagnostics": '<path d="M22 12h-4l-3 9L9 3l-3 9H2"/>',
    "safe": '<path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/>',
    "opensource": '<rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 9.9-1"/>',
    "watchdog": '<path d="M10 2h4"/><path d="M12 14l3-3"/><circle cx="12" cy="14" r="8"/>',
    "edit": '<path d="M12 3H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.38 2.63a1 1 0 0 1 3 3l-9.02 9.01a2 2 0 0 1-.85.5l-2.87.84a.5.5 0 0 1-.62-.62l.84-2.87a2 2 0 0 1 .5-.85z"/>',
    "efi": '<path d="M12 2 2 7l10 5 10-5-10-5z"/><path d="m2 17 10 5 10-5"/><path d="m2 12 10 5 10-5"/>',
    "gpu": '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M11 9h4a2 2 0 0 0 2-2V3"/><circle cx="9" cy="9" r="2"/><path d="M7 21v-4a2 2 0 0 1 2-2h4"/><circle cx="15" cy="15" r="2"/>',
    "power": '<path d="M12 2v10"/><path d="M18.4 6.6a9 9 0 1 1-12.77.04"/>',
}
# Menu classes that share a glyph; the label already names the vendor.
ALIASES = {"nvidia": "gpu", "amd": "gpu", "intel": "gpu", "bigcommunity": "power"}


def run(*cmd: str) -> None:
    subprocess.run(cmd, check=True)


def svg_doc(w: int, h: int, body: str, defs: str = "") -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">'
            f"<defs>{defs}</defs>{body}</svg>")


def render(path: Path, svg: str, w: int, h: int) -> Path:
    src = TMP / (path.stem + ".svg")
    src.write_text(svg, encoding="utf-8")
    run("rsvg-convert", "-w", str(w), "-h", str(h), str(src), "-o", str(path))
    return path


def size_of(p: Path) -> tuple[int, int]:
    out = subprocess.run(["magick", "identify", "-format", "%w %h", str(p)],
                         check=True, capture_output=True, text=True).stdout.split()
    return int(out[0]), int(out[1])


def slice9(prefix: str, full: Path, c: int) -> None:
    """Cut a square box into GRUB's nine <prefix>_<side>.png slices of c px."""
    w, h = size_of(full)
    parts = {"nw": (c, c, 0, 0), "n": (w - 2 * c, c, c, 0), "ne": (c, c, w - c, 0),
             "w": (c, h - 2 * c, 0, c), "c": (w - 2 * c, h - 2 * c, c, c), "e": (c, h - 2 * c, w - c, c),
             "sw": (c, c, 0, h - c), "s": (w - 2 * c, c, c, h - c), "se": (c, c, w - c, h - c)}
    for side, (pw, ph, x, y) in parts.items():
        run("magick", str(full), "-crop", f"{pw}x{ph}+{x}+{y}", "+repage", *NOCHUNK,
            f"PNG32:{THEME / f'{prefix}_{side}.png'}")


# ------------------------------------------------------------------ icons
def menu_classes() -> set[str]:
    """Every --class used by the menu; GRUB draws the icon icons/<class>.png."""
    text = "\n".join(p.read_text(encoding="utf-8") for p in CFG.glob("*.cfg"))
    return set(re.findall(r"--class=([a-z0-9-]+)", text))


def icons() -> None:
    # One icon per menu class, no more. "X-submenu" (entries that open a page)
    # uses the glyph of X.
    d = THEME / "icons"
    shutil.rmtree(d, ignore_errors=True)
    d.mkdir()
    for cls in sorted(menu_classes()):
        name = cls.removesuffix("-submenu")
        glyph = ALIASES.get(name, name)
        if glyph not in ICONS:
            sys.exit(f"menu class '{cls}' has no icon: add '{glyph}' to ICONS or ALIASES")
        svg = ('<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" '
               f'stroke="{ICON}" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round">{ICONS[glyph]}</svg>')
        render(d / f"{cls}.png", svg, 22, 22)


# ------------------------------------------------------------------ font
def font() -> None:
    var = TTFont(ADWAITA)
    axes = {a.axisTag: a.defaultValue for a in var["fvar"].axes}
    axes["wght"] = 600
    static = instancer.instantiateVariableFont(var, axes)
    ttf = TMP / "AdwaitaSans-SemiBold.ttf"
    static.save(ttf)
    run("grub-mkfont", "-s", "18", "-n", "Adwaita Sans SemiBold", "-r", PF2_RANGES,
        "-o", str(THEME / PF2), str(ttf))


# ------------------------------------------------------------------ progress bar
def progress_bar() -> None:
    # Recolour only: the slice geometry is what keeps the bar 6 px tall (README).
    for f in THEME.glob("progress_bar_*.png"):
        run("magick", str(f), "-channel", "RGB", "-fill", "#ffffff", "-colorize", "100", "+channel",
            "-channel", "A", "-fx", "u>0 ? 0.141 : 0", "+channel", *NOCHUNK, f"PNG32:{f}")
    for f in THEME.glob("progress_highlight_*.png"):
        run("magick", str(f), "-channel", "RGB", "-fill", ACCENT, "-colorize", "100", "+channel",
            *NOCHUNK, f"PNG32:{f}")


# ------------------------------------------------------------------ background
def background() -> None:
    # A 16:9 composition extended to 32:9 by repeating its last column, which
    # is plain shaded dark. "crop" scales the image to cover the screen and
    # keeps its left part: any screen up to 32:9 (4:3, 16:10, 16:9, 21:9) is
    # covered by height, so the owl keeps the same place and size. A 16:9
    # master was covered by width on 21:9 screens, which enlarged the owl
    # under the menu.
    W, H = 2133, 1200
    WIDE = round(H * 32 / 9)
    base = TMP / "bg0.png"
    run("magick", "-size", f"{W}x{H}", "xc:#08061a",
        "(", str(HERE / "olhar.jpg"), "-resize", "x980", ")", "-geometry", "-470-30", "-composite", str(base))
    shade = render(TMP / "shade.png", svg_doc(W, H, f"""
<rect width="{W}" height="{H}" fill="url(#v)"/><rect width="{W}" height="{H}" fill="url(#h)"/>
<rect width="{W}" height="{H}" fill="url(#glow)"/>""", """
<linearGradient id="v" x1="0" y1="0" x2="0" y2="1">
 <stop offset="0" stop-color="#0a0718" stop-opacity="0"/>
 <stop offset="0.30" stop-color="#0a0718" stop-opacity="0.05"/>
 <stop offset="0.42" stop-color="#0a0718" stop-opacity="0.84"/>
 <stop offset="1" stop-color="#0a0718" stop-opacity="0.96"/></linearGradient>
<linearGradient id="h" x1="0" y1="0" x2="1" y2="0">
 <stop offset="0.34" stop-color="#0a0718" stop-opacity="0"/>
 <stop offset="0.75" stop-color="#0a0718" stop-opacity="0.5"/></linearGradient>
<radialGradient id="glow" cx="0.72" cy="0.0" r="0.5">
 <stop offset="0" stop-color="#8b3ff0" stop-opacity="0.22"/>
 <stop offset="1" stop-color="#8b3ff0" stop-opacity="0"/></radialGradient>"""), W, H)
    run("magick", str(base), str(shade), "-composite", "-alpha", "off",
        "(", "+clone", "-crop", f"1x{H}+{W - 1}+0", "+repage", "-scale", f"{WIDE - W}x{H}!", ")",
        "+append", "+repage", *NOCHUNK, f"PNG24:{THEME / 'background.png'}")


# ------------------------------------------------------------------ header and hints
def header() -> None:
    render(THEME / "header.png", svg_doc(420, 92, f"""
<text x="420" y="22" text-anchor="end" font-family="{SANS}" font-weight="700" font-size="12" letter-spacing="2.6" fill="{ACCENT}">LIVE ENVIRONMENT</text>
<text x="420" y="66" text-anchor="end" font-family="{SANS}" font-weight="800" font-size="42" letter-spacing="-1.4" fill="{FG}">Big<tspan fill="{ACCENT}">Community</tspan></text>
<text x="420" y="88" text-anchor="end" font-family="{SANS}" font-weight="500" font-size="14" fill="{FG_DIM}">GNOME, made by the community.</text>"""), 420, 92)


def hints() -> Path:
    """Key hints as keycaps. GRUB never translates theme text, so English only."""
    pairs = [("Enter", "select"), ("E", "edit"), ("C", "command line"), ("Esc", "back"), (">>", "opens a submenu")]
    x, parts = 0.0, []
    for key, label in pairs:
        kw = 12 + len(key) * 8.2
        parts.append(f'<rect x="{x}" y="3" width="{kw}" height="22" rx="6" fill="#ffffff" fill-opacity="0.06" '
                     f'stroke="{FG_DIM}" stroke-opacity="0.22"/>'
                     f'<text x="{x + kw / 2}" y="18.5" text-anchor="middle" font-family="{MONO}" font-weight="700" '
                     f'font-size="12.5" fill="{FG}">{key}</text>')
        x += kw + 8
        parts.append(f'<text x="{x}" y="19" font-family="{SANS}" font-weight="500" font-size="14.5" '
                     f'fill="{FG_DIM}">{label}</text>')
        x += len(label) * 7.6 + 26
    w = int(x) + 4
    return render(THEME / "hints.png", svg_doc(w, 28, "".join(parts)), w, 28)


# ------------------------------------------------------------------ selection and rows
SEL = 14   # slice size: GRUB pads the row content by this much
GLOW = 5   # part of each slice reserved for the neon glow outside the frame


def selection() -> None:
    s = 3 * SEL
    x0, w = GLOW + 0.75, s - 2 * GLOW - 1.5
    defs = '<filter id="g" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="3.2"/></filter>'
    body = (f'<rect x="{x0}" y="{x0}" width="{w}" height="{w}" rx="9" fill="none" stroke="#a45cff" '
            f'stroke-width="4" stroke-opacity="0.75" filter="url(#g)"/>'
            f'<rect x="{x0}" y="{x0}" width="{w}" height="{w}" rx="9" fill="{ACCENT_BG}" fill-opacity="0.34" '
            f'stroke="{ACCENT}" stroke-width="1.5" stroke-opacity="0.85"/>'
            f'<rect x="{GLOW + 3}" y="{SEL - 2}" width="3" height="{s - 2 * SEL + 4}" rx="1.5" fill="#efe0ff"/>')
    slice9("select", render(TMP / "select_full.png", svg_doc(s, s, body, defs), s, s), SEL)
    # Unselected rows get a transparent pixmap with the same slices, or GRUB
    # shifts only the selected row's text by the padding.
    slice9("item", render(TMP / "item_full.png", svg_doc(s, s, ""), s, s), SEL)


def scrollbar() -> None:
    # "east" would draw the bar inside the menu box's right padding, which is
    # 0 here (no menu_pixmap_style), so the bar vanished. "center" draws it in
    # the list area and narrows the rows to make room.
    for name, colour, op in (("scrollbar", "#ffffff", 0.06), ("scrollbar_thumb", ACCENT, 0.9)):
        svg = svg_doc(9, 9, f'<rect x="2" y="0" width="5" height="9" rx="2.5" fill="{colour}" fill-opacity="{op}"/>')
        slice9(name, render(TMP / f"{name}_full.png", svg, 9, 9), 3)


# ------------------------------------------------------------------ theme.txt
def theme_txt(hints_w: int, hints_h: int) -> None:
    (THEME / "theme.txt").write_text(f"""title-text: ""
desktop-color: "#0a0718"
desktop-image: "background.png"
desktop-image-scale-method: "crop"
desktop-image-h-align: "left"
desktop-image-v-align: "top"
terminal-font: "Terminus Bold 22"
terminal-left: "0"
terminal-top: "0"
terminal-width: "100%"
terminal-height: "100%"
terminal-border: "0"

+ image {{
    left = 100%-8%-420
    top = 7%
    width = 420
    height = 92
    file = "header.png"
}}

+ boot_menu {{
    left = 50%-430
    top = 38%
    width = 860
    height = 48%
    item_font = "{FONT_NAME}"
    selected_item_font = "{FONT_NAME}"
    item_color = "{ITEM}"
    selected_item_color = "#ffffff"
    icon_width = 22
    icon_height = 22
    item_icon_space = 16
    item_height = 28
    item_padding = 14
    item_spacing = 16
    item_pixmap_style = "item_*.png"
    selected_item_pixmap_style = "select_*.png"
    scrollbar = true
    scrollbar_width = 9
    scrollbar_frame = "scrollbar_*.png"
    scrollbar_thumb = "scrollbar_thumb_*.png"
    scrollbar_thumb_overlay = true
    scrollbar_slice = center
    scrollbar_left_pad = 10
    scrollbar_right_pad = 0
    scrollbar_top_pad = 10
    scrollbar_bottom_pad = 10
}}

+ label {{
    id = "__timeout__"
    left = 50%-100
    top = 87%
    width = 200
    height = 24
    align = "center"
    text = "%ds"
    color = "{ACCENT}"
    font = "{FONT_NAME}"
}}

+ progress_bar {{
    id = "__timeout__"
    left = 50%-120
    top = 92%
    width = 240
    height = 6
    bar_style = "progress_bar_*.png"
    highlight_style = "progress_highlight_*.png"
}}

+ image {{
    left = 50%-{hints_w // 2}
    top = 95%
    width = {hints_w}
    height = {hints_h}
    file = "hints.png"
}}
""", encoding="utf-8")


def main() -> None:
    THEME.mkdir(parents=True, exist_ok=True)
    icons()
    font()
    progress_bar()
    background()
    header()
    selection()
    scrollbar()
    theme_txt(*size_of(hints()))
    shutil.rmtree(TMP, ignore_errors=True)
    print(THEME)


if __name__ == "__main__":
    main()
