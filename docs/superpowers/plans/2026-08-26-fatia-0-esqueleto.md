# Fatia 0 — Esqueleto e loop de verificação — Plano de implementação

> **Para executores:** SUB-SKILL OBRIGATÓRIA: use superpowers:subagent-driven-development ou superpowers:executing-plans para executar tarefa a tarefa. Os passos usam checkbox (`- [ ]`).

**Objetivo:** Deixar `make check` (ruff + mypy estrito + pytest) rodando verde sobre um esqueleto de pacote vazio, sem nenhuma lógica de negócio.

**Arquitetura:** Layout `src/`, projeto gerenciado por `uv` (lockfile + venv), pacote `mapscout` com submódulos criados apenas como arquivos de docstring. Toda a qualidade é imposta por configuração no `pyproject.toml` — ruff com regras de docstring (`D`) e anotação (`ANN`) ligadas para que as regras 4 do CLAUDE.md sejam checadas por máquina, não por disciplina.

**Tech Stack:** Python 3.12 · uv · FastAPI · SQLModel · httpx · selectolax · tldextract · APScheduler · Jinja2 · pytest + respx · ruff · mypy · GNU make

**Spec:** `CLAUDE.md` na raiz (seções "Stack", "Comandos", "Regras invioláveis", "Como trabalhar comigo") + o enunciado da Fatia 0 na conversa de 2026-08-26.

## Restrições globais

- Python **3.12** (`requires-python = ">=3.12,<3.13"`). A máquina só tem 3.13 — ver Decisão D1.
- Stack fixa do CLAUDE.md; nenhuma substituição sem aprovação.
- **Nenhuma lógica de negócio nesta fatia.** Módulos contêm apenas docstring.
- **Nunca ler, editar ou imprimir `.env`.**
- `make check` deve passar antes de qualquer commit.
- Um commit por fatia concluída (esta fatia = 1 commit).

---

## Decisões (aprovadas em 2026-08-26, antes da execução)

| # | Decisão | Alternativa recusada |
|---|---|---|
| D1 | `uv python install 3.12` + `.python-version` + `requires-python = ">=3.12,<3.13"` | rodar no 3.13 já instalado |
| D2 | `winget install ezwinports.make` | trocar `make` por poethepoet |
| D3 | deny amplo em `.env.*`, com `.env.example` criado antes do `settings.json` | denyar só `.env` e `.env.local` |
| D4 | APScheduler, não `arq` | `arq` (exigiria Redis) |
| D5 | stub mínimo em `cli.py` e `web/app.py` | deixar os dois só com docstring |
| D6 | `git init -b main`; camada de IA versionada (repo pessoal) | — |

O racional de cada uma está registrado em `ROADMAP.md`, seção "Estado e decisões".

---

## Estrutura de arquivos

| Arquivo | Responsabilidade |
|---|---|
| `pyproject.toml` | metadados, dependências, config de ruff/mypy/pytest |
| `.python-version` | pin 3.12 para o uv |
| `.gitignore` | `.env`, `.venv`, `__pycache__`, `*.db`, caches de ferramenta |
| `.env.example` | template dos dois segredos, sem valores |
| `Makefile` | `check`, `test`, `lint`, `types`, `coletar`, `api` |
| `.claude/settings.json` | deny de `.env`/`git push`/`rm -rf`; allow do loop de verificação |
| `ROADMAP.md` | as 11 fatias, só a 0 marcada |
| `src/mapscout/__init__.py` | `__version__` — única coisa com valor nesta fatia |
| `src/mapscout/config.py` | leitura de env vars (vazio) |
| `src/mapscout/db.py` | engine/sessão SQLite (vazio) |
| `src/mapscout/models.py` | tabelas SQLModel (vazio) |
| `src/mapscout/repositories/__init__.py` | fronteira única de escrita no banco (regra 5) |
| `src/mapscout/repositories/businesses.py` | (vazio) |
| `src/mapscout/repositories/api_calls.py` | (vazio) — regra 6 |
| `src/mapscout/repositories/blocklist.py` | (vazio) — Fatia 3 |
| `src/mapscout/places/client.py` | httpx → `places:searchText` (vazio) |
| `src/mapscout/places/schemas.py` | Pydantic da resposta Places New (vazio) |
| `src/mapscout/enrichment/fetcher.py` | httpx + robots.txt (vazio) |
| `src/mapscout/enrichment/parser.py` | selectolax (vazio) |
| `src/mapscout/classification/presence.py` | `presence_level` + evidência (vazio) |
| `src/mapscout/dedupe.py` | níveis de dedupe (vazio) |
| `src/mapscout/scoring.py` | score determinístico (vazio) |
| `src/mapscout/ai/schemas.py` | schema Pydantic da saída de IA (vazio) |
| `src/mapscout/ai/client.py` | chamada + validação de citação (vazio) |
| `src/mapscout/ai/cache.py` | cache por `place_id` + hash (vazio) |
| `src/mapscout/web/app.py` | FastAPI + Jinja2/HTMX |
| `src/mapscout/cli.py` | entrada da CLI |
| `tests/conftest.py` | fixtures compartilhadas (vazio por ora) |
| `tests/test_smoke.py` | o teste trivial |
| `tests/fixtures/.gitkeep` | onde as fixtures reais de API vão morar (regra 1 e 2) |

