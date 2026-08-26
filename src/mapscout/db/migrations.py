"""Migração mínima: adiciona colunas novas a tabelas que já existem."""

from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
from sqlmodel import SQLModel


def garantir_colunas(engine: Engine) -> list[str]:
    """Adiciona por ALTER TABLE as colunas do modelo que faltam no banco existente."""
    inspetor = inspect(engine)
    adicionadas: list[str] = []

    for nome_tabela, tabela in SQLModel.metadata.tables.items():
        if not inspetor.has_table(nome_tabela):
            continue
        existentes = {coluna["name"] for coluna in inspetor.get_columns(nome_tabela)}
        for coluna in tabela.columns:
            if coluna.name in existentes:
                continue
            tipo = coluna.type.compile(engine.dialect)
            comando = f"ALTER TABLE {nome_tabela} ADD COLUMN {coluna.name} {tipo}"
            with engine.begin() as conexao:
                conexao.execute(text(comando))
            adicionadas.append(f"{nome_tabela}.{coluna.name}")

    return adicionadas
