"""Palpites: probabilidade de cada resultado, calculada pelo próprio site com um modelo estatístico simples e aberto.

Como funciona (modelo de Poisson, o mesmo princípio usado em análises de futebol desde os anos 1980):
- A força de ataque de um time é a média de gols que ele marca por jogo no campeonato, comparada com a média
  da liga; a força de defesa é a média de gols que ele sofre. Os dois números vêm da tabela da temporada (ESPN)
  e são puxados um pouco para a média da liga ("N0" jogos imaginários na média), para não exagerar com pouco jogo.
- Gols esperados: mandante = média de gols do mandante na liga x ataque do mandante x defesa do visitante;
  visitante = média do visitante na liga x ataque do visitante x defesa do mandante. A vantagem de jogar em casa
  sai do próprio histórico do campeonato.
- Os gols de cada time seguem uma distribuição de Poisson; a correção de Dixon e Coles (RHO) ajusta os placares
  baixos (0 x 0, 1 x 0, 0 x 1, 1 x 1), que a Poisson pura erra um pouco.
- Os parâmetros foram escolhidos testando o modelo nos jogos já disputados, sempre só com o que se sabia antes de
  cada jogo (rode `python3 robo/palpites.py --validar` para ver os números).

O palpite de cada jogo fica congelado em dados/palpites.json na última atualização antes do apito inicial; depois
do jogo, a página mostra se ele acertou. Nada disso é garantia de resultado: é estatística.

Espaço de apostas: desligado por padrão (robo/config.json -> "apostas"). Só liga com operadora autorizada pela
Secretaria de Prêmios e Apostas (domínio .bet.br e número da portaria de autorização), e sempre com os avisos da
Portaria SPA/MF nº 1.231/2024 (art. 13 e 15, com a redação da Portaria SPA/MF nº 1.964/2026).
"""
import json
import math
import sys
import urllib.parse
from datetime import datetime, timedelta, timezone
from html import escape
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ARQ = RAIZ / "dados" / "palpites.json"
CONFIG = RAIZ / "robo" / "config.json"
BRT = timezone(timedelta(hours=-3))

# parâmetros do modelo (escolhidos com --validar; ver o docstring)
N0 = 4            # jogos "imaginários" na média da liga somados a cada time
RHO = 0.0        # correção de Dixon e Coles para placares baixos (a validação não mostrou ganho: fica em 0)
CASA_PADRAO = 1.25  # mandante / visitante, quando o campeonato ainda tem pouco histórico
MIN_JOGOS_TIME = 5     # cada time precisa de pelo menos isso de jogos na temporada
MIN_JOGOS_COMP = 40    # e o campeonato, de jogos no histórico do site
GUARDA_DIAS = 60
MAX_GOLS = 10

# links oficiais (gov.br) para jogo responsável
JOGO_RESPONSAVEL = "https://www.gov.br/fazenda/pt-br/composicao/orgaos/secretaria-de-premios-e-apostas/jogo-responsavel"
AUTOEXCLUSAO = "https://www.gov.br/bets/autoexclusao"
AUTORIZADAS = "https://www.gov.br/pt-br/servicos/consultar-as-empresas-autorizadas-a-operar-apostas-de-quota-fixa"
# Portaria SPA/MF nº 1.964/2026: uma destas frases em toda peça publicitária de apostas
ADVERTENCIAS = ["Ministério da Fazenda adverte: Aposta não é investimento",
                "Ministério da Fazenda adverte: Apostar faz você perder dinheiro",
                "Ministério da Fazenda adverte: Apostar pode causar dependência"]

e = escape


def log(*a):
    print("[palpites]", *a, flush=True)


# ---------------------------------------------------------------- matemática
def _poisson(lam, k):
    return math.exp(-lam) * lam ** k / math.factorial(k)


def _tau(i, j, lh, la, rho):
    if i == 0 and j == 0:
        return 1 - lh * la * rho
    if i == 0 and j == 1:
        return 1 + lh * rho
    if i == 1 and j == 0:
        return 1 + la * rho
    if i == 1 and j == 1:
        return 1 - rho
    return 1.0


