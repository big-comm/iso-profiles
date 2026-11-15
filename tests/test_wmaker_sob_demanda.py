"""Serviços do sistema sob demanda na edição wmaker (missão de memória do
Big WindowMaker, Etapa B/F). O ModemManager continua instalado e habilitado,
mas só sobe com um possível modem; o render-menu-options do usuário não
segura mais o login. Samba e CUPS ficam como estão (rejeitados, ver
docs/performance-decisions.md do big-wm). Tudo fica no desktop-overlay da
edição; o shared/ e as outras edições não mudam."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OV = ROOT / "bigcommunity" / "wmaker" / "desktop-overlay"
SYS = OV / "etc" / "systemd" / "system"


def _linhas(p):
    return [l.strip() for l in p.read_text().splitlines() if l.strip() and not l.lstrip().startswith("#")]


def test_modemmanager_so_com_modem():
    conds = [l for l in _linhas(SYS / "ModemManager.service.d" / "bigwm-sob-demanda.conf")
             if l.startswith("Condition")]
    assert conds and all(l.startswith("ConditionPathExistsGlob=|") for l in conds)
    for pat in ("/dev/ttyUSB*", "/dev/ttyACM*", "/dev/cdc-wdm*", "/sys/class/wwan/*"):
        assert f"ConditionPathExistsGlob=|{pat}" in conds
    regras = _linhas(OV / "etc" / "udev" / "rules.d" / "90-bigwm-modemmanager.rules")
    assert len(regras) == 3
    assert all('ENV{SYSTEMD_WANTS}+="ModemManager.service"' in r and 'TAG+="systemd"' in r for r in regras)


def test_render_menu_options_nao_segura_o_login():
    conf = _linhas(OV / "etc" / "systemd" / "user" / "render-menu-options-user.service.d" / "bigwm-nao-bloqueia.conf")
    assert "Type=exec" in conf
    assert "ExecStartPre=" in conf  # zera o sleep do pacote
    start = [l for l in conf if l.startswith("ExecStart=") and l != "ExecStart="]
    assert len(start) == 1 and "sleep 10" in start[0] and "render-menu-options.sh" in start[0]
    assert '"$$1"' in start[0]  # $$: o systemd não expande, o sh recebe $1
    assert "Nice=19" in conf and "IOSchedulingClass=idle" in conf


def test_snapshot_detect_so_em_boot_por_snapshot():
    conf = _linhas(OV / "etc" / "systemd" / "user" / "biglinux-snapshot-detect.service.d" / "bigwm-so-em-snapshot.conf")
    # O mesmo teste do aplicativo (biglinux-snapshot-restore.py, is_in_snapshot).
    assert "ExecCondition=/bin/sh -c 'grep -q timeshift-btrfs/snapshots /proc/cmdline'" in conf


def test_driver_manager_gpu_so_com_nvidia_ou_no_live():
    # Antes do display manager; sem NVIDIA e fora do live o "gpu boot" não
    # faz nada, e listava todos os pacotes (pacman -Qq) num disco frio.
    conf = _linhas(SYS / "big-driver-manager-gpu.service.d" / "bigwm-so-com-nvidia.conf")
    assert ("ExecCondition=/bin/sh -c 'test -e /livefs-pkgs.txt || "
            "grep -qsx 0x10de /sys/bus/pci/devices/*/vendor'") in conf


def test_auto_unlock_pacman_sem_disputar_o_disco():
    conf = _linhas(SYS / "auto-unlock-pacman.service.d" / "bigwm-sem-disputar-o-disco.conf")
    assert "Nice=19" in conf and "IOSchedulingClass=idle" in conf
    assert not any(l.startswith(("Exec", "Condition")) for l in conf)  # continua a cada boot


def test_nada_no_shared():
    # Os arquivos novos são da edição: nenhum caminho passa pelo shared/
    # (o desktop-overlay/usr da edição é link para o shared/).
    shared = (ROOT / "shared").resolve()
    for p in [SYS / "ModemManager.service.d",
              OV / "etc" / "udev" / "rules.d" / "90-bigwm-modemmanager.rules",
              OV / "etc" / "systemd" / "user" / "render-menu-options-user.service.d",
              OV / "etc" / "systemd" / "user" / "biglinux-snapshot-detect.service.d",
              SYS / "big-driver-manager-gpu.service.d",
              SYS / "auto-unlock-pacman.service.d"]:
        assert shared not in p.resolve().parents, p
