"""A edição Big WindowMaker registra os travamentos (coredumpctl), com
limite de tamanho, mesmo com o auto-rules-io e o
biglinux-improve-compatibility desligando os dumps nas outras edições."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ETC = ROOT / "bigcommunity" / "wmaker" / "root-overlay" / "etc"
SYSCTL = ETC / "sysctl.d" / "99-zz-big-wm-coredump.conf"
COREDUMP = ETC / "systemd" / "coredump.conf.d" / "zz-big-wm.conf"
SYSTEMD_DEFAULT = Path("/usr/lib/sysctl.d/50-coredump.conf")


def _ativas(path):
    return [l.strip() for l in path.read_text().splitlines() if l.strip() and not l.lstrip().startswith("#")]


def test_vem_depois_dos_que_desligam():
    # sysctl.d e coredump.conf.d: o último na ordem dos nomes vale
    assert SYSCTL.name > "99-games-tweaks.conf"
    assert COREDUMP.name > "custom.conf"


def test_core_pattern_do_systemd():
    linha = [l for l in _ativas(SYSCTL) if l.startswith("kernel.core_pattern")]
    assert linha and linha[0].startswith("kernel.core_pattern=|/usr/lib/systemd/systemd-coredump ")
    if SYSTEMD_DEFAULT.exists():  # a mesma linha do systemd instalado
        assert linha[0] in _ativas(SYSTEMD_DEFAULT)


def test_dumps_com_limite():
    assert _ativas(COREDUMP) == [
        "[Coredump]", "Storage=external", "ProcessSizeMax=512M", "ExternalSizeMax=512M", "MaxUse=1G"]
