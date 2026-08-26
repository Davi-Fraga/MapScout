"""Normalização de endereço e extração de CEP."""

from __future__ import annotations

import re

from mapscout.normalize.name import sem_acento

_CEP = re.compile(r"\b(\d{5})-?(\d{3})\b")
_NAO_ALFANUMERICO = re.compile(r"[^a-z0-9]+")
_ESPACOS = re.compile(r"\s+")

ABREVIACOES = {
    "r": "rua",
    "av": "avenida",
    "avn": "avenida",
    "al": "alameda",
    "tv": "travessa",
    "pc": "praca",
    "rod": "rodovia",
    "estr": "estrada",
    "sl": "sala",
    "cj": "conjunto",
    "ed": "edificio",
    "apto": "apartamento",
    "ap": "apartamento",
    "bl": "bloco",
    "n": "numero",
    "no": "numero",
    "jd": "jardim",
    "pq": "parque",
    "vl": "vila",
}


def extrair_cep(bruto: str | None) -> str | None:
    """Extrai o CEP no formato 00000-000, ou None se não houver."""
    if not bruto:
        return None
    achado = _CEP.search(bruto)
    if achado is None:
        return None
    return f"{achado.group(1)}-{achado.group(2)}"


def normalizar_endereco(bruto: str | None) -> str:
    """Minúsculas, sem acento nem pontuação, com abreviações expandidas."""
    if not bruto:
        return ""

    texto = _NAO_ALFANUMERICO.sub(" ", sem_acento(bruto).lower())
    partes = _ESPACOS.sub(" ", texto).strip().split()
    return " ".join(ABREVIACOES.get(parte, parte) for parte in partes)