def probabilidades(lh, la, rho=RHO):
    """Tudo o que a página mostra, a partir dos gols esperados de cada lado."""
    ph = [_poisson(lh, i) for i in range(MAX_GOLS + 1)]
    pa = [_poisson(la, j) for j in range(MAX_GOLS + 1)]
    m = [[ph[i] * pa[j] * _tau(i, j, lh, la, rho) for j in range(MAX_GOLS + 1)] for i in range(MAX_GOLS + 1)]
    tot = sum(map(sum, m))
    m = [[x / tot for x in linha] for linha in m]
    casa = sum(m[i][j] for i in range(MAX_GOLS + 1) for j in range(MAX_GOLS + 1) if i > j)
    emp = sum(m[i][i] for i in range(MAX_GOLS + 1))
    fora = 1 - casa - emp
    pl = max(((i, j) for i in range(MAX_GOLS + 1) for j in range(MAX_GOLS + 1)), key=lambda p: m[p[0]][p[1]])
    ambos = sum(m[i][j] for i in range(1, MAX_GOLS + 1) for j in range(1, MAX_GOLS + 1))
    mais25 = sum(m[i][j] for i in range(MAX_GOLS + 1) for j in range(MAX_GOLS + 1) if i + j >= 3)
    return {"p": [round(casa, 4), round(emp, 4), round(fora, 4)], "pl": list(pl), "ppl": round(m[pl[0]][pl[1]], 4),
            "ambos": round(ambos, 4), "mais25": round(mais25, 4), "gc": round(lh, 2), "gf": round(la, 2)}


class Liga:
    """Médias de um campeonato e força de cada time, a partir de totais (gols pró, contra e jogos)."""

    def __init__(self, times, media_casa=None, media_fora=None, n0=N0):
        # times: {nome: (gp, gc, pj)}
        self.t = times
        gols = sum(v[0] for v in times.values())
        jogos = sum(v[2] for v in times.values())
        self.m = gols / jogos if jogos else 1.3  # gols por time por jogo
        if media_casa and media_fora:
            self.mc, self.mf = media_casa, media_fora
        else:
            r = math.sqrt(CASA_PADRAO)
            self.mc, self.mf = self.m * r, self.m / r
        self.n0 = n0

    def ataque(self, t):
        gp, _, pj = self.t[t]
        return (gp + self.n0 * self.m) / ((pj + self.n0) * self.m)

    def defesa(self, t):
        _, gc, pj = self.t[t]
        return (gc + self.n0 * self.m) / ((pj + self.n0) * self.m)

    def esperados(self, casa, fora):
        return (self.mc * self.ataque(casa) * self.defesa(fora), self.mf * self.ataque(fora) * self.defesa(casa))


def _medias_casa_fora(jogos):
    """Médias de gols do mandante e do visitante num conjunto de jogos (None se forem poucos)."""
    js = [x for x in jogos if x.get("placar")]
    if len(js) < 30:
        return None, None
    return (sum(x["placar"]["casa"] for x in js) / len(js), sum(x["placar"]["fora"] for x in js) / len(js))


def _tabela_times(tab):
    out = {}
    for g in tab.get("grupos", []):
        for l in g["linhas"]:
            out[l["time"]] = (l["gp"], l["gc"], l["pj"])
    return out


