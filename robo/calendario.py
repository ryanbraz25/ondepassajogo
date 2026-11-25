"""Agenda no calendário do celular: um arquivo iCalendar (.ics) por time e por campeonato.

A pessoa assina o link (Google Agenda, iPhone, Outlook) e os jogos aparecem e se atualizam sozinhos,
com horário certo, estádio, onde passa e o link da página do jogo.

Arquivos: site/agenda/<time>.ics e site/agenda/campeonato/<campeonato>.ics (RFC 5545).
O carimbo de cada jogo (DTSTAMP/LAST-MODIFIED) só muda quando o jogo muda (estado em
dados/calendario.json), para o arquivo não mudar à toa a cada hora.
"""
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PASTA = RAIZ / "site" / "agenda"
ESTADO = RAIZ / "dados" / "calendario.json"
URL = "https://ondepassajogo.com.br"
DOMINIO = "ondepassajogo.com.br"
UTC = timezone.utc
BRT = timezone(timedelta(hours=-3))
DURACAO = timedelta(hours=2)
DIAS_TIME = 45   # resultados recentes que ficam na agenda do time
DIAS_COMP = 10   # e na do campeonato (que tem muito mais jogos)
ATUALIZAR = "PT6H"  # de quanto em quanto tempo o calendário deve buscar de novo


def log(*a):
    print("[agenda]", *a, flush=True)


# ---------------------------------------------------------------- iCalendar (RFC 5545)
def texto(s):
    """Escapa um valor de texto: barra invertida, ponto e vírgula, vírgula e quebra de linha."""
    return (str(s).replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,")
            .replace("\r\n", "\\n").replace("\n", "\\n"))


def dobrar(linha):
    """Linhas de no máximo 75 octetos; a continuação começa com um espaço (sem partir letra acentuada)."""
    b = linha.encode("utf-8")
    if len(b) <= 75:
        return linha
    partes, atual, tam, limite = [], "", 0, 75
    for ch in linha:
        n = len(ch.encode("utf-8"))
        if tam + n > limite:
            partes.append(atual)
            atual, tam, limite = "", 0, 74  # as linhas seguintes já gastam 1 octeto com o espaço
        atual += ch
        tam += n
    partes.append(atual)
    return "\r\n ".join(partes)


def utc(dt):
    return dt.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")


def calendario(nome, descricao, eventos):
    linhas = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Onde Passa Jogo//Agenda de jogos//PT-BR",
              "CALSCALE:GREGORIAN", "METHOD:PUBLISH", f"X-WR-CALNAME:{texto(nome)}", f"X-WR-CALDESC:{texto(descricao)}",
              "X-WR-TIMEZONE:America/Sao_Paulo", f"REFRESH-INTERVAL;VALUE=DURATION:{ATUALIZAR}", f"X-PUBLISHED-TTL:{ATUALIZAR}"]
    for ev in eventos:
        linhas += ["BEGIN:VEVENT", *ev, "END:VEVENT"]
    linhas.append("END:VCALENDAR")
    return "\r\n".join(dobrar(l) for l in linhas) + "\r\n"


# ---------------------------------------------------------------- jogos
def uid(j):
    """Igual enquanto o jogo for o mesmo, mesmo se mudar de horário (o calendário atualiza em vez de duplicar)."""
    if j.get("eid"):
        return f"espn-{j['eid']}@{DOMINIO}"
    base = f"{j['comp']}|{j['casa']}|{j['fora']}|{j['inicio'][:7]}"
    return hashlib.sha1(base.encode()).hexdigest()[:20] + "@" + DOMINIO