---

### Tarefa 1: Base do projeto e ambiente reproduzível

**Files:**
- Create: `pyproject.toml`, `.python-version`, `.gitignore`, `.env.example`

**Interfaces:**
- Consumes: nada.
- Produces: um venv em `.venv` com todas as deps e o pacote `mapscout` instalado em modo editável; `uv run <cmd>` funcionando.

- [ ] **Passo 1: `git init` e branch**

```bash
cd /c/Dev/MapScout
git init -b main
```

- [ ] **Passo 2: instalar Python 3.12 e fixá-lo** (decisão D1)

```bash
uv python install 3.12
echo "3.12" > .python-version
```

- [ ] **Passo 3: escrever `pyproject.toml`**

```toml
[project]
name = "mapscout"
version = "0.1.0"
description = "Prospecção B2B geolocalizada — ferramenta pessoal"
requires-python = ">=3.12,<3.13"
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.32",
    "sqlmodel>=0.0.22",
    "httpx>=0.28",
    "selectolax>=0.3.27",
    "tldextract>=5.1",
    "apscheduler>=3.11",
    "jinja2>=3.1",
]

[project.scripts]
mapscout = "mapscout.cli:main"

[dependency-groups]
dev = [
    "pytest>=8.3",
    "pytest-asyncio>=0.24",
    "respx>=0.22",
    "ruff>=0.8",
    "mypy>=1.13",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/mapscout"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-q"
asyncio_mode = "auto"

[tool.ruff]
line-length = 88
target-version = "py312"
src = ["src", "tests"]

[tool.ruff.lint]
select = ["E", "F", "W", "I", "N", "UP", "B", "SIM", "ANN", "D", "RUF"]

[tool.ruff.lint.pydocstyle]
convention = "google"

[tool.ruff.lint.per-file-ignores]
"tests/**" = ["D"]

[tool.mypy]
python_version = "3.12"
strict = true
files = ["src", "tests"]
mypy_path = "src"
explicit_package_bases = true
warn_unreachable = true
```

- [ ] **Passo 4: escrever `.gitignore`**

```gitignore
.env
.env.local
.venv/
__pycache__/
*.py[cod]
*.db
*.sqlite3
.pytest_cache/
.mypy_cache/
.ruff_cache/
dist/
build/
*.egg-info/
```

- [ ] **Passo 5: escrever `.env.example`** — antes do settings.json, por causa da decisão D3

```dotenv
# Copie para .env e preencha. O .env nunca é versionado nem lido pelo Claude.
GOOGLE_MAPS_API_KEY=
DATABASE_URL=sqlite:///./mapscout.db
```

- [ ] **Passo 6: sincronizar e verificar a versão do interpretador**

Rode: `uv sync && uv run python -c "import sys; print(sys.version)"`
Esperado: imprime `3.12.x`. Se imprimir 3.13, o `.python-version` não pegou — pare e me avise.

---

### Tarefa 2: Pacote esqueleto e o primeiro teste verde

**Files:**
- Create: os 20 arquivos sob `src/mapscout/` listados na tabela acima
- Test: `tests/test_smoke.py`, `tests/conftest.py`, `tests/fixtures/.gitkeep`

**Interfaces:**
- Consumes: o venv da Tarefa 1.
- Produces: `mapscout.__version__: str`; `mapscout.cli.main() -> None`; `mapscout.web.app.app: FastAPI`.

- [ ] **Passo 1: escrever o teste que falha**

`tests/test_smoke.py`:
```python
"""Verifica que o pacote importa e expõe a versão."""

import mapscout


def test_pacote_expoe_versao() -> None:
    assert isinstance(mapscout.__version__, str)
    assert mapscout.__version__ == "0.1.0"
```

