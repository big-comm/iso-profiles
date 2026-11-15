"""The firewall ships installed but off.

Turned on by default it blocked SSH and every other incoming connection the
user had not allowed (a test machine could not be reached). ufw.service stays
enabled: with ENABLED=no it loads nothing, and after "sudo ufw enable" it
keeps the firewall on across boots, with the rules of the overlay.
"""

from __future__ import annotations

import re
from pathlib import Path

EDITION = Path(__file__).resolve().parent.parent / "bigcommunity/wmaker"


def test_ufw_is_off_by_default() -> None:
    conf = (EDITION / "desktop-overlay/etc/ufw/ufw.conf").read_text(encoding="utf-8")
    assert re.findall(r"^ENABLED=(\w+)$", conf, re.M) == ["no"]


def test_ufw_service_stays_enabled_for_users_who_turn_it_on() -> None:
    profile = (EDITION / "profile.conf").read_text(encoding="utf-8")
    enabled = re.search(r"^enable_systemd=\((.*)\)$", profile, re.M)
    assert enabled and "'ufw'" in enabled.group(1)
    # the rules that apply once it is turned on are still there
    rules = (EDITION / "desktop-overlay/etc/ufw/user.rules").read_text(encoding="utf-8")
    assert "dapp_CIFS" in rules


def test_split_packages_called_by_the_menus_are_installed() -> None:
    # The root menus of both sessions call big-wm-welcome and big-wm-zoom;
    # they are split packages of big-wm, not dependencies of the session.
    names = set()
    for line in (EDITION / "Packages-Desktop").read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            names.add(line.split()[0])
    assert {"big-wm-welcome", "big-wm-zoom"} <= names
