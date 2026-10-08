"""Utilitários de SQL compartilhados pelos repositórios PostgreSQL.

Os nomes de coluna vêm sempre dos campos dos modelos de domínio (código nosso),
nunca de entrada do usuário — por isso podem ser interpolados no SQL. Valores
vão sempre como parâmetros ($1, $2...).
"""

from enum import Enum

import asyncpg
from pydantic import BaseModel
from pydantic_core import to_jsonable_python

Executor = asyncpg.Pool | asyncpg.Connection


def _valor(valor: object) -> object:
    if isinstance(valor, Enum):
        return valor.value
    if isinstance(valor, (list, dict)):
        # Vai para coluna JSONB: datas, enums e submodelos viram JSON puro.
        return to_jsonable_python(valor)
    return valor


def para_linha(modelo: BaseModel, *, excluir: set[str] | None = None) -> dict:
    """Modelo de domínio -> {coluna: valor} pronto para o asyncpg."""
    dados = modelo.model_dump(exclude=excluir)
    return {coluna: _valor(valor) for coluna, valor in dados.items()}


async def inserir(executor: Executor, tabela: str, linha: dict) -> None:
    colunas = ", ".join(linha)
    parametros = ", ".join(f"${i}" for i in range(1, len(linha) + 1))
    await executor.execute(
        f"INSERT INTO {tabela} ({colunas}) VALUES ({parametros})", *linha.values()
    )


async def upsert(executor: Executor, tabela: str, chave: tuple[str, ...], linha: dict) -> None:
    """INSERT, ou UPDATE de todas as colunas se a chave já existir."""
    colunas = ", ".join(linha)
    parametros = ", ".join(f"${i}" for i in range(1, len(linha) + 1))
    atualizacao = ", ".join(f"{c} = EXCLUDED.{c}" for c in linha if c not in chave)
    await executor.execute(
        f"INSERT INTO {tabela} ({colunas}) VALUES ({parametros}) "
        f"ON CONFLICT ({', '.join(chave)}) DO UPDATE SET {atualizacao}",
        *linha.values(),
    )
