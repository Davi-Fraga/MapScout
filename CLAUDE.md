# MapScout — ferramenta pessoal de prospecção B2B geolocalizada

Descobre empresas por categoria e localização, enriquece com dados públicos do
site delas, classifica a força da presença digital e prioriza quem tem maior
chance de comprar um site/landing page.

**Uso pessoal. Não é SaaS.** Sem multi-tenant, sem billing, sem créditos, sem
autenticação de usuários. Se um plano incluir qualquer uma dessas coisas, o
plano está errado.

## Ambiente

Windows. Terminal PowerShell ou Git Bash. Scripts e comandos do Makefile devem
funcionar nos dois — não gere script que dependa de utilitário só-Unix sem me
avisar. Repositório com `.gitattributes` usando `* text=auto eol=lf`.

## Stack (fixa — não substitua sem me perguntar)

Python 3.12 · uv · FastAPI · SQLModel · SQLite · httpx (async) · selectolax ·
tldextract · APScheduler · Jinja2 + HTMX · pytest + respx · ruff · mypy

## Comandos

```bash
make check      # ruff + mypy + pytest — DEVE passar antes de qualquer commit
make test       # pytest -q
make coletar    # CLI de coleta
make api        # uvicorn em dev
```

## Regras invioláveis

0. **Sempre dê `git pull` antes de qualquer alteração ou análise.** Há múltiplos
   devs trabalhando no repositório. O código local DEVE estar atualizado com
   `origin/main` antes de começar qualquer análise ou alteração.
1. **Testes nunca acessam a rede.** Use `respx` e as fixtures de
   `tests/fixtures/`. Toda chamada externa é paga ou instável.
2. **Nunca invente nomes de campo de API externa.** Se não houver fixture real
   em `tests/fixtures/`, pare e me peça para capturar uma.
3. **Nunca leia, edite ou imprima `.env`.** Segredos só via `os.environ`.
4. Toda função pública tem type hints e uma docstring de uma linha.
5. Toda escrita no banco passa por uma função de repositório — sem SQL solto
   espalhado pelos módulos.
6. Toda chamada à Places API é registrada em `api_calls`, e o runner para
   sozinho ao atingir o limite diário definido no config. Custo é rastreável e
   tem freio no código, não só no console do Google.
7. Um commit por bloco concluído. Não commite com `make check` vermelho.
8. Ao concluir um bloco, atualize `ROADMAP.md` com o estado e as decisões.

## Fonte de dados

- **Descoberta:** Google Places API (New), endpoint `places:searchText`.
  · Campos corretos: `id`, `displayName.text`, `formattedAddress`, `location`,
    `nationalPhoneNumber`, `websiteUri`, `rating`, `userRatingCount`,
    `businessStatus`, `googleMapsUri`. **Não use nomes da API legada.**
  · `pageSize` máximo é 20; até 3 páginas via `nextPageToken`.
  · **`locationRestriction` aceita APENAS `rectangle`** (`low`/`high`).
    `circle` só é válido em `locationBias`. O grid gera retângulos.
  · `low` é o canto sudoeste, `high` o nordeste. Em latitude negativa (Brasil),
    `low` é o número mais negativo.
- **Enriquecimento:** site público da própria empresa. Respeitar `robots.txt`,
  máximo 5 páginas por domínio, User-Agent identificável.
- **Nunca** raspar MapLeads ou qualquer concorrente.

## Glossário do domínio

**Níveis de presença digital** (`presence_level`). A escala é monotônica:
nível menor = oportunidade maior. Se você precisar inserir um caso novo,
renumere a tabela inteira em vez de criar sufixo tipo "3b".

| Nível | Significado | Score base |
|---|---|---|
| 0 | sem site cadastrado | 100 |
| 1 | `business.site` / `negocio.site` (grátis do Google, descontinuado) | 95 |
| 2 | domínio próprio que não resolve (DNS/timeout/4xx/5xx) | 90 |
| 3 | link de WhatsApp no lugar do site | 88 |
| 4 | domínio estacionado ou página praticamente vazia | 87 |
| 5 | só rede social ou agregador de links | 85 |
| 6 | subdomínio gratuito de construtor de site | 80 |
| 7 | página em marketplace de terceiro | 75 |
| 8 | site próprio fraco (sem viewport, sem HTTPS, copyright ≤2020) | 50 |
| 9 | site próprio saudável | 10 |

Listas de domínios ficam em módulo de constantes separado e editável:
- **Nível 5 (social):** instagram, facebook, fb.me, linktr.ee, beacons.ai,
  bio.link, campsite.bio, tiktok, youtube, x.com, twitter
- **Nível 6 (construtor grátis):** wixsite.com, lovable.app, netlify.app,
  vercel.app, site123.me, webnode.page, weebly.com, blogspot.com,
  wordpress.com, github.io, glitch.me, replit.app
- **Nível 7 (marketplace):** doctoralia.com.br, mechameaqui.com.br, ifood.com.br,
  booking.com, tripadvisor, olx.com.br, elo7.com.br, mercadolivre.com.br,
  getninjas.com.br, gympass.com, zenklub.com.br, airbnb.com, rappi.com.br

Todo registro classificado guarda **nível + evidência textual**. A evidência é
usada na abordagem comercial: precisa ser uma frase que eu mandaria para o
cliente, não um código interno. Bom: "o link do site no perfil do Google está
fora do ar (erro 404)". Ruim: "PRESENCE_LEVEL_2_DNS_FAIL".

**Níveis de dedupe:** `place_id` (certeza, funde) > domínio registrável (alta,
funde) > telefone E.164 + mesma cidade (média, funde) > nome+endereço similares
(média, marca para revisão) > mesmo nome em cidades diferentes (**não funde** —
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

- `blocklist` de opt-out existe desde o Bloco B e é consultada em toda exportação.
- Não coletar dado sensível, não enriquecer com CPF.
- Não implementar disparo em massa de WhatsApp nem verificação não oficial de número.
- Places API: `place_id` pode ser armazenado indefinidamente; demais campos
  precisam de refresh periódico (`checado_em` > 60 dias → re-checar).

## Como trabalhar comigo

- Antes de codar um bloco: mostre o plano, os arquivos a criar e as decisões em
  aberto. **Não escreva código até eu aprovar.**
- Nos pontos marcados `⏸ CHECKPOINT` no prompt, **pare de verdade** e espere
  minha resposta. Não siga por conta própria mesmo que o próximo passo pareça
  óbvio.
- Blocos verticais: cada um termina em um comando que roda e produz resultado
  visível. Nunca "todos os models primeiro".
- Se um bloco estiver crescendo demais, pare e proponha dividir.
- Prefira código óbvio a código esperto. Eu vou manter isso sozinho.