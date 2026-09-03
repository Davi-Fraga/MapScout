"""Testes do TaskManager e do agendador APScheduler."""

from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy.engine import Engine
from sqlmodel import Session

from mapscout.db.models import Place, agora_utc
from mapscout.db.session import criar_engine, criar_tabelas, preparar_banco
from mapscout.tasks.manager import TaskManager
from mapscout.tasks.scheduler import (
    configurar_tarefas_padrao,
    executar_tarefa_agora,
    listar_tarefas_agendadas,
    obter_agendador,
    parar_agendador,
    rotina_conformidade_google,
)


@pytest.fixture
def engine_teste() -> Engine:
    """Cria banco SQLite em memória para os testes."""
    eng = criar_engine("sqlite:///:memory:")
    criar_tabelas(eng)
    preparar_banco(eng)
    return eng


def test_task_manager_estado_inicial() -> None:
    """Verifica que o TaskManager inicia no estado idle sem tarefas ativas."""
    tm = TaskManager()
    assert tm.esta_ativa() is False
    status = tm.obter_status()
    assert status["status"] == "idle"
    assert status["ativa"] is False
    assert status["porcentagem"] == 0


def test_task_manager_sem_pendentes(engine_teste: Engine) -> None:
    """Testa enriquecimento quando não há nenhum lead pendente."""
    tm = TaskManager()
    iniciou = tm.iniciar_enriquecimento(engine=engine_teste)
    assert iniciou is True
    status = tm.obter_status()
    assert status["status"] == "completed"
    assert "Nenhum lead" in status["mensagem"]


def test_task_manager_cancelamento() -> None:
    """Verifica que cancelar quando não há tarefa retorna False."""
    tm = TaskManager()
    assert tm.cancelar() is False


@pytest.mark.asyncio
async def test_rotina_conformidade_google(engine_teste: Engine) -> None:
    """Testa a renovação da data de checagem para lugares com mais de 60 dias."""
    sessao = Session(engine_teste)
    place_antigo = Place(
        place_id="place_velho",
        display_name="Empresa Antiga",
        checado_em=agora_utc() - timedelta(days=65),
    )
    sessao.add(place_antigo)
    sessao.commit()

    rechecados = await rotina_conformidade_google(engine_teste)
    assert rechecados == 1

    sessao.refresh(place_antigo)
    # Deve ter checado_em atualizado recentemente
    diferenca = agora_utc() - place_antigo.checado_em
    assert diferenca.total_seconds() < 10
    sessao.close()


def test_agendador_tarefas_listagem(engine_teste: Engine) -> None:
    """Verifica que as tarefas padrão são configuradas e listadas com sucesso."""
    agendador = obter_agendador()
    configurar_tarefas_padrao(agendador, engine_teste)
    tarefas = listar_tarefas_agendadas()
    assert len(tarefas) >= 2
    ids = [t["id"] for t in tarefas]
    assert "conformidade_google" in ids
    assert "rechecar_sites_caidos" in ids
    parar_agendador()


@pytest.mark.asyncio
async def test_executar_tarefa_agora_inexistente(engine_teste: Engine) -> None:
    """Testa tentativa de rodar tarefa inexistente."""
    sucesso = await executar_tarefa_agora("tarefa_invalida", engine=engine_teste)
    assert sucesso is False