def _evento(cx, j, pg, carimbos, agora):
    ini = datetime.fromisoformat(j["inicio"])
    placar = j.get("placar")
    titulo = (f"{j['casa']} {placar['casa']} x {placar['fora']} {j['fora']}" if placar else f"{j['casa']} x {j['fora']}")
    comp = cx.comp_nome(j["comp"])
    desc = [comp + (f" · {j['rodada']}" if j.get("rodada") else "")]
    if not placar:
        canais = [cx.canal_info(j, c) for c in j.get("canais", [])]
        canais.sort(key=lambda c: not c[3])
        if canais:
            desc.append("Onde passa: " + ", ".join(c[0] + (" (grátis)" if c[3] else "") for c in canais)
                        + (" (a confirmar)" if j.get("status") == "a_confirmar" else ""))
        else:
            desc.append("Onde passa: canais ainda não anunciados")
        if j.get("nota"):
            desc.append(j["nota"])
    link = URL + pg if pg else ""
    if link:  # jogo antigo pode não ter mais página no site
        desc.append(("Detalhes e onde assistir: " if not placar else "Detalhes do jogo: ") + link)
    adiado = (j.get("nota") or "") in ("Adiado", "Cancelado")
    status = "CANCELLED" if adiado else "TENTATIVE" if j.get("status") == "a_confirmar" else "CONFIRMED"
    corpo = [f"SUMMARY:{texto(titulo)}", f"DTSTART:{utc(ini)}", f"DTEND:{utc(ini + DURACAO)}",
             f"DESCRIPTION:{texto(chr(10).join(desc))}", f"STATUS:{status}", "TRANSP:TRANSPARENT",
             f"CATEGORIES:{texto(comp)}"] + ([f"URL:{link}"] if link else [])
    if j.get("local"):
        corpo.insert(3, f"LOCATION:{texto(j['local'])}")
    u = uid(j)
    h = hashlib.sha1("\n".join(corpo).encode()).hexdigest()[:16]
    ant = carimbos.get(u)
    if not ant or ant[0] != h:
        carimbos[u] = ant = [h, utc(agora), ini.date().isoformat()]
    return [f"UID:{u}", f"DTSTAMP:{ant[1]}", f"LAST-MODIFIED:{ant[1]}", *corpo]


def _gravar(arq, conteudo):
    if arq.exists() and arq.read_bytes() == conteudo.encode("utf-8"):
        return False
    arq.parent.mkdir(parents=True, exist_ok=True)
    arq.write_bytes(conteudo.encode("utf-8"))
    return True


