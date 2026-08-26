"""Configuração lida de variáveis de ambiente, com padrões conservadores."""

from __future__ import annotations

import os

RATE_LIMIT_RPS_PADRAO = 2.0
TETO_CHAMADAS_DIA_PADRAO = 500
PASSO_PADRAO_M = 1200.0
RAIO_MINIMO_M = 300.0
LIMIAR_SATURACAO = 55


def _float_do_ambiente(nome: str, padrao: float) -> float:
    """Lê um float de variável de ambiente, caindo no padrão se ausente ou inválido."""
    bruto = os.environ.get(nome)
    if not bruto:
        return padrao
    try:
        return float(bruto)
    except ValueError:
        return padrao


def _int_do_ambiente(nome: str, padrao: int) -> int:
    """Lê um int de variável de ambiente, caindo no padrão se ausente ou inválido."""
    bruto = os.environ.get(nome)
    if not bruto:
        return padrao
    try:
        return int(bruto)
    except ValueError:
        return padrao


def rate_limit_rps() -> float:
    """Requisições por segundo permitidas ao varrer o grid."""
    return _float_do_ambiente("MAPSCOUT_RATE_LIMIT_RPS", RATE_LIMIT_RPS_PADRAO)


def teto_chamadas_dia() -> int:
    """Teto diário de chamadas à Places API — o freio de custo exigido pela regra 6."""
    return _int_do_ambiente("MAPSCOUT_TETO_CHAMADAS_DIA", TETO_CHAMADAS_DIA_PADRAO)
