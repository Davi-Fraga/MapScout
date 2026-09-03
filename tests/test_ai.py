from sqlmodel import Session

from mapscout.ai.client import gerar_rascunho_abordagem
from mapscout.ai.schemas import AbordagemLead, validar_ancoragem
from mapscout.db.models import Place


def test_validar_ancoragem_rejeita_alucinacao() -> None:
    place_sem_site = Place(place_id="a1", display_name="Auto Center", website_uri=None)
    abordagem_falsa = AbordagemLead(
        gancho_comercial="Site lento",
        justificativa="Vi no site da empresa que ele demora para carregar",
        mensagem_whatsapp="Olá",
    )
    assert validar_ancoragem(abordagem_falsa, place_sem_site) is False


def test_gerar_rascunho_abordagem_sem_site(sessao: Session) -> None:
    place = Place(
        place_id="a2",
        display_name="Dr. Carlos Dentista",
        cidade="Campinas",
        website_uri=None,
        presence_level=0,
        presence_evidence="Não possui site cadastrado no perfil da empresa.",
    )
    abordagem = gerar_rascunho_abordagem(place, sessao=sessao)
    assert "Dr. Carlos" in abordagem.mensagem_whatsapp
    assert "Campinas" in abordagem.mensagem_whatsapp
    assert "site" in abordagem.mensagem_whatsapp.lower()
    assert abordagem.gancho_comercial != ""


def test_gerar_rascunho_com_cache(sessao: Session) -> None:
    place = Place(
        place_id="a3",
        display_name="Clínica Sorriso",
        cidade="São Paulo",
        website_uri="https://instagram.com/sorriso",
        presence_level=5,
        presence_evidence="Utiliza perfil em rede social no lugar de site próprio.",
    )
    ab1 = gerar_rascunho_abordagem(place, sessao=sessao)
    # Segunda chamada deve bater no cache
    ab2 = gerar_rascunho_abordagem(place, sessao=sessao)
    assert ab1.mensagem_whatsapp == ab2.mensagem_whatsapp
