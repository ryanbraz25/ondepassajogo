# Onde Passa Jogo (ondepassajogo.com.br): site que se atualiza sozinho

Site com os jogos dos próximos 14 dias: horário de Brasília, campeonato e o canal oficial de cada partida, com botão que leva direto para a transmissão.

## Como funciona

```
a cada 3 horas (GitHub Actions, grátis)
   │
   ├─ TheSportsDB ........ jogos e horários das principais ligas
   ├─ TheSportsDB TV ..... canais do Brasil (só com chave premium)
   ├─ YouTube Data API ... lives agendadas da CazéTV, ge tv, Canal GOAT
   │                        (link direto da transmissão no jogo)
   └─ dados/verificados.json  jogos conferidos (checagem diária), têm prioridade
   │
   ▼
robo/atualizar.py → dados/jogos.json + site/index.html → publicado no GitHub Pages
```

Se todas as fontes falharem, o robô mantém a agenda anterior, para o site nunca ficar vazio.

## Colocar no ar (uma vez só, uns 15 minutos)

1. Crie uma conta grátis em github.com.
2. Crie um repositório **público** (ex.: `agenda-futebol`). Repositório público não consome minutos do plano.
3. Envie todos os arquivos desta pasta para o repositório, mantendo as pastas (`robo`, `dados`, `site`, `.github`). Pelo site do GitHub: "Add file" → "Upload files" → arraste a pasta inteira.
4. No repositório: **Settings → Pages → Source: GitHub Actions**.
5. **Actions → Atualizar agenda → Run workflow**. Em 1 ou 2 minutos o site aparece no endereço que o GitHub mostra em Settings → Pages.

Pronto: daí em diante ele roda sozinho a cada 3 horas.

## Chaves opcionais (Settings → Secrets and variables → Actions → New repository secret)

| Nome | Para quê | Custo |
|---|---|---|
| `YOUTUBE_API_KEY` | Link direto das lives da CazéTV, ge tv, Canal GOAT | Grátis (cota diária do Google) |
| `THESPORTSDB_KEY` | Mais ligas e canais de TV por jogo | Plano pago da TheSportsDB |
| `AMAZON_TAG` | Sua tag de Associado Amazon no link do Prime Video | Grátis |

Para a chave do YouTube: console.cloud.google.com → criar projeto → "Biblioteca" → ativar **YouTube Data API v3** → "Credenciais" → "Criar chave de API".

Sem nenhuma chave o robô já funciona com a chave gratuita da TheSportsDB e com o `dados/verificados.json`.

## Arquivos

| Arquivo | O que é |
|---|---|
| `site/template.html` | Visual do site (o robô injeta os dados nele) |
| `robo/atualizar.py` | O robô (só Python padrão, sem instalar nada) |
| `robo/config.json` | Canais e seus links oficiais, ligas, canais do YouTube monitorados |
| `dados/verificados.json` | Jogos conferidos; têm prioridade sobre as APIs |
| `dados/jogos.json` | Agenda final gerada pelo robô (não editar) |
| `.github/workflows/atualizar.yml` | Agendamento a cada 3 horas e publicação |

## Ajustes comuns

- **Trocar o link de um canal**: edite `url` em `robo/config.json`.
- **Adicionar um canal do YouTube para monitorar**: inclua em `youtube.canais` no `config.json`.
- **Adicionar uma liga**: inclua em `competicoes`, com o nome exato da liga na TheSportsDB.
- **Domínio próprio** (ex.: `ondepassaojogo.com.br`): registre no registro.br e configure em Settings → Pages → Custom domain.

## Testar no computador

```
python robo/atualizar.py --offline   # só monta o site com os dados verificados
python robo/atualizar.py             # busca nas APIs
```
Depois abra `site/index.html` no navegador.

## Sugestões dos visitantes ("Sugerir onde está passando")

1. Em forms.google.com crie um formulário "Sugestões Onde Passa Jogo" com 3 perguntas de resposta curta, nesta ordem: **Jogo**, **Canal ou plataforma**, **Link**.
2. Menu ⋮ → "Gerar link pré-preenchido" → preencha qualquer coisa → "Copiar link". O link traz `entry.NÚMERO` de cada pergunta.
3. Em `robo/config.json`, no bloco `sugestoes`, cole o endereço do formulário em `form_url` e cada `entry.NÚMERO` em `campos` (jogo, canal, link).
4. Em "Respostas", ligue a planilha do Google. A checagem automática lê essa planilha, confere se a transmissão é oficial ou autorizada e publica só as aprovadas.

Links de sites piratas conhecidos são recusados na hora, no próprio site.
