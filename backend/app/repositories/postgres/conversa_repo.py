"""Tabela `mensagens`. A ordem da conversa é a coluna `seq`."""

import asyncpg

from app.domain.enums import Remetente
from app.domain.models import Mensagem
from app.repositories.base import ConversaRepository
from app.repositories.postgres._sql import inserir, para_linha


class PgConversaRepository(ConversaRepository):
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def adicionar_mensagem(self, mensagem: Mensagem) -> Mensagem:
        await inserir(self._pool, "mensagens", para_linha(mensagem))
        return mensagem

    async def listar_mensagens(self, protocolo: str) -> list[Mensagem]:
        linhas = await self._pool.fetch(
            "SELECT * FROM mensagens WHERE protocolo = $1 ORDER BY seq", protocolo
        )
        return [Mensagem.model_validate(dict(linha)) for linha in linhas]

    async def ultimas_do_cliente(self, protocolo: str, limite: int) -> list[Mensagem]:
        # As N mais recentes, devolvidas em ordem cronológica como na memória.
        linhas = await self._pool.fetch(
            """
            SELECT * FROM (
                SELECT * FROM mensagens
                 WHERE protocolo = $1 AND remetente = $2
                 ORDER BY seq DESC
                 LIMIT $3
            ) t ORDER BY seq
            """,
            protocolo,
            str(Remetente.CLIENTE),
            limite if limite > 0 else None,  # LIMIT NULL = sem limite
        )
        return [Mensagem.model_validate(dict(linha)) for linha in linhas]

    async def contar(self, protocolo: str) -> int:
        return await self._pool.fetchval(
            "SELECT count(*) FROM mensagens WHERE protocolo = $1", protocolo
        )

    async def listar_registros_autoatendimento(self) -> list[Mensagem]:
        linhas = await self._pool.fetch(
            "SELECT * FROM mensagens "
            "WHERE metadados->>'tipo' = 'acao' OR metadados->>'ia' = 'true' ORDER BY seq"
        )
        return [Mensagem.model_validate(dict(linha)) for linha in linhas]
