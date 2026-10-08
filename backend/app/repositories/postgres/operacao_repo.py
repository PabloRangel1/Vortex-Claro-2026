"""Tabelas `faturas`, `equipamentos`, `planos` e `solicitacoes`."""

import asyncpg

from app.domain.models import Equipamento, Fatura, Plano, Solicitacao
from app.repositories.base import OperacaoRepository
from app.repositories.postgres._sql import inserir, para_linha, upsert


class PgOperacaoRepository(OperacaoRepository):
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def obter_fatura_atual(self, cliente_id: str) -> Fatura | None:
        linha = await self._pool.fetchrow("SELECT * FROM faturas WHERE cliente_id = $1", cliente_id)
        return Fatura.model_validate(dict(linha)) if linha else None

    async def salvar_fatura(self, fatura: Fatura) -> Fatura:
        await upsert(self._pool, "faturas", ("cliente_id",), para_linha(fatura))
        return fatura

    async def obter_equipamento(self, cliente_id: str) -> Equipamento | None:
        linha = await self._pool.fetchrow(
            "SELECT * FROM equipamentos WHERE cliente_id = $1", cliente_id
        )
        return Equipamento.model_validate(dict(linha)) if linha else None

    async def salvar_equipamento(self, equipamento: Equipamento) -> Equipamento:
        await upsert(self._pool, "equipamentos", ("id",), para_linha(equipamento))
        return equipamento

    async def listar_planos(self) -> list[Plano]:
        linhas = await self._pool.fetch("SELECT * FROM planos ORDER BY seq")
        return [Plano.model_validate(dict(linha)) for linha in linhas]

    async def obter_plano(self, plano_id: str) -> Plano | None:
        linha = await self._pool.fetchrow("SELECT * FROM planos WHERE id = $1", plano_id)
        return Plano.model_validate(dict(linha)) if linha else None

    async def salvar_plano(self, plano: Plano) -> Plano:
        """Fora da interface: o catálogo só é escrito pela semeadura."""
        await upsert(self._pool, "planos", ("id",), para_linha(plano))
        return plano

    async def criar_solicitacao(self, solicitacao: Solicitacao) -> Solicitacao:
        await inserir(self._pool, "solicitacoes", para_linha(solicitacao))
        return solicitacao

    async def obter_solicitacao(self, protocolo: str) -> Solicitacao | None:
        linha = await self._pool.fetchrow("SELECT * FROM solicitacoes WHERE protocolo = $1", protocolo)
        return Solicitacao.model_validate(dict(linha)) if linha else None

    async def listar_solicitacoes(self, cliente_id: str) -> list[Solicitacao]:
        linhas = await self._pool.fetch(
            "SELECT * FROM solicitacoes WHERE cliente_id = $1 ORDER BY seq", cliente_id
        )
        return [Solicitacao.model_validate(dict(linha)) for linha in linhas]
