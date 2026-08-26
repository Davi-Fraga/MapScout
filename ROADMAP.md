# ROADMAP — MapScout

## Blocos

- [x] **Bloco A** — Fundação e primeira coleta
      Esqueleto, loop de verificação (`make check`), cliente Places API,
      primeira coleta gravando no SQLite.
- [ ] **Bloco B** — Cobertura real e base limpa
      Grid adaptativo em retângulos, jobs retomáveis, normalização,
      dedupe multinível, blocklist.
- [ ] **Bloco C** — Enriquecimento e diagnóstico
      Crawler do site da empresa, e-mails, redes sociais, tecnologia,
      classificador de presença digital (níveis 0–9).
- [ ] **Bloco D** — Qualificação
      Filtros, scoring determinístico, exportação, camada de IA ancorada.
- [ ] **Bloco E** — Automação, API e painel
      API REST, webhooks, agendador e refresh, painel HTMX.
- [ ] **Bloco F** — Diferencial CNPJ (opcional)
      Dados abertos da Receita, matching por CEP + nome, filtro de empresa nova.

---

## Estado atual

**Bloco A concluído.** `make check` verde. Pacote `mapscout` em layout `src/`.
Fixture real da Places API capturado.

> Preserve aqui a seção "Estado e decisões" que o agente já tinha escrito no
> Bloco A — ela registra as escolhas de uv, APScheduler, regras do ruff etc.

---

## Decisões registradas

### Bloco B, Parte 2 — normalização, dedupe e blocklist (26/08/2026)

`make check` verde, 102 testes. Comando novo: `mapscout relatorio`.

- **0800 é tratado como `especial` e excluído da fusão por telefone.** O fixture
  tem `"0800 160 5555"` (Uniodonto): pela regra "11 dígitos = móvel" viraria celular,
  e como um 0800 é compartilhado entre unidades, fundiria filiais distintas. Também
  entram 0300, 0500, 4003, 4004 e 4020.
- **`wixsite.com` obrigou a lista de domínios compartilhados.** `tldextract` devolve
  `wixsite.com` como domínio registrável de `redesags.wixsite.com` — dois dentistas
  diferentes no Wix colidiriam. `dominios.py` reúne social, construtor grátis e
  marketplace (as listas do CLAUDE.md), e a regra "mesmo domínio funde" os ignora.
  O mesmo vale para dois perfis distintos na Doctoralia.
- **A guarda de filial roda antes de domínio e telefone.** O CLAUDE.md lista "mesmo
  nome, cidades diferentes" por último, mas uma rede compartilha site e 0800 entre
  unidades — avaliar a guarda depois deixaria a fusão acontecer antes. Há teste
  específico para isso (`test_filiais_com_o_mesmo_site_ainda_assim_nao_fundem`).
- **Similaridade por `difflib.SequenceMatcher`**, da stdlib, sem dependência nova.
  Nome ≥ 0.88; endereço por CEP igual quando houver, senão texto ≥ 0.85.
- **`Decisao` é dataclass com ação, confiança e motivo** — nunca booleano. O motivo é
  frase legível ("mesmo domínio próprio (oralclincampinas.com.br)"), no mesmo espírito
  da regra de evidência do CLAUDE.md.
- **`tldextract` configurado com `suffix_list_urls=()`**, usando só o snapshot
  embutido. Sem isso ele tentaria baixar a Public Suffix List e violaria a regra 1.
- **Blocklist consultada por place_id, domínio próprio e telefone normalizado.**
  Domínio compartilhado não bloqueia: banir um perfil da Doctoralia não pode banir
  todos os outros.
- **Dedupe em lote por chaves de bloqueio**, não O(n²): índice por domínio próprio e
  por telefone+cidade. Só a marcação para revisão compara par a par, e apenas dentro
  do mesmo CEP.

### Bloco B, Parte 1 — grid adaptativo e retomada (26/08/2026)

`make check` verde, 40 testes, nenhum acesso à rede. Comando novo: `mapscout varrer`.

- **Geometria reconciliada.** O prompt pedia célula com "raio = metade da diagonal
  para garantir sobreposição"; o CLAUDE.md exige `rectangle` e diz que as células
  encaixam sem sobreposição. A célula é um quadrado e é isso que vai na requisição —
  quadrados adjacentes ladrilham sem buraco por construção. `raio_m` continua
  existindo como propriedade derivada, usada para recortar o círculo de varredura e
  para o piso de 300 m na subdivisão. Nada consulta por círculo.
