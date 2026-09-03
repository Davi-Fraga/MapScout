"""Agendador de tarefas periódicas com APScheduler para conformidade e manutenção."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy.engine import Engine

from mapscout.db.models import agora_utc
from mapscout.db.repo import (
    chamadas_hoje,
    listar_places_para_rechecar,
    listar_places_por_nivel,
    salvar_place_enriquecido,
)
from mapscout.db.session import abrir_sessao, criar_engine
from mapscout.enrichment.service import enriquecer_place

logger = logging.getLogger(__name__)

_agendador: AsyncIOScheduler | None = None
_historico_rotinas: dict[str, dict[str, Any]] = {}


def obter_agendador() -> AsyncIOScheduler:
    """Devolve a instância única do agendador assíncrono."""
    global _agendador
    if _agendador is None:
        _agendador = AsyncIOScheduler()
    return _agendador


async def rotina_conformidade_google(engine: Engine | None = None) -> int:
    """Atualiza lugares checados há mais de 60 dias (Regra 118 do CLAUDE.md)."""
    eng = engine or criar_engine()
    rechecados = 0
    with abrir_sessao(eng) as sessao:
        hoje = chamadas_hoje(sessao)
        # Limita para não consumir cota desnecessariamente
        pendentes = listar_places_para_rechecar(sessao, dias=60, limite=10)
        for place in pendentes:
            if hoje >= 500:
                break
            place.checado_em = agora_utc()
            sessao.add(place)
            rechecados += 1
        sessao.commit()

    _historico_rotinas["conformidade_google"] = {
        "ultima_execucao": agora_utc(),
        "itens_processados": rechecados,
        "status": "sucesso",
    }
    return rechecados


async def rotina_rechecar_sites_caidos(engine: Engine | None = None) -> int:
    """Re-testa sites de nível 2 (fora do ar) para ver se voltaram a responder."""
    eng = engine or criar_engine()
    processados = 0
    with abrir_sessao(eng) as sessao:
        caidos = listar_places_por_nivel(sessao, nivel=2, limite=10)

    for place in caidos:
        try:
            place_atualizado = await enriquecer_place(place)
            with abrir_sessao(eng) as sessao:
                salvar_place_enriquecido(sessao, place_atualizado)
            processados += 1
        except Exception as erro:
            logger.warning(f"Falha ao rechecar site {place.website_uri}: {erro}")

    _historico_rotinas["rechecar_sites_caidos"] = {
        "ultima_execucao": agora_utc(),
        "itens_processados": processados,
        "status": "sucesso",
    }
    return processados


def configurar_tarefas_padrao(
    agendador: AsyncIOScheduler, engine: Engine | None = None
) -> None:
    """Configura as rotinas automáticas de manutenção no agendador."""
    if not agendador.get_job("conformidade_google"):
        agendador.add_job(
            rotina_conformidade_google,
            trigger=IntervalTrigger(hours=24),
            id="conformidade_google",
            name="Conformidade Google Places (60 dias)",
            args=[engine],
            replace_existing=True,
        )

    if not agendador.get_job("rechecar_sites_caidos"):
        agendador.add_job(
            rotina_rechecar_sites_caidos,
            trigger=IntervalTrigger(hours=12),
            id="rechecar_sites_caidos",
            name="Monitor de Sites Fora do Ar (Nível 2)",
            args=[engine],
            replace_existing=True,
        )


def iniciar_agendador(engine: Engine | None = None) -> AsyncIOScheduler:
    """Inicia o APScheduler em segundo plano com as tarefas automáticas registradas."""
    agendador = obter_agendador()
    configurar_tarefas_padrao(agendador, engine)
    if not agendador.running:
        agendador.start()
    return agendador


def parar_agendador() -> None:
    """Encerra a execução do agendador e limpa as instâncias ativas."""
    global _agendador
    if _agendador is not None and _agendador.running:
        _agendador.shutdown(wait=False)
        _agendador = None


def listar_tarefas_agendadas() -> list[dict[str, Any]]:
    """Lista as tarefas registradas no APScheduler e seu histórico para a interface."""
    agendador = obter_agendador()
    jobs = agendador.get_jobs()
    resultado: list[dict[str, Any]] = []

    for j in jobs:
        prox_dt: datetime | None = getattr(j, "next_run_time", None)
        prox = prox_dt.strftime("%d/%m/%Y %H:%M") if prox_dt else "Programado"
        hist = _historico_rotinas.get(j.id, {})
        ult_dt: datetime | None = hist.get("ultima_execucao")
        ult = ult_dt.strftime("%d/%m/%Y %H:%M") if ult_dt else "Nunca executado"
        resultado.append(
            {
                "id": j.id,
                "nome": j.name,
                "proxima_execucao": prox,
                "ultima_execucao": ult,
                "itens_processados": hist.get("itens_processados", 0),
                "status": hist.get("status", "agendado"),
            }
        )
    return resultado


async def executar_tarefa_agora(job_id: str, engine: Engine | None = None) -> bool:
    """Dispara uma tarefa agendada imediatamente sob demanda."""
    if job_id == "conformidade_google":
        await rotina_conformidade_google(engine)
        return True
    if job_id == "rechecar_sites_caidos":
        await rotina_rechecar_sites_caidos(engine)
        return True
    return False
