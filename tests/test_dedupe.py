"""Dedupe multinível: fusões corretas e, sobretudo, as que não podem acontecer."""

from __future__ import annotations

from sqlmodel import Session

from mapscout.db.models import Place
from mapscout.db.repo import adicionar_blocklist, esta_bloqueado
from mapscout.dedupe.rules import Acao, Confianca, comparar

CEP_JAGUARA = "Rua Barão de Jaguara, 655 - Centro, Campinas - SP, 13015-001"
CEP_EMILIO = "R. Dr. Emílio Ribas, 805 - Sl 61 - Cambuí, Campinas - SP, 13025-141"


def _place(
    place_id: str,
    nome: str,
    *,
    cidade: str | None = "Campinas",
    telefone: str | None = None,
    site: str | None = None,
    endereco: str | None = None,
) -> Place:
    return Place(
        place_id=place_id,
        display_name=nome,
        cidade=cidade,
        national_phone_number=telefone,
        website_uri=site,
        formatted_address=endereco,
    )


# --------------------------- fusões que devem ocorrer ---------------------------


def test_mesmo_place_id_funde_com_certeza() -> None:
    a = _place("ChIJ3Ssrf0rPyJQR", "Dra. Beatriz Toriani, Dentista")
    b = _place("ChIJ3Ssrf0rPyJQR", "Beatriz Toriani Odontologia", cidade="Valinhos")

    decisao = comparar(a, b)

    assert decisao.acao is Acao.FUNDE
    assert decisao.confianca is Confianca.CERTEZA
    assert "place_id" in decisao.motivo


def test_mesmo_dominio_proprio_funde_com_alta_confianca() -> None:
    a = _place("A", "Oral Clin", site="https://www.oralclincampinas.com.br/")
    b = _place("B", "Oral Clin Campinas", site="http://oralclincampinas.com.br/contato")

    decisao = comparar(a, b)

    assert decisao.acao is Acao.FUNDE
    assert decisao.confianca is Confianca.ALTA
    assert "oralclincampinas.com.br" in decisao.motivo


def test_mesmo_telefone_na_mesma_cidade_funde() -> None:
    a = _place("A", "Consultório Odontológico", telefone="(19) 3233-4558")
    b = _place("B", "Clínica Dentária Centro", telefone="+55 19 3233-4558")

    decisao = comparar(a, b)

    assert decisao.acao is Acao.FUNDE
    assert decisao.confianca is Confianca.MEDIA
    assert "+551932334558" in decisao.motivo


def test_nome_parecido_e_mesmo_cep_apenas_marca_para_revisao() -> None:
    a = _place("A", "Odontologia Pazotto", endereco=CEP_JAGUARA)
    b = _place("B", "Odontologia Pazotto Ltda", endereco=CEP_JAGUARA)

    decisao = comparar(a, b)

    assert decisao.acao is Acao.REVISAR
    assert decisao.confianca is Confianca.MEDIA
    assert "confira antes de fundir" in decisao.motivo


# ----------------------- os negativos: nunca podem fundir -----------------------


def test_filiais_da_mesma_rede_em_cidades_diferentes_nao_fundem() -> None:
    a = _place("A", "Uniodonto", cidade="Campinas", endereco=CEP_JAGUARA)
    b = _place("B", "Uniodonto", cidade="Piracicaba", endereco=CEP_JAGUARA)

    decisao = comparar(a, b)

    assert decisao.acao is Acao.NAO_FUNDE
    assert "filial" in decisao.motivo


def test_filiais_com_o_mesmo_site_ainda_assim_nao_fundem() -> None:
    """A guarda de filial vem antes da regra de domínio, de propósito."""
    a = _place("A", "Uniodonto", cidade="Campinas", site="https://uniodonto.com.br/")
    b = _place("B", "Uniodonto", cidade="Limeira", site="https://uniodonto.com.br/")

    decisao = comparar(a, b)

    assert decisao.acao is Acao.NAO_FUNDE
    assert "filial" in decisao.motivo


def test_mesmo_0800_em_cidades_diferentes_nao_funde() -> None:
    a = _place("A", "Rede Odonto Norte", cidade="Campinas", telefone="0800 160 5555")
    b = _place("B", "Rede Odonto Sul", cidade="Santos", telefone="0800 160 5555")

    decisao = comparar(a, b)

    assert decisao.acao is Acao.NAO_FUNDE


def test_mesmo_0800_na_mesma_cidade_tambem_nao_funde() -> None:
    """0800 é compartilhado entre unidades: não identifica um consultório."""
    a = _place("A", "Rede Odonto Centro", telefone="0800 160 5555")
    b = _place("B", "Rede Odonto Cambuí", telefone="0800 160 5555")

    decisao = comparar(a, b)

    assert decisao.acao is Acao.NAO_FUNDE


