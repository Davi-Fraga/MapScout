"""Tabelas SQLModel do MapScout."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlmodel import Field, SQLModel


def agora_utc() -> datetime:
    """Devolve o instante atual em UTC, sem tzinfo — o SQLite não a armazena."""
    return datetime.now(UTC).replace(tzinfo=None)


def para_utc_naive(momento: datetime) -> datetime:
    """Normaliza um datetime para UTC sem tzinfo, a convenção de armazenamento."""
    if momento.tzinfo is None:
        return momento
    return momento.astimezone(UTC).replace(tzinfo=None)


class Place(SQLModel, table=True):
    """Empresa descoberta na Places API, identificada pelo place_id."""

    __tablename__ = "places"

    place_id: str = Field(primary_key=True)
    display_name: str
    formatted_address: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    national_phone_number: str | None = None
    website_uri: str | None = None
    rating: float | None = None
    user_rating_count: int | None = None
    business_status: str | None = None
    google_maps_uri: str | None = None
    types: str | None = None
    primary_type_display_name: str | None = None
    cidade: str | None = None
    coletado_em: datetime = Field(default_factory=agora_utc)
    checado_em: datetime = Field(default_factory=agora_utc)


class Blocklist(SQLModel, table=True):
    """Opt-out de LGPD: quem nunca deve ser abordado nem sair numa exportação."""

    __tablename__ = "blocklist"

    id: int | None = Field(default=None, primary_key=True)
    telefone_e164: str | None = Field(default=None, index=True)
    dominio: str | None = Field(default=None, index=True)
    place_id: str | None = Field(default=None, index=True)
    motivo: str
    data: datetime = Field(default_factory=agora_utc)


class ApiCall(SQLModel, table=True):
    """Uma tentativa de chamada à Places API, para auditoria de custo."""

    __tablename__ = "api_calls"

    id: int | None = Field(default=None, primary_key=True)
    endpoint: str
    timestamp: datetime
    qtd_resultados: int
    field_mask: str
    status_code: int
