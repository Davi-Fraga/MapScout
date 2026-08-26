"""Testes do repositório: upsert idempotente e auditoria de chamadas."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from sqlmodel import Session

from mapscout.db.models import Place
from mapscout.db.repo import (
    contar_api_calls,
    contar_places,
    listar_places,
    place_de_resposta,
    registrar_api_call,
    upsert_place,
)
from mapscout.sources.places_api import ENDPOINT, PaginaResposta, RegistroChamada

ONTEM = datetime(2026, 8, 25, 12, 0, tzinfo=UTC)
HOJE = datetime(2026, 8, 26, 12, 0, tzinfo=UTC)

# O SQLite não guarda tzinfo: o repositório normaliza tudo para UTC sem timezone.
ONTEM_GRAVADO = ONTEM.replace(tzinfo=None)
HOJE_GRAVADO = HOJE.replace(tzinfo=None)


def _places_do_fixture(pagina: dict[str, Any]) -> list[Place]:
    return [place_de_resposta(p) for p in PaginaResposta.model_validate(pagina).places]


def test_place_de_resposta_achata_os_campos(pagina_places: dict[str, Any]) -> None:
    place = _places_do_fixture(pagina_places)[0]

    assert place.place_id == "ChIJ3Ssrf0rPyJQR-4Xd6fHI26k"
    assert place.display_name == "Dra. Beatriz Toriani, Dentista"
    assert place.latitude is not None
    assert place.longitude is not None
    assert place.primary_type_display_name == "Dentista"
    assert json.loads(place.types or "[]")[0] == "dentist"


def test_upsert_cria_registro_novo(
    sessao: Session, pagina_places: dict[str, Any]
) -> None:
    place = _places_do_fixture(pagina_places)[0]

    criou = upsert_place(sessao, place, agora=ONTEM)
    sessao.commit()

    assert criou is True
    assert contar_places(sessao) == 1
    gravado = sessao.get(Place, place.place_id)
    assert gravado is not None
    assert gravado.coletado_em == ONTEM_GRAVADO
    assert gravado.checado_em == ONTEM_GRAVADO


def test_upsert_e_idempotente_por_place_id(
    sessao: Session, pagina_places: dict[str, Any]
) -> None:
    places = _places_do_fixture(pagina_places)

    for place in places:
        upsert_place(sessao, place, agora=ONTEM)
    sessao.commit()
    for place in _places_do_fixture(pagina_places):
        upsert_place(sessao, place, agora=HOJE)
    sessao.commit()

    assert contar_places(sessao) == 20


def test_upsert_preserva_coletado_em_e_atualiza_checado_em(
    sessao: Session, pagina_places: dict[str, Any]
) -> None:
    place = _places_do_fixture(pagina_places)[0]
    upsert_place(sessao, place, agora=ONTEM)
    sessao.commit()

    de_novo = _places_do_fixture(pagina_places)[0]
    de_novo.website_uri = "https://mudou.com.br/"
    criou = upsert_place(sessao, de_novo, agora=HOJE)
    sessao.commit()

    gravado = sessao.get(Place, place.place_id)
    assert criou is False
    assert gravado is not None
    assert gravado.coletado_em == ONTEM_GRAVADO
    assert gravado.checado_em == HOJE_GRAVADO
    assert gravado.website_uri == "https://mudou.com.br/"


def test_listar_places_respeita_o_limite(
    sessao: Session, pagina_places: dict[str, Any]
) -> None:
    for place in _places_do_fixture(pagina_places):
        upsert_place(sessao, place, agora=ONTEM)
    sessao.commit()

    assert len(listar_places(sessao, limite=5)) == 5


def test_registrar_api_call_grava_a_auditoria(sessao: Session) -> None:
    registro = RegistroChamada(
        endpoint=ENDPOINT,
        timestamp=HOJE,
        qtd_resultados=20,
        field_mask="places.id,nextPageToken",
        status_code=200,
    )

    linha = registrar_api_call(sessao, registro)
    sessao.commit()

    assert contar_api_calls(sessao) == 1
    assert linha.timestamp == HOJE_GRAVADO
    assert linha.timestamp.tzinfo is None


def test_datas_sao_comparaveis_depois_de_reler(
    sessao: Session, pagina_places: dict[str, Any]
) -> None:
    """Datas relidas do banco precisam comparar sem TypeError de naive vs aware."""
    place = _places_do_fixture(pagina_places)[0]
    upsert_place(sessao, place, agora=ONTEM)
    sessao.commit()

    gravado = sessao.get(Place, place.place_id)
    assert gravado is not None
    assert (HOJE_GRAVADO - gravado.checado_em).days == 1
