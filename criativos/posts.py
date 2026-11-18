"""Gera as artes estáticas (carrossel da rodada, story de jogos do dia, card do jogão) a partir da agenda do site."""
import asyncio, json, re, sys, unicodedata
from datetime import datetime, timedelta, timezone
from html import escape as e
from playwright.async_api import async_playwright

BRT = timezone(timedelta(hours=-3))
D = json.load(open(sys.argv[1] if len(sys.argv) > 1 else "/tmp/t/dados/jogos.json"))
SAB = sys.argv[2] if len(sys.argv) > 2 else "2026-11-21"
MODO = sys.argv[3] if len(sys.argv) > 3 else "rodada"  # "rodada" = carrossel do fim de semana; "dia" = story, jogão e rodada do dia
OUT = "/tmp/vid/out"
POP = D["popularidade"]["times"]
sys.path.insert(0, "/home/claude/ondepassajogo/robo")
try:
    import atualizar as _a
    _CFG = json.load(open("/home/claude/ondepassajogo/robo/config.json"))
    for _j in D["jogos"]:
        if _j.get("local"):
            _j["local"] = _a.acentua(_CFG, _j["local"])
except Exception:
    pass


def estadio(j):
    l = (j.get("local") or "").split(",")[0].strip()
    return re.sub(r"^(Estádio|Estadio|Arena)\s+(do|da|de)\s+", "", l) if l.startswith(("Estádio d", "Estadio d")) else l
SEM = ["SEGUNDA", "TERÇA", "QUARTA", "QUINTA", "SEXTA", "SÁBADO", "DOMINGO"]


def n2(s):
    s = unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode().lower()
    return " ".join(re.sub(r"[^a-z0-9]+", " ", s).split())


def pop(j):
    return (POP.get(n2(j["casa"]), 5) + POP.get(n2(j["fora"]), 5)
            + (15 if D["competicoes"][j["comp"]].get("principal") else 0))


def canal(j, c):
    info = D["canais"].get(c, {"nome": c, "tipo": ""})
    link = (j.get("links") or {}).get(c, "")
    gr = info.get("tipo") in ("TV aberta", "YouTube") or "youtube" in link
    return info["nome"], gr


def hora(t):
    return f"{t.hour}h{t.minute:02d}" if t.minute else f"{t.hour}h"


def jogos_do_dia(dia, n):
    js = [j for j in D["jogos"] if j["inicio"][:10] == dia and j["comp"] != "ligamx" and "A definir" not in (j["casa"], j["fora"])]
    com = [j for j in js if j.get("canais")]
    if len(com) >= min(n, 4):
        js = com
    js = sorted(js, key=lambda j: -pop(j))[:n]
    return sorted(js, key=lambda j: j["inicio"])


CSS = open("/tmp/vid/fonts.css").read() + """
*{box-sizing:border-box;margin:0}
body{width:W;height:H;overflow:hidden;font-family:Barlow,sans-serif;color:#fff;
 background:radial-gradient(120% 70% at 50% 30%,#0f8a46 0%,#0a6d35 45%,#06331b 100%)}
body::before{content:"";position:fixed;inset:0;background:repeating-linear-gradient(90deg,rgba(255,255,255,.035) 0 135px,transparent 135px 270px);z-index:-1}
.wrap{position:relative;height:100%;padding:70px 64px;display:flex;flex-direction:column}
.top{display:flex;align-items:center;gap:14px;font:900 italic 46px 'Barlow Condensed';letter-spacing:-.01em}
.top span{transform:skewX(-6deg)} .top em{font-style:inherit;color:#ffd400}
.foot{margin-top:auto;display:flex;justify-content:space-between;align-items:center;font:700 34px Barlow}
.url{background:#ffd400;color:#0a3d20;border-radius:999px;padding:12px 30px;font:800 36px Barlow}
.big{font:900 italic 128px/.92 'Barlow Condensed';text-transform:uppercase;letter-spacing:-.01em}
.big em{font-style:inherit;color:#ffd400}
.dia{font:900 italic 92px/1 'Barlow Condensed';margin:34px 0 22px} .dia small{font-size:56px;color:#ffd400;margin-left:14px}
.list{display:flex;flex-direction:column;gap:14px}
.j{display:grid;grid-template-columns:150px 1fr;gap:4px 18px;background:#fff;color:#0d1a12;border-radius:24px;padding:18px 24px}
.j .h{grid-row:1/3;font:900 52px/1 'Barlow Condensed';align-self:center}
.j .t{font:800 36px/1.1 Barlow}
.j .c{display:flex;flex-wrap:wrap;gap:8px;align-items:center;font:600 24px Barlow;color:#5b6b61}
.p{border-radius:999px;padding:3px 14px;font:700 24px Barlow;background:#eef3f0;color:#0d1a12}
.p.g{background:#0a6d35;color:#fff}
.aconf{font-size:22px;color:#a06a00}
.list.lg{gap:20px}.list.lg .j{padding:26px 30px;grid-template-columns:170px 1fr}.list.lg .j .h{font-size:62px}.list.lg .j .t{font-size:44px}.list.lg .p{font-size:28px}.list.lg .j .c{font-size:28px}
.tag{display:inline-block;background:#fff;color:#0a6d35;border-radius:999px;padding:14px 32px;font:800 40px Barlow}
"""


