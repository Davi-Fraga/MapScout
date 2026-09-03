import csv
import json
from pathlib import Path

from sqlmodel import Session

from mapscout.db.models import Place
from mapscout.db.repo import adicionar_blocklist, upsert_place
from mapscout.export import exportar_leads_qualificados, formatar_link_whatsapp


def test_formatar_link_whatsapp() -> None:
    link = formatar_link_whatsapp("(19) 99999-8888", "Olá, tudo bem?")
    assert "https://wa.me/5519999998888?text=" in link
    assert "Ol%C3%A1" in link


def test_exportar_leads_respeita_blocklist_e_cria_csv(
    sessao: Session, tmp_path: Path
) -> None:
    p1 = Place(
        place_id="exp1",
        display_name="Empresa A",
        cidade="Campinas",
        national_phone_number="(19) 99999-1111",
        presence_level=0,
        score=95.0,
    )
    p2_bloqueado = Place(
        place_id="exp2",
        display_name="Empresa B Bloqueada",
        cidade="Campinas",
        national_phone_number="(19) 99999-2222",
        presence_level=0,
        score=95.0,
    )
    upsert_place(sessao, p1)
    upsert_place(sessao, p2_bloqueado)
    sessao.commit()

    adicionar_blocklist(
        sessao,
        place_id="exp2",
        telefone="(19) 99999-2222",
        dominio=None,
        motivo="Opt-out solicitado",
    )
    sessao.commit()

    caminho_csv = tmp_path / "leads.csv"
    total = exportar_leads_qualificados(sessao, caminho_csv, formato="csv")

    assert total == 1
    assert caminho_csv.exists()

    with open(caminho_csv, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=";")
        linhas = list(reader)
        assert len(linhas) == 1
        assert linhas[0]["Nome"] == "Empresa A"
        assert "wa.me" in linhas[0]["Link_WhatsApp_Direto"]


def test_exportar_leads_json(sessao: Session, tmp_path: Path) -> None:
    p = Place(
        place_id="exp3",
        display_name="Empresa C",
        presence_level=2,
        score=90.0,
    )
    upsert_place(sessao, p)
    sessao.commit()

    caminho_json = tmp_path / "leads.json"
    total = exportar_leads_qualificados(sessao, caminho_json, formato="json")

    assert total == 1
    with open(caminho_json, encoding="utf-8") as f:
        dados = json.load(f)
        assert len(dados) == 1
        assert dados[0]["Nome"] == "Empresa C"
