"""Cliente async da Google Places API (New), endpoint places:searchText."""

from __future__ import annotations

import asyncio
import math
import os
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

import httpx
from pydantic import BaseModel, ConfigDict, Field

ENDPOINT = "https://places.googleapis.com/v1/places:searchText"
TIMEOUT_S = 30.0
PAGE_SIZE = 20
MAX_PAGINAS = 3
PAUSA_PAGE_TOKEN_S = 2.0
MAX_TENTATIVAS = 3
BACKOFF_BASE_S = 1.0
STATUS_RETENTAVEIS = frozenset({429, 500, 502, 503, 504})

METROS_POR_GRAU_LAT = 111_320.0

Dormir = Callable[[float], Awaitable[None]]
"""Função de espera; injetável para que os testes não durmam de verdade."""

CAMPOS_PADRAO: tuple[str, ...] = (
    "id",
    "displayName",
    "formattedAddress",
    "location",
    "nationalPhoneNumber",
    "websiteUri",
    "rating",
    "userRatingCount",
    "businessStatus",
    "googleMapsUri",
    "types",
    "primaryTypeDisplayName",
)


def montar_field_mask(campos: Sequence[str] = CAMPOS_PADRAO) -> str:
    """Monta o valor do header X-Goog-FieldMask a partir dos campos pedidos."""
    return ",".join([f"places.{campo}" for campo in campos] + ["nextPageToken"])


class TextoLocalizado(BaseModel):
    """Par texto + idioma usado em displayName e primaryTypeDisplayName."""

    model_config = ConfigDict(populate_by_name=True)

    texto: str = Field(alias="text")
    idioma: str | None = Field(default=None, alias="languageCode")


class Coordenada(BaseModel):
    """Latitude e longitude de um lugar."""

    latitude: float
    longitude: float


