"""Jogos por rodada, como no ge.

De onde vem cada coisa:
- número da rodada (pontos corridos, fase de liga e fase de grupos): TheSportsDB, consulta eventsround
  (grátis, chave "123", no máximo ~30 consultas por minuto). Tudo fica guardado em dados/rodadas.json e
  só se busca de novo o que pode ter mudado.
- fases de mata-mata (oitavas, quartas, semifinal...): a própria ESPN, que manda a fase em season.slug.
- nomes, horário certo, placar, canais e página do jogo: os jogos que o site já tem (agenda + histórico).
"""
import json
import time
import urllib.error
from datetime import datetime, timedelta, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
CACHE = RAIZ / "dados" / "rodadas.json"
BRT = timezone(timedelta(hours=-3))
UTC = timezone.utc

TSDB = "https://www.thesportsdb.com/api/v1/json/{}/{}"
ORCAMENTO = 30        # consultas à TheSportsDB por execução (a chave grátis também tem limite por hora)
ORCAMENTO_COMPLETO = 60
ESPACO = 3            # segundos entre consultas (limite grátis ~30 por minuto)

FIM = {"FT", "AET", "PEN", "AP", "MATCH FINISHED", "FINISHED", "AWARDED"}
ADIADO = {"PST", "POSTPONED", "MATCH POSTPONED", "CANC", "CANCELLED", "ABD", "ABANDONED", "SUSP", "SUSPENDED"}

# fases da ESPN que são "pontos corridos" (as rodadas dessas vêm da TheSportsDB)
CORRIDOS = ("regular-season", "league-phase", "group-stage", "groups", "torneo-apertura", "torneo-clausura",
            "apertura", "clausura", "season")
FASES = [  # (trecho do slug da ESPN, nome em português) — o primeiro que casar vale
    ("round-of-64", "32-avos de final"), ("round-of-32", "16-avos de final"), ("round-of-16", "Oitavas de final"),
    ("quarterfinal", "Quartas de final"), ("semifinal", "Semifinal"), ("third-place", "Disputa do 3º lugar"),
    ("3rd-place", "Disputa do 3º lugar"), ("final", "Final"),
    ("knockout-round-playoff", "Playoffs"), ("knockout-playoff", "Playoffs"), ("play-in", "Play-in"),
    ("preliminary", "Fase preliminar"), ("qualifying", "Fase preliminar"),
    ("first-round", "1ª fase"), ("second-round", "2ª fase"), ("third-round", "3ª fase"), ("fourth-round", "4ª fase"),
    ("fifth-round", "5ª fase"), ("sixth-round", "6ª fase"), ("round-one", "1ª fase"), ("round-two", "2ª fase"),
    ("round-three", "3ª fase"), ("conference-semifinal", "Semifinal de conferência"),
    ("conference-final", "Final de conferência"), ("playoff", "Playoffs"),
]


def log(*a):
    print("[rodadas]", *a, flush=True)


