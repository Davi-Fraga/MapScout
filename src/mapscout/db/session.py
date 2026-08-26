"""Engine SQLite e criação das tabelas."""

from __future__ import annotations

import os

from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, create_engine

from mapscout.db import models as _models

DATABASE_URL_PADRAO = "sqlite:///./mapscout.db"

__all__ = ["abrir_sessao", "criar_engine", "criar_tabelas", "obter_database_url"]

_ = _models  # garante que as tabelas estejam registradas em SQLModel.metadata


def obter_database_url() -> str:
    """Lê DATABASE_URL do ambiente, caindo no SQLite local por padrão."""
    return os.environ.get("DATABASE_URL") or DATABASE_URL_PADRAO


def criar_engine(url: str | None = None) -> Engine:
    """Cria a engine SQLAlchemy para a URL informada ou a do ambiente."""
    return create_engine(url or obter_database_url())


def criar_tabelas(engine: Engine) -> None:
    """Cria as tabelas que ainda não existirem no banco."""
    SQLModel.metadata.create_all(engine)


def abrir_sessao(engine: Engine) -> Session:
    """Abre uma sessão de banco ligada à engine."""
    return Session(engine)
