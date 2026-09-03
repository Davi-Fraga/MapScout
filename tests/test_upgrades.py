"""Testes automatizados dos novos recursos de CRM, Kanban e Memória Geográfica."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from mapscout.auth import COOKIE_NAME, gerar_token_sessao
from mapscout.db.models import Place
from mapscout.db.repo import (
    adicionar_nota_lead,
    atualizar_status_lead,
    listar_notas_lead,
    listar_zonas_varridas,
    registrar_zona_varrida,
    upsert_place,
)
from mapscout.db.session import normalizar_database_url
from mapscout.geo.cidades import calcular_deslocamento_coordenadas
from mapscout.web.app import app, obter_sessao

client = TestClient(app)


@pytest.fixture(autouse=True)
def configurar_sessao_teste(sessao: Session) -> Iterator[None]:
    """Sobrescreve a dependência de sessão do FastAPI com banco em memória."""
    app.dependency_overrides[obter_sessao] = lambda: sessao
    client.cookies.set(COOKIE_NAME, gerar_token_sessao("admin"))
    yield
    client.cookies.clear()
    app.dependency_overrides.clear()


def test_normalizar_database_url() -> None:
    """Verifica normalização de URLs postgres para SQLAlchemy com psycopg."""
    url_pg = "postgres://user:pass@host:5432/db"
    assert (
        normalizar_database_url(url_pg) == "postgresql+psycopg://user:pass@host:5432/db"
    )

    url_standard = "postgresql://user:pass@host:5432/db"
    assert (
        normalizar_database_url(url_standard)
        == "postgresql+psycopg://user:pass@host:5432/db"
    )

    url_sqlite = "sqlite:///./mapscout.db"
    assert normalizar_database_url(url_sqlite) == "sqlite:///./mapscout.db"


def test_calcular_deslocamento_coordenadas() -> None:
    """Valida cálculo de deslocamento geográfico por direções cardeais."""
    lat_orig = -23.9608
    lng_orig = -46.3336

    lat_norte, _ = calcular_deslocamento_coordenadas(lat_orig, lng_orig, "norte", 10.0)
    assert lat_norte > lat_orig

    lat_sul, _ = calcular_deslocamento_coordenadas(lat_orig, lng_orig, "sul", 10.0)
    assert lat_sul < lat_orig

    _, lng_leste = calcular_deslocamento_coordenadas(lat_orig, lng_orig, "leste", 10.0)
    assert lng_leste > lng_orig

    _, lng_oeste = calcular_deslocamento_coordenadas(lat_orig, lng_orig, "oeste", 10.0)
    assert lng_oeste < lng_orig


def test_memoria_zonas_varridas(sessao: Session) -> None:
    """Testa persistência e consulta do histórico de zonas mapeadas."""
    zona = registrar_zona_varrida(
        sessao,
        cidade="Santos",
        categoria="dentista",
        lat=-23.9608,
        lng=-46.3336,
        raio_km=5.0,
        passo_m=1000.0,
        total_encontrados=42,
    )
    assert zona.id is not None

    zonas = listar_zonas_varridas(sessao, cidade="Santos")
    assert len(zonas) == 1
    assert zonas[0].total_encontrados == 42


def test_notas_lead_e_historico(sessao: Session) -> None:
    """Valida inserção e listagem cronológica de notas comerciais."""
    p = Place(place_id="lead_teste_1", display_name="Clínica Exemplo")
    upsert_place(sessao, p)

    nota1 = adicionar_nota_lead(
        sessao, place_id="lead_teste_1", texto="Falei com recepcionista", autor="davi"
    )
    nota2 = adicionar_nota_lead(
        sessao,
        place_id="lead_teste_1",
        texto="Enviei proposta comercial",
        autor="socio",
    )

    assert nota1.id is not None
    assert nota2.id is not None

    notas = listar_notas_lead(sessao, "lead_teste_1")
    assert len(notas) == 2
    assert "Enviei proposta comercial" in [n.texto for n in notas]


def test_atualizar_status_lead_funil(sessao: Session) -> None:
    """Verifica transição de estágio do lead no funil de vendas."""
    p = Place(place_id="lead_kanban", display_name="Empresa do Funil")
    upsert_place(sessao, p)

    sucesso = atualizar_status_lead(sessao, "lead_kanban", "proposta")
    assert sucesso is True

    place_atualizado = sessao.get(Place, "lead_kanban")
    assert place_atualizado is not None
    assert place_atualizado.status_lead == "proposta"


def test_endpoints_kanban_e_notas(sessao: Session) -> None:
    """Testa endpoints web do Kanban, adição de notas e deslocamento geográfico."""
    p = Place(
        place_id="place_web_1", display_name="Escritório Alfa", status_lead="novo"
    )
    upsert_place(sessao, p)

    # 1. Kanban
    resp_kanban = client.get("/partials/kanban")
    assert resp_kanban.status_code == 200
    assert "Escritório Alfa" in resp_kanban.text
    assert "Novos Leads" in resp_kanban.text

    # 2. Atualizar status via POST
    resp_status = client.post(
        "/api/leads/place_web_1/status", data={"status": "em_conversa"}
    )
    assert resp_status.status_code == 200
    assert "Escritório Alfa" in resp_status.text

    # 3. Adicionar nota
    resp_nota = client.post(
        "/api/leads/place_web_1/notas", data={"texto": "Reunião agendada para sexta"}
    )
    assert resp_nota.status_code == 200
    assert "Reunião agendada para sexta" in resp_nota.text

    # 4. Deslocamento geográfico
    resp_geo = client.get(
        "/api/geo/deslocamento?lat=-23.55&lng=-46.63&direcao=norte&distancia_km=5"
    )
    assert resp_geo.status_code == 200
    dados_geo = resp_geo.json()
    assert "lat" in dados_geo and "lng" in dados_geo
