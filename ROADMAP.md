# ROADMAP — MapScout

## Blocos

- [x] **Bloco A** — Fundação e primeira coleta
      Esqueleto, loop de verificação (`make check`), cliente Places API,
      primeira coleta gravando no SQLite.
- [x] **Bloco B** — Cobertura real e base limpa
      Grid adaptativo em retângulos, jobs retomáveis, normalização,
      dedupe multinível, blocklist.
- [x] **Bloco C** — Enriquecimento e diagnóstico
      Crawler do site da empresa, e-mails, redes sociais, tecnologia,
      classificador de presença digital (níveis 0–9).
- [x] **Bloco D** — Qualificação
      Filtros, scoring determinístico, exportação, camada de IA ancorada.
- [x] **Bloco E** — Automação, API e painel
      API REST, painel web HTMX, Mini-CRM de vendas, exportação direta.
- [ ] **Bloco F** — Diferencial CNPJ (opcional)
      Dados abertos da Receita, matching por CEP + nome, filtro de empresa nova.

---

## Estado atual

**Blocos A, B, C, D, E e Automação APScheduler concluídos.** `make check` verde (149 testes).
Painel web moderno com FastAPI + HTMX + Jinja2, disparo de varredura geográfica
e diagnóstico de sites em background com barra de progresso em tempo real,
rotinas agendadas pelo APScheduler (conformidade Google de 60 dias e monitor
de sites caídos), filtros instantâneos por nível/score/cidade, modal de
auditoria com copy da IA, mini-CRM com alteração de status do funil de prospecção,
disparo direto para WhatsApp Web (`wa.me`) e download de CSV.

---

## Decisões registradas

### Automação com APScheduler e Background Jobs Web (02/09/2026)

`make check` verde, 149 testes (12 novos testes unitários e de integração).
Comando novo / rotinas automatizadas no painel web.

- **Disparo de Varredura e Enriquecimento pelo Painel Web:**
  - `TaskManager` assíncrono executa coletas e diagnósticos sem bloquear o servidor.
  - Barra de progresso ao vivo via HTMX (`hx-trigger="every 1s"`) com percentual,
    itens processados, indicador pulsante e botão de cancelamento cooperativo.
  - Modal moderno de **Nova Varredura** com presets de categorias (dentista, estética, etc.)
    e cidades (Campinas, São Paulo, Rio, etc.) que preenchem latitude/longitude com 1 clique.
  - Parse de formulário via `urllib.parse.parse_qs` nativo, mantendo a stack fixa sem
    necessidade de pacotes externos (`python-multipart`).
- **Agendador de Tarefas Periódicas (APScheduler):**
  - Instância de `AsyncIOScheduler` integrada ao ciclo de vida (`lifespan`) do FastAPI.
  - **Rotina de Conformidade Google (Regra 118 do CLAUDE.md):** varre periodicamente
    places checados há mais de 60 dias (`checado_em > 60d`) para renovação cadastral
    respeitando o teto de chamadas diárias.
  - **Monitor de Sites Caídos (Nível 2):** re-testa periodicamente sites com erro de
    conexão/HTTP para verificar se voltaram ao ar ou continuam offline.
  - Modal de automações com histórico de execuções e botão para disparo manual sob demanda.

### Bloco E — Painel Web HTMX e Mini-CRM de Prospecção (02/09/2026)

`make check` verde, 137 testes (4 novos testes de integração web com TestClient).
Comando novo para desenvolvimento: `make api` (roda uvicorn em dev).

- **Interface orientada à produtividade comercial (Espelho do Mapaleads):**
  - **Filtros instantâneos sem recarregar a página (HTMX):** busca por texto,
    filtro por cidade, nível de presença digital (0 a 9), status de funil e score mínimo.
  - **Cards de Métricas:** contagem de total de empresas, oportunidades de ouro (sem site),
    sites fracos/fora do ar e leads em processo de prospecção.
  - **Auditoria detalhada no Modal:** diagnóstico técnico do site (SSL, viewport mobile,
    ano de copyright, e-mails, redes sociais), cópia de rascunho com 1 clique e botão
    de abrir conversa direto no WhatsApp Web.
  - **Mini-CRM integrado:** dropdown na tabela para atualizar o status do lead
    (`novo` → `contatado` → `em_conversa` → `proposta` → `fechado` → `perdido`)
    atualizando o banco de dados de forma assíncrona.
  - **Opt-out LGPD no painel:** botão para adicionar lead à `blocklist` com 1 clique.
  - **Design System Vanilla CSS:** tema escuro moderno, glassmorphism e badges semânticos
    com zero frameworks pesados ou complexos de frontend.

