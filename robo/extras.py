"""Dados extras da ESPN (sem chave): tabelas dos campeonatos, histórico de resultados e escalações oficiais.

Grava:
  dados/tabelas.json      classificação de cada campeonato (atualizada a cada rodada do robô)
  dados/historico.json    resultados dos últimos meses (para "últimos jogos" e "como chegam")
  dados/escalacoes.json   escalações oficiais (saem ~1h antes do jogo)
  site/dados/camp-<id>.json  tabela + últimos resultados de cada campeonato, para as abas da página inicial
"""
import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
BRT = timezone(timedelta(hours=-3))
TABELAS = RAIZ / "dados" / "tabelas.json"
HIST = RAIZ / "dados" / "historico.json"
ESCAL = RAIZ / "dados" / "escalacoes.json"
SAIDA = RAIZ / "site" / "dados"
STANDINGS = "https://site.api.espn.com/apis/v2/sports/soccer/{}/standings"
SCOREBOARD = "https://site.api.espn.com/apis/site/v2/sports/soccer/{}/scoreboard?dates={}"
SUMMARY = "https://site.web.api.espn.com/apis/site/v2/sports/soccer/{}/summary?event={}&region=br&lang=en"  # siglas em inglês (CD-R, DM, AM-L...): dizem a linha e o lado de cada jogador
DIAS_HIST = 75          # quanto do passado buscar (preenchido aos poucos)
GUARDA_HIST = 200       # quanto guardar
CONSULTAS_POR_RODADA = 4000


def log(*a):
    print("[extras]", *a, flush=True)


def ler(p, padrao):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:
        return padrao


def grava(p, obj, compacto=False):
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    Path(p).write_text(json.dumps(obj, ensure_ascii=False, indent=None if compacto else 1,
                                  separators=(",", ":") if compacto else None, sort_keys=not compacto), encoding="utf-8")


def ligas(cfg):
    for comp, c in cfg["competicoes"].items():
        ls = c.get("espn") or []
        for liga in ([ls] if isinstance(ls, str) else ls):
            yield comp, c, liga


# ---------------------------------------------------------------- tabelas
def _n(s):
    import re
    import unicodedata
    s = unicodedata.normalize("NFD", str(s)).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"\b(fc|ec|sc|cf|afc|club|clube|de|futebol|esporte|sport)\b", " ", s)
    return " ".join(re.sub(r"[^a-z0-9]+", " ", s).split())


def _nome_tabela(cfg, nome, comp, t, conhecidos):
    """A tabela da ESPN às vezes usa outro nome que o placar ("Athletico Paranaense" x "Athletico-PR").
    Usa o nome que o site já conhece para esse time."""
    cands = [nome(cfg, t[k], comp) for k in ("displayName", "shortDisplayName", "name", "location") if t.get(k)]
    for c in cands:
        if c in conhecidos:
            return c
    idx = {_n(k): k for k in conhecidos}
    for c in cands:
        if _n(c) in idx:
            return idx[_n(c)]
    for c in cands:  # mesma primeira palavra, e só um time conhecido com ela: "Athletico Paranaense" ~ "Athletico-PR"
        a = _n(c).split()
        if not a or len(a[0]) < 6:
            continue
        iguais = [v for k, v in idx.items() if k.split()[:1] == a[:1]]
        if len(iguais) == 1:
            return iguais[0]
    return cands[0] if cands else "?"


# ---------------------------------------------------------------- faixas da tabela (vagas, acesso, queda)
# Paleta única do site, para a mesma ideia ter a mesma cor em qualquer campeonato.
AZUL, AZUL_CL, LARANJA, VERDE, VERDE_CL, ROSA, VERMELHO, CINZA = (
    "#1d5fd1", "#6aa5f0", "#f08a1c", "#12924f", "#6cc795", "#f39aa2", "#d7263d", "#a7b0bb")