def ler():
    try:
        return json.loads(CACHE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _iso(d):
    return d.isoformat(timespec="minutes")


def _quando(s):
    try:
        return datetime.fromisoformat(s)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------- fases do mata-mata (ESPN)
def mata_mata(slug):
    """Nome da fase em português, ou None se o slug é de pontos corridos (ou não diz nada)."""
    s = (slug or "").lower()
    if not s:
        return None
    ultimo = s.split("---")[-1]
    if any(ultimo == c or ultimo.endswith(c) for c in CORRIDOS) or ultimo[:4].isdigit():
        return None
    for trecho, nome_pt in FASES:
        if trecho in ultimo:
            if "playoff" in s and not nome_pt.startswith("Playoff") and "conference" in s:
                return "Playoffs · " + nome_pt
            return nome_pt
    return None


# ---------------------------------------------------------------- TheSportsDB
class Tsdb:
    """Consultas à TheSportsDB com intervalo entre elas, uma nova tentativa e parada cedo quando o
    servidor está recusando (para não gastar a execução inteira esperando)."""

    def __init__(self, get_json, key, orcamento):
        self.get_json, self.key, self.resta = get_json, key, orcamento
        self.feitas = self.falhas = self.seguidas = 0
        self.motivos = {}

    def __call__(self, rota):
        if self.resta <= 0 or self.seguidas >= 4:
            return None
        self.resta -= 1
        for tentativa in range(2):
            if self.feitas:
                time.sleep(ESPACO if tentativa == 0 else 15)
            self.feitas += 1
            try:
                r = self.get_json(TSDB.format(self.key, rota))
                self.seguidas = 0
                return r
            except urllib.error.HTTPError as e:
                motivo = f"HTTP {e.code}"
                if e.code not in (429, 500, 502, 503):
                    break
            except Exception as e:
                motivo = type(e).__name__
        self.falhas += 1
        self.seguidas += 1
        self.motivos[motivo] = self.motivos.get(motivo, 0) + 1
        return None


def _evento(ev):
    ts = None
    hora = (ev.get("strTime") or "")[:8]
    if ev.get("strTimestamp"):
        ts = datetime.fromisoformat(ev["strTimestamp"].replace("Z", "")[:19]).replace(tzinfo=UTC)
    elif ev.get("dateEvent") and hora:
        ts = datetime.fromisoformat(f'{ev["dateEvent"]}T{hora}').replace(tzinfo=UTC)
    gol = lambda x: int(x) if str(x or "").strip().lstrip("-").isdigit() else None
    # "00:00:00" às vezes é meia-noite UTC de verdade (21h em Brasília) e às vezes é "sem horário":
    # só confia quando o jogo está perto (até 15 dias), que é quando os horários já saíram
    sem_hora = not hora or (hora == "00:00:00" and ts and ts > datetime.now(UTC) + timedelta(days=15))
    return {"id": str(ev.get("idEvent") or ""), "casa": ev.get("strHomeTeam") or "", "fora": ev.get("strAwayTeam") or "",
            "ts": _iso(ts) if ts else "", "hora": not sem_hora,
            "gc": gol(ev.get("intHomeScore")), "gf": gol(ev.get("intAwayScore")),
            "st": (ev.get("strStatus") or "").strip().upper(), "local": ev.get("strVenue") or ""}


def _agora_da(c, agora):
    """Rodada 'de agora' pelo que já está guardado: a que tem jogo por vir mais cedo."""
    melhor = None
    for n, r in (c.get("rodadas") or {}).items():
        datas = sorted(_quando(j["ts"]) for j in r["jogos"] if j["ts"] and j["st"] not in FIM | ADIADO)
        datas = [d for d in datas if d and d > agora - timedelta(days=4)]
        if datas and (melhor is None or datas[0] < melhor[1]):
            melhor = (int(n), datas[0])
    return melhor[0] if melhor else None


def buscar(cfg, get_json, jogos, completo=False, offline=False):
    """Atualiza dados/rodadas.json com o que falta ou pode ter mudado, dentro do orçamento de consultas."""
    cache = ler()
    if offline:
        return cache
    hoje = datetime.now(BRT).date().isoformat()
    proximos = {}  # campeonato -> dia (UTC) do próximo jogo que a ESPN já deu
    for j in sorted(jogos, key=lambda j: j["inicio"]):
        if j["inicio"][:10] >= hoje and not j.get("placar"):
            proximos.setdefault(j["comp"], _quando(j["inicio"]).astimezone(UTC).date().isoformat())
    import os
    api = Tsdb(get_json, os.environ.get("THESPORTSDB_KEY") or "123", ORCAMENTO_COMPLETO if completo else ORCAMENTO)
    agora = datetime.now(UTC)
    ligas = {k: v["tsdb_id"] for k, v in cfg["competicoes"].items() if v.get("tsdb_id")}
    cs = cache.setdefault("comps", {})
    for k in list(cs):
        if k not in ligas:
            del cs[k]

    # 1) temporada atual de cada liga (uma vez por semana)
    for k, lid in ligas.items():
        c = cs.setdefault(k, {"id": lid, "rodadas": {}})
        if c.get("id") != lid:
            cs[k] = c = {"id": lid, "rodadas": {}}
        velho = _quando(c.get("temporada_em", "")) or datetime(2000, 1, 1, tzinfo=UTC)
        if c.get("temporada") and agora - velho < timedelta(days=7):
            continue
        r = api(f"lookupleague.php?id={lid}")
        t = ((r or {}).get("leagues") or [{}])[0].get("strCurrentSeason")
        if t:
            if c.get("temporada") and t != c["temporada"]:
                log(k, "temporada nova:", t)
                c["rodadas"] = {}
                c.pop("ultima", None)
            c["temporada"], c["temporada_em"] = t, _iso(agora)

    # 2) lista do que buscar, por prioridade: rodada de agora e vizinhas; depois o que falta; depois o velho
    pedidos = []  # (prioridade, comp, rodada)
    for k, c in cs.items():
        if not c.get("temporada"):
            continue
        rods = c["rodadas"]
        atual = _agora_da(c, agora)
        if atual is None:
            # o que está guardado não diz qual é a rodada de agora: pergunta à TheSportsDB pelo próximo jogo
            # (pelo dia do próximo jogo que a ESPN já deu, ou pela lista de próximos jogos da liga)
            perguntou = _quando(c.get("perguntou_em", "")) or datetime(2000, 1, 1, tzinfo=UTC)
            if agora - perguntou < timedelta(hours=12) and c.get("atual"):
                atual = c["atual"]
            else:
                dia = proximos.get(k)
                r = api(f"eventsday.php?d={dia}&l={c['id']}" if dia else f"eventsnextleague.php?id={c['id']}")
                if r is None:
                    continue  # a consulta falhou: tenta na próxima execução, sem chutar a rodada
                ns = [int(e["intRound"]) for e in r.get("events") or [] if str(e.get("intRound") or "").isdigit()]
                ns = [n for n in ns if 0 < n < 100]
                atual = min(ns) if ns else max([int(n) for n in rods] or [1])
                c["perguntou_em"] = _iso(agora)
        c["atual"] = atual
        ultima = c.get("ultima")  # última rodada da temporada, quando já se sabe
        for n in range(1, (ultima or max([atual + 1] + [int(x) for x in rods])) + 1):
            r = rods.get(str(n))
            if not r:
                pedidos.append((0 if abs(n - atual) <= 1 else 2, abs(n - atual), k, n))
                continue
            em = _quando(r.get("em")) or datetime(2000, 1, 1, tzinfo=UTC)
            jogos = r["jogos"]
            acabou = jogos and all(j["st"] in FIM for j in jogos)
            if acabou:
                continue
            perto = abs(n - atual) <= 1
            adiado = any(j["st"] in ADIADO for j in jogos)
            idade = agora - em
            if (perto and idade > timedelta(hours=6)) or (adiado and idade > timedelta(days=1)) or idade > timedelta(days=3):
                pedidos.append((1 if perto else 3, abs(n - atual), k, n))
        if not ultima:  # ainda não se sabe onde a temporada acaba: testa a próxima depois da maior conhecida
            proxima = max([int(x) for x in rods] + [atual]) + 1
            if str(proxima) not in rods:
                pedidos.append((2, proxima - atual, k, proxima))
    menor = {}
    for p in pedidos:  # a mesma rodada pode ter entrado por dois motivos: vale a prioridade maior
        if (p[2], p[3]) not in menor or p < menor[(p[2], p[3])]:
            menor[(p[2], p[3])] = p
    pedidos = sorted(menor.values())

    novas = 0
    for _, _, k, n in pedidos:
        if api.resta <= 0:
            break
        c = cs[k]
        if c.get("ultima") and n > c["ultima"]:
            continue
        r = api(f"eventsround.php?id={c['id']}&r={n}&s={c['temporada']}")
        if r is None:
            continue
        evs = r.get("events") or []
        if not evs:
            if n > c.get("atual", 1):  # rodada vazia depois da atual: a temporada acaba na anterior
                c["ultima"] = n - 1 if not c.get("ultima") else min(c["ultima"], n - 1)
            continue
        c["rodadas"][str(n)] = {"em": _iso(agora), "jogos": [_evento(e) for e in evs]}
        novas += 1
    log(f"TheSportsDB: {api.feitas} consultas, {novas} rodadas atualizadas, {api.falhas} falhas {api.motivos or ''}, "
        f"{len(pedidos) - novas} pedidos para as próximas execuções")
    return cache


def gravar(cache):
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(cache, ensure_ascii=False, separators=(",", ":"), sort_keys=True), encoding="utf-8")


