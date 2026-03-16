# Auditoria Completa — iso-profiles BigCommunity

## Resumo

Auditoria realizada em todos os perfis do repositório `iso-profiles`.
Encontrados **28 problemas** classificados por severidade.

---

## CRÍTICOS (Correção Automática)

### C1 — Cosmic: displaymanager errado
- **Arquivo:** `bigcommunity/cosmic/profile.conf` linha 8
- **Atual:** `displaymanager="gdm"`
- **Pacotes instalados:** `lightdm`, `lightdm-webkit2-greeter`, `lightdm-webkit2-theme-community`
- **Overlays:** `lightdm.conf` em live-overlay e root-overlay
- **Correção:** `displaymanager="lightdm"`

### C2 — Hyprland: displaymanager vazio
- **Arquivo:** `bigcommunity/hyprland/profile.conf` linha 8
- **Atual:** `displaymanager=""`
- **Pacotes instalados:** `sddm`, `sddm-theme-biglinux`
- **Overlays:** `sddm.conf` em live-overlay e root-overlay
- **Correção:** `displaymanager="sddm"`

### C3 — Cinnamon: bluetooth duplicado + ufw faltando no enable_systemd
- **Arquivo:** `bigcommunity/cinnamon/profile.conf` linha 46
- **Atual:** `enable_systemd=('bluetooth' ... 'vboxservice' 'bluetooth' 'avahi-daemon' 'smb' ...)`
- **Problemas:** `bluetooth` aparece 2x, `ufw` não está presente
- **Correção:** Remover `bluetooth` duplicado, adicionar `ufw`

### C4 — Core: bluetooth duplicado + sshd no lugar de smb
- **Arquivo:** `bigcommunity/core/profile.conf` linha 46
- **Atual:** `enable_systemd=('bluetooth' ... 'vboxservice' 'bluetooth' 'avahi-daemon' 'sshd' ...)`
- **Problemas:** `bluetooth` aparece 2x, tem `sshd` ao invés de `smb`, falta `ufw`
- **Nota:** `sshd` pode ser intencional para perfil "core" (servidor). Manter, mas adicionar `smb` e `ufw`.
- **Correção:** Remover `bluetooth` duplicado, adicionar `ufw` e `smb`

### C5 — Xfce: systemd-timesyncd duplicado
- **Arquivo:** `bigcommunity/xfce/profile.conf` linha 47
- **Atual:** `enable_systemd=('systemd-timesyncd' ... 'cups-browsed' 'systemd-timesyncd')`
- **Correção:** Remover o `systemd-timesyncd` duplicado (manter no início)

### C6 — shared/Packages-Root: pacotes duplicados
- **Arquivo:** `shared/Packages-Root`
- **Duplicados encontrados:**
  - `auto-unlock-pacman-git` (2x)
  - `biglinux-hibernate-in-swapfile-btrfs` (2x)
  - `virtualbox-guest-utils` (2x)
  - `vulkan-tools` (2x)
- **Correção:** Remover as ocorrências duplicadas

---

## AVISOS (Correção Automática)

### A1 — Gnome: desktop-overlay sem symlinks para shared
- **Problema:** Gnome não tem symlinks `desktop-overlay/etc` e `desktop-overlay/usr` para `shared/desktop-overlay/`
- **Impacto:** pam.d/sudo, pam.d/polkit-1, environment, useradd, icons não se aplicam às ISOs Gnome
- **Correção:** Criar symlinks `etc` → `../../../shared/desktop-overlay/etc` e `usr` → `../../../shared/desktop-overlay/usr`

### A2 — Xfce: label inconsistente
- **Arquivo:** `bigcommunity/xfce/profile.conf` linha 21
- **Atual:** `label="BIGCOMMUNITY_LIVE_XFCE"`
- **Padrão dos outros:** `label="BigCommunity.iso"`
- **Correção:** Padronizar para `label="BigCommunity.iso"`

---

## REQUEREM DECISÃO DO USUÁRIO

### D1 — Deepin: displaymanager vs pacotes
- **profile.conf:** `displaymanager="lightdm"` + overlay com lightdm.conf
- **Packages-Desktop:** instala `sddm` (sem lightdm)
- **Opções:**
  A) Trocar pacote `sddm` por `lightdm` + `lightdm-slick-greeter` em Packages-Desktop
  B) Trocar profile.conf para `displaymanager="sddm"` e atualizar overlay
- **Recomendação:** Opção A (DDE tradicionalmente usa lightdm)

### D2 — Gnome: user-repos.conf único com repos extras
- **Arquivo:** `bigcommunity/gnome/user-repos.conf`
- **Conteúdo:** Adiciona `[biglinux-update-stable]` e `[biglinux-stable]`
- **Outros perfis:** user-repos.conf é vazio
- **Nota:** `[biglinux-update-stable]` já está em `shared/pacman.conf`
- **Opções:**
  A) Propagar para todos os perfis
  B) Remover do gnome (repos redundantes)
  C) Manter como está (intencional para gnome)