# (trecho em inglês que a ESPN manda, nome em português, cor) — o primeiro que casar vale
FAIXAS_ESPN = [
    ("relegation playoff", "Playoff de rebaixamento", ROSA),
    ("relegation", "Rebaixamento", VERMELHO),
    ("relegated", "Rebaixamento", VERMELHO),
    ("promotion playoff", "Playoff de acesso", VERDE_CL),
    ("promotion", "Acesso", VERDE),
    ("champions league qualifying", "Pré-Champions", AZUL_CL),
    ("champions league", "Champions League", AZUL),
    ("europa league qualifying", "Pré-Europa League", LARANJA),
    ("europa league", "Europa League", LARANJA),
    ("conference league qualifying", "Pré-Conference League", VERDE_CL),
    ("conference league", "Conference League", VERDE),
    ("sudamericana", "Playoff da Sul-Americana", LARANJA),
    ("seeded", "Playoff das oitavas (cabeça de chave)", AZUL_CL),
    ("knockout phase playoffs", "Playoff das oitavas", "#9cc3f5"),
    ("ko playoffs", "Playoff das oitavas", AZUL_CL),
    ("best 3rd", "Melhores 3ºs avançam", AZUL_CL),
    ("round of 16", "Oitavas de final", AZUL),
    ("qfs", "Quartas de final", AZUL),
    ("wild card", "Playoffs (repescagem)", AZUL_CL),
    ("playoffs", "Playoffs", AZUL),
    ("eliminated", "Eliminado", CINZA),
]


def faixa_espn(desc, cor=""):
    d = (desc or "").lower()
    if d.startswith("a: qualifies for qfs; b-d: promotion playoffs"):
        return "Quartas (Liga A) / playoff de acesso", AZUL_CL
    for trecho, nome_pt, c in FAIXAS_ESPN:
        if trecho in d:
            if trecho == "seeded" and "unseeded" in d:
                continue
            return nome_pt, c
    return desc, "#" + (cor or "").lstrip("#") if cor else CINZA


def tabelas(cfg, nome, get_json, logo=lambda u: u, conhecidos=()):
    """Classificação de cada campeonato (pontos corridos e fases de grupos)."""
    conhecidos = set(conhecidos)
    conhecidos_comp = {}
    out = ler(TABELAS, {})
    novas = 0
    for comp, c, liga in ligas(cfg):
        try:
            r = get_json(STANDINGS.format(liga))
        except Exception as e:
            log("tabela falhou:", liga, e)
            continue
        grupos = []
        filhos = r.get("children") or ([r] if r.get("standings") else [])
        for ch in filhos:
            linhas = []
            for en in (ch.get("standings") or {}).get("entries") or []:
                st = {s.get("name"): s for s in en.get("stats") or []}
                v = lambda k: int(round(float((st.get(k) or {}).get("value") or 0)))
                t = en.get("team") or {}
                nota = en.get("note") or {}
                lg_ = ((t.get("logos") or [{}])[0] or {}).get("href", "")
                linhas.append({
                    "pos": v("rank") or len(linhas) + 1, "time": _nome_tabela(cfg, nome, comp, t, conhecidos_comp.get(comp, conhecidos)),
                    "pj": v("gamesPlayed"), "v": v("wins"), "e": v("ties"), "d": v("losses"),
                    "gp": v("pointsFor"), "gc": v("pointsAgainst"), "sg": v("pointDifferential"), "pts": v("points"),
                    **(dict(zip(("zona", "cor"), faixa_espn(nota["description"], nota.get("color")))) if nota.get("description") else {}),
                    **({"esc": logo(lg_)} if lg_ else {}),
                    **({"tid": str(t["id"])} if t.get("id") else {}),  # id da ESPN: liga a linha ao placar ao vivo
                })
            if linhas:
                linhas.sort(key=lambda x: x["pos"])
                grupos.append({"nome": ch.get("name") or ch.get("abbreviation") or "", "linhas": linhas, "lg": liga})
        if grupos:
            if len(grupos) == 1:
                grupos[0]["nome"] = ""
            ant = out.get(comp, {})
            # campeonato com mais de um código na ESPN (ex.: Eurocopa + eliminatórias): fica a que tem grupos agora
            if ant.get("liga") and ant.get("liga") != liga and ant.get("_rodada") == RODADA:
                grupos = ant["grupos"] + grupos
            temporada = str((r.get("season") or {}).get("displayName") or (r.get("season") or {}).get("year") or "")
            zonas = [z for z in (cfg.get("zonas", {}).get(comp) or []) if isinstance(z, dict)]
            for g in grupos:
                for l in g["linhas"]:
                    if zonas:  # faixas do regulamento substituem as da ESPN
                        l.pop("zona", None); l.pop("cor", None)
                    for z in zonas:
                        if z["de"] <= l["pos"] <= z["ate"]:
                            l["zona"], l["cor"] = z["nome"], z["cor"]
            obs = (cfg.get("zonas_obs") or {}).get(comp)
            out[comp] = {"grupos": grupos, "liga": liga, "temporada": temporada, **({"obs": obs} if obs else {}),
                         "atualizado": datetime.now(BRT).isoformat(timespec="minutes"), "_rodada": RODADA}
            novas += 1
        time.sleep(0.2)
    grava(TABELAS, out)
    log(f"tabelas: {novas} campeonatos")
    return out


