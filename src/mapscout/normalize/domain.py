"""Extração do domínio registrável de uma URL."""

from __future__ import annotations

from tldextract import TLDExtract

# suffix_list_urls=() força o uso do snapshot embutido: nenhuma chamada de rede.
_extrator = TLDExtract(suffix_list_urls=())


def dominio_registravel(url: str | None) -> str | None:
    """Devolve o domínio registrável da URL, sem protocolo, www, porta nem query."""
    if not url or not url.strip():
        return None

    bruto = url.strip()
    if "://" not in bruto:
        bruto = f"http://{bruto}"

    dominio = _extrator(bruto).top_domain_under_public_suffix
    return dominio.lower() or None
