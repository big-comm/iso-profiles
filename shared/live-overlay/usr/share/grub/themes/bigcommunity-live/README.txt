BigCommunity Live - Compact Minimal

Objetivo:
- manter o fundo atual (background_fx.png, herdado do tema anterior, com os
  "cards" pintados do cabeçalho e do rodapé removidos - só o painel do menu
  ficou, porque é o único que casa com a geometria);
- usar o novo cabeçalho/logo (header.png);
- reduzir ruído visual;
- ícones pequenos monocromáticos em roxo;
- seleção discreta, sem gradiente;
- compatível com o boot_menu vertical padrão do GRUB gfxmenu.

Instalação: o tema é copiado para /boot/grub/themes/bigcommunity-live/ na ISO
live e apontado por cfg/variable.cfg (grub_theme). A fonte ter-u22b.pf2 é
carregada por cfg/grub.cfg; unicode.pf2 cobre os alfabetos não latinos do
seletor de idioma.

Restrições descobertas em teste real (grub-mkrescue + QEMU, 1024x768):

- boot_menu está alinhado ao painel desenhado no background_fx.png
  (left 14% / top 37% / width 72% / height 39%). Mexer na geometria sem
  regerar o fundo faz o painel pintado e o menu desencontrarem. O fundo é
  esticado (desktop-image-scale-method stretch) e a geometria é percentual,
  então o alinhamento se mantém em qualquer resolução.
- o GRUB nao reduz imagem: o tamanho nativo do bitmap e o minimo do
  componente, entao width/height menores no + image sao ignorados. header.png
  tem 460x190 e e desenhado com esses 460px; o offset de left tem de ser
  50%-230 (metade da largura real) ou o logo fica descentralizado - com
  50%-170 ele aparecia 60px a direita.
- select_*.png tem fatias de 6px, então a moldura da seleção cresce 6px acima
  e abaixo da linha. item_spacing precisa ser >= 12 ou a seleção invade o texto
  das entradas vizinhas.
- scrollbar_width tem de ser bem maior que as fatias de scrollbar_*.png; com
  fatias de 3px e largura 14 o polegar fica visível. Fatias grossas com largura
  pequena colapsam o polegar para 1px (a barra fica praticamente invisível).
- o GRUB impõe uma altura mínima à progress_bar (altura da fonte, ~28px),
  mesmo com height menor, sem text e com pixmaps. E ele desenha o highlight
  dentro da área de conteúdo do trilho, isto é, deslocado pelo pad do trilho.
  Daí a barra fina de 6px:
    * progress_bar_*.png (trilho) usa fatias de 1px de largura por 11px de
      altura e só pinta a FILEIRA DO MEIO do 9-slice, que o GRUB comprime de
      11px para altura-22 = 6px. As fatias do 9-slice podem ter largura e
      altura independentes, e isso é essencial aqui: o GRUB desenha o
      preenchimento deslocado pelos pads do trilho, então uma fatia larga
      (11px) empurrava o roxo 11px para dentro e deixava um pedaço de trilho
      vazio antes do começo da barra. Com 1px de largura o preenchimento
      começa junto do trilho;
    * progress_highlight_*.png usa fatias de 2px e é desenhado pelo GRUB em
      y=11 com exatamente esses mesmos 6px.
  Os dois derivam da mesma conta, então continuam alinhados se a altura mínima
  mudar. Fatias iguais nos dois arquivos desalinham as barras (o trilho fica
  em cima e o preenchimento embaixo) ou engordam a barra para os 28px.
- @TIMEOUT_NOTIFICATION_*@ só funciona em progress_bar. Em label o contador é
  "%ds", que o GRUB substitui pelo número - e que dispensa tradução.
- com item_height 32 + item_spacing 12 cabem 6 entradas sem rolagem; o menu 3
  (7 entradas) e o seletor de idioma (30) rolam com a barra visível.

PREVIEW.png é uma captura real do QEMU, não uma montagem.
