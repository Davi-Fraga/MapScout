"""Normalização de telefone brasileiro para E.164."""

from __future__ import annotations

import re

TIPO_MOVEL = "movel"
TIPO_FIXO = "fixo"
TIPO_ESPECIAL = "especial"

# Números não-geográficos: compartilhados entre filiais, logo não identificam
# uma unidade. Ficam registrados, mas a dedupe por telefone os ignora.
PREFIXOS_ESPECIAIS = ("0800", "0300", "0500", "4003", "4004", "4020")

_RAMAL = re.compile(r"\b(ramal|ramais|r\.)\b.*$", re.IGNORECASE)
_NAO_DIGITO = re.compile(r"\D")

DDD_MINIMO = 11
DDD_MAXIMO = 99
PRIMEIRO_DIGITO_FIXO = frozenset("2345")


def normalizar_telefone(bruto: str | None) -> tuple[str | None, str | None]:
    """Converte um telefone brasileiro em (E.164, tipo), ou (None, None) se inválido."""
    if not bruto:
        return (None, None)

    digitos = _NAO_DIGITO.sub("", _RAMAL.sub("", bruto))
    if not digitos:
        return (None, None)

    if digitos.startswith("55") and len(digitos) in {12, 13}:
        digitos = digitos[2:]

    for prefixo in PREFIXOS_ESPECIAIS:
        if digitos.startswith(prefixo):
            return (f"+55{digitos.lstrip('0')}", TIPO_ESPECIAL)

    digitos = digitos.removeprefix("0")

    if len(digitos) not in {10, 11}:
        return (None, None)
    if not DDD_MINIMO <= int(digitos[:2]) <= DDD_MAXIMO:
        return (None, None)

    if len(digitos) == 11:
        if digitos[2] != "9":
            return (None, None)
        return (f"+55{digitos}", TIPO_MOVEL)

    if digitos[2] not in PRIMEIRO_DIGITO_FIXO:
        return (None, None)
    return (f"+55{digitos}", TIPO_FIXO)