# ---------------------------------------------------------------- nomes da TheSportsDB -> nomes do site
def _norm(s, norm):
    return norm(s).replace("atletico", "atl").replace("athletico", "athl")


class Nomes:
    """Traduz o nome da TheSportsDB para o nome que o site usa. Aprende pelos jogos que batem em data
    e adversário, e guarda o que aprendeu em dados/rodadas.json para as rodadas futuras."""

    def __init__(self, conhecidos, aprendidos, norm, acentua):
        self.conh, self.apr, self.norm, self.acentua = set(conhecidos), aprendidos, norm, acentua
        self.por_norm = {}
        for t in self.conh:
            self.por_norm.setdefault(_norm(t, norm), t)

    def certo(self, nm):
        if nm in self.apr:
            return self.apr[nm]
        if nm in self.conh:
            return nm
        return self.por_norm.get(_norm(nm, self.norm))

    def palpite(self, nm):
        """Quando não há certeza: mesmo primeiro nome e só um time assim no campeonato."""
        a = _norm(nm, self.norm).split()
        if not a:
            return None
        cands = [t for t in self.conh if _norm(t, self.norm).split()[:1] == a[:1]]
        if len(cands) == 1:
            return cands[0]
        toks = set(a)
        melhor = sorted(((len(toks & set(_norm(t, self.norm).split())), t) for t in self.conh), reverse=True)
        if melhor and melhor[0][0] >= 2 and (len(melhor) == 1 or melhor[1][0] < melhor[0][0]):
            return melhor[0][1]
        return None

    def final(self, nm):
        return self.certo(nm) or self.palpite(nm) or self.acentua(nm)


