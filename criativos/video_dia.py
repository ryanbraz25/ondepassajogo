"""Gera o HTML do Reels "jogos de hoje" (cortes rápidos, um jogo por vez) a partir da agenda. Uso:
python3 video_dia.py <jogos.json> AAAA-MM-DD  ->  /tmp/vid/v_dia.html  (depois: python3 render.py v_dia)"""
import json, sys
sys.argv = [sys.argv[0], sys.argv[1], sys.argv[2], "dia"]
import importlib.util
spec = importlib.util.spec_from_file_location("posts", "/tmp/vid/posts.py")
P = importlib.util.module_from_spec(spec)
P.__name__ = "posts_mod"  # não roda o main()
src = open("/tmp/vid/posts.py").read().replace("asyncio.run(main())", "")
exec(compile(src, "posts.py", "exec"), P.__dict__)
from datetime import datetime

dia = sys.argv[2]
d = datetime.fromisoformat(dia).date()
js = P.jogos_do_dia(dia, 7)
hoje = d == datetime.now(P.BRT).date()
quando = "hoje" if hoje else P.SEM[d.weekday()].lower()
from collections import Counter
k = Counter(x["comp"] for x in js).most_common(1)[0][0]
mesmo = all(x["comp"] == k for x in js)
nm = (P.D["competicoes"][k].get("curto") or P.D["competicoes"][k]["nome"]) if mesmo else "futebol"
n = len(js)
corte = 1.15
t0 = 2.4
cards = []
for i, j in enumerate(js):
    t = datetime.fromisoformat(j["inicio"]).astimezone(P.BRT)
    cs = [P.canal(j, c) for c in j.get("canais", [])]
    pills = "".join(
        f"<span style='display:inline-block;margin:8px;border-radius:999px;padding:12px 30px;font:800 48px Barlow;"
        f"background:{'#ffd400' if g else '#fff'};color:#0a3d20'>{P.e(nm_)}{' · GRÁTIS' if g else ''}</span>" for nm_, g in sorted(cs, key=lambda x: not x[1])) \
        or "<span style='font:700 44px Barlow;opacity:.85'>canal a confirmar</span>"
    comp = P.D["competicoes"][j["comp"]].get("curto") or P.D["competicoes"][j["comp"]]["nome"]
    a = t0 + i * corte
    cards.append(f"""add(`<div style="text-align:center;padding:0 60px">
 <div style="font:900 italic 200px/1 'Barlow Condensed';color:#ffd400">{P.hora(t)}</div>
 <div style="font:900 italic 112px/.95 'Barlow Condensed';text-transform:uppercase;margin:20px 0 14px">{P.e(j['casa'])}<br><span style="color:#ffd400;font-size:80px">x</span><br>{P.e(j['fora'])}</div>
 <div style="font:700 40px Barlow;opacity:.85;margin-bottom:26px">{P.e(comp)}{(' · ' + P.e(P.estadio(j))) if P.estadio(j) else ''}</div>
 <div>{pills}</div></div>`,'top:470px',[[{a:.2f},{{o:0,x:260}}],[{a+.18:.2f},{{o:1,x:0}},'out'],[{a+corte-.12:.2f},{{o:1,x:0}}],[{a+corte:.2f},{{o:0,x:-260}},'inout']]);
add(`<div class="center"><div style="font:800 40px Barlow;background:rgba(0,0,0,.25);border-radius:999px;padding:10px 28px">{i+1}/{n}</div></div>`,'top:300px',[[{a:.2f},{{o:0}}],[{a+.1:.2f},{{o:1}}],[{a+corte-.1:.2f},{{o:1}}],[{a+corte:.2f},{{o:0}}]]);""")
fim = t0 + n * corte
gr = sum(1 for j in js if any(P.canal(j, c)[1] for c in j.get("canais", [])))
html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><link rel="stylesheet" href="base.css"></head><body><div id="stage"></div>
<script src="engine.js"></script><script src="common.js"></script><script>
const DUR={fim + 2.9:.2f};
pop('<div class="cap">{n} jogos do<br><em>{P.e(nm)}</em> {quando}</div>','top:560px',0.1,1.35,{{s0:.7}});
pop('<div class="cap m">e você sabe<br><em>onde passa</em><br>cada um?</div>','top:600px',1.4,2.4,{{s0:.8}});
{''.join(cards)}
pop('<div class="cap m">Todos com o<br><em>link oficial</em><br>no site</div>{('<div class="center" style="margin-top:34px"><span class="tag">' + str(gr) + (' jogos com opção grátis' if gr > 1 else ' jogo com opção grátis') + '</span></div>') if gr else ''}','top:620px',{fim + .05:.2f},{fim + 1.35:.2f},{{s0:.8}});
endCard({fim + 1.4:.2f},'Salva e manda no grupo da resenha');
render(0);
</script></body></html>"""
open("/tmp/vid/v_dia.html", "w").write(html)
print("ok", n, "jogos", f"{fim + 2.9:.1f}s")
