"""Big WindowMaker has a system keyring (Secret Service) in both sessions.

Without one (measured on 2026-11-17 in wlmaker: libsecret loads, every lookup
fails), applications could not keep any password: Big Remote Play forgot
Sunshine's password every session and lost the Headscale API key it had just
created. GNOME Keyring is the light GTK choice; the wdm and LightDM PAM
stacks already load pam_gnome_keyring, so the login password opens it.
"""

from __future__ import annotations

from pathlib import Path

PACKAGES = Path(__file__).resolve().parent.parent / "bigcommunity/wmaker/Packages-Desktop"


def _names() -> set[str]:
    names = set()
    for line in PACKAGES.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            names.add(line.split()[-1] if line.startswith(">") else line.split()[0])
    return names


def test_the_edition_ships_a_secret_service() -> None:
    assert "gnome-keyring" in _names()
