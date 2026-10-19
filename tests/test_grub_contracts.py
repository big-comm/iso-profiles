"""Contracts for the BigCommunity live ISO GRUB menu."""

from __future__ import annotations

import re
import shlex
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LIVE_OVERLAY = ROOT / "shared/live-overlay"
SYSTEMD = LIVE_OVERLAY / "etc/systemd/system"
SHARED = ROOT / "shared/live-overlay/usr/share/grub"
CFG = SHARED / "cfg"
THEME = SHARED / "themes/bigcommunity-live"
I18N = ROOT / "shared/grub-i18n"
LINGUAS = I18N.joinpath("LINGUAS").read_text(encoding="utf-8").split()


def _boot_arguments(kernels: str, entry_number: str) -> list[str]:
    entry = re.search(
        rf'^\s*menuentry \$"{re.escape(entry_number)} - [^"]+"[^\n]*\{{'
        r"(?P<body>.*?)^\s*\}",
        kernels,
        re.MULTILINE | re.DOTALL,
    )
    assert entry is not None, entry_number
    boot = re.search(
        r"^\s*boot_bigcommunity(?:_verbose)?\s+(?P<arguments>.+)$",
        entry.group("body"),
        re.MULTILINE,
    )
    assert boot is not None, entry_number
    return boot.group("arguments").split()


def _module_blacklist(arguments: list[str]) -> set[str]:
    options = [
        argument.removeprefix("module_blacklist=").split(",")
        for argument in arguments
        if argument.startswith("module_blacklist=")
    ]
    assert len(options) == 1
    return set(options[0])


def test_grub_sources_are_syntactically_valid() -> None:
    checker = shutil.which("grub-script-check")
    assert checker is not None
    for config in sorted(CFG.glob("*.cfg")):
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


def test_bignvidia_modes_use_the_numeric_contract() -> None:
    # big-driver-manager-cli reads 1-8 as hybrid and 9-16 as nvidia
    kernels = CFG.joinpath("kernels.cfg").read_text(encoding="utf-8")
    modes = set(re.findall(r"\bbignvidia=([^\s]+)", kernels))
    assert modes <= {str(mode) for mode in range(1, 17)}


def test_free_boot_does_not_request_an_nvidia_mode() -> None:
    kernels = CFG.joinpath("kernels.cfg").read_text(encoding="utf-8")
    arguments = _boot_arguments(kernels, "2")
    assert "driver=free" in arguments
    assert not any(argument.startswith("bignvidia=") for argument in arguments)


def test_integrated_gpu_boot_avoids_all_nvidia_drivers() -> None:
    kernels = CFG.joinpath("kernels.cfg").read_text(encoding="utf-8")
    arguments = _boot_arguments(kernels, "3.5.2")
    assert "driver=free" in arguments
    assert not any(argument.startswith("bignvidia=") for argument in arguments)
    assert {
        "nvidia",
        "nvidia_drm",
        "nvidia_modeset",
        "nvidia_uvm",
        "nouveau",
        "nova",
        "nova_core",
    } <= _module_blacklist(arguments)


def test_proprietary_boot_entries_blacklist_open_nvidia_drivers() -> None:
    kernels = CFG.joinpath("kernels.cfg").read_text(encoding="utf-8")
    for entry_number in ("1", "3.5.1"):
        arguments = _boot_arguments(kernels, entry_number)
        assert "driver=nonfree" in arguments
        assert "nvidia_drm.modeset=1" in arguments
        assert {"nouveau", "nova", "nova_core"} <= _module_blacklist(arguments)


def _package_lines(path: Path) -> list[str]:
    return [
        line.split("#", 1)[0].strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.split("#", 1)[0].strip()
    ]


def test_drivers_come_from_big_driver_manager_cli_not_mhwd() -> None:
    legacy_override = LIVE_OVERLAY / "usr/lib/systemd/system/mhwd-live.service"
    assert not legacy_override.exists()
    for drop_in in ("mhwd-live.service.d", "nvidia-manager-verify.service.d"):
        assert not (SYSTEMD / drop_in).exists(), drop_in

    root_packages = _package_lines(ROOT / "shared/Packages-Root")
    assert "big-driver-manager-cli" in root_packages
    for retired in ("mhwd", "mhwd-db", "mhwd-biglinux", "xf86-video-intel"):
        assert retired not in root_packages, retired

    profiles = [ROOT / "shared/profile.conf"]
    profiles.extend(sorted(ROOT.glob("bigcommunity/*/profile.conf")))
    # Any edition at all, without pinning how many the repository ships.
    assert len(profiles) > 1
    for profile in profiles:
        text = profile.read_text(encoding="utf-8")
        disabled = re.search(
            r"^disable_systemd_live=\((?P<units>[^)]*)\)",
            text,
            re.MULTILINE,
        )
        assert disabled is not None, profile
        # big-driver-manager-live.service installs the live drivers instead
        assert "mhwd-live" in shlex.split(disabled.group("units")), profile

    package_lists = {ROOT / "shared/Packages-Live"}
    package_lists.update(profile.parent / "Packages-Live" for profile in profiles)
    for package_list in package_lists:
        requirements = [
            line
            for line in _package_lines(package_list)
            if line.startswith("biglinux-livecd")
        ]
        # The installer profile that runs big-driver-manager-cli, not mhwdcfg
        assert requirements == ["biglinux-livecd>=26.10.19-0000"], package_list