def page(w, h, body):
    return f"<!DOCTYPE html><html><head><meta charset='utf-8'><style>{CSS.replace('W', str(w) + 'px').replace('H', str(h) + 'px')}</style></head><body><div class='wrap'>{body}</div></body></html>"


TOP = "<div class='top'><img src='file:///tmp/vid/logo.svg' width='40' height='53'><span>ONDE PASSA <em>JOGO</em></span></div>"


def linha(j):
    t = datetime.fromisoformat(j["inicio"]).astimezone(BRT)
    pills = "".join(f"<span class='p{' g' if g else ''}'>{e(n)}{' · grátis' if g else ''}</span>" for n, g in (canal(j, c) for c in j.get("canais", []))) or "<span class='p'>a confirmar</span>"
    conf = "<span class='aconf'>a confirmar</span>" if j.get("status") == "a_confirmar" and j.get("canais") else ""
    comp = D["competicoes"][j["comp"]].get("curto") or D["competicoes"][j["comp"]]["nome"]
    return (f"<div class='j'><div class='h'>{hora(t)}</div><div class='t'>{e(j['casa'])} x {e(j['fora'])}</div>"
            f"<div class='c'>{e(comp)} · {pills}{conf}</div></div>")


def slides():
    sab = datetime.fromisoformat(SAB).date()
    dom = sab + timedelta(days=1)
    out = []
    out.append(("carrossel_1_capa", 1080, 1350, TOP + f"""
<div style='margin-top:150px' class='big'>Onde passa<br>cada jogo do<br><em>fim de semana</em></div>
<div style='font:700 52px Barlow;margin-top:40px'>Sábado {sab:%d/%m} e domingo {dom:%d/%m} · horário de Brasília</div>
<div style='margin-top:60px'><span class='tag'>Arrasta para o lado →</span></div>
<div class='foot'><span>Salva para consultar na hora do jogo</span></div>"""))
    for i, d in enumerate((sab, dom)):
        js = jogos_do_dia(d.isoformat(), 7)
        out.append((f"carrossel_{i + 2}_{SEM[d.weekday()].lower()}", 1080, 1350, TOP +
                    f"<div class='dia'>{SEM[d.weekday()]}<small>{d:%d/%m}</small></div><div class='list'>{''.join(linha(j) for j in js)}</div>"
                    "<div class='foot'><span>Links oficiais no site</span><span class='url'>ondepassajogo.com.br</span></div>"))
    out.append(("carrossel_4_final", 1080, 1350, TOP + """
<div style='margin-top:170px' class='big'>Todos os jogos,<br>com o <em>link oficial</em><br>de cada canal</div>
<div style='font:600 46px/1.35 Barlow;margin-top:44px'>Filtro de transmissão grátis, placar ao vivo e aviso no celular quando seu time joga.</div>
<div style='margin-top:56px'><span class='url' style='font-size:56px;padding:18px 44px'>ondepassajogo.com.br</span></div>
<div class='foot'><span>Manda no grupo da resenha</span></div>"""))
    # story: jogos do dia (sábado)
    js = jogos_do_dia(sab.isoformat(), 8)
    out.append(("story_jogos_do_dia", 1080, 1920, TOP + f"""
<div style='margin-top:150px' class='big' >Jogos de <em>hoje</em></div>
<div style='font:700 48px Barlow;margin:12px 0 30px'>{SEM[sab.weekday()].capitalize()}, {sab:%d/%m} · onde assistir</div>
<div class='list'>{''.join(linha(j) for j in js)}</div>
<div style='margin-top:40px;text-align:center'><span class='url' style='font-size:50px'>Link na bio · ondepassajogo.com.br</span></div>
<div style='height:260px'></div>"""))
    # card do jogão
    j = sorted([x for x in D["jogos"] if x["inicio"][:10] == sab.isoformat()], key=lambda x: -pop(x))[0]
    t = datetime.fromisoformat(j["inicio"]).astimezone(BRT)
    comp = D["competicoes"][j["comp"]]["nome"]
    btns = "".join(f"<div style='display:flex;justify-content:space-between;align-items:center;background:{'#ffd400' if g else '#fff'};color:#0a3d20;border-radius:22px;padding:22px 30px;font:800 46px Barlow'><span>{e(n)}</span><span style='font-size:34px'>{'GRÁTIS' if g else ''}</span></div>"
                   for n, g in sorted((canal(j, c) for c in j.get("canais", [])), key=lambda x: not x[1]))
    local = (j.get("local") or "").split(",")[0]
    out.append(("jogao_do_dia", 1080, 1350, TOP + f"""
<div style='margin-top:60px;font:800 40px Barlow;color:#ffd400'>JOGÃO DE {SEM[t.weekday()]} · {e(comp.upper())}</div>
<div class='big' style='font-size:150px;margin-top:10px'>{e(j['casa'])}<br><span style='color:#ffd400'>x</span> {e(j['fora'])}</div>
<div style='font:800 64px Barlow;margin-top:22px'>{hora(t)} · {t:%d/%m}{(' · ' + e(local)) if local else ''}</div>
<div style='font:900 italic 64px "Barlow Condensed";margin:40px 0 18px'>ONDE ASSISTIR</div>
<div style='display:flex;flex-direction:column;gap:14px'>{btns}</div>
<div class='foot'><span>Links oficiais no site</span><span class='url'>ondepassajogo.com.br</span></div>"""))
    return out


