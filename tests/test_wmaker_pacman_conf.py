"""O pacman.conf da edição wmaker é o shared/pacman.conf mais o repositório
[big-wm] (big-windowmaker/repo), antes de todos os outros. Qualquer outra
diferença é um esquecimento: as mudanças do shared têm de chegar aqui também.

O IgnorePkg do windowmaker saiu: o windowmaker do Big WindowMaker tem
epoch=1 (big-windowmaker/packages), e o do extra não parece mais novo."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SHARED = ROOT / "shared" / "pacman.conf"
WMAKER = ROOT / "bigcommunity" / "wmaker" / "root-overlay" / "etc" / "pacman.conf"
PACOTES = ROOT / "bigcommunity" / "wmaker" / "Packages-Desktop"


def _secoes(texto):
    return [l.strip() for l in texto.splitlines() if l.strip().startswith("[")]


def _sem_big_wm(texto):
    saida, pular = [], False
    for linha in texto.splitlines():
        if linha.startswith("# Big WindowMaker: o repositório assinado [big-wm]"):
            pular = True
        if pular:
            if linha.startswith("Server = https://github.com/big-windowmaker/repo/"):
                pular = None  # a linha em branco depois do bloco também sai
            continue
        if pular is None:
            pular = False
            if not linha.strip():
                continue
        saida.append(linha)
    return saida


def test_big_wm_antes_de_todos_os_repositorios():
    assert not WMAKER.is_symlink()
    secoes = _secoes(WMAKER.read_text())
    assert secoes[:2] == ["[options]", "[big-wm]"]


def test_big_wm_assinado():
    linhas = WMAKER.read_text().splitlines()
    i = linhas.index("[big-wm]")
    bloco = linhas[i + 1:i + 3]
    assert bloco == [
        "SigLevel = Required",
        "Server = https://github.com/big-windowmaker/repo/releases/download/$arch",
    ]


def test_sem_ignorepkg_do_windowmaker():
    ativos = [l.split("#", 1)[0].split() for l in WMAKER.read_text().splitlines()]
    assert not any(l[:1] == ["IgnorePkg"] for l in ativos)


def test_chaveiro_na_iso():
    assert "big-wm-keyring" in PACOTES.read_text().split()


def test_wmaker_igual_ao_shared_fora_o_big_wm():
    assert _sem_big_wm(WMAKER.read_text()) == SHARED.read_text().splitlines()
