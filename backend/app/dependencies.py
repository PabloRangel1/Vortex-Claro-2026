"""Injeção de dependências — o ÚNICO arquivo que conhece as implementações.

⭐ PONTO DE TROCA DA PERSISTÊNCIA ⭐
Com `DATABASE_URL` definida, a API abre um pool PostgreSQL na inicialização
(`iniciar_persistencia`, chamada pelo lifespan em `main.py`) e o container usa
os repositórios de `repositories/postgres/`. Sem ela — e é assim nos testes —
usa os de `repositories/memory/`.

Nenhum service, router ou schema sabe qual dos dois está ativo.
"""

import asyncio
import logging
from typing import Annotated

import asyncpg

from fastapi import Depends

from app.config import Settings, get_settings
from app.core.protocolo import reiniciar_sequencia
from app.repositories.base import (
    AtendimentoRepository,
    ClienteRepository,
    ConversaRepository,
    OperacaoRepository,
    SessaoRepository,
)
from app.repositories import postgres
from app.repositories.seed import CLIENTES_DEMO_AO_VIVO
from app.repositories.memory import (
    MemAtendimentoRepository,
    MemClienteRepository,
    MemConversaRepository,
    MemOperacaoRepository,
    MemSessaoRepository,
    MemoryStore,
    semear,
)
from app.services.autoatendimento_service import AutoatendimentoService
from app.services.demonstracao_service import semear_demonstracao, tem_demonstracao
from app.services.dialogo_service import DialogoService
from app.services.estatisticas_service import EstatisticasService
from app.services.friccao_service import FriccaoService
from app.services.ia_service import IAService
from app.services.nlp_service import NLPService
from app.services.orquestrador_service import OrquestradorService
from app.services.resposta_service import RespostaService
from app.services.sessao_service import SessaoService
from app.services.verificacao_service import VerificacaoService


class Container:
    def __init__(self, settings: Settings, pool: asyncpg.Pool | None = None) -> None:
        self.settings = settings
        self.pool = pool

        # --- Infraestrutura ---
        self.clientes: ClienteRepository
        self.sessoes_repo: SessaoRepository
        self.conversas: ConversaRepository
        self.atendimentos: AtendimentoRepository
        self.operacao: OperacaoRepository

        # Um reset por vez: um segundo clique espera o primeiro, não roda outro.
        self._reset_em_curso: asyncio.Task | None = None

        if pool is not None:
            self.store: MemoryStore | None = None
            self.clientes = postgres.PgClienteRepository(pool)
            self.sessoes_repo = postgres.PgSessaoRepository(pool)
            self.conversas = postgres.PgConversaRepository(pool)
            self.atendimentos = postgres.PgAtendimentoRepository(pool)
            self.operacao = postgres.PgOperacaoRepository(pool)
        else:
            self.store = MemoryStore()
            semear(self.store)
            self.clientes = MemClienteRepository(self.store)
            self.sessoes_repo = MemSessaoRepository(self.store)
            self.conversas = MemConversaRepository(self.store)
            self.atendimentos = MemAtendimentoRepository(self.store)
            self.operacao = MemOperacaoRepository(self.store)

        # --- Serviços de domínio ---
        self.nlp = NLPService(settings)
        self.friccao = FriccaoService(settings)
        self.respostas = RespostaService()
        self.sessoes = SessaoService(self.sessoes_repo, settings)
        self.estatisticas = EstatisticasService(self.friccao, settings)

        # Autoatendimento: ações do catálogo (Fase 1) conduzidas pela conversa
        # guiada (Fase 2), chamada pelo orquestrador a cada mensagem (Fase 4).
        self.autoatendimento = AutoatendimentoService(
            clientes=self.clientes,
            operacao=self.operacao,
            conversas=self.conversas,
            atendimentos=self.atendimentos,
            settings=settings,
        )
        # Fase 5: IA como camada de linguagem. Sem GEMINI_API_KEY ela fica
        # inerte e a conversa usa só as regras determinísticas.
        self.ia = IAService(settings, conversas=self.conversas, clientes=self.clientes)
        self.dialogo = DialogoService(
            autoatendimento=self.autoatendimento,
            sessoes=self.sessoes_repo,
            settings=settings,
            ia=self.ia,
        )

        self.verificacao = VerificacaoService(settings)

        self.orquestrador = OrquestradorService(
            clientes=self.clientes,
            conversas=self.conversas,
            atendimentos=self.atendimentos,
            sessoes=self.sessoes,
            nlp=self.nlp,
            friccao=self.friccao,
            respostas=self.respostas,
            dialogo=self.dialogo,
            verificacao=self.verificacao,
            settings=settings,
        )


    @property
    def persistencia(self) -> str:
        return "postgresql" if self.pool is not None else "memoria"

    async def resetar(self) -> None:
        """Apaga tudo e semeia de novo os dados fictícios (POST /reset).

        Com `semear_demonstracao`, recarrega também as conversas simuladas —
        o dashboard volta ao estado de apresentação, não vazio. Se já houver um
        reset em andamento, espera por ele em vez de começar outro.
        """
        if self._reset_em_curso is not None and not self._reset_em_curso.done():
            await self._reset_em_curso
            return
        self._reset_em_curso = asyncio.ensure_future(self._resetar())
        await self._reset_em_curso

    async def _resetar(self) -> None:
        if self.pool is None:
            self.store.limpar()
            semear(self.store)
            if self.settings.semear_demonstracao:
                await semear_demonstracao(self)
            return
        await postgres.limpar(self.pool)
        await postgres.semear(self.pool)
        if self.settings.semear_demonstracao:
            await self.carregar_demonstracao(preservar=set())

    async def carregar_demonstracao(self, preservar: set[str]) -> None:
        """No banco, a simulação roda EM MEMÓRIA (menos de 1s) e o resultado é
        gravado em lote — passar cada mensagem pelo banco remoto levava ~107s."""
        rascunho = Container(self.settings)  # memória, já semeado
        await semear_demonstracao(rascunho)
        await postgres.copiar_simulacao(self.pool, rascunho.store, preservar)


