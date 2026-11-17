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


class Ctx:
    def __init__(self, dados, head_extra, favicon, pin):
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
def pagina(cx, caminho, titulo, descricao, corpo, jsonld=None, migalhas=None, noindex=False):
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
<link rel="stylesheet" href="/p.css">
{cx.head_extra}
{ld}</head>
<body>
<header class="topo"><div class="wrap"><a class="marca" href="/">{cx.pin}<span>ONDE PASSA <b>JOGO</b></span></a><a class="todos" href="/">Ver agenda completa</a></div></header>
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


# ---------------------------------------------------------------- página do jogo
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
             + (f", pela {e(rodada)}" if rodada else "") + f" do {e(comp)}"
             + (f", no {e(local)}" if local else "") + ". ")
    if nomes:
        texto += f"A transmissão é {'da' if len(nomes) == 1 else 'de'} {e(lista_nomes)}."
        if gratis:
            texto += f" Dá para assistir de graça em {e(', '.join(gratis))}."
    else:
        texto += "Os canais ainda não foram anunciados; esta página é atualizada assim que sair a confirmação."
    nota = f'<p class="nota">{e(j["nota"])}</p>' if j.get("nota") else ""
    res = (f'<p class="res">Resultado: <b>{e(casa)} {placar["casa"]} x {placar["fora"]} {e(fora)}</b></p>' if encerrado else "")

    mesmos = [x for x in cx.jogos if x["comp"] == j["comp"] and x["_t"].date() == t.date() and x is not j]
    prox_c = [x for x in cx.jogos if casa in (x["casa"], x["fora"]) and x is not j and x["_t"] > t][:4]
    prox_f = [x for x in cx.jogos if fora in (x["casa"], x["fora"]) and x is not j and x["_t"] > t][:4]
    rel = ""
    if mesmos:
        rel += f"<h2>Outros jogos do {e(comp)} no mesmo dia</h2>" + lista(cx, mesmos, mostrar_data=False, mostrar_comp=False)
    for time, xs in ((casa, prox_c), (fora, prox_f)):
        if xs and time != "A definir":
            rel += f'<h2>Próximos jogos do {e(nl(time))}</h2>' + lista(cx, xs)

    faq = f"""<h2>Que horas é o jogo {e(casa)} x {e(fora)}?</h2>
<p>A partida começa às <b>{hora(t)}</b>, horário de Brasília, {e(data_longa(t))}.</p>
<h2>Onde vai passar {e(casa)} x {e(fora)}?</h2>
<p>{(f"Na {e(lista_nomes)}." if nomes else "Ainda não há canal confirmado.")}{(" Os botões acima levam direto para a transmissão oficial." if nomes else "")}</p>
<h2>Tem transmissão grátis?</h2>
<p>{(f"Sim: {e(', '.join(gratis))}." if gratis else ("Por enquanto, não há transmissão gratuita anunciada." if nomes else "Ainda não sabemos; confira de novo mais perto do jogo."))}</p>
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
        "superEvent": {"@type": "SportsEvent", "name": comp},
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

    corpo = f"""<article class="jogo">
<p class="comp"><a href="/campeonato/{slug(j['comp'])}/">{e(comp)}</a>{(' · ' + e(rodada)) if rodada else ''}</p>
<h1>Onde assistir {e(casa)} x {e(fora)} ao vivo</h1>
<div class="placa">
 <a class="tm" href="/time/{slug(casa)}/">{escudo(cx, casa, 56)}<span>{e(casa)}</span></a>
 <div class="hr">{(f'<b class="pl">{placar["casa"]} x {placar["fora"]}</b><small>Encerrado</small>' if encerrado else f'<b>{hora(t)}</b><small>{e(data_curta(t))}</small>')}</div>
 <a class="tm" href="/time/{slug(fora)}/">{escudo(cx, fora, 56)}<span>{e(fora)}</span></a>
