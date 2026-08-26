"""Testes do cliente da Places API, contra a resposta real capturada."""

from __future__ import annotations

from typing import Any

import httpx
import pytest
import respx

from mapscout.sources.places_api import (
    ENDPOINT,
    Dormir,
    buscar_texto,
    montar_field_mask,
    retangulo_do_raio,
)


def _ok(corpo: dict[str, Any]) -> httpx.Response:
    return httpx.Response(200, json=corpo)


@respx.mock
async def test_parseia_a_pagina_real(
    pagina_places: dict[str, Any], dormir_falso: Dormir
) -> None:
    respx.post(ENDPOINT).mock(return_value=_ok(pagina_places))

    resultado = await buscar_texto(
        texto="dentista em Campinas", max_paginas=1, dormir=dormir_falso
    )

    assert len(resultado.places) == 20
    primeiro = resultado.places[0]
    assert primeiro.id == "ChIJ3Ssrf0rPyJQR-4Xd6fHI26k"
    assert primeiro.nome.texto == "Dra. Beatriz Toriani, Dentista"
    assert primeiro.telefone == "(19) 3233-4558"
    assert primeiro.localizacao is not None
    assert primeiro.localizacao.latitude == pytest.approx(-22.908821)
    assert primeiro.nota == pytest.approx(4.5)
    assert primeiro.qtd_avaliacoes == 144
    assert primeiro.status == "OPERATIONAL"
    assert primeiro.tipo_principal is not None
    assert primeiro.tipo_principal.texto == "Dentista"


@respx.mock
async def test_website_uri_ausente_vira_none(
    pagina_places: dict[str, Any], dormir_falso: Dormir
) -> None:
    respx.post(ENDPOINT).mock(return_value=_ok(pagina_places))

    resultado = await buscar_texto(
        texto="dentista em Campinas", max_paginas=1, dormir=dormir_falso
    )

    sem_site = [p for p in resultado.places if p.site is None]
    assert len(sem_site) == 5
    assert "Dentista Dra. Vânia Cristina N. Horie" in {p.nome.texto for p in sem_site}


@respx.mock
async def test_envia_field_mask_e_chave_no_header(
    pagina_final: dict[str, Any], dormir_falso: Dormir
) -> None:
    rota = respx.post(ENDPOINT).mock(return_value=_ok(pagina_final))

    await buscar_texto(texto="dentista", dormir=dormir_falso)

    enviado = rota.calls.last.request
    assert enviado.headers["X-Goog-Api-Key"] == "chave-de-teste"
    mask = enviado.headers["X-Goog-FieldMask"]
    assert "places.id" in mask
    assert "places.websiteUri" in mask
    assert mask.endswith("nextPageToken")


@respx.mock
async def test_field_mask_configuravel(
    pagina_final: dict[str, Any], dormir_falso: Dormir
) -> None:
    rota = respx.post(ENDPOINT).mock(return_value=_ok(pagina_final))

    await buscar_texto(
        texto="dentista", campos=("id", "websiteUri"), dormir=dormir_falso
    )

    assert rota.calls.last.request.headers["X-Goog-FieldMask"] == (
        "places.id,places.websiteUri,nextPageToken"
    )
    assert montar_field_mask(("id",)) == "places.id,nextPageToken"


@respx.mock
async def test_para_em_tres_paginas(
    pagina_places: dict[str, Any], dormir_falso: Dormir
) -> None:
    rota = respx.post(ENDPOINT).mock(return_value=_ok(pagina_places))

    resultado = await buscar_texto(texto="dentista", dormir=dormir_falso)

    assert rota.call_count == 3
    assert len(resultado.places) == 60


@respx.mock
async def test_para_quando_nao_ha_next_page_token(
    pagina_final: dict[str, Any], dormir_falso: Dormir
) -> None:
    rota = respx.post(ENDPOINT).mock(return_value=_ok(pagina_final))

    resultado = await buscar_texto(texto="dentista", dormir=dormir_falso)

    assert rota.call_count == 1
    assert len(resultado.places) == 20


@respx.mock
async def test_pausa_dois_segundos_antes_de_usar_page_token(
    pagina_places: dict[str, Any], dormir_falso: Dormir, dormidas: list[float]
) -> None:
    respx.post(ENDPOINT).mock(return_value=_ok(pagina_places))

    await buscar_texto(texto="dentista", dormir=dormir_falso)

    assert dormidas == [2.0, 2.0]


@respx.mock
async def test_envia_page_token_e_retangulo(
    pagina_places: dict[str, Any],
    pagina_final: dict[str, Any],
    dormir_falso: Dormir,
) -> None:
    rota = respx.post(ENDPOINT).mock(
        side_effect=[_ok(pagina_places), _ok(pagina_final)]
    )

    await buscar_texto(
        texto="dentista",
        retangulo=retangulo_do_raio(-22.9, -47.06, 2000),
        dormir=dormir_falso,
    )

    primeiro = rota.calls[0].request.read().decode()
    segundo = rota.calls[1].request.read().decode()
    assert "pageToken" not in primeiro
    assert "locationRestriction" in primeiro
    assert "rectangle" in primeiro
    assert pagina_places["nextPageToken"] in segundo


@respx.mock
async def test_retenta_em_429_e_depois_tem_sucesso(
    pagina_final: dict[str, Any], dormir_falso: Dormir, dormidas: list[float]
) -> None:
    rota = respx.post(ENDPOINT).mock(
        side_effect=[httpx.Response(429), _ok(pagina_final)]
    )

    resultado = await buscar_texto(texto="dentista", dormir=dormir_falso)

    assert rota.call_count == 2
    assert len(resultado.places) == 20
    assert dormidas == [1.0]


@respx.mock
async def test_retenta_em_503_e_esgota_as_tentativas(dormir_falso: Dormir) -> None:
    rota = respx.post(ENDPOINT).mock(return_value=httpx.Response(503))

    with pytest.raises(httpx.HTTPStatusError):
        await buscar_texto(texto="dentista", dormir=dormir_falso)

    assert rota.call_count == 3


@respx.mock
async def test_registra_uma_chamada_por_tentativa(
    pagina_final: dict[str, Any], dormir_falso: Dormir
) -> None:
    respx.post(ENDPOINT).mock(
        side_effect=[httpx.Response(429), httpx.Response(500), _ok(pagina_final)]
    )

    resultado = await buscar_texto(texto="dentista", dormir=dormir_falso)

    assert [c.status_code for c in resultado.chamadas] == [429, 500, 200]
    assert [c.qtd_resultados for c in resultado.chamadas] == [0, 0, 20]
    assert all(c.endpoint == ENDPOINT for c in resultado.chamadas)
    assert all("places.id" in c.field_mask for c in resultado.chamadas)


def test_retangulo_do_raio_circunscreve_o_circulo() -> None:
    retangulo = retangulo_do_raio(-22.9, -47.06, 1000)

    assert retangulo.lat_min < -22.9 < retangulo.lat_max
    assert retangulo.lng_min < -47.06 < retangulo.lng_max
    assert retangulo.lat_max - -22.9 == pytest.approx(1000 / 111_320.0)
    assert retangulo.para_json()["low"]["latitude"] == retangulo.lat_min