def test_consultorios_no_mesmo_predio_com_telefones_diferentes_nao_fundem() -> None:
    a = _place(
        "A", "Dra. Mirian Bustillo", telefone="(19) 99214-1001", endereco=CEP_EMILIO
    )
    b = _place(
        "B", "Dr. Pedro Afonso Ferreira", telefone="(19) 3231-0784", endereco=CEP_EMILIO
    )

    decisao = comparar(a, b)

    assert decisao.acao is Acao.NAO_FUNDE
    assert decisao.confianca is Confianca.NENHUMA


def test_dois_perfis_no_mesmo_marketplace_nao_fundem() -> None:
    """Dois dentistas distintos podem ter perfil na Doctoralia."""
    a = _place(
        "A",
        "Dra. Beatriz Toriani",
        site="https://www.doctoralia.com.br/beatriz-toriani/dentista/campinas",
        endereco=CEP_JAGUARA,
    )
    b = _place(
        "B",
        "Dr. Guilherme Mancini",
        site="https://www.doctoralia.com.br/guilherme-mancini/dentista/campinas",
        endereco=CEP_EMILIO,
    )

    decisao = comparar(a, b)

    assert decisao.acao is Acao.NAO_FUNDE


def test_dois_sites_no_mesmo_construtor_gratis_nao_fundem() -> None:
    """redesags.wixsite.com e outro.wixsite.com têm o mesmo domínio registrável."""
    a = _place("A", "Dra Thainá Souza", site="https://redesags.wixsite.com/thaina")
    b = _place("B", "Clínica Sorriso Bom", site="https://outroestudio.wixsite.com/x")

    decisao = comparar(a, b)

    assert decisao.acao is Acao.NAO_FUNDE


def test_dois_perfis_de_instagram_nao_fundem() -> None:
    a = _place("A", "Dr. Guilherme Mancini", site="https://instagram.com/drmancini/")
    b = _place("B", "Dra. Vânia Horie", site="https://www.instagram.com/dravania/")

    decisao = comparar(a, b)

    assert decisao.acao is Acao.NAO_FUNDE


def test_mesmo_telefone_em_cidades_diferentes_nao_funde() -> None:
    a = _place("A", "Consultório Alfa", cidade="Campinas", telefone="(19) 3233-4558")
    b = _place("B", "Consultório Beta", cidade="Valinhos", telefone="(19) 3233-4558")

    decisao = comparar(a, b)

    assert decisao.acao is Acao.NAO_FUNDE


def test_registros_sem_nada_em_comum_nao_fundem() -> None:
    a = _place("A", "Odonto Urgente", telefone="(19) 3325-0025")
    b = _place("B", "Karina Marani Odontologia", telefone="(19) 98875-5828")

    decisao = comparar(a, b)

    assert decisao.acao is Acao.NAO_FUNDE
    assert decisao.motivo == "nenhum identificador em comum"


def test_toda_decisao_traz_acao_confianca_e_motivo_legivel() -> None:
    """Nunca um booleano: a fusão precisa ser auditável depois."""
    decisao = comparar(_place("A", "X"), _place("A", "Y"))

    assert isinstance(decisao.acao, Acao)
    assert isinstance(decisao.confianca, Confianca)
    assert decisao.motivo and not decisao.motivo.isupper()


# --------------------------------- blocklist ---------------------------------


def test_blocklist_barra_por_place_id(sessao: Session) -> None:
    place = _place("ChIJ-bloqueado", "Consultório que pediu opt-out")
    adicionar_blocklist(
        sessao, motivo="pediu para não ser contactado", place_id=place.place_id
    )
    sessao.commit()

    bloqueio = esta_bloqueado(sessao, place)

    assert bloqueio is not None
    assert bloqueio.motivo == "pediu para não ser contactado"


def test_blocklist_barra_por_telefone_normalizado(sessao: Session) -> None:
    adicionar_blocklist(
        sessao, motivo="opt-out por telefone", telefone="+55 19 3233-4558"
    )
    sessao.commit()

    bloqueio = esta_bloqueado(
        sessao, _place("X", "Outro nome", telefone="(19) 3233-4558")
    )

    assert bloqueio is not None


def test_blocklist_barra_por_dominio(sessao: Session) -> None:
    adicionar_blocklist(
        sessao,
        motivo="advogado do cliente pediu",
        dominio="https://www.oralclincampinas.com.br/",
    )
    sessao.commit()

    bloqueio = esta_bloqueado(
        sessao, _place("X", "Oral Clin", site="http://oralclincampinas.com.br/contato")
    )

    assert bloqueio is not None


def test_blocklist_nao_barra_por_dominio_compartilhado(sessao: Session) -> None:
    """Bloquear um perfil na Doctoralia não pode bloquear todos os outros."""
    adicionar_blocklist(
        sessao,
        motivo="opt-out de um perfil",
        dominio="https://www.doctoralia.com.br/fulano",
    )
    sessao.commit()

    bloqueio = esta_bloqueado(
        sessao,
        _place("X", "Outro dentista", site="https://www.doctoralia.com.br/sicrano"),
    )

    assert bloqueio is None


def test_place_liberado_passa(sessao: Session) -> None:
    assert (
        esta_bloqueado(sessao, _place("Z", "Livre", telefone="(19) 99999-8888")) is None
    )
