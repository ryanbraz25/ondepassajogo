"""Artilharia e assistências de cada campeonato.

Fonte: a lista de líderes da liga da ESPN (/apis/site/v2/sports/soccer/<liga>/statistics), grátis e sem
chave, com os 50 primeiros em gols e em assistências. O robô traduz o time para o nome que o site usa
(pelo id da ESPN que já está na tabela; se não estiver, pelo mesmo tradutor de nomes da agenda) e grava:
- dados/artilharia.json (para as páginas dos campeonatos);
- site/dados/art-<campeonato>.json (para a aba "Artilharia" da página inicial).
"""
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from html import escape as e
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ARQ = RAIZ / "dados" / "artilharia.json"
SAIDA = RAIZ / "site" / "dados"
BRT = timezone(timedelta(hours=-3))
URL = "https://site.api.espn.com/apis/site/v2/sports/soccer/{}/statistics"
TOP_GOLS, TOP_ASSIST = 20, 10
SEM_ARTILHARIA = {"amistoso"}  # amistosos misturam seleções do mundo todo: lista sem sentido


def log(*a):
    print("[artilharia]", *a, flush=True)


def ler():
    try:
        return json.loads(ARQ.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _lista(cat, por_tid, nome_time, chave, top):
    out = []
    for x in (cat.get("leaders") or [])[:top]:
        a = x.get("athlete") or {}
        st = {s.get("name"): s.get("value") for s in a.get("statistics") or []}
        t = a.get("team") or {}
        tid = str(t.get("id") or "")
        time_ = por_tid.get(tid) or (nome_time(t.get("displayName") or "") if t.get("displayName") else "")
        n = int(x.get("value") or st.get(chave) or 0)
        if not a.get("displayName") or n <= 0:
            continue
        out.append({"nome": a["displayName"], "time": time_, "n": n, "jogos": int(st.get("appearances") or 0)})
    # posição com empate (1º, 2º, 2º, 4º...)
    for i, l in enumerate(out):
        l["pos"] = out[i - 1]["pos"] if i and out[i - 1]["n"] == l["n"] else i + 1
    return out


def buscar(cfg, get_json, tabs, nome, comps_ativos, offline=False):
    """{campeonato: {"gols": [...], "assist": [...], "temporada": "2026"}} dos campeonatos em andamento."""
    dados = ler()
    if not offline:
        alvo = []
        for k, c in cfg["competicoes"].items():
            espn = c.get("espn")
            liga = (espn[0] if isinstance(espn, list) else espn) if espn else None
            if liga and k in comps_ativos and k not in SEM_ARTILHARIA:
                alvo.append((k, liga))

        def um(par):
            k, liga = par
            try:
                return k, liga, get_json(URL.format(liga), timeout=30)
            except Exception as ex:
                log("falhou:", k, ex)
                return k, liga, None

        novos = {}
        with ThreadPoolExecutor(max_workers=6) as ex:
            for k, liga, r in ex.map(um, alvo):
                if r is None:
                    if k in dados:
                        novos[k] = dados[k]  # falhou agora: fica o que já havia
                    continue
                por_tid = {}
                for g in (tabs.get(k) or {}).get("grupos", []):
                    por_tid.update({l["tid"]: l["time"] for l in g["linhas"] if l.get("tid")})
                cats = {c.get("name"): c for c in r.get("stats") or []}
                tr = lambda t, k=k: nome(cfg, t, k)
                gols = _lista(cats.get("goalsLeaders") or {}, por_tid, tr, "totalGoals", TOP_GOLS)
                assist = _lista(cats.get("assistsLeaders") or {}, por_tid, tr, "goalAssists", TOP_ASSIST)
                if gols:
                    novos[k] = {"gols": gols, "assist": assist, "temporada": str((r.get("season") or {}).get("year") or ""),
                                "atualizado": datetime.now(BRT).isoformat(timespec="minutes")}
        dados = novos
    ARQ.parent.mkdir(parents=True, exist_ok=True)
    ARQ.write_text(json.dumps(dados, ensure_ascii=False, separators=(",", ":"), sort_keys=True), encoding="utf-8")
    log(f"{len(dados)} campeonatos com artilharia")
    return dados


def arquivos_site(art, escudos):
    """site/dados/art-<campeonato>.json para a aba da página inicial (com o escudo de cada time)."""
    SAIDA.mkdir(parents=True, exist_ok=True)
    feitos = set()
    for k, a in art.items():
        com_esc = lambda xs: [{**x, **({"esc": escudos[x["time"]]} if escudos.get(x["time"]) else {})} for x in xs]
        conteudo = json.dumps({"gols": com_esc(a["gols"]), "assist": com_esc(a.get("assist") or []), "temporada": a.get("temporada", "")},
                              ensure_ascii=False, separators=(",", ":"))
        arq = SAIDA / f"art-{k}.json"
        if not arq.exists() or arq.read_text(encoding="utf-8") != conteudo:
            arq.write_text(conteudo, encoding="utf-8")
        feitos.add(arq.name)
    for f in SAIDA.glob("art-*.json"):
        if f.name not in feitos:
            f.unlink()


def html(a, escudo, link_time):
    """Tabelas de artilheiros e de assistências (página do campeonato). escudo(time) e link_time(time) vêm de paginas.py."""
    def tabela(xs, titulo, col):
        def time_(t):
            if not t:
                return ""
            href = link_time(t)
            nome_t = f'<a href="{e(href)}">{e(t)}</a>' if href else e(t)
            return f"{escudo(t)}{nome_t}"
        linhas = "".join(
            f'<tr><td class="ar-p">{x["pos"]}</td><td class="ar-j"><b>{e(x["nome"])}</b><span>{time_(x["time"])}</span></td>'
            f'<td class="ar-n">{x["n"]}</td><td class="ar-g">{x["jogos"] or "–"}</td></tr>' for x in xs)
        return (f'<div class="ar-bloco"><h3>{e(titulo)}</h3><table class="ar-tab"><thead><tr><th>#</th><th>Jogador</th>'
                f'<th title="{e(col)}">{e(col[:1])}</th><th title="Jogos">J</th></tr></thead><tbody>{linhas}</tbody></table></div>')
    partes = [tabela(a["gols"], "Artilheiros", "Gols")]
    if a.get("assist"):
        partes.append(tabela(a["assist"], "Assistências", "Assistências"))
    return f'<div class="ar">{"".join(partes)}</div><p class="ar-fonte">Gols e jogos na temporada {e(a.get("temporada", ""))}, atualizados a cada hora.</p>'
