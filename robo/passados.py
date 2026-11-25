"""Jogos dos dias que já passaram.

O jogos.json só guarda de ontem em diante. Este arquivo (dados/passados.json) guarda cada jogo como
ele estava na agenda (canais, local, rodada, placar), para:
  - as páginas dos jogos antigos continuarem sendo geradas com o modelo atual (escalações, números
    dos jogadores, estatísticas), em vez de ficarem congeladas como estavam no dia;
  - a página inicial mostrar os resultados dos dias anteriores (arquivos site/dados/dia-AAAA-MM-DD.json).

Dias anteriores ao arquivo saem do histórico de resultados da ESPN (robo/extras.py), sem a informação de
onde passou: esses jogos vão marcados com "sc": 1 e o site não mostra canal para eles.
"""
import json
from datetime import datetime, timedelta
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ARQ = RAIZ / "dados" / "passados.json"
PASTA_SITE = RAIZ / "site" / "dados"
GUARDAR_DIAS = 60  # o mesmo tempo que as páginas dos jogos ficam no ar (paginas.GUARDAR_DIAS)
DIAS_HOME = 14     # quantos dias para trás a página inicial mostra


def _ler():
    try:
        return json.loads(ARQ.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"v": 1, "jogos": {}}


def atualizar(jogos, hist, hoje, caminho_jogo):
    """Guarda os jogos de dias passados que estão na agenda e completa o placar e os lances pelo histórico."""
    arq = _ler()
    js = arq.setdefault("jogos", {})
    h = hoje.isoformat()
    for j in jogos:
        if j["inicio"][:10] < h and "A definir" not in (j["casa"], j["fora"]):
            js[caminho_jogo(j)] = {k: v for k, v in j.items() if k not in ("pg", "fase")}
    por_eid = hist.get("jogos") or {}
    por_par = {(x.get("inicio", "")[:10], x["casa"], x["fora"]): (k, x) for k, x in por_eid.items()}
    for j in js.values():
        x = por_eid.get(str(j.get("eid") or ""))
        if not x and not j.get("eid"):  # jogo que entrou na agenda sem o id da ESPN: acha pelo dia e pelos times
            k, x = por_par.get((j["inicio"][:10], j["casa"], j["fora"]), (None, None))
            if x:
                j["eid"] = k
                if x.get("lg"):
                    j["lg"] = x["lg"]
        if x and x.get("placar"):
            j["placar"] = x["placar"]
            if x.get("lances") and not j.get("lances"):
                j["lances"] = x["lances"]
    corte = (hoje - timedelta(days=GUARDAR_DIAS)).isoformat()
    arq["jogos"] = {k: v for k, v in sorted(js.items(), key=lambda kv: kv[1]["inicio"]) if v["inicio"][:10] >= corte}
    novo = json.dumps(arq, ensure_ascii=False, indent=0, sort_keys=True)
    if not ARQ.exists() or ARQ.read_text(encoding="utf-8") != novo:
        ARQ.write_text(novo, encoding="utf-8")
    return arq


def com_resultado(arq):
    """Jogos passados que aconteceram (com placar). Jogo adiado fica com a data velha e sem placar: não entra."""
    return [j for j in arq["jogos"].values() if j.get("placar")]


def dias_home(arq, hist, hoje):
    """{dia: [jogos]} dos últimos DIAS_HOME dias: o arquivo da agenda e, onde faltar, o histórico da ESPN."""
    ini = (hoje - timedelta(days=DIAS_HOME)).isoformat()
    h = hoje.isoformat()
    out = {}
    vistos_eid, vistos_par = set(), set()
    for j in com_resultado(arq):
        d = j["inicio"][:10]
        if ini <= d < h:
            out.setdefault(d, []).append(dict(j))
            vistos_eid.add(str(j.get("eid") or ""))
            vistos_par.add((d, j["casa"], j["fora"]))
    for eid, x in (hist.get("jogos") or {}).items():
        d = x.get("inicio", "")[:10]
        if not (ini <= d < h) or not x.get("placar") or eid in vistos_eid or (d, x["casa"], x["fora"]) in vistos_par:
            continue
        g = {k: x[k] for k in ("inicio", "comp", "casa", "fora", "local", "placar", "lg") if x.get(k)}
        g.update({"eid": eid, "canais": [], "status": "", "sc": 1})
        if x.get("lances"):
            g["lances"] = x["lances"]
        out.setdefault(d, []).append(g)
    for d in out:
        out[d].sort(key=lambda j: (j["inicio"], j["casa"]))
    return dict(sorted(out.items()))


def arquivos_site(dias, escudos_de, com_pagina):
    """site/dados/dia-AAAA-MM-DD.json para cada dia; devolve a lista [{"d", "n"}] que vai para a página inicial.

    escudos_de(jogos) -> {time: url}; com_pagina(jogo) -> caminho da página do jogo, ou "" se não houver."""
    PASTA_SITE.mkdir(parents=True, exist_ok=True)
    feitos, lista = set(), []
    for d, js in dias.items():
        saida = []
        for j in js:
            g = {k: v for k, v in j.items() if k != "lances"}
            pg = com_pagina(j)
            if pg:
                g["pg"] = pg
            saida.append(g)
        conteudo = json.dumps({"jogos": saida, "escudos": escudos_de(js)}, ensure_ascii=False, separators=(",", ":"))
        nome = f"dia-{d}.json"
        arq = PASTA_SITE / nome
        if not arq.exists() or arq.read_text(encoding="utf-8") != conteudo:
            arq.write_text(conteudo, encoding="utf-8")
        feitos.add(nome)
        lista.append({"d": d, "n": len(saida)})
    for f in PASTA_SITE.glob("dia-*.json"):
        if f.name not in feitos:
            f.unlink()
    return lista
