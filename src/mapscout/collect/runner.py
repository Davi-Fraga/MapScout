"""Orquestra a varredura do grid: fila, rate limit, freio de custo e retomada."""

from __future__ import annotations

import asyncio
from collections import deque
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

import httpx
from sqlalchemy.engine import Engine

from mapscout.collect.grid import Celula, subdividir
from mapscout.collect.jobs import EstadoJob
from mapscout.config import LIMIAR_SATURACAO, rate_limit_rps, teto_chamadas_dia
from mapscout.db.repo import (
    celula_ja_executada,
    chamadas_hoje,
    marcar_job,
    place_de_resposta,
    registrar_api_call,
    registrar_celula,
    upsert_place,
)
from mapscout.db.session import abrir_sessao
from mapscout.sources.places_api import Dormir, buscar_texto


@dataclass
class ResultadoVarredura:
    """Resumo de uma execução de varredura, para relatório e para os testes."""

    job_id: int | None
    estado: EstadoJob
    celulas_visitadas: int = 0
    celulas_puladas: int = 0
    celulas_subdivididas: int = 0
    total_bruto: int = 0
    novos: int = 0
    chamadas: int = 0
    celulas_saturadas: list[str] = field(default_factory=list)


def _nunca_parar() -> bool:
    """Predicado padrão de interrupção: nunca pede para parar."""
    return False


async def varrer(
    *,
    categoria: str,
    cidade: str,
    celulas: Sequence[Celula],
    engine: Engine,
    job_id: int | None = None,
    dormir: Dormir = asyncio.sleep,
    deve_parar: Callable[[], bool] = _nunca_parar,
    rps: float | None = None,
    teto_dia: int | None = None,
    cliente: httpx.AsyncClient | None = None,
    ao_progredir: Callable[[int, int, ResultadoVarredura], None] | None = None,
) -> ResultadoVarredura:
    """Percorre as células, subdividindo as saturadas e pulando as já executadas."""
    limite_rps = rps if rps is not None else rate_limit_rps()
    teto = teto_dia if teto_dia is not None else teto_chamadas_dia()
    pausa = 1.0 / limite_rps if limite_rps > 0 else 0.0

    resultado = ResultadoVarredura(job_id=job_id, estado=EstadoJob.RUNNING)
    fila: deque[Celula] = deque(celulas)

    while fila:
        if deve_parar():
            resultado.estado = EstadoJob.CANCELLED
            break

        celula = fila.popleft()

        with abrir_sessao(engine) as sessao:
            if celula_ja_executada(sessao, celula.id, categoria):
                resultado.celulas_puladas += 1
                if ao_progredir:
                    ao_progredir(
                        resultado.celulas_visitadas + resultado.celulas_puladas,
                        resultado.celulas_visitadas
                        + resultado.celulas_puladas
                        + len(fila),
                        resultado,
                    )
                continue
            if chamadas_hoje(sessao) >= teto:
                resultado.estado = EstadoJob.PAUSED_QUOTA
                break

        if resultado.celulas_visitadas > 0 and pausa > 0:
            await dormir(pausa)

        try:
            busca = await buscar_texto(
                texto=f"{categoria} em {cidade}",
                retangulo=celula.para_retangulo(),
                cliente=cliente,
                dormir=dormir,
            )
        except KeyboardInterrupt:
            # Nada foi cobrado nem gravado para esta célula: ela volta na retomada.
            resultado.estado = EstadoJob.CANCELLED
            break

        saturada = len(busca.places) >= LIMIAR_SATURACAO

        # Uma transação por célula: ou a célula inteira ficou registrada, ou nada.
        with abrir_sessao(engine) as sessao:
            for resposta in busca.places:
                if upsert_place(sessao, place_de_resposta(resposta, cidade)):
                    resultado.novos += 1
            for chamada in busca.chamadas:
                registrar_api_call(sessao, chamada)
            registrar_celula(
                sessao,
                celula_id=celula.id,
                categoria=categoria,
                job_id=job_id,
                qtd_resultados=len(busca.places),
                saturada=saturada,
                nivel=celula.nivel,
            )
            sessao.commit()

        resultado.celulas_visitadas += 1
        resultado.total_bruto += len(busca.places)
        resultado.chamadas += len(busca.chamadas)

        if saturada:
            filhas = subdividir(celula)
            if filhas:
                resultado.celulas_subdivididas += 1
                resultado.celulas_saturadas.append(celula.id)
                fila.extend(filhas)

        if ao_progredir:
            ao_progredir(
                resultado.celulas_visitadas + resultado.celulas_puladas,
                resultado.celulas_visitadas + resultado.celulas_puladas + len(fila),
                resultado,
            )

    if resultado.estado is EstadoJob.RUNNING:
        resultado.estado = EstadoJob.COMPLETED

    if job_id is not None:
        with abrir_sessao(engine) as sessao:
            marcar_job(
                sessao,
                job_id,
                resultado.estado,
                total_encontrado=resultado.total_bruto,
                total_processado=resultado.celulas_visitadas,
            )
            sessao.commit()

    return resultado
