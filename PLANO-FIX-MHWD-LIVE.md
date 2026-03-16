# Plano de Correção — Hang do mhwd-live.service em GPUs Híbridas Intel/NVIDIA

## Problema

O serviço systemd `mhwd-live.service` (Manjaro Hardware Detection) trava indefinidamente
durante o boot da LiveMedia em sistemas com GPU híbrida Intel/NVIDIA.
O serviço aparece como `"2min 11s / no limit"` na tela de boot e nunca completa.

**Perfis afetados:** Todos (Cinnamon, KDE, GNOME, XFCE, Cosmic, Deepin, Hyprland, Core)
**Hardware afetado:** Somente sistemas com GPU híbrida Intel + NVIDIA

## Causa Raiz

1. A variável `enable_systemd_live` está **comentada** em todos os `profile.conf`
   (tanto shared quanto perfis individuais):
   ```
   # enable_systemd_live=('manjaro-live' 'mhwd-live' 'pacman-init' 'mirrors-live')
   ```
   
2. Quando comentada, o manjaro-tools usa o valor **padrão**, que inclui `mhwd-live`

3. A variável `disable_systemd_live` **não inclui** `mhwd-live`:
   ```
   disable_systemd_live=('mirrors-live' 'pacman-init' 'ufw' 'fstrim.timer' 'big-btrfs-balance' 'auto-unlock-pacman')
   ```

4. Não existe arquivo override vazio em `shared/live-overlay/usr/lib/systemd/system/mhwd-live.service`

5. Resultado: o serviço vanilla `mhwd-live` do manjaro-tools executa durante live boot
   e trava ao tentar detectar/instalar drivers NVIDIA em hardware híbrido

## Por que é seguro desabilitar

- O pacote `mhwd-biglinux` já está em `Packages-Root` de todos os perfis
- Os drivers NVIDIA já estão em `Packages-Mhwd` (nvidia, nvidia-open, nvidia-470xx)
- O `switcheroo-control` já está em `Packages-Root` para gerenciamento de GPU híbrida
- O `biglinux-driver-manager` está disponível para o usuário pós-boot
- O serviço vanilla `mhwd-live` é redundante no contexto BigCommunity/BigLinux

## Etapas da Correção

### Etapa 1 — Override mhwd-live.service (shared live-overlay)

**Ação:** Criar arquivo vazio `mhwd-live.service` no diretório shared live-overlay.

**Caminho:** `shared/live-overlay/usr/lib/systemd/system/mhwd-live.service`

**Mecanismo:** Quando o systemd encontra um arquivo de unit vazio, se recusa a iniciar
o serviço. Isso segue o padrão já estabelecido no projeto:
- `pacman-init.service` (vazio)
- `big-mount.service` (vazio)
- `big-btrfs-balance.service` (vazio)
- `auto-unlock-pacman.service` (vazio)
- `ufw.service` (vazio)

### Etapa 2 — Adicionar mhwd-live ao disable_systemd_live (shared/profile.conf)

**Ação:** Adicionar `'mhwd-live'` ao array `disable_systemd_live` no `shared/profile.conf`.

**Redundância intencional:** O override do arquivo (Etapa 1) é o mecanismo primário.
A entrada no `disable_systemd_live` é uma camada adicional de segurança, seguindo o
mesmo padrão usado para `pacman-init`, `ufw`, `big-btrfs-balance`, `auto-unlock-pacman`.

### Etapa 3 — Atualizar disable_systemd_live nos perfis

**Ação:** Adicionar `'mhwd-live'` em todos os `profile.conf` de perfis que sobrescrevem
o `disable_systemd_live` do shared:

- `bigcommunity/cinnamon/profile.conf`
- `bigcommunity/core/profile.conf`
- `bigcommunity/cosmic/profile.conf`
- `bigcommunity/deepin/profile.conf`
- `bigcommunity/gnome/profile.conf`
- `bigcommunity/hyprland/profile.conf`
- `bigcommunity/kde/profile.conf`
- `bigcommunity/xfce/profile.conf`

### Etapa 4 — Validação

- Verificar que o arquivo override foi criado corretamente (vazio)
- Verificar consistência de todos os profile.conf
- Testar build da ISO (se possível via acesso remoto)

## Impacto

- **Nenhuma regressão** em hardware não-NVIDIA (o serviço não é necessário)
- **Resolve o hang** em hardware híbrido Intel/NVIDIA
- **Drivers continuam disponíveis:** via mhwd-biglinux e packages diretos na ISO
- **Consistente** com o padrão já usado para desabilitar outros serviços