def gerar(cx, times, existentes, slug, caminho_jogo):
    """times: nomes dos times que têm página. existentes: caminhos de páginas de jogo que estão no ar."""
    agora = datetime.now(UTC)
    try:
        estado = json.loads(ESTADO.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        estado = {}
    carimbos = estado.get("carimbos", {})

    # agenda (com canais) + resultados recentes do histórico, sem repetir o mesmo jogo
    jogos, vistos = [], set()
    for j in cx.jogos:
        if "A definir" in (j["casa"], j["fora"]):
            continue
        jogos.append(j)
        vistos.add(j.get("eid") or uid(j))
    corte = (agora - timedelta(days=DIAS_TIME)).isoformat()
    for eid, x in (cx.hist.get("jogos") or {}).items():
        if eid not in vistos and x.get("inicio", "") >= corte:
            jogos.append({"eid": eid, **x})
    jogos.sort(key=lambda j: j["inicio"])
    pg = {}
    for j in jogos:
        cam = caminho_jogo(j)
        pg[id(j)] = cam if cam in existentes else ""

    feitos, mudaram = set(), 0
    por_time = {}
    for j in jogos:
        for t in (j["casa"], j["fora"]):
            por_time.setdefault(t, []).append(j)
    for t in sorted(times):
        js = por_time.get(t, [])
        evs = [_evento(cx, j, pg[id(j)], carimbos, agora) for j in js]
        nome = f"Jogos do {t} · Onde Passa Jogo"
        desc = f"Jogos do {t} com horário de Brasília e onde assistir. Atualiza sozinho: {URL}/time/{slug(t)}/"
        arq = PASTA / f"{slug(t)}.ics"
        mudaram += _gravar(arq, calendario(nome, desc, evs))
        feitos.add(arq)
    corte_c = (agora - timedelta(days=DIAS_COMP)).isoformat()
    for k in cx.comps:
        js = [j for j in jogos if j["comp"] == k and j["inicio"] >= corte_c]
        if not js:
            continue
        nome = f"{cx.comp_nome(k)} · Onde Passa Jogo"
        desc = f"Jogos {cx.comp_nome(k)} com horário de Brasília e onde assistir. {URL}/campeonato/{slug(k)}/"
        arq = PASTA / "campeonato" / f"{slug(k)}.ics"
        mudaram += _gravar(arq, calendario(nome, desc, [_evento(cx, j, pg[id(j)], carimbos, agora) for j in js]))
        feitos.add(arq)
    # times e campeonatos que saíram do site
    for arq in list(PASTA.glob("*.ics")) + list((PASTA / "campeonato").glob("*.ics")):
        if arq not in feitos:
            arq.unlink()
    # carimbos de jogos que já saíram de todas as agendas
    limite = (agora - timedelta(days=DIAS_TIME + 5)).date().isoformat()
    estado["carimbos"] = {u: c for u, c in carimbos.items() if c[2] >= limite}
    ESTADO.write_text(json.dumps(estado, ensure_ascii=False, separators=(",", ":"), sort_keys=True), encoding="utf-8")
    log(f"{len(feitos)} agendas (.ics), {mudaram} mudaram")
    return {arq.stem for arq in feitos if arq.parent == PASTA}, {arq.stem for arq in feitos if arq.parent != PASTA}


def links(caminho):
    """Endereços para assinar o .ics em cada app de calendário."""
    https = URL + caminho
    webcal = "webcal://" + DOMINIO + caminho
    from urllib.parse import quote
    return {"google": "https://calendar.google.com/calendar/render?cid=" + quote(webcal, safe=""),
            "apple": webcal,
            "outlook": "https://outlook.live.com/calendar/0/addfromweb?url=" + quote(https, safe=""),
            "url": https}


# ---------------------------------------------------------------- botões nas páginas
ICO_AGENDA = ('<svg width="20" height="20" viewBox="0 0 24 24" aria-hidden="true"><path d="M5 6h14v14H5zM5 10h14M9 3.5v4M15 3.5v4" '
              'fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>'
              '<path d="M12 12.5v5M9.5 15h5" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>')
ICO_SINO = ('<svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true"><path d="M6 17V11a6 6 0 0 1 12 0v6l1.6 2H4.4Z" '
            'fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/><path d="M10 21.5h4" stroke="currentColor" '
            'stroke-width="2" stroke-linecap="round"/></svg>')


def _e(s):
    from html import escape
    return escape(str(s), quote=True)


def botao_agenda(caminho, quem):
    """Menu "Adicionar à minha agenda" (details/summary: abre sem JavaScript). caminho = /agenda/....ics"""
    l = links(caminho)
    return (f'<details class="agd"><summary>{ICO_AGENDA}Adicionar à minha agenda</summary><div class="agd-op">'
            f'<p>Os jogos {_e(quem)} entram na agenda do celular e se atualizam sozinhos, com horário e onde passa.</p>'
            f'<a href="{_e(l["google"])}" target="_blank" rel="noopener" data-app="google">Google Agenda<small>Android e computador</small></a>'
            f'<a href="{_e(l["apple"])}" data-app="apple">iPhone, iPad e Mac<small>Calendário da Apple</small></a>'
            f'<a href="{_e(l["outlook"])}" target="_blank" rel="noopener" data-app="outlook">Outlook<small>Hotmail e Microsoft 365</small></a>'
            f'<button type="button" data-copiar="{_e(l["url"])}">Copiar o link<small>Para outros apps de agenda</small></button>'
            '</div></details>')


def botao_lembrete(caminho_jogo, inicio, grande=False):
    """Sino "Avisar 1 hora antes" (o lembretes.js mostra só onde dá para receber aviso e só antes do jogo)."""
    return (f'<button class="lemb{" grande" if grande else ""}" type="button" data-lemb="{_e(caminho_jogo)}" data-ini="{_e(inicio)}" '
            f'aria-pressed="false" aria-label="Avisar 1 hora antes do jogo" title="Avisar 1 hora antes do jogo" hidden>{ICO_SINO}</button>')
