"""Testes de normalização com dados brasileiros reais."""

from __future__ import annotations

import pytest

from mapscout.normalize.address import extrair_cep, normalizar_endereco
from mapscout.normalize.domain import dominio_registravel
from mapscout.normalize.name import normalizar_nome
from mapscout.normalize.phone import (
    TIPO_ESPECIAL,
    TIPO_FIXO,
    TIPO_MOVEL,
    normalizar_telefone,
)


@pytest.mark.parametrize(
    ("bruto", "esperado", "tipo"),
    [
        # Os dois primeiros vêm literalmente do fixture da Places API.
        ("(19) 3233-4558", "+551932334558", TIPO_FIXO),
        ("(19) 99214-1001", "+5519992141001", TIPO_MOVEL),
        ("+55 (19) 99214-1001", "+5519992141001", TIPO_MOVEL),
        ("55 19 3233 4558", "+551932334558", TIPO_FIXO),
        ("(019) 3233-4558", "+551932334558", TIPO_FIXO),
        ("(19) 3233-4558 ramal 205", "+551932334558", TIPO_FIXO),
        # 0800 da Uniodonto Campinas, também do fixture.
        ("0800 160 5555", "+558001605555", TIPO_ESPECIAL),
        ("4004-1234", "+5540041234", TIPO_ESPECIAL),
    ],
)
def test_normalizar_telefone_validos(bruto: str, esperado: str, tipo: str) -> None:
    assert normalizar_telefone(bruto) == (esperado, tipo)


@pytest.mark.parametrize(
    "bruto",
    [
        None,
        "",
        "sem telefone",
        "123",
        "(19) 12345-6789",  # 11 dígitos mas o terceiro não é 9: não é móvel
        "(19) 9233-4558",  # 10 dígitos começando com 9: não é fixo válido
        "(01) 3233-4558",  # DDD inexistente
    ],
)
def test_normalizar_telefone_invalidos(bruto: str | None) -> None:
    assert normalizar_telefone(bruto) == (None, None)


@pytest.mark.parametrize(
    ("url", "esperado"),
    [
        (
            "https://www.doctoralia.com.br/beatriz-toriani/dentista/campinas"
            "?utm_source=google&utm_medium=gmb",
            "doctoralia.com.br",
        ),
        ("https://mirianbustillodentista.com.br/", "mirianbustillodentista.com.br"),
        ("https://redesags.wixsite.com/drathainasouza", "wixsite.com"),
        ("http://dentistacampinas.odo.br/", "dentistacampinas.odo.br"),
        ("www.oralclincampinas.com.br:8080/contato#topo", "oralclincampinas.com.br"),
        (None, None),
        ("   ", None),
    ],
)
def test_dominio_registravel(url: str | None, esperado: str | None) -> None:
    assert dominio_registravel(url) == esperado


@pytest.mark.parametrize(
    ("bruto", "esperado"),
    [
        ("ODONTOLOGIA PAZOTTO", "odontologia pazotto"),
        ("Odontologia Pazotto Ltda", "odontologia pazotto"),
        ("Dra. Thainá Souza - Dentista", "dra thaina souza dentista"),
        ("Oral Clin Campinas S/A", "oral clin campinas"),
        ("Clínica  Sorriso   EIRELI", "clinica sorriso"),
        (None, ""),
    ],
)
def test_normalizar_nome(bruto: str | None, esperado: str) -> None:
    assert normalizar_nome(bruto) == esperado


@pytest.mark.parametrize(
    ("bruto", "esperado"),
    [
        ("Rua Barão de Jaguara, 655 - Centro, Campinas - SP, 13015-001", "13015-001"),
        ("Av. Brasil, 220 - Vila Itapura, Campinas - SP, 13023075", "13023-075"),
        ("Rua sem CEP, 10", None),
        (None, None),
    ],
)
def test_extrair_cep(bruto: str | None, esperado: str | None) -> None:
    assert extrair_cep(bruto) == esperado


def test_normalizar_endereco_expande_abreviacoes() -> None:
    bruto = "R. Dr. Emílio Ribas, 805 - Sl 61 - Cambuí"

    assert normalizar_endereco(bruto) == "rua dr emilio ribas 805 sala 61 cambui"


def test_normalizar_endereco_equipara_grafias_diferentes() -> None:
    a = normalizar_endereco("Av. da Saudade, 832 - Sl 02")
    b = normalizar_endereco("Avenida da Saudade, 832, Sala 02")

    assert a == b
