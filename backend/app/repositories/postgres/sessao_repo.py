"""Tabela `sessoes`. O TTL vira a coluna `expira_em`, checada na leitura."""

from datetime import datetime, timedelta, timezone

import asyncpg

from app.domain.models import Sessao
from app.repositories.base import SessaoRepository
from app.repositories.postgres._sql import para_linha, upsert


class PgSessaoRepository(SessaoRepository):
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def obter(self, cliente_id: str) -> Sessao | None:
        # Sessão vencida continua na tabela até ser sobrescrita, mas não é devolvida.
        linha = await self._pool.fetchrow(
            "SELECT * FROM sessoes WHERE cliente_id = $1 AND expira_em > now()", cliente_id
        )
        return Sessao.model_validate(dict(linha)) if linha else None

    async def salvar(self, sessao: Sessao, ttl_segundos: int) -> None:
        linha = para_linha(sessao)
        linha["expira_em"] = datetime.now(timezone.utc) + timedelta(seconds=ttl_segundos)
        await upsert(self._pool, "sessoes", ("cliente_id",), linha)

    async def remover(self, cliente_id: str) -> None:
        await self._pool.execute("DELETE FROM sessoes WHERE cliente_id = $1", cliente_id)
