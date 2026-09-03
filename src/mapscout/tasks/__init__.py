"""Módulo de tarefas em segundo plano e agendamento do MapScout."""

from mapscout.tasks.manager import TaskManager, gerenciador_tarefas
from mapscout.tasks.scheduler import (
    iniciar_agendador,
    listar_tarefas_agendadas,
    obter_agendador,
    parar_agendador,
)

__all__ = [
    "TaskManager",
    "gerenciador_tarefas",
    "iniciar_agendador",
    "listar_tarefas_agendadas",
    "obter_agendador",
    "parar_agendador",
]