### D3 — systemd-timesyncd inconsistente entre perfis
- **COM `systemd-timesyncd`:** cinnamon, core, gnome, xfce
- **SEM:** kde, cosmic, deepin, hyprland, shared
- **Opções:**
  A) Adicionar a TODOS os perfis
  B) Remover de todos (deixar no shared)
  C) Manter diferença (cada perfil escolhe)

### D4 — Minimal: Branch = testing
- **Arquivo:** `bigcommunity/minimal/pacman-mirrors.conf` linha 6
- **Atual:** `Branch = testing`
- **Esperado para produção:** `Branch = stable`
- **Requer confirmação:** Pode ser intencional para desenvolvimento

---

## INFORMATIVOS

### I1 — Cinnamon/Xfce: lightdm-webkit2-greeter.conf sem webkit2-greeter instalado
- Ambos têm `lightdm-webkit2-greeter.conf` em root-overlay
- Mas instalam `lightdm-slick-greeter`, não `lightdm-webkit2-greeter`
- Arquivo de config fica órfão (sem efeito, mas desnecessário)

### I2 — KDE: kfind duplicado em Packages-Desktop
- `kfind` aparece nas linhas ~4 e ~105

### I3 — KDE: big-preload duplicado entre Packages-Root e Packages-Desktop
- `big-preload` está em shared/Packages-Root e em kde/Packages-Desktop

### I4 — Inconsistência de addgroups entre perfis
- `kde/cinnamon/cosmic/hyprland/core`: `lp,network,power,wheel,sambashare,audio`
- `gnome/xfce`: `lp,network,power,wheel,sambashare,users,storage,input,audio`
- `deepin`: `lp,network,power,wheel,sambashare,audio,trezord,plugdev`
- Pode ser intencional por DE

### I5 — Core: Packages-Live contém desktop Cinnamon completo
- Core instala ~260 pacotes no live (incluindo Cinnamon, lightdm, jogos)
- Mas Packages-Desktop só tem `btop`
- Padrão: live com GUI para instalador, sistema instalado é CLI

### I6 — Deepin: pacotes faltantes comparado com outros perfis
- Sem Xorg packages (xorg-server ausente)
- Sem Wayland packages (wayland-protocols, wayland-utils)
- Sem gvfs stack completo
- Sem espeak-ng (backend do orca/speech-dispatcher)
- Sem bibata-cursor-theme

---

## Etapas de Execução

### Fase 1 — Correções Automáticas (Sem Risco)
1. [x] Fix C1 — Cosmic displaymanager → lightdm
2. [x] Fix C2 — Hyprland displaymanager → sddm
3. [x] Fix C3 — Cinnamon enable_systemd (bluetooth dup, +ufw)
4. [x] Fix C4 — Core enable_systemd (bluetooth dup, +ufw, +smb)
5. [x] Fix C5 — Xfce enable_systemd (systemd-timesyncd dup)
6. [x] Fix C6 — shared/Packages-Root duplicados
7. [x] Fix A1 — Gnome desktop-overlay symlinks
8. [x] Fix A2 — Xfce label padronizado
9. [x] Fix I2 — KDE kfind duplicado
10. [x] Fix I3 — KDE big-preload duplicado

### Fase 2 — Decisões do Usuário
11. [ ] D1 — Deepin DM (lightdm vs sddm)
12. [ ] D2 — Gnome user-repos.conf
13. [ ] D3 — systemd-timesyncd padronização
14. [ ] D4 — Minimal Branch testing

### Fase 3 — Validação
15. [x] Acesso remoto SSH realizado — diagnósticos coletados
16. [x] bpftune-git desabilitado (causa crash no biglinux-improve-compatibility)
17. [ ] Build de ISO com todas as correções
18. [ ] Teste boot em hardware híbrido Intel/NVIDIA

## Diagnóstico Remoto (SSH 192.168.0.121)

### Sistema
- **Kernel:** 6.18.12-1-MANJARO
- **GPU:** Intel HD 630 + NVIDIA GTX 1050 Ti Mobile
- **Driver:** nouveau + i915 (modesetting) — SEM driver proprietário
- **Boot time:** ~1min (15s userspace)

### Problemas Encontrados

1. **biglinux-improve-compatibility.service FAILED**
   - Causa: bpftune-git instala `/etc/init.d/bpftune` com shebang OpenRC
   - Script tenta executar e falha: "bad interpreter: No such file"
   - **Corrigido:** bpftune-git desabilitado no Packages-Root

2. **MHWD configs inválidos (warnings)**
   - `nvidia-390xx` e `hybrid-intel-nvidia-390xx-bumblebee` — driver descontinuado
   - `r8168` e `rt3562sta` — drivers de rede antigos
   - Causa: mhwd-db tem configs antigos. Não é problema do iso-profiles.

3. **GPU sem driver proprietário**
   - Apenas video-modesetting instalado via MHWD
   - nvidia-smi indisponível
   - Nota: mhwd-live.service completou (3s) neste boot, usando modesetting