def slides_dia(dia):
    d = datetime.fromisoformat(dia).date()
    out = []
    js = jogos_do_dia(dia, 8)
    nome_dia = "hoje" if d == datetime.now(BRT).date() else SEM[d.weekday()].lower()
    out.append((f"story_jogos_do_dia_{d:%d-%m}", 1080, 1920, TOP + f"""
<div style='margin-top:150px' class='big'>Jogos de <em>{nome_dia}</em></div>
<div style='font:700 48px Barlow;margin:12px 0 30px'>{SEM[d.weekday()].capitalize()}, {d:%d/%m} · onde assistir</div>
<div class='list{" lg" if len(js) <= 6 else ""}'>{''.join(linha(j) for j in js)}</div>
<div style='margin-top:44px;text-align:center'><span class='url' style='font-size:50px'>Link na bio · ondepassajogo.com.br</span></div>
<div style='height:260px'></div>"""))
    j = sorted(js, key=lambda x: -pop(x))[0]
    t = datetime.fromisoformat(j["inicio"]).astimezone(BRT)
    comp = D["competicoes"][j["comp"]]["nome"]
    btns = "".join(f"<div style='display:flex;justify-content:space-between;align-items:center;background:{'#ffd400' if g else '#fff'};color:#0a3d20;border-radius:22px;padding:22px 30px;font:800 46px Barlow'><span>{e(n)}</span><span style='font-size:34px'>{'GRÁTIS' if g else ''}</span></div>"
                   for n, g in sorted((canal(j, c) for c in j.get("canais", [])), key=lambda x: not x[1]))
    local = estadio(j)
    rod = (" · " + j["rodada"].upper()) if j.get("rodada") else ""
    out.append((f"jogao_do_dia_{d:%d-%m}", 1080, 1350, TOP + f"""
<div style='margin-top:60px;font:800 40px Barlow;color:#ffd400'>JOGÃO DE {'HOJE' if nome_dia == 'hoje' else SEM[t.weekday()]} · {e(comp.upper())}{e(rod)}</div>
<div class='big' style='font-size:150px;margin-top:10px'>{e(j['casa'])}<br><span style='color:#ffd400'>x</span> {e(j['fora'])}</div>
<div style='font:800 64px Barlow;margin-top:22px'>{hora(t)} · {t:%d/%m}{(' · ' + e(local)) if local else ''}</div>
<div style='font:900 italic 64px "Barlow Condensed";margin:40px 0 18px'>ONDE ASSISTIR</div>
<div style='display:flex;flex-direction:column;gap:14px'>{btns}</div>
<div class='foot'><span>Links oficiais no site</span><span class='url'>ondepassajogo.com.br</span></div>"""))
    # rodada do dia no feed: campeonato com mais jogos entre os escolhidos
    from collections import Counter
    k = Counter(x["comp"] for x in js).most_common(1)[0][0]
    rj = [x for x in js if x["comp"] == k][:7]
    rod = next((x.get("rodada") for x in rj if x.get("rodada")), "")
    nm = D["competicoes"][k].get("curto") or D["competicoes"][k]["nome"]
    gr = [x for x in rj if any(canal(x, c)[1] for c in x.get("canais", []))]
    out.append((f"rodada_do_dia_{d:%d-%m}", 1080, 1350, TOP + f"""
<div class='dia' style='margin-bottom:6px'>{e(nm.upper())} {nome_dia.upper()}<small>{d:%d/%m}</small></div>
<div style='font:700 40px Barlow;margin-bottom:22px'>{e(rod + ' · ') if rod else ''}{len(rj)} jogos{' · ' + str(len(gr)) + ' com opção grátis' if gr else ''}</div>
<div class='list'>{''.join(linha(x) for x in rj)}</div>
<div class='foot'><span>Links oficiais no site</span><span class='url'>ondepassajogo.com.br</span></div>"""))
    return out, js, j


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--allow-file-access-from-files"])
        lista = slides_dia(SAB)[0] if MODO == "dia" else slides()
        for nome, w, h, body in lista:
            pg = await b.new_page(viewport={"width": w, "height": h})
            open(f"/tmp/vid/_p.html", "w").write(page(w, h, body))
            await pg.goto("file:///tmp/vid/_p.html")
            await pg.evaluate("document.fonts.ready"); await pg.wait_for_timeout(400)
            await pg.screenshot(path=f"{OUT}/{nome}.png")
            await pg.close()
            print(nome)
        await b.close()

asyncio.run(main())
