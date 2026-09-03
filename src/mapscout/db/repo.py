"""Repositório: todo acesso ao banco passa por aqui."""

from __future__ import annotations

import json
from datetime import datetime, time, timedelta

from sqlmodel import Session, col, func, select

from mapscout.collect.jobs import EstadoJob, GridLog, SearchJob
from mapscout.db.models import (
    ApiCall,
    Blocklist,
    LeadNote,
    Place,
    ScanZone,
    agora_utc,
    para_utc_naive,
)
from mapscout.dominios import e_compartilhado
from mapscout.normalize.domain import dominio_registravel
from mapscout.normalize.phone import normalizar_telefone
from mapscout.sources.places_api import PlaceResposta, RegistroChamada

CAMPOS_PRESERVADOS = frozenset({"place_id", "coletado_em", "checado_em"})


def place_de_resposta(resposta: PlaceResposta, cidade: str | None = None) -> Place:
    """Converte um lugar da Places API no modelo persistido."""
    nivel_inicial = 0 if not resposta.site or not resposta.site.strip() else None
    return Place(
        place_id=resposta.id,
        cidade=cidade,
        display_name=resposta.nome.texto,
        formatted_address=resposta.endereco,
        latitude=resposta.localizacao.latitude if resposta.localizacao else None,
        longitude=resposta.localizacao.longitude if resposta.localizacao else None,
        national_phone_number=resposta.telefone,
        website_uri=resposta.site,
        presence_level=nivel_inicial,
        rating=resposta.nota,
        user_rating_count=resposta.qtd_avaliacoes,
        business_status=resposta.status,
        google_maps_uri=resposta.maps_uri,
        types=json.dumps(resposta.tipos, ensure_ascii=False),
        primary_type_display_name=(
            resposta.tipo_principal.texto if resposta.tipo_principal else None
        ),
    )


def upsert_place(sessao: Session, place: Place, agora: datetime | None = None) -> bool:
    """Insere ou atualiza um Place por place_id sem sobrescrever coletado_em."""
    instante = para_utc_naive(agora) if agora is not None else agora_utc()
    existente = sessao.get(Place, place.place_id)
    if existente is None:
        place.coletado_em = instante
        place.checado_em = instante
        sessao.add(place)
        return True

    novos = place.model_dump(exclude=set(CAMPOS_PRESERVADOS))
    for campo, valor in novos.items():
        setattr(existente, campo, valor)
    existente.checado_em = instante
    sessao.add(existente)
    return False


def registrar_api_call(sessao: Session, registro: RegistroChamada) -> ApiCall:
    """Grava uma tentativa de chamada à Places API na tabela api_calls."""
    linha = ApiCall(
        endpoint=registro.endpoint,
        timestamp=para_utc_naive(registro.timestamp),
        qtd_resultados=registro.qtd_resultados,
        field_mask=registro.field_mask,
        status_code=registro.status_code,
    )
    sessao.add(linha)
    return linha


def listar_places(sessao: Session, limite: int = 5) -> list[Place]:
    """Lista os primeiros places por ordem de coleta."""
    consulta = (
        select(Place)
        .order_by(col(Place.coletado_em), col(Place.place_id))
        .limit(limite)
    )
    return list(sessao.exec(consulta).all())


def listar_todos_places(sessao: Session) -> list[Place]:
    """Lista a base inteira em ordem estável, para o dedupe em lote."""
    consulta = select(Place).order_by(col(Place.coletado_em), col(Place.place_id))
    return list(sessao.exec(consulta).all())


def contar_places(sessao: Session) -> int:
    """Conta quantos places existem no banco."""
    return int(sessao.exec(select(func.count()).select_from(Place)).one())


def contar_api_calls(sessao: Session) -> int:
    """Conta quantas chamadas à Places API foram registradas."""
    return int(sessao.exec(select(func.count()).select_from(ApiCall)).one())


def adicionar_blocklist(
    sessao: Session,
    *,
    motivo: str,
    telefone: str | None = None,
    dominio: str | None = None,
    place_id: str | None = None,
) -> Blocklist:
    """Registra um opt-out, normalizando telefone e domínio antes de gravar."""
    e164, _tipo = normalizar_telefone(telefone)
    linha = Blocklist(
        telefone_e164=e164,
        dominio=dominio_registravel(dominio),
        place_id=place_id,
        motivo=motivo,
    )
    sessao.add(linha)
    return linha


