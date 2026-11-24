"""Páginas para o Google: uma por jogo, time e campeonato, mais "jogos de hoje" e "de amanhã".

Cada página tem o título do jeito que as pessoas pesquisam ("Flamengo x Palmeiras: onde assistir..."),
o texto com horário e canais, dados estruturados (schema.org SportsEvent) e links entre si.
Também gera o sitemap.xml e avisa o Bing pelo IndexNow sobre as páginas que mudaram.
"""
import hashlib
import json
import re
import shutil
import unicodedata
import urllib.request
from datetime import datetime, timedelta, timezone
from html import escape
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SITE = RAIZ / "site"
URL = "https://ondepassajogo.com.br"
BRT = timezone(timedelta(hours=-3))
ESTADO = RAIZ / "dados" / "paginas.json"
INDEXNOW_KEY = "6f2c0d8b4a9e47c1b3d5e8f0a7c6b2d9"
GUARDAR_DIAS = 60
GRATIS = {"TV aberta", "YouTube"}
SEMANA = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo"]
MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro",
         "outubro", "novembro", "dezembro"]
NOME_LONGO = {"Brasil": "Seleção Brasileira"}


def log(*a):
    print("[páginas]", *a, flush=True)


def slug(s):
    s = unicodedata.normalize("NFD", str(s)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-") or "x"


def slug_jogo(j):
    d = datetime.fromisoformat(j["inicio"]).astimezone(BRT)
    return f"{slug(j['casa'])}-x-{slug(j['fora'])}-{d:%d-%m-%Y}"


def caminho_jogo(j):
    return f"/jogo/{slug_jogo(j)}/"


def hora(d):
    return f"{d.hour}h{d.minute:02d}" if d.minute else f"{d.hour}h"


def data_longa(d):
    return f"{SEMANA[d.weekday()]}, {d.day} de {MESES[d.month - 1]} de {d.year}"


def data_curta(d):
    return f"{SEMANA[d.weekday()].split('-')[0]} {d:%d/%m}"


def nl(t):
    return NOME_LONGO.get(t, t)


def e(s):
    return escape(str(s), quote=True)


MASC = ("Brasileirão", "Paulistão", "Campeonato", "Carioca", "Mineiro", "Gauchão", "Mundial", "Championship", "Argentino", "Italiano", "Francês", "Alemão", "Inglês", "Espanhol", "Português", "Turco", "Holandês", "Saudita", "Nordestão")


def art(nome, m, f):
    """Artigo certo para o campeonato: "do Brasileirão", "da Liga da Turquia"."""
    return m if str(nome).startswith(MASC) else f


def do_(nome):
    return art(nome, "do", "da") + " " + nome


def no_(nome):
    return art(nome, "no", "na") + " " + nome


class Ctx:
    def __init__(self, dados, head_extra, favicon, pin, extras=None):
        ex = extras or {}
        self.tabs = ex.get("tabelas") or {}
        self.hist = ex.get("historico") or {"jogos": {}}
        self.escs = ex.get("escalacoes") or {}
        self.rods = ex.get("rodadas") or {}
        self.d = dados
        self.head_extra = head_extra
        self.favicon = favicon
        self.pin = pin
        self.agora = datetime.now(BRT)
        self.hoje = self.agora.date()
        self.comps = dados["competicoes"]
        self.canais = dados["canais"]
        self.esc = dados.get("escudos", {})
        self.jogos = []
        for j in dados["jogos"]:
            t = datetime.fromisoformat(j["inicio"]).astimezone(BRT)
            self.jogos.append({**j, "_t": t, "_pg": caminho_jogo(j)})
        self.jogos.sort(key=lambda j: j["_t"])
        pop = dados.get("popularidade", {})
        self.pop_times = pop.get("times", {})
        self.pop_padrao = pop.get("padrao", 10)

    def pop(self, t):
        return self.pop_times.get(" ".join(slug(t).split("-")), self.pop_padrao)

    def comp_nome(self, k):
        return (self.comps.get(k) or {}).get("nome", k)

    def canal_info(self, j, c):
        info = self.canais.get(c) or {"nome": c, "tipo": "", "url": ""}
        link = (j.get("links") or {}).get(c) or info.get("url", "")
        yt = "youtube.com" in link or "youtu.be" in link
        gratis = info.get("tipo") in GRATIS or yt
        tipo = "Grátis no YouTube" if yt and info.get("tipo") != "YouTube" else info.get("tipo", "")
        return info.get("nome", c), tipo, link, gratis

    def tem_gratis(self, j):
        return any(self.canal_info(j, c)[3] for c in j.get("canais", []))


# ---------------------------------------------------------------- moldura comum
def pagina(cx, caminho, titulo, descricao, corpo, jsonld=None, migalhas=None, noindex=False, largo=False):
    url = URL + caminho
    ld = ""
    blocos = list(jsonld or [])
    if migalhas:
        blocos.append({"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": i + 1, "name": n, "item": URL + p} for i, (n, p) in enumerate(migalhas)]})
    for b in blocos:
        ld += '<script type="application/ld+json">' + json.dumps(b, ensure_ascii=False).replace("</", "<\\/") + "</script>\n"
    mig = ""
    if migalhas:
        partes = [f'<a href="{e(p)}">{e(n)}</a>' for n, p in migalhas[:-1]] + [f"<span>{e(migalhas[-1][0])}</span>"]
        mig = '<nav class="mig" aria-label="Você está em">' + " › ".join(partes) + "</nav>"
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(titulo)}</title>
<meta name="description" content="{e(descricao)}">
<link rel="canonical" href="{e(url)}">
{'<meta name="robots" content="noindex">' if noindex else ''}
<meta property="og:type" content="website">
<meta property="og:site_name" content="Onde Passa Jogo">
<meta property="og:title" content="{e(titulo)}">
<meta property="og:description" content="{e(descricao)}">
<meta property="og:url" content="{e(url)}">
<meta property="og:image" content="{URL}/icone-512.png">
<meta property="og:locale" content="pt_BR">
<meta name="theme-color" content="#0a6d35">
<link rel="manifest" href="/manifest.webmanifest">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
{cx.favicon}
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:ital,wght@0,700;0,800;1,900&family=Barlow:wght@400;600;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/p.css?v=5">
<link rel="stylesheet" href="/menu.css?v=2">
<link rel="stylesheet" href="/rodadas.css?v=2">
<link rel="stylesheet" href="/aovivo.css?v=1">
<script src="/p.js?v=5" defer></script>
<script src="/rodadas.js?v=2" defer></script>
<script src="/aovivo.js?v=1" defer></script>
<script src="/menu.js?v=2" defer></script>
{cx.head_extra}
{ld}</head>
<body{' class="largo"' if largo else ''}>
<header class="topo"><div class="wrap"><div class="hesq">{botao_menu(rotulo=False)}<a class="marca" href="/" aria-label="Onde Passa Jogo: página inicial">{cx.pin}<span>ONDE PASSA <b>JOGO</b></span></a></div><div class="hdir"><a class="todos" href="/">Ver agenda<span class="dk"> completa</span></a></div></div></header>
{menu_html(cx.comps, cx.tabs)}
<main class="wrap">
{mig}
{corpo}
</main>
<footer class="wrap rodape">
<p><a href="/jogos-de-hoje/">Jogos de hoje</a> · <a href="/jogos-de-amanha/">Jogos de amanhã</a> · <a href="/">Agenda completa</a> · <a href="https://www.instagram.com/ondepassajogo.com.br/" rel="noopener">Instagram</a> · <a href="/privacidade.html">Privacidade</a></p>
<p>Horário de Brasília. Os links levam às páginas oficiais de cada emissora. Horários e canais podem mudar; "a confirmar" indica informação ainda não anunciada oficialmente.</p>
</footer>
</body>
</html>
"""


def escudo(cx, t, tam=40):
    u = cx.esc.get(t, "")
    if u and "thesportsdb" in u:
        u += "/tiny"
    if u:
        return f'<img class="cr" src="{e(u)}" alt="" width="{tam}" height="{tam}" loading="lazy">'
    ini = "".join(p[0] for p in t.split()[:2]).upper() if t != "A definir" else "?"
    return f'<span class="cr ini" aria-hidden="true">{e(ini)}</span>'


def lista_canais(cx, j):
    if not j.get("canais"):
        return '<p class="semcanal">Os canais ainda não foram anunciados. A gente atualiza esta página assim que sair a confirmação.</p>'
    itens = []
    for c in j["canais"]:
        nome, tipo, link, gratis = cx.canal_info(j, c)
        selo = '<span class="gr">Grátis</span>' if gratis else ""
        tag = f'<a class="canal" href="{e(link)}" target="_blank" rel="noopener">' if link else '<span class="canal">'
        fim = "</a>" if link else "</span>"
        itens.append(f'{tag}<b>{e(nome)}</b><small>{e(tipo)}</small>{selo}{fim}')
    aviso = '<p class="aconf">Transmissão a confirmar: ainda não saiu anúncio oficial.</p>' if j.get("status") == "a_confirmar" else ""
    return '<div class="canais">' + "".join(itens) + "</div>" + aviso


def linha_jogo(cx, j, mostrar_data=True, mostrar_comp=True):
    t = j["_t"]
    quando = (data_curta(t) + " · " if mostrar_data else "") + hora(t)
    placar = j.get("placar")
    meio = f'<b class="pl">{placar["casa"]} x {placar["fora"]}</b>' if placar else '<span class="x">x</span>'
    can = ", ".join(cx.canal_info(j, c)[0] for c in j.get("canais", [])) or "canais a confirmar"
    sub = (e(cx.comp_nome(j["comp"])) + " · " if mostrar_comp else "") + e(can)
    return (f'<li><a class="lj" href="{e(j["_pg"])}"><span class="lh">{e(quando)}</span>'
            f'<span class="lt">{escudo(cx, j["casa"], 22)}{e(j["casa"])} {meio} {e(j["fora"])}{escudo(cx, j["fora"], 22)}</span>'
            f'<span class="ls">{sub}</span></a></li>')


def lista(cx, jogos, **kw):
    return '<ul class="lista">' + "".join(linha_jogo(cx, j, **kw) for j in jogos) + "</ul>"


def por_dia(cx, jogos, **kw):
    out, dia = [], None
    grupo = []
    for j in jogos:
        if j["_t"].date() != dia:
            if grupo:
                out.append(f"<h3>{e(data_longa(grupo[0]['_t']).capitalize())}</h3>" + lista(cx, grupo, mostrar_data=False, **kw))
            dia, grupo = j["_t"].date(), []
        grupo.append(j)
    if grupo:
        out.append(f"<h3>{e(data_longa(grupo[0]['_t']).capitalize())}</h3>" + lista(cx, grupo, mostrar_data=False, **kw))
    return "".join(out)


# ---------------------------------------------------------------- tabela, forma, resultados, escalações
import extras as X  # noqa: E402

COLS = '<tr><th class="c-pos">#</th><th class="c-time">Time</th><th>P</th><th>J</th><th class="c-x">V</th><th class="c-x">E</th><th class="c-x">D</th><th class="c-x">GP</th><th class="c-x">GC</th><th>SG</th><th class="c-f">Últimos 5</th></tr>'


def forma(cx, time_, n=5, antes=None):
    js = X.ultimos(cx.hist, time_, n, antes)
    if not js:
        return ""
    bolas = []
    for x in reversed(js):
        r = X.resultado_para(time_, x)
        adv = x["fora"] if x["casa"] == time_ else x["casa"]
        pl = f'{x["placar"]["casa"]} x {x["placar"]["fora"]}'
        tit = f'{"Vitória" if r == "V" else "Empate" if r == "E" else "Derrota"}: {x["casa"]} {pl} {x["fora"]} ({datetime.fromisoformat(x["inicio"]).astimezone(BRT):%d/%m})'
        bolas.append(f'<span class="fm f{r}" title="{e(tit)}" aria-label="{e(tit)}">{r}</span>')
    return '<span class="forma">' + "".join(bolas) + "</span>"


def esc_tab(cx, l):
    u = cx.esc.get(l["time"]) or l.get("esc", "")
    if u and "thesportsdb" in u:
        u += "/tiny"
    return f'<img class="cr" src="{e(u)}" alt="" width="20" height="20" loading="lazy">' if u else '<span class="cr ini"></span>'


def texto_sobre(cor):
    """Cor do número em cima da faixa: branco nas cores escuras, quase preto nas claras."""
    h = str(cor).lstrip("#")
    if len(h) != 6:
        return "#fff"
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    lum = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return "#0b1a10" if 0.2126 * lum(r) + 0.7152 * lum(g) + 0.0722 * lum(b) > 0.33 else "#fff"


# ---------------------------------------------------------------- menu (botão de três barrinhas)
ICO_MENU = '<svg width="20" height="20" viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7h16M4 12h16M4 17h16" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/></svg>'
_ICO = {
    "hoje": '<path d="M5 6h14v13H5zM5 10h14M9 3.5v4M15 3.5v4" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>',
    "amanha": '<path d="M5 6h14v13H5zM5 10h14M9 3.5v4M15 3.5v4M10 14.5h4m-1.5-1.5 1.5 1.5-1.5 1.5" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>',
    "agenda": '<path d="M5 6h14M5 12h14M5 18h9" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/>',
    "seg": '<path d="m12 3.6 2.6 5.3 5.8.8-4.2 4.1 1 5.8L12 16.9l-5.2 2.7 1-5.8-4.2-4.1 5.8-.8Z" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/>',
    "tab": '<path d="M4 5h16v14H4zM4 10h16M4 15h16M9 5v14" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/>',
    "aviso": '<path d="M6 17V11a6 6 0 0 1 12 0v6l1.6 2H4.4Z" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/><path d="M10 21.5h4" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>',
    "ig": '<rect x="3" y="3" width="18" height="18" rx="5" fill="none" stroke="currentColor" stroke-width="2"/><circle cx="12" cy="12" r="4.2" fill="none" stroke="currentColor" stroke-width="2"/><circle cx="17.4" cy="6.6" r="1.3" fill="currentColor"/>',
}


def _ico(k):
    return f'<svg width="20" height="20" viewBox="0 0 24 24" aria-hidden="true">{_ICO[k]}</svg>'


def botao_menu(classe="mbtn", rotulo=True):
    return (f'<button class="{classe}" type="button" data-menu aria-haspopup="dialog" aria-controls="menu" aria-label="Abrir menu">'
            f'{ICO_MENU}{"<span>Menu</span>" if rotulo else ""}</button>')


def menu_html(comps, com_tabela):
    """A gaveta do menu. comps = config dos campeonatos (na ordem do site); com_tabela = os que têm tabela agora."""
    tabs = "".join(
        f'<a href="/campeonato/{slug(k)}/"><i style="background:{e(c.get("cor") or "#0a6d35")}"></i>{e(c.get("curto") or c.get("nome") or k)}</a>'
        for k, c in comps.items() if k in com_tabela)
    item = lambda href, ico, txt, extra="": f'<a href="{href}"{extra}>{_ico(ico)}<span>{txt}</span></a>'
    return (
        '<dialog class="menu" id="menu" aria-labelledby="menu-t">'
        '<div class="mn-hd"><b id="menu-t">Menu</b><button class="mn-x" type="button" data-menu-fechar aria-label="Fechar menu">'
        '<svg width="20" height="20" viewBox="0 0 24 24" aria-hidden="true"><path d="M6 6l12 12M18 6 6 18" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/></svg></button></div>'
        '<nav class="mn-bd" aria-label="Menu do site">'
        '<h3>Jogos</h3><div class="mn-ls">'
        + item("/jogos-de-hoje/", "hoje", "Jogos de hoje")
        + item("/jogos-de-amanha/", "amanha", "Jogos de amanhã")
        + item("/", "agenda", "Agenda completa (15 dias)")
        + item("/#seguindo", "seg", "Meus times e campeonatos", ' data-menu-seguindo')
        + '</div>'
        + (f'<h3>Tabelas</h3><div class="mn-tb">{tabs}</div>' if tabs else "")
        + item("/tabelas/", "tab", "Todas as tabelas", ' class="mn-all"')
        + '<h3>Mais</h3><div class="mn-ls">'
        + item("/#avisos", "aviso", "Avisos no celular", ' data-menu-avisos')
        + item("https://www.instagram.com/ondepassajogo.com.br/", "ig", "Siga no Instagram", ' target="_blank" rel="noopener"')
        + '</div></nav></dialog>')


def tabela_html(cx, k, destaque=(), recorte=None, com_forma=True):
    t = cx.tabs.get(k)
    if not t:
        return ""
    out = []
    zonas = {}
    for g in t["grupos"]:
        linhas = g["linhas"]
        if recorte:
            linhas = [l for l in linhas if recorte[0] <= l["pos"] <= recorte[1]]
            if not linhas:
                continue
        rows = []
        for l in linhas:
            if l.get("zona"):
                zonas[l["zona"]] = l.get("cor") or "#0a6d35"
            cor = f' style="--z:{e(l["cor"])};--zt:{texto_sobre(l["cor"])}"' if l.get("zona") and l.get("cor") else ""
            dst = " eu" if l["time"] in destaque else ""
            tid = f' data-tid="{e(l["tid"])}"' if l.get("tid") else ""
            rows.append(f'<tr class="{("zn" if l.get("zona") else "") + dst}"{cor}{tid}><td class="c-pos"><span title="{e(l.get("zona", ""))}">{l["pos"]}</span></td>'
                        f'<td class="c-time"><a href="/time/{slug(l["time"])}/">{esc_tab(cx, l)}<span>{e(l["time"])}</span></a></td>'
                        f'<td class="c-p" data-s="pts"><b>{l["pts"]}</b></td><td data-s="pj">{l["pj"]}</td><td class="c-x" data-s="v">{l["v"]}</td><td class="c-x" data-s="e">{l["e"]}</td><td class="c-x" data-s="d">{l["d"]}</td>'
                        f'<td class="c-x" data-s="gp">{l["gp"]}</td><td class="c-x" data-s="gc">{l["gc"]}</td><td data-s="sg">{"+" if l["sg"] > 0 else ""}{l["sg"]}</td>'
                        f'<td class="c-f">{forma(cx, l["time"]) if com_forma else ""}</td></tr>')
        cab = f'<h3 class="grp">{e(g["nome"])}</h3>' if g.get("nome") else ""
        # tabela inteira (não o recorte) ganha placar ao vivo: o aovivo.js reordena enquanto há jogo rolando
        viva = (f' data-lg="{e(g.get("lg") or t.get("liga", ""))}" data-em="{e(t.get("atualizado", ""))}"'
                if not recorte and (g.get("lg") or t.get("liga")) else "")
        out.append(f'{cab}<div class="tabwrap"><table class="tab"{viva}><thead>{COLS}</thead><tbody>{"".join(rows)}</tbody></table></div>')
    leg = ""
    if zonas and not recorte:
        leg = '<ul class="leg" aria-label="Legenda da tabela">' + "".join(
            f'<li><i style="background:{e(c)}"></i>{e(z)}</li>' for z, c in zonas.items()) + "</ul>"
        if t.get("obs"):
            leg += f'<p class="leg2">{e(t["obs"])}</p>'
    return "".join(out) + leg + '<p class="leg2">P = pontos · J = jogos · V/E/D = vitórias, empates e derrotas · SG = saldo de gols</p>'


def resultados_html(cx, xs, time_=None, mostrar_comp=True):
    if not xs:
        return ""
    itens = []
    for x in xs:
        t = datetime.fromisoformat(x["inicio"]).astimezone(BRT)
        r = f'<span class="fm f{X.resultado_para(time_, x)}">{X.resultado_para(time_, x)}</span>' if time_ else ""
        pen = f' <small>(pên. {x["pen"][0]} x {x["pen"][1]})</small>' if x.get("pen") else ""
        comp = f' · {e(cx.comp_nome(x["comp"]))}' if mostrar_comp else ""
        itens.append(f'<li><span class="rd">{t:%d/%m}</span>{r}<span class="rj"><span class="{"vc" if x["placar"]["casa"] > x["placar"]["fora"] else ""}">{e(x["casa"])}</span>'
                     f' <b>{x["placar"]["casa"]} x {x["placar"]["fora"]}</b> <span class="{"vc" if x["placar"]["fora"] > x["placar"]["casa"] else ""}">{e(x["fora"])}</span>{pen}</span>'
                     f'<span class="rc">{comp[3:] if comp else ""}</span></li>')
    return '<ul class="res">' + "".join(itens) + "</ul>"


GOL = {"G", "GK", "GOL"}
ATA = {"A", "AC", "AE", "AD", "CA", "PE", "PD", "F", "CF", "ST", "LW", "RW", "SS", "FW", "LF", "RF"}


def linha_pos(p):
    """Quão adiantado o jogador joga, pela sigla da ESPN (0 = goleiro ... 5 = centroavante). Igual ao prof() do p.js."""
    a = (p or "").upper()
    if a in GOL:
        return 0
    tabela = [(r"^(CD|CB|SW|D|DF)(-[LR])?$|^Z", 1), (r"^(RB|LB|LD|LE)$", 1.1), (r"^(RWB|LWB)$", 1.3), (r"^DM|^VOL", 2),
              (r"^CM|^MC", 3), (r"^(RM|LM|M|MD|ME)$", 3.2), (r"^AM|^MA|^MEI", 4), (r"^(RCF|LCF)$", 4.2), (r"^(RW|LW|RF|LF|PD|PE|AD|AE)$", 4.4),
              (r"^CF-|^SS$|^ATC|^ACI", 4.6), (r"^(F|CF|ST|FW|A|CA)$", 5)]
    for padrao, v in tabela:
        if re.search(padrao, a):
            return v
    return 3


def escalacoes_html(cx, j):
    """Texto das escalações (para o Google e para quem não tem JavaScript); o desenho do campo é feito pelo p.js."""
    es = cx.escs.get(j.get("eid", ""))
    ini = j["_t"]
    agora = cx.agora
    dados = ""
    if es:
        lados = []
        for lado, nome_ in (("casa", j["casa"]), ("fora", j["fora"])):
            x = es[lado]
            tit = ", ".join(f'{p["nome"]}' for p in sorted(x["titulares"], key=lambda p: (linha_pos(p["pos"]), p.get("fp", 99))))
            res = ", ".join(p["nome"] for p in x["reservas"])
            lados.append(f'<div class="esq"><h3>{e(nome_)}{(" · " + e(x["esquema"])) if x.get("esquema") else ""}</h3>'
                         f'<p><b>Titulares:</b> {e(tit)}.</p>' + (f'<p class="rs"><b>Reservas:</b> {e(res)}.</p>' if res else "") + "</div>")
        dados = ('<script type="application/json" class="escdata">' + json.dumps(es, ensure_ascii=False).replace("</", "<\\/") + "</script>")
        return (f'<section id="escalacoes" class="escal"><h2>Escalações</h2><div class="campo" data-pronto="1"></div>'
                f'<div class="esqs esqs-txt">{"".join(lados)}</div>{dados}</section>')
    if j.get("placar") or ini - agora > timedelta(days=3):
        return ""
    return (f'<section id="escalacoes" class="escal"><h2>Escalações</h2>'
            f'<div class="campo" data-lg="{e(j.get("lg", ""))}" data-eid="{e(j.get("eid", ""))}" data-ini="{ini.isoformat()}" '
            f'data-casa="{e(j["casa"])}" data-fora="{e(j["fora"])}"></div>'
            f'<p class="escnota">As escalações oficiais saem cerca de 1 hora antes do jogo e aparecem aqui sozinhas.</p></section>')


def como_chegam(cx, j):
    blocos = []
    for time_ in (j["casa"], j["fora"]):
        l, g = X.posicao(cx.tabs, j["comp"], time_)
        pos = (f'<p class="cpos"><b>{l["pos"]}º</b> {e(no_(cx.comp_nome(j["comp"])))}{(" (" + e(g["nome"]) + ")") if g and g.get("nome") else ""} · {l["pts"]} pts em {l["pj"]} jogos</p>' if l else "")
        ult = X.ultimos(cx.hist, time_, 5, j["inicio"])
        if not (pos or ult):
            continue
        blocos.append(f'<div class="cc"><h3><a href="/time/{slug(time_)}/">{escudo(cx, time_, 28)}{e(time_)}</a></h3>{pos}'
                      + (f'<p class="cfm">Últimos jogos: {forma(cx, time_, 5, j["inicio"])}</p>' + resultados_html(cx, ult, time_, mostrar_comp=False) if ult else "")
                      + "</div>")
    h2h = X.confrontos(cx.hist, j["casa"], j["fora"])
    h2h = [x for x in h2h if x["inicio"] < j["inicio"]]
    if not blocos and not h2h:
        return ""
    return ('<section class="chegam"><h2>Como chegam</h2><div class="ccs">' + "".join(blocos) + "</div>"
            + (f"<h3>Últimos confrontos</h3>{resultados_html(cx, h2h)}" if h2h else "") + "</section>")


# ---------------------------------------------------------------- página do jogo
BOLA = '<svg class="lb" width="16" height="16" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="10" fill="#fff" stroke="currentColor" stroke-width="1.5"/><path d="M12 7l3.8 2.8-1.45 4.45h-4.7L8.2 9.8Z" fill="currentColor"/><path d="M12 2v5M15.8 9.8l5.2-1.7M14.35 14.25l3.1 4.3M9.65 14.25l-3.1 4.3M8.2 9.8 3 8.1" fill="none" stroke="currentColor" stroke-width="1.4"/></svg>'
CARTAO = '<svg class="lb" width="15" height="15" viewBox="0 0 24 24" aria-hidden="true"><rect x="6" y="3" width="12" height="18" rx="2" fill="#e3242b"/></svg>'


def lances_html(j):
    """Gols e expulsões, como no placar do ge: os do mandante à esquerda, os do visitante à direita."""
    itens = []
    for x in j.get("lances") or []:
        extra = {"p": " (pênalti)", "c": " (contra)"}.get(x["k"], "")
        ico = CARTAO if x["k"] == "v" else BOLA
        rot = "expulso" if x["k"] == "v" else "gol"
        itens.append(f'<li class="l{x["l"]}{" lv" if x["k"] == "v" else ""}"><span class="lm">{e(x["m"])}</span>{ico}'
                     f'<span class="ln">{e(x["n"])}{e(extra)}</span><span class="so-leitor"> ({rot} do {e(j["casa"] if x["l"] == "c" else j["fora"])})</span></li>')
    return (f'<section class="lances" aria-label="Gols e expulsões"{"" if itens else " hidden"}>'
            f'<ul>{"".join(itens)}</ul></section>')


def pagina_jogo(cx, j):
    t = j["_t"]
    casa, fora = j["casa"], j["fora"]
    comp = cx.comp_nome(j["comp"])
    canais = [cx.canal_info(j, c) for c in j.get("canais", [])]
    nomes = [c[0] for c in canais]
    gratis = [c[0] for c in canais if c[3]]
    lista_nomes = (", ".join(nomes[:-1]) + " e " + nomes[-1]) if len(nomes) > 1 else (nomes[0] if nomes else "")
    placar = j.get("placar")
    encerrado = bool(placar)
    rodada = j.get("rodada") or ""
    local = j.get("local") or ""
    titulo = (f"{casa} x {fora}: onde assistir ao vivo, horário e canais ({t:%d/%m})" if not encerrado
              else f"{casa} {placar['casa']} x {placar['fora']} {fora}: resultado e onde passou ({t:%d/%m})")
    desc = (f"{casa} x {fora} pelo {comp}, {data_curta(t)} às {hora(t)} (Brasília). "
            + (f"Onde assistir: {lista_nomes}." if nomes else "Veja onde vai passar e o horário.")
            + (" Tem transmissão grátis." if gratis else ""))
    quando = f"{data_longa(t)}, às {hora(t)} (horário de Brasília)"
    texto = (f"{e(nl(casa))} e {e(nl(fora))} se enfrentam {e(quando)}"
             + (f", pela {e(rodada)}" if rodada else "") + f" {e(do_(comp))}"
             + (f", no {e(local)}" if local else "") + ". ")
    if nomes:
        texto += f"Transmissão: {e(lista_nomes)}."
        if gratis:
            lg = (", ".join(gratis[:-1]) + " e " + gratis[-1]) if len(gratis) > 1 else gratis[0]
            texto += f" De graça: {e(lg)}."
    else:
        texto += "Os canais ainda não foram anunciados; esta página é atualizada assim que sair a confirmação."
    nota = f'<p class="nota">{e(j["nota"])}</p>' if j.get("nota") else ""
    res = (f'<p class="res">Resultado: <b>{e(casa)} {placar["casa"]} x {placar["fora"]} {e(fora)}</b></p>' if encerrado else "")

    mesmos = [x for x in cx.jogos if x["comp"] == j["comp"] and x["_t"].date() == t.date() and x is not j]
    prox_c = [x for x in cx.jogos if casa in (x["casa"], x["fora"]) and x is not j and x["_t"] > t][:4]
    prox_f = [x for x in cx.jogos if fora in (x["casa"], x["fora"]) and x is not j and x["_t"] > t][:4]
    rel = ""
    if mesmos:
        rel += f"<h2>Outros jogos {e(do_(comp))} no mesmo dia</h2>" + lista(cx, mesmos, mostrar_data=False, mostrar_comp=False)
    for time, xs in ((casa, prox_c), (fora, prox_f)):
        if xs and time != "A definir":
            rel += f'<h2>Próximos jogos do {e(nl(time))}</h2>' + lista(cx, xs)

    faq = f"""<h3>Que horas é o jogo {e(casa)} x {e(fora)}?</h3>
