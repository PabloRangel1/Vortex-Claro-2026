"""Tabelas `atendimentos` e `eventos_friccao`."""

import asyncpg

from app.domain.enums import StatusAtendimento
from app.domain.models import Atendimento, EventoFriccao
from app.repositories.base import AtendimentoRepository
from app.repositories.postgres._sql import para_linha, upsert


def _atendimento(linha: asyncpg.Record | None) -> Atendimento | None:
    return Atendimento.model_validate(dict(linha)) if linha else None


def _eventos(linhas: list[asyncpg.Record]) -> list[EventoFriccao]:
    return [EventoFriccao.model_validate(dict(linha)) for linha in linhas]


class PgAtendimentoRepository(AtendimentoRepository):
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def obter(self, protocolo: str) -> Atendimento | None:
        return _atendimento(
            await self._pool.fetchrow("SELECT * FROM atendimentos WHERE protocolo = $1", protocolo)
        )

    async def salvar(self, atendimento: Atendimento) -> Atendimento:
        await upsert(self._pool, "atendimentos", ("protocolo",), para_linha(atendimento))
        return atendimento

    async def listar_por_status(self, *status: StatusAtendimento) -> list[Atendimento]:
        linhas = await self._pool.fetch(
            "SELECT * FROM atendimentos WHERE status = ANY($1::text[]) ORDER BY aberto_em",
            [str(s) for s in status],
        )
        return [_atendimento(linha) for linha in linhas]

    async def listar_todos(self) -> list[Atendimento]:
        linhas = await self._pool.fetch("SELECT * FROM atendimentos ORDER BY aberto_em")
        return [_atendimento(linha) for linha in linhas]

    async def ultimo_do_cliente(self, cliente_id: str) -> Atendimento | None:
        return _atendimento(
            await self._pool.fetchrow(
                "SELECT * FROM atendimentos WHERE cliente_id = $1 "
                "ORDER BY aberto_em DESC LIMIT 1",
                cliente_id,
            )
        )

    async def listar_do_cliente(self, cliente_id: str) -> list[Atendimento]:
        linhas = await self._pool.fetch(
            "SELECT * FROM atendimentos WHERE cliente_id = $1 ORDER BY aberto_em DESC",
            cliente_id,
        )
        return [_atendimento(linha) for linha in linhas]

    async def listar_todos_eventos(self) -> list[EventoFriccao]:
        return _eventos(await self._pool.fetch("SELECT * FROM eventos_friccao ORDER BY seq"))

    async def registrar_eventos(self, eventos: list[EventoFriccao]) -> None:
        """Append-only: só INSERT. Todos os sinais do turno entram juntos."""
        if not eventos:
            return
        linhas = [para_linha(e) for e in eventos]
        colunas = list(linhas[0])
        parametros = ", ".join(f"${i}" for i in range(1, len(colunas) + 1))
        await self._pool.executemany(
            f"INSERT INTO eventos_friccao ({', '.join(colunas)}) VALUES ({parametros})",
            [tuple(linha.values()) for linha in linhas],
        )

    async def listar_eventos(self, protocolo: str) -> list[EventoFriccao]:
        return _eventos(
            await self._pool.fetch(
                "SELECT * FROM eventos_friccao WHERE protocolo = $1 ORDER BY seq", protocolo
            )
        )
