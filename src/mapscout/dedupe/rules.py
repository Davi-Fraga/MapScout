"""Regras de deduplicação: sempre (decisão, confiança, motivo), nunca um booleano."""

from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
from enum import StrEnum

from mapscout.db.models import Place
from mapscout.dominios import e_compartilhado
from mapscout.normalize.address import extrair_cep, normalizar_endereco
from mapscout.normalize.domain import dominio_registravel
from mapscout.normalize.name import normalizar_nome
from mapscout.normalize.phone import TIPO_ESPECIAL, normalizar_telefone

LIMIAR_NOME = 0.88
LIMIAR_ENDERECO = 0.85


class Acao(StrEnum):
    """O que fazer com o par de registros."""

    FUNDE = "funde"
    REVISAR = "revisar"
    NAO_FUNDE = "nao_funde"


class Confianca(StrEnum):
    """Quanta certeza há por trás da ação."""

    CERTEZA = "certeza"
    ALTA = "alta"
    MEDIA = "media"
    NENHUMA = "nenhuma"


@dataclass(frozen=True)
class Decisao:
    """Resultado auditável de uma comparação entre dois registros."""

    acao: Acao
    confianca: Confianca
    motivo: str


def similaridade(a: str, b: str) -> float:
    """Razão de similaridade entre dois textos já normalizados, de 0 a 1."""
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def _mesma_cidade(a: Place, b: Place) -> bool:
    """Diz se os dois registros declaram a mesma cidade."""
    if not a.cidade or not b.cidade:
        return False
    return normalizar_nome(a.cidade) == normalizar_nome(b.cidade)


def _cidade_conhecida_e_diferente(a: Place, b: Place) -> bool:
    """Diz se ambas as cidades são conhecidas e são diferentes."""
    if not a.cidade or not b.cidade:
        return False
    return normalizar_nome(a.cidade) != normalizar_nome(b.cidade)


def _enderecos_batem(a: Place, b: Place) -> bool:
    """Compara endereços por CEP quando houver, senão por similaridade textual."""
    cep_a = extrair_cep(a.formatted_address)
    cep_b = extrair_cep(b.formatted_address)
    if cep_a and cep_b:
        return cep_a == cep_b
    similar = similaridade(
        normalizar_endereco(a.formatted_address),
        normalizar_endereco(b.formatted_address),
    )
    return similar >= LIMIAR_ENDERECO


def comparar(a: Place, b: Place) -> Decisao:
    """Compara dois registros e devolve ação, confiança e motivo legível."""
    if a.place_id and a.place_id == b.place_id:
        return Decisao(
            Acao.FUNDE,
            Confianca.CERTEZA,
            f"mesmo place_id do Google ({a.place_id})",
        )

    nome_a = normalizar_nome(a.display_name)
    nome_b = normalizar_nome(b.display_name)

    # Guarda de filial: vem antes de domínio e telefone porque uma rede costuma
    # compartilhar site e 0800 entre unidades de cidades diferentes.
    if nome_a and nome_a == nome_b and _cidade_conhecida_e_diferente(a, b):
        return Decisao(
            Acao.NAO_FUNDE,
            Confianca.NENHUMA,
            f"mesmo nome em cidades diferentes ({a.cidade} e {b.cidade}): "
            "provável filial",
        )

    dominio_a = dominio_registravel(a.website_uri)
    dominio_b = dominio_registravel(b.website_uri)
    if dominio_a and dominio_a == dominio_b:
        if e_compartilhado(dominio_a):
            pass  # domínio de terceiro não identifica a empresa; segue a análise
        else:
            return Decisao(
                Acao.FUNDE,
                Confianca.ALTA,
                f"mesmo domínio próprio ({dominio_a})",
            )

    telefone_a, tipo_a = normalizar_telefone(a.national_phone_number)
    telefone_b, tipo_b = normalizar_telefone(b.national_phone_number)
    if (
        telefone_a
        and telefone_a == telefone_b
        and TIPO_ESPECIAL not in {tipo_a, tipo_b}
        and _mesma_cidade(a, b)
    ):
        return Decisao(
            Acao.FUNDE,
            Confianca.MEDIA,
            f"mesmo telefone {telefone_a} na mesma cidade ({a.cidade})",
        )

    parecenca = similaridade(nome_a, nome_b)
    if parecenca >= LIMIAR_NOME and _enderecos_batem(a, b):
        return Decisao(
            Acao.REVISAR,
            Confianca.MEDIA,
            f"nomes {parecenca:.0%} parecidos e endereços compatíveis: "
            "confira antes de fundir",
        )

    return Decisao(
        Acao.NAO_FUNDE,
        Confianca.NENHUMA,
        "nenhum identificador em comum",
    )
