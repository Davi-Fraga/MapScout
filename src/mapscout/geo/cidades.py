"""Base de cidades brasileiras com geolocalização e busca inteligente."""

from __future__ import annotations

import math
import unicodedata
from typing import Any


def normalizar_texto(texto: str) -> str:
    """Remove acentos e converte para minúsculas para busca flexível."""
    nfkd = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower().strip()


CIDADES_BRASIL: list[dict[str, Any]] = [
    # Capitais
    {"nome": "São Paulo", "uf": "SP", "lat": -23.5505, "lng": -46.6333},
    {"nome": "Rio de Janeiro", "uf": "RJ", "lat": -22.9068, "lng": -43.1729},
    {"nome": "Brasília", "uf": "DF", "lat": -15.7942, "lng": -47.8822},
    {"nome": "Belo Horizonte", "uf": "MG", "lat": -19.9167, "lng": -43.9345},
    {"nome": "Salvador", "uf": "BA", "lat": -12.9777, "lng": -38.5016},
    {"nome": "Fortaleza", "uf": "CE", "lat": -3.7319, "lng": -38.5267},
    {"nome": "Curitiba", "uf": "PR", "lat": -25.4284, "lng": -49.2733},
    {"nome": "Recife", "uf": "PE", "lat": -8.0578, "lng": -34.8778},
    {"nome": "Porto Alegre", "uf": "RS", "lat": -30.0346, "lng": -51.2177},
    {"nome": "Manaus", "uf": "AM", "lat": -3.1190, "lng": -60.0217},
    {"nome": "Belém", "uf": "PA", "lat": -1.4558, "lng": -48.4902},
    {"nome": "Goiânia", "uf": "GO", "lat": -16.6869, "lng": -49.2648},
    {"nome": "Guarulhos", "uf": "SP", "lat": -23.4542, "lng": -46.5333},
    {"nome": "Campinas", "uf": "SP", "lat": -22.9056, "lng": -47.0608},
    {"nome": "São Luís", "uf": "MA", "lat": -2.5307, "lng": -44.3068},
    {"nome": "São Gonçalo", "uf": "RJ", "lat": -22.8268, "lng": -43.0537},
    {"nome": "Maceió", "uf": "AL", "lat": -9.6658, "lng": -35.7350},
    {"nome": "Campo Grande", "uf": "MS", "lat": -20.4697, "lng": -54.6201},
    {"nome": "Natal", "uf": "RN", "lat": -5.7945, "lng": -35.2110},
    {"nome": "Teresina", "uf": "PI", "lat": -5.0920, "lng": -42.8038},
    {"nome": "São Bernardo do Campo", "uf": "SP", "lat": -23.6914, "lng": -46.5647},
    {"nome": "João Pessoa", "uf": "PB", "lat": -7.1195, "lng": -34.8450},
    {"nome": "Santo André", "uf": "SP", "lat": -23.6639, "lng": -46.5383},
    {"nome": "Osasco", "uf": "SP", "lat": -23.5325, "lng": -46.7917},
    {"nome": "São José dos Campos", "uf": "SP", "lat": -23.1896, "lng": -45.8841},
    {"nome": "Ribeirão Preto", "uf": "SP", "lat": -21.1767, "lng": -47.8108},
    {"nome": "Uberlândia", "uf": "MG", "lat": -18.9186, "lng": -48.2772},
    {"nome": "Sorocaba", "uf": "SP", "lat": -23.5017, "lng": -47.4581},
    {"nome": "Contagem", "uf": "MG", "lat": -19.9317, "lng": -44.0536},
    {"nome": "Aracaju", "uf": "SE", "lat": -10.9472, "lng": -37.0731},
    {"nome": "Feira de Santana", "uf": "BA", "lat": -12.2667, "lng": -38.9667},
    {"nome": "Cuiabá", "uf": "MT", "lat": -15.6014, "lng": -56.0979},
    {"nome": "Joinville", "uf": "SC", "lat": -26.3045, "lng": -48.8487},
    {"nome": "Juiz de Fora", "uf": "MG", "lat": -21.7642, "lng": -43.3497},
    {"nome": "Londrina", "uf": "PR", "lat": -23.3045, "lng": -51.1696},
    {"nome": "Niterói", "uf": "RJ", "lat": -22.8833, "lng": -43.1036},
    {"nome": "Ananindeua", "uf": "PA", "lat": -1.3656, "lng": -48.3722},
    {"nome": "Belford Roxo", "uf": "RJ", "lat": -22.7642, "lng": -43.3997},
    {"nome": "Caxias do Sul", "uf": "RS", "lat": -29.1678, "lng": -51.1794},
    {"nome": "Campos dos Goytacazes", "uf": "RJ", "lat": -21.7544, "lng": -41.3244},
    {"nome": "Santos", "uf": "SP", "lat": -23.9608, "lng": -46.3336},
    {"nome": "Florianópolis", "uf": "SC", "lat": -27.5954, "lng": -48.5480},
    {"nome": "Vila Velha", "uf": "ES", "lat": -20.3297, "lng": -40.2925},
    {"nome": "Serra", "uf": "ES", "lat": -20.1286, "lng": -40.3078},
    {"nome": "Diadema", "uf": "SP", "lat": -23.6865, "lng": -46.6228},
    {"nome": "Mauá", "uf": "SP", "lat": -23.6678, "lng": -46.4614},
    {"nome": "São José do Rio Preto", "uf": "SP", "lat": -20.8113, "lng": -49.3758},
    {"nome": "Mogi das Cruzes", "uf": "SP", "lat": -23.5206, "lng": -46.1853},
    {"nome": "Betim", "uf": "MG", "lat": -19.9678, "lng": -44.1983},
    {"nome": "Jundiaí", "uf": "SP", "lat": -23.1857, "lng": -46.8978},
    {"nome": "Piracicaba", "uf": "SP", "lat": -22.7339, "lng": -47.6478},
    {"nome": "Montes Claros", "uf": "MG", "lat": -16.7350, "lng": -43.8617},
    {"nome": "Maringá", "uf": "PR", "lat": -23.4210, "lng": -51.9331},
    {"nome": "Anápolis", "uf": "GO", "lat": -16.3267, "lng": -48.9533},
    {"nome": "Bauru", "uf": "SP", "lat": -22.3147, "lng": -49.0606},
    {"nome": "Pelotas", "uf": "RS", "lat": -31.7654, "lng": -52.3376},
    {"nome": "Vitória", "uf": "ES", "lat": -20.3155, "lng": -40.3128},
    {"nome": "Franca", "uf": "SP", "lat": -20.5386, "lng": -47.4008},
    {"nome": "Ponta Grossa", "uf": "PR", "lat": -25.0950, "lng": -50.1619},
    {"nome": "Blumenau", "uf": "SC", "lat": -26.9194, "lng": -49.0661},
    {"nome": "Petrolina", "uf": "PE", "lat": -9.3989, "lng": -40.5008},
    {"nome": "Paulista", "uf": "PE", "lat": -7.9408, "lng": -34.8731},
    {"nome": "Canoas", "uf": "RS", "lat": -29.9178, "lng": -51.1836},
    {"nome": "Cascavel", "uf": "PR", "lat": -24.9578, "lng": -53.4594},
    {"nome": "São Vicente", "uf": "SP", "lat": -23.9631, "lng": -46.3919},
    {"nome": "Praia Grande", "uf": "SP", "lat": -24.0058, "lng": -46.4028},
    {"nome": "Taubaté", "uf": "SP", "lat": -23.0264, "lng": -45.5553},
    {"nome": "Limeira", "uf": "SP", "lat": -22.5647, "lng": -47.4017},
    {"nome": "Suzano", "uf": "SP", "lat": -23.5425, "lng": -46.3108},
    {"nome": "Petrópolis", "uf": "RJ", "lat": -22.5050, "lng": -43.1789},
    {"nome": "Uberaba", "uf": "MG", "lat": -19.7483, "lng": -47.9319},
    {"nome": "Santarém", "uf": "PA", "lat": -2.4431, "lng": -54.7083},
    {"nome": "Volta Redonda", "uf": "RJ", "lat": -22.5231, "lng": -44.1042},
    {"nome": "Novo Hamburgo", "uf": "RS", "lat": -29.6783, "lng": -51.1308},
    {"nome": "Santa Maria", "uf": "RS", "lat": -29.6842, "lng": -53.8069},
    {"nome": "Gravataí", "uf": "RS", "lat": -29.9439, "lng": -50.9928},
    {"nome": "Governador Valadares", "uf": "MG", "lat": -18.8511, "lng": -41.9494},
    {"nome": "Barueri", "uf": "SP", "lat": -23.5111, "lng": -46.8761},
    {"nome": "Palmas", "uf": "TO", "lat": -10.1844, "lng": -48.3336},
    {"nome": "Boa Vista", "uf": "RR", "lat": 2.8235, "lng": -60.6758},
    {"nome": "Rio Branco", "uf": "AC", "lat": -9.9753, "lng": -67.8249},
    {"nome": "Macapá", "uf": "AP", "lat": 0.0349, "lng": -51.0694},
    {"nome": "Porto Velho", "uf": "RO", "lat": -8.7619, "lng": -63.9039},
    {"nome": "Indaiatuba", "uf": "SP", "lat": -23.0903, "lng": -47.2181},
    {"nome": "Americana", "uf": "SP", "lat": -22.7375, "lng": -47.3331},
    {"nome": "Araraquara", "uf": "SP", "lat": -21.7944, "lng": -48.1758},
    {"nome": "São Carlos", "uf": "SP", "lat": -22.0175, "lng": -47.8908},
    {"nome": "Hortolândia", "uf": "SP", "lat": -22.8583, "lng": -47.2200},
    {"nome": "Presidente Prudente", "uf": "SP", "lat": -22.1256, "lng": -51.3889},
    {"nome": "Rio Claro", "uf": "SP", "lat": -22.4114, "lng": -47.5614},
    {"nome": "Marília", "uf": "SP", "lat": -22.2139, "lng": -49.9458},
    {"nome": "Criciúma", "uf": "SC", "lat": -28.6775, "lng": -49.3697},
    {"nome": "Chapecó", "uf": "SC", "lat": -27.1006, "lng": -52.6153},
    {"nome": "Itajaí", "uf": "SC", "lat": -26.9078, "lng": -48.6619},
    {"nome": "Balneário Camboriú", "uf": "SC", "lat": -26.9931, "lng": -48.6347},
    {"nome": "Foz do Iguaçu", "uf": "PR", "lat": -25.5478, "lng": -54.5881},
]