RODADA = datetime.now(BRT).strftime("%Y%m%d%H")


# ---------------------------------------------------------------- histórico de resultados
def lances(cp, tm):
    """Gols e expulsões do jogo, na ordem: [{"l": "c"/"f", "m": "28'", "n": "Pedro Lima", "k": "g"/"p"/"c"/"v"}].
    k: g = gol, p = gol de pênalti, c = gol contra, v = cartão vermelho. A ESPN manda isso no placar, de graça."""
    lado = {str(x["team"]["id"]): ("c" if h == "home" else "f") for h, x in tm.items() if (x.get("team") or {}).get("id")}
    out = []
    for d in cp.get("details") or []:
        tipo = ((d.get("type") or {}).get("text") or "").lower()
        if "shootout" in tipo:  # cobranças da disputa de pênaltis não são gols do jogo
            continue
        if d.get("scoringPlay"):
            k = "c" if d.get("ownGoal") else "p" if d.get("penaltyKick") else "g"
        elif "red" in tipo:
            k = "v"
        else:
            continue
        l = lado.get(str((d.get("team") or {}).get("id")))
        if not l:
            continue
        ats = d.get("athletesInvolved") or []
        n = (ats[0].get("shortName") or ats[0].get("displayName") or "") if ats else ""
        m = ((d.get("clock") or {}).get("displayValue") or "").replace("'+", "+").rstrip("'")
        out.append({"l": l, "m": m + "'" if m else "", "n": n, "k": k})
    return out


def _resultado(cfg, nome, comp, liga, ev):
    try:
        cp = ev["competitions"][0]
        st = (ev.get("status") or cp.get("status") or {}).get("type") or {}
        if not st.get("completed") or "CANCEL" in st.get("name", "") or "POSTPON" in st.get("name", ""):
            return None
        tm = {x["homeAway"]: x for x in cp["competitors"]}
        ini = datetime.fromisoformat(ev["date"].replace("Z", "+00:00")).astimezone(BRT)
        v = cp.get("venue") or ev.get("venue") or {}
        fase = (ev.get("season") or {}).get("slug") or ""
        r = {"inicio": ini.isoformat(), "comp": comp, "lg": liga, **({"fase": fase} if fase else {}),
             **({"local": ", ".join(x for x in (v.get("fullName"), (v.get("address") or {}).get("city")) if x)} if v.get("fullName") else {}),
             "casa": nome(cfg, tm["home"]["team"]["displayName"], comp), "fora": nome(cfg, tm["away"]["team"]["displayName"], comp),
             "placar": {"casa": int(tm["home"]["score"]), "fora": int(tm["away"]["score"])}}
        pen = [tm[x].get("shootoutScore") for x in ("home", "away")]
        if all(p is not None for p in pen):
            r["pen"] = [int(pen[0]), int(pen[1])]
        ls = lances(cp, tm)
        if ls:
            r["lances"] = ls
        return r
    except (KeyError, ValueError, TypeError, IndexError):
        return None