def esta_bloqueado(sessao: Session, place: Place) -> Blocklist | None:
    """Devolve a linha da blocklist que barra este registro, ou None se liberado."""
    if place.place_id:
        por_id = sessao.exec(
            select(Blocklist).where(col(Blocklist.place_id) == place.place_id)
        ).first()
        if por_id is not None:
            return por_id

    dominio = dominio_registravel(place.website_uri)
    if dominio and not e_compartilhado(dominio):
        por_dominio = sessao.exec(
            select(Blocklist).where(col(Blocklist.dominio) == dominio)
        ).first()
        if por_dominio is not None:
            return por_dominio

    e164, _tipo = normalizar_telefone(place.national_phone_number)
    if e164:
        por_telefone = sessao.exec(
            select(Blocklist).where(col(Blocklist.telefone_e164) == e164)
        ).first()
        if por_telefone is not None:
            return por_telefone

    return None


def chamadas_hoje(sessao: Session, agora: datetime | None = None) -> int:
    """Conta as chamadas feitas desde a meia-noite UTC — base do freio de custo."""
    instante = para_utc_naive(agora) if agora is not None else agora_utc()
    inicio_do_dia = datetime.combine(instante.date(), time.min)
    consulta = (
        select(func.count())
        .select_from(ApiCall)
        .where(col(ApiCall.timestamp) >= inicio_do_dia)
    )
    return int(sessao.exec(consulta).one())


def criar_job(sessao: Session, query: str, cidade: str) -> SearchJob:
    """Cria uma varredura no estado running e devolve o job já com id."""
    job = SearchJob(
        query=query,
        cidade=cidade,
        estado=EstadoJob.RUNNING,
        iniciado_em=agora_utc(),
    )
    sessao.add(job)
    sessao.commit()
    sessao.refresh(job)
    return job


def obter_job(sessao: Session, job_id: int) -> SearchJob | None:
    """Busca uma varredura pelo id."""
    return sessao.get(SearchJob, job_id)


def marcar_job(
    sessao: Session,
    job_id: int,
    estado: EstadoJob,
    *,
    erro: str | None = None,
    total_encontrado: int | None = None,
    total_processado: int | None = None,
) -> SearchJob | None:
    """Atualiza estado, totais e o instante de conclusão de uma varredura."""
    job = sessao.get(SearchJob, job_id)
    if job is None:
        return None

    job.estado = estado
    if erro is not None:
        job.erro = erro
    if total_encontrado is not None:
        job.total_encontrado = total_encontrado
    if total_processado is not None:
        job.total_processado = total_processado
    if estado in {EstadoJob.COMPLETED, EstadoJob.FAILED, EstadoJob.CANCELLED}:
        job.concluido_em = agora_utc()

    sessao.add(job)
    return job


def celula_ja_executada(sessao: Session, celula_id: str, categoria: str) -> bool:
    """Diz se a célula já foi consultada para essa categoria em qualquer execução."""
    return sessao.get(GridLog, (celula_id, categoria)) is not None


def registrar_celula(
    sessao: Session,
    *,
    celula_id: str,
    categoria: str,
    job_id: int | None,
    qtd_resultados: int,
    saturada: bool,
    nivel: int,
    agora: datetime | None = None,
) -> GridLog:
    """Marca a célula como executada para a categoria, tornando a retomada exata."""
    linha = GridLog(
        celula=celula_id,
        categoria=categoria,
        job_id=job_id,
        qtd_resultados=qtd_resultados,
        saturada=saturada,
        nivel=nivel,
        executado_em=para_utc_naive(agora) if agora is not None else agora_utc(),
    )
    sessao.add(linha)
    return linha


def listar_celulas(sessao: Session, categoria: str | None = None) -> list[GridLog]:
    """Lista as células já executadas, opcionalmente filtrando por categoria."""
    consulta = select(GridLog)
    if categoria is not None:
        consulta = consulta.where(col(GridLog.categoria) == categoria)
    return list(sessao.exec(consulta).all())


def listar_places_para_enriquecer(
    sessao: Session, *, forcar: bool = False, limite: int | None = None
) -> list[Place]:
    """Lista places que ainda não foram enriquecidos ou todos se forcar for True."""
    consulta = select(Place).order_by(col(Place.coletado_em))
    if not forcar:
        consulta = consulta.where(col(Place.enriquecido_em).is_(None))
    if limite is not None:
        consulta = consulta.limit(limite)
    return list(sessao.exec(consulta).all())


