from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from mapscout.auth import COOKIE_NAME, gerar_token_sessao
from mapscout.db.models import Place
from mapscout.db.repo import upsert_place
from mapscout.web.app import app, obter_sessao

client = TestClient(app)


@pytest.fixture(autouse=True)
def configurar_sessao_teste(sessao: Session) -> Iterator[None]:
    """Sobrescreve a dependência de sessão do FastAPI para usar a fixture em memória."""
    app.dependency_overrides[obter_sessao] = lambda: sessao
    client.cookies.set(COOKIE_NAME, gerar_token_sessao("admin"))
    yield
    client.cookies.clear()
    app.dependency_overrides.clear()


def test_index_page(sessao: Session) -> None:
    p = Place(
        place_id="web1",
        display_name="Consultório Dr. Marcelo",
        cidade="Campinas",
        presence_level=0,
        score=95.0,
    )
    upsert_place(sessao, p)
    sessao.commit()

    response = client.get("/")
    assert response.status_code == 200
    assert "MapScout" in response.text
    assert "Radar de Oportunidades" in response.text


def test_filtrar_leads_endpoint(sessao: Session) -> None:
    p = Place(
        place_id="web2",
        display_name="Auto Mecânica Silva",
        cidade="Campinas",
        presence_level=2,
        score=90.0,
    )
    upsert_place(sessao, p)
    sessao.commit()

    response = client.get("/partials/leads?busca=Mecânica")
    assert response.status_code == 200
    assert "Auto Mecânica Silva" in response.text


def test_modal_detalhes_lead(sessao: Session) -> None:
    p = Place(
        place_id="web3",
        display_name="Pizzaria Napoli",
        cidade="Campinas",
        presence_level=0,
        presence_evidence="Não possui site cadastrado.",
        score=95.0,
    )
    upsert_place(sessao, p)
    sessao.commit()

    response = client.get("/partials/lead/web3")
    assert response.status_code == 200
    assert "Pizzaria Napoli" in response.text
    assert "Rascunho de Abordagem" in response.text


def test_atualizar_status_lead(sessao: Session) -> None:
    p = Place(
        place_id="web4",
        display_name="Clínica Odonto",
        cidade="Campinas",
        presence_level=0,
        score=95.0,
        status_lead="novo",
    )
    upsert_place(sessao, p)
    sessao.commit()

    response = client.post(
        "/api/lead/web4/status",
        data={"novo_status": "contatado"},
    )
    assert response.status_code == 200
    assert "contatado" in response.text
