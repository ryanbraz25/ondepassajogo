# Criativos do Onde Passa Jogo

Gerador dos vídeos (Reels/TikTok 1080x1920) e das artes (feed 1080x1350, story 1080x1920) com a cara do site.
Tudo sai dos dados reais da agenda (`dados/jogos.json`).

## Preparar (uma vez por sessão)
```bash
mkdir -p /tmp/vid/out && cp criativos/* /tmp/vid/ && cp site/logo.svg /tmp/vid/
cd /tmp/vid && npm i -s @fontsource/barlow @fontsource/barlow-condensed
rm -rf /tmp/t && cp -r <repo> /tmp/t && (cd /tmp/t && python3 robo/atualizar.py --offline)   # site local para filmar
cp /tmp/vid/fonts.css /tmp/t/site/fonts-local.css
python3 /tmp/vid/shots.py        # telas do site (s_home, s_bra, s_gratis, s_jogo)
```

## Gerar
- Artes: `python3 posts.py /tmp/t/dados/jogos.json AAAA-MM-DD` (data do sábado) → carrossel, story do dia e card do jogão em `out/`.
- Vídeos: `python3 render.py v1_5minutos v2_gratis ...` → `out/*.mp4`. Para conferir antes: `python3 render.py --frames v1_5minutos 1.0 5.0 9.0`.
- Cada vídeo é um HTML com quadros-chave (`pop`, `add`, `phone`, `tapS`, `boxS`, `endCard`). `measure.py` dá as posições dos elementos do site para o toque e a moldura.

## Regras
- Sem escudos de clubes, logos de emissoras ou trechos de transmissão (anúncio reprovado / direitos).
- Nunca "assista aqui": o site não transmite; usar "veja onde passa".
- Emojis coloridos não aparecem no Chrome sem tela: usar os ícones de `ICO` em `common.js`.
- Vídeos saem sem música: o áudio é escolhido no app (áudio em alta).
