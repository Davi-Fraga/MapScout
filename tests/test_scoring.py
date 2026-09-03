from mapscout.db.models import Place
from mapscout.scoring import calcular_saude_negocio, calcular_score_lead


def test_saude_negocio_sem_avaliacoes() -> None:
    saude = calcular_saude_negocio(rating=None, user_rating_count=None)
    assert saude == 0.90


def test_saude_negocio_muitas_avaliacoes_alta_nota() -> None:
    saude = calcular_saude_negocio(rating=4.8, user_rating_count=160)
    assert saude > 1.30


def test_saude_negocio_nota_baixa() -> None:
    saude = calcular_saude_negocio(rating=3.0, user_rating_count=20)
    assert saude < 1.0


def test_calcular_score_lead_sem_site_clinica() -> None:
    place = Place(
        place_id="s1",
        display_name="Clínica Odonto Prime",
        website_uri=None,
        rating=4.9,
        user_rating_count=120,
        primary_type_display_name="Clínica Odontológica",
    )
    score = calcular_score_lead(place, categoria="dentista")
    # Nível 0 tem base 100 * saude (~1.37) * ticket (1.25) -> alto score (> 150)
    assert score > 120.0


def test_calcular_score_lead_site_saudavel() -> None:
    place = Place(
        place_id="s2",
        display_name="Pizzaria Central",
        website_uri="https://pizzariacentral.com.br",
        presence_level=9,
        rating=4.0,
        user_rating_count=30,
        primary_type_display_name="Restaurante",
    )
    score = calcular_score_lead(place, categoria="restaurante")
    # Nível 9 tem base 10 -> score muito menor (< 20)
    assert score < 25.0
