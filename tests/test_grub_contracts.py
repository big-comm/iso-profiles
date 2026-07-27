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
MINIMAL = ROOT / "bigcommunity/minimal/live-overlay/usr/share/grub"
CFG = SHARED / "cfg"
MINIMAL_CFG = MINIMAL / "cfg"
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


def _systemd_directives(path: Path) -> dict[str, dict[str, list[str]]]:
    assert path.is_file()
    sections: dict[str, dict[str, list[str]]] = {}
    section: str | None = None
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith(("#", ";")):
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
            sections.setdefault(section, {})
            continue
        assert section is not None and "=" in line, (path, raw_line)
        key, value = line.split("=", 1)
        sections[section].setdefault(key, []).append(value)
    return sections


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


def test_bignvidia_modes_use_the_mhwd_numeric_contract() -> None:
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


def test_mhwd_live_is_enabled_for_full_offline_profiles() -> None:
    legacy_override = LIVE_OVERLAY / "usr/lib/systemd/system/mhwd-live.service"
    assert not legacy_override.exists()

    profiles = [ROOT / "shared/profile.conf"]
    profiles.extend(
        path
        for path in sorted(ROOT.glob("bigcommunity/*/profile.conf"))
        if path.parent.name != "minimal"
    )
    assert len(profiles) == 9
    for profile in profiles:
        text = profile.read_text(encoding="utf-8")
        disabled = re.search(
            r"^disable_systemd_live=\((?P<units>[^)]*)\)",
            text,
            re.MULTILINE,
        )
        assert disabled is not None, profile
        assert "mhwd-live" not in shlex.split(disabled.group("units")), profile

    package_lists = {ROOT / "shared/Packages-Live"}
    package_lists.update(profile.parent / "Packages-Live" for profile in profiles)
    for package_list in package_lists:
        packages = [
            line.split("#", 1)[0].strip()
            for line in package_list.read_text(encoding="utf-8").splitlines()
        ]
        requirements = [
            line for line in packages if line.startswith("biglinux-livecd")
        ]
        assert requirements == ["biglinux-livecd>=26.07.24-0157"], package_list


def test_mhwd_live_service_uses_the_offline_mkinitcpio_shim() -> None:
    drop_in = _systemd_directives(
        SYSTEMD / "mhwd-live.service.d/10-bigcommunity.conf"
    )
    assert drop_in["Unit"] == {
        "After": ["livecd-tweaks.service"],
        "Before": ["nvidia-manager-verify.service display-manager.service"],
        "ConditionPathExists": [
            "/livefs-pkgs.txt",
            "/opt/mhwd/pacman-mhwd.conf",
        ],
        "ConditionFileIsExecutable": [
            "/usr/lib/biglinux-livecd/shims/mkinitcpio"
        ],
    }
    assert drop_in["Service"] == {
        "BindReadOnlyPaths": [
            "/usr/lib/biglinux-livecd/shims/mkinitcpio:/usr/bin/mkinitcpio"
        ],
        "TimeoutStartSec": ["3min"],
        "TimeoutStopSec": ["5s"],
        "KillMode": ["control-group"],
    }


def test_live_pacman_does_not_regenerate_initramfs() -> None:
    hooks = LIVE_OVERLAY / "usr/share/libalpm/hooks"
    for name in ("60-mkinitcpio-remove.hook", "90-mkinitcpio-install.hook"):
        hook = hooks / name
        assert hook.is_file()
        assert hook.stat().st_size == 0


def test_nvidia_verifier_uses_only_offline_live_resources() -> None:
    drop_in = _systemd_directives(
        SYSTEMD / "nvidia-manager-verify.service.d/10-bigcommunity.conf"
    )
    assert drop_in["Unit"] == {
        "ConditionPathExists": [
            "/livefs-pkgs.txt",
            "/opt/mhwd/pacman-mhwd.conf",
        ],
        "ConditionFileIsExecutable": [
            "/usr/lib/biglinux-livecd/shims/mkinitcpio"
        ],
        "ConditionKernelCommandLine": ["driver=nonfree"],
    }
    assert drop_in["Service"] == {
        "BindReadOnlyPaths": [
            "/opt/mhwd/pacman-mhwd.conf:/etc/pacman.conf",
            "/usr/lib/biglinux-livecd/shims/mkinitcpio:/usr/bin/mkinitcpio",
        ],
        "TimeoutStartSec": ["60s"],
        "TimeoutStopSec": ["5s"],
        "KillMode": ["control-group"],
    }


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
