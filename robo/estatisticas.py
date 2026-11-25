"""Estatísticas dos jogos (posse, finalizações, escanteios, faltas...), como no ge.

Fonte: o resumo do jogo da ESPN (boxscore.teams[].statistics), grátis e sem chave. O robô guarda as
estatísticas dos jogos que já começaram em dados/estatisticas.json; a página do jogo sai com o bloco
pronto (bom para o Google) e o estatisticas.js atualiza enquanto a bola rola.
"""
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from html import escape as e
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ARQ = RAIZ / "dados" / "estatisticas.json"
BRT = timezone(timedelta(hours=-3))
SUMMARY = "https://site.web.api.espn.com/apis/site/v2/sports/soccer/{}/summary?event={}&region=br&lang=pt"
GUARDA_DIAS = 60      # o mesmo tempo que as páginas de jogo ficam no ar
POR_RODADA = 40       # consultas por execução, no máximo

# (nome na ESPN, rótulo, tipo) — a ordem é a do bloco na página; "pct" vira a barra grande de posse
ITENS = [
    ("possessionPct", "Posse de bola", "pct"),
    ("totalShots", "Finalizações", "n"),
    ("shotsOnTarget", "Finalizações no gol", "n"),
    ("wonCorners", "Escanteios", "n"),
    ("foulsCommitted", "Faltas", "n"),
    ("offsides", "Impedimentos", "n"),
    ("yellowCards", "Cartões amarelos", "n"),
    ("redCards", "Cartões vermelhos", "n"),
    ("saves", "Defesas do goleiro", "n"),
    ("accuratePasses", "Passes certos", "n"),
]


def log(*a):
    print("[estatísticas]", *a, flush=True)


def ler():
    try:
        return json.loads(ARQ.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _num(v):
    try:
        x = float(str(v).replace("%", "").replace(",", "."))
    except (TypeError, ValueError):
        return None
    return int(x) if x.is_integer() else round(x, 1)


def extrair(summary):
    """{"casa": {nome: valor}, "fora": {...}, "fim": bool} a partir do resumo da ESPN; None se não houver números."""
    lados = {}
    for t in ((summary.get("boxscore") or {}).get("teams") or []):
        st = {x.get("name"): _num(x.get("displayValue", x.get("value"))) for x in t.get("statistics") or []}
        st = {k: st[k] for k, _, _ in ITENS if st.get(k) is not None}
        if t.get("homeAway") in ("home", "away") and st:
            lados["casa" if t["homeAway"] == "home" else "fora"] = st
    if len(lados) != 2:
        return None
    # sem nenhum número diferente de zero o jogo ainda não começou de verdade
    if not any(v for lado in lados.values() for v in lado.values()):
        return None
    comp = ((summary.get("header") or {}).get("competitions") or [{}])[0]
    estado = (((comp.get("status") or {}).get("type")) or {}).get("state")
    return {**lados, "fim": estado == "post"}


def buscar(get_json, jogos, offline=False):
    """Atualiza as estatísticas dos jogos que já começaram (até GUARDA_DIAS) e ainda não estão completas."""
    dados = ler()
    agora = datetime.now(BRT)
    if not offline:
        alvo = []
        for j in jogos:
            if not (j.get("eid") and j.get("lg")) or (dados.get(j["eid"]) or {}).get("fim"):
                continue
            ini = datetime.fromisoformat(j["inicio"]).astimezone(BRT)
            # do início até o fim da guarda: jogo antigo sem números (de antes deste arquivo ou de quando
            # o robô não rodou) é buscado aos poucos, os mais recentes primeiro
            if timedelta(minutes=5) <= agora - ini <= timedelta(days=GUARDA_DIAS):
                alvo.append(j)
        alvo.sort(key=lambda j: j["inicio"], reverse=True)

        def um(j):
            try:
                return j, extrair(get_json(SUMMARY.format(j["lg"], j["eid"]), timeout=30))
            except Exception as ex:
                log("falhou:", j["casa"], "x", j["fora"], ex)
                return j, None

        with ThreadPoolExecutor(max_workers=6) as ex:
            for j, st in ex.map(um, alvo[:POR_RODADA]):
                if st:
                    dados[j["eid"]] = {**st, "inicio": j["inicio"]}
    corte = (agora - timedelta(days=GUARDA_DIAS)).isoformat()
    dados = {k: v for k, v in dados.items() if v.get("inicio", "") >= corte}
    ARQ.parent.mkdir(parents=True, exist_ok=True)
    ARQ.write_text(json.dumps(dados, ensure_ascii=False, separators=(",", ":"), sort_keys=True), encoding="utf-8")
    log(f"{len(dados)} jogos com estatísticas guardadas")
    return dados


def _fmt(v, tipo):
    txt = f"{v:g}".replace(".", ",")  # 69,6 (vírgula, como se escreve no Brasil)
    return txt + "%" if tipo == "pct" else txt


def html(st, casa, fora):
    """Bloco "Estatísticas" da página do jogo. Sem dados, sai vazio e escondido (o estatisticas.js preenche ao vivo)."""
    linhas = []
    for k, rot, tipo in ITENS if st else []:
        a, b = st["casa"].get(k), st["fora"].get(k)
        if a is None or b is None:
            continue
        pa = round(a) if tipo == "pct" else round(100 * a / (a + b)) if a + b else 50
        cls = ("st-pct " if tipo == "pct" else "") + ("st-zero" if a + b == 0 else "")
        lider = "c" if a > b else "f" if b > a else ""
        linhas.append(
            f'<li class="st-l {cls.strip()}" data-k="{k}"><div class="st-n"><b class="{"lid" if lider == "c" else ""}">{_fmt(a, tipo)}</b>'
            f'<span>{e(rot)}</span><b class="{"lid" if lider == "f" else ""}">{_fmt(b, tipo)}</b></div>'
            f'<div class="st-b" role="img" aria-label="{e(rot)}: {e(casa)} {_fmt(a, tipo)}, {e(fora)} {_fmt(b, tipo)}">'
            f'<i class="st-bc" style="width:{pa}%"></i><i class="st-bf" style="width:{100 - pa}%"></i></div></li>')
    fim = bool(st and st.get("fim"))
    return (f'<section class="estat" aria-labelledby="estat-t"{"" if linhas else " hidden"}>'
            f'<h2 id="estat-t">Estatísticas{"" if fim else " <small>parciais</small>"}</h2>'
            f'<div class="st-times"><span>{e(casa)}</span><span>{e(fora)}</span></div>'
            f'<ul class="st-lista">{"".join(linhas)}</ul></section>')
