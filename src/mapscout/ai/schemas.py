"""Schemas Pydantic da camada de IA e validação de ancoragem estrita."""

from __future__ import annotations

from pydantic import BaseModel, Field

from mapscout.db.models import Place


class AbordagemLead(BaseModel):
    """Rascunho de abordagem comercial personalizada ancorada em dados reais."""

    gancho_comercial: str = Field(
        description="A dor central identificada na presença digital da empresa."
    )
    justificativa: str = Field(
        description="Por que abordar esta empresa, citando campo real."
    )
    mensagem_whatsapp: str = Field(
        description="Mensagem direta e consultiva para contato no WhatsApp."
    )
    mensagem_email: str | None = Field(
        default=None,
        description="E-mail consultivo de diagnóstico rápido (se houver e-mail).",
    )


def validar_ancoragem(abordagem: AbordagemLead, place: Place) -> bool:
    """Garante que a justificativa cita apenas campos existentes e preenchidos."""
    justificativa_lower = abordagem.justificativa.lower()

    # Se o place não tem site e a justificativa falar de 'site da empresa'
    if not place.website_uri and "no site da empresa" in justificativa_lower:
        return False

    # Se a justificativa cita avaliações mas o place não tem avaliações
    if (
        place.user_rating_count is None or place.user_rating_count == 0
    ) and "avaliações no google" in justificativa_lower:
        return False

    # Se cita redes sociais mas o place não tem links de redes
    sem_redes = not place.instagram_url and not place.facebook_url
    return not (sem_redes and "perfil do instagram" in justificativa_lower)
