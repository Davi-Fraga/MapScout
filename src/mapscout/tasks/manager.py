"""Gerenciador de tarefas em background para varredura e enriquecimento."""

from __future__ import annotations

import asyncio
from typing import Any

from sqlalchemy.engine import Engine

from mapscout.collect.grid import gerar_grid
from mapscout.collect.jobs import EstadoJob
from mapscout.collect.runner import ResultadoVarredura, varrer
from mapscout.db.repo import (
    criar_job,
    listar_places_para_enriquecer,
    marcar_job,
    registrar_zona_varrida,
    salvar_place_enriquecido,
)
from mapscout.db.session import abrir_sessao
from mapscout.enrichment.service import enriquecer_lote


class TaskManager:
    """Orquestra a execução assíncrona de varreduras e enriquecimentos em background."""

    def __init__(self) -> None:
        """Inicializa o gerenciador com estado ocioso."""
        self.tipo: str | None = None
        self.status: str = "idle"
        self.mensagem: str = "Nenhuma tarefa em execução"
        self.progresso_atual: int = 0
        self.total: int = 0
        self.porcentagem: int = 0
        self.detalhes: dict[str, Any] = {}
        self.job_id: int | None = None
        self._tarefa_async: asyncio.Task[Any] | None = None
        self._cancelamento_solicitado: bool = False

    def esta_ativa(self) -> bool:
        """Indica se há uma tarefa sendo executada no momento."""
        return (
            self.status == "running"
            and self._tarefa_async is not None
            and not self._tarefa_async.done()
        )

    def obter_status(self) -> dict[str, Any]:
        """Devolve um resumo estruturado do progresso da tarefa para a UI."""
        return {
            "ativa": self.esta_ativa(),
            "tipo": self.tipo,
            "status": self.status,
            "mensagem": self.mensagem,
            "progresso_atual": self.progresso_atual,
            "total": self.total,
            "porcentagem": self.porcentagem,
            "detalhes": self.detalhes,
            "job_id": self.job_id,
        }

    def cancelar(self) -> bool:
        """Solicita o cancelamento cooperativo da tarefa em execução."""
        if not self.esta_ativa():
            return False
        self._cancelamento_solicitado = True
        self.mensagem = "Cancelamento solicitado..."
        return True

    def iniciar_varredura(
        self,
        *,
        categoria: str,
        cidade: str,
        lat: float,
        lng: float,
        raio_km: float,
        passo_m: float,
        engine: Engine,
    ) -> bool:
        """Inicia varredura geográfica em background se não houver outra ativa."""
        if self.esta_ativa():
            return False

        self.tipo = "varredura"
        self.status = "running"
        self._cancelamento_solicitado = False
        self.mensagem = f"Iniciando varredura para '{categoria}' em {cidade}..."
        self.progresso_atual = 0
        self.total = 0
        self.porcentagem = 0
        self.detalhes = {
            "categoria": categoria,
            "cidade": cidade,
            "novos": 0,
            "total_bruto": 0,
        }

        with abrir_sessao(engine) as sessao:
            job = criar_job(sessao, query=f"{categoria} em {cidade}", cidade=cidade)
            self.job_id = job.id

        self._tarefa_async = asyncio.create_task(
            self._executar_varredura(
                categoria=categoria,
                cidade=cidade,
                lat=lat,
                lng=lng,
                raio_km=raio_km,
                passo_m=passo_m,
                engine=engine,
                job_id=self.job_id,
            )
        )
        return True

    async def _executar_varredura(
        self,
        *,
        categoria: str,
        cidade: str,
        lat: float,
        lng: float,
        raio_km: float,
        passo_m: float,
        engine: Engine,
        job_id: int | None,
    ) -> None:
        """Rotina interna que executa a varredura com acompanhamento de progresso."""
        try:
            celulas = gerar_grid(lat, lng, raio_km, passo_m)
            self.total = len(celulas)

            def ao_progredir(
                atual: int, total_estimado: int, res: ResultadoVarredura
            ) -> None:
                self.progresso_atual = atual
                self.total = total_estimado
                self.porcentagem = (
                    int((atual / total_estimado) * 100) if total_estimado > 0 else 0
                )
                self.mensagem = (
                    f"Processando célula {atual}/{total_estimado} "
                    f"({res.novos} novos lugares encontrados)..."
                )
                self.detalhes["novos"] = res.novos
                self.detalhes["total_bruto"] = res.total_bruto

            resultado = await varrer(
                categoria=categoria,
                cidade=cidade,
                celulas=celulas,
                engine=engine,
                job_id=job_id,
                deve_parar=lambda: self._cancelamento_solicitado,
                ao_progredir=ao_progredir,
            )

            if resultado.estado is EstadoJob.CANCELLED:
                self.status = "cancelled"
                self.mensagem = (
                    f"Varredura cancelada. {resultado.novos} lugares novos salvos."
                )
            elif resultado.estado is EstadoJob.PAUSED_QUOTA:
                self.status = "paused_quota"
                self.mensagem = (
                    "Teto diário de chamadas da Places API atingido. Retome amanhã."
                )
            else:
                self.status = "completed"
                self.porcentagem = 100
                self.mensagem = (
                    f"Varredura concluída! {resultado.total_bruto} processados, "
                    f"{resultado.novos} novos cadastrados."
                )
                try:
                    with abrir_sessao(engine) as sessao:
                        registrar_zona_varrida(
                            sessao,
                            cidade=cidade,
                            categoria=categoria,
                            lat=lat,
                            lng=lng,
                            raio_km=raio_km,
                            passo_m=passo_m,
                            total_encontrados=resultado.novos,
                        )
                except Exception:
                    pass
        except Exception as erro:
            self.status = "failed"
            self.mensagem = f"Erro na varredura: {erro}"
            if job_id is not None:
                with abrir_sessao(engine) as sessao:
                    marcar_job(sessao, job_id, EstadoJob.FAILED, erro=str(erro))
                    sessao.commit()

    def iniciar_enriquecimento(
        self,
        *,
        engine: Engine,
        limite: int | None = None,
        concorrencia: int = 5,
        forcar: bool = False,
    ) -> bool:
        """Inicia o diagnóstico de presença digital em segundo plano."""
        if self.esta_ativa():
            return False

        with abrir_sessao(engine) as sessao:
            places = listar_places_para_enriquecer(sessao, forcar=forcar, limite=limite)

        if not places:
            self.tipo = "enriquecimento"
            self.status = "completed"
            self.mensagem = "Nenhum lead pendente de enriquecimento."
            self.progresso_atual = 0
            self.total = 0
            self.porcentagem = 100
            return True

        self.tipo = "enriquecimento"
        self.status = "running"
        self._cancelamento_solicitado = False
        self.total = len(places)
        self.progresso_atual = 0
        self.porcentagem = 0
        self.mensagem = f"Iniciando diagnóstico de {len(places)} empresas..."
        self.detalhes = {"enriquecidos": 0, "total": len(places)}

        self._tarefa_async = asyncio.create_task(
            self._executar_enriquecimento(
                engine=engine,
                places=places,
                concorrencia=concorrencia,
            )
        )
        return True

    async def _executar_enriquecimento(
        self,
        *,
        engine: Engine,
        places: list[Any],
        concorrencia: int,
    ) -> None:
        """Rotina interna que diagnostica os sites com semáforo assíncrono."""
        try:
            total = len(places)

            def ao_progredir(atual: int, _total: int) -> None:
                self.progresso_atual = atual
                self.porcentagem = int((atual / total) * 100) if total > 0 else 0
                self.mensagem = f"Diagnosticando site da empresa {atual}/{total}..."
                self.detalhes["enriquecidos"] = atual

            processados = await enriquecer_lote(
                places,
                concorrencia=concorrencia,
                ao_progredir=ao_progredir,
            )

            with abrir_sessao(engine) as sessao:
                for p in processados:
                    salvar_place_enriquecido(sessao, p)

            self.status = "completed"
            self.porcentagem = 100
            self.mensagem = (
                f"Diagnóstico concluído com sucesso para {len(processados)} empresas!"
            )
        except Exception as erro:
            self.status = "failed"
            self.mensagem = f"Erro no enriquecimento: {erro}"


gerenciador_tarefas = TaskManager()