</div>
<p class="quando">{e(data_longa(t).capitalize())} · {hora(t)} (Brasília){(' · ' + e(local)) if local else ''}</p>
{res}{nota}
<h2>{'Onde passou' if encerrado else 'Onde vai passar'}</h2>
{lista_canais(cx, j)}
<p>{texto}</p>
<p class="cta"><a href="/?utm_source=pagina_jogo&utm_medium=link#seguindo">Siga seu time e receba aviso no celular</a></p>
{faq}
{rel}
<p class="mais"><a href="/jogos-de-hoje/">Ver todos os jogos de hoje</a> · <a href="/campeonato/{slug(j['comp'])}/">Jogos do {e(comp)}</a></p>
</article>"""
    mig = [("Início", "/"), (comp, f"/campeonato/{slug(j['comp'])}/"), (f"{casa} x {fora}", j["_pg"])]
    return pagina(cx, j["_pg"], titulo, desc, corpo, [ld], mig)


# ---------------------------------------------------------------- time, campeonato, hoje
def pagina_time(cx, time, jogos):
    nome = nl(time)
    cam = f"/time/{slug(time)}/"
    futuros = [j for j in jogos if not j.get("placar")]
    passados = [j for j in jogos if j.get("placar")][-3:]
    prox = futuros[0] if futuros else None
    if prox:
        can = ", ".join(cx.canal_info(prox, c)[0] for c in prox.get("canais", [])) or "canal a confirmar"
        intro = (f'<p class="dest">Próximo jogo: <a href="{e(prox["_pg"])}"><b>{e(prox["casa"])} x {e(prox["fora"])}</b></a>, '
                 f'{e(data_curta(prox["_t"]))} às {hora(prox["_t"])} · {e(can)}</p>')
        desc = (f"Próximo jogo do {nome}: {prox['casa']} x {prox['fora']}, {data_curta(prox['_t'])} às {hora(prox['_t'])}"
                f" ({can}). Veja todos os jogos, horários e onde assistir.")
    else:
        intro, desc = "<p>Sem jogos marcados nos próximos dias.</p>", f"Jogos do {nome}: horários e onde assistir ao vivo."
    corpo = (f'<h1>{escudo(cx, time, 44)} Jogos do {e(nome)}: onde assistir ao vivo</h1>{intro}'
             + (f"<h2>Próximos jogos</h2>{lista(cx, futuros)}" if futuros else "")
             + (f"<h2>Últimos resultados</h2>{lista(cx, passados)}" if passados else "")
             + f'<p>Todos os horários são de Brasília. Os canais de cada jogo são conferidos todos os dias nas grades oficiais das emissoras.</p>'
             + '<p class="cta"><a href="/?utm_source=pagina_time&utm_medium=link#seguindo">Seguir o time e receber aviso no dia do jogo</a></p>')
    titulo = f"Próximo jogo do {nome}: horário e onde assistir ao vivo"
    ld = {"@context": "https://schema.org", "@type": "SportsTeam", "name": time, "sport": "Futebol", "url": URL + cam}
    if cx.esc.get(time):
        ld["logo"] = cx.esc[time]
    return pagina(cx, cam, titulo, desc, corpo, [ld], [("Início", "/"), (f"Jogos do {nome}", cam)])


def pagina_comp(cx, k, jogos):
    nome = cx.comp_nome(k)
    cam = f"/campeonato/{slug(k)}/"
    futuros = [j for j in jogos if not j.get("placar")]
    titulo = f"{nome}: jogos, horários e onde assistir ao vivo"
    desc = (f"Agenda do {nome} com horário de Brasília e onde assistir cada jogo"
            + (f": {len(futuros)} jogos nos próximos dias." if futuros else "."))
    corpo = (f"<h1>{e(nome)}: jogos e onde assistir</h1>"
             + (por_dia(cx, futuros, mostrar_comp=False) if futuros else "<p>Sem jogos marcados nos próximos dias.</p>"))
    return pagina(cx, cam, titulo, desc, corpo, None, [("Início", "/"), (nome, cam)])


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
def gerar(dados, head_extra, favicon, pin):
    cx = Ctx(dados, head_extra, favicon, pin)
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
    comps = {}
    for j in cx.jogos:
        comps.setdefault(j["comp"], []).append(j)
    for k in cx.comps:
        novas[f"/campeonato/{slug(k)}/"] = (pagina_comp(cx, k, comps.get(k, [])), "")
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
            "0.7" if cam.startswith(("/time/", "/campeonato/")) else "0.4")
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


PENDENTE = RAIZ / ".indexnow_pendente.json"


def guardar_para_avisar(mudou):
    """Guarda as páginas mudadas; o GitHub avisa os buscadores depois de publicar o site."""
    PENDENTE.write_text(json.dumps(mudou), encoding="utf-8")


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
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            log(f"IndexNow: {len(mudou)} endereços enviados (HTTP {r.status})")
    except Exception as ex:
        log(f"IndexNow falhou: {ex}")


if __name__ == "__main__":
    avisar_buscadores()
