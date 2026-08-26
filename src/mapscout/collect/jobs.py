"""Estados e tabelas das execuções de varredura."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from sqlmodel import Field, SQLModel


class EstadoJob(StrEnum):
    """Estados possíveis de uma varredura."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED_QUOTA = "paused_quota"


class SearchJob(SQLModel, table=True):
    """Uma execução de varredura, retomável entre processos."""

    __tablename__ = "search_jobs"

    id: int | None = Field(default=None, primary_key=True)
    query: str
    cidade: str
    estado: str = Field(default=EstadoJob.PENDING)
    total_encontrado: int = 0
    total_processado: int = 0
    iniciado_em: datetime | None = None
    concluido_em: datetime | None = None
    erro: str | None = None


class GridLog(SQLModel, table=True):
    """Célula já executada para uma categoria — é o que permite retomar sem repetir."""

    __tablename__ = "grid_log"

    celula: str = Field(primary_key=True)
    categoria: str = Field(primary_key=True)
    job_id: int | None = None
    qtd_resultados: int = 0
    saturada: bool = False
    nivel: int = 0
    executado_em: datetime | None = None
