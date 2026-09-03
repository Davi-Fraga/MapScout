"""Módulo de autenticação segura e gerenciamento de sessões para o MapScout."""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import time

COOKIE_NAME = "mapscout_session"
SECRET_PADRAO = "mapscout-secret-chave-padrao-producao-substitua-se-quiser"


def obter_chave_secreta() -> str:
    """Retorna a chave de assinatura de tokens a partir das variáveis de ambiente."""
    return os.environ.get("MAPSCOUT_SECRET_KEY", SECRET_PADRAO)


def obter_usuarios_autorizados() -> dict[str, str]:
    """Carrega os usuários e senhas autorizados da variável MAPSCOUT_USERS."""
    bruto = os.environ.get("MAPSCOUT_USERS")
    if not bruto or not bruto.strip():
        # Usuário e senha padrão de primeiro acesso se não configurado
        return {"admin": "admin123"}

    bruto_limpo = bruto.strip().strip("'\"")
    # Aceita separação por vírgula, ponto e vírgula ou quebras de linha
    itens = [
        item.strip()
        for linha in bruto_limpo.splitlines()
        for bloco in linha.split(";")
        for item in bloco.split(",")
        if item.strip()
    ]

    usuarios: dict[str, str] = {}
    for par in itens:
        if ":" in par:
            u, s = par.split(":", 1)
            u_limpo = u.strip().strip("'\"").lower()
            s_limpo = s.strip().strip("'\"")
            if u_limpo and s_limpo:
                usuarios[u_limpo] = s_limpo

    if not usuarios:
        usuarios["admin"] = "admin123"

    return usuarios


def verificar_credenciais(usuario: str, senha: str) -> bool:
    """Verifica se o usuário e a senha coincidem com algum dos cadastrados."""
    autorizados = obter_usuarios_autorizados()
    usuario_limpo = usuario.strip().lower()
    if usuario_limpo not in autorizados:
        return False

    senha_esperada = autorizados[usuario_limpo]
    return secrets.compare_digest(senha, senha_esperada)


def gerar_token_sessao(usuario: str, chave: str | None = None) -> str:
    """Gera um token criptográfico assinado com timestamp e HMAC-SHA256."""
    secret = chave or obter_chave_secreta()
    timestamp = int(time.time())
    payload = f"{usuario}:{timestamp}"
    assinatura = hmac.new(
        secret.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"{payload}:{assinatura}"


def validar_token_sessao(
    token: str,
    max_dias: int = 30,
    chave: str | None = None,
) -> str | None:
    """Valida a assinatura e o prazo de expiração do token, devolvendo o usuário."""
    if not token or ":" not in token:
        return None

    partes = token.split(":")
    if len(partes) != 3:
        return None

    usuario, ts_str, assinatura = partes
    try:
        ts = int(ts_str)
    except ValueError:
        return None

    agora = int(time.time())
    limite_segundos = max_dias * 86400
    if agora - ts > limite_segundos or ts > agora + 300:
        return None

    secret = chave or obter_chave_secreta()
    payload = f"{usuario}:{ts}"
    assinatura_esperada = hmac.new(
        secret.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    if not secrets.compare_digest(assinatura, assinatura_esperada):
        return None

    return usuario
