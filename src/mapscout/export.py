"""Exportação de leads qualificados respeitando a blocklist de opt-out."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any
from urllib.parse import quote

from sqlmodel import Session, col, select

from mapscout.ai.client import gerar_rascunho_abordagem
from mapscout.db.models import Place
from mapscout.db.repo import esta_bloqueado
from mapscout.normalize.phone import normalizar_telefone
from mapscout.scoring import calcular_score_lead


def formatar_link_whatsapp(telefone: str | None, mensagem: str) -> str:
    """Monta link do WhatsApp no formato wa.me com mensagem pré-carregada."""
    if not telefone:
        return ""
    e164, _ = normalizar_telefone(telefone)
    if not e164:
        return ""
    numero_limpo = e164.removeprefix("+")
    texto_codificado = quote(mensagem)
    return f"https://wa.me/{numero_limpo}?text={texto_codificado}"


def exportar_leads_qualificados(
    sessao: Session,
    caminho_saida: str | Path,
    *,
    min_score: float = 0.0,
    categoria: str | None = None,
    cidade: str | None = None,
    formato: str = "csv",
) -> int:
    """Exporta leads qualificados respeitando estritamente a blocklist de opt-out."""
    consulta = select(Place).order_by(col(Place.coletado_em).desc())
    if cidade:
        consulta = consulta.where(col(Place.cidade) == cidade)

    todos = list(sessao.exec(consulta).all())
    exportaveis: list[dict[str, Any]] = []

    for place in todos:
        # 1. Conformidade LGPD: checa a blocklist
        if esta_bloqueado(sessao, place) is not None:
            continue

        # 2. Score de oportunidade
        score = place.score or calcular_score_lead(place, categoria=categoria)
        if score < min_score:
            continue

        # 3. Rascunho da abordagem
        abordagem = gerar_rascunho_abordagem(place, sessao=sessao)
        link_whats = formatar_link_whatsapp(
            place.national_phone_number, abordagem.mensagem_whatsapp
        )

        registro = {
            "Nome": place.display_name,
            "Cidade": place.cidade or "",
            "Telefone": place.national_phone_number or "",
            "Nivel_Presenca": place.presence_level
            if place.presence_level is not None
            else "",
            "Diagnostico": place.presence_evidence or "",
            "Score": score,
            "Site": place.website_uri or "",
            "Avaliacao": place.rating or "",
            "Qtd_Avaliacoes": place.user_rating_count or 0,
            "Emails": place.emails or "",
            "Instagram": place.instagram_url or "",
            "Gancho_Comercial": abordagem.gancho_comercial,
            "Abordagem_WhatsApp": abordagem.mensagem_whatsapp,
            "Link_WhatsApp_Direto": link_whats,
        }
        exportaveis.append(registro)

    # Ordena pelo maior score (maior oportunidade primeiro)
    exportaveis.sort(key=lambda r: float(r["Score"]), reverse=True)

    destino = Path(caminho_saida)
    destino.parent.mkdir(parents=True, exist_ok=True)

    if formato.lower() == "json":
        with open(destino, "w", encoding="utf-8") as f:
            json.dump(exportaveis, f, ensure_ascii=False, indent=2)
    else:
        if not exportaveis:
            campos = [
                "Nome",
                "Cidade",
                "Telefone",
                "Nivel_Presenca",
                "Diagnostico",
                "Score",
                "Site",
                "Avaliacao",
                "Qtd_Avaliacoes",
                "Emails",
                "Instagram",
                "Gancho_Comercial",
                "Abordagem_WhatsApp",
                "Link_WhatsApp_Direto",
            ]
        else:
            campos = list(exportaveis[0].keys())

        with open(destino, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=campos, delimiter=";")
            writer.writeheader()
            for linha in exportaveis:
                writer.writerow(linha)

    return len(exportaveis)