def _casar(ev, por_dia, nomes):
    """Acha o jogo do site que é este jogo da TheSportsDB (mesmo dia ±1 e um dos times igual)."""
    ts = _quando(ev["ts"])
    if not ts:
        return None
    c, f = nomes.certo(ev["casa"]), nomes.certo(ev["fora"])
    for d in (0, -1, 1):
        dia = (ts.astimezone(BRT) + timedelta(days=d)).date().isoformat()
        for j in por_dia.get(dia, []):
            if abs((_quando(j["inicio"]) - ts).total_seconds()) > 36 * 3600:
                continue
            if (c and j["casa"] == c) or (f and j["fora"] == f) or (c and f and {c, f} == {j["casa"], j["fora"]}):
                return j
    return None


# ---------------------------------------------------------------- montagem do que o site mostra
def _jogo_site(j):
    """Um jogo no formato das rodadas, a partir de um jogo da agenda ou do histórico."""
    o = {"casa": j["casa"], "fora": j["fora"], "inicio": j["inicio"], "hora": True}
    if j.get("placar"):
        o["placar"] = [j["placar"]["casa"], j["placar"]["fora"]]
        o["st"] = "fim"
        if j.get("pen"):
            o["pen"] = j["pen"]
    if (j.get("nota") or "") in ("Adiado", "Cancelado"):
        o["st"] = "adiado"
    for x in ("eid", "lg", "ed", "local", "canais", "links"):
        if j.get(x):
            o[x] = j[x]
    if j.get("fase"):
        o["_fase"] = j["fase"]
    return o


def _resumo_datas(jogos):
    ds = sorted(_quando(j["inicio"]).astimezone(BRT).date() for j in jogos if j.get("inicio"))
    return (ds[0].isoformat(), ds[-1].isoformat()) if ds else ("", "")