- [ ] **Passo 2: rodar e confirmar que falha**

Rode: `uv run pytest tests/test_smoke.py -v`
Esperado: FAIL — `ModuleNotFoundError: No module named 'mapscout'`.

- [ ] **Passo 3: criar o pacote**

`src/mapscout/__init__.py`:
```python
"""MapScout — prospecção B2B geolocalizada para uso pessoal."""

__version__ = "0.1.0"
```

Os módulos vazios — cada um recebe **só** a docstring de uma linha abaixo, nada mais:

| Arquivo | Conteúdo integral |
|---|---|
| `config.py` | `"""Configuração lida de variáveis de ambiente."""` |
| `db.py` | `"""Engine e sessões SQLite via SQLModel."""` |
| `models.py` | `"""Tabelas SQLModel do domínio."""` |
| `dedupe.py` | `"""Regras de deduplicação de registros."""` |
| `scoring.py` | `"""Score determinístico de oportunidade."""` |
| `repositories/__init__.py` | `"""Única fronteira de escrita no banco."""` |
| `repositories/businesses.py` | `"""Persistência de empresas."""` |
| `repositories/api_calls.py` | `"""Registro de chamadas à Places API para rastrear custo."""` |
| `repositories/blocklist.py` | `"""Consulta e escrita da blocklist de opt-out."""` |
| `places/__init__.py` | `"""Descoberta via Google Places API (New)."""` |
| `places/client.py` | `"""Cliente httpx do endpoint places:searchText."""` |
| `places/schemas.py` | `"""Schemas Pydantic da resposta da Places API (New)."""` |
| `enrichment/__init__.py` | `"""Enriquecimento a partir do site público da empresa."""` |
| `enrichment/fetcher.py` | `"""Busca de páginas respeitando robots.txt."""` |
| `enrichment/parser.py` | `"""Extração de sinais do HTML via selectolax."""` |
| `classification/__init__.py` | `"""Classificação de presença digital."""` |
| `classification/presence.py` | `"""Atribui presence_level e a evidência textual."""` |
| `ai/__init__.py` | `"""Camada de IA — rascunhos de abordagem, nunca envio."""` |
| `ai/schemas.py` | `"""Schemas Pydantic da saída da camada de IA."""` |
| `ai/cache.py` | `"""Cache por place_id e hash dos campos de entrada."""` |
| `ai/client.py` | `"""Chamada ao modelo com validação de citação de campo."""` |
| `web/__init__.py` | `"""Interface web FastAPI + Jinja2 + HTMX."""` |

`src/mapscout/cli.py` (decisão D5):
```python
"""Interface de linha de comando do MapScout."""


def main() -> None:
    """Ponto de entrada da CLI."""
    print("mapscout: nenhum comando implementado ainda (Fatia 0)")
```

`src/mapscout/web/app.py` (decisão D5):
```python
"""Aplicação FastAPI do MapScout."""

from fastapi import FastAPI

app = FastAPI(title="MapScout")
```

`tests/conftest.py`:
```python
"""Fixtures compartilhadas. Testes nunca acessam a rede."""
```

Crie também `tests/fixtures/.gitkeep` vazio.

- [ ] **Passo 4: rodar e confirmar que passa**

Rode: `uv run pytest -q`
Esperado: `1 passed`.

---

### Tarefa 3: Lint e tipos estritos verdes

**Files:**
- Modify: qualquer arquivo da Tarefa 2 que ruff ou mypy reprovar

**Interfaces:**
- Consumes: o pacote da Tarefa 2 e a config já escrita no `pyproject.toml`.
- Produces: árvore limpa sob `ruff check`, `ruff format --check` e `mypy --strict`.

- [ ] **Passo 1: rodar o ruff**

Rode: `uv run ruff check . && uv run ruff format --check .`
Esperado no primeiro disparo: possíveis achados de `D` (docstring faltando em `__init__.py`) e de formatação. Corrija adicionando a docstring que falta ou rodando `uv run ruff format .`. **Não** silencie regra com `# noqa` — se uma regra do conjunto for insustentável no projeto, remova-a do `select` e me diga qual e por quê.

- [ ] **Passo 2: rodar o mypy**

Rode: `uv run mypy`
Esperado: `Success: no issues found`. Se reclamar de stubs de terceiros (`selectolax`, `apscheduler`), adicione ao `pyproject.toml` — e **só** para os pacotes que reclamarem:

```toml
[[tool.mypy.overrides]]
module = ["selectolax.*", "apscheduler.*"]
ignore_missing_imports = true
```

