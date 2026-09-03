from mapscout.classification.presence import (
    classificar_por_url,
    classificar_site_proprio,
)


def test_nivel_0_sem_site() -> None:
    c1 = classificar_por_url(None)
    assert c1 is not None
    assert c1.nivel == 0
    assert c1.score_base == 100.0

    c2 = classificar_por_url("   ")
    assert c2 is not None
    assert c2.nivel == 0


def test_nivel_1_google_business_site() -> None:
    c = classificar_por_url("https://dr-silva.business.site")
    assert c is not None
    assert c.nivel == 1
    assert c.score_base == 95.0
    assert "business.site" in c.evidencia


def test_nivel_3_whatsapp_como_site() -> None:
    c1 = classificar_por_url("https://wa.me/5519999998888")
    assert c1 is not None
    assert c1.nivel == 3
    assert c1.score_base == 88.0

    c2 = classificar_por_url("https://api.whatsapp.com/send?phone=5511988887777")
    assert c2 is not None
    assert c2.nivel == 3


def test_nivel_5_rede_social_ou_agregador() -> None:
    c_insta = classificar_por_url("https://instagram.com/clinicadentaria")
    assert c_insta is not None
    assert c_insta.nivel == 5
    assert c_insta.score_base == 85.0

    c_linktree = classificar_por_url("https://linktr.ee/doutorpedro")
    assert c_linktree is not None
    assert c_linktree.nivel == 5


def test_nivel_6_construtor_gratis() -> None:
    c_wix = classificar_por_url("https://doutoraana.wixsite.com/meusite")
    assert c_wix is not None
    assert c_wix.nivel == 6
    assert c_wix.score_base == 80.0

    c_lovable = classificar_por_url("https://clinica.lovable.app")
    assert c_lovable is not None
    assert c_lovable.nivel == 6


def test_nivel_7_marketplace() -> None:
    c_doc = classificar_por_url("https://www.doctoralia.com.br/medico/joao-silva")
    assert c_doc is not None
    assert c_doc.nivel == 7
    assert c_doc.score_base == 75.0


def test_dominio_proprio_devolve_none_na_classificacao_por_url() -> None:
    c = classificar_por_url("https://clinicasilva.com.br")
    assert c is None


def test_nivel_2_site_proprio_com_erro() -> None:
    c_404 = classificar_site_proprio(
        status_code=404,
        has_ssl=True,
        has_mobile_viewport=True,
        copyright_year=2026,
    )
    assert c_404.nivel == 2
    assert c_404.score_base == 90.0
    assert "404" in c_404.evidencia

    c_dns = classificar_site_proprio(
        status_code=None,
        has_ssl=False,
        has_mobile_viewport=False,
        copyright_year=None,
        erro_conexao="DNS falhou",
    )
    assert c_dns.nivel == 2
    assert "DNS falhou" in c_dns.evidencia


def test_nivel_4_dominio_estacionado() -> None:
    c = classificar_site_proprio(
        status_code=200,
        has_ssl=True,
        has_mobile_viewport=True,
        copyright_year=None,
        is_parked_or_empty=True,
    )
    assert c.nivel == 4
    assert c.score_base == 87.0


def test_nivel_8_site_proprio_fraco() -> None:
    # Sem mobile viewport
    c_sem_mobile = classificar_site_proprio(
        status_code=200,
        has_ssl=True,
        has_mobile_viewport=False,
        copyright_year=2026,
    )
    assert c_sem_mobile.nivel == 8
    assert c_sem_mobile.score_base == 50.0
    assert "viewport mobile" in c_sem_mobile.evidencia

    # Sem SSL
    c_sem_ssl = classificar_site_proprio(
        status_code=200,
        has_ssl=False,
        has_mobile_viewport=True,
        copyright_year=2026,
    )
    assert c_sem_ssl.nivel == 8
    assert "SSL" in c_sem_ssl.evidencia

    # Copyright antigo
    c_antigo = classificar_site_proprio(
        status_code=200,
        has_ssl=True,
        has_mobile_viewport=True,
        copyright_year=2018,
    )
    assert c_antigo.nivel == 8
    assert "2018" in c_antigo.evidencia


def test_nivel_9_site_saudavel() -> None:
    c = classificar_site_proprio(
        status_code=200,
        has_ssl=True,
        has_mobile_viewport=True,
        copyright_year=2026,
    )
    assert c.nivel == 9
    assert c.score_base == 10.0
