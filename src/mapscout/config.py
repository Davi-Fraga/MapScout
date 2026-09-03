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


TICKETS_CATEGORIA: dict[str, float] = {
    "dentista": 1.25,
    "odonto": 1.25,
    "medico": 1.30,
    "clinica": 1.30,
    "advogado": 1.30,
    "advocacia": 1.30,
    "engenharia": 1.25,
    "arquiteto": 1.25,
    "arquitetura": 1.25,
    "contabilidade": 1.20,
    "imobiliaria": 1.20,
    "estetica": 1.15,
    "salao": 1.05,
    "restaurante": 1.00,
    "pizzaria": 1.00,
    "oficina": 1.05,
}


def multiplicador_ticket(categoria: str | None) -> float:
    """Devolve o peso estimado de ticket médio para a categoria da empresa."""
    if not categoria:
        return 1.0
    cat_lower = categoria.lower().strip()
    for chave, valor in TICKETS_CATEGORIA.items():
        if chave in cat_lower:
            return valor
    return 1.0