class PlaceResposta(BaseModel):
    """Um lugar como a Places API (New) o devolve em places:searchText."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    nome: TextoLocalizado = Field(alias="displayName")
    endereco: str | None = Field(default=None, alias="formattedAddress")
    localizacao: Coordenada | None = Field(default=None, alias="location")
    telefone: str | None = Field(default=None, alias="nationalPhoneNumber")
    site: str | None = Field(default=None, alias="websiteUri")
    nota: float | None = Field(default=None, alias="rating")
    qtd_avaliacoes: int | None = Field(default=None, alias="userRatingCount")
    status: str | None = Field(default=None, alias="businessStatus")
    maps_uri: str | None = Field(default=None, alias="googleMapsUri")
    tipos: list[str] = Field(default_factory=list, alias="types")
    tipo_principal: TextoLocalizado | None = Field(
        default=None, alias="primaryTypeDisplayName"
    )


class PaginaResposta(BaseModel):
    """Uma página de resultados de places:searchText."""

    model_config = ConfigDict(populate_by_name=True)

    places: list[PlaceResposta] = Field(default_factory=list)
    proximo_token: str | None = Field(default=None, alias="nextPageToken")


@dataclass(frozen=True)
class Retangulo:
    """Retângulo geográfico aceito por locationRestriction no searchText."""

    lat_min: float
    lng_min: float
    lat_max: float
    lng_max: float

    def para_json(self) -> dict[str, dict[str, float]]:
        """Serializa o retângulo no formato low/high esperado pela API."""
        return {
            "low": {"latitude": self.lat_min, "longitude": self.lng_min},
            "high": {"latitude": self.lat_max, "longitude": self.lng_max},
        }


@dataclass(frozen=True)
class RegistroChamada:
    """Uma tentativa de requisição HTTP à Places API, para auditoria de custo."""

    endpoint: str
    timestamp: datetime
    qtd_resultados: int
    field_mask: str
    status_code: int


@dataclass(frozen=True)
class ResultadoBusca:
    """Lugares coletados e o registro de cada tentativa HTTP feita."""

    places: list[PlaceResposta]
    chamadas: list[RegistroChamada]


def retangulo_do_raio(lat: float, lng: float, raio_m: float) -> Retangulo:
    """Converte centro e raio em metros no retângulo que circunscreve o círculo."""
    delta_lat = raio_m / METROS_POR_GRAU_LAT
    cos_lat = max(math.cos(math.radians(lat)), 1e-6)
    delta_lng = raio_m / (METROS_POR_GRAU_LAT * cos_lat)
    return Retangulo(
        lat_min=max(lat - delta_lat, -90.0),
        lng_min=max(lng - delta_lng, -180.0),
        lat_max=min(lat + delta_lat, 90.0),
        lng_max=min(lng + delta_lng, 180.0),
    )


def _obter_api_key(api_key: str | None) -> str:
    """Devolve a chave da API recebida ou a de GOOGLE_MAPS_API_KEY."""
    if api_key:
        return api_key
    chave = os.environ.get("GOOGLE_MAPS_API_KEY")
    if not chave:
        msg = "GOOGLE_MAPS_API_KEY não está definida no ambiente"
        raise RuntimeError(msg)
    return chave


async def _postar_com_retry(
    cliente: httpx.AsyncClient,
    corpo: dict[str, object],
    cabecalhos: dict[str, str],
    field_mask: str,
    chamadas: list[RegistroChamada],
    dormir: Dormir,
) -> dict[str, object]:
    """Faz o POST com backoff exponencial em 429 e 5xx, registrando cada tentativa."""
    resposta: httpx.Response | None = None
    for tentativa in range(1, MAX_TENTATIVAS + 1):
        resposta = await cliente.post(ENDPOINT, json=corpo, headers=cabecalhos)
        dados = _corpo_json(resposta)
        places = dados.get("places")
        chamadas.append(
            RegistroChamada(
                endpoint=ENDPOINT,
                timestamp=datetime.now(UTC),
                qtd_resultados=len(places) if isinstance(places, list) else 0,
                field_mask=field_mask,
                status_code=resposta.status_code,
            )
        )
        if resposta.status_code in STATUS_RETENTAVEIS and tentativa < MAX_TENTATIVAS:
            await dormir(BACKOFF_BASE_S * 2 ** (tentativa - 1))
            continue
        resposta.raise_for_status()
        return dados
    resposta.raise_for_status()  # type: ignore[union-attr]
    return {}


def _corpo_json(resposta: httpx.Response) -> dict[str, object]:
    """Lê o corpo JSON da resposta, devolvendo dict vazio quando não houver."""
    try:
        dados = resposta.json()
    except ValueError:
        return {}
    return dados if isinstance(dados, dict) else {}


async def buscar_texto(
    *,
    texto: str,
    retangulo: Retangulo | None = None,
    campos: Sequence[str] = CAMPOS_PADRAO,
    max_paginas: int = MAX_PAGINAS,
    page_size: int = PAGE_SIZE,
    api_key: str | None = None,
    cliente: httpx.AsyncClient | None = None,
    dormir: Dormir = asyncio.sleep,
) -> ResultadoBusca:
    """Busca lugares por texto, paginando até max_paginas e registrando as chamadas."""
    field_mask = montar_field_mask(campos)
    cabecalhos = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": _obter_api_key(api_key),
        "X-Goog-FieldMask": field_mask,
    }
    encontrados: list[PlaceResposta] = []
    chamadas: list[RegistroChamada] = []
    token: str | None = None
    paginas = 0

    proprio = cliente is None
    http = cliente or httpx.AsyncClient(timeout=TIMEOUT_S)
    try:
        while paginas < max_paginas:
            corpo: dict[str, object] = {
                "textQuery": texto,
                "pageSize": min(page_size, PAGE_SIZE),
            }
            if retangulo is not None:
                corpo["locationRestriction"] = {"rectangle": retangulo.para_json()}
            if token:
                await dormir(PAUSA_PAGE_TOKEN_S)
                corpo["pageToken"] = token

            dados = await _postar_com_retry(
                http, corpo, cabecalhos, field_mask, chamadas, dormir
            )
            pagina = PaginaResposta.model_validate(dados)
            encontrados.extend(pagina.places)
            paginas += 1
            token = pagina.proximo_token
            if not token:
                break
    finally:
        if proprio:
            await http.aclose()

    return ResultadoBusca(places=encontrados, chamadas=chamadas)
