# ROADMAP — MapScout

Fatias verticais. Cada uma termina em um comando que roda e produz resultado visível.

- [x] **Fatia 0 — Esqueleto e loop de verificação.** `make check` roda ruff + mypy estrito + pytest e passa verde.
- [ ] **Fatia 1 — Config e banco.** `config.py` lê env vars, engine SQLite, tabelas iniciais, `api_calls`, funções de repositório. Entrega: um comando cria o banco e lista as tabelas.
- [ ] **Fatia 2 — Descoberta via Places.** Cliente `places:searchText` com paginação (`pageSize` 20, até 3 páginas via `nextPageToken`), toda chamada registrada em `api_calls`. Entrega: `make coletar` grava empresas reais no banco.
- [ ] **Fatia 3 — Dedupe e blocklist.** Níveis de dedupe do glossário, tabela `blocklist`, exportação CSV que a consulta. Entrega: coleta repetida não duplica e o export respeita opt-out.
- [ ] **Fatia 4 — Classificação sem rede.** `presence_level` 0–3 a partir de `websiteUri`, com evidência textual legível. Entrega: relatório por nível.
- [ ] **Fatia 5 — Enriquecimento HTTP.** Fetch do site respeitando `robots.txt`, máximo 5 páginas por domínio, User-Agent identificável. Níveis 4, 5 e 6.
- [ ] **Fatia 6 — Qualidade do site.** Níveis 7 e 8 via selectolax (viewport, HTTPS, copyright ≤2020).
- [ ] **Fatia 7 — Score determinístico.** `base_presença × saúde_do_negócio × ticket_categoria`, tabela de ticket editável em config. Entrega: ranking ordenado.
- [ ] **Fatia 8 — Interface web.** FastAPI + Jinja2 + HTMX: lista, filtro, ordenação por score, evidência visível. Entrega: `make api`.
- [ ] **Fatia 9 — Camada de IA.** Saída JSON validada por Pydantic, justificativa obrigatoriamente citando campo real e preenchido, cache por `place_id` + hash. Gera rascunho, nunca envia.
- [ ] **Fatia 10 — Refresh e agendamento.** `checado_em` > 60 dias re-checa; APScheduler; exportação final.

## Estado e decisões

### Fatia 0 — concluída em 2026-08-26

`make check` verde: ruff (E, F, W, I, N, UP, B, SIM, ANN, D, RUF) + mypy `strict` + 1 teste.

Decisões tomadas:

- **uv como gerenciador de ambiente.** Não estava na stack do CLAUDE.md. Entrou porque o Python 3.12 exigido não existia na máquina (só 3.13) e o uv resolve pin de interpretador, venv e lock de uma vez. Interpretador travado em 3.12.13 via `.python-version` e `requires-python = ">=3.12,<3.13"`.
- **GNU make instalado** (`ezwinports.make` 4.4.1) para que os quatro comandos do CLAUDE.md fossem literais no Windows, em vez de trocar por um task runner Python.
- **`ANN` e `D` ligados no ruff.** A regra 4 do CLAUDE.md (type hints + docstring em toda função pública) passa a ser checada por máquina. Achado de lint não se silencia com `# noqa`: ou se corrige, ou a regra sai do `select` com justificativa.
- **APScheduler no lugar de `arq`.** O CLAUDE.md aceita os dois; APScheduler roda in-process com SQLite e não exige Redis. Já é dependência, será usado na Fatia 10.
- **`repositories/` é pacote, não módulo**, com um arquivo por tabela (`businesses`, `api_calls`, `blocklist`), para sustentar a regra 5 conforme o domínio cresce.
- **`cli.py` e `web/app.py` têm stub mínimo.** Sem eles, `make coletar` e `make api` quebrariam e o loop de verificação ficaria decorativo já no primeiro commit.
- **`.claude/settings.json` nega `.env` e `.env.*`** — inclusive `.env.example`, que por isso foi criado antes do settings. Alterações futuras no template são manuais.