def test_offline_repository_drops_xorg_era_drivers() -> None:
    packages = _package_lines(ROOT / "shared/Packages-Mhwd")
    for retired in ("bumblebee", "primus", "KERNEL-bbswitch", "xf86-video-intel"):
        assert not any(line.split()[-1] == retired for line in packages), retired
    for kept in ("KERNEL-nvidia-open", "KERNEL-nvidia-580xx", "nvidia-prime"):
        assert any(line.split()[-1] == kept for line in packages), kept


def test_live_pacman_does_not_regenerate_initramfs() -> None:
    hooks = LIVE_OVERLAY / "usr/share/libalpm/hooks"
    for name in ("60-mkinitcpio-remove.hook", "90-mkinitcpio-install.hook"):
        hook = hooks / name
        assert hook.is_file()
        assert hook.stat().st_size == 0


def test_grub_fix_does_not_persist_live_only_gpu_controls() -> None:
    script = LIVE_OVERLAY.joinpath("usr/bin/grub-fix.sh").read_text(encoding="utf-8")
    sanitizer = re.search(r"\$\(sed '([^']+)' /proc/cmdline\)", script)
    assert sanitizer is not None
    command_line = (
        "BOOT_IMAGE=/boot/vmlinuz-x86_64 root=live driver=free "
        "bignvidia=12 quiet splash keep=yes\n"
    )
    sanitized = subprocess.run(
        ["sed", sanitizer.group(1)],
        input=command_line,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.split()
    assert "bignvidia=12" not in sanitized
    assert {"root=live", "keep=yes"} <= set(sanitized)


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
        for path in (CFG / "kernels.cfg", CFG / "languages.cfg")
    )
    classes = set(re.findall(r"--class=([a-z0-9-]+)", text))
    icon_names = {path.stem for path in THEME.joinpath("icons").glob("*.png")}
    assert classes <= icon_names


def test_language_selector_covers_catalogs() -> None:
    assert len(LINGUAS) == 29
    selector = CFG.joinpath("languages.cfg").read_text(encoding="utf-8")
    selected = re.findall(r"select_language\s+([A-Za-z_]+)\s+", selector)
    assert selected == LINGUAS


def test_language_selector_uses_a_dedicated_page() -> None:
    cases = ((CFG / "kernels.cfg", 'menuentry $"4 - Language:'),)
    language_state = 'elif [ "${bigcommunity_menu}" = "language" ]; then'
    for path, language_label in cases:
        text = path.read_text(encoding="utf-8")
        root_page, language_page = text.split(language_state, 1)
        language_page = language_page.split("\nelif ", 1)[0]
        assert language_label in root_page
        assert 'set bigcommunity_menu="language"' in root_page
        assert "source /boot/grub/languages.cfg" not in root_page
        assert "source /boot/grub/languages.cfg" in language_page
        assert text.count("source /boot/grub/languages.cfg") == 1
        assert "bigcommunity_language_expanded" not in text

    for selector_path in (CFG / "languages.cfg",):
        selector = selector_path.read_text(encoding="utf-8")
        assert "bigcommunity_language_expanded" not in selector
        assert selector.count('set bigcommunity_menu="root"') == 2
        assert 'menuentry $"Back to main menu"' in selector
        assert selector.count("menu_reload") == 2


def test_dispatcher_reloads_nested_menu_states() -> None:
    for path in (CFG / "kernels.cfg",):
        text = path.read_text(encoding="utf-8")
        assert "normal /boot/grub/kernels.cfg" not in text
        assert "normal_exit" not in text
        assert "menu_reload" in text


def test_catalogs_are_complete_and_compiled() -> None:
    for locale in LINGUAS:
        po = I18N / "po" / f"{locale}.po"
        shared_mo = SHARED / "locales/bigcommunity" / f"{locale}.mo"
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
    assets = re.findall(r'^desktop-image:\s*"([^"]+)"', theme, re.MULTILINE)
    assets += re.findall(
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


def test_uefi_memtest_uses_chainloader() -> None:
    for kernels in (CFG / "kernels.cfg",):
        text = kernels.read_text(encoding="utf-8")
        assert "chainloader /boot/memtest-efi" in text
        assert "linux16 /boot/memtest-efi" not in text


def test_legacy_backups_are_removed() -> None:
    assert not CFG.joinpath("kernels.cfg.bak").exists()
    assert not SHARED.parent.joinpath("boot/grub.bak").exists()
