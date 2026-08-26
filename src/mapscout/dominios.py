"""Listas editáveis de domínios que não pertencem à empresa em si."""

from __future__ import annotations

# Nível 5 do glossário: perfil social ou agregador de links.
SOCIAL = frozenset(
    {
        "instagram.com",
        "facebook.com",
        "fb.me",
        "linktr.ee",
        "beacons.ai",
        "bio.link",
        "campsite.bio",
        "tiktok.com",
        "youtube.com",
        "x.com",
        "twitter.com",
    }
)

# Nível 6: subdomínio gratuito de construtor de site.
CONSTRUTOR_GRATIS = frozenset(
    {
        "wixsite.com",
        "lovable.app",
        "netlify.app",
        "vercel.app",
        "site123.me",
        "webnode.page",
        "weebly.com",
        "blogspot.com",
        "wordpress.com",
        "github.io",
        "glitch.me",
        "replit.app",
    }
)

# Nível 7: página em marketplace de terceiro.
MARKETPLACE = frozenset(
    {
        "doctoralia.com.br",
        "mechameaqui.com.br",
        "ifood.com.br",
        "booking.com",
        "tripadvisor.com",
        "olx.com.br",
        "elo7.com.br",
        "mercadolivre.com.br",
        "getninjas.com.br",
        "gympass.com",
        "zenklub.com.br",
        "airbnb.com",
        "rappi.com.br",
    }
)

# Domínios compartilhados por empresas distintas: nunca fundem dois registros.
COMPARTILHADOS = SOCIAL | CONSTRUTOR_GRATIS | MARKETPLACE


def e_compartilhado(dominio: str | None) -> bool:
    """Diz se o domínio é de terceiro e portanto não identifica uma empresa."""
    return dominio is not None and dominio.lower() in COMPARTILHADOS