def buscar_cidades(termo: str, limite: int = 8) -> list[dict[str, Any]]:
    """Busca cidades pelo nome com correspondência flexível."""
    if not termo or not termo.strip():
        return CIDADES_BRASIL[:limite]

    termo_norm = normalizar_texto(termo)
    resultados: list[dict[str, Any]] = []

    for c in CIDADES_BRASIL:
        nome_norm = normalizar_texto(c["nome"])
        uf_norm = normalizar_texto(c["uf"])
        rotulo_norm = f"{nome_norm} {uf_norm}"
        if termo_norm in rotulo_norm or termo_norm in nome_norm:
            resultados.append(c)
            if len(resultados) >= limite:
                break

    return resultados


def obter_coordenadas_cidade(cidade: str) -> tuple[float, float] | None:
    """Devolve a latitude e longitude da cidade se conhecida."""
    if not cidade:
        return None
    cidade_norm = normalizar_texto(cidade)
    # Tenta match exato primeiro
    for c in CIDADES_BRASIL:
        if normalizar_texto(c["nome"]) == cidade_norm:
            return float(c["lat"]), float(c["lng"])
        if normalizar_texto(f"{c['nome']}/{c['uf']}") == cidade_norm:
            return float(c["lat"]), float(c["lng"])
        if normalizar_texto(f"{c['nome']} {c['uf']}") == cidade_norm:
            return float(c["lat"]), float(c["lng"])

    # Tenta correspondência parcial
    for c in CIDADES_BRASIL:
        if cidade_norm in normalizar_texto(c["nome"]):
            return float(c["lat"]), float(c["lng"])

    return None


