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
    presence_level: int | None = Field(default=None, index=True)
    presence_evidence: str | None = None
    website_status_code: int | None = None
    has_ssl: bool | None = None
    has_mobile_viewport: bool | None = None
    copyright_year: int | None = None
    emails: str | None = None
    instagram_url: str | None = None
    facebook_url: str | None = None
    whatsapp_url: str | None = None
    tech_detected: str | None = None
    enriquecido_em: datetime | None = None
    score: float | None = Field(default=None, index=True)
    status_lead: str = Field(default="novo", index=True)
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


class AiCache(SQLModel, table=True):
    """Cache de respostas da IA para evitar reprocessamento e gasto com tokens."""

    __tablename__ = "ai_cache"

    id: int | None = Field(default=None, primary_key=True)
    place_id: str = Field(index=True)
    hash_entrada: str = Field(index=True)
    resposta_json: str
    criado_em: datetime = Field(default_factory=agora_utc)


class ScanZone(SQLModel, table=True):
    """Zona geográfica que já foi varrida para evitar chamadas redundantes."""

    __tablename__ = "scan_zones"

    id: int | None = Field(default=None, primary_key=True)
    cidade: str = Field(index=True)
    categoria: str = Field(index=True)
    lat: float
    lng: float
    raio_km: float = 5.0
    passo_m: float = 1000.0
    total_encontrados: int = 0
    criado_em: datetime = Field(default_factory=agora_utc)


class LeadNote(SQLModel, table=True):
    """Anotação comercial e histórico de contato com um lead."""

    __tablename__ = "lead_notes"

    id: int | None = Field(default=None, primary_key=True)
    place_id: str = Field(foreign_key="places.place_id", index=True)
    autor: str = "davi"
    texto: str
    criado_em: datetime = Field(default_factory=agora_utc)
