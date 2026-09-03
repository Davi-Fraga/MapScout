"""Score determinístico de oportunidade de venda de sites e presença digital."""

from __future__ import annotations

from mapscout.classification.presence import SCORE_BASE_PRESENCA, classificar_por_url
from mapscout.config import multiplicador_ticket
from mapscout.db.models import Place


def calcular_saude_negocio(
    rating: float | None, user_rating_count: int | None
) -> float:
    """Calcula o multiplicador de saúde e tração comercial da empresa no Google."""
    if not user_rating_count or user_rating_count <= 0:
        return 0.90

    # Volume de avaliações demonstra fluxo de clientes e caixa ativo
    if user_rating_count <= 10:
        fator_volume = 0.95
    elif user_rating_count <= 30:
        fator_volume = 1.05
    elif user_rating_count <= 70:
        fator_volume = 1.15
    elif user_rating_count <= 150:
        fator_volume = 1.25
    else:
        fator_volume = 1.35

    # Nota reflete satisfação dos clientes e zelo pela marca
    nota = rating if rating is not None else 4.0
    if nota >= 4.5:
        fator_nota = 1.10
    elif nota >= 4.0:
        fator_nota = 1.00
    elif nota >= 3.5:
        fator_nota = 0.90
    else:
        fator_nota = 0.80

    saude = fator_volume * fator_nota
    return round(max(0.60, min(1.50, saude)), 3)


def calcular_score_lead(place: Place, categoria: str | None = None) -> float:
    """Calcula o score: base_presenca * saude_negocio * ticket_categoria."""
    nivel = place.presence_level
    if nivel is None:
        preliminar = classificar_por_url(place.website_uri)
        nivel = preliminar.nivel if preliminar is not None else 8

    base_presenca = SCORE_BASE_PRESENCA.get(nivel, 50.0)
    saude = calcular_saude_negocio(place.rating, place.user_rating_count)
    cat = categoria or place.primary_type_display_name or ""
    ticket = multiplicador_ticket(cat)

    score = base_presenca * saude * ticket
    return round(max(5.0, score), 1)
