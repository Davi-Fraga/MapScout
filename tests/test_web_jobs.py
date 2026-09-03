"""Testes dos endpoints web para background jobs e automações do MapScout."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from mapscout.auth import COOKIE_NAME, gerar_token_sessao
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


def test_status_job_endpoint() -> None:
    """Verifica retorno do endpoint HTMX de status do job."""
    response = client.get("/partials/jobs/status")
    assert response.status_code == 200
    assert "job-status-banner" in response.text


def test_modal_nova_varredura_endpoint() -> None:
    """Verifica retorno do modal de nova varredura com campos e presets."""
    response = client.get("/partials/modal/varrer")
    assert response.status_code == 200
    assert "Nova Varredura" in response.text
    assert "Campinas" in response.text
    assert "input-categoria" in response.text


def test_modal_automacoes_endpoint() -> None:
    """Verifica retorno do modal com tarefas agendadas do APScheduler."""
    response = client.get("/partials/automacoes")
    assert response.status_code == 200
    assert "Automações em Segundo Plano" in response.text
    assert "APScheduler" in response.text


def test_enriquecer_job_endpoint() -> None:
    """Verifica disparo de enriquecimento via requisição POST."""
    response = client.post("/api/jobs/enriquecer")
    assert response.status_code == 200
    assert "job-status-banner" in response.text


def test_cancelar_job_endpoint() -> None:
    """Verifica cancelamento de job via requisição POST."""
    response = client.post("/api/jobs/cancelar")
    assert response.status_code == 200
    assert "job-status-banner" in response.text


def test_disparar_automacao_endpoint() -> None:
    """Verifica execução manual de rotina de conformidade."""
    response = client.post("/api/automacoes/conformidade_google/executar")
    assert response.status_code == 200
    assert "sucesso" in response.text.lower()


def test_favicon_endpoint() -> None:
    """Verifica que /favicon.ico responde com 200 OK e imagem SVG."""
    response = client.get("/favicon.ico")
    assert response.status_code == 200
    assert "svg" in response.headers.get("content-type", "")


def test_buscar_cidades_endpoint() -> None:
    """Verifica endpoint de autocompletar de cidades brasileiras."""
    response = client.get("/api/cidades/busca?q=Campinas")
    assert response.status_code == 200
    dados = response.json()
    assert len(dados) > 0
    assert dados[0]["nome"] == "Campinas"
    assert dados[0]["uf"] == "SP"
