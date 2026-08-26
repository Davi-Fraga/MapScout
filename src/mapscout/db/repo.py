"""Repositório: todo acesso ao banco passa por aqui."""

from __future__ import annotations

import json
from datetime import datetime

from sqlmodel import Session, col, func, select

from mapscout.db.models import ApiCall, Place, agora_utc, para_utc_naive
from mapscout.sources.places_api import PlaceResposta, RegistroChamada

CAMPOS_PRESERVADOS = frozenset({"place_id", "coletado_em", "checado_em"})


def place_de_resposta(resposta: PlaceResposta) -> Place:
    """Converte um lugar da Places API no modelo persistido."""
    return Place(
        place_id=resposta.id,
        display_name=resposta.nome.texto,
        formatted_address=resposta.endereco,
        latitude=resposta.localizacao.latitude if resposta.localizacao else None,
        longitude=resposta.localizacao.longitude if resposta.localizacao else None,
        national_phone_number=resposta.telefone,
        website_uri=resposta.site,
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


def contar_places(sessao: Session) -> int:
    """Conta quantos places existem no banco."""
    return int(sessao.exec(select(func.count()).select_from(Place)).one())


def contar_api_calls(sessao: Session) -> int:
    """Conta quantas chamadas à Places API foram registradas."""
    return int(sessao.exec(select(func.count()).select_from(ApiCall)).one())
