"""Testes do grid adaptativo."""

from __future__ import annotations

import math

import pytest

from mapscout.collect.grid import Celula, distancia_m, gerar_grid, subdividir
from mapscout.config import RAIO_MINIMO_M
from mapscout.sources.places_api import METROS_POR_GRAU_LAT

CENTRO_LAT = -22.9099
CENTRO_LNG = -47.0626


def _celula_de(passo_m: float, nivel: int = 0) -> Celula:
    """Uma célula quadrada de lado passo_m ancorada no centro de referência."""
    delta_lat = passo_m / METROS_POR_GRAU_LAT
    delta_lng = passo_m / (METROS_POR_GRAU_LAT * math.cos(math.radians(CENTRO_LAT)))
    return Celula(
        lat_min=CENTRO_LAT,
        lng_min=CENTRO_LNG,
        lat_max=CENTRO_LAT + delta_lat,
        lng_max=CENTRO_LNG + delta_lng,
        nivel=nivel,
    )


def test_todas_as_celulas_tem_o_centro_dentro_do_circulo() -> None:
    grid = gerar_grid(CENTRO_LAT, CENTRO_LNG, raio_km=2.0, passo_m=1000.0)

    assert len(grid) > 4
    for celula in grid:
        lat, lng = celula.centro
        assert distancia_m(lat, lng, CENTRO_LAT, CENTRO_LNG) <= 2000.0


def test_lado_da_celula_corresponde_ao_passo_pedido() -> None:
    celula = _celula_de(1000.0)

    assert celula.lado_m == pytest.approx(1000.0, rel=1e-6)


def test_raio_e_metade_da_diagonal_do_quadrado() -> None:
    celula = _celula_de(1000.0)

    assert celula.raio_m == pytest.approx(1000.0 * math.sqrt(2) / 2, rel=1e-6)


def test_celulas_vizinhas_ladrilham_sem_buraco() -> None:
    grid = gerar_grid(CENTRO_LAT, CENTRO_LNG, raio_km=2.0, passo_m=1000.0)
    por_canto = {(round(c.lat_min, 6), round(c.lng_min, 6)): c for c in grid}

    vizinhas = 0
    for celula in grid:
        acima = por_canto.get((round(celula.lat_max, 6), round(celula.lng_min, 6)))
        if acima is not None:
            # O topo de uma é exatamente a base da outra: sem buraco e sem sobreposição.
            assert acima.lat_min == pytest.approx(celula.lat_max)
            vizinhas += 1
    assert vizinhas > 0


def test_id_e_deterministico_entre_execucoes() -> None:
    primeiro = gerar_grid(CENTRO_LAT, CENTRO_LNG, raio_km=1.0, passo_m=800.0)
    segundo = gerar_grid(CENTRO_LAT, CENTRO_LNG, raio_km=1.0, passo_m=800.0)

    assert [c.id for c in primeiro] == [c.id for c in segundo]
    assert len({c.id for c in primeiro}) == len(primeiro)


def test_retangulo_usa_low_sudoeste_e_high_nordeste() -> None:
    celula = _celula_de(1000.0)
    retangulo = celula.para_retangulo()

    assert retangulo.lat_min < retangulo.lat_max
    assert retangulo.lng_min < retangulo.lng_max
    assert retangulo.para_json()["low"]["latitude"] == celula.lat_min
    assert retangulo.para_json()["high"]["latitude"] == celula.lat_max


def test_subdividir_gera_quatro_filhas_que_cobrem_a_mae() -> None:
    mae = _celula_de(2000.0)

    filhas = subdividir(mae)

    assert len(filhas) == 4
    assert all(f.nivel == mae.nivel + 1 for f in filhas)
    assert all(f.lado_m == pytest.approx(mae.lado_m / 2) for f in filhas)
    assert min(f.lat_min for f in filhas) == pytest.approx(mae.lat_min)
    assert max(f.lat_max for f in filhas) == pytest.approx(mae.lat_max)
    assert min(f.lng_min for f in filhas) == pytest.approx(mae.lng_min)
    assert max(f.lng_max for f in filhas) == pytest.approx(mae.lng_max)


def test_subdividir_respeita_o_piso_de_300m() -> None:
    # Filha teria raio abaixo de 300 m, então a subdivisão para.
    lado_minimo = RAIO_MINIMO_M * 2 * math.sqrt(2) * 0.99
    mae = _celula_de(lado_minimo)

    assert mae.raio_m / 2 < RAIO_MINIMO_M
    assert subdividir(mae) == []
