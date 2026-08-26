"""Teste ponta a ponta da CLI: coleta mockada gravando no banco."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx
import pytest
import respx
from sqlmodel import Session

from mapscout.cli import main
from mapscout.db.repo import contar_api_calls, contar_places, listar_places
from mapscout.db.session import criar_engine
from mapscout.sources.places_api import ENDPOINT


@respx.mock
def test_coletar_grava_places_e_api_calls(
    pagina_final: dict[str, Any],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    banco = tmp_path / "teste.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{banco}")
    respx.post(ENDPOINT).mock(return_value=httpx.Response(200, json=pagina_final))

    codigo = main(
        [
            "coletar",
            "--categoria",
            "dentista",
            "--lat",
            "-22.9099",
            "--lng",
            "-47.0626",
            "--raio-m",
            "3000",
            "--cidade",
            "Campinas",
        ]
    )

    assert codigo == 0
    assert banco.exists()
    with Session(criar_engine(f"sqlite:///{banco}")) as sessao:
        assert contar_places(sessao) == 20
        assert contar_api_calls(sessao) == 1
        assert len(listar_places(sessao, limite=5)) == 5
    assert "coletados 20 lugares" in capsys.readouterr().out


@respx.mock
def test_coletar_duas_vezes_nao_duplica(
    pagina_final: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    banco = tmp_path / "teste.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{banco}")
    respx.post(ENDPOINT).mock(return_value=httpx.Response(200, json=pagina_final))

    argumentos = [
        "coletar",
        "--categoria",
        "dentista",
        "--lat",
        "-22.9099",
        "--lng",
        "-47.0626",
        "--raio-m",
        "3000",
        "--cidade",
        "Campinas",
    ]
    main(argumentos)
    main(argumentos)

    with Session(criar_engine(f"sqlite:///{banco}")) as sessao:
        assert contar_places(sessao) == 20
        assert contar_api_calls(sessao) == 2


def test_coletar_exige_os_argumentos() -> None:
    with pytest.raises(SystemExit):
        main(["coletar", "--categoria", "dentista"])


ARGS_VALIDOS = [
    "coletar",
    "--categoria",
    "dentista",
    "--lat",
    "-22.9099",
    "--lng",
    "-47.0626",
    "--raio-m",
    "3000",
    "--cidade",
    "Campinas",
]


def test_sem_api_key_falha_com_mensagem_limpa(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("GOOGLE_MAPS_API_KEY", raising=False)

    codigo = main(ARGS_VALIDOS)

    assert codigo == 2
    assert "GOOGLE_MAPS_API_KEY" in capsys.readouterr().err


@respx.mock
def test_api_fora_do_ar_falha_com_mensagem_limpa(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'teste.db'}")
    monkeypatch.setattr("mapscout.sources.places_api.BACKOFF_BASE_S", 0.0)
    respx.post(ENDPOINT).mock(return_value=httpx.Response(503))

    codigo = main(ARGS_VALIDOS)

    assert codigo == 3
    assert "HTTP 503" in capsys.readouterr().err
