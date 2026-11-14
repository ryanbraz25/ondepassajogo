#!/usr/bin/env python3
"""
Robô de atualização da Agenda do Futebol.

Roda sozinho (GitHub Actions, a cada 3 horas) e:
  1. busca jogos e horários dos próximos dias na TheSportsDB;
  2. se houver chave premium da TheSportsDB, busca também os canais de TV do Brasil;
  3. se houver chave da API do YouTube, procura as transmissões agendadas nos canais
     oficiais (CazéTV, ge tv, Canal GOAT...) e põe o link direto da live no jogo;
  4. junta tudo com dados/verificados.json (jogos conferidos pela checagem diária),
     que sempre tem prioridade;
  5. grava dados/jogos.json e gera site/index.html.

Só usa a biblioteca padrão do Python. Variáveis de ambiente (todas opcionais):
  THESPORTSDB_KEY   chave da TheSportsDB (padrão: chave gratuita "123")
  YOUTUBE_API_KEY   chave da YouTube Data API v3
  AMAZON_TAG        sua tag de Associado Amazon (vai no link do Prime Video)

Uso:  python robo/atualizar.py            (normal)
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


def gerar_site(dados):
    tpl = (RAIZ / "site" / "template.html").read_text(encoding="utf-8")
    bloco = json.dumps(dados, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    (RAIZ / "site" / "index.html").write_text(tpl.replace("__DADOS__", bloco), encoding="utf-8")


def main():
    cfg = ler(RAIZ / "robo" / "config.json")
    verif = ler(RAIZ / "dados" / "verificados.json")["jogos"]
    hoje = datetime.now(BRT).date()
    dias = [(hoje + timedelta(days=i)).isoformat() for i in range(cfg["site"]["dias_a_frente"])]

    api = []
    if not OFFLINE:
        if cfg["site"].get("usar_thesportsdb"):
            api = thesportsdb(cfg, dias)
            thesportsdb_tv(cfg, dias, api)
        youtube(cfg, api + verif)

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
    }
    anterior.write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8")
    gerar_site(dados)
    log(f"Pronto: {len(jogos)} jogos, site/index.html gerado.")


if __name__ == "__main__":
    main()