- [ ] **Passo 3: reconfirmar o teste**

Rode: `uv run pytest -q`
Esperado: `1 passed`.

---

### Tarefa 4: Fechar o loop — Makefile, permissões, roadmap, commit

**Files:**
- Create: `Makefile`, `.claude/settings.json`, `ROADMAP.md`

**Interfaces:**
- Consumes: tudo das tarefas 1–3.
- Produces: `make check` como o comando único de verificação do projeto.

- [ ] **Passo 1: instalar o GNU make** (decisão D2)

```bash
winget install --id ezwinports.make --accept-source-agreements --accept-package-agreements
```
Depois, em um shell novo: `make --version` deve responder.

- [ ] **Passo 2: escrever o `Makefile`**

```makefile
.PHONY: check lint types test coletar api

check: lint types test

lint:
	uv run ruff check .
	uv run ruff format --check .

types:
	uv run mypy

test:
	uv run pytest -q

coletar:
	uv run mapscout

api:
	uv run uvicorn mapscout.web.app:app --reload
```

(indentação de receita é **TAB**, não espaços)

- [ ] **Passo 3: escrever `.claude/settings.json`**

```json
{
  "permissions": {
    "deny": [
      "Read(./.env)",
      "Read(./.env.*)",
      "Edit(./.env)",
      "Edit(./.env.*)",
      "Bash(git push)",
      "Bash(git push *)",
      "Bash(rm -rf *)"
    ],
    "allow": [
      "Bash(make check)",
      "Bash(make test)",
      "Bash(make lint)",
      "Bash(make types)",
      "Bash(uv run pytest *)",
      "Bash(uv run ruff *)",
      "Bash(uv run mypy *)",
      "Bash(pytest *)",
      "Bash(ruff *)",
      "Bash(mypy *)",
      "Bash(git status *)",
      "Bash(git diff *)",
      "Bash(git add *)",
      "Bash(git commit *)"
    ]
  }
}
```

- [ ] **Passo 4: escrever `ROADMAP.md`**

```markdown
# ROADMAP — MapScout

Fatias verticais. Cada uma termina em um comando que roda e produz resultado visível.

- [x] **Fatia 0 — Esqueleto e loop de verificação.** `make check` roda ruff + mypy estrito + pytest e passa verde.
- [ ] **Fatia 1 — Config e banco.** `config.py` lê env vars, engine SQLite, tabelas iniciais, `api_calls`, repositórios. Entrega: um comando cria o banco e lista as tabelas.
- [ ] **Fatia 2 — Descoberta via Places.** Cliente `places:searchText` com paginação (`pageSize` 20, até 3 páginas), toda chamada registrada em `api_calls`. Entrega: `make coletar` grava empresas reais no banco.
- [ ] **Fatia 3 — Dedupe e blocklist.** Níveis de dedupe do glossário, tabela `blocklist`, exportação CSV que consulta a blocklist. Entrega: coleta repetida não duplica.
- [ ] **Fatia 4 — Classificação sem rede.** `presence_level` 0–3 a partir de `websiteUri`, com evidência textual. Entrega: relatório por nível.
- [ ] **Fatia 5 — Enriquecimento HTTP.** Fetch do site respeitando `robots.txt`, máx. 5 páginas, User-Agent identificável. Níveis 4, 5 e 6.
- [ ] **Fatia 6 — Qualidade do site.** Níveis 7 e 8 via selectolax (viewport, HTTPS, copyright).
- [ ] **Fatia 7 — Score determinístico.** `base_presença × saúde_do_negócio × ticket_categoria`, tabela de ticket editável em config. Entrega: ranking ordenado.
- [ ] **Fatia 8 — Interface web.** FastAPI + Jinja2 + HTMX: lista, filtro, ordenação por score, evidência visível. Entrega: `make api`.
- [ ] **Fatia 9 — Camada de IA.** Saída JSON validada por Pydantic, justificativa obrigatoriamente citando campo preenchido, cache por `place_id` + hash. Gera rascunho, nunca envia.
- [ ] **Fatia 10 — Refresh e agendamento.** `checado_em` > 60 dias re-checa; APScheduler; exportação final.
```

- [ ] **Passo 5: rodar o critério de pronto**

Rode: `make check`
Esperado: ruff limpo, `Success: no issues found` do mypy, `1 passed` do pytest, saída final sem erro. **Cole a saída real** antes de declarar pronto.

- [ ] **Passo 6: commit único da fatia**

```bash
git add -A
git commit -m "chore: esqueleto do projeto e loop de verificação (Fatia 0)"
```
