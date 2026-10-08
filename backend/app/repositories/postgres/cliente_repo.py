"""Tabelas `clientes` e `identificadores_cliente`."""

import asyncpg

from app.domain.enums import Canal
from app.domain.models import Cliente
from app.repositories.base import ClienteRepository
from app.repositories.postgres._sql import para_linha, upsert

# Os identificadores voltam agregados como {"app": ..., "whatsapp": ...}.
_SELECT = """
    SELECT c.*,
           COALESCE(
               (SELECT jsonb_object_agg(i.canal, i.identificador)
                  FROM identificadores_cliente i
                 WHERE i.cliente_id = c.cliente_id),
               '{}'::jsonb
           ) AS identificadores
      FROM clientes c
"""


def _cliente(linha: asyncpg.Record | None) -> Cliente | None:
    return Cliente.model_validate(dict(linha)) if linha else None


class PgClienteRepository(ClienteRepository):
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def obter(self, cliente_id: str) -> Cliente | None:
        return _cliente(await self._pool.fetchrow(f"{_SELECT} WHERE c.cliente_id = $1", cliente_id))

    async def resolver_por_identificador(self, canal: Canal, identificador: str) -> Cliente | None:
        return _cliente(
            await self._pool.fetchrow(
                f"""{_SELECT}
                 WHERE c.cliente_id = (
                     SELECT cliente_id FROM identificadores_cliente
                      WHERE canal = $1 AND identificador = $2
                 )""",
                str(canal),
                identificador,
            )
        )

    async def salvar(self, cliente: Cliente) -> Cliente:
        async with self._pool.acquire() as conexao, conexao.transaction():
            await upsert(
                conexao, "clientes", ("cliente_id",),
                para_linha(cliente, excluir={"identificadores"}),
            )
            for canal, identificador in cliente.identificadores.items():
                await upsert(
                    conexao, "identificadores_cliente", ("canal", "identificador"),
                    {"canal": str(canal), "identificador": identificador,
                     "cliente_id": cliente.cliente_id},
                )
        return cliente

    async def listar(self) -> list[Cliente]:
        return [_cliente(linha) for linha in await self._pool.fetch(f"{_SELECT} ORDER BY c.seq")]
