# MapScout — ferramenta pessoal de prospecção B2B geolocalizada

Descobre empresas por categoria e localização, enriquece com dados públicos do
site delas, classifica a força da presença digital e prioriza quem tem maior
chance de comprar um site/landing page.

**Uso pessoal. Não é SaaS.** Sem multi-tenant, sem billing, sem créditos, sem
autenticação de usuários. Se um plano incluir qualquer uma dessas coisas, o
plano está errado.

## Stack (fixa — não substitua sem me perguntar)

Python 3.12 · FastAPI · SQLModel · SQLite · httpx (async) · selectolax ·
tldextract · arq/APScheduler · Jinja2 + HTMX · pytest + respx · ruff · mypy

## Comandos

```bash
make check      # ruff + mypy + pytest — DEVE passar antes de qualquer commit
make test       # pytest -q
make coletar    # CLI de coleta
make api        # uvicorn em dev
```

## Regras invioláveis

1. **Testes nunca acessam a rede.** Use `respx` e as fixtures de
   `tests/fixtures/`. Toda chamada externa é paga ou instável.
2. **Nunca invente nomes de campo de API externa.** Se não houver fixture real
   em `tests/fixtures/`, pare e me peça para capturar uma.
3. **Nunca leia, edite ou imprima `.env`.** Segredos só via `os.environ`.
4. Toda função pública tem type hints e uma docstring de uma linha.
5. Toda escrita no banco passa por uma função de repositório — sem SQL solto
   espalhado pelos módulos.
6. Toda chamada à Places API é registrada em `api_calls` (custo é rastreável).
7. Um commit por fatia concluída. Não commite com `make check` vermelho.
8. Ao concluir uma fatia, atualize `ROADMAP.md` com o estado e as decisões.

## Fonte de dados

  locationRestriction no searchText aceita apenas rectangle (low/high). circle só é válido em locationBias.
- **Descoberta:** Google Places API (New), endpoint `places:searchText`.
  Campos corretos: `id`, `displayName.text`, `formattedAddress`, `location`,
  `nationalPhoneNumber`, `websiteUri`, `rating`, `userRatingCount`,
  `businessStatus`, `googleMapsUri`. **Não use nomes da API legada.**
  `pageSize` máximo é 20; até 3 páginas via `nextPageToken`.
- **Enriquecimento:** site público da própria empresa. Respeitar `robots.txt`,
  máximo 5 páginas por domínio, User-Agent identificável.
- **Nunca** raspar MapLeads ou qualquer concorrente.

## Glossário do domínio

**Níveis de presença digital** (`presence_level`) — quanto menor, maior a oportunidade:

| Nível | Significado | Score base |
|---|---|---|
| 0 | sem site cadastrado | 100 |
| 1 | `business.site` / `negocio.site` (grátis do Google, descontinuado) | 95 |
| 2 | link de WhatsApp no lugar do site | 88 |
| 3 | só rede social ou agregador de links | 85 |
| 3b | subdomínio gratuito de construtor (wixsite, lovable.app, netlify.app, vercel.app, site123, webnode, weebly, blogspot, wordpress.com) | 80 |
| 4 | domínio próprio que não resolve (DNS/timeout/4xx/5xx) | 90 |
| 5 | domínio estacionado ou página vazia | 87 |
| 6 | página em marketplace de terceiro (iFood, Doctoralia...) | 75 |
| 7 | site próprio fraco (sem viewport, sem HTTPS, copyright ≤2020) | 50 |
| 8 | site próprio saudável | 10 |

Todo registro classificado guarda **nível + evidência textual** — a evidência é
usada na abordagem comercial, então precisa ser uma frase legível por humano.

**Níveis de dedupe:** `place_id` (certo, funde) > domínio registrável (alto,
funde) > telefone E.164 + mesma cidade (médio, funde) > nome+endereço similares
(médio, marca para revisão) > mesmo nome em cidades diferentes (**não funde** —
é filial).

**Score determinístico:** `base_presença × saúde_do_negócio × ticket_categoria`.
Saúde considera `userRatingCount` e `rating`; ticket é tabela editável em config.

## Regras da camada de IA

- Saída sempre em JSON validado por schema Pydantic.
- **Toda justificativa deve citar um campo real e preenchido do registro.** Se o
  campo estiver `null`, a justificativa não pode existir. Valide isso em código
  e rejeite a resposta se falhar.
- Cache por `place_id` + hash dos campos de entrada.
- Gera rascunho de abordagem. **Nunca envia mensagem.**

## Conformidade

- `blocklist` de opt-out existe desde a Fatia 3 e é consultada em toda exportação.
- Não coletar dado sensível, não enriquecer com CPF.
- Não implementar disparo em massa de WhatsApp nem verificação não oficial de número.
- Places API: `place_id` pode ser armazenado indefinidamente; demais campos
  precisam de refresh periódico (`checado_em` > 60 dias → re-checar).

## Como trabalhar comigo

- Antes de codar uma fatia: mostre o plano, os arquivos a criar e as decisões em
  aberto. **Não escreva código até eu aprovar.**
- Fatias verticais: cada uma termina em um comando que roda e produz resultado
  visível. Nunca "todos os models primeiro".
- Se uma fatia estiver crescendo demais, pare e proponha dividir.
- Prefira código óbvio a código esperto. Eu vou manter isso sozinho.
