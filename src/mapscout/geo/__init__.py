"""Módulo geográfico do MapScout."""

from mapscout.geo.cidades import (
    CIDADES_BRASIL,
    buscar_cidades,
    obter_coordenadas_cidade,
)

__all__ = ["CIDADES_BRASIL", "buscar_cidades", "obter_coordenadas_cidade"]
