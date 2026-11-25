"""Guia "Onde passa cada campeonato": quem transmite cada campeonato no Brasil.

Junta duas coisas:
- os canais reais dos jogos da agenda (quantos jogos de cada campeonato passam em cada canal nos próximos dias);
- um texto curto e conferido por campeonato, em robo/config.json -> "guia" (só o que tem fonte oficial ou jornalística).
Vira a página /onde-passa/ e uma seção no fim de cada página de campeonato.
"""
from html import escape as e

ORDEM_TIPOS = ["TV aberta", "Grátis no YouTube", "YouTube", "TV fechada", "Streaming", "Pay-per-view", "App"]
ROTULO_TIPO = {"Grátis no YouTube": "YouTube (grátis)", "YouTube": "YouTube (grátis)"}


def canais_do_campeonato(cx, k):
    """[(tipo, [(nome, n_jogos, gratis)])] dos jogos de k na agenda, do tipo mais acessível ao menos."""
    jogos = [j for j in cx.jogos if j["comp"] == k]
    conta = {}
    for j in jogos:
        for c in j.get("canais") or []:
            nome_c, tipo, _, gratis = cx.canal_info(j, c)
            tipo = ROTULO_TIPO.get(tipo, tipo) or "Outros"
            x = conta.setdefault((tipo, nome_c), [0, gratis])
            x[0] += 1
            x[1] = x[1] or gratis
    por_tipo = {}
    for (tipo, nome_c), (n, gratis) in conta.items():
        por_tipo.setdefault(tipo, []).append((nome_c, n, gratis))
    ordem = [ROTULO_TIPO.get(t, t) for t in ORDEM_TIPOS]
    tipos = sorted(por_tipo, key=lambda t: (ordem.index(t) if t in ordem else 99, t))
    return [(t, sorted(por_tipo[t], key=lambda x: (-x[1], x[0]))) for t in tipos], len(jogos)


def _resumo(cx, k, grupos):
    """Frase curta para o FAQ do Google quando não há texto conferido no config."""
    from paginas import art
    nomes = [n for _, xs in grupos for n, _, _ in xs][:6]
    if not nomes:
        return ""
    nome = cx.comp_nome(k)
    return f"Nos próximos jogos, {art(nome, 'o', 'a')} {nome} passa em " + ", ".join(nomes[:-1]) + (" e " if len(nomes) > 1 else "") + nomes[-1] + "."


def bloco(cx, k, titulo_tag="h2", com_link=False):
    """Seção de um campeonato: texto conferido + canais dos próximos jogos agrupados por tipo."""
    from paginas import art, do_, slug
    nome = cx.comp_nome(k)
    o_nome = f"{art(nome, 'o', 'a')} {nome}"
    texto = (cx.guia or {}).get(k, "")
    grupos, n = canais_do_campeonato(cx, k)
    if not texto and not grupos:
        return ""
    linhas = "".join(
        f'<li><span class="gu-t">{e(t)}</span><span class="gu-cs">'
        + "".join(f'<span class="gu-c{" gr" if gr else ""}">{e(nm)}<small>{q} {"jogo" if q == 1 else "jogos"}</small></span>' for nm, q, gr in xs)
        + "</span></li>" for t, xs in grupos)
    agenda = (f'<p class="gu-sub">Nos próximos {n} {"jogo" if n == 1 else "jogos"} da agenda:</p><ul class="gu-l">{linhas}</ul>' if grupos
              else '<p class="gu-sub">Sem jogos na agenda dos próximos dias.</p>')
    link = f'<p class="gu-mais"><a href="/campeonato/{slug(k)}/">Jogos e tabela {e(do_(nome))} ›</a></p>' if com_link else ""
    return (f'<section class="guia-c" id="onde-{slug(k)}"><{titulo_tag}>Onde assistir {e(o_nome)}</{titulo_tag}>'
            + (f"<p>{e(texto)}</p>" if texto else "") + agenda + link + "</section>")


def pagina_guia(cx):
    from paginas import art, pagina, slug
    principais = [k for k in cx.comps if cx.comps[k].get("principal")]
    outros = sorted([k for k in cx.comps if not cx.comps[k].get("principal")], key=cx.comp_nome)
    secoes, indice, faq = [], [], []
    for k in principais + outros:
        b = bloco(cx, k, "h2", com_link=True)
        if not b:
            continue
        secoes.append(b)
        indice.append(f'<a href="#onde-{slug(k)}">{e(cx.comp_nome(k))}</a>')
        resposta = (cx.guia or {}).get(k) or _resumo(cx, k, canais_do_campeonato(cx, k)[0])
        if resposta:
            faq.append({"@type": "Question", "name": f"Onde assistir {art(cx.comp_nome(k), 'o', 'a')} {cx.comp_nome(k)} ao vivo?",
                        "acceptedAnswer": {"@type": "Answer", "text": resposta}})
    corpo = ("<h1>Onde assistir o Brasileirão 2026 e outros campeonatos</h1>"
             "<p>Quem transmite cada campeonato no Brasil: TV aberta, TV fechada, streaming e os canais grátis no YouTube. "
             "Os canais de cada jogo saem da agenda do site, atualizada todo dia; os links levam sempre às páginas oficiais.</p>"
             f'<nav class="gu-idx" aria-label="Campeonatos">{"".join(indice)}</nav>' + "".join(secoes))
    ld = [{"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": faq}] if faq else None
    return pagina(cx, "/onde-passa/", "Onde assistir o Brasileirão 2026 e outros campeonatos: canais e streaming",
                  "Quem transmite o Brasileirão, a Libertadores, a Champions, a Premier League e outros campeonatos no Brasil: "
                  "TV aberta, fechada, streaming e jogos grátis no YouTube.",
                  corpo, ld, [("Início", "/"), ("Onde passa cada campeonato", "/onde-passa/")])
