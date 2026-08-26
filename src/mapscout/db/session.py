"""Engine SQLite, criação das tabelas e migração de colunas."""

from __future__ import annotations

import os

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
    "obter_database_url",
    "preparar_banco",
]

# Importados só para registrar as tabelas em SQLModel.metadata.
_ = (_models, _jobs)


def obter_database_url() -> str:
    """Lê DATABASE_URL do ambiente, caindo no SQLite local por padrão."""
    return os.environ.get("DATABASE_URL") or DATABASE_URL_PADRAO


def criar_engine(url: str | None = None) -> Engine:
    """Cria a engine SQLAlchemy para a URL informada ou a do ambiente."""
    return create_engine(url or obter_database_url())


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