def calcular_deslocamento_coordenadas(
    lat: float, lng: float, direcao: str, distancia_km: float
) -> tuple[float, float]:
    """Calcula novo par lat/lng deslocando um centro geográfico em km."""
    delta_lat = distancia_km / 111.0
    lat_rad = math.radians(lat)
    fator_lng = math.cos(lat_rad)
    delta_lng = distancia_km / (111.0 * fator_lng if abs(fator_lng) > 1e-6 else 111.0)

    dir_norm = direcao.lower().strip()
    if dir_norm == "norte":
        return round(lat + delta_lat, 6), round(lng, 6)
    if dir_norm == "sul":
        return round(lat - delta_lat, 6), round(lng, 6)
    if dir_norm == "leste":
        return round(lat, 6), round(lng + delta_lng, 6)
    if dir_norm == "oeste":
        return round(lat, 6), round(lng - delta_lng, 6)
    if dir_norm == "nordeste":
        return round(lat + delta_lat * 0.707, 6), round(lng + delta_lng * 0.707, 6)
    if dir_norm == "noroeste":
        return round(lat + delta_lat * 0.707, 6), round(lng - delta_lng * 0.707, 6)
    if dir_norm == "sudeste":
        return round(lat - delta_lat * 0.707, 6), round(lng + delta_lng * 0.707, 6)
    if dir_norm == "sudoeste":
        return round(lat - delta_lat * 0.707, 6), round(lng - delta_lng * 0.707, 6)

    return lat, lng
