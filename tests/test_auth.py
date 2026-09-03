"""Testes do módulo de autenticação e proteção de rotas."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from mapscout.auth import (
    COOKIE_NAME,
    gerar_token_sessao,
    obter_usuarios_autorizados,
    validar_token_sessao,
    verificar_credenciais,
)
from mapscout.web.app import app

client = TestClient(app, follow_redirects=False)


def test_obter_usuarios_padrao() -> None:
    """Verifica que na ausência de configuração existe o usuário padrão admin."""
    usuarios = obter_usuarios_autorizados()
    assert "admin" in usuarios
    assert usuarios["admin"] == "admin123"


def test_obter_usuarios_variavel_ambiente(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifica parsing de múltiplos usuários a partir de MAPSCOUT_USERS."""
    monkeypatch.setenv("MAPSCOUT_USERS", "davi:senha123,socio:senha456")
    usuarios = obter_usuarios_autorizados()
    assert usuarios["davi"] == "senha123"
    assert usuarios["socio"] == "senha456"


def test_verificar_credenciais(monkeypatch: pytest.MonkeyPatch) -> None:
    """Valida verificação de senha correta e incorreta."""
    monkeypatch.setenv("MAPSCOUT_USERS", "davi:segredo")
    assert verificar_credenciais("davi", "segredo") is True
    assert verificar_credenciais("davi", "errada") is False
    assert verificar_credenciais("estranho", "segredo") is False


def test_token_sessao_ciclo_de_vida() -> None:
    """Testa geração, validação e rejeição de tokens alterados."""
    token = gerar_token_sessao("davi")
    assert token is not None
    usuario = validar_token_sessao(token)
    assert usuario == "davi"

    # Token adulterado
    token_falso = token[:-4] + "ffff"
    assert validar_token_sessao(token_falso) is None

    # Token malformado
    assert validar_token_sessao("invalido") is None


def test_redirecionamento_sem_login() -> None:
    """Verifica que acessar rota protegida sem sessão redireciona para /login."""
    cli_anonimo = TestClient(app, follow_redirects=False)
    response = cli_anonimo.get("/")
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_redirecionamento_htmx_sem_login() -> None:
    """Verifica cabeçalho HX-Redirect quando requisição HTMX não está autenticada."""
    cli_anonimo = TestClient(app, follow_redirects=False)
    response = cli_anonimo.get("/partials/jobs/status", headers={"HX-Request": "true"})
    assert response.status_code == 200
    assert response.headers.get("HX-Redirect") == "/login"


def test_login_falha() -> None:
    """Testa submissão com credenciais inválidas."""
    cli = TestClient(app, follow_redirects=False)
    response = cli.post("/login", data={"usuario": "admin", "senha": "senhaerrada"})
    assert response.status_code == 401
    assert "Usuário ou senha incorretos" in response.text


def test_login_sucesso_e_logout() -> None:
    """Testa fluxo completo de login, acesso autenticado e logout."""
    cli = TestClient(app, follow_redirects=False)
    # 1. Login com credencial padrão
    response_login = cli.post("/login", data={"usuario": "admin", "senha": "admin123"})
    assert response_login.status_code == 303
    assert response_login.headers["location"] == "/"
    assert COOKIE_NAME in response_login.cookies

    cookie_val = response_login.cookies[COOKIE_NAME]

    # 2. Acesso ao painel com o cookie de sessão
    cli.cookies.set(COOKIE_NAME, cookie_val)
    response_painel = cli.get("/")
    assert response_painel.status_code == 200
    assert "MapScout" in response_painel.text

    # 3. Logout
    response_logout = cli.get("/logout")
    assert response_logout.status_code == 303
    assert response_logout.headers["location"] == "/login"
