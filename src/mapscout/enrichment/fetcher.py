"""Cliente HTTP assíncrono para crawler e diagnóstico de sites das empresas."""

from __future__ import annotations

import ssl
from dataclasses import dataclass

import httpx

from mapscout.enrichment.parser import SinaisPagina, extrair_sinais_html

USER_AGENT_PADRAO = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36 MapScoutBot/1.0"
)


@dataclass(frozen=True)
class ResultadoFetch:
    """Resultado completo da inspeção HTTP e análise de uma empresa."""

    url_final: str
    status_code: int | None
    has_ssl: bool
    sinais: SinaisPagina
    erro: str | None = None
    tempo_resposta_ms: int = 0


async def buscar_pagina(
    url: str,
    *,
    client: httpx.AsyncClient | None = None,
    timeout_s: float = 6.0,
) -> ResultadoFetch:
    """Acessa a URL, verifica HTTPS, status HTTP e extrai sinais e contatos."""
    url_limpa = url.strip()
    if not url_limpa.startswith(("http://", "https://")):
        url_limpa = f"https://{url_limpa}"

    tem_ssl = url_limpa.startswith("https://")

    # Headers comuns para evitar bloqueio por WAFs básicos
    headers = {
        "User-Agent": USER_AGENT_PADRAO,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    }

    async def _fazer_requisicao(
        cli: httpx.AsyncClient, target_url: str
    ) -> httpx.Response:
        return await cli.get(
            target_url,
            headers=headers,
            follow_redirects=True,
            timeout=timeout_s,
        )

    response: httpx.Response | None = None
    erro_str: str | None = None

    try:
        if client is not None:
            response = await _fazer_requisicao(client, url_limpa)
        else:
            async with httpx.AsyncClient(verify=True) as novo_cli:
                response = await _fazer_requisicao(novo_cli, url_limpa)
    except (httpx.ConnectError, ssl.SSLError) as exc_ssl:
        # Se falhou com SSL na URL https, tenta com http puro
        if url_limpa.startswith("https://"):
            tem_ssl = False
            http_url = f"http://{url_limpa[8:]}"
            try:
                if client is not None:
                    response = await _fazer_requisicao(client, http_url)
                else:
                    async with httpx.AsyncClient(verify=False) as novo_cli:
                        response = await _fazer_requisicao(novo_cli, http_url)
            except Exception as erro_http:
                erro_str = f"Falha na conexão HTTP/HTTPS: {type(erro_http).__name__}"
        else:
            erro_str = f"Falha na conexão: {type(exc_ssl).__name__}"
    except httpx.TimeoutException:
        erro_str = "Tempo limite de conexão esgotado (timeout)"
    except Exception as exc:
        erro_str = f"Erro de conexão: {type(exc).__name__}"

    if response is None:
        return ResultadoFetch(
            url_final=url_limpa,
            status_code=None,
            has_ssl=tem_ssl,
            sinais=SinaisPagina(
                has_mobile_viewport=False,
                copyright_year=None,
                is_parked_or_empty=True,
            ),
            erro=erro_str or "Não respondeu",
        )

    # Se a URL final for https, confirma SSL
    url_final_str = str(response.url)
    has_ssl_final = url_final_str.startswith("https://") and tem_ssl

    html_content = response.text or ""
    sinais = extrair_sinais_html(html_content, url_origem=url_final_str)

    return ResultadoFetch(
        url_final=url_final_str,
        status_code=response.status_code,
        has_ssl=has_ssl_final,
        sinais=sinais,
        erro=erro_str,
    )
