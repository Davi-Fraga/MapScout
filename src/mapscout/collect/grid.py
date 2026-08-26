"""Grid geográfico adaptativo em células quadradas."""

from __future__ import annotations

import math
from dataclasses import dataclass

from mapscout.config import RAIO_MINIMO_M
from mapscout.sources.places_api import METROS_POR_GRAU_LAT, Retangulo


def _metros_por_grau_lng(latitude: float) -> float:
    """Metros correspondentes a um grau de longitude na latitude informada."""
    cos_lat = max(math.cos(math.radians(latitude)), 1e-6)
    return METROS_POR_GRAU_LAT * cos_lat


def distancia_m(lat_a: float, lng_a: float, lat_b: float, lng_b: float) -> float:
    """Distância aproximada em metros entre dois pontos próximos (equirretangular)."""
    dy = (lat_a - lat_b) * METROS_POR_GRAU_LAT
    dx = (lng_a - lng_b) * _metros_por_grau_lng((lat_a + lat_b) / 2)
    return math.hypot(dx, dy)


@dataclass(frozen=True)
class Celula:
    """Uma célula quadrada do grid, consultada como rectangle na Places API."""

    lat_min: float
    lng_min: float
    lat_max: float
    lng_max: float
    nivel: int = 0

    @property
    def centro(self) -> tuple[float, float]:
        """Latitude e longitude do centro da célula."""
        return ((self.lat_min + self.lat_max) / 2, (self.lng_min + self.lng_max) / 2)

    @property
    def lado_m(self) -> float:
        """Lado da célula em metros, medido pela extensão em latitude."""
        return (self.lat_max - self.lat_min) * METROS_POR_GRAU_LAT

    @property
    def raio_m(self) -> float:
        """Metade da diagonal do quadrado — o raio que circunscreve a célula."""
        return self.lado_m * math.sqrt(2) / 2

    @property
    def id(self) -> str:
        """Identificador determinístico, estável entre execuções; PK do GridLog."""
        return (
            f"{self.lat_min:.6f}:{self.lng_min:.6f}:"
            f"{self.lat_max:.6f}:{self.lng_max:.6f}"
        )

    def para_retangulo(self) -> Retangulo:
        """Converte a célula no rectangle low/high aceito por locationRestriction."""
        return Retangulo(
            lat_min=self.lat_min,
            lng_min=self.lng_min,
            lat_max=self.lat_max,
            lng_max=self.lng_max,
        )


def gerar_grid(lat: float, lng: float, raio_km: float, passo_m: float) -> list[Celula]:
    """Gera as células quadradas de passo_m cujo centro cai no círculo pedido."""
    raio_m = raio_km * 1000.0
    delta_lat = passo_m / METROS_POR_GRAU_LAT
    delta_lng = passo_m / _metros_por_grau_lng(lat)
    passos = math.ceil(raio_m / passo_m)

    celulas: list[Celula] = []
    for i in range(-passos, passos):
        for j in range(-passos, passos):
            celula = Celula(
                lat_min=lat + i * delta_lat,
                lng_min=lng + j * delta_lng,
                lat_max=lat + (i + 1) * delta_lat,
                lng_max=lng + (j + 1) * delta_lng,
            )
            centro_lat, centro_lng = celula.centro
            if distancia_m(centro_lat, centro_lng, lat, lng) <= raio_m:
                celulas.append(celula)
    return celulas


def subdividir(celula: Celula) -> list[Celula]:
    """Divide a célula em 4 filhas, ou devolve lista vazia se atingir o piso de raio."""
    if celula.raio_m / 2 < RAIO_MINIMO_M:
        return []

    lat_meio = (celula.lat_min + celula.lat_max) / 2
    lng_meio = (celula.lng_min + celula.lng_max) / 2
    nivel = celula.nivel + 1
    return [
        Celula(celula.lat_min, celula.lng_min, lat_meio, lng_meio, nivel),
        Celula(celula.lat_min, lng_meio, lat_meio, celula.lng_max, nivel),
        Celula(lat_meio, celula.lng_min, celula.lat_max, lng_meio, nivel),
        Celula(lat_meio, lng_meio, celula.lat_max, celula.lng_max, nivel),
    ]
