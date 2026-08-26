"""Critério de aceite da Parte 1: retomar sem repetir nenhuma chamada paga."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx
from sqlalchemy.engine import Engine

from mapscout.collect.grid import Celula
from mapscout.collect.jobs import EstadoJob
from mapscout.collect.runner import ResultadoVarredura, varrer
from mapscout.db.repo import contar_api_calls, criar_job, listar_celulas
from mapscout.db.session import abrir_sessao, criar_engine, preparar_banco
from mapscout.sources.places_api import ENDPOINT, Dormir

CATEGORIA = "dentista"
CIDADE = "Campinas"

CELULAS = [
    Celula(-22.9100, -47.0700, -22.9000, -47.0600),
    Celula(-22.9100, -47.0600, -22.9000, -47.0500),
    Celula(-22.9000, -47.0700, -22.8900, -47.0600),
    Celula(-22.9000, -47.0600, -22.8900, -47.0500),
]


def _chave_do_retangulo(request: httpx.Request) -> str:
    """Identifica qual retângulo a requisição pediu, para provar que não repetiu."""
    corpo = json.loads(request.content)
    return json.dumps(corpo["locationRestriction"]["rectangle"], sort_keys=True)


def _mock_contando(
    pagina: dict[str, Any], interromper_na: int | None = None
) -> tuple[Callable[[httpx.Request], httpx.Response], list[str]]:
    """Devolve um responder que registra os retângulos servidos e a lista deles."""
    servidos: list[str] = []

    def responder(request: httpx.Request) -> httpx.Response:
        if interromper_na is not None and len(servidos) + 1 == interromper_na:
            # É exatamente isto que um Ctrl+C produz no Python.
            raise KeyboardInterrupt
        servidos.append(_chave_do_retangulo(request))
        return httpx.Response(200, json=pagina)

    return responder, servidos


def _engine_de_arquivo(tmp_path: Path) -> Engine:
    """Engine em arquivo: cada chamada simula um processo novo sobre o mesmo banco."""
    engine = criar_engine(f"sqlite:///{tmp_path / 'varredura.db'}")
    preparar_banco(engine)
    return engine


async def _rodar(
    engine: Engine,
    responder: Callable[[httpx.Request], httpx.Response],
    dormir: Dormir,
    job_id: int | None,
) -> ResultadoVarredura:
    respx.post(ENDPOINT).mock(side_effect=responder)
    return await varrer(
        categoria=CATEGORIA,
        cidade=CIDADE,
        celulas=CELULAS,
        engine=engine,
        job_id=job_id,
        dormir=dormir,
        rps=100.0,
        teto_dia=1000,
    )


@respx.mock
async def test_retoma_de_onde_parou_sem_repetir_chamada_paga(
    pagina_final: dict[str, Any], tmp_path: Path, dormir_falso: Dormir
) -> None:
    engine = _engine_de_arquivo(tmp_path)
    with abrir_sessao(engine) as sessao:
        job_id = criar_job(sessao, query=f"{CATEGORIA} em {CIDADE}", cidade=CIDADE).id

    # --- Execução 1: morre no meio, ao tentar a terceira célula ---
    responder, servidos_1 = _mock_contando(pagina_final, interromper_na=3)
    primeira = await _rodar(engine, responder, dormir_falso, job_id)

    assert primeira.estado is EstadoJob.CANCELLED
    assert primeira.celulas_visitadas == 2
    with abrir_sessao(engine) as sessao:
        assert len(listar_celulas(sessao, CATEGORIA)) == 2
        assert contar_api_calls(sessao) == 2
    assert len(servidos_1) == 2

    # --- Execução 2: processo novo, mesmo banco, mesmo grid ---
    respx.post(ENDPOINT).mock(side_effect=httpx.ConnectError("mock substituído"))
    engine_2 = criar_engine(f"sqlite:///{tmp_path / 'varredura.db'}")
    responder_2, servidos_2 = _mock_contando(pagina_final)
    segunda = await _rodar(engine_2, responder_2, dormir_falso, job_id)

    # O aceite: nenhuma célula da execução 1 foi requisitada de novo.
    assert set(servidos_1) & set(servidos_2) == set()
    assert len(set(servidos_1) | set(servidos_2)) == 4
    assert segunda.celulas_puladas == 2
    assert segunda.celulas_visitadas == 2
    assert segunda.estado is EstadoJob.COMPLETED

    with abrir_sessao(engine_2) as sessao:
        assert len(listar_celulas(sessao, CATEGORIA)) == 4
        # 4 chamadas no total, não 6: as duas primeiras células não foram repagas.
        assert contar_api_calls(sessao) == 4


@respx.mock
async def test_celula_saturada_e_subdividida_em_quatro(
    pagina_places: dict[str, Any],
    pagina_final: dict[str, Any],
    tmp_path: Path,
    dormir_falso: Dormir,
) -> None:
    engine = _engine_de_arquivo(tmp_path)
    primeiro_retangulo: list[str] = []

    def responder(request: httpx.Request) -> httpx.Response:
        chave = _chave_do_retangulo(request)
        if not primeiro_retangulo:
            primeiro_retangulo.append(chave)
        # So a primeira celula satura: 3 paginas de 20 dao 60 resultados.
        satura = chave == primeiro_retangulo[0]
        return httpx.Response(200, json=pagina_places if satura else pagina_final)

    respx.post(ENDPOINT).mock(side_effect=responder)
    resultado = await varrer(
        categoria=CATEGORIA,
        cidade=CIDADE,
        celulas=[CELULAS[0]],
        engine=engine,
        dormir=dormir_falso,
        rps=100.0,
        teto_dia=1000,
    )

    assert resultado.celulas_subdivididas == 1
    # A mãe mais as 4 filhas.
    assert resultado.celulas_visitadas == 5
    with abrir_sessao(engine) as sessao:
        celulas = listar_celulas(sessao, CATEGORIA)
        assert len(celulas) == 5
        assert sum(1 for c in celulas if c.saturada) == 1
        assert {c.nivel for c in celulas} == {0, 1}


@respx.mock
async def test_para_sozinho_ao_atingir_o_teto_diario(
    pagina_final: dict[str, Any], tmp_path: Path, dormir_falso: Dormir
) -> None:
    engine = _engine_de_arquivo(tmp_path)
    responder, servidos = _mock_contando(pagina_final)
    respx.post(ENDPOINT).mock(side_effect=responder)

    resultado = await varrer(
        categoria=CATEGORIA,
        cidade=CIDADE,
        celulas=CELULAS,
        engine=engine,
        dormir=dormir_falso,
        rps=100.0,
        teto_dia=1,
    )

    assert resultado.estado is EstadoJob.PAUSED_QUOTA
    assert resultado.celulas_visitadas == 1
    assert len(servidos) == 1


@respx.mock
async def test_sigint_cooperativo_para_entre_celulas(
    pagina_final: dict[str, Any], tmp_path: Path, dormir_falso: Dormir
) -> None:
    engine = _engine_de_arquivo(tmp_path)
    responder, _servidos = _mock_contando(pagina_final)
    respx.post(ENDPOINT).mock(side_effect=responder)
    pedidos: list[bool] = []

    def deve_parar() -> bool:
        pedidos.append(True)
        return len(pedidos) > 2

    resultado = await varrer(
        categoria=CATEGORIA,
        cidade=CIDADE,
        celulas=CELULAS,
        engine=engine,
        dormir=dormir_falso,
        deve_parar=deve_parar,
        rps=100.0,
        teto_dia=1000,
    )

    assert resultado.estado is EstadoJob.CANCELLED
    assert resultado.celulas_visitadas == 2
    with abrir_sessao(engine) as sessao:
        # A célula em curso foi gravada antes de sair: nada foi pago sem registro.
        assert len(listar_celulas(sessao, CATEGORIA)) == 2
        assert contar_api_calls(sessao) == 2


def test_job_registra_estado_e_totais(tmp_path: Path) -> None:
    engine = _engine_de_arquivo(tmp_path)

    with abrir_sessao(engine) as sessao:
        job = criar_job(sessao, query="dentista em Campinas", cidade=CIDADE)

        assert job.id is not None
        assert job.estado == EstadoJob.RUNNING
        assert job.iniciado_em is not None
        assert job.concluido_em is None


@pytest.mark.parametrize("categoria", ["dentista", "advogado"])
def test_gridlog_e_por_categoria(tmp_path: Path, categoria: str) -> None:
    """A mesma célula precisa ser varrida de novo para outra categoria."""
    from mapscout.db.repo import celula_ja_executada, registrar_celula

    engine = _engine_de_arquivo(tmp_path)
    with abrir_sessao(engine) as sessao:
        registrar_celula(
            sessao,
            celula_id=CELULAS[0].id,
            categoria="dentista",
            job_id=None,
            qtd_resultados=20,
            saturada=False,
            nivel=0,
        )
        sessao.commit()

        ja_feita = celula_ja_executada(sessao, CELULAS[0].id, categoria)

    assert ja_feita is (categoria == "dentista")