- **Freio de custo (regra 6).** `config.teto_chamadas_dia()` (padrão 500,
  sobrescrevível por `MAPSCOUT_TETO_CHAMADAS_DIA`). O runner consulta
  `chamadas_hoje()` antes de cada célula e encerra o job em `paused_quota` — sexto
  estado, além dos cinco do enunciado. Rate limit em `MAPSCOUT_RATE_LIMIT_RPS`.
- **Retomada por transação-por-célula.** `GridLog` tem PK composta
  `(celula, categoria)` e é gravado na mesma transação dos places e das `api_calls`.
  Ou a célula inteira ficou registrada, ou nada ficou — não existe estado
  intermediário em que se pagou sem registrar.
- **`Celula.id` determinístico** a partir dos limites arredondados em 6 casas. É o
  que permite reconhecer a mesma célula entre processos diferentes.
- **SIGINT cooperativo.** `loop.add_signal_handler` não existe no Windows. A CLI
  instala `signal.signal` setando um `threading.Event`, checado **entre** células.
  A célula em curso termina e é gravada antes de sair. Se o Ctrl+C cair no meio de
  um `await`, o `KeyboardInterrupt` é capturado antes de qualquer gravação — a
  célula não foi cobrada e volta na retomada.
- **`db/migrations.garantir_colunas()`.** `create_all` não adiciona coluna a tabela
  existente. Migração idempotente por `PRAGMA table_info` + `ALTER TABLE ADD COLUMN`,
  chamada por `preparar_banco()`. Foi o que permitiu adicionar `Place.cidade` sem
  mandar apagar o banco.
- **O teste de aceite foi verificado por mutação:** desligando o
  `celula_ja_executada`, ele reprova. A falha vem da constraint UNIQUE do `GridLog`,
  que funciona como segunda linha de defesa — gravar duas vezes a mesma célula é
  estruturalmente impossível, não só improvável.

### Validação inicial da API (26/08/2026)

- **`locationRestriction` no `searchText` aceita apenas `rectangle`** (`low`/`high`).
  `circle` retorna 400 "Unknown name circle". `circle` só é válido em
  `locationBias`. Consequência: o grid do Bloco B gera retângulos, não círculos.
  Isso é melhor para o nosso caso — retângulo restringe de verdade e as células
  encaixam sem sobreposição.
- **Fixture real** capturado em `tests/fixtures/places_searchtext.json`:
  20 dentistas em Campinas centro, com `nextPageToken` presente.
- **Amostra confirmou a tese:** 10 dos 20 registros são oportunidade real —
  5 sem site nenhum e 5 com "site" que o filtro binário deixaria passar
  (Doctoralia, mechameaqui, wixsite.com, lovable.app, Instagram).

### Escala de presença digital renumerada (26/08/2026)

A tabela original não era monotônica: nível 4 tinha score 90 e nível 3 tinha 85,
contradizendo a regra "nível menor = oportunidade maior". Renumerada de 0 a 9 em
ordem decrescente de oportunidade. Categoria nova incluída: **subdomínio gratuito
de construtor de site** (nível 6, score 80) — a pessoa tem site, mas sem domínio
próprio, sem SEO, sem e-mail profissional e sem controle. Apareceu duas vezes
numa amostra de 20, com wixsite.com e lovable.app.

### Ambiente (26/08/2026)

- Windows, PowerShell e Git Bash.
- `.gitattributes` com `* text=auto eol=lf` para evitar diff fantasma de CRLF.
- `make` instalado via winget; exige reiniciar o terminal para entrar no PATH.

---

## Backlog / ideias não priorizadas

- Fonte complementar: Overpass API (OpenStreetMap), gratuita e sem restrição
  de armazenamento. Útil para cruzar e validar.
- Verificação antifalso-positivo: antes de abordar dizendo "vi que você não tem
  site", buscar o nome do negócio na web. Errar isso queima o contato.
- Registrar taxa de resposta por nível de presença e por categoria, para
  recalibrar os pesos do score com dado real em vez de palpite.