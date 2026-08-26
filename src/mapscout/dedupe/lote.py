"""Aplica as regras de dedupe sobre a base inteira, mantendo a trilha de auditoria."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field

from mapscout.db.models import Place
from mapscout.dedupe.rules import Acao, Decisao, comparar
from mapscout.dominios import e_compartilhado
from mapscout.normalize.address import extrair_cep
from mapscout.normalize.domain import dominio_registravel
from mapscout.normalize.name import normalizar_nome
from mapscout.normalize.phone import TIPO_ESPECIAL, normalizar_telefone


@dataclass(frozen=True)
class Fusao:
    """Um par que a dedupe decidiu unir ou marcar, com o porquê."""

    mantido: str
    duplicado: str
    nome_mantido: str
    nome_duplicado: str
    decisao: Decisao


@dataclass
class ResultadoDedupe:
    """Resumo do dedupe sobre a base, com os pares auditáveis."""

    total_bruto: int = 0
    total_unico: int = 0
    fusoes: list[Fusao] = field(default_factory=list)
    revisar: list[Fusao] = field(default_factory=list)


def chaves_de_fusao(place: Place) -> list[tuple[str, str]]:
    """Chaves que, se colidirem, tornam dois registros candidatos a fusão."""
    chaves: list[tuple[str, str]] = []

    dominio = dominio_registravel(place.website_uri)
    if dominio and not e_compartilhado(dominio):
        chaves.append(("dominio", dominio))

    e164, tipo = normalizar_telefone(place.national_phone_number)
    if e164 and tipo != TIPO_ESPECIAL and place.cidade:
        chaves.append(("telefone", f"{e164}|{normalizar_nome(place.cidade)}"))

    return chaves


def _fusao(mantido: Place, duplicado: Place, decisao: Decisao) -> Fusao:
    return Fusao(
        mantido=mantido.place_id,
        duplicado=duplicado.place_id,
        nome_mantido=mantido.display_name,
        nome_duplicado=duplicado.display_name,
        decisao=decisao,
    )


def deduplicar(places: Sequence[Place]) -> ResultadoDedupe:
    """Agrupa duplicatas por place_id, domínio próprio e telefone + cidade."""
    resultado = ResultadoDedupe(total_bruto=len(places))
    representante_de_chave: dict[tuple[str, str], Place] = {}
    vistos_por_id: dict[str, Place] = {}
    unicos: list[Place] = []

    for place in places:
        anterior = vistos_por_id.get(place.place_id)
        if anterior is not None:
            resultado.fusoes.append(_fusao(anterior, place, comparar(anterior, place)))
            continue

        fundido = False
        for chave in chaves_de_fusao(place):
            candidato = representante_de_chave.get(chave)
            if candidato is None:
                continue
            decisao = comparar(candidato, place)
            if decisao.acao is Acao.FUNDE:
                resultado.fusoes.append(_fusao(candidato, place, decisao))
                fundido = True
                break

        if fundido:
            continue

        vistos_por_id[place.place_id] = place
        unicos.append(place)
        for chave in chaves_de_fusao(place):
            representante_de_chave.setdefault(chave, place)

    resultado.total_unico = len(unicos)
    resultado.revisar = _pares_para_revisar(unicos)
    return resultado


def _pares_para_revisar(places: Sequence[Place]) -> list[Fusao]:
    """Compara apenas registros no mesmo CEP: barato e é onde o risco mora."""
    por_cep: dict[str, list[Place]] = defaultdict(list)
    for place in places:
        cep = extrair_cep(place.formatted_address)
        if cep:
            por_cep[cep].append(place)

    marcados: list[Fusao] = []
    for grupo in por_cep.values():
        for i, primeiro in enumerate(grupo):
            for segundo in grupo[i + 1 :]:
                decisao = comparar(primeiro, segundo)
                if decisao.acao is Acao.REVISAR:
                    marcados.append(_fusao(primeiro, segundo, decisao))
    return marcados