### Bloco D — Qualificação, Scoring e Camada de IA (02/09/2026)

`make check` verde, 133 testes. Comando novo: `mapscout exportar`.

- **Score determinístico transparente:**
  $\text{score} = \text{base\_presenca} \times \text{saude\_negocio} \times \text{ticket\_categoria}$.
  Empresas com muitas avaliações (50+) e nota alta (4.5+) têm faturamento ativo e zelo
  pela marca, recebendo multiplicador de até 1.48x; categorias com ticket elevado
  (clínicas, odonto, advocacia) recebem até 1.30x.
- **Camada de IA ancorada:**
  Schema Pydantic `AbordagemLead` com gancho comercial, justificativa, pitch de WhatsApp
  e proposta de e-mail consultivo. Validador `validar_ancoragem` rejeita alucinações de campos
  ausentes no banco. Cache SQLite via hash SHA-256 (`AiCache`) para reutilizar abordagens
  sem gastar tokens ou recomputar.
- **Exportação comercial acionável:**
  CSV (compatível com Excel) e JSON com coluna `Link_WhatsApp_Direto` (`wa.me/55...&text=...`).
  Ao abrir a planilha, um clique no link abre o WhatsApp com a mensagem personalizada
  já preenchida. Respeito estrito à `blocklist` de opt-out (regra LGPD).

### Bloco C — Enriquecimento e diagnóstico de presença digital (02/09/2026)

`make check` verde, 122 testes (20 novos testes com zero acesso à rede via `respx`).
Comando novo: `mapscout enriquecer`.

- **Classificação estrita em 10 níveis (0 a 9):**
  - Níveis 0, 1, 3, 5, 6 e 7 são resolvidos sem requisição de rede (`classificar_por_url`),
    poupando banda e tempo.
  - Níveis 2, 4, 8 e 9 são resolvidos após crawler HTTP assíncrono (`classificar_site_proprio`).
- **Evidência textual orientada à abordagem de vendas:**
  Em vez de códigos internos, o campo `presence_evidence` armazena frases prontas
  que o profissional pode enviar ao lead (ex: *"O link do site no perfil do Google
  está fora do ar (erro HTTP 404)"*, *"Utiliza perfil em rede social ou agregador no
  lugar de site próprio"*, *"Site próprio com problemas técnicos: não é adaptado para
  visualização em celulares (sem viewport mobile)"*).
- **Parser de alta velocidade com `selectolax`:**
  Extração de meta viewport, detecção de CMS/tecnologias (WordPress, Wix, WooCommerce,
  Shopify), links de WhatsApp direto (`wa.me`, `api.whatsapp.com`), perfis sociais
  (Instagram, Facebook) e e-mails com exclusão de assets estáticos e placeholders.
- **Detecção de domínio estacionado / página vazia:**
  Páginas com termos de domínio à venda ou com menos de 20 caracteres de texto visível
  são classificadas como Nível 4 (alta oportunidade: empresa comprou domínio mas não
  tem site).
- **Processamento paralelo respeitoso:**
  `enriquecer_lote` usa `asyncio.Semaphore` para manter concorrência controlada (padrão 5),
  evitando sobrecarregar conexões locais.
- **Campos adicionados a `Place`:**
  `presence_level`, `presence_evidence`, `website_status_code`, `has_ssl`,
  `has_mobile_viewport`, `copyright_year`, `emails`, `instagram_url`, `facebook_url`,
  `whatsapp_url`, `tech_detected`, `enriquecido_em`, `score`, `status_lead`.
  Adicionados via `db/migrations.py` de forma idempotente sem recriar o banco.

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