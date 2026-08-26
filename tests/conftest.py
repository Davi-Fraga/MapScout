"""Fixtures compartilhadas. Testes nunca acessam a rede."""

from __future__ import annotations

import copy
import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy.engine import Engine
from sqlmodel import Session

from mapscout.db.session import criar_tabelas
from mapscout.sources.places_api import ENDPOINT, Dormir

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def pagina_places() -> dict[str, Any]:
    """Resposta real de places:searchText capturada da API."""
    with (FIXTURES / "places_searchtext.json").open(encoding="utf-8") as arquivo:
        dados: dict[str, Any] = json.load(arquivo)
    return dados


@pytest.fixture
def pagina_final(pagina_places: dict[str, Any]) -> dict[str, Any]:
    """A mesma resposta real, sem nextPageToken — última página."""
    ultima = copy.deepcopy(pagina_places)
    ultima.pop("nextPageToken", None)
    return ultima


@pytest.fixture
def dormidas() -> list[float]:
    """Acumula os intervalos que o cliente pediu para dormir."""
    return []


@pytest.fixture
def dormir_falso(dormidas: list[float]) -> Dormir:
    """Substituto de asyncio.sleep que registra o intervalo e não espera."""

    async def _dormir(segundos: float) -> None:
        dormidas.append(segundos)

    return _dormir


@pytest.fixture
def url_places() -> str:
    """Endpoint da Places API usado nos mocks de rede."""
    return ENDPOINT


@pytest.fixture
def engine_memoria() -> Iterator[Engine]:
    """Engine SQLite em arquivo temporário com as tabelas já criadas."""
    from sqlalchemy.pool import StaticPool
    from sqlmodel import create_engine

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    criar_tabelas(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def sessao(engine_memoria: Engine) -> Iterator[Session]:
    """Sessão aberta sobre a engine em memória."""
    with Session(engine_memoria) as aberta:
        yield aberta


@pytest.fixture(autouse=True)
def api_key_falsa(monkeypatch: pytest.MonkeyPatch) -> None:
    """Garante uma chave de API no ambiente sem tocar em .env."""
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "chave-de-teste")
