"""Cliente da camada de IA com ancoragem estrita e gerador consultivo de copy."""

from __future__ import annotations

from sqlmodel import Session

from mapscout.ai.cache import (
    calcular_hash_place,
    obter_abordagem_cache,
    salvar_abordagem_cache,
)
from mapscout.ai.schemas import AbordagemLead, validar_ancoragem
from mapscout.db.models import Place


def _gerar_copy_deterministica(place: Place) -> AbordagemLead:
    """Gera abordagem de alta conversão ancorada nos dados reais do lead."""
    nome = place.display_name
    cidade_str = f" em {place.cidade}" if place.cidade else ""
    evidencia = place.presence_evidence or "ausência de site oficial"
    nivel = place.presence_level if place.presence_level is not None else 0

    if nivel == 0:
        gancho = "Ausência de site oficial no perfil do Google"
        justificativa = (
            f"A empresa {nome} tem presença no Google Maps, mas sem site cadastrado."
        )
        msg_whats = (
            f"Olá! Tudo bem? Encontrei o perfil da {nome}{cidade_str} no Google. "
            "Notei que vocês têm ótimas referências, mas ainda não têm um site "
            "para apresentar seus serviços e agilizar o contato com novos clientes.\n\n"
            "Eu desenvolvo páginas rápidas e adaptadas para celular para seu setor. "
            "Posso te mandar uma prévia de como ficaria um site para vocês?"
        )
    elif nivel == 2:
        gancho = "Site cadastrado no Google está fora do ar ou com erro"
        justificativa = (
            f"O site da empresa {nome} ({place.website_uri}) está fora do ar."
        )
        msg_whats = (
            f"Olá! Tudo bem? Encontrei o perfil da {nome}{cidade_str} no Google.\n\n"
            f"Percebi que o link do site cadastrado ({place.website_uri}) "
            "está fora do ar neste momento. Isso pode estar afastando clientes.\n\n"
            "Trabalho corrigindo e modernizando sites para empresas locais. "
            "Se quiser, posso te passar uma orientação rápida sem compromisso."
        )
    elif nivel in (3, 5):
        gancho = "Uso de rede social ou WhatsApp no lugar de site profissional"
        justificativa = (
            f"A empresa {nome} utiliza link de rede social/WhatsApp no perfil."
        )
        msg_whats = (
            f"Olá! Tudo bem? Vi o perfil da {nome} no Google "
            "com ótimas recomendações.\n\n"
            "Notei que o link principal direciona direto para o Instagram/WhatsApp. "
            "Muitos clientes preferem ver informações claras e depoimentos "
            "em um site rápido antes de chamar.\n\n"
            "Desenvolvo páginas de alta conversão integradas ao WhatsApp. "
            "Teria 2 minutos para ver um modelo focado no seu segmento?"
        )
    elif nivel == 8:
        gancho = "Site próprio com problemas de adaptação para celular ou segurança"
        justificativa = (
            f"O site da {nome} ({place.website_uri}) apresenta falhas técnicas."
        )
        msg_whats = (
            f"Olá! Tudo bem? Visitei o site da {nome} a partir da busca do Google.\n\n"
            f"Notei um ponto importante: {evidencia}. "
            "Hoje, a maioria das buscas locais são feitas pelo smartphone, e sites que "
            "não são responsivos perdem posições no Google e clientes.\n\n"
            "Posso te enviar um diagnóstico breve mostrando onde melhorar?"
        )
    else:
        gancho = "Otimização de presença digital e captação de clientes"
        justificativa = f"Empresa ativa com presença no Google: {evidencia}."
        msg_whats = (
            f"Olá! Tudo bem? Acompanhei o trabalho da {nome}{cidade_str}.\n\n"
            "Ajudamos empresas locais a aumentarem suas vendas pelo Google através "
            "de páginas profissionais e estratégias de captação.\n\n"
            "Você teria disponibilidade para conversarmos brevemente?"
        )

    msg_email: str | None = None
    if place.emails:
        msg_email = (
            f"Assunto: Oportunidade de melhoria na presença digital da {nome}\n\n"
            f"Olá, equipe da {nome}!\n\n"
            f"Ao analisar a presença digital de empresas do setor{cidade_str}, "
            "encontrei o perfil de vocês no Google.\n\n"
            f"Identifiquei um ponto de atenção importante: {evidencia}.\n\n"
            "Ter uma página moderna, rápida e otimizada garante que quem "
            "pesquisa pela sua empresa feche negócio com vocês.\n\n"
            "Ficarei feliz em apresentar um diagnóstico gratuito.\n\n"
            "Podemos conversar esta semana?\n\n"
            "Atenciosamente,"
        )

    return AbordagemLead(
        gancho_comercial=gancho,
        justificativa=justificativa,
        mensagem_whatsapp=msg_whats,
        mensagem_email=msg_email,
    )


def gerar_rascunho_abordagem(
    place: Place, *, sessao: Session | None = None
) -> AbordagemLead:
    """Gera abordagem comercial personalizada com cache e validação estrita."""
    hash_entrada = calcular_hash_place(place)

    if sessao is not None:
        em_cache = obter_abordagem_cache(sessao, place.place_id, hash_entrada)
        if em_cache is not None:
            return em_cache

    abordagem = _gerar_copy_deterministica(place)

    if not validar_ancoragem(abordagem, place):
        msg_erro = f"Abordagem violou ancoragem para o place {place.place_id}"
        raise ValueError(msg_erro)

    if sessao is not None:
        salvar_abordagem_cache(sessao, place.place_id, hash_entrada, abordagem)

    return abordagem