def salvar_place_enriquecido(sessao: Session, place: Place) -> None:
    """Atualiza os campos de diagnóstico e enriquecimento de um Place no banco."""
    sessao.add(place)
    sessao.commit()


def contar_pendentes_enriquecimento(sessao: Session) -> int:
    """Conta quantos lugares estão cadastrados mas ainda não foram enriquecidos."""
    consulta = (
        select(func.count())
        .select_from(Place)
        .where(col(Place.enriquecido_em).is_(None))
    )
    return int(sessao.exec(consulta).one())


def listar_places_para_rechecar(
    sessao: Session, *, dias: int = 60, limite: int | None = None
) -> list[Place]:
    """Lista lugares checados há mais de X dias para conformidade com a Places API."""
    limite_data = agora_utc() - timedelta(days=dias)
    consulta = (
        select(Place)
        .where(col(Place.checado_em) < limite_data)
        .order_by(col(Place.checado_em))
    )
    if limite is not None:
        consulta = consulta.limit(limite)
    return list(sessao.exec(consulta).all())


def listar_places_por_nivel(
    sessao: Session, *, nivel: int, limite: int | None = None
) -> list[Place]:
    """Lista lugares com um determinado nível de presença digital."""
    consulta = (
        select(Place)
        .where(col(Place.presence_level) == nivel)
        .order_by(col(Place.enriquecido_em).desc())
    )
    if limite is not None:
        consulta = consulta.limit(limite)
    return list(sessao.exec(consulta).all())


def listar_jobs(sessao: Session, limite: int = 10) -> list[SearchJob]:
    """Lista as varreduras mais recentes registradas no sistema."""
    consulta = select(SearchJob).order_by(col(SearchJob.id).desc()).limit(limite)
    return list(sessao.exec(consulta).all())


def registrar_zona_varrida(
    sessao: Session,
    *,
    cidade: str,
    categoria: str,
    lat: float,
    lng: float,
    raio_km: float,
    passo_m: float,
    total_encontrados: int = 0,
) -> ScanZone:
    """Registra uma nova zona geográfica varrida para memória de radar."""
    zona = ScanZone(
        cidade=cidade,
        categoria=categoria,
        lat=lat,
        lng=lng,
        raio_km=raio_km,
        passo_m=passo_m,
        total_encontrados=total_encontrados,
    )
    sessao.add(zona)
    sessao.commit()
    sessao.refresh(zona)
    return zona


def listar_zonas_varridas(
    sessao: Session,
    *,
    cidade: str | None = None,
    categoria: str | None = None,
    limite: int = 20,
) -> list[ScanZone]:
    """Lista zonas já varridas filtrando por cidade ou categoria."""
    consulta = select(ScanZone).order_by(col(ScanZone.criado_em).desc())
    if cidade:
        consulta = consulta.where(col(ScanZone.cidade) == cidade)
    if categoria:
        consulta = consulta.where(col(ScanZone.categoria) == categoria)
    return list(sessao.exec(consulta.limit(limite)).all())


def atualizar_status_lead(sessao: Session, place_id: str, novo_status: str) -> bool:
    """Atualiza o estágio do lead no funil de vendas (Kanban)."""
    place = sessao.get(Place, place_id)
    if not place:
        return False
    place.status_lead = novo_status
    sessao.add(place)
    sessao.commit()
    return True


def adicionar_nota_lead(
    sessao: Session,
    *,
    place_id: str,
    texto: str,
    autor: str = "davi",
) -> LeadNote:
    """Cria uma nova anotação de histórico comercial para o lead."""
    nota = LeadNote(
        place_id=place_id,
        texto=texto.strip(),
        autor=autor.strip(),
    )
    sessao.add(nota)
    sessao.commit()
    sessao.refresh(nota)
    return nota


def listar_notas_lead(sessao: Session, place_id: str) -> list[LeadNote]:
    """Retorna todas as notas de um lead em ordem cronológica reversa."""
    consulta = (
        select(LeadNote)
        .where(col(LeadNote.place_id) == place_id)
        .order_by(col(LeadNote.criado_em).desc())
    )
    return list(sessao.exec(consulta).all())
