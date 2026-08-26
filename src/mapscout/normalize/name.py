"""Normalização de nome fantasia e razão social."""

from __future__ import annotations

import re
import unicodedata

SUFIXOS_SOCIETARIOS = frozenset({"ltda", "me", "epp", "eireli", "sa", "s a", "s/a"})

_SA_COM_BARRA = re.compile(r"\bs\s*/\s*a\b", re.IGNORECASE)
_NAO_ALFANUMERICO = re.compile(r"[^a-z0-9]+")
_ESPACOS = re.compile(r"\s+")


def sem_acento(texto: str) -> str:
    """Remove acentos preservando as letras de base."""
    decomposto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in decomposto if not unicodedata.combining(c))


def normalizar_nome(bruto: str | None) -> str:
    """Minúsculas, sem acento nem pontuação, sem sufixo societário no fim."""
    if not bruto:
        return ""

    texto = sem_acento(_SA_COM_BARRA.sub(" sa ", bruto)).lower()
    texto = _NAO_ALFANUMERICO.sub(" ", texto)
    partes = _ESPACOS.sub(" ", texto).strip().split()

    while partes and partes[-1] in SUFIXOS_SOCIETARIOS:
        partes.pop()

    return " ".join(partes)
