"""Contracts for the Big WindowMaker (wmaker) boot themes."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SHARED_CFG = ROOT / "shared/live-overlay/usr/share/grub/cfg"
WMAKER = ROOT / "bigcommunity/wmaker"
LIVE_GRUB = WMAKER / "live-overlay/usr/share/grub"
THEME = LIVE_GRUB / "themes/bigcommunity-live"


def _packages(path: Path) -> set[str]:
    names = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            names.add(line.split()[-1] if line.startswith(">") else line.split()[0])
    return names


def test_live_menu_keeps_every_shared_cfg() -> None:
    # buildiso copies cfg/*.cfg only: the edition links the shared files and
    # adds profile.cfg, which the shared grub.cfg sources.
    shared = {p.name for p in SHARED_CFG.glob("*.cfg")}
    edition = {p.name for p in (LIVE_GRUB / "cfg").glob("*.cfg")}
    assert edition == shared | {"profile.cfg"}
    # kernels.cfg é gerado do shared com a entrada 1 dizendo "Big WindowMaker"
    # (grub-i18n/gerar.sh; conferido em test_wmaker_grub_nome.py).
    for name in shared - {"kernels.cfg"}:
        link = LIVE_GRUB / "cfg" / name
        assert link.is_symlink(), name
        assert link.resolve() == (SHARED_CFG / name).resolve(), name
    assert "source /boot/grub/profile.cfg" in (SHARED_CFG / "grub.cfg").read_text(encoding="utf-8")


def test_profile_cfg_is_valid_grub_script() -> None:
    checker = shutil.which("grub-script-check")
    assert checker is not None
    subprocess.run([checker, str(LIVE_GRUB / "cfg/profile.cfg")], check=True)


def test_live_theme_fonts_and_assets() -> None:
    theme = THEME.joinpath("theme.txt").read_text(encoding="utf-8")
    profile = (LIVE_GRUB / "cfg/profile.cfg").read_text(encoding="utf-8")
    assert "Big WindowMaker Live" in theme
    assert not re.search(r"@(?!KEYMAP_SHORT@|TIMEOUT_NOTIFICATION_MIDDLE@)[A-Z_]+@", theme)

    loop = re.search(r"for font in (?P<names>[^;]+);", profile)
    assert loop is not None
    loaded = loop.group("names").split()
    assert "loadfont /boot/grub/themes/bigcommunity-live/${font}.pf2" in profile
    font_names = set()
    for name in loaded:
        data = THEME.joinpath(f"{name}.pf2").read_bytes()
        assert data.startswith(b"FILE"), name
        # PFF2 "NAME" section: 4-byte length, then the NUL-terminated name.
        start = data.index(b"NAME") + 8
        font_names.add(data[start : data.index(b"\0", start)].decode())
    wanted = set(re.findall(r'font\s*[:=]\s*"([^"]+)"', theme))
    assert wanted <= font_names, wanted - font_names

    assets = re.findall(
        r'^\s*(?:file|selected_item_pixmap_style|scrollbar_frame|scrollbar_thumb)\s*=\s*"([^"]+)"',
        theme,
        re.MULTILINE,
    )
    assert assets
    for asset in assets:
        assert list(THEME.glob(asset)), asset


def test_every_font_the_shared_menu_loads_exists() -> None:
    # The edition's theme replaces the shared one; a font the shared grub.cfg
    # loads from it and that is missing prints "file not found" on every boot.
    grub = (SHARED_CFG / "grub.cfg").read_text(encoding="utf-8")
    for name in re.findall(r"loadfont /boot/grub/themes/bigcommunity-live/([\w.-]+\.pf2)", grub):
        assert THEME.joinpath(name).read_bytes().startswith(b"FILE"), name


def test_installed_system_selects_the_big_wm_themes() -> None:
    dropin = (WMAKER / "root-overlay/etc/default/grub.d/big-wm-theme.cfg").read_text(encoding="utf-8")
    assert 'GRUB_THEME="/boot/grub/themes/big-wm/theme.txt"' in dropin
    assert re.search(r'^GRUB_GFXMODE="1024x768,800x600,auto"$', dropin, re.MULTILINE)
    assert re.search(r'^GRUB_DISTRIBUTOR="Big WindowMaker"$', dropin, re.MULTILINE)
    plymouth = (WMAKER / "root-overlay/etc/plymouth/plymouthd.conf").read_text(encoding="utf-8")
    assert re.search(r"^Theme=big-wm$", plymouth, re.MULTILINE)

    desktop = _packages(WMAKER / "Packages-Desktop")
    assert {"grub-theme-big-wm", "plymouth-theme-big-wm"} <= desktop
    # plymouth-theme-community resets the theme to its own on every upgrade.
    assert "plymouth-theme-community" in _packages(WMAKER / "Root-remove")