def historico(cfg, nome, get_json, jogos, offline=False):
    h = ler(HIST, {"jogos": {}, "feitos": []})
    if h.get("v") != 2:  # versão 2 guarda a fase (oitavas, quartas...): busca o passado de novo uma vez
        h["feitos"], h["v"] = [], 2
    feitos = set(h.get("feitos", []))
    # 1) o que já está na agenda e terminou
    for j in jogos:
        if j.get("placar") and j.get("eid"):
            h["jogos"][j["eid"]] = {k: j[k] for k in ("inicio", "comp", "casa", "fora", "placar", "fase", "local", "lances") if j.get(k)} | \
                ({"lg": j["lg"]} if j.get("lg") else {})
    # 2) busca o passado aos poucos (mais recente primeiro)
    if not offline:
        hoje = datetime.now(BRT).date()
        pend = []
        for i in range(2, DIAS_HIST + 1):
            d = (hoje - timedelta(days=i)).strftime("%Y%m%d")
            for comp, c, liga in ligas(cfg):
                if f"{liga}:{d}" not in feitos:
                    pend.append((comp, liga, d))
        # busca em paralelo (8 de cada vez): o histórico inteiro sai numa rodada só
        from concurrent.futures import ThreadPoolExecutor

        def busca(item):
            comp, liga, d = item
            try:
                return item, get_json(SCOREBOARD.format(liga, d))
            except Exception as e:
                log("histórico falhou:", liga, d, e)
                return item, None

        n = 0
        with ThreadPoolExecutor(max_workers=8) as ex:
            for (comp, liga, d), r in ex.map(busca, pend[:CONSULTAS_POR_RODADA]):
                if r is None:
                    continue  # tenta de novo na próxima rodada
                for ev in r.get("events") or []:
                    x = _resultado(cfg, nome, comp, liga, ev)
                    if x:
                        h["jogos"][str(ev.get("id"))] = x
                feitos.add(f"{liga}:{d}")
                n += 1
        log(f"histórico: {n} dias consultados, faltam {max(0, len(pend) - n)}")
    corte = (datetime.now(BRT) - timedelta(days=GUARDA_HIST)).isoformat()
    h["jogos"] = {k: v for k, v in h["jogos"].items() if v["inicio"] >= corte}
    limite = (datetime.now(BRT).date() - timedelta(days=DIAS_HIST + 2)).strftime("%Y%m%d")
    h["feitos"] = sorted(f for f in feitos if f.split(":")[-1] >= limite)
    grava(HIST, h)
    return h


# ---------------------------------------------------------------- escalações oficiais
ESTAT = {"totalGoals": "g", "goalAssists": "a", "totalShots": "ch", "shotsOnTarget": "cg", "foulsCommitted": "fc",
         "foulsSuffered": "fs", "offsides": "imp", "yellowCards": "am", "redCards": "vm", "saves": "df",
         "goalsConceded": "gs", "ownGoals": "gc"}


def _minuto_sub(p, ultimo=False):
    m = [x.get("clock", {}).get("displayValue", "") for x in p.get("plays") or [] if x.get("substitution")]
    m = [x for x in m if x]
    return (m[-1] if ultimo else m[0]) if m else ""


def _lado(r):
    """Titulares e reservas de um time, com quem entrou/saiu (minuto) e os números de cada jogador na partida.
    O mesmo formato é montado pelo p.js quando o navegador busca na ESPN (jogo ao vivo)."""
    titulares, reservas = [], []
    for p in r.get("roster") or []:
        a = p.get("athlete") or {}
        pos = (p.get("position") or {}).get("abbreviation") or ""
        item = {"n": str(p.get("jersey") or ""), "nome": a.get("shortName") or a.get("displayName") or "?", "pos": pos}
        if a.get("id"):
            item["id"] = str(a["id"])
        if p.get("formationPlace"):
            item["fp"] = int(p["formationPlace"])
        if p.get("subbedIn"):
            item["e"] = _minuto_sub(p) or "?"
        if p.get("subbedOut"):
            item["s"] = _minuto_sub(p, ultimo=True) or "?"
        st = {}
        for x in p.get("stats") or []:
            k = ESTAT.get(x.get("name"))
            try:
                v = int(float(x.get("value") or 0))
            except (TypeError, ValueError):
                v = 0
            if k and v and not (k == "gs" and pos not in ("G", "GK")):
                st[k] = v
        if st:
            item["st"] = st
        (titulares if p.get("starter") else reservas).append(item)
    titulares.sort(key=lambda x: x.get("fp", 99))
    out = {"titulares": titulares, "reservas": reservas}
    f = r.get("formation")
    if isinstance(f, dict):
        f = f.get("summary") or f.get("name")
    if f:
        out["esquema"] = str(f)
    return out


