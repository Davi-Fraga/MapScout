"""Serviço de enriquecimento e diagnóstico completo de presença digital."""

from __future__ import annotations

import asyncio
from collections.abc import Callable

import httpx

from mapscout.classification.presence import (
    classificar_por_url,
    classificar_site_proprio,
)
from mapscout.db.models import Place, agora_utc
from mapscout.enrichment.fetcher import buscar_pagina


async def enriquecer_place(
    place: Place,
    *,
    client: httpx.AsyncClient | None = None,
) -> Place:
    """Aplica o diagnóstico de presença digital e enriquece os dados do Place."""
    # 1. Tenta classificação imediata pela URL (níveis 0, 1, 3, 5, 6, 7)
    preliminar = classificar_por_url(place.website_uri)
    if preliminar is not None:
        place.presence_level = preliminar.nivel
        place.presence_evidence = preliminar.evidencia
        place.enriquecido_em = agora_utc()
        return place

    # 2. Domínio próprio: executa crawler e análise técnica
    assert place.website_uri is not None
    fetch_res = await buscar_pagina(place.website_uri, client=client)
    sinais = fetch_res.sinais

    diagnostico = classificar_site_proprio(
        status_code=fetch_res.status_code,
        has_ssl=fetch_res.has_ssl,
        has_mobile_viewport=sinais.has_mobile_viewport,
        copyright_year=sinais.copyright_year,
        is_parked_or_empty=sinais.is_parked_or_empty,
        erro_conexao=fetch_res.erro,
    )

    place.presence_level = diagnostico.nivel
    place.presence_evidence = diagnostico.evidencia
    place.website_status_code = fetch_res.status_code
    place.has_ssl = fetch_res.has_ssl
    place.has_mobile_viewport = sinais.has_mobile_viewport
    place.copyright_year = sinais.copyright_year
    place.emails = ", ".join(sinais.emails) if sinais.emails else None
    place.instagram_url = sinais.instagram_url
    place.facebook_url = sinais.facebook_url
    place.whatsapp_url = sinais.whatsapp_url
    place.tech_detected = (
        ", ".join(sinais.tech_detected) if sinais.tech_detected else None
    )
    place.enriquecido_em = agora_utc()

    return place


async def enriquecer_lote(
    places: list[Place],
    *,
    client: httpx.AsyncClient | None = None,
    concorrencia: int = 5,
    ao_progredir: Callable[[int, int], None] | None = None,
) -> list[Place]:
    """Enriquece uma lista de places em paralelo com limite de concorrência."""
    semaforo = asyncio.Semaphore(concorrencia)
    contador = 0
    total = len(places)

    async def _processar(p: Place, cli: httpx.AsyncClient | None) -> Place:
        nonlocal contador
        async with semaforo:
            resultado = await enriquecer_place(p, client=cli)
            contador += 1
            if ao_progredir:
                ao_progredir(contador, total)
            return resultado

    if client is not None:
        tarefas = [_processar(p, client) for p in places]
        return await asyncio.gather(*tarefas)

    async with httpx.AsyncClient() as novo_cli:
        tarefas = [_processar(p, novo_cli) for p in places]
        return await asyncio.gather(*tarefas)
