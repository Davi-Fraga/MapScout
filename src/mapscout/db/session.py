"""Engine SQLite, criação das tabelas e migração de colunas."""

from __future__ import annotations

import os
from typing import Any

from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, create_engine

from mapscout.collect import jobs as _jobs
from mapscout.db import models as _models
from mapscout.db.migrations import garantir_colunas

DATABASE_URL_PADRAO = "sqlite:///./mapscout.db"

__all__ = [
    "abrir_sessao",
    "criar_engine",
    "criar_tabelas",
    "normalizar_database_url",
    "obter_database_url",
    "preparar_banco",
]

# Importados só para registrar as tabelas em SQLModel.metadata.
_ = (_models, _jobs)


def obter_database_url() -> str:
    """Lê DATABASE_URL do ambiente, caindo no SQLite local por padrão."""
    return os.environ.get("DATABASE_URL") or DATABASE_URL_PADRAO


def normalizar_database_url(url: str) -> str:
    """Normaliza o esquema da URL de banco para drivers SQLAlchemy compatíveis."""
    url_limpa = url.strip()
    if url_limpa.startswith("postgres://"):
        return url_limpa.replace("postgres://", "postgresql+psycopg://", 1)
    if url_limpa.startswith("postgresql://") and "+psycopg" not in url_limpa:
        return url_limpa.replace("postgresql://", "postgresql+psycopg://", 1)
    return url_limpa


def criar_engine(url: str | None = None) -> Engine:
    """Cria a engine SQLAlchemy para a URL informada ou a do ambiente."""
    db_url = normalizar_database_url(url or obter_database_url())
    is_sqlite = db_url.startswith("sqlite")
    kwargs: dict[str, Any] = {}
    if not is_sqlite:
        kwargs["pool_pre_ping"] = True
    return create_engine(db_url, **kwargs)


def criar_tabelas(engine: Engine) -> None:
    """Cria as tabelas que ainda não existirem no banco."""
    SQLModel.metadata.create_all(engine)


def preparar_banco(engine: Engine) -> list[str]:
    """Cria tabelas faltantes e adiciona colunas novas às que já existem."""
    criar_tabelas(engine)
    return garantir_colunas(engine)


def abrir_sessao(engine: Engine) -> Session:
    """Abre uma sessão de banco ligada à engine."""
    return Session(engine)