def _substituicoes(resumo):
    """[{"l": "c"/"f", "m": "63'", "ent": nome, "sai": nome}] pela ordem do jogo (keyEvents da ESPN)."""
    nomes, lado_time = {}, {}
    for ros in resumo.get("rosters") or []:
        lado_time[str((ros.get("team") or {}).get("id"))] = "c" if ros.get("homeAway") == "home" else "f"
        for p in ros.get("roster") or []:
            a = p.get("athlete") or {}
            if a.get("id"):
                nomes[str(a["id"])] = a.get("shortName") or a.get("displayName") or "?"
    out = []
    for k in resumo.get("keyEvents") or []:
        if "substitution" not in str((k.get("type") or {}).get("text", "")).lower():
            continue
        ps = [x.get("athlete") or {} for x in k.get("participants") or []]
        if len(ps) < 2:
            continue
        nm = lambda a: nomes.get(str(a.get("id")), a.get("shortName") or a.get("displayName") or "?")
        out.append({"l": lado_time.get(str((k.get("team") or {}).get("id")), ""), "m": (k.get("clock") or {}).get("displayValue", ""),
                    "ent": nm(ps[0]), "sai": nm(ps[1])})
    return out


def escalacoes(cfg, get_json, jogos, offline=False):
    e = ler(ESCAL, {})
    agora = datetime.now(BRT)
    if not offline:
        alvo = []
        for j in jogos:
            if not (j.get("eid") and j.get("lg")) or j["eid"] in e and e[j["eid"]].get("completa") and e[j["eid"]].get("v") == 3:
                continue
            ini = datetime.fromisoformat(j["inicio"]).astimezone(BRT)
            # de 2h30 antes do jogo até 2 dias depois: se o robô não rodou na hora (o agendador grátis
            # do GitHub atrasa), a escalação ainda é buscada depois, porque a ESPN guarda a do jogo
            if -timedelta(days=2) <= ini - agora <= timedelta(hours=2, minutes=30):
                alvo.append(j)
        alvo.sort(key=lambda j: abs((datetime.fromisoformat(j["inicio"]).astimezone(BRT) - agora).total_seconds()))
        for j in alvo[:40]:
            try:
                r = get_json(SUMMARY.format(j["lg"], j["eid"]), timeout=30)
            except Exception as ex:
                log("escalação falhou:", j["casa"], j["fora"], ex)
                continue
            lados = {x.get("homeAway"): x for x in r.get("rosters") or []}
            if not all(len((lados.get(k) or {}).get("roster") or []) >= 11 for k in ("home", "away")):
                continue
            casa, fora = _lado(lados["home"]), _lado(lados["away"])
            if len(casa["titulares"]) >= 11 and len(fora["titulares"]) >= 11:
                ini = datetime.fromisoformat(j["inicio"]).astimezone(BRT)
                # "completa" só depois do fim do jogo: até lá, substituições e números dos jogadores mudam
                e[j["eid"]] = {"casa": casa, "fora": fora, "subs": _substituicoes(r), "inicio": j["inicio"],
                               "time_casa": j["casa"], "time_fora": j["fora"], "comp": j["comp"], "pg": j.get("pg", ""),
                               "achada": (e.get(j["eid"]) or {}).get("achada") or agora.isoformat(timespec="minutes"),
                               "atualizada": agora.isoformat(timespec="minutes"),
                               "completa": agora > ini + timedelta(hours=3), "v": 3}
            time.sleep(0.3)
    corte = (agora - timedelta(days=4)).isoformat()
    e = {k: v for k, v in e.items() if v["inicio"] >= corte}
    grava(ESCAL, e)
    log(f"escalações: {len(e)} guardadas")
    return e