_container: Container | None = None

log = logging.getLogger(__name__)

# Esperas entre tentativas de conectar na subida (~30s no total). O Neon
# gratuito suspende o banco ocioso e pode demorar a acordar.
ESPERAS_CONEXAO = (1, 2, 4, 8, 15)


async def iniciar_persistencia(settings: Settings) -> None:
    """Chamada uma vez na subida da API. Sem DATABASE_URL, não faz nada.

    Se o banco não responder, tenta de novo algumas vezes antes de desistir.
    Desistir derruba a subida de propósito: cair para memória em silêncio
    faria a demo perder dados sem ninguém perceber.
    """
    global _container
    if not settings.database_url:
        # Em memória a base nasce vazia a cada subida: carrega a demonstração.
        if settings.semear_demonstracao:
            _container = Container(settings)
            await semear_demonstracao(_container)
        return
    for tentativa, espera in enumerate((*ESPERAS_CONEXAO, None), start=1):
        pool = None
        try:
            pool = await postgres.criar_pool(settings.database_url)
            await postgres.preparar_banco(pool)
            break
        except (OSError, asyncpg.PostgresError, asyncio.TimeoutError) as erro:
            if pool is not None:
                await pool.close()
            if espera is None:
                raise
            log.warning(
                "Banco indisponível (tentativa %s: %s). Nova tentativa em %ss.",
                tentativa, type(erro).__name__, espera,
            )
            await asyncio.sleep(espera)
    _container = Container(settings, pool)

    # Nunca apaga nada na subida: só completa o cadastro de clientes do seed...
    await postgres.semear_faltantes(pool)
    # ...e carrega as conversas simuladas se elas ainda não estiverem no banco.
    # (Basear isso em "banco vazio" falhava: uma conversa de teste qualquer
    # impedia a demonstração de aparecer.)
    if settings.semear_demonstracao and not await tem_demonstracao(_container):
        # Não sobrescreve o cadastro dos clientes da demo ao vivo: o uso real
        # pode tê-lo alterado. As conversas simuladas entram normalmente.
        await _container.carregar_demonstracao(preservar=set(CLIENTES_DEMO_AO_VIVO))


async def encerrar_persistencia() -> None:
    global _container
    if _container is not None:
        await _container.ia.fechar()
        if _container.pool is not None:
            await _container.pool.close()
    _container = None


def get_container() -> Container:
    global _container
    if _container is None:
        _container = Container(get_settings())
    return _container


def resetar_container() -> None:
    """Estado limpo entre testes."""
    global _container
    _container = None
    reiniciar_sequencia()


ContainerDep = Annotated[Container, Depends(get_container)]


def get_orquestrador(container: ContainerDep) -> OrquestradorService:
    return container.orquestrador


def get_atendimento_repo(container: ContainerDep) -> AtendimentoRepository:
    return container.atendimentos


def get_conversa_repo(container: ContainerDep) -> ConversaRepository:
    return container.conversas


def get_cliente_repo(container: ContainerDep) -> ClienteRepository:
    return container.clientes


def get_operacao_repo(container: ContainerDep) -> OperacaoRepository:
    return container.operacao


def get_sessao_repo(container: ContainerDep) -> SessaoRepository:
    return container.sessoes_repo


def get_friccao(container: ContainerDep) -> FriccaoService:
    return container.friccao


def get_estatisticas(container: ContainerDep) -> EstatisticasService:
    return container.estatisticas


OrquestradorDep = Annotated[OrquestradorService, Depends(get_orquestrador)]
AtendimentoRepoDep = Annotated[AtendimentoRepository, Depends(get_atendimento_repo)]
ConversaRepoDep = Annotated[ConversaRepository, Depends(get_conversa_repo)]
ClienteRepoDep = Annotated[ClienteRepository, Depends(get_cliente_repo)]
SessaoRepoDep = Annotated[SessaoRepository, Depends(get_sessao_repo)]
OperacaoRepoDep = Annotated[OperacaoRepository, Depends(get_operacao_repo)]
FriccaoDep = Annotated[FriccaoService, Depends(get_friccao)]
EstatisticasDep = Annotated[EstatisticasService, Depends(get_estatisticas)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
