"""Aplicação web FastAPI com painel interativo HTMX do MapScout."""

from __future__ import annotations

import math
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Any
from urllib.parse import parse_qs

import dotenv
from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, col, func, select
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from mapscout.ai.client import gerar_rascunho_abordagem
from mapscout.auth import (
    COOKIE_NAME,
    gerar_token_sessao,
    validar_token_sessao,
    verificar_credenciais,
)
from mapscout.db.models import Place
from mapscout.db.repo import (
    adicionar_blocklist,
    adicionar_nota_lead,
    atualizar_status_lead,
    listar_notas_lead,
    listar_zonas_varridas,
)
from mapscout.db.session import abrir_sessao, criar_engine, preparar_banco
from mapscout.export import exportar_leads_qualificados, formatar_link_whatsapp
from mapscout.geo.cidades import (
    CIDADES_BRASIL,
    buscar_cidades,
    calcular_deslocamento_coordenadas,
    obter_coordenadas_cidade,
)
from mapscout.scoring import calcular_score_lead
from mapscout.tasks.manager import gerenciador_tarefas
from mapscout.tasks.scheduler import (
    executar_tarefa_agora,
    iniciar_agendador,
    listar_tarefas_agendadas,
    parar_agendador,
)

dotenv.load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

_engine = criar_engine()
preparar_banco(_engine)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Gerencia ciclo de vida do servidor e do agendador APScheduler."""
    iniciar_agendador(_engine)
    yield
    parar_agendador()


class AuthMiddleware(BaseHTTPMiddleware):
    """Protege o acesso à aplicação exigindo autenticação por cookie de sessão."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        """Verifica se a requisição possui sessão válida ou redireciona para login."""
        caminho = request.url.path
        if (
            caminho == "/login"
            or caminho == "/ping"
            or caminho == "/health"
            or caminho.startswith("/static")
            or caminho == "/favicon.ico"
        ):
            return await call_next(request)

        token = request.cookies.get(COOKIE_NAME)
        usuario = validar_token_sessao(token) if token else None

        if usuario is None:
            if request.headers.get("HX-Request") == "true":
                return Response(
                    content="",
                    status_code=200,
                    headers={"HX-Redirect": "/login"},
                )
            return RedirectResponse(url="/login", status_code=303)

        request.state.usuario = usuario
        return await call_next(request)


app = FastAPI(title="MapScout — Radar de Prospecção", lifespan=lifespan)
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(AuthMiddleware)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATES_DIR)


def obter_sessao() -> Iterator[Session]:
    """Devolve uma nova sessão de banco de dados para os endpoints."""
    with abrir_sessao(_engine) as sessao:
        yield sessao


SessaoDep = Annotated[Session, Depends(obter_sessao)]


def _preparar_item_lead(sessao: Session, place: Place) -> dict[str, Any]:
    """Calcula score e gera link de contato direto para a listagem."""
    score = place.score or calcular_score_lead(place)
    link_whats = ""
    if place.national_phone_number:
        msg = (
            f"Olá! Vi a ficha de {place.display_name} no Google "
            "e gostaria de falar com o responsável."
        )
        link_whats = formatar_link_whatsapp(place.national_phone_number, msg)

    return {
        "place": place,
        "score": score,
        "link_whatsapp": link_whats,
    }


def resolver_nivel_presenca(place: Place) -> int | None:
    """Resolve o nível de presença considerando ausência de site cadastrado."""
    if place.presence_level is not None:
        return place.presence_level
    if not place.website_uri or not place.website_uri.strip():
        return 0
    return None


def _filtrar_leads(
    sessao: Session,
    *,
    busca: str | None = None,
    cidade: str | None = None,
    nivel: int | None = None,
    status_lead: str | None = None,
    min_score: float = 0.0,
    pagina: int = 1,
    limite: int = 50,
) -> tuple[list[dict[str, Any]], int]:
    """Consulta e filtra leads com queries SQL otimizadas e paginação."""
    consulta = select(Place)
    contagem = select(func.count()).select_from(Place)

    if cidade and cidade.strip():
        consulta = consulta.where(col(Place.cidade) == cidade.strip())
        contagem = contagem.where(col(Place.cidade) == cidade.strip())

    if status_lead and status_lead.strip():
        consulta = consulta.where(col(Place.status_lead) == status_lead.strip())
        contagem = contagem.where(col(Place.status_lead) == status_lead.strip())

    if nivel is not None:
        if nivel == 0:
            cond_n0 = (
                (col(Place.presence_level) == 0)
                | (col(Place.website_uri) == None)  # noqa: E711
                | (col(Place.website_uri) == "")
            )
            consulta = consulta.where(cond_n0)
            contagem = contagem.where(cond_n0)
        else:
            consulta = consulta.where(col(Place.presence_level) == nivel)
            contagem = contagem.where(col(Place.presence_level) == nivel)

    if busca and busca.strip():
        termo = f"%{busca.strip()}%"
        cond_busca = col(Place.display_name).ilike(termo) | col(
            Place.formatted_address
        ).ilike(termo)
        consulta = consulta.where(cond_busca)
        contagem = contagem.where(cond_busca)

    if min_score > 0:
        consulta = consulta.where(col(Place.score) >= min_score)
        contagem = contagem.where(col(Place.score) >= min_score)

    total_filtrado = sessao.exec(contagem).one()

    # Ordena pelo maior score e depois pelos mais recentes
    consulta = consulta.order_by(
        col(Place.score).desc().nullslast(), col(Place.coletado_em).desc()
    )

    offset = max(0, (pagina - 1) * limite)
    places = list(sessao.exec(consulta.offset(offset).limit(limite)).all())

    itens: list[dict[str, Any]] = []
    for p in places:
        itens.append(_preparar_item_lead(sessao, p))

    return itens, total_filtrado


@app.get("/", response_class=HTMLResponse)
def index(request: Request, sessao: SessaoDep) -> HTMLResponse:
    """Renderiza o painel principal do MapScout com métricas agregadas."""
    total_leads = sessao.exec(select(func.count()).select_from(Place)).one()
    sem_site = sessao.exec(
        select(func.count())
        .select_from(Place)
        .where(
            (col(Place.presence_level) == 0)
            | (col(Place.website_uri) == None)  # noqa: E711
            | (col(Place.website_uri) == "")
        )
    ).one()
    site_fraco_ou_fora = sessao.exec(
        select(func.count())
        .select_from(Place)
        .where(col(Place.presence_level).in_([1, 2, 3, 4, 5, 6, 8]))
    ).one()
    em_prospeccao = sessao.exec(
        select(func.count())
        .select_from(Place)
        .where(col(Place.status_lead).in_(["contatado", "em_conversa", "proposta"]))
    ).one()

    cidades = list(
        sessao.exec(
            select(Place.cidade)
            .where(col(Place.cidade) != None, col(Place.cidade) != "")  # noqa: E711
            .distinct()
            .order_by(col(Place.cidade))
        ).all()
    )

    leads, total_filtrado = _filtrar_leads(sessao, pagina=1, limite=50)
    total_paginas = max(1, math.ceil(total_filtrado / 50))

    stats = {
        "total_leads": total_leads,
        "sem_site": sem_site,
        "site_fraco_ou_fora": site_fraco_ou_fora,
        "em_prospeccao": em_prospeccao,
    }

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "leads": leads,
            "total_filtrado": total_filtrado,
            "pagina": 1,
            "limite": 50,
            "total_paginas": total_paginas,
            "cidades": [c for c in cidades if c],
            "stats": stats,
            "task": gerenciador_tarefas.obter_status(),
        },
    )


@app.get("/partials/leads", response_class=HTMLResponse)
def filtrar_leads_endpoint(
    request: Request,
    sessao: SessaoDep,
    busca: str | None = Query(default=None),
    cidade: str | None = Query(default=None),
    nivel: int | None = Query(default=None),
    status_lead: str | None = Query(default=None),
    min_score: float = Query(default=0.0),
    pagina: int = Query(default=1),
    limite: int = Query(default=50),
) -> HTMLResponse:
    """Endpoint HTMX que retorna apenas a tabela de leads filtrada com paginação."""
    leads, total_filtrado = _filtrar_leads(
        sessao,
        busca=busca,
        cidade=cidade,
        nivel=nivel,
        status_lead=status_lead,
        min_score=min_score,
        pagina=pagina,
        limite=limite,
    )
    total_paginas = max(1, math.ceil(total_filtrado / limite))

    return templates.TemplateResponse(
        request=request,
        name="partials/tabela_leads.html",
        context={
            "leads": leads,
            "total_filtrado": total_filtrado,
            "pagina": pagina,
            "limite": limite,
            "total_paginas": total_paginas,
        },
    )


@app.get("/partials/lead/{place_id}", response_class=HTMLResponse)
def detalhar_lead_modal(
    request: Request,
    place_id: str,
    sessao: SessaoDep,
) -> HTMLResponse:
    """Carrega o modal com a auditoria completa, pitches e histórico de anotações."""
    place = sessao.get(Place, place_id)
    if not place:
        raise HTTPException(status_code=404, detail="Lead não encontrado")

    score = place.score or calcular_score_lead(place)
    abordagem = gerar_rascunho_abordagem(place, sessao=sessao)
    link_whats = formatar_link_whatsapp(
        place.national_phone_number, abordagem.mensagem_whatsapp
    )
    notas = listar_notas_lead(sessao, place_id)

    return templates.TemplateResponse(
        request=request,
        name="partials/lead_modal.html",
        context={
            "place": place,
            "score": score,
            "abordagem": abordagem,
            "link_whatsapp": link_whats,
            "notas": notas,
        },
    )


@app.get("/partials/kanban", response_class=HTMLResponse)
def kanban_endpoint(
    request: Request,
    sessao: SessaoDep,
    busca: str | None = None,
    cidade: str | None = None,
    nivel: int | None = None,
    min_score: float = 0.0,
    limite_por_coluna: int = 25,
) -> HTMLResponse:
    """Retorna o quadro Kanban com os top leads mais quentes de cada etapa comercial."""
    status_lista = [
        "novo",
        "contatado",
        "em_conversa",
        "proposta",
        "fechado",
        "perdido",
    ]
    leads_por_status: dict[str, list[dict[str, Any]]] = {}

    for st in status_lista:
        leads_col, _ = _filtrar_leads(
            sessao,
            busca=busca,
            cidade=cidade,
            nivel=nivel,
            status_lead=st,
            min_score=min_score,
            pagina=1,
            limite=limite_por_coluna,
        )
        leads_por_status[st] = leads_col

    return templates.TemplateResponse(
        request=request,
        name="partials/kanban.html",
        context={"leads_por_status": leads_por_status},
    )


@app.post("/api/leads/{place_id}/status", response_class=HTMLResponse)
@app.post("/api/lead/{place_id}/status", response_class=HTMLResponse)
async def atualizar_status_lead_endpoint(
    request: Request,
    place_id: str,
    sessao: SessaoDep,
    status: str | None = Query(default=None),
) -> HTMLResponse:
    """Atualiza o estágio do lead e devolve a visualização Kanban atualizada."""
    status_final = status
    if not status_final:
        corpo = (await request.body()).decode("utf-8")
        parsed = parse_qs(corpo)
        if parsed.get("status"):
            status_final = parsed["status"][0]
        elif parsed.get("novo_status"):
            status_final = parsed["novo_status"][0]

    if status_final:
        atualizar_status_lead(sessao, place_id, status_final)

    return kanban_endpoint(
        request=request,
        sessao=sessao,
        busca=None,
        cidade=None,
        nivel=None,
        min_score=0.0,
    )


@app.post("/api/leads/{place_id}/notas", response_class=HTMLResponse)
async def adicionar_nota_endpoint(
    request: Request,
    place_id: str,
    sessao: SessaoDep,
) -> HTMLResponse:
    """Adiciona anotação de contato e histórico ao lead."""
    corpo = (await request.body()).decode("utf-8")
    dados = parse_qs(corpo)
    texto = dados.get("texto", [""])[0]
    usuario = getattr(request.state, "usuario", "davi")

    if texto.strip():
        adicionar_nota_lead(sessao, place_id=place_id, texto=texto, autor=usuario)

    notas = listar_notas_lead(sessao, place_id)
    html_itens = []
    for n in notas:
        dt_str = n.criado_em.strftime("%d/%m às %H:%M") if n.criado_em else ""
        html_itens.append(
            '<div style="background: rgba(255, 255, 255, 0.03); '
            "border: 1px solid rgba(255, 255, 255, 0.05); "
            'border-radius: 4px; padding: 6px 10px; font-size: 12px;">'
            f'<div style="display: flex; justify-content: space-between; '
            f'color: var(--text-dim); font-size: 10px; margin-bottom: 2px;">'
            f"<span>👤 {n.autor}</span><span>{dt_str}</span></div>"
            f'<div style="color: #fff;">{n.texto}</div></div>'
        )

    conteudo = "\n".join(html_itens) or (
        '<div style="font-size: 12px; color: var(--text-dim); '
        'text-align: center; padding: 6px;">Nenhuma anotação.</div>'
    )
    return HTMLResponse(content=conteudo)


@app.post("/api/lead/{place_id}/block", response_class=HTMLResponse)
def bloquear_lead_endpoint(
    place_id: str,
    sessao: SessaoDep,
) -> HTMLResponse:
    """Registra opt-out definitivo do lead e remove da visualização."""
    place = sessao.get(Place, place_id)
    if place:
        adicionar_blocklist(
            sessao,
            place_id=place.place_id,
            telefone=place.national_phone_number,
            dominio=place.website_uri,
            motivo="Opt-out pelo painel web",
        )
        sessao.commit()

    return HTMLResponse(content="")


@app.get("/exportar")
def exportar_csv_endpoint(
    sessao: SessaoDep,
) -> FileResponse:
    """Gera e faz o download direto do arquivo CSV de leads qualificados."""
    caminho_csv = BASE_DIR.parent.parent.parent / "leads_mapscout.csv"
    exportar_leads_qualificados(
        sessao,
        caminho_csv,
        formato="csv",
    )

    return FileResponse(
        path=caminho_csv,
        filename="leads_mapscout.csv",
        media_type="text/csv",
    )


@app.get("/partials/jobs/status", response_class=HTMLResponse)
def obter_status_job(request: Request) -> HTMLResponse:
    """Devolve o componente HTML com o progresso do job ativo em tempo real."""
    return templates.TemplateResponse(
        request=request,
        name="partials/job_status.html",
        context={"task": gerenciador_tarefas.obter_status()},
    )


@app.get("/favicon.ico")
def favicon_endpoint() -> HTMLResponse:
    """Devolve favicon SVG direto para evitar erros 404 no console."""
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">'
        '<text y=".9em" font-size="90">🎯</text></svg>'
    )
    return HTMLResponse(content=svg, media_type="image/svg+xml")


@app.get("/api/cidades/busca")
def buscar_cidades_endpoint(q: str = Query(default="")) -> list[dict[str, Any]]:
    """Busca cidades brasileiras por nome e devolve coordenadas geográficas."""
    return buscar_cidades(q)


@app.get("/api/geo/deslocamento")
def geo_deslocamento_endpoint(
    lat: float = Query(...),
    lng: float = Query(...),
    direcao: str = Query(...),
    distancia_km: float = Query(default=5.0),
) -> dict[str, float]:
    """Calcula novo par lat/lng deslocando centro em km."""
    nova_lat, nova_lng = calcular_deslocamento_coordenadas(
        lat, lng, direcao, distancia_km
    )
    return {"lat": nova_lat, "lng": nova_lng}


@app.get("/partials/modal/varrer", response_class=HTMLResponse)
def modal_nova_varredura(request: Request, sessao: SessaoDep) -> HTMLResponse:
    """Retorna o modal de configuração para iniciar uma nova varredura."""
    zonas_recentes = listar_zonas_varridas(sessao, limite=6)
    return templates.TemplateResponse(
        request=request,
        name="partials/nova_varredura_modal.html",
        context={
            "cidades_brasil": CIDADES_BRASIL,
            "zonas_recentes": zonas_recentes,
        },
    )


@app.post("/api/jobs/varrer", response_class=HTMLResponse)
async def iniciar_varredura_endpoint(request: Request) -> HTMLResponse:
    """Dispara uma varredura geográfica em background e devolve o banner de status."""
    corpo = (await request.body()).decode("utf-8")
    dados = parse_qs(corpo)

    categoria = dados.get("categoria", ["dentista"])[0].strip()
    cidade = dados.get("cidade", ["Campinas"])[0].strip()
    lat_str = dados.get("lat", [""])[0].strip()
    lng_str = dados.get("lng", [""])[0].strip()
    raio_str = dados.get("raio_km", ["5.0"])[0].strip()
    passo_str = dados.get("passo_m", ["1000.0"])[0].strip()

    # Se o usuário digitou uma cidade conhecida, usa as coordenadas dela automaticamente
    coords = obter_coordenadas_cidade(cidade)
    if coords and (not lat_str or not lng_str or lat_str == "-22.9056"):
        lat, lng = coords
    else:
        lat = float(lat_str) if lat_str else -22.9056
        lng = float(lng_str) if lng_str else -47.0608

    raio_km = float(raio_str) if raio_str else 5.0
    passo_m = float(passo_str) if passo_str else 1000.0

    gerenciador_tarefas.iniciar_varredura(
        categoria=categoria,
        cidade=cidade,
        lat=lat,
        lng=lng,
        raio_km=raio_km,
        passo_m=passo_m,
        engine=_engine,
    )
    return templates.TemplateResponse(
        request=request,
        name="partials/job_status.html",
        context={"task": gerenciador_tarefas.obter_status()},
    )


@app.post("/api/jobs/enriquecer", response_class=HTMLResponse)
async def iniciar_enriquecimento_endpoint(
    request: Request,
    limite: int | None = Query(default=None),
    concorrencia: int = Query(default=5),
) -> HTMLResponse:
    """Dispara o diagnóstico e enriquecimento de presença digital em background."""
    gerenciador_tarefas.iniciar_enriquecimento(
        engine=_engine,
        limite=limite,
        concorrencia=concorrencia,
    )
    return templates.TemplateResponse(
        request=request,
        name="partials/job_status.html",
        context={"task": gerenciador_tarefas.obter_status()},
    )


@app.post("/api/jobs/cancelar", response_class=HTMLResponse)
async def cancelar_job_endpoint(request: Request) -> HTMLResponse:
    """Cancela a tarefa em segundo plano em execução."""
    gerenciador_tarefas.cancelar()
    return templates.TemplateResponse(
        request=request,
        name="partials/job_status.html",
        context={"task": gerenciador_tarefas.obter_status()},
    )


@app.get("/partials/automacoes", response_class=HTMLResponse)
def modal_automacoes(request: Request) -> HTMLResponse:
    """Retorna o modal com as tarefas agendadas e histórico do APScheduler."""
    tarefas = listar_tarefas_agendadas()
    return templates.TemplateResponse(
        request=request,
        name="partials/automacoes_modal.html",
        context={"tarefas": tarefas},
    )


@app.post("/api/automacoes/{job_id}/executar", response_class=HTMLResponse)
async def disparar_automacao_endpoint(job_id: str) -> HTMLResponse:
    """Dispara a execução imediata sob demanda de uma rotina do APScheduler."""
    sucesso = await executar_tarefa_agora(job_id, engine=_engine)
    if sucesso:
        return HTMLResponse(
            '<span style="color: var(--accent-green); '
            'font-size: 13px; font-weight: 600;">'
            "✓ Rotina executada com sucesso agora!</span>"
        )
    return HTMLResponse(
        '<span style="color: var(--accent-red); font-size: 13px;">'
        "Rotina não encontrada.</span>"
    )


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request) -> Response:
    """Renderiza a página de login ou redireciona para o painel se já logado."""
    token = request.cookies.get(COOKIE_NAME)
    if token and validar_token_sessao(token):
        return RedirectResponse(url="/", status_code=303)

    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={"erro": None},
    )


@app.post("/login", response_class=HTMLResponse)
async def login_post(request: Request) -> Response:
    """Valida as credenciais enviadas e estabelece a sessão segura."""
    corpo = (await request.body()).decode("utf-8")
    dados = parse_qs(corpo)

    usuario = dados.get("usuario", [""])[0].strip()
    senha = dados.get("senha", [""])[0]

    if verificar_credenciais(usuario, senha):
        token = gerar_token_sessao(usuario)
        resposta = RedirectResponse(url="/", status_code=303)
        resposta.set_cookie(
            key=COOKIE_NAME,
            value=token,
            max_age=30 * 86400,
            httponly=True,
            samesite="lax",
        )
        return resposta

    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={"erro": "Usuário ou senha incorretos."},
        status_code=401,
    )


@app.get("/logout")
def logout_endpoint() -> RedirectResponse:
    """Encerra a sessão do usuário limpando o cookie seguro."""
    resposta = RedirectResponse(url="/login", status_code=303)
    resposta.delete_cookie(key=COOKIE_NAME)
    return resposta


@app.get("/ping")
@app.get("/health")
def ping_endpoint() -> dict[str, str]:
    """Endpoint de healthcheck para monitoramento e keep-alive do Render."""
    return {"status": "ok"}