# ---------------------------------------------------------------- validação (só com o que se sabia antes do jogo)
def validar(tabs, hist, n0=N0, rho=RHO, comps=None, saida=True):
    """Para cada jogo do histórico: refaz a tabela como estava antes dele (tira os jogos daquele dia em diante),
    calcula o palpite e compara com o resultado. Devolve acerto, Brier e log-loss do modelo e de duas referências."""
    jogos = sorted((x for x in hist["jogos"].values() if x.get("placar")), key=lambda x: x["inicio"])
    res = {"n": 0, "acerto": 0, "brier": 0.0, "logloss": 0.0, "ref_brier": 0.0, "ref_logloss": 0.0, "por_comp": {}}
    for k, tab in tabs.items():
        if comps and k not in comps:
            continue
        total = _tabela_times(tab)
        jk = [x for x in jogos if x["comp"] == k and x["casa"] in total and x["fora"] in total]
        if len(jk) < MIN_JOGOS_COMP:
            continue
        pc = {"n": 0, "acerto": 0, "brier": 0.0, "logloss": 0.0, "ref": 0.0}
        for i, g in enumerate(jk):
            depois = jk[i:]
            antes = jk[:i]
            # tabela antes do jogo: total da temporada menos tudo o que o histórico tem desse dia em diante
            t0 = dict(total)
            for x in depois:
                for lado, gp, gc in ((x["casa"], x["placar"]["casa"], x["placar"]["fora"]),
                                     (x["fora"], x["placar"]["fora"], x["placar"]["casa"])):
                    a, b, c = t0[lado]
                    t0[lado] = (a - gp, b - gc, c - 1)
            if min(t0[g["casa"]][2], t0[g["fora"]][2]) < MIN_JOGOS_TIME or any(v[2] < 0 for v in t0.values()):
                continue
            mc, mf = _medias_casa_fora(antes)
            liga = Liga({t: v for t, v in t0.items() if v[2] > 0}, mc, mf, n0)
            lh, la = liga.esperados(g["casa"], g["fora"])
            p = probabilidades(lh, la, rho)["p"]
            r = 0 if g["placar"]["casa"] > g["placar"]["fora"] else 1 if g["placar"]["casa"] == g["placar"]["fora"] else 2
            # referência: frequência de vitória do mandante, empate e visitante nos jogos anteriores do campeonato
            ant = [x for x in antes]
            if len(ant) >= 20:
                f = [sum(1 for x in ant if (x["placar"]["casa"] > x["placar"]["fora"], x["placar"]["casa"] == x["placar"]["fora"],
                                            x["placar"]["casa"] < x["placar"]["fora"])[o]) / len(ant) for o in range(3)]
            else:
                f = [0.45, 0.27, 0.28]
            for alvo, prob in ((pc, p), (None, f)):
                brier = sum((prob[o] - (1 if o == r else 0)) ** 2 for o in range(3))
                ll = -math.log(max(prob[r], 1e-9))
                if alvo is pc:
                    pc["n"] += 1
                    pc["acerto"] += int(max(range(3), key=lambda o: prob[o]) == r)
                    pc["brier"] += brier
                    pc["logloss"] += ll
                else:
                    res["ref_brier"] += brier
                    res["ref_logloss"] += ll
                    pc["ref"] += ll
        if pc["n"]:
            res["por_comp"][k] = {"n": pc["n"], "acerto": round(pc["acerto"] / pc["n"], 3),
                                  "brier": round(pc["brier"] / pc["n"], 4), "logloss": round(pc["logloss"] / pc["n"], 4),
                                  "ref_logloss": round(pc["ref"] / pc["n"], 4)}
            for x in ("n", "acerto", "brier", "logloss"):
                res[x] += pc[x]
    n = res["n"] or 1
    out = {"jogos": res["n"], "acerto": round(res["acerto"] / n, 3), "brier": round(res["brier"] / n, 4),
           "logloss": round(res["logloss"] / n, 4), "ref_brier": round(res["ref_brier"] / n, 4),
           "ref_logloss": round(res["ref_logloss"] / n, 4), "uniforme_brier": 0.6667, "uniforme_logloss": round(math.log(3), 4),
           "por_comp": res["por_comp"]}
    if saida:
        print(json.dumps(out, ensure_ascii=False, indent=1))
    return out


# ---------------------------------------------------------------- palpites dos jogos do site
def _chave(j):
    return f'{j["inicio"][:10]}|{j["casa"]}|{j["fora"]}'


def _ler():
    try:
        return json.loads(ARQ.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"jogos": {}}


def config_apostas():
    """Espaço de apostas: só aparece se estiver ligado e completo (operadora autorizada, domínio .bet.br)."""
    try:
        a = json.loads(CONFIG.read_text(encoding="utf-8")).get("apostas") or {}
    except (OSError, ValueError):
        return None
    if not a.get("ativo"):
        return None
    falta = [c for c in ("nome", "link_afiliado", "autorizacao") if not str(a.get(c) or "").strip()]
    host = urllib.parse.urlparse(a.get("link_afiliado") or "").hostname or ""
    if falta or not host.endswith(".bet.br"):
        log("espaço de apostas NÃO ligado: falta", falta or "link de operadora autorizada (domínio .bet.br)")
        return None
    return a


def preparar(cx):
    """Calcula o palpite de cada jogo elegível (j["_palp"]), congela os de antes do jogo e mede o acerto."""
    hist = cx.hist.get("jogos") or {}
    dados = _ler()
    gravados = dados.setdefault("jogos", {})
    # só entram campeonatos em que o modelo, testado nos jogos já disputados, foi melhor que a referência
    val = validar(cx.tabs, cx.hist, saida=False)
    aprovados = {k for k, v in val["por_comp"].items() if v["n"] >= MIN_JOGOS_COMP and v["logloss"] < v["ref_logloss"]}
    dados["validacao"] = {"em": cx.agora.isoformat(timespec="minutes"), "N0": N0, "RHO": RHO,
                          **{k: v for k, v in val.items() if k != "por_comp"}, "por_comp": val["por_comp"],
                          "aprovados": sorted(aprovados)}
    ligas = {}
    for k, tab in cx.tabs.items():
        hk = [x for x in hist.values() if x["comp"] == k and x.get("placar")]
        if k not in aprovados:
            continue
        times = {t: v for t, v in _tabela_times(tab).items() if v[2] > 0}
        mc, mf = _medias_casa_fora(hk)
        ligas[k] = Liga(times, mc, mf)
    agora = cx.agora
    novos = 0
    for j in cx.jogos:
        liga = ligas.get(j["comp"])
        ch = _chave(j)
        if liga and j["casa"] in liga.t and j["fora"] in liga.t and \
                min(liga.t[j["casa"]][2], liga.t[j["fora"]][2]) >= MIN_JOGOS_TIME and agora < j["_t"]:
            p = probabilidades(*liga.esperados(j["casa"], j["fora"]))
            gravados[ch] = {**p, "comp": j["comp"], "casa": j["casa"], "fora": j["fora"], "inicio": j["inicio"],
                            "em": agora.isoformat(timespec="minutes")}
            novos += 1
        if ch in gravados:
            j["_palp"] = gravados[ch]
    # resultado dos palpites dos jogos que já terminaram (histórico + jogos de hoje com placar)
    placares = {f'{x["inicio"][:10]}|{x["casa"]}|{x["fora"]}': x["placar"] for x in hist.values() if x.get("placar")}
    placares.update({_chave(j): j["placar"] for j in cx.jogos if j.get("placar")})
    limite = (agora - timedelta(days=GUARDA_DIAS)).isoformat()
    for ch in list(gravados):
        g = gravados[ch]
        if g["inicio"] < limite:
            del gravados[ch]
            continue
        pl = placares.get(ch)
        if pl:
            r = 0 if pl["casa"] > pl["fora"] else 1 if pl["casa"] == pl["fora"] else 2
            g["resultado"] = [pl["casa"], pl["fora"]]
            g["acertou"] = max(range(3), key=lambda o: g["p"][o]) == r
    for j in cx.jogos:
        if j.get("_palp"):
            j["_palp"] = gravados.get(_chave(j), j["_palp"])
    # acerto dos últimos 30 dias, para mostrar com transparência
    desde = (agora - timedelta(days=30)).isoformat()
    feitos = [g for g in gravados.values() if "acertou" in g and g["inicio"] >= desde]
    cx.palp_acerto = (sum(g["acertou"] for g in feitos), len(feitos))
    cx.palp_apostas = config_apostas()
    ARQ.parent.mkdir(parents=True, exist_ok=True)
    ARQ.write_text(json.dumps(dados, ensure_ascii=False, separators=(",", ":"), sort_keys=True), encoding="utf-8")
    log(f"{novos} palpites calculados; acerto dos últimos 30 dias: {cx.palp_acerto[0]} de {cx.palp_acerto[1]}")


# ---------------------------------------------------------------- HTML
def _pct(x):
    return f"{round(x * 100)}%"


def _barra(j, p):
    nomes = (j["casa"], "Empate", j["fora"])
    seg = "".join(f'<span class="pb-s pb-{c}" style="width:{max(p[i] * 100, 2):.1f}%"></span>' for i, c in enumerate(("c", "e", "f")))
    rot = "".join(f'<span class="pb-r pb-{c}"><b>{_pct(p[i])}</b><span class="pb-n">{e(nomes[i])}</span></span>'
                  for i, c in enumerate(("c", "e", "f")))
    leitor = ", ".join(f"{nomes[i]}: {_pct(p[i])}" for i in range(3))
    return f'<div class="pb" role="img" aria-label="Chances: {e(leitor)}"><div class="pb-b">{seg}</div><div class="pb-l">{rot}</div></div>'


def _texto(cx, j, g):
    """Texto curto, só com fatos dos dados e a estimativa (sem prometer nada)."""
    import extras as X
    casa, fora = j["casa"], j["fora"]
    p = g["p"]
    fav = 0 if p[0] >= p[2] else 2
    frases = []
    if round(max(p[0], p[2]) * 100) >= 50:
        nome = casa if fav == 0 else fora
        frases.append(f"{nome} chega como favorito{' em casa' if fav == 0 else ' mesmo fora de casa'}: "
                      f"{_pct(p[fav])} de chance de vitória pelo modelo.")
    elif abs(p[0] - p[2]) < 0.1:
        frases.append(f"Jogo equilibrado: {_pct(p[0])} para o {casa}, {_pct(p[1])} de empate e {_pct(p[2])} para o {fora}.")
    else:
        nome = casa if fav == 0 else fora
        frases.append(f"Leve vantagem para o {nome} ({_pct(p[fav])}), com {_pct(p[1])} de chance de empate.")
    for t in (casa, fora):
        l, _ = X.posicao(cx.tabs, j["comp"], t)
        if l and l["pj"]:
            frases.append(f"{t}: {l['pos']}º colocado, marca {_num(l['gp'] / l['pj'])} e sofre {_num(l['gc'] / l['pj'])} gols por jogo.")
    ult = []
    for t in (casa, fora):
        u = X.ultimos(cx.hist, t, 5, antes=j["inicio"])
        if len(u) >= 3:
            r = [X.resultado_para(t, x) for x in u]
            ult.append(f"{t} {r.count('V')}V {r.count('E')}E {r.count('D')}D")
    if ult:
        frases.append("Últimos 5 jogos: " + "; ".join(ult) + ".")
    frases.append(f"Expectativa de {_num(g['gc'] + g['gf'])} gols no total.")
    return " ".join(frases)


def _num(x):
    return f"{x:.1f}".replace(".", ",")


def apostas_html(cx, onde):
    """Bloco publicitário de apostas, com todos os avisos legais. Vazio se o espaço estiver desligado."""
    a = getattr(cx, "palp_apostas", None)
    if not a:
        return ""
    adv = ADVERTENCIAS[cx.hoje.toordinal() % len(ADVERTENCIAS)]
    link = a["link_afiliado"]
    sep = "&" if "?" in link else "?"
    link = f"{link}{sep}utm_source=ondepassajogo&utm_medium=afiliado&utm_campaign={urllib.parse.quote(onde)}"
    cupom = f'<p class="ap-cupom">Cupom: <b>{e(a["cupom"])}</b></p>' if a.get("cupom") else ""
    return (f'<aside class="ap" aria-label="Publicidade de apostas">'
            f'<p class="ap-tag"><span class="ap-18" title="Proibido para menores de 18 anos">18+</span>Publicidade</p>'
            f'<a class="ap-bt" href="{e(link)}" rel="sponsored nofollow noopener" target="_blank">Ver odds na {e(a["nome"])}</a>{cupom}'
            f'<p class="ap-adv">{e(adv)}.</p>'
            f'<p class="ap-leg">{e(a["nome"])}: operadora autorizada pela Portaria SPA/MF nº {e(a["autorizacao"])} '
            f'(<a href="{AUTORIZADAS}" target="_blank" rel="noopener">confira a lista oficial</a>). Proibido para menores de 18 anos. '
            f'Apostar envolve risco de perder dinheiro e pode causar dependência: '
            f'<a href="{JOGO_RESPONSAVEL}" target="_blank" rel="noopener">jogo responsável</a> · '
            f'<a href="{AUTOEXCLUSAO}" target="_blank" rel="noopener">autoexclusão</a>. '
            f'O Onde Passa Jogo recebe comissão por este link.</p></aside>')


CSS = '<link rel="stylesheet" href="/palpites.css?v=1">'


def secao(cx, j):
    """Seção "Palpite" da página do jogo: antes do jogo, a estimativa; depois, se acertou."""
    g = j.get("_palp")
    if not g:
        return ""
    comecou = cx.agora >= j["_t"]
    acerto = ""
    if "acertou" in g:
        r = g["resultado"]
        acerto = (f'<p class="pa {"pa-ok" if g["acertou"] else "pa-no"}">'
                  f'{"Acertou" if g["acertou"] else "Errou"}: o palpite apontava '
                  f'{["vitória do " + j["casa"], "empate", "vitória do " + j["fora"]][max(range(3), key=lambda o: g["p"][o])]}'
                  f' e o jogo terminou {r[0]} x {r[1]}.</p>')
    elif comecou:
        acerto = '<p class="pa">Palpite feito antes do jogo; o resultado aparece aqui quando o jogo terminar.</p>'
    titulo = "Palpite antes do jogo" if comecou else "Palpite"
    det = (f'<ul class="pm"><li><span>Placar mais provável</span><b>{g["pl"][0]} x {g["pl"][1]}</b><small>{_pct(g["ppl"])}</small></li>'
           f'<li><span>Ambos marcam</span><b>{_pct(g["ambos"])}</b></li>'
           f'<li><span>Mais de 2,5 gols</span><b>{_pct(g["mais25"])}</b></li>'
           f'<li><span>Gols esperados</span><b>{_num(g["gc"])} x {_num(g["gf"])}</b></li></ul>')
    ac, n = getattr(cx, "palp_acerto", (0, 0))
    hist_ac = f" O modelo acertou o resultado em {ac} de {n} jogos nos últimos 30 dias ({_pct(ac / n)})." if n >= 20 else ""
    nota = (f'<p class="pn">Estimativa estatística do Onde Passa Jogo, feita com os gols marcados e sofridos na temporada '
            f'(modelo de Poisson). Não é garantia de resultado.{hist_ac} <a href="/palpites-de-hoje/#como">Como calculamos</a></p>')
    apostas = apostas_html(cx, "jogo") if not comecou else ""
    return (f'{CSS}<section class="palp" id="palpite"><h2>{titulo}</h2>{_barra(j, g["p"])}{acerto}{det}'
            f'<p class="pt">{e(_texto(cx, j, g))}</p>{nota}{apostas}</section>')