def montar(cfg, cache, jogos, hist, tabs, norm, acentua):
    """Para cada campeonato: lista de rodadas/fases já com os jogos do site. {comp: {"atual": i, "rodadas": [...]}}"""
    agora = datetime.now(UTC)
    aprendidos = cache.setdefault("nomes", {})
    site = {}  # comp -> jogos do site (agenda vale mais que o histórico)
    for eid, x in (hist.get("jogos") or {}).items():
        site.setdefault(x["comp"], {})[(x["inicio"][:10], x["casa"], x["fora"])] = _jogo_site({"eid": eid, **x})
    for j in jogos:
        if "A definir" in (j["casa"], j["fora"]):
            continue
        site.setdefault(j["comp"], {})[(j["inicio"][:10], j["casa"], j["fora"])] = _jogo_site(j)
    out = {}
    for k, c in cfg["competicoes"].items():
        meus = list((site.get(k) or {}).values())
        grupos = []
        # pontos corridos / fase de liga: rodadas da TheSportsDB
        tc = ((cache.get("comps") or {}).get(k) or {})
        # só mostra as rodadas quando a de agora já chegou (antes disso a página continua por data)
        if tc.get("rodadas") and str(tc.get("atual")) in tc["rodadas"]:
            conhecidos = {j["casa"] for j in meus} | {j["fora"] for j in meus}
            for g in (tabs.get(k) or {}).get("grupos", []):
                conhecidos |= {l["time"] for l in g["linhas"]}
            apr = aprendidos.setdefault(k, {})
            nomes = Nomes(conhecidos, apr, norm, acentua)
            por_dia = {}
            for j in meus:
                por_dia.setdefault(_quando(j["inicio"]).astimezone(BRT).date().isoformat(), []).append(j)
            # duas passadas: a primeira aprende nomes pelos jogos que batem; a segunda já usa o que aprendeu
            for _ in range(2):
                for n in sorted(tc["rodadas"], key=int):
                    for ev in tc["rodadas"][n]["jogos"]:
                        j = _casar(ev, por_dia, nomes)
                        if j:
                            for de, para in ((ev["casa"], j["casa"]), (ev["fora"], j["fora"])):
                                if de and de not in apr and de != para:
                                    apr[de] = para
            rotulo = c.get("rotulo_rodada", "")
            for n in sorted(tc["rodadas"], key=int):
                lista = []
                for ev in tc["rodadas"][n]["jogos"]:
                    j = _casar(ev, por_dia, nomes)
                    if j:
                        o = dict(j)
                        if ev["st"] in ADIADO and not j.get("placar"):
                            o["st"] = "adiado"
                    else:
                        o = {"casa": nomes.final(ev["casa"]), "fora": nomes.final(ev["fora"]),
                             "inicio": _iso(_quando(ev["ts"]).astimezone(BRT)) if ev["ts"] else "", "hora": ev["hora"]}
                        if ev["local"]:
                            o["local"] = acentua(ev["local"])
                        if ev["st"] in FIM and ev["gc"] is not None and ev["gf"] is not None:
                            o["placar"], o["st"] = [ev["gc"], ev["gf"]], "fim"
                        elif ev["st"] in ADIADO:
                            o["st"] = "adiado"
                    lista.append(o)
                nome_r = f"{int(n)}ª rodada"
                grupos.append({"tipo": "r", "n": int(n), "nome": f"{rotulo} · {nome_r}" if rotulo else nome_r, "jogos": lista})
        # mata-mata: fases que a ESPN informa
        fases = {}
        for j in meus:
            f = mata_mata(j.get("_fase"))
            if f:
                fases.setdefault(f, []).append(j)
        for f, js in fases.items():
            grupos.append({"tipo": "f", "nome": f, "jogos": js})
        if not grupos:
            continue
        # ordem: rodadas pelo número; fases pela data; e cada fase depois das rodadas que acontecem antes dela
        for g in grupos:
            g["jogos"].sort(key=lambda j: (j.get("inicio") or "9999", j["casa"]))
            g["de"], g["ate"] = _resumo_datas(g["jogos"])
        rods = sorted([g for g in grupos if g["tipo"] == "r"], key=lambda g: g["n"])
        fs = sorted([g for g in grupos if g["tipo"] == "f"], key=lambda g: g["de"] or "9999")
        ordem = rods + fs if (not rods or not fs or fs[0]["de"] >= (rods[-1]["de"] or "")) else \
            sorted(grupos, key=lambda g: g["de"] or "9999")
        out[k] = {"rodadas": ordem, "atual": _escolher(ordem, agora)}
    return out


def _escolher(grupos, agora):
    """Abre na rodada em andamento ou na próxima (a de jogo por vir mais cedo; sobra adiada não conta)."""
    melhor = None
    for i, g in enumerate(grupos):
        ds = sorted(_quando(j["inicio"]) for j in g["jogos"] if j.get("inicio"))
        if not ds:
            continue
        meio = ds[len(ds) // 2]
        pend = [j for j in g["jogos"] if j.get("st") not in ("fim", "adiado") and j.get("inicio")]
        if pend and meio > agora - timedelta(days=5):
            if melhor is None or meio < melhor[1]:
                melhor = (i, meio)
    if melhor:
        return melhor[0]
    passadas = [i for i, g in enumerate(grupos) if g["de"] and g["de"] <= agora.astimezone(BRT).date().isoformat()]
    return passadas[-1] if passadas else 0
