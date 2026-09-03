"""Interface de linha de comando do MapScout."""

from __future__ import annotations

import argparse
import asyncio
import signal
import sys
import threading
from collections.abc import Sequence
from types import FrameType

import httpx

from mapscout.collect.grid import gerar_grid
from mapscout.collect.jobs import EstadoJob
from mapscout.collect.runner import ResultadoVarredura, varrer
from mapscout.config import PASSO_PADRAO_M, teto_chamadas_dia
from mapscout.db.repo import (
    contar_api_calls,
    contar_places,
    criar_job,
    listar_celulas,
    listar_places_para_enriquecer,
    listar_todos_places,
    place_de_resposta,
    registrar_api_call,
    salvar_place_enriquecido,
    upsert_place,
)
from mapscout.db.session import (
    abrir_sessao,
    criar_engine,
    criar_tabelas,
    preparar_banco,
)
from mapscout.dedupe.lote import ResultadoDedupe, deduplicar
from mapscout.enrichment.service import enriquecer_lote
from mapscout.export import exportar_leads_qualificados
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

    varredura = subcomandos.add_parser(
        "varrer", help="Varre um raio inteiro com grid adaptativo."
    )
    varredura.add_argument("--categoria", required=True, help="Ex.: dentista")
    varredura.add_argument("--lat", required=True, type=float, help="Latitude central")
    varredura.add_argument("--lng", required=True, type=float, help="Longitude central")
    varredura.add_argument(
        "--raio-km", required=True, type=float, help="Raio da varredura em km"
    )
    varredura.add_argument(
        "--passo-m",
        type=float,
        default=PASSO_PADRAO_M,
        help=f"Lado da célula em metros (padrão {PASSO_PADRAO_M:.0f})",
    )
    varredura.add_argument("--cidade", required=True, help="Ex.: Campinas")

    relatorio = subcomandos.add_parser(
        "relatorio", help="Resumo da varredura e do dedupe sobre a base."
    )
    relatorio.add_argument("--categoria", help="Filtra as células por categoria")
    relatorio.add_argument(
        "--exemplos", type=int, default=5, help="Quantas fusões listar (padrão 5)"
    )

    enriquecer = subcomandos.add_parser(
        "enriquecer", help="Diagnostica a presença digital e enriquece os sites."
    )
    enriquecer.add_argument(
        "--limite", type=int, default=None, help="Limite de lugares a enriquecer"
    )
    enriquecer.add_argument(
        "--forcar", action="store_true", help="Re-enriquece mesmo os já processados"
    )
    enriquecer.add_argument(
        "--concorrencia", type=int, default=5, help="Concorrência paralela (padrão 5)"
    )
    exportar = subcomandos.add_parser(
        "exportar", help="Exporta leads qualificados para CSV/JSON com abordagem."
    )
    exportar.add_argument(
        "--arquivo", default="leads.csv", help="Caminho do arquivo de saída"
    )
    exportar.add_argument(
        "--min-score", type=float, default=0.0, help="Score mínimo de oportunidade"
    )
    exportar.add_argument("--cidade", default=None, help="Filtrar por cidade")
    exportar.add_argument(
        "--formato", choices=["csv", "json"], default="csv", help="Formato do arquivo"
    )
    return parser


def executar_relatorio(*, categoria: str | None, exemplos: int) -> ResultadoDedupe:
    """Imprime cobertura do grid e resultado do dedupe, com fusões auditáveis."""
    engine = criar_engine()
    preparar_banco(engine)

    with abrir_sessao(engine) as sessao:
        celulas = listar_celulas(sessao, categoria)
        places = listar_todos_places(sessao)
        chamadas = contar_api_calls(sessao)

    dedupe = deduplicar(places)
    subdivididas = sum(1 for c in celulas if c.saturada)

    print("--- cobertura ---")
    print(f"células visitadas .......... {len(celulas)}")
    print(f"células subdivididas ....... {subdivididas}")
    print(f"chamadas à Places API ...... {chamadas}")
    print("\n--- base ---")
    print(f"total bruto coletado ....... {dedupe.total_bruto}")
    print(f"total após dedupe .......... {dedupe.total_unico}")
    print(f"fusões ..................... {len(dedupe.fusoes)}")
    print(f"marcados para revisão ...... {len(dedupe.revisar)}")

    if dedupe.fusoes:
        print(f"\n--- {min(exemplos, len(dedupe.fusoes))} exemplos de fusão ---")
        for fusao in dedupe.fusoes[:exemplos]:
            print(f"{fusao.nome_mantido}  <-  {fusao.nome_duplicado}")
            print(f"    {fusao.decisao.confianca}: {fusao.decisao.motivo}")

    if dedupe.revisar:
        print(f"\n--- {min(exemplos, len(dedupe.revisar))} marcados para revisão ---")
        for par in dedupe.revisar[:exemplos]:
            print(f"{par.nome_mantido}  ~  {par.nome_duplicado}")
            print(f"    {par.decisao.motivo}")

    return dedupe


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