def pagina_palpites(cx, cam, rot, dia, pagina, escudo, hora, data_longa, URL):
    """Página /palpites-de-hoje/ e /palpites-de-amanha/ (recebe as funções de página do paginas.py)."""
    js = [j for j in cx.jogos if j["_t"].date() == dia and j.get("_palp")]
    js.sort(key=lambda j: (j["_t"], j["comp"]))
    dtxt = f"{dia:%d/%m}"
    titulo = f"Palpites de {rot} ({dtxt}): chances de vitória e placar provável | Onde Passa Jogo"
    desc = (f"Palpites de {rot}, {data_longa(dia)}: probabilidade de vitória, empate e derrota, placar mais provável, "
            f"ambos marcam e mais de 2,5 gols em {len(js)} jogos, calculados com estatística. E onde assistir cada jogo.")
    cards = []
    for j in js:
        g = j["_palp"]
        res = ""
        if "acertou" in g:
            res = f'<span class="pa {"pa-ok" if g["acertou"] else "pa-no"}">{"Acertou" if g["acertou"] else "Errou"} · {g["resultado"][0]} x {g["resultado"][1]}</span>'
        cards.append(
            f'<li class="pc"><p class="pc-i">{e(cx.comp_nome(j["comp"]))} · {hora(j["_t"])}</p>'
            f'<a class="pc-t" href="{e(j["_pg"])}#palpite">{escudo(cx, j["casa"], 26)}<b>{e(j["casa"])}</b><i>x</i>'
            f'<b>{e(j["fora"])}</b>{escudo(cx, j["fora"], 26)}</a>{_barra(j, g["p"])}'
            f'<p class="pc-d">Placar mais provável <b>{g["pl"][0]} x {g["pl"][1]}</b> · Ambos marcam <b>{_pct(g["ambos"])}</b>'
            f' · Mais de 2,5 gols <b>{_pct(g["mais25"])}</b>{res}</p></li>')
    outro = ("/palpites-de-amanha/", "Palpites de amanhã ›") if rot == "hoje" else ("/palpites-de-hoje/", "‹ Palpites de hoje")
    ac, n = getattr(cx, "palp_acerto", (0, 0))
    ac_txt = f"<p>Nos últimos 30 dias, o modelo acertou o resultado (vitória, empate ou derrota) em <b>{ac} de {n}</b> jogos ({_pct(ac / n)}).</p>" if n >= 20 else ""
    como = (
        '<section class="como" id="como"><h2>Como calculamos os palpites</h2>'
        "<p>Para cada time, comparamos a média de gols que ele marca e sofre por jogo na temporada com a média do campeonato "
        "(força de ataque e de defesa). Com isso e a vantagem de jogar em casa medida no próprio campeonato, estimamos quantos "
        "gols cada time deve fazer e calculamos a chance de cada placar com a distribuição de Poisson, com um ajuste para "
        "placares baixos (Dixon e Coles). Só entram jogos de campeonatos com dados suficientes.</p>"
        "<p>O palpite de cada jogo é registrado antes do apito inicial e, depois do jogo, mostramos se ele acertou. "
        "São estimativas estatísticas: futebol tem muito acaso, e nenhum palpite é garantia de resultado.</p>"
        f"{ac_txt}"
        f'<p class="pn">Se você aposta: apostas são proibidas para menores de 18 anos, envolvem risco de perder dinheiro e '
        f'podem causar dependência. <a href="{JOGO_RESPONSAVEL}" target="_blank" rel="noopener">Jogo responsável</a> · '
        f'<a href="{AUTOEXCLUSAO}" target="_blank" rel="noopener">Autoexclusão</a>.</p></section>')
    lista = f'<ul class="pcs">{"".join(cards)}</ul>' if cards else \
        f'<p class="pvazio">Ainda não há palpites para {rot}: eles aparecem para jogos de campeonatos com dados suficientes.</p>'
    corpo = (f'{CSS}<h1>Palpites de {rot} <small>{e(data_longa(dia))}</small></h1>'
             f'<p class="pint">Chances de cada resultado, placar mais provável e gols, calculados com estatística para '
             f'{len(js)} jogo{"s" if len(js) != 1 else ""}. Toque no jogo para ver a análise completa e onde assistir.</p>'
             f'{apostas_html(cx, "palpites-" + rot)}{lista}'
             f'<p class="mais"><a href="{outro[0]}">{outro[1]}</a> · <a href="/jogos-de-{"hoje" if rot == "hoje" else "amanha"}/">'
             f'Onde assistir os jogos de {rot}</a></p>{como}')
    ld = {"@context": "https://schema.org", "@type": "ItemList", "name": f"Palpites de {rot} ({dtxt})",
          "itemListElement": [{"@type": "ListItem", "position": i + 1,
                               "item": {"@type": "SportsEvent", "name": f'{j["casa"]} x {j["fora"]}', "startDate": j["inicio"],
                                        "url": URL + j["_pg"], "sport": "Futebol",
                                        "homeTeam": {"@type": "SportsTeam", "name": j["casa"]},
                                        "awayTeam": {"@type": "SportsTeam", "name": j["fora"]}}}
                              for i, j in enumerate(js)]}
    return pagina(cx, cam, titulo, desc, corpo, [ld], [("Início", "/"), (f"Palpites de {rot}", cam)])


if __name__ == "__main__":
    if "--validar" in sys.argv:
        tabs = json.loads((RAIZ / "dados" / "tabelas.json").read_text(encoding="utf-8"))
        hist = json.loads((RAIZ / "dados" / "historico.json").read_text(encoding="utf-8"))
        if "--grade" in sys.argv:
            for n0 in (0, 2, 4, 6, 8, 12):
                for rho in (-0.15, -0.1, -0.05, 0.0, 0.05):
                    r = validar(tabs, hist, n0, rho, saida=False)
                    print(f"N0={n0:>2} RHO={rho:+.2f}  jogos={r['jogos']} acerto={r['acerto']} brier={r['brier']} logloss={r['logloss']}")
        else:
            validar(tabs, hist)
