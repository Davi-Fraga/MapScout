"""Extração de sinais, contatos e tecnologias a partir do HTML via selectolax."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import urlparse

from selectolax.lexbor import LexborHTMLParser

_PADRAO_COPYRIGHT = re.compile(
    r"(?:©|&copy;|copyright)\s*(?:20\d{2}\s*[-/]\s*)?(20\d{2})",
    re.IGNORECASE,
)

_PADRAO_EMAIL = re.compile(
    r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
)

_PADRAO_WHATSAPP_LINK = re.compile(
    r"(?:https?://)?(?:wa\.me|api\.whatsapp\.com/send|chat\.whatsapp\.com)/?[^\s\"'>]*",
    re.IGNORECASE,
)

_TERMOS_PARKED = frozenset(
    {
        "este domínio está à venda",
        "domain for sale",
        "buy this domain",
        "em construção",
        "under construction",
        "página em construção",
        "sedo parking",
        "godaddy.com/park",
        "registrobr - domínio não configurado",
    }
)

_EXTENSOES_IGNORADAS_EMAIL = frozenset(
    {
        "png",
        "jpg",
        "jpeg",
        "gif",
        "webp",
        "svg",
        "js",
        "css",
        "woff",
        "woff2",
        "ttf",
    }
)


@dataclass(frozen=True)
class SinaisPagina:
    """Sinais e metadados extraídos do HTML de uma página web."""

    has_mobile_viewport: bool
    copyright_year: int | None
    emails: list[str] = field(default_factory=list)
    instagram_url: str | None = None
    facebook_url: str | None = None
    whatsapp_url: str | None = None
    tech_detected: list[str] = field(default_factory=list)
    is_parked_or_empty: bool = False


def extrair_emails_do_texto(texto: str) -> list[str]:
    """Extrai e valida e-mails únicos a partir de uma string de texto."""
    encontrados = _PADRAO_EMAIL.findall(texto)
    emails_validos: set[str] = set()
    for email in encontrados:
        email_limpo = email.strip().lower().rstrip(".,;:")
        partes = email_limpo.split("@")
        if len(partes) != 2:
            continue
        extensao = email_limpo.split(".")[-1]
        if extensao in _EXTENSOES_IGNORADAS_EMAIL:
            continue
        # Ignora exemplos comuns ou bibliotecas
        if any(
            ign in email_limpo
            for ign in ("example.com", "sentry.io", "wix.com", "placeholder")
        ):
            continue
        emails_validos.add(email_limpo)
    return sorted(emails_validos)


def extrair_sinais_html(html: str, url_origem: str = "") -> SinaisPagina:
    """Processa o conteúdo HTML e extrai sinais técnicos e contatos."""
    if not html or not html.strip():
        return SinaisPagina(
            has_mobile_viewport=False,
            copyright_year=None,
            is_parked_or_empty=True,
        )

    parser = LexborHTMLParser(html)

    # 1. Viewport mobile
    tem_viewport = False
    for meta in parser.css('meta[name="viewport"], meta[name="VIEWPORT"]'):
        content = meta.attributes.get("content") or ""
        if "width=" in content.lower():
            tem_viewport = True
            break

    # 2. Texto bruto visível
    body_node = parser.body
    texto_visivel = body_node.text(separator=" ", strip=True) if body_node else ""
    texto_lower = texto_visivel.lower()

    # 3. Detecção de domínio estacionado ou página quase sem conteúdo
    pouco_conteudo = len(texto_visivel.strip()) < 20
    termo_parked_encontrado = any(termo in texto_lower for termo in _TERMOS_PARKED)
    is_parked_or_empty = pouco_conteudo or termo_parked_encontrado

    # 4. Ano de copyright
    copyright_year: int | None = None
    matches_ano = _PADRAO_COPYRIGHT.findall(texto_visivel)
    if matches_ano:
        try:
            # Pega o maior ano encontrado para representar a última atualização
            anos = [int(a) for a in matches_ano if 1995 <= int(a) <= 2030]
            if anos:
                copyright_year = max(anos)
        except ValueError:
            pass

    # 5. Redes sociais, WhatsApp e Links Mailto
    emails_set: set[str] = set()
    instagram_url: str | None = None
    facebook_url: str | None = None
    whatsapp_url: str | None = None

    for link in parser.css("a[href]"):
        href_raw = link.attributes.get("href")
        if not href_raw:
            continue
        href = href_raw.strip()
        if not href:
            continue

        href_lower = href.lower()

        # Mailto
        if href_lower.startswith("mailto:"):
            email_candidato = href[7:].split("?")[0].strip()
            for e in extrair_emails_do_texto(email_candidato):
                emails_set.add(e)
            continue

        # WhatsApp
        if _PADRAO_WHATSAPP_LINK.search(href):
            if not whatsapp_url:
                whatsapp_url = href
            continue

        # Redes sociais
        if "instagram.com/" in href_lower and not instagram_url:
            parsed = urlparse(href)
            caminho = parsed.path.strip("/")
            if caminho and not any(
                caminho.startswith(ign)
                for ign in ("p/", "reel/", "explore/", "stories/")
            ):
                instagram_url = href

        if "facebook.com/" in href_lower and not facebook_url:
            parsed = urlparse(href)
            caminho = parsed.path.strip("/")
            if caminho and not any(
                caminho.startswith(ign) for ign in ("sharer", "share", "events")
            ):
                facebook_url = href

    # E-mails no texto visível
    for email in extrair_emails_do_texto(texto_visivel):
        emails_set.add(email)

    # 6. Tecnologias detectadas
    techs: list[str] = []
    html_lower = html.lower()
    if "wp-content" in html_lower or "wp-includes" in html_lower:
        techs.append("WordPress")
    if "woocommerce" in html_lower:
        techs.append("WooCommerce")
    if "wix.com" in html_lower or "_wix_" in html_lower:
        techs.append("Wix")
    if "shopify" in html_lower or "cdn.shopify.com" in html_lower:
        techs.append("Shopify")
    if "elementor" in html_lower:
        techs.append("Elementor")
    if "rdstation" in html_lower:
        techs.append("RD Station")

    return SinaisPagina(
        has_mobile_viewport=tem_viewport,
        copyright_year=copyright_year,
        emails=sorted(emails_set),
        instagram_url=instagram_url,
        facebook_url=facebook_url,
        whatsapp_url=whatsapp_url,
        tech_detected=techs,
        is_parked_or_empty=is_parked_or_empty,
    )