# ---------------------------------------------------------------- arquivos das abas (página inicial)
def ativos(jogos, hist, dias=45):
    """Campeonatos em andamento: com jogo na agenda ou resultado recente (evita mostrar tabela de edição antiga)."""
    corte = (datetime.now(BRT) - timedelta(days=dias)).isoformat()
    a = {j["comp"] for j in jogos}
    a |= {x["comp"] for x in hist["jogos"].values() if x["inicio"] >= corte}
    return a


def arquivos_site(comps, tabs, hist, ativos_=None, rodadas=None):
    SAIDA.mkdir(parents=True, exist_ok=True)
    if ativos_ is not None:
        tabs = {k: v for k, v in tabs.items() if k in ativos_}
    por_comp = {}
    for x in hist["jogos"].values():
        por_comp.setdefault(x["comp"], []).append(x)
    feitos = set()
    for comp in comps:
        t = (tabs.get(comp) or {}).get("grupos") or []
        res = sorted(por_comp.get(comp, []), key=lambda x: x["inicio"], reverse=True)[:40]
        if not t and not res:
            continue
        grava(SAIDA / f"camp-{comp}.json", {"tabela": t, "temporada": (tabs.get(comp) or {}).get("temporada", ""), "atualizado": (tabs.get(comp) or {}).get("atualizado", ""), **({"obs": tabs[comp]["obs"]} if (tabs.get(comp) or {}).get("obs") else {}), "resultados": [{k: r[k] for k in ("inicio", "casa", "fora", "placar") if k in r} |
                                                                         ({"pen": r["pen"]} if r.get("pen") else {}) for r in res]}, compacto=True)
        feitos.add(f"camp-{comp}.json")
    out = _limpa(feitos, tabs, por_comp)
    for c in rodadas or {}:  # "d" = jogos por rodada (arquivo rod-<comp>.json, feito em paginas.py)
        out[c] = out.get(c, "") + "d"
    return out


def _limpa(feitos, tabs, por_comp):
    """Apaga arquivos de campeonatos sem dados e devolve, para a página inicial, quais abas cada um tem
    ("t" = tabela, "r" = resultados)."""
    for f in SAIDA.glob("camp-*.json"):
        if f.name not in feitos:
            f.unlink()
    out = {}
    for f in sorted(feitos):
        c = f[5:-5]
        out[c] = ("t" if (tabs.get(c) or {}).get("grupos") else "") + ("r" if por_comp.get(c) else "")
    return out


# ---------------------------------------------------------------- consultas para as páginas
def ultimos(hist, time_, n=5, antes=None):
    js = [x for x in hist["jogos"].values() if time_ in (x["casa"], x["fora"]) and (antes is None or x["inicio"] < antes)]
    return sorted(js, key=lambda x: x["inicio"], reverse=True)[:n]


def resultado_para(time_, x):
    a, b = (x["placar"]["casa"], x["placar"]["fora"]) if x["casa"] == time_ else (x["placar"]["fora"], x["placar"]["casa"])
    if a == b and x.get("pen"):
        pa, pb = x["pen"] if x["casa"] == time_ else x["pen"][::-1]
        return "V" if pa > pb else "D"
    return "V" if a > b else "E" if a == b else "D"


def confrontos(hist, a, b, n=3):
    js = [x for x in hist["jogos"].values() if {x["casa"], x["fora"]} == {a, b}]
    return sorted(js, key=lambda x: x["inicio"], reverse=True)[:n]


def posicao(tabs, comp, time_):
    for g in (tabs.get(comp) or {}).get("grupos") or []:
        for l in g["linhas"]:
            if l["time"] == time_:
                return l, g
    return None, None