def executar_varredura(
    *,
    categoria: str,
    lat: float,
    lng: float,
    raio_km: float,
    passo_m: float,
    cidade: str,
) -> ResultadoVarredura:
    """Monta o grid, instala o Ctrl+C cooperativo e roda a varredura retomável."""
    celulas = gerar_grid(lat, lng, raio_km, passo_m)
    engine = criar_engine()
    preparar_banco(engine)

    with abrir_sessao(engine) as sessao:
        job = criar_job(sessao, query=f"{categoria} em {cidade}", cidade=cidade)
        job_id = job.id

    parada = threading.Event()

    def ao_receber_sigint(_sinal: int, _quadro: FrameType | None) -> None:
        print(
            "\ninterrompendo: a célula atual termina e o estado é gravado "
            "antes de sair",
            file=sys.stderr,
        )
        parada.set()

    anterior = signal.signal(signal.SIGINT, ao_receber_sigint)
    try:
        resultado = asyncio.run(
            varrer(
                categoria=categoria,
                cidade=cidade,
                celulas=celulas,
                engine=engine,
                job_id=job_id,
                deve_parar=parada.is_set,
            )
        )
    finally:
        signal.signal(signal.SIGINT, anterior)

    print(
        f"job #{job_id} terminou em {resultado.estado}: "
        f"{resultado.celulas_visitadas} células visitadas, "
        f"{resultado.celulas_puladas} puladas, "
        f"{resultado.celulas_subdivididas} subdivididas"
    )
    print(
        f"{resultado.total_bruto} registros brutos "
        f"({resultado.novos} novos) em {resultado.chamadas} chamada(s) HTTP"
    )
    if resultado.estado is EstadoJob.PAUSED_QUOTA:
        print(
            f"teto diário de {teto_chamadas_dia()} chamadas atingido; "
            "rode de novo amanhã que ele retoma de onde parou",
            file=sys.stderr,
        )
    return resultado


def executar_enriquecimento(
    *, limite: int | None, forcar: bool, concorrencia: int
) -> int:
    """Diagnostica a presença digital e enriquece os sites das empresas cadastradas."""
    engine = criar_engine()
    preparar_banco(engine)

    with abrir_sessao(engine) as sessao:
        places = listar_places_para_enriquecer(sessao, forcar=forcar, limite=limite)

    if not places:
        print("Nenhum lead pendente de enriquecimento.")
        return 0

    print(f"Enriquecendo {len(places)} empresas (concorrência: {concorrencia})...")
    processados = asyncio.run(enriquecer_lote(places, concorrencia=concorrencia))

    with abrir_sessao(engine) as sessao:
        for p in processados:
            salvar_place_enriquecido(sessao, p)

    por_nivel: dict[int, int] = {}
    com_email = 0
    com_whats = 0
    com_insta = 0
    for p in processados:
        nv = p.presence_level if p.presence_level is not None else -1
        por_nivel[nv] = por_nivel.get(nv, 0) + 1
        if p.emails:
            com_email += 1
        if p.whatsapp_url:
            com_whats += 1
        if p.instagram_url:
            com_insta += 1

    print("\n--- diagnóstico de presença digital ---")
    nomes_nivel = {
        0: "0 - sem site cadastrado",
        1: "1 - business.site (Google, descontinuado)",
        2: "2 - domínio próprio fora do ar (erro HTTP/DNS)",
        3: "3 - link de WhatsApp como site",
        4: "4 - domínio estacionado / página vazia",
        5: "5 - rede social / agregador (Instagram/Linktree)",
        6: "6 - construtor grátis (Wix/Blogspot/etc)",
        7: "7 - marketplace terceiro (Doctoralia/iFood)",
        8: "8 - site próprio fraco (sem mobile/sem SSL/antigo)",
        9: "9 - site próprio saudável",
    }
    for nv in range(10):
        if nv in por_nivel:
            print(f"  {nomes_nivel.get(nv, str(nv))}: {por_nivel[nv]}")

    print("\n--- contatos enriquecidos ---")
    print(f"  e-mails encontrados: {com_email}")
    print(f"  links de WhatsApp direto: {com_whats}")
    print(f"  perfis de Instagram: {com_insta}")
    print(f"\nTotal enriquecido: {len(processados)} leads salvos.")
    return len(processados)


def executar_exportacao(
    *,
    arquivo: str,
    min_score: float,
    cidade: str | None,
    formato: str,
) -> int:
    """Exporta leads qualificados para arquivo com links de WhatsApp."""
    engine = criar_engine()
    preparar_banco(engine)

    with abrir_sessao(engine) as sessao:
        total = exportar_leads_qualificados(
            sessao,
            arquivo,
            min_score=min_score,
            cidade=cidade,
            formato=formato,
        )

    print(
        f"Exportados {total} leads qualificados para '{arquivo}' "
        f"(score >= {min_score})."
    )
    return total


def main(argv: Sequence[str] | None = None) -> int:
    """Ponto de entrada da CLI."""
    args = montar_parser().parse_args(argv)
    if args.comando == "relatorio":
        executar_relatorio(categoria=args.categoria, exemplos=args.exemplos)
        return 0

    if args.comando == "enriquecer":
        executar_enriquecimento(
            limite=args.limite, forcar=args.forcar, concorrencia=args.concorrencia
        )
        return 0

    if args.comando == "exportar":
        executar_exportacao(
            arquivo=args.arquivo,
            min_score=args.min_score,
            cidade=args.cidade,
            formato=args.formato,
        )
        return 0

    if args.comando in {"coletar", "varrer"}:
        try:
            if args.comando == "coletar":
                executar_coleta(
                    categoria=args.categoria,
                    lat=args.lat,
                    lng=args.lng,
                    raio_m=args.raio_m,
                    cidade=args.cidade,
                )
            else:
                executar_varredura(
                    categoria=args.categoria,
                    lat=args.lat,
                    lng=args.lng,
                    raio_km=args.raio_km,
                    passo_m=args.passo_m,
                    cidade=args.cidade,
                )
        except RuntimeError as erro:
            print(f"erro: {erro}", file=sys.stderr)
            return 2
        except httpx.HTTPStatusError as erro:
            print(
                f"erro: a Places API respondeu HTTP {erro.response.status_code} "
                f"após 3 tentativas",
                file=sys.stderr,
            )
            return 3
    return 0
