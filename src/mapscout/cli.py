"""Interface de linha de comando do MapScout."""

from __future__ import annotations

import argparse
import asyncio
from collections.abc import Sequence

from mapscout.db.repo import (
    contar_api_calls,
    contar_places,
    place_de_resposta,
    registrar_api_call,
    upsert_place,
)
from mapscout.db.session import abrir_sessao, criar_engine, criar_tabelas
from mapscout.sources.places_api import ResultadoBusca, buscar_texto, retangulo_do_raio


def montar_parser() -> argparse.ArgumentParser:
    """Monta o parser de argumentos da CLI."""
    parser = argparse.ArgumentParser(prog="mapscout", description="Prospecção B2B.")
    subcomandos = parser.add_subparsers(dest="comando", required=True)

    coletar = subcomandos.add_parser("coletar", help="Coleta empresas na Places API.")
    coletar.add_argument("--categoria", required=True, help="Ex.: dentista")
    coletar.add_argument("--lat", required=True, type=float, help="Latitude do centro")
    coletar.add_argument("--lng", required=True, type=float, help="Longitude do centro")
    coletar.add_argument("--raio-m", required=True, type=int, help="Raio em metros")
    coletar.add_argument("--cidade", required=True, help="Ex.: Campinas")
    return parser


def executar_coleta(
    *, categoria: str, lat: float, lng: float, raio_m: int, cidade: str
) -> ResultadoBusca:
    """Busca na Places API e persiste lugares e chamadas, devolvendo o resultado."""
    resultado = asyncio.run(
        buscar_texto(
            texto=f"{categoria} em {cidade}",
            retangulo=retangulo_do_raio(lat, lng, raio_m),
        )
    )

    engine = criar_engine()
    criar_tabelas(engine)
    novos = 0
    with abrir_sessao(engine) as sessao:
        for resposta in resultado.places:
            if upsert_place(sessao, place_de_resposta(resposta)):
                novos += 1
        for chamada in resultado.chamadas:
            registrar_api_call(sessao, chamada)
        sessao.commit()
        total = contar_places(sessao)
        chamadas = contar_api_calls(sessao)

    print(
        f"coletados {len(resultado.places)} lugares "
        f"({novos} novos, {len(resultado.places) - novos} atualizados) "
        f"em {len(resultado.chamadas)} chamada(s) HTTP"
    )
    print(f"banco: {total} places, {chamadas} linhas em api_calls")
    return resultado


def main(argv: Sequence[str] | None = None) -> int:
    """Ponto de entrada da CLI."""
    args = montar_parser().parse_args(argv)
    if args.comando == "coletar":
        executar_coleta(
            categoria=args.categoria,
            lat=args.lat,
            lng=args.lng,
            raio_m=args.raio_m,
            cidade=args.cidade,
        )
    return 0
