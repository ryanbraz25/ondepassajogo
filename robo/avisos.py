"""Avisos no celular: resumo do dia às 9h (horário de Brasília).

Roda no GitHub depois do robô da agenda, a cada passo de hora em hora. Envia uma vez por dia:
lê os inscritos no Firestore (projeto Firebase do site), monta uma mensagem para cada pessoa
com os jogos de hoje dos times e ligas que ela segue (ou os jogos mais importantes do dia)
e manda pelo Firebase Cloud Messaging. O texto não entrega o canal: chama para abrir o site.

Precisa do segredo FIREBASE_SA (JSON da conta de serviço). Sem ele, não faz nada.
Teste sem enviar: python robo/avisos.py --simular
Forçar envio fora do horário (uma vez): python robo/avisos.py --agora
"""
import json
import os
import sys
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
BRT = timezone(timedelta(hours=-3))
ESTADO = RAIZ / "dados" / "avisos_estado.json"
SITE = "https://ondepassajogo.com.br/"
GRATIS = {"TV aberta", "YouTube"}


def log(*a):
    print("[avisos]", *a, flush=True)


def ler(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def n2(s):
    s = unicodedata.normalize("NFD", str(s)).encode("ascii", "ignore").decode().lower()
    return " ".join("".join(ch if ch.isalnum() else " " for ch in s).split())


def hhmm(dt):
    return f"{dt.hour}h{dt.minute:02d}" if dt.minute else f"{dt.hour}h"


def jogos_de_hoje(dados, agora):
    hoje = agora.date()
    out = []
    for j in dados["jogos"]:
        ini = datetime.fromisoformat(j["inicio"]).astimezone(BRT)
        if ini.date() != hoje or ini < agora - timedelta(minutes=30) or j.get("placar"):
            continue
        out.append({**j, "_t": ini})
    return sorted(out, key=lambda j: j["_t"])


def audiencia(cfg, j):
    pop = cfg.get("popularidade", {})
    times, comps = pop.get("times", {}), pop.get("competicoes", {})
    p = lambda t: times.get(n2(t), pop.get("padrao", 10))
    a, b = p(j["casa"]), p(j["fora"])
    txt = n2((j.get("rodada") or "") + " " + (j.get("nota") or ""))
    extra = (pop.get("final", 30) if " final" in " " + txt else 0)
    extra += pop.get("decisivo", 5) if any(w in txt for w in ("titulo", "rebaixamento", "classico", "lider")) else 0
    return max(a, b) + min(a, b) * 0.5 + comps.get(j["comp"], 0) + extra


def tem_gratis(dados, j):
    canais = dados.get("canais", {})
    for c in j.get("canais", []):
        if (canais.get(c) or {}).get("tipo") in GRATIS:
            return True
        link = (j.get("links") or {}).get(c, "")
        if "youtube.com" in link or "youtu.be" in link:
            return True
    return False


def mensagem(dados, meus, destaque, total_hoje):
    """Texto curto que chama para abrir o site (sem entregar o canal).

    meus já vem ordenado: primeiro jogos dos times seguidos, depois os das ligas, do maior para o menor."""
    if meus:
        j = meus[0]
        g = any(tem_gratis(dados, x) for x in meus)
        isca = "Tem opção grátis 👀 Toque e veja onde assistir." if g else "Toque e veja onde passa."
        mais = len(meus) - 1
        resto = f" E mais {mais} {'jogo' if mais == 1 else 'jogos'} de quem você segue." if mais else ""
        url = SITE + "?utm_source=push&utm_medium=notificacao&utm_campaign=meus_jogos#seguindo"
        if j["_time"]:
            return (f"⚽ Hoje tem {j['_quem']}!", f"{j['casa']} x {j['fora']} às {hhmm(j['_t'])}.{resto} {isca}", url)
        return (f"⚽ Hoje tem {j['_quem']}: {len(meus)} {'jogo' if len(meus) == 1 else 'jogos'}",
                f"Destaque: {j['casa']} x {j['fora']} às {hhmm(j['_t'])}. {isca}", url)
    j = destaque[0]
    outros = total_hoje - 1
    g = tem_gratis(dados, j)
    return (f"🔥 Jogão hoje: {j['casa']} x {j['fora']} às {hhmm(j['_t'])}",
            "Veja onde passa" + (" (tem opção grátis!)" if g else "") + "." +
            (f" Hoje ainda tem mais {outros} jogos na agenda." if outros > 0 else ""),
            SITE + "?utm_source=push&utm_medium=notificacao&utm_campaign=destaque")


class Firebase:
    """Conexão única com o Firebase (inscritos + envio), usada pelo resumo do dia e pelo aviso de escalação."""
    def __init__(self, simular):
        self.simular = simular
        self.sa = os.environ.get("FIREBASE_SA", "").strip()
        self.db = None
        self._inscritos = None

    def ok(self):
        return bool(self.sa) or self.simular

    def inscritos(self):
        if self._inscritos is None:
            if self.simular and not self.sa:
                self._inscritos = [{"id": "teste", "token": "x", "times": ["Flamengo", "Palmeiras"], "ligas": ["premier"], "destaques": True},
                                   {"id": "teste2", "token": "y", "times": [], "ligas": [], "destaques": True}]
            else:
                import firebase_admin
                from firebase_admin import credentials, firestore
                if not firebase_admin._apps:
                    firebase_admin.initialize_app(credentials.Certificate(json.loads(self.sa)))
                self.db = firestore.client()
                self._inscritos = [{"id": d.id, **d.to_dict()} for d in self.db.collection("inscritos").stream()]
            log(f"{len(self._inscritos)} inscritos")
        return self._inscritos

    def enviar(self, envios, tag, ttl):
        """envios: [(inscrito, título, texto, url)] -> quantos chegaram"""
        if self.simular:
            for p, t, c, u in envios:
                log(f"{p['id']}: {t} | {c} | {u}")
            return len(envios)
        from firebase_admin import messaging
        ok = ruins = 0
        for i in range(0, len(envios), 500):
            lote = envios[i:i + 500]
            msgs = [messaging.Message(
                token=p["token"],
                webpush=messaging.WebpushConfig(
                    headers={"Urgency": "high", "TTL": str(ttl)},
                    data={"title": t, "body": c, "url": u, "tag": tag},
                    fcm_options=messaging.WebpushFCMOptions(link=u)))
                for p, t, c, u in lote]
            resp = messaging.send_each(msgs)
            for (p, *_), r in zip(lote, resp.responses):
                if r.success:
                    ok += 1
                else:
                    nome = type(r.exception).__name__
                    if nome in ("UnregisteredError", "SenderIdMismatchError") or "not a valid FCM registration token" in str(r.exception):
                        self.db.collection("inscritos").document(p["id"]).delete()
                        ruins += 1
                    else:
                        log("falhou:", nome, str(r.exception)[:120])
        log(f"enviados {ok}, tokens vencidos apagados {ruins}")
        return ok


def resumo_do_dia(fb, cfg, estado, agora, forcar):
    nt = cfg.get("notificacoes") or {}
    if not forcar:
        if estado.get("ultimo") == agora.date().isoformat():
            return log("resumo de hoje já foi enviado")
        if not (nt.get("hora", 9) <= agora.hour < nt.get("ate", 20)):
            return log(f"resumo: fora do horário ({agora:%H:%M})")
    dados = ler(RAIZ / "dados" / "jogos.json")
    hoje = jogos_de_hoje(dados, agora)
    destaque = sorted(hoje, key=lambda j: -audiencia(cfg, j))
    destaque = [j for j in destaque if audiencia(cfg, j) >= 40][:1]
    log(f"{len(hoje)} jogos hoje; destaque: {destaque[0]['casa'] + ' x ' + destaque[0]['fora'] if destaque else 'nenhum'}")
    envios = []
    for p in fb.inscritos():
        times, ligas = set(p.get("times") or []), set(p.get("ligas") or [])
        meus = []
        for j in hoje:
            quem = (f"{j['casa']} x {j['fora']}" if j["casa"] in times and j["fora"] in times
                    else j["casa"] if j["casa"] in times else j["fora"] if j["fora"] in times else None)
            if quem or j["comp"] in ligas:
                meus.append({**j, "_time": bool(quem), "_quem": quem or (cfg["competicoes"].get(j["comp"], {}).get("curto") or j["comp"])})
        meus.sort(key=lambda x: (not x["_time"], -audiencia(cfg, x), x["_t"]))
        if not meus and not (p.get("destaques", True) and destaque):
            continue
        titulo, corpo, url = mensagem(dados, meus, destaque, len(hoje))
        envios.append((p, titulo, corpo, url))
    ok = fb.enviar(envios, "resumo-" + agora.date().isoformat(), 6 * 3600)
    if not fb.simular:
        estado.update({"ultimo": agora.date().isoformat(), "enviados": ok, "inscritos": len(fb.inscritos()),
                       "hora": agora.isoformat(timespec="minutes")})


def aviso_escalacao(fb, cfg, estado, agora):
    """Quando a escalação oficial sai (cerca de 1h antes), avisa quem segue um dos times. Uma vez por jogo."""
    arq = RAIZ / "dados" / "escalacoes.json"
    if not arq.exists():
        return
    esc = ler(arq)
    jogos = {j.get("eid"): j for j in ler(RAIZ / "dados" / "jogos.json")["jogos"] if j.get("eid")}
    feitos = set(estado.get("escalacoes", []))
    pend = []
    for eid, x in esc.items():
        ini = datetime.fromisoformat(x["inicio"]).astimezone(BRT)
        if eid in feitos or not (timedelta(minutes=-5) <= ini - agora <= timedelta(minutes=100)):
            continue
        pend.append((eid, x, ini))
    if not pend:
        return
    for eid, x, ini in pend:
        j = jogos.get(eid, {})
        url = SITE.rstrip("/") + (j.get("pg") or "/") + "?utm_source=push&utm_medium=notificacao&utm_campaign=escalacao#escalacoes"
        envios = []
        for p in fb.inscritos():
            times = set(p.get("times") or [])
            quem = [t for t in (x["time_casa"], x["time_fora"]) if t in times]
            if not quem:
                continue
            q = quem[0] if len(quem) == 1 else f"{x['time_casa']} e {x['time_fora']}"
            envios.append((p, f"📋 Saiu a escalação do {q}!" if len(quem) == 1 else f"📋 Saíram as escalações de {q}!",
                           f"{x['time_casa']} x {x['time_fora']} às {hhmm(ini)}. Veja quem joga e onde assistir.", url))
        log(f"escalação {x['time_casa']} x {x['time_fora']}: {len(envios)} avisos")
        if envios:
            fb.enviar(envios, "escalacao-" + eid, 2 * 3600)
        feitos.add(eid)
    if not fb.simular:
        estado["escalacoes"] = sorted(feitos)[-200:]


def main():
    simular = "--simular" in sys.argv
    agora = datetime.now(BRT)
    cfg = ler(RAIZ / "robo" / "config.json")
    estado = ler(ESTADO) if ESTADO.exists() else {}
    fb = Firebase(simular)
    if not fb.ok():
        return log("sem FIREBASE_SA; nada a fazer")
    resumo_do_dia(fb, cfg, estado, agora, simular or "--agora" in sys.argv)
    aviso_escalacao(fb, cfg, estado, agora)
    if not simular:
        ESTADO.write_text(json.dumps(estado, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
