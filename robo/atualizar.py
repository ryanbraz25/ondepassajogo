#!/usr/bin/env python3
"""
Robô de atualização da Agenda do Futebol.

Roda sozinho (GitHub Actions, a cada 3 horas) e:
  1. busca jogos, horários e placares dos próximos dias na ESPN (sem chave);
  2. junta os canais que a pesquisa noturna do Claude grava em dados/canais.json;
  3. se houver chave da API do YouTube, procura as transmissões agendadas nos canais
     oficiais (CazéTV, ge tv, Canal GOAT...) e põe o link direto da live no jogo;
  4. aplica dados/verificados.json (correções feitas à mão), que sempre têm prioridade;
  5. acha o escudo de cada time (TheSportsDB) e a bandeira de cada seleção;
  6. grava dados/jogos.json e gera site/index.html.

Só usa a biblioteca padrão do Python. Variáveis de ambiente (todas opcionais):
  THESPORTSDB_KEY   chave da TheSportsDB (padrão: chave gratuita "123")
  YOUTUBE_API_KEY   chave da YouTube Data API v3
  AMAZON_TAG        sua tag de Associado Amazon (vai no link do Prime Video)

Uso:  python robo/atualizar.py            (normal: a cada 6 horas busca 15 dias; nas outras, ontem a amanhã)
      python robo/atualizar.py --completo (força a busca dos 15 dias)
      python robo/atualizar.py --offline  (não acessa a internet; só monta o site)
"""
import json, os, re, sys, unicodedata, urllib.parse, urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
BRT = timezone(timedelta(hours=-3))  # Brasília não tem horário de verão desde 2019
OFFLINE = "--offline" in sys.argv


def log(*a):
    print("[robô]", *a, flush=True)


