"""The edition installs: no two packages of the profile conflict.

Seen on 2026-11-23 (build-iso run 45281436926, testing): usb-dirty-pages-udev
23.10.15-4 (Packages-Desktop) and udev-usb-sync 1.1-4 (shared Packages-Root)
became conflicting packages in the repositories; mkimage stopped at "unresolvable
package conflicts detected". Both limit the dirty pages of USB writes; the shared
root already ships udev-usb-sync, so the edition leaves the other one out.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def names(path: Path) -> set[str]:
    return {line.split("#", 1)[0].strip() for line in path.read_text(encoding="utf-8").splitlines()} - {""}


def test_usb_dirty_pages_comes_only_from_the_shared_root() -> None:
    assert "udev-usb-sync" in names(ROOT / "shared/Packages-Root")
    assert "usb-dirty-pages-udev" not in names(ROOT / "bigcommunity/wmaker/Packages-Desktop")
