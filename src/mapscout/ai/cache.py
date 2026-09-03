"""Cache persistente de chamadas de IA por place_id e hash de entrada."""

from __future__ import annotations

import hashlib
import json

from sqlmodel import Session, col, select

from mapscout.ai.schemas import AbordagemLead
from mapscout.db.models import AiCache, Place


def calcular_hash_place(place: Place) -> str:
    """Calcula o hash SHA-256 dos campos de entrada do lead."""
    dados = (
        f"{place.place_id}|{place.display_name}|{place.website_uri}|"
        f"{place.presence_level}|{place.presence_evidence}|{place.rating}|"
        f"{place.user_rating_count}|{place.cidade}"
    )
    return hashlib.sha256(dados.encode("utf-8")).hexdigest()


def obter_abordagem_cache(
    sessao: Session, place_id: str, hash_entrada: str
) -> AbordagemLead | None:
    """Recupera a abordagem em cache para o par (place_id, hash) se existir."""
    consulta = select(AiCache).where(
        col(AiCache.place_id) == place_id,
        col(AiCache.hash_entrada) == hash_entrada,
    )
    registro = sessao.exec(consulta).first()
    if registro is None:
        return None

    try:
        dados = json.loads(registro.resposta_json)
        return AbordagemLead(**dados)
    except Exception:
        return None


def salvar_abordagem_cache(
    sessao: Session,
    place_id: str,
    hash_entrada: str,
    abordagem: AbordagemLead,
) -> None:
    """Salva a abordagem no banco de dados para evitar recomputação."""
    linha = AiCache(
        place_id=place_id,
        hash_entrada=hash_entrada,
        resposta_json=abordagem.model_dump_json(),
    )
    sessao.add(linha)
    sessao.commit()