<p>A partida começa às <b>{hora(t)}</b>, horário de Brasília, {e(data_longa(t))}.</p>
<h3>Onde vai passar {e(casa)} x {e(fora)}?</h3>
<p>{(f"{e(lista_nomes)}." if nomes else "Ainda não há canal confirmado.")}{(" Os botões acima levam direto para a transmissão oficial." if nomes else "")}</p>
<h3>Tem transmissão grátis?</h3>
<p>{(f"Sim: {e(' e '.join(gratis))}." if gratis else ("Por enquanto, não há transmissão gratuita anunciada." if nomes else "Ainda não sabemos; confira de novo mais perto do jogo."))}</p>
"""
    ld = {
        "@context": "https://schema.org", "@type": "SportsEvent",
        "name": f"{casa} x {fora}", "sport": "Futebol",
        "description": desc,
        "url": URL + j["_pg"],
        "startDate": t.isoformat(), "endDate": (t + timedelta(hours=2)).isoformat(),
        "eventStatus": "https://schema.org/EventScheduled",
        "eventAttendanceMode": "https://schema.org/OfflineEventAttendanceMode",
        "homeTeam": {"@type": "SportsTeam", "name": casa},
        "awayTeam": {"@type": "SportsTeam", "name": fora},
        "competitor": [{"@type": "SportsTeam", "name": casa}, {"@type": "SportsTeam", "name": fora}],
        "performer": [{"@type": "SportsTeam", "name": casa}, {"@type": "SportsTeam", "name": fora}],
        "organizer": {"@type": "Organization", "name": comp, "url": URL + f"/campeonato/{slug(j['comp'])}/"},
    }
    imgs = [cx.esc[x] for x in (casa, fora) if cx.esc.get(x)]
    if imgs:
        ld["image"] = imgs
    if local:
        partes = [p.strip() for p in local.rsplit(",", 1)]
        lugar = {"@type": "Place", "name": partes[0]}
        lugar["address"] = {"@type": "PostalAddress", "addressLocality": partes[-1] if len(partes) > 1 else partes[0]}
        ld["location"] = lugar
    if "adiad" in (j.get("nota") or "").lower():
        ld["eventStatus"] = "https://schema.org/EventPostponed"
    elif "cancel" in (j.get("nota") or "").lower():
        ld["eventStatus"] = "https://schema.org/EventCancelled"

    def rk(time_):
        l, _ = X.posicao(cx.tabs, j["comp"], time_)
        return f'<small class="rk">{l["pos"]}º · {l["pts"]} pts</small>' if l else ""

    # canais: grátis primeiro, cada um vira um botão para a transmissão oficial
    botoes = ""
    for nome, tipo, link, gr in sorted(canais, key=lambda c: not c[3]):
        sub = "Grátis" + (f" · {tipo}" if tipo and tipo != "Grátis no YouTube" else " · YouTube" if "YouTube" in tipo else "") if gr else tipo
        acao = ("Assistir grátis" if gr else "Assistir") if not encerrado else "Abrir"
        miolo = f'<span class="cn"><b>{e(nome)}</b><small>{e(sub)}</small></span><span class="ir">{acao} <span aria-hidden="true">›</span></span>'
        cls = "ver gratis" if gr else "ver"
        botoes += (f'<a class="{cls}" href="{e(link)}" target="_blank" rel="noopener">{miolo}</a>' if link
                   else f'<span class="{cls}">{miolo}</span>')
    if botoes:
        bloco_canais = (f'<div class="botoes">{botoes}</div>'
                        + ('<p class="aconf">Transmissão a confirmar: ainda não saiu anúncio oficial.</p>' if j.get("status") == "a_confirmar"
                           else '<p class="ofc">Os botões abrem a página oficial de cada emissora.</p>'))
    else:
        bloco_canais = ('<p class="semcanal">Os canais ainda não foram anunciados. Esta página é atualizada assim que sair a confirmação.</p>'
                        '<p class="cta2"><a href="/?utm_source=pagina_jogo&utm_medium=link#seguindo">Me avise quando sair</a></p>')
    estadio = local.rsplit(",", 1)[0].strip() if local else ""
    cidade = local.rsplit(",", 1)[1].strip() if local and "," in local else ""
    pino = '<svg width="13" height="13" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 2a7 7 0 0 0-7 7c0 5 7 13 7 13s7-8 7-13a7 7 0 0 0-7-7Zm0 9.5A2.5 2.5 0 1 1 12 6.5a2.5 2.5 0 0 1 0 5Z" fill="currentColor"/></svg>'
    status = "" if encerrado else (
        f'<p class="status" id="st" data-ini="{t.isoformat()}" hidden></p>'
        "<script>(function(){var e=document.getElementById('st'),i=Date.parse(e.dataset.ini),n=Date.now(),m=Math.round((i-n)/6e4);"
        "if(n>=i&&n<i+1.3e7){e.textContent='Ao vivo agora';e.className='status live';e.hidden=false}"
        "else if(m>0&&m<=360){e.textContent=m<60?'Começa em '+m+' min':'Começa em '+Math.floor(m/60)+'h'+(m%60?String(m%60).padStart(2,'0'):'');e.className='status breve';e.hidden=false}})()</script>")

    # placar ao vivo e gols (aovivo.js): só para jogo de hoje com o id da ESPN
    vivo_attrs = "".join(f' data-{a}="{e(j[a])}"' for a in ("eid", "lg", "ed") if j.get(a)) + f' data-ini="{t.isoformat()}"' if j.get("eid") and j.get("lg") else ""
    corpo = f"""<article class="jogo">