def ler(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def norm(s):
    s = unicodedata.normalize("NFD", s or "").encode("ascii", "ignore").decode().lower()
    s = re.sub(r"\b(fc|ec|sc|cf|afc|club|clube|de|futebol)\b", " ", s)
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def get_json(url, headers=None, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": "agenda-futebol/1.0", **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def chave(j):
    return j["inicio"][:10] + "|" + norm(j["casa"]) + "|" + norm(j["fora"])


# ---------------------------------------------------------------- TheSportsDB
def thesportsdb(cfg, dias):
    key = os.environ.get("THESPORTSDB_KEY", "123")
    ligas = {v["thesportsdb"]: k for k, v in cfg["competicoes"].items() if v.get("thesportsdb")}
    jogos = []
    for d in dias:
        url = f"https://www.thesportsdb.com/api/v1/json/{key}/eventsday.php?d={d}&s=Soccer"
        try:
            dados = get_json(url).get("events") or []
        except Exception as e:
            log("TheSportsDB falhou em", d, e)
            continue
        for ev in dados:
            comp = ligas.get(ev.get("strLeague"))
            if not comp or not ev.get("strTime"):
                continue
            utc = datetime.fromisoformat(f'{ev["dateEvent"]}T{ev["strTime"][:8]}+00:00')
            jogos.append({
                "inicio": utc.astimezone(BRT).isoformat(),
                "comp": comp,
                "casa": ev.get("strHomeTeam", ""),
                "fora": ev.get("strAwayTeam", ""),
                "local": ev.get("strVenue") or "",
                "rodada": f'{ev["intRound"]}ª rodada' if ev.get("intRound") else "",
                "canais": [],
                "status": "a_confirmar",
                "_id": ev.get("idEvent"),
            })
    log(f"TheSportsDB: {len(jogos)} jogos das ligas escolhidas")
    return jogos


def thesportsdb_tv(cfg, dias, jogos):
    """Canais de TV do Brasil. Só funciona com chave premium (API v2)."""
    key = os.environ.get("THESPORTSDB_KEY")
    if not key or key == "123":
        return
    apel = cfg["apelidos_canais"]
    por_id = {j.get("_id"): j for j in jogos if j.get("_id")}
    n = 0
    for d in dias:
        try:
            tv = get_json(f"https://www.thesportsdb.com/api/v2/json/filter/tv/day/{d}",
                          headers={"X-API-KEY": key}).get("filter") or []
        except Exception as e:
            log("TV TheSportsDB falhou em", d, e)
            continue
        for t in tv:
            if (t.get("strCountry") or "").lower() not in ("brazil", "brasil"):
                continue
            j = por_id.get(t.get("idEvent"))
            canal = apel.get((t.get("strChannel") or "").strip().lower())
            if j and canal and canal not in j["canais"]:
                j["canais"].append(canal)
                n += 1
    log(f"TheSportsDB TV: {n} canais brasileiros encontrados")


# ---------------------------------------------------------------- ESPN (jogos, horários e placares)
ESPN = "https://site.api.espn.com/apis/site/v2/sports/soccer/{}/scoreboard?dates={}"
CACHE = RAIZ / "dados" / "agenda_api.json"


def nome(cfg, t):
    """Nome do time como o site usa (português, igual ao das tarefas de canais)."""
    return cfg.get("nomes", {}).get(t, t)


LOGO_LIGA = {}


def espn(cfg, completo):
    """Busca os jogos de cada campeonato na ESPN, um dia por vez.

    completo=True busca de ontem até dias_a_frente; senão só ontem, hoje e amanhã
    (o resto vem do cache dados/agenda_api.json, gravado na última busca completa)."""
    import time
    hoje = datetime.now(BRT).date()
    n_dias = cfg["site"]["dias_a_frente"] + 1 if completo else 3
    datas = [(hoje + timedelta(days=i - 1)).strftime("%Y%m%d") for i in range(n_dias)]
    cache = ler(CACHE) if CACHE.exists() else {}
    destaque = set(cfg.get("selecoes_destaque", []))
    ok = falhas = 0
    pares = []
    for comp, c in cfg["competicoes"].items():
        ligas = c.get("espn") or []
        for liga in ([ligas] if isinstance(ligas, str) else ligas):
            pares.append((comp, c, liga))
    for comp, c, liga in pares:
        for d in datas:
            try:
                r = get_json(ESPN.format(liga, d))
                evs = r.get("events") or []
                for lg in r.get("leagues") or []:
                    for lo in lg.get("logos") or []:
                        if lo.get("href") and "dark" not in (lo.get("rel") or []):
                            LOGO_LIGA.setdefault(comp, lo["href"])
                            break
            except Exception as e:
                falhas += 1
                log("ESPN falhou:", liga, d, e)
                continue
            ok += 1
            for k in [k for k, v in cache.items() if v.get("_liga") == liga and v.get("_d") == d]:
                del cache[k]
            for ev in evs:
                try:
                    cp = ev["competitions"][0]
                    times = {x["homeAway"]: x for x in cp["competitors"]}
                    casa = nome(cfg, times["home"]["team"]["displayName"])
                    fora = nome(cfg, times["away"]["team"]["displayName"])
                except (KeyError, IndexError):
                    continue
                if c.get("so_destaque") and not ({casa, fora} & destaque):
                    continue
                st = ev.get("status", {}).get("type", {})
                ini = datetime.fromisoformat(ev["date"].replace("Z", "+00:00")).astimezone(BRT)
                v = cp.get("venue") or ev.get("venue") or {}
                local = ", ".join(x for x in (v.get("fullName"), (v.get("address") or {}).get("city")) if x)
                j = {"inicio": ini.isoformat(), "comp": comp, "casa": casa, "fora": fora, "local": local,
                     "canais": list(c.get("canais_padrao", [])), "status": "a_confirmar",
                     "_liga": liga, "_d": d, "eid": str(ev.get("id", "")), "lg": liga, "ed": d,
                     "_logos": {casa: times["home"]["team"].get("logo", ""), fora: times["away"]["team"].get("logo", "")}}
                nm = st.get("name", "")
                if st.get("completed") and "CANCEL" not in nm and "POSTPON" not in nm:
                    try:
                        j["placar"] = {"casa": int(times["home"]["score"]), "fora": int(times["away"]["score"])}
                    except (KeyError, ValueError, TypeError):
                        pass
                    pen = [times[x].get("shootoutScore") for x in ("home", "away")]
                    if all(p is not None for p in pen):
                        j["nota"] = f"Pênaltis: {int(pen[0])} x {int(pen[1])}"
                elif "POSTPON" in nm:
                    j["nota"] = "Adiado"
                elif "CANCEL" in nm:
                    j["nota"] = "Cancelado"
                cache["espn:" + str(ev.get("id"))] = j
            time.sleep(0.25)
    ontem = (hoje - timedelta(days=1)).isoformat()
    cache = {k: v for k, v in cache.items() if v["inicio"][:10] >= ontem}
    if ok:
        CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
    log(f"ESPN: {ok} consultas certas, {falhas} falhas, {len(cache)} jogos no cache")
    return [dict(v) for v in cache.values()]


def aplicar_canais(cfg, jogos):
    """Junta os canais pesquisados pelo Claude (dados/canais.json) aos jogos da ESPN.

    Casa por dia + mandante + visitante (aceita 1 dia de diferença, para jogo remarcado
    perto da meia-noite). Entrada com "inicio" e "comp" que não achar jogo vira jogo novo."""
    arq = RAIZ / "dados" / "canais.json"
    if not arq.exists():
        return jogos
    entradas = ler(arq).get("jogos", [])
    idx = {}
    for j in jogos:
        idx.setdefault((norm(j["casa"]), norm(j["fora"])), []).append(j)
    usados = n = 0
    for e in entradas:
        dia = (e.get("data") or e.get("inicio", ""))[:10]
        alvo = None
        for j in idx.get((norm(nome(cfg, e["casa"])), norm(nome(cfg, e["fora"]))), []):
            dif = abs((datetime.fromisoformat(j["inicio"]).date() - datetime.fromisoformat(dia).date()).days) if dia else 0
            if dif <= 1:
                alvo = j
                break
        if alvo is None:
            if e.get("inicio") and e.get("comp"):
                novo = {k: v for k, v in e.items() if k != "data"}
                novo.setdefault("canais", [])
                novo.setdefault("status", "a_confirmar")
                jogos.append(novo)
                n += 1
            continue
        usados += 1
        if e.get("canais"):
            alvo["canais"] = [c for c in e["canais"] if c in cfg["canais"]]
        for k in ("status", "rodada", "nota"):
            if e.get(k) and not (k == "nota" and alvo.get("nota") in ("Adiado", "Cancelado")):
                alvo[k] = e[k]
        if e.get("links"):
            alvo["links"] = {**alvo.get("links", {}), **e["links"]}
    log(f"Canais: {usados} jogos com canais pesquisados, {n} jogos acrescentados só pela pesquisa")
    return jogos


# ---------------------------------------------------------------- YouTube
def youtube(cfg, jogos):
    key = os.environ.get("YOUTUBE_API_KEY")
    if not key:
        log("YouTube: sem YOUTUBE_API_KEY, pulando")
        return
    base = "https://www.googleapis.com/youtube/v3/"
    n = 0
    for canal, handle in cfg["youtube"]["canais"].items():
        try:
            ch = get_json(base + "channels?" + urllib.parse.urlencode({"part": "id", "forHandle": handle, "key": key}))
            cid = ch["items"][0]["id"]
            busca = get_json(base + "search?" + urllib.parse.urlencode({
                "part": "snippet", "channelId": cid, "eventType": "upcoming",
                "type": "video", "maxResults": 25, "key": key}))
            ids = [i["id"]["videoId"] for i in busca.get("items", [])]
            if not ids:
                continue
            vids = get_json(base + "videos?" + urllib.parse.urlencode({
                "part": "snippet,liveStreamingDetails", "id": ",".join(ids), "key": key}))
        except Exception as e:
            log("YouTube falhou em", handle, e)
            continue
        for v in vids.get("items", []):
            titulo = norm(v["snippet"]["title"])
            ini = v.get("liveStreamingDetails", {}).get("scheduledStartTime")
            if not ini:
                continue
            ini = datetime.fromisoformat(ini.replace("Z", "+00:00"))
            for j in jogos:
                t = datetime.fromisoformat(j["inicio"])
                casa, fora = norm(j["casa"]), norm(j["fora"])
                if casa and fora and casa in titulo and fora in titulo and abs((t - ini).total_seconds()) < 3 * 3600:
                    if canal not in j["canais"]:
                        j["canais"].append(canal)
                    j.setdefault("links", {})[canal] = f'https://www.youtube.com/watch?v={v["id"]}'
                    n += 1
    log(f"YouTube: {n} transmissões ligadas a jogos")


# ---------------------------------------------------------------- montagem
def juntar(api, verificados):
    final = {chave(j): j for j in api}
    for v in verificados:
        k = chave(v)
        base = final.get(k, {})
        links = {**base.get("links", {}), **v.get("links", {})}
        final[k] = {**base, **v}
        if links:
            final[k]["links"] = links
    agora = datetime.now(BRT)
    ontem = (agora - timedelta(days=1)).date().isoformat()
    jogos = [j for j in final.values() if j["inicio"][:10] >= ontem]
    for j in jogos:
        j.pop("_id", None)
    return sorted(jogos, key=lambda j: (j["inicio"], j["casa"]))


def aplicar_afiliado(cfg):
    tag = os.environ.get("AMAZON_TAG")
    if not tag:
        return
    for c in cfg["canais"].values():
        if c.get("afiliado") == "amazon":
            sep = "&" if "?" in c["url"] else "?"
            c["url"] = f'{c["url"]}{sep}tag={urllib.parse.quote(tag)}'


# ---------------------------------------------------------------- Escudos e bandeiras
BADGE = "https://r2.thesportsdb.com/images/media/team/badge/"
FLAG = "https://flagcdn.com/w80/{}.png"


def espn_logo(u):
    """Escudo da ESPN já reduzido (80 px), para carregar rápido."""
    if not u:
        return ""
    m = re.match(r"https://a\.espncdn\.com(/i/.+)$", u)
    return f"https://a.espncdn.com/combiner/i?img={m.group(1)}&h=80&w=80" if m else u


def escudos(cfg, jogos, logos=None):
    """Escudo de cada time (TheSportsDB, grátis) e bandeira de cada seleção (flagcdn).

    dados/escudos.json guarda o que já foi achado: nome do time -> arquivo do escudo
    (ou "" quando a busca não achou). A cada rodada, busca no máximo 8 times novos,
    devagar, para respeitar o limite da chave gratuita."""
    arq = RAIZ / "dados" / "escudos.json"
    salvos = ler(arq) if arq.exists() else {}
    band = cfg.get("bandeiras", {})
    busca = cfg.get("escudos_busca", {})
    times = []
    for j in jogos:
        for t in (j["casa"], j["fora"]):
            if t not in times:
                times.append(t)
    logos = logos or {}
    faltam = [t for t in times if t not in band and t not in salvos and not logos.get(t)]
    if faltam and not OFFLINE:
        import time
        key = os.environ.get("THESPORTSDB_KEY", "123")
        for t in faltam[:8]:
            termo = busca.get(t) or unicodedata.normalize("NFD", t).encode("ascii", "ignore").decode()
            try:
                r = get_json(f"https://www.thesportsdb.com/api/v1/json/{key}/searchteams.php?t={urllib.parse.quote(termo)}")
                ts = [x for x in (r.get("teams") or []) if x.get("strSport") == "Soccer" and x.get("strBadge")]
                ts.sort(key=lambda x: x.get("strCountry") != "Brazil")
                salvos[t] = ts[0]["strBadge"].split("/badge/")[-1] if ts else ""
                log(f"Escudo de {t}: {salvos[t] or 'não achado'}")
            except Exception as e:
                log(f"Escudo de {t}: falhou ({e})")
            time.sleep(7)
        arq.write_text(json.dumps(salvos, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
    out = {}
    for t in times:
        if t in band:
            out[t] = FLAG.format(band[t])
        elif salvos.get(t):
            v = salvos[t]
            out[t] = v if v.startswith("http") else BADGE + v
        elif logos.get(t):
            out[t] = espn_logo(logos[t])
    return out


def logos_ligas(cfg):
    """Logo de cada campeonato (vem da ESPN com os jogos), guardado em dados/logos_ligas.json.
    Para tirar o logo de uma liga, ponha "" no lugar do endereço nesse arquivo."""
    arq = RAIZ / "dados" / "logos_ligas.json"
    salvos = ler(arq) if arq.exists() else {}
    novos = {k: v for k, v in LOGO_LIGA.items() if k not in salvos}
    if novos:
        salvos.update(novos)
        arq.write_text(json.dumps(salvos, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
    return {k: espn_logo(v) for k, v in salvos.items() if v and k in cfg["competicoes"]}


def gerar_site(dados):
    pub = (dados.get("anuncios") or {}).get("adsense_client", "").replace("ca-pub-", "pub-")
    ads = RAIZ / "site" / "ads.txt"
    if pub:
        ads.write_text(f"google.com, {pub}, DIRECT, f08c47fec0942fa0\n", encoding="utf-8")
    elif ads.exists():
        ads.unlink()
    tpl = (RAIZ / "site" / "template.html").read_text(encoding="utf-8")
    cli = (dados.get("anuncios") or {}).get("adsense_client", "")
    head = (f'<meta name="google-adsense-account" content="{cli}">\n'
            f'<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client={cli}" crossorigin="anonymous"></script>') if cli else ""
    tpl = tpl.replace("__ADSENSE_HEAD__", head)
    bloco = json.dumps(dados, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    (RAIZ / "site" / "index.html").write_text(tpl.replace("__DADOS__", bloco), encoding="utf-8")


def main():
    cfg = ler(RAIZ / "robo" / "config.json")
    verif = ler(RAIZ / "dados" / "verificados.json")["jogos"]
    hoje = datetime.now(BRT).date()
    dias = [(hoje + timedelta(days=i)).isoformat() for i in range(cfg["site"]["dias_a_frente"])]

    agora = datetime.now(BRT)
    if OFFLINE:
        api = [dict(v) for v in ler(CACHE).values()] if CACHE.exists() else []
    else:
        completo = "--completo" in sys.argv or not CACHE.exists() or agora.hour % 6 == 0
        api = espn(cfg, completo)
        if cfg["site"].get("usar_thesportsdb"):
            api += thesportsdb(cfg, dias)
            thesportsdb_tv(cfg, dias, api)
    api = aplicar_canais(cfg, api)
    if not OFFLINE:
        youtube(cfg, api + verif)
    logos = {}
    for j in api:
        j.pop("_liga", None)
        j.pop("_d", None)
        logos.update({k: v for k, v in (j.pop("_logos", None) or {}).items() if v})

    jogos = juntar(api, verif)
    anterior = RAIZ / "dados" / "jogos.json"
    if not jogos and anterior.exists():
        log("Nenhum jogo obtido; mantendo a agenda anterior para não apagar o site.")
        jogos = ler(anterior)["jogos"]

    aplicar_afiliado(cfg)
    dados = {
        "atualizado": datetime.now(BRT).isoformat(timespec="seconds"),
        "canais": cfg["canais"],
        "competicoes": {k: {x: v[x] for x in ("nome", "curto", "cor", "principal")} for k, v in cfg["competicoes"].items()},
        "jogos": jogos,
        "sugestoes": {k: v for k, v in cfg.get("sugestoes", {}).items() if k != "comentario"},
        "popularidade": {k: v for k, v in cfg.get("popularidade", {}).items() if k != "comentario"},
        "escudos": escudos(cfg, jogos, logos),
        "logos_ligas": logos_ligas(cfg),
        "anuncios": {k: v for k, v in cfg.get("anuncios", {}).items() if k != "comentario"},
    }
    anterior.write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8")
    gerar_site(dados)
    log(f"Pronto: {len(jogos)} jogos, site/index.html gerado.")


if __name__ == "__main__":
    main()
