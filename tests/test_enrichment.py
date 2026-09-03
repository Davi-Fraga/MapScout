import httpx
import pytest
import respx

from mapscout.db.models import Place
from mapscout.enrichment.parser import extrair_emails_do_texto, extrair_sinais_html
from mapscout.enrichment.service import enriquecer_lote, enriquecer_place


def test_extrair_emails() -> None:
    texto = (
        "Nosso contato é contato@clinicasilva.com.br "
        "ou suporte@clinicasilva.com.br. Ignorar logo.png"
    )
    emails = extrair_emails_do_texto(texto)
    assert emails == ["contato@clinicasilva.com.br", "suporte@clinicasilva.com.br"]


def test_extrair_sinais_html_completo() -> None:
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <link rel="stylesheet" href="/wp-content/themes/custom/style.css">
    </head>
    <body>
        <h1>Clínica Odontológica</h1>
        <p>Agende uma consulta: contato@odonto.com.br</p>
        <a href="https://wa.me/5519999990000?text=Ola">Fale no WhatsApp</a>
        <a href="https://www.instagram.com/odontoclinica/">Instagram</a>
        <a href="https://www.facebook.com/odontoclinica">Facebook</a>
        <footer>
            <p>© 2025 Clínica Odontológica. Todos os direitos reservados.</p>
        </footer>
    </body>
    </html>
    """
    sinais = extrair_sinais_html(html)
    assert sinais.has_mobile_viewport is True
    assert sinais.copyright_year == 2025
    assert "contato@odonto.com.br" in sinais.emails
    assert sinais.whatsapp_url == "https://wa.me/5519999990000?text=Ola"
    assert sinais.instagram_url == "https://www.instagram.com/odontoclinica/"
    assert sinais.facebook_url == "https://www.facebook.com/odontoclinica"
    assert "WordPress" in sinais.tech_detected
    assert sinais.is_parked_or_empty is False


def test_extrair_sinais_sem_viewport_e_antigo() -> None:
    html = """
    <html>
    <body>
        <h1>Site Antigo</h1>
        <p>Desenvolvido em 2015.</p>
        <footer>Copyright 2017 - Minha Empresa</footer>
    </body>
    </html>
    """
    sinais = extrair_sinais_html(html)
    assert sinais.has_mobile_viewport is False
    assert sinais.copyright_year == 2017
    assert sinais.is_parked_or_empty is False


def test_extrair_sinais_pagina_estacionada() -> None:
    html = (
        "<html><body>Este domínio está à venda. Contate o administrador.</body></html>"
    )
    sinais = extrair_sinais_html(html)
    assert sinais.is_parked_or_empty is True


@pytest.mark.asyncio
async def test_enriquecer_place_sem_site() -> None:
    place = Place(place_id="p1", display_name="Empresa Sem Site", website_uri=None)
    atualizado = await enriquecer_place(place)
    assert atualizado.presence_level == 0
    assert atualizado.presence_evidence is not None
    assert atualizado.enriquecido_em is not None


@pytest.mark.asyncio
async def test_enriquecer_place_social_sem_rede() -> None:
    place = Place(
        place_id="p2",
        display_name="Empresa com Insta",
        website_uri="https://instagram.com/dentistasilva",
    )
    atualizado = await enriquecer_place(place)
    assert atualizado.presence_level == 5
    assert "instagram" in (atualizado.presence_evidence or "").lower()


@pytest.mark.asyncio
@respx.mock
async def test_enriquecer_place_site_proprio_com_respx() -> None:
    site_url = "https://www.odontoclinic.com.br"
    html = """
    <!DOCTYPE html>
    <html>
    <head><meta name="viewport" content="width=device-width, initial-scale=1"></head>
    <body>
        <p>Email: contato@odontoclinic.com.br</p>
        <a href="https://wa.me/5511999998888">WhatsApp</a>
        <footer>© 2026 Odonto Clinic</footer>
    </body>
    </html>
    """
    respx.get(site_url).respond(status_code=200, html=html)

    place = Place(
        place_id="p3",
        display_name="Odonto Clinic",
        website_uri=site_url,
    )

    async with httpx.AsyncClient() as client:
        atualizado = await enriquecer_place(place, client=client)

    assert atualizado.presence_level == 9
    assert atualizado.has_ssl is True
    assert atualizado.has_mobile_viewport is True
    assert atualizado.copyright_year == 2026
    assert atualizado.emails == "contato@odontoclinic.com.br"
    assert atualizado.whatsapp_url == "https://wa.me/5511999998888"


@pytest.mark.asyncio
@respx.mock
async def test_enriquecer_place_site_fora_do_ar_com_respx() -> None:
    site_url = "https://www.sitefora.com.br"
    respx.get(site_url).respond(status_code=503)

    place = Place(
        place_id="p4",
        display_name="Site Fora",
        website_uri=site_url,
    )

    async with httpx.AsyncClient() as client:
        atualizado = await enriquecer_place(place, client=client)

    assert atualizado.presence_level == 2
    assert "503" in (atualizado.presence_evidence or "")


@pytest.mark.asyncio
@respx.mock
async def test_enriquecer_lote_com_respx() -> None:
    respx.get("https://site1.com.br").respond(
        status_code=200,
        html=(
            "<html><head><meta name='viewport' content='width=device-width'></head>"
            "<body><p>Bem-vindo ao site da clínica odontológica 2026</p></body></html>"
        ),
    )
    respx.get("https://site2.com.br").respond(status_code=404)

    places = [
        Place(place_id="l1", display_name="L1", website_uri="https://site1.com.br"),
        Place(place_id="l2", display_name="L2", website_uri="https://site2.com.br"),
        Place(place_id="l3", display_name="L3", website_uri=None),
    ]

    async with httpx.AsyncClient() as client:
        processados = await enriquecer_lote(places, client=client, concorrencia=2)

    assert len(processados) == 3
    assert processados[0].presence_level == 9
    assert processados[1].presence_level == 2
    assert processados[2].presence_level == 0
