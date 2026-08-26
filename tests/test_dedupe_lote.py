"""Dedupe em lote sobre a base, e o relatório do Checkpoint 2."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from sqlmodel import Session

from mapscout.cli import main
from mapscout.db.models import Place
from mapscout.db.repo import place_de_resposta, upsert_place
from mapscout.db.session import abrir_sessao, criar_engine, preparar_banco
from mapscout.dedupe.lote import deduplicar
from mapscout.sources.places_api import PaginaResposta


def _place(
    place_id: str,
    nome: str,
    *,
    cidade: str | None = "Campinas",
    telefone: str | None = None,
    site: str | None = None,
    endereco: str | None = None,
) -> Place:
    return Place(
        place_id=place_id,
        display_name=nome,
        cidade=cidade,
        national_phone_number=telefone,
        website_uri=site,
        formatted_address=endereco,
    )


def test_base_do_fixture_nao_tem_duplicata(pagina_places: dict[str, Any]) -> None:
    """Os 20 registros reais são 20 empresas distintas: nada pode fundir."""
    pagina = PaginaResposta.model_validate(pagina_places)
    places = [place_de_resposta(p, "Campinas") for p in pagina.places]

    resultado = deduplicar(places)

    assert resultado.total_bruto == 20
    assert resultado.total_unico == 20
    assert resultado.fusoes == []


def test_place_id_repetido_funde() -> None:
    places = [
        _place("A", "Odonto Urgente"),
        _place("A", "Odonto Urgente Campinas"),
        _place("B", "Oral Clin"),
    ]

    resultado = deduplicar(places)

    assert resultado.total_bruto == 3
    assert resultado.total_unico == 2
    assert len(resultado.fusoes) == 1
    assert "place_id" in resultado.fusoes[0].decisao.motivo


def test_dominio_proprio_repetido_funde_e_marketplace_nao() -> None:
    places = [
        _place("A", "Oral Clin", site="https://www.oralclincampinas.com.br/"),
        _place("B", "Oral Clin Cambuí", site="https://oralclincampinas.com.br/x"),
        _place("C", "Dra. Beatriz", site="https://www.doctoralia.com.br/beatriz"),
        _place("D", "Dr. Guilherme", site="https://www.doctoralia.com.br/guilherme"),
    ]

    resultado = deduplicar(places)

    # Os dois da Doctoralia continuam separados; só os do domínio próprio fundem.
    assert resultado.total_unico == 3
    assert len(resultado.fusoes) == 1
    assert "oralclincampinas.com.br" in resultado.fusoes[0].decisao.motivo


def test_filiais_com_mesmo_site_sobrevivem_ao_lote() -> None:
    places = [
        _place("A", "Uniodonto", cidade="Campinas", site="https://uniodonto.com.br/"),
        _place("B", "Uniodonto", cidade="Limeira", site="https://uniodonto.com.br/"),
    ]

    resultado = deduplicar(places)

    assert resultado.total_unico == 2
    assert resultado.fusoes == []


def test_pares_no_mesmo_cep_sao_marcados_para_revisao() -> None:
    endereco = "Rua Barão de Jaguara, 655 - Centro, Campinas - SP, 13015-001"
    places = [
        _place("A", "Odontologia Pazotto", endereco=endereco),
        _place("B", "Odontologia Pazotto Ltda", endereco=endereco),
    ]

    resultado = deduplicar(places)

    assert resultado.total_unico == 2
    assert len(resultado.revisar) == 1
    assert "confira antes de fundir" in resultado.revisar[0].decisao.motivo


def test_relatorio_imprime_cobertura_dedupe_e_exemplos(
    pagina_places: dict[str, Any],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    banco = tmp_path / "relatorio.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{banco}")
    engine = criar_engine(f"sqlite:///{banco}")
    preparar_banco(engine)

    pagina = PaginaResposta.model_validate(pagina_places)
    with abrir_sessao(engine) as sessao:
        for resposta in pagina.places:
            upsert_place(sessao, place_de_resposta(resposta, "Campinas"))
        upsert_place(
            sessao, _place("duplicado", "Oral Clin", site="oralclincampinas.com.br")
        )
        sessao.commit()

    codigo = main(["relatorio", "--exemplos", "3"])
    saida = capsys.readouterr().out

    assert codigo == 0
    assert "total bruto coletado ....... 21" in saida
    assert "total após dedupe .......... 20" in saida
    assert "exemplos de fusão" in saida
    assert "oralclincampinas.com.br" in saida


def test_relatorio_em_base_vazia_nao_quebra(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'vazio.db'}")

    codigo = main(["relatorio"])

    assert codigo == 0
    assert "total bruto coletado ....... 0" in capsys.readouterr().out


def test_sessao_fixture_continua_utilizavel(sessao: Session) -> None:
    assert deduplicar([]).total_unico == 0
