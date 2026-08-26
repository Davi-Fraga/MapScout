# ROADMAP — MapScout

Blocos verticais. Cada um termina em um comando que roda e produz resultado visível.

- [x] **Bloco 1 — Esqueleto e loop de verificação.** `make check` roda ruff + mypy estrito + pytest e passa verde.
- [x] **Bloco 2 — Coleta.** Cliente da Places API (`places:searchText`), banco SQLite, repositório e CLI. Entrega: `make coletar` grava empresas reais e registra o custo em `api_calls`.
- [ ] **Bloco 3 — Dedupe, blocklist e exportação.** Níveis de dedupe do glossário, tabela `blocklist` de opt-out consultada em toda exportação, export CSV.
- [ ] **Bloco 4 — Enriquecimento e classificação de presença.** Fetch do site respeitando `robots.txt` (máx. 5 páginas, User-Agent identificável) e atribuição de `presence_level` 0–8 com evidência textual.
- [ ] **Bloco 5 — Score e interface web.** `base_presença × saúde_do_negócio × ticket_categoria` e a tela FastAPI + Jinja2 + HTMX com filtro e ordenação.
- [ ] **Bloco 6 — Camada de IA e refresh.** Rascunho de abordagem em JSON validado por Pydantic com citação obrigatória de campo preenchido, cache por `place_id` + hash, e re-checagem de `checado_em` > 60 dias via APScheduler.

## Estado e decisões

### Bloco 1 — concluído em 2026-08-26

`make check` verde: ruff (E, F, W, I, N, UP, B, SIM, ANN, D, RUF) + mypy `strict` + pytest.

- **uv como gerenciador de ambiente.** Não estava na stack do CLAUDE.md. Entrou porque o Python 3.12 exigido não existia na máquina (só 3.13) e o uv resolve pin de interpretador, venv e lock de uma vez. Interpretador travado em 3.12.13.
- **GNU make instalado** (`ezwinports.make` 4.4.1) para que os quatro comandos do CLAUDE.md fossem literais no Windows.
- **`ANN` e `D` ligados no ruff.** A regra 4 do CLAUDE.md vira checagem de máquina. Achado de lint não se silencia com `# noqa`: ou se corrige, ou a regra sai do `select` com justificativa.
- **APScheduler no lugar de `arq`.** O CLAUDE.md aceita os dois; APScheduler roda in-process e não exige Redis.

### Bloco 2 — concluído em 2026-08-26

Coleta ponta a ponta com 23 testes, zero acesso à rede.

- **Layout renomeado** para bater com a especificação do bloco: `places/` virou `sources/places_api.py`; `db.py`, `models.py` e `repositories/` viraram o pacote `db/` com `models.py`, `session.py` e `repo.py`.
- **Modelos derivados do fixture real**, não do CLAUDE.md. `tests/fixtures/places_searchtext.json` tem 20 lugares; `websiteUri` aparece em 15 deles e é o único campo comprovadamente opcional. Os schemas Pydantic usam `alias` para que o nome real da API (`displayName`, `nationalPhoneNumber`, ...) exista num lugar só e seja auditável.
- **`types` e `primaryTypeDisplayName` persistidos** mesmo não estando na lista do CLAUDE.md: estão no fixture, e `primaryTypeDisplayName.text` é o rótulo de categoria que o score do Bloco 5 vai precisar.
- **`locationRestriction` com `rectangle`**, conforme a restrição registrada no CLAUDE.md (`circle` só vale em `locationBias`). A CLI recebe `--raio-m` e `retangulo_do_raio()` circunscreve o círculo. Efeito colateral aceito: os cantos da caixa vão ~41% além do raio pedido.
- **`--cidade` só compõe o `textQuery`** (`"dentista em Campinas"`), sem coluna no banco — a spec do `Place` é "campos do fixture + `coletado_em` + `checado_em`". O Bloco 3 precisa da cidade para a regra de dedupe "telefone E.164 + mesma cidade" e vai adicionar a coluna via `ALTER TABLE`.
- **Uma linha em `api_calls` por tentativa HTTP**, não por página. Um 429 seguido de sucesso grava duas linhas — é o que responde "quanto gastei" com honestidade.
- **Datas gravadas em UTC sem `tzinfo`.** O SQLite descarta timezone; um teste pegou isso na hora. A normalização acontece no repositório (`para_utc_naive`), que é a fronteira de persistência, para que a comparação de `checado_em > 60 dias` do Bloco 6 não estoure com naive vs aware.
- **Páginas 2 e 3 nos testes reusam o mesmo fixture real**, com o `nextPageToken` removido na última. Remover uma chave não inventa nada, e os `place_id` repetidos exercitam o upsert idempotente de graça.
- **`argparse` na CLI**, não `typer`/`click`, para não declarar dependência fora da stack.
