"""The firewall ships on, denying incoming connections except Samba, mDNS and SSH.

Off (2026-11-14 to 11-24), the installed system answered on every network it
joined: Samba, Avahi and dnsmasq (an open DNS forwarder). The 11-14 complaint
that turned it off was SSH being blocked; SSH is now one of the allowed rules,
so it answers as soon as sshd is turned on. ufw.conf stays ASCII: ufw rewrites
it in ASCII and "ufw enable"/"ufw disable" failed with UnicodeEncodeError on
the accented comment it had.
"""

from __future__ import annotations

import re
from pathlib import Path

EDITION = Path(__file__).resolve().parent.parent / "bigcommunity/wmaker"


def test_ufw_is_on_by_default() -> None:
    conf = (EDITION / "desktop-overlay/etc/ufw/ufw.conf").read_text(encoding="utf-8")
    assert re.findall(r"^ENABLED=(\w+)$", conf, re.M) == ["yes"]


def test_ufw_conf_is_ascii() -> None:
    # ufw writes ufw.conf back with bytes(line, "ascii") on enable/disable
    (EDITION / "desktop-overlay/etc/ufw/ufw.conf").read_bytes().decode("ascii")


def test_ufw_service_is_enabled() -> None:
    profile = (EDITION / "profile.conf").read_text(encoding="utf-8")
    enabled = re.search(r"^enable_systemd=\((.*)\)$", profile, re.M)
    assert enabled and "'ufw'" in enabled.group(1)


def _active_rules(text: str, chain: str) -> list[tuple[str, str, str]]:
    """(action proto ports) of each tuple, checked against the -A line under it."""
    lines = [line for line in text.splitlines() if line.strip()]
    rules = []
    for i, line in enumerate(lines):
        if line.startswith(f"-A {chain} "):
            assert lines[i - 1].startswith("### tuple ### "), f"rule without tuple: {line}"
        if not line.startswith("### tuple ### "):
            continue
        action, proto, ports = line.split()[3:6]
        rule = lines[i + 1].split()
        assert rule[:2] == ["-A", chain], f"tuple without rule: {line}"
        assert rule[rule.index("-p") + 1] == proto
        flag = "--dports" if "," in ports else "--dport"
        assert rule[rule.index(flag) + 1] == ports
        assert rule[rule.index("-j") + 1] == {"allow": "ACCEPT"}[action]
        rules.append((action, proto, ports))
    return rules


def test_ufw_allows_samba_mdns_and_ssh_on_ipv4_and_ipv6() -> None:
    expected = {("allow", "udp", "137,138"), ("allow", "tcp", "139,445"),
                ("allow", "udp", "5353"), ("allow", "tcp", "22")}
    for name, chain in (("user.rules", "ufw-user-input"), ("user6.rules", "ufw6-user-input")):
        rules = (EDITION / "desktop-overlay/etc/ufw" / name).read_text(encoding="utf-8")
        assert set(_active_rules(rules, chain)) == expected, name


def test_split_packages_called_by_the_menus_are_installed() -> None:
    # The root menus of both sessions call big-wm-welcome and big-wm-zoom;
    # they are split packages of big-wm, not dependencies of the session.
    names = set()
    for line in (EDITION / "Packages-Desktop").read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            names.add(line.split()[0])
    assert {"big-wm-welcome", "big-wm-zoom"} <= names


def test_cdn_mirrors_use_https() -> None:
    # shared/ keeps http (other editions); the CDN serves the same files over
    # https, and pacman (SigLevel DatabaseNever) trusts the database it gets
    mirrorcdn = EDITION / "root-overlay/etc/pacman.d/mirrorcdn"
    assert not mirrorcdn.is_symlink()
    servers = re.findall(r"^Server\s*=\s*(\S+)", mirrorcdn.read_text(encoding="utf-8"), re.M)
    assert servers and all(s.startswith("https://") for s in servers)


def test_mirrorlist_and_pacman_mirrors_use_https_only() -> None:
    # The installer (pacman-mirrors -f3/-f 5) and the pamac timer regenerate
    # the mirrorlist; with the package default (no Protocols) they sometimes
    # picked an http mirror (openQA installed_security, ISO r72). The static
    # list is what an offline install copies from the live session.
    etc = EDITION / "root-overlay/etc"
    conf = (etc / "pacman-mirrors.conf").read_text(encoding="utf-8")
    assert re.findall(r"^Protocols\s*=\s*(.+?)\s*$", conf, re.M) == ["https"]
    mirrorlist = (etc / "pacman.d/mirrorlist").read_text(encoding="utf-8")
    servers = re.findall(r"^\s*Server\s*=\s*(\S+)", mirrorlist, re.M)
    assert servers and all(s.startswith("https://") for s in servers)
