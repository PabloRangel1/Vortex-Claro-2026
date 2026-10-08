"""Conexão com o PostgreSQL e preparação do banco na inicialização da API."""

import json
from pathlib import Path

import asyncpg

from app.core.protocolo import continuar_sequencia
from app.repositories import seed
from app.repositories.postgres.cliente_repo import PgClienteRepository
from app.repositories.postgres.operacao_repo import PgOperacaoRepository

SCHEMA = Path(__file__).with_name("schema.sql")

TABELAS = (
    "clientes",
    "identificadores_cliente",
    "sessoes",
    "atendimentos",
    "mensagens",
    "eventos_friccao",
    "planos",
    "faturas",
    "equipamentos",
    "solicitacoes",
)


async def _configurar_conexao(conexao: asyncpg.Connection) -> None:
    # JSONB entra e sai como objeto Python, sem json.dumps espalhado pelos repositórios.
    await conexao.set_type_codec(
        "jsonb", encoder=json.dumps, decoder=json.loads, schema="pg_catalog"
    )


async def criar_pool(database_url: str) -> asyncpg.Pool:
    return await asyncpg.create_pool(
        database_url,
        min_size=1,
        max_size=5,
        init=_configurar_conexao,
        # A URL do Neon com "-pooler" passa por um PgBouncer em modo transação,
        # que não convive com o cache de prepared statements do asyncpg.
        statement_cache_size=0,
        # O Neon gratuito suspende o banco ocioso; conexão parada é descartada.
        max_inactive_connection_lifetime=60,
    )


async def preparar_banco(pool: asyncpg.Pool) -> None:
    """Cria as tabelas que faltam, semeia se vazio e retoma a numeração."""
    await pool.execute(SCHEMA.read_text(encoding="utf-8"))
    if not await pool.fetchval("SELECT EXISTS (SELECT 1 FROM clientes)"):
        await semear(pool)
    await _continuar_numeracao(pool)


async def semear(pool: asyncpg.Pool) -> None:
    """Os mesmos dados fictícios do modo em memória."""
    clientes = PgClienteRepository(pool)
    operacao = PgOperacaoRepository(pool)
    for cliente in seed.CLIENTES_SEED:
        await clientes.salvar(cliente)
    for plano in seed.planos():
        await operacao.salvar_plano(plano)
    for fatura in seed.faturas():
        await operacao.salvar_fatura(fatura)
    for equipamento in seed.equipamentos():
        await operacao.salvar_equipamento(equipamento)


async def semear_faltantes(pool: asyncpg.Pool) -> None:
    """Cadastra clientes do seed que ainda não existem e completa o cadastro dos
    que existem sem e-mail/cidade/nascimento — sem mexer em plano, vencimento
    ou qualquer outro dado que o uso possa ter alterado."""
    clientes = PgClienteRepository(pool)
    operacao = PgOperacaoRepository(pool)
    faturas = {f.cliente_id: f for f in seed.faturas()}
    equipamentos = {e.cliente_id: e for e in seed.equipamentos()}
    for cliente in seed.CLIENTES_SEED:
        existente = await clientes.obter(cliente.cliente_id)
        if existente is not None:
            if existente.email is None:
                existente.data_nascimento = cliente.data_nascimento
                existente.email = cliente.email
                existente.cidade = cliente.cidade
                await clientes.salvar(existente)
            continue
        await clientes.salvar(cliente)
        if cliente.cliente_id in faturas:
            await operacao.salvar_fatura(faturas[cliente.cliente_id])
        if cliente.cliente_id in equipamentos:
            await operacao.salvar_equipamento(equipamentos[cliente.cliente_id])


async def copiar_simulacao(pool: asyncpg.Pool, store, preservar: set[str]) -> None:
    """Grava no banco, em lote e numa transação só, o resultado de uma
    simulação feita em memória (ver `services/demonstracao_service.py`).

    Antes, cada mensagem simulada fazia várias consultas ao banco remoto:
    o reset levava ~107s no Neon e estourava o tempo do navegador. Em lote,
    são poucos comandos.

    `preservar`: clientes cujo cadastro NÃO é sobrescrito (os da demo ao vivo,
    que o uso real pode ter alterado). Atendimentos e mensagens deles entram.
    """
    from app.repositories.postgres._sql import para_linha

    async def em_lote(conexao, tabela: str, linhas: list[dict], conflito: str = "") -> None:
        if not linhas:
            return
        colunas = list(linhas[0])
        parametros = ", ".join(f"${i}" for i in range(1, len(colunas) + 1))
        await conexao.executemany(
            f"INSERT INTO {tabela} ({', '.join(colunas)}) VALUES ({parametros}) {conflito}",
            [tuple(l.values()) for l in linhas],
        )

    def upsert_sql(chave: str, colunas: list[str]) -> str:
        sets = ", ".join(f"{c} = EXCLUDED.{c}" for c in colunas if c != chave)
        return f"ON CONFLICT ({chave}) DO UPDATE SET {sets}"

    clientes = [c for c in store.clientes.values() if c.cliente_id not in preservar]
    linhas_clientes = [para_linha(c, excluir={"identificadores"}) for c in clientes]
    faturas = [para_linha(f) for f in store.faturas.values() if f.cliente_id not in preservar]
    equipamentos = [
        para_linha(e) for e in store.equipamentos.values() if e.cliente_id not in preservar
    ]
    atendimentos = [para_linha(a) for a in store.atendimentos.values()]
    mensagens = [para_linha(m) for lista in store.conversas.values() for m in lista]
    eventos = [para_linha(e) for lista in store.eventos.values() for e in lista]
    solicitacoes = sorted(
        (s for lista in store.solicitacoes.values() for s in lista), key=lambda s: s.criada_em
    )

    async with pool.acquire() as conexao, conexao.transaction():
        if linhas_clientes:
            await em_lote(conexao, "clientes", linhas_clientes,
                          upsert_sql("cliente_id", list(linhas_clientes[0])))
        if faturas:
            await em_lote(conexao, "faturas", faturas, upsert_sql("cliente_id", list(faturas[0])))
        if equipamentos:
            await em_lote(conexao, "equipamentos", equipamentos,
                          upsert_sql("id", list(equipamentos[0])))
        await em_lote(conexao, "atendimentos", atendimentos)
        await em_lote(conexao, "mensagens", mensagens)
        await em_lote(conexao, "eventos_friccao", eventos)
        await em_lote(conexao, "solicitacoes", [para_linha(s) for s in solicitacoes])
    await _continuar_numeracao(pool)


async def limpar(pool: asyncpg.Pool) -> None:
    """Apaga TODOS os dados (POST /reset). As tabelas continuam existindo."""
    await pool.execute(f"TRUNCATE {', '.join(TABELAS)} RESTART IDENTITY CASCADE")


async def _continuar_numeracao(pool: asyncpg.Pool) -> None:
    ultimo_protocolo = await pool.fetchval(
        r"""
        SELECT max(split_part(protocolo, '-', 3)::int) FROM (
            SELECT protocolo FROM atendimentos
            UNION ALL
            SELECT protocolo FROM sessoes
        ) t
        WHERE protocolo ~ '^\d{4}-\d{4}-\d+$'
        """
    )
    ultima_solicitacao = await pool.fetchval(
        r"""
        SELECT max(split_part(protocolo, '-', 3)::int) FROM solicitacoes
        WHERE protocolo ~ '^SOL-\d{8}-\d+$'
        """
    )
    continuar_sequencia(ultimo_protocolo, ultima_solicitacao)
