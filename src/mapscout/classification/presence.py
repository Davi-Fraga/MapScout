"""Classificação de presença digital conforme os níveis 0 a 9 do domínio."""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse

from mapscout.dominios import CONSTRUTOR_GRATIS, MARKETPLACE, SOCIAL
from mapscout.normalize.domain import dominio_registravel

SCORE_BASE_PRESENCA: dict[int, float] = {
    0: 100.0,
    1: 95.0,
    2: 90.0,
    3: 88.0,
    4: 87.0,
    5: 85.0,
    6: 80.0,
    7: 75.0,
    8: 50.0,
    9: 10.0,
}

_PADRAO_WHATSAPP = re.compile(
    r"(?:wa\.me|api\.whatsapp\.com|whatsapp\.com/send|chat\.whatsapp\.com)",
    re.IGNORECASE,
)
_PADRAO_GOOGLE_SITE = re.compile(
    r"(?:business\.site|negocio\.site)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ClassificacaoPresenca:
    """Resultado da classificação de presença digital de uma empresa."""

    nivel: int
    evidencia: str
    score_base: float


def classificar_por_url(website_uri: str | None) -> ClassificacaoPresenca | None:
    """Classifica preliminarmente pela URL sem requisição (níveis 0, 1, 3, 5, 6, 7)."""
    if not website_uri or not website_uri.strip():
        return ClassificacaoPresenca(
            nivel=0,
            evidencia="Não possui site cadastrado no perfil da empresa.",
            score_base=SCORE_BASE_PRESENCA[0],
        )

    url_limpa = website_uri.strip()
    if _PADRAO_GOOGLE_SITE.search(url_limpa):
        return ClassificacaoPresenca(
            nivel=1,
            evidencia=(
                "Utiliza o construtor gratuito descontinuado do Google (business.site)."
            ),
            score_base=SCORE_BASE_PRESENCA[1],
        )

    if _PADRAO_WHATSAPP.search(url_limpa):
        return ClassificacaoPresenca(
            nivel=3,
            evidencia=(
                "O link no perfil direciona diretamente para o WhatsApp "
                "no lugar de um site."
            ),
            score_base=SCORE_BASE_PRESENCA[3],
        )

    parsed = urlparse(url_limpa if "://" in url_limpa else f"http://{url_limpa}")
    netloc = parsed.netloc.lower().removeprefix("www.")
    dominio = dominio_registravel(url_limpa)

    # Verifica se o host completo ou o domínio registrável é social/agregador
    if (dominio and dominio in SOCIAL) or any(s in netloc for s in SOCIAL):
        return ClassificacaoPresenca(
            nivel=5,
            evidencia=(
                f"Utiliza perfil em rede social ou agregador ({dominio or netloc}) "
                "no lugar de site próprio."
            ),
            score_base=SCORE_BASE_PRESENCA[5],
        )

    # Construtores gratuitos
    if (dominio and dominio in CONSTRUTOR_GRATIS) or any(
        c in netloc for c in CONSTRUTOR_GRATIS
    ):
        return ClassificacaoPresenca(
            nivel=6,
            evidencia=(
                "Utiliza subdomínio gratuito de construtor de sites "
                f"({dominio or netloc})."
            ),
            score_base=SCORE_BASE_PRESENCA[6],
        )

    # Marketplaces de terceiros
    if (dominio and dominio in MARKETPLACE) or any(m in netloc for m in MARKETPLACE):
        return ClassificacaoPresenca(
            nivel=7,
            evidencia=(
                "O link direciona para página em marketplace de terceiros "
                f"({dominio or netloc})."
            ),
            score_base=SCORE_BASE_PRESENCA[7],
        )

    return None


def classificar_site_proprio(
    *,
    status_code: int | None,
    has_ssl: bool,
    has_mobile_viewport: bool,
    copyright_year: int | None,
    is_parked_or_empty: bool = False,
    erro_conexao: str | None = None,
) -> ClassificacaoPresenca:
    """Classifica o diagnóstico técnico de um domínio próprio (níveis 2, 4, 8 ou 9)."""
    # Nível 2: Erro HTTP ou não resolve
    if erro_conexao is not None or status_code is None or status_code >= 400:
        detalhe = (
            f"erro HTTP {status_code}"
            if status_code
            else (erro_conexao or "fora do ar")
        )
        return ClassificacaoPresenca(
            nivel=2,
            evidencia=(
                f"O link do site no perfil do Google está fora do ar ({detalhe})."
            ),
            score_base=SCORE_BASE_PRESENCA[2],
        )

    # Nível 4: Domínio estacionado ou página quase vazia
    if is_parked_or_empty:
        return ClassificacaoPresenca(
            nivel=4,
            evidencia=(
                "O domínio está registrado mas sem conteúdo funcional "
                "(página em branco ou estacionada)."
            ),
            score_base=SCORE_BASE_PRESENCA[4],
        )

    # Nível 8: Site próprio fraco (sem mobile, sem HTTPS ou copyright antigo <= 2020)
    problemas: list[str] = []
    if not has_mobile_viewport:
        problemas.append(
            "não é adaptado para visualização em celulares (sem viewport mobile)"
        )
    if not has_ssl:
        problemas.append("não possui certificado de segurança SSL (HTTP inseguro)")
    if copyright_year is not None and copyright_year <= 2020:
        problemas.append(f"está desatualizado há anos (copyright de {copyright_year})")

    if problemas:
        evidencia = "Site próprio com problemas técnicos: " + "; ".join(problemas) + "."
        return ClassificacaoPresenca(
            nivel=8,
            evidencia=evidencia,
            score_base=SCORE_BASE_PRESENCA[8],
        )

    # Nível 9: Site próprio saudável
    return ClassificacaoPresenca(
        nivel=9,
        evidencia="Site próprio funcional, seguro e responsivo para celulares.",
        score_base=SCORE_BASE_PRESENCA[9],
    )
