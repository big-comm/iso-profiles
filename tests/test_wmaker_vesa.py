"""A graphics card without a KMS driver still gets a graphical login.

Measured on 2026-11-21 (r56 ISO, QEMU "VMware compatible" display, the
Proxmox option): vmwgfx refuses QEMU ("unsupported hypervisor"), there is no
/dev/dri and no /dev/fb0, Xorg finds no driver and wdm fails. With
xf86-video-vesa the X server falls back to VESA and the live session starts.
"""

from __future__ import annotations

from pathlib import Path

PACKAGES = Path(__file__).resolve().parent.parent / "bigcommunity/wmaker/Packages-Desktop"


def test_the_edition_ships_the_vesa_fallback() -> None:
    names = {line.split("#", 1)[0].strip() for line in PACKAGES.read_text(encoding="utf-8").splitlines()}
    assert "xf86-video-vesa" in names