<p class="comp"><a href="/campeonato/{slug(j['comp'])}/">{e(comp)}</a>{(' · ' + e(rodada)) if rodada else ''}</p>
<h1>Onde assistir {e(casa)} x {e(fora)} ao vivo</h1>
<div class="placa"{vivo_attrs}>
 {f'<p class="nota">{e(j["nota"])}</p>' if j.get("nota") else ''}
 <a class="tm" href="/time/{slug(casa)}/">{escudo(cx, casa, 56)}<span>{e(casa)}</span>{rk(casa)}</a>
 <div class="hr">{(f'<b class="pl">{placar["casa"]} x {placar["fora"]}</b><small>Encerrado · {e(data_curta(t))}</small>' if encerrado else f'<b>{hora(t)}</b><small>{e(data_curta(t))}</small>')}
  {f'<span class="est" title="{e(local)}">{pino}{e(estadio)}</span>' if estadio else ''}
 </div>
 <a class="tm" href="/time/{slug(fora)}/">{escudo(cx, fora, 56)}<span>{e(fora)}</span>{rk(fora)}</a>
</div>
{status}
{lances_html(j)}
<h2>{'Onde passou' if encerrado else 'Onde assistir'}</h2>
{bloco_canais}
<p class="cta2"><a href="/?utm_source=pagina_jogo&utm_medium=link#seguindo">★ Seguir {e(nl(casa))} ou {e(nl(fora))} e receber aviso no dia do jogo</a></p>
{escalacoes_html(cx, j)}
{como_chegam(cx, j)}
{rel}
<section class="sobre">
<h2>Sobre o jogo</h2>
<p>{texto}</p>
{faq}
</section>
<p class="mais"><a href="/jogos-de-hoje/">Ver todos os jogos de hoje</a> · <a href="/campeonato/{slug(j['comp'])}/">Jogos {e(do_(comp))}</a></p>
</article>"""
    mig = [("Início", "/"), (comp, f"/campeonato/{slug(j['comp'])}/"), (f"{casa} x {fora}", j["_pg"])]
    return pagina(cx, j["_pg"], titulo, desc, corpo, [ld], mig)


# ---------------------------------------------------------------- time, campeonato, hoje
def pagina_time(cx, time, jogos):
    nome = nl(time)
    cam = f"/time/{slug(time)}/"
    futuros = [j for j in jogos if not j.get("placar")]
    ult = X.ultimos(cx.hist, time, 10)
    prox = futuros[0] if futuros else None
    # posição: campeonato em que o time aparece (os principais e de grupo único primeiro)
    pos_l = pos_k = pos_g = None
    for k in sorted(cx.tabs, key=lambda k: (not cx.comps.get(k, {}).get("principal"), len(cx.tabs[k]["grupos"]))):
        l, g = X.posicao(cx.tabs, k, time)
        if l:
            pos_l, pos_k, pos_g = l, k, g
            break
    if prox:
        can = ", ".join(cx.canal_info(prox, c)[0] for c in prox.get("canais", [])) or "canal a confirmar"
        intro = (f'<p class="dest">Próximo jogo: <a href="{e(prox["_pg"])}"><b>{e(prox["casa"])} x {e(prox["fora"])}</b></a>, '
                 f'{e(data_curta(prox["_t"]))} às {hora(prox["_t"])} · {e(can)}</p>')
        desc = (f"Próximo jogo do {nome}: {prox['casa']} x {prox['fora']}, {data_curta(prox['_t'])} às {hora(prox['_t'])}"
                f" ({can}). Últimos resultados, posição na tabela e onde assistir.")
    else:
        intro, desc = "<p>Sem jogos marcados nos próximos dias.</p>", f"Jogos do {nome}: últimos resultados, tabela e onde assistir ao vivo."
    resumo = ""
    if pos_l or ult:
        resumo = ('<div class="tresumo">'
                  + (f'<div><small>{e(cx.comp_nome(pos_k))}</small><b>{pos_l["pos"]}º lugar</b><span>{pos_l["pts"]} pts · {pos_l["pj"]} jogos</span></div>' if pos_l else "")
                  + (f'<div><small>Últimos 5 jogos</small>{forma(cx, time)}</div>' if ult else "") + "</div>")
    mini = ""
    if pos_l:
        n = len(pos_g["linhas"])
        if n > 6:
            a = max(1, pos_l["pos"] - 2)
            b = min(n, a + 4)
            a = max(1, b - 4)
            mini = (f'<h2>Posição {e(no_(cx.comp_nome(pos_k)))}</h2>' + tabela_html(cx, pos_k, {time}, (a, b), com_forma=False)
                    + f'<p class="mais"><a href="/campeonato/{slug(pos_k)}/#tabela">Ver a tabela completa</a></p>')
        else:
            mini = f'<h2>Posição {e(no_(cx.comp_nome(pos_k)))}</h2>' + tabela_html(cx, pos_k, {time}, com_forma=False)
    corpo = (f'<h1>{escudo(cx, time, 44)} Jogos do {e(nome)}: onde assistir ao vivo</h1>{intro}{resumo}'
             + (f"<h2>Próximos jogos</h2>{lista(cx, futuros)}" if futuros else "")
             + (f"<h2>Últimos resultados</h2>{resultados_html(cx, ult, time)}" if ult else "")
             + mini
             + '<p class="cta"><a href="/?utm_source=pagina_time&utm_medium=link#seguindo">Seguir o time e receber aviso no dia do jogo</a></p>'
             + '<p class="leg2">Horários de Brasília. Canais conferidos todos os dias nas grades oficiais das emissoras.</p>')
    titulo = f"Próximo jogo do {nome}: horário, onde assistir e últimos resultados"
    ld = {"@context": "https://schema.org", "@type": "SportsTeam", "name": time, "sport": "Futebol", "url": URL + cam}
    if cx.esc.get(time):
        ld["logo"] = cx.esc[time]
    return pagina(cx, cam, titulo, desc, corpo, [ld], [("Início", "/"), (f"Jogos do {nome}", cam)])


def pagina_comp(cx, k, jogos):
    nome = cx.comp_nome(k)
    cam = f"/campeonato/{slug(k)}/"
    futuros = [j for j in jogos if not j.get("placar")]
    res = sorted([x for x in cx.hist["jogos"].values() if x["comp"] == k], key=lambda x: x["inicio"], reverse=True)[:30]
    tem_tab = k in cx.tabs
    temporada = (cx.tabs.get(k) or {}).get("temporada", "")
    rd = cx.rods.get(k)
    if rd:  # jogos por rodada: no computador fica ao lado da tabela; no celular, numa aba
        abas = [("tabela", "Tabela", tabela_html(cx, k)) if tem_tab else None, ("jogos", "Jogos", rodadas_caixa(cx, k, rd))]
    else:
        abas = [("tabela", "Tabela", tabela_html(cx, k)) if tem_tab else None,
                ("jogos", "Próximos jogos", por_dia(cx, futuros, mostrar_comp=False) if futuros else "<p>Sem jogos marcados nos próximos dias.</p>"),
                ("resultados", "Resultados", resultados_html(cx, res, mostrar_comp=False) if res else "<p>Sem resultados recentes.</p>")]
    abas = [a for a in abas if a]
    botoes = "".join(f'<a class="aba{" on" if i == 0 else ""}" href="#{a[0]}" role="tab" data-aba="{a[0]}">{e(a[1])}</a>' for i, a in enumerate(abas))
    secoes = "".join(f'<section id="{a[0]}" class="painel" role="tabpanel"><h2 class="ph">{e(a[1])}</h2>{a[2]}</section>' for a in abas)
    lado_a_lado = bool(rd) and len(abas) == 2
    if tem_tab:
        g0 = cx.tabs[k]["grupos"]
        lider = g0[0]["linhas"][0]
        ano = temporada if temporada and len(temporada) <= 9 else ""
        titulo = f"Tabela {do_(nome)}{(' ' + ano) if ano else ''} atualizada, jogos e onde assistir"
        desc = (f"Classificação {do_(nome)} atualizada a cada rodada"
                + (f" (líder: {lider['time']}, {lider['pts']} pts)" if len(g0) == 1 else "")
                + ", próximos jogos com horário de Brasília e onde assistir, e os últimos resultados.")
        h1 = f"{e(nome)}: tabela, jogos e onde assistir"
    else:
        titulo = f"{nome}: jogos, resultados e onde assistir ao vivo"
        desc = (f"Agenda {do_(nome)} com horário de Brasília e onde assistir cada jogo"
                + (f": {len(futuros)} jogos nos próximos dias." if futuros else ".") + " Últimos resultados.")
        h1 = f"{e(nome)}: jogos e onde assistir"
    if rd:
        g = rd["rodadas"][rd["atual"]]
        desc = desc.replace("próximos jogos", f"jogos da {g['nome'].split(' · ')[-1]}", 1) if "próximos jogos" in desc else desc
    nav = f'<nav class="abas" role="tablist">{botoes}</nav>' if len(abas) > 1 else ""
    corpo = f'<h1>{h1}</h1>' + (f'<div class="camp2">{nav}{secoes}</div>' if lado_a_lado else nav + secoes)
    return pagina(cx, cam, titulo, desc, corpo, None, [("Início", "/"), (nome, cam)], largo=lado_a_lado)


# ---------------------------------------------------------------- jogos por rodada (como no ge)
# O HTML de cada rodada sai só daqui: vai na página do campeonato (a rodada de agora) e no arquivo
# /dados/rod-<campeonato>.json, que o rodadas.js usa para trocar de rodada sem recarregar.
def _periodo(de, ate):
    if not de:
        return ""
    a, b = datetime.fromisoformat(de), datetime.fromisoformat(ate or de)
    if a == b:
        return f"{SEMANA[a.weekday()].split('-')[0]}, {a.day} de {MESES[a.month - 1]}"
    if a.month == b.month:
        return f"{a.day} a {b.day} de {MESES[b.month - 1]}"
    return f"{a.day} de {MESES[a.month - 1][:3]}. a {b.day} de {MESES[b.month - 1][:3]}."


def _rodada_jogo(cx, j):
    t = datetime.fromisoformat(j["inicio"]).astimezone(BRT) if j.get("inicio") else None
    st = j.get("st", "")
    cls = {"fim": " fim", "adiado": " adiado"}.get(st, "")
    info = []
    if t:
        quando = f"{SEMANA[t.weekday()][:3]} {t:%d/%m}" + (f" · {hora(t)}" if j.get("hora", True) else " · horário a definir")
        info.append(f'<time datetime="{e(t.isoformat())}">{e(quando)}</time>')
    else:
        info.append("<span>Data a definir</span>")
    if j.get("local"):
        info.append(f'<span class="rj-loc">{e(j["local"])}</span>')
    if j.get("placar"):
        a, b = j["placar"]
        meio = f'<span class="rj-p"><b>{a}</b><i>x</i><b>{b}</b></span>'
    else:
        meio = '<span class="rj-p rj-x"><i>x</i></span>'
    times = (f'<span class="rj-t rj-c"><span class="rj-n">{e(j["casa"])}</span>{escudo(cx, j["casa"], 30)}</span>{meio}'
             f'<span class="rj-t rj-f">{escudo(cx, j["fora"], 30)}<span class="rj-n">{e(j["fora"])}</span></span>')
    pg = j.get("pg")
    rot = f'{j["casa"]} x {j["fora"]}' + (f', {j["placar"][0]} a {j["placar"][1]}' if j.get("placar") else "")
    miolo = (f'<a class="rj-m" href="{e(pg)}" aria-label="{e(rot)}: ver detalhes">{times}</a>' if pg
             else f'<div class="rj-m" aria-label="{e(rot)}">{times}</div>')
    if st == "fim":
        rodape = "Pênaltis: " + " x ".join(map(str, j["pen"])) if j.get("pen") else "Encerrado"
        rodape = f'<p class="rj-tv rj-s">{e(rodape)}</p>'
    elif st == "adiado":
        rodape = '<p class="rj-tv rj-s">Adiado</p>'
    elif j.get("canais"):
        cs = []
        for c in j["canais"]:
            nome_c, _, _, gratis = cx.canal_info(j, c)
            cs.append(f'<span class="{"gr" if gratis else ""}">{e(nome_c)}</span>')
        rodape = f'<p class="rj-tv">{"".join(cs)}</p>'
    elif t and t > cx.agora - timedelta(hours=3):
        rodape = '<p class="rj-tv rj-s">Canais a confirmar</p>'
    else:
        rodape = ""
    dados = "".join(f' data-{a}="{e(j[b])}"' for a, b in (("eid", "eid"), ("lg", "lg"), ("ed", "ed")) if j.get(b))
    return f'<li class="rjx{cls}"{dados}><p class="rj-i">{" · ".join(info)}</p>{miolo}{rodape}</li>'


def rodada_html(cx, g):
    return "".join(_rodada_jogo(cx, j) for j in g["jogos"]) or '<li class="rj-vazio">Sem jogos nesta rodada.</li>'


def rodadas_caixa(cx, k, rd):
    """A caixa com as setas e a rodada de agora já desenhada (o resto chega pelo JSON)."""
    i = rd["atual"]
    g = rd["rodadas"][i]
    opcoes = "".join(f'<option value="{n}"{" selected" if n == i else ""}>{e(x["nome"])}</option>' for n, x in enumerate(rd["rodadas"]))
    return (f'<div class="rdx" data-rod="{e(slug(k))}" data-i="{i}" data-total="{len(rd["rodadas"])}">'
            f'<div class="rd-nav"><button class="rd-b rd-ant" type="button" aria-label="Rodada anterior"{" disabled" if i == 0 else ""}>'
            '<svg width="22" height="22" viewBox="0 0 24 24" aria-hidden="true"><path d="M15 5l-7 7 7 7" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/></svg></button>'
            f'<div class="rd-t"><b>{e(g["nome"])}</b><small>{e(_periodo(g["de"], g["ate"]))}</small>'
            f'<label class="so-leitor" for="rd-sel-{e(slug(k))}">Escolher a rodada</label><select class="rd-sel" id="rd-sel-{e(slug(k))}">{opcoes}</select></div>'
            f'<button class="rd-b rd-prox" type="button" aria-label="Próxima rodada"{" disabled" if i == len(rd["rodadas"]) - 1 else ""}>'
            '<svg width="22" height="22" viewBox="0 0 24 24" aria-hidden="true"><path d="M9 5l7 7-7 7" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/></svg></button></div>'
            f'<ul class="rd-l" aria-live="polite">{rodada_html(cx, g)}</ul></div>')


def rodadas_arquivo(cx, rd):
    """Conteúdo do /dados/rod-<campeonato>.json: cada rodada com o HTML pronto."""
    return {"atual": rd["atual"], "rodadas": [{"nome": g["nome"], "periodo": _periodo(g["de"], g["ate"]), "html": rodada_html(cx, g)}
                                             for g in rd["rodadas"]]}


def preparar_rodadas(cx, existentes):
    """Liga cada jogo da rodada à página dele (quando ela existe no site)."""
    for rd in cx.rods.values():
        for g in rd["rodadas"]:
            for j in g["jogos"]:
                if j.get("inicio") and "A definir" not in (j["casa"], j["fora"]):
                    cam = caminho_jogo(j)
                    if cam in existentes:
                        j["pg"] = cam


def pagina_tabelas(cx):
    itens = []
    for k in sorted(cx.tabs, key=lambda k: (not cx.comps.get(k, {}).get("principal"), cx.comp_nome(k))):
        g = cx.tabs[k]["grupos"]
        top = " · ".join(f'{l["pos"]}º {l["time"]}' for l in g[0]["linhas"][:3]) if len(g) == 1 else f"{len(g)} grupos"
        itens.append(f'<li><a class="lj" href="/campeonato/{slug(k)}/#tabela"><span class="lt">{e(cx.comp_nome(k))}</span><span class="ls">{e(top)}</span></a></li>')
    corpo = ("<h1>Tabelas dos campeonatos</h1><p>Classificação atualizada a cada rodada. Toque no campeonato para ver a tabela completa, os próximos jogos e onde assistir.</p>"
             + '<ul class="lista tabs1">' + "".join(itens) + "</ul>")
    return pagina(cx, "/tabelas/", "Tabelas dos campeonatos de futebol atualizadas: Brasileirão, Premier League e mais",
                  "Tabela atualizada do Brasileirão, Série B, Libertadores, Premier League, La Liga, Champions e outros campeonatos, com jogos e onde assistir.",
                  corpo, None, [("Início", "/"), ("Tabelas", "/tabelas/")])


def pagina_dia(cx, cam, rotulo, dia, jogos):
    d = datetime(dia.year, dia.month, dia.day, tzinfo=BRT)
    gr = [j for j in jogos if cx.tem_gratis(j)]
    titulo = f"Jogos de {rotulo} na TV ({d:%d/%m}): horários e onde assistir"
    destaque = sorted(jogos, key=lambda j: -(cx.pop(j["casa"]) + cx.pop(j["fora"])))[:3]
    desc = (f"{len(jogos)} jogos de futebol {rotulo}, {data_curta(d)}, com horário de Brasília e onde assistir"
            + (": " + ", ".join(f"{j['casa']} x {j['fora']}" for j in destaque) if destaque else "") + ".")
    blocos = []
    por_comp = {}
    for j in jogos:
        por_comp.setdefault(j["comp"], []).append(j)
    ordem = sorted(por_comp, key=lambda k: (not cx.comps.get(k, {}).get("principal"), -max(cx.pop(x["casa"]) + cx.pop(x["fora"]) for x in por_comp[k])))
    for k in ordem:
        blocos.append(f'<h2><a href="/campeonato/{slug(k)}/">{e(cx.comp_nome(k))}</a></h2>' + lista(cx, por_comp[k], mostrar_data=False, mostrar_comp=False))
    intro = (f"<p>{len(jogos)} jogos {rotulo}, {e(data_longa(d))}"
             + (f", {len(gr)} com transmissão grátis" if gr else "") + ". Toque no jogo para ver os canais e os links oficiais.</p>")
    corpo = f"<h1>Jogos de {rotulo} na TV e onde assistir</h1>{intro}" + ("".join(blocos) if jogos else "<p>Nenhum jogo na agenda.</p>")
    return pagina(cx, cam, titulo, desc, corpo, None, [("Início", "/"), (f"Jogos de {rotulo}", cam)])


# ---------------------------------------------------------------- geração, sitemap e IndexNow
def gerar(dados, head_extra, favicon, pin, extras=None):
    cx = Ctx(dados, head_extra, favicon, pin, extras)
    estado = json.loads(ESTADO.read_text(encoding="utf-8")) if ESTADO.exists() else {"paginas": {}}
    pags = estado.setdefault("paginas", {})
    novas = {}

    cx.jogos = [j for j in cx.jogos if "A definir" not in (j["casa"], j["fora"])]
    for j in cx.jogos:
        novas[j["_pg"]] = (pagina_jogo(cx, j), j["_t"].date().isoformat())
    times = {}
    for j in cx.jogos:
        for t in (j["casa"], j["fora"]):
            if t != "A definir":
                times.setdefault(t, []).append(j)
    for t, js in times.items():
        novas[f"/time/{slug(t)}/"] = (pagina_time(cx, t, js), "")
    for cam, info in pags.items():  # time sem jogo agora: a página continua, sem jogos marcados
        if cam.startswith("/time/") and cam not in novas and info.get("nome"):
            novas[cam] = (pagina_time(cx, info["nome"], []), "")
    nomes_time = {f"/time/{slug(t)}/": t for t in times}
    guarda = (cx.hoje - timedelta(days=GUARDAR_DIAS)).isoformat()
    preparar_rodadas(cx, set(novas) | {c for c, i in pags.items() if c.startswith("/jogo/") and i.get("dia", "") >= guarda})
    pasta = SITE / "dados"
    pasta.mkdir(parents=True, exist_ok=True)
    feitos = set()
    for k, rd in cx.rods.items():
        nome_arq = f"rod-{slug(k)}.json"
        conteudo = json.dumps(rodadas_arquivo(cx, rd), ensure_ascii=False, separators=(",", ":"))
        arq = pasta / nome_arq
        if not arq.exists() or arq.read_text(encoding="utf-8") != conteudo:
            arq.write_text(conteudo, encoding="utf-8")
        feitos.add(nome_arq)
    for f in pasta.glob("rod-*.json"):
        if f.name not in feitos:
            f.unlink()
    comps = {}
    for j in cx.jogos:
        comps.setdefault(j["comp"], []).append(j)
    for k in cx.comps:
        novas[f"/campeonato/{slug(k)}/"] = (pagina_comp(cx, k, comps.get(k, [])), "")
    if cx.tabs:
        novas["/tabelas/"] = (pagina_tabelas(cx), "")
    for cam, rot, dia in (("/jogos-de-hoje/", "hoje", cx.hoje), ("/jogos-de-amanha/", "amanhã", cx.hoje + timedelta(days=1))):
        js = [j for j in cx.jogos if j["_t"].date() == dia]
        novas[cam] = (pagina_dia(cx, cam, rot, dia, js), "")

    mudou = []
    agora = cx.agora.isoformat(timespec="minutes")
    for cam, (html, dia) in novas.items():
        arq = SITE / cam.strip("/") / "index.html"
        h = hashlib.sha1(html.encode()).hexdigest()[:16]
        ant = pags.get(cam) or {}
        if ant.get("h") != h or not arq.exists():
            arq.parent.mkdir(parents=True, exist_ok=True)
            arq.write_text(html, encoding="utf-8")
            pags[cam] = {"h": h, "mod": agora, "dia": dia or ant.get("dia", "")}
            if cam in nomes_time or ant.get("nome"):
                pags[cam]["nome"] = nomes_time.get(cam) or ant["nome"]
            mudou.append(cam)
        else:
            if dia:
                ant["dia"] = dia
            if cam in nomes_time:
                ant["nome"] = nomes_time[cam]

    # páginas de jogos antigos ficam no ar por GUARDAR_DIAS; depois saem do site e do sitemap
    limite = (cx.hoje - timedelta(days=GUARDAR_DIAS)).isoformat()
    for cam in list(pags):
        info = pags[cam]
        velho = cam.startswith("/jogo/") and info.get("dia") and info["dia"] < limite
        sumiu = cam not in novas and not cam.startswith("/jogo/")
        if velho or sumiu:
            shutil.rmtree(SITE / cam.strip("/"), ignore_errors=True)
            del pags[cam]

    # sitemap
    urls = [("/", agora, "hourly", "1.0"), ("/jogos-de-hoje/", pags.get("/jogos-de-hoje/", {}).get("mod", agora), "hourly", "0.9"),
            ("/jogos-de-amanha/", pags.get("/jogos-de-amanha/", {}).get("mod", agora), "daily", "0.8")]
    for cam, info in sorted(pags.items()):
        if cam in ("/jogos-de-hoje/", "/jogos-de-amanha/"):
            continue
        pri = "0.8" if cam.startswith("/jogo/") and info.get("dia", "") >= cx.hoje.isoformat() else (
            "0.7" if cam.startswith(("/time/", "/campeonato/", "/tabelas/")) else "0.4")
        urls.append((cam, info["mod"], "daily", pri))
    urls.append(("/privacidade.html", "2026-11-17", "yearly", "0.1"))
    xml = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for cam, mod, freq, pri in urls:
        xml.append(f" <url><loc>{URL}{e(cam)}</loc><lastmod>{mod}</lastmod><changefreq>{freq}</changefreq><priority>{pri}</priority></url>")
    xml.append("</urlset>")
    (SITE / "sitemap.xml").write_text("\n".join(xml) + "\n", encoding="utf-8")
    (SITE / f"{INDEXNOW_KEY}.txt").write_text(INDEXNOW_KEY, encoding="utf-8")

    ESTADO.write_text(json.dumps(estado, ensure_ascii=False, indent=0, sort_keys=True), encoding="utf-8")
    log(f"{len(novas)} páginas ({len(mudou)} novas ou mudadas), sitemap com {len(urls)} endereços")
    return mudou


PENDENTE = RAIZ / "dados" / "indexnow_pendente.json"


def guardar_para_avisar(mudou):
    """Guarda as páginas mudadas (somando às que ainda não foram avisadas); o GitHub avisa depois de publicar."""
    antes = json.loads(PENDENTE.read_text(encoding="utf-8")) if PENDENTE.exists() else []
    PENDENTE.write_text(json.dumps(sorted(set(antes) | set(mudou))), encoding="utf-8")


def avisar_buscadores(mudou=None):
    """IndexNow: avisa Bing (e quem usa o Bing) das páginas novas ou mudadas. Grátis, sem conta."""
    if mudou is None:
        mudou = json.loads(PENDENTE.read_text(encoding="utf-8")) if PENDENTE.exists() else []
    if not mudou:
        return log("IndexNow: nada mudou")
    corpo = json.dumps({"host": "ondepassajogo.com.br", "key": INDEXNOW_KEY,
                        "keyLocation": f"{URL}/{INDEXNOW_KEY}.txt",
                        "urlList": [URL + c for c in ["/"] + mudou][:10000]}).encode()
    req = urllib.request.Request("https://api.indexnow.org/indexnow", data=corpo,
                                 headers={"Content-Type": "application/json; charset=utf-8"})
    import time
    for tentativa in range(3):
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                log(f"IndexNow: {len(mudou)} endereços enviados (HTTP {r.status})")
                PENDENTE.write_text("[]", encoding="utf-8")
                return
        except Exception as ex:
            log(f"IndexNow tentativa {tentativa + 1} falhou: {ex}")
            time.sleep(60)  # o site publicado pode levar um minuto para mostrar o arquivo da chave


if __name__ == "__main__":
    avisar_buscadores()
