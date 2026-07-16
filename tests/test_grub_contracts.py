"""Contracts for the BigCommunity live ISO GRUB menu."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SHARED = ROOT / "shared/live-overlay/usr/share/grub"
MINIMAL = ROOT / "bigcommunity/minimal/live-overlay/usr/share/grub"
CFG = SHARED / "cfg"
MINIMAL_CFG = MINIMAL / "cfg"
THEME = SHARED / "themes/bigcommunity-live"
I18N = ROOT / "shared/grub-i18n"
LINGUAS = I18N.joinpath("LINGUAS").read_text(encoding="utf-8").split()


def test_grub_sources_are_syntactically_valid() -> None:
    checker = shutil.which("grub-script-check")
    assert checker is not None
    for config in sorted(CFG.glob("*.cfg")) + sorted(MINIMAL_CFG.glob("*.cfg")):
        subprocess.run([checker, config], check=True, capture_output=True, text=True)


def test_shared_boot_contract() -> None:
    grub = CFG.joinpath("grub.cfg").read_text(encoding="utf-8")
    kernels = CFG.joinpath("kernels.cfg").read_text(encoding="utf-8")
    assert 'set locale_dir="/boot/grub/locales"' in grub
    assert 'set secondary_locale_dir="/boot/grub/locales/bigcommunity"' in grub
    assert "insmod gettext" in grub
    assert "${bootlang} ${keyboard} ${timezone} ${hwclock}" in grub
    assert "${kopts}" in kernels
    assert "misobasedir=${bigcommunity_iso_base}" in kernels
    assert "misolabel=${bigcommunity_iso_label}" in kernels


def test_intel_driver_choices_are_explicit() -> None:
    kernels = CFG.joinpath("kernels.cfg").read_text(encoding="utf-8")
    assert '"i915.force_probe=*" "xe.force_probe=!*"' in kernels
    assert '"i915.force_probe=!*" "xe.force_probe=*"' in kernels


def test_desktop_specific_entries_are_neutral() -> None:
    text = "\n".join(path.read_text(encoding="utf-8") for path in CFG.glob("*.cfg"))
    forbidden = ("KDE", "Plasma", "boot-in-plasma", "only-konsole")
    assert not any(value in text for value in forbidden)


def test_default_boot_does_not_disable_security_or_diagnostics() -> None:
    kernels = CFG.joinpath("kernels.cfg").read_text(encoding="utf-8")
    default_entry = kernels.split('menuentry $"1 - ', 1)[1].split("}", 1)[0]
    forbidden = {
        "audit=0",
        "clearcpuid=514",
        "intremap=off",
        "nomce",
        "nosoftlockup",
        "nowatchdog",
        "rcupdate.rcu_expedited=1",
    }
    assert not forbidden.intersection(default_entry.split())


def test_menu_classes_have_icons() -> None:
    text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (CFG / "kernels.cfg", CFG / "languages.cfg", MINIMAL_CFG / "kernels.cfg")
    )
    classes = set(re.findall(r"--class=([a-z0-9-]+)", text))
    icon_names = {path.stem for path in THEME.joinpath("icons").glob("*.png")}
    assert classes <= icon_names


def test_language_selector_covers_catalogs() -> None:
    assert len(LINGUAS) == 29
    selector = CFG.joinpath("languages.cfg").read_text(encoding="utf-8")
    selected = re.findall(r"select_language\s+([A-Za-z_]+)\s+", selector)
    assert selected == LINGUAS


def test_language_selector_expands_inline() -> None:
    cases = (
        (CFG / "kernels.cfg", 'menuentry $"4 - Language:', 'menuentry $"6 - Run memory test"', "set default=3"),
        (MINIMAL_CFG / "kernels.cfg", 'menuentry $"2 - Language:', 'menuentry $"4 - Run memory test"', "set default=1"),
    )
    for path, language_label, following_label, selected_default in cases:
        text = path.read_text(encoding="utf-8")
        language = text.index(language_label)
        inline_source = text.index("source /boot/grub/languages.cfg", language)
        following = text.index(following_label, inline_source)
        assert language < inline_source < following
        assert 'set bigcommunity_menu="language"' not in text
        assert selected_default in text

    selector = CFG.joinpath("languages.cfg").read_text(encoding="utf-8")
    assert selector.count("unset bigcommunity_language_expanded") == 2
    assert 'menuentry $"Back to main menu"' in selector
    assert "menu_reload" in selector


def test_dispatcher_reloads_nested_menu_states() -> None:
    for path in (CFG / "kernels.cfg", MINIMAL_CFG / "kernels.cfg"):
        text = path.read_text(encoding="utf-8")
        assert "normal /boot/grub/kernels.cfg" not in text
        assert "normal_exit" not in text
        assert "menu_reload" in text


def test_catalogs_are_complete_and_compiled() -> None:
    for locale in LINGUAS:
        po = I18N / "po" / f"{locale}.po"
        shared_mo = SHARED / "locales/bigcommunity" / f"{locale}.mo"
        minimal_mo = MINIMAL / "locales/bigcommunity" / f"{locale}.mo"
        assert po.is_file()
        subprocess.run(["msgfmt", "--check", str(po), "-o", "/dev/null"], check=True)
        if locale != "en":
            untranslated = subprocess.run(
                ["msgattrib", "--untranslated", str(po)],
                check=True,
                capture_output=True,
                text=True,
            ).stdout
            assert '\nmsgid "' not in untranslated
        assert shared_mo.is_file()
        assert minimal_mo.read_bytes() == shared_mo.read_bytes()


def test_theme_assets_and_unicode_fallback() -> None:
    theme = THEME.joinpath("theme.txt").read_text(encoding="utf-8")
    grub = CFG.joinpath("grub.cfg").read_text(encoding="utf-8")
    assert 'terminal-font: "Terminus Bold 22"' in theme
    assert 'terminal-left: "0"' in theme
    assert 'terminal-top: "0"' in theme
    assert 'terminal-width: "100%"' in theme
    assert 'terminal-height: "100%"' in theme
    assert "PREVIEW-concept.png" not in theme
    assert "bigcommunity-grub-live.png" not in theme
    assert not THEME.joinpath("bigcommunity-grub-live.png").exists()
    assets = re.findall(
        r'^\s*(?:file|selected_item_pixmap_style|scrollbar_frame|scrollbar_thumb)\s*=\s*"([^"]+)"',
        theme,
        re.MULTILINE,
    )
    assert assets
    for asset in assets:
        if "*" in asset:
            assert list(THEME.glob(asset)), asset
        else:
            assert THEME.joinpath(asset).is_file(), asset
    assert 'set grub_theme="/boot/grub/themes/bigcommunity-live/theme.txt"' in grub
    assert "loadfont /boot/grub/themes/bigcommunity-live/ter-u22b.pf2" in grub
    assert THEME.joinpath("ter-u22b.pf2").read_bytes().startswith(b"FILE")
    assert "loadfont /boot/grub/unicode.pf2" in grub


def test_minimal_reuses_common_menu_infrastructure() -> None:
    for name in ("defaults.cfg", "grub.cfg", "languages.cfg", "loopback.cfg"):
        assert MINIMAL_CFG.joinpath(name).read_bytes() == CFG.joinpath(name).read_bytes()
    variable = MINIMAL_CFG.joinpath("variable.cfg").read_text(encoding="utf-8")
    assert 'set bigcommunity_iso_label="BIGCOMMUNITY_LIVE_BASE"' in variable


def test_uefi_memtest_uses_chainloader() -> None:
    for kernels in (CFG / "kernels.cfg", MINIMAL_CFG / "kernels.cfg"):
        text = kernels.read_text(encoding="utf-8")
        assert "chainloader /boot/memtest-efi" in text
        assert "linux16 /boot/memtest-efi" not in text


def test_legacy_backups_are_removed() -> None:
    assert not CFG.joinpath("kernels.cfg.bak").exists()
    assert not MINIMAL_CFG.joinpath("kernels.cfg.old").exists()
    assert not SHARED.parent.joinpath("boot/grub.bak").exists()
    assert not MINIMAL.parent.joinpath("boot/grub").exists()
