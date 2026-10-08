"""Ciclo de vida da sessão — onde a continuidade de contexto acontece.

A regra que sustenta a proposta de valor do Vortex está em
`obter_ou_criar`: enquanto houver sessão viva para o cliente, QUALQUER canal
escreve no mesmo protocolo. A troca de canal vira um evento, não um novo
atendimento.
"""

from collections.abc import Awaitable, Callable

from app.config import Settings
from app.core.protocolo import gerar_protocolo
from app.domain.enums import Canal, Intencao
from app.domain.models import Atendimento, Sessao, agora
from app.repositories.base import SessaoRepository
from app.services.verificacao_service import VERIFICADAS

# Dado o cliente, devolve o atendimento que precisa ser retomado (ou None).
BuscaRetomada = Callable[[str], Awaitable[Atendimento | None]]


class ResultadoSessao:
    __slots__ = ("sessao", "nova", "troca_de_canal")

    def __init__(self, sessao: Sessao, nova: bool, troca_de_canal: bool) -> None:
        self.sessao = sessao
        self.nova = nova
        self.troca_de_canal = troca_de_canal


class SessaoService:
    def __init__(self, repo: SessaoRepository, settings: Settings) -> None:
        self._repo = repo
        self._s = settings

    async def obter_ou_criar(
        self, cliente_id: str, canal: Canal, retomar: BuscaRetomada | None = None
    ) -> ResultadoSessao:
        sessao = await self._repo.obter(cliente_id)

        if sessao is None and retomar is not None:
            # A sessão expirou, mas o atendimento não acabou (ex.: o cliente
            # esperava um humano há mais de 30 min). Abrir protocolo novo aqui
            # partiria o histórico em dois — o oposto do que o produto promete.
            aberto = await retomar(cliente_id)
            if aberto is not None:
                sessao = Sessao(
                    cliente_id=cliente_id,
                    protocolo=aberto.protocolo,
                    canal_ativo=aberto.canal_atual,
                    canal_origem=aberto.canal_origem,
                    canais_utilizados=list(aberto.canais_utilizados),
                    # Quem já tinha provado a identidade não prova de novo.
                    identidade_verificada=aberto.identidade in VERIFICADAS,
                )

        if sessao is None:
            sessao = Sessao(
                cliente_id=cliente_id,
                protocolo=gerar_protocolo(),
                canal_ativo=canal,
                canal_origem=canal,
                canais_utilizados=[canal],
            )
            await self._repo.salvar(sessao, self._s.sessao_ttl_segundos)
            return ResultadoSessao(sessao, nova=True, troca_de_canal=False)

        troca = sessao.canal_ativo != canal
        if troca:
            sessao.canal_ativo = canal
            if canal not in sessao.canais_utilizados:
                sessao.canais_utilizados.append(canal)
            # Em memória a mudança já valeria por referência; num banco, não.
            await self._repo.salvar(sessao, self._s.sessao_ttl_segundos)

        return ResultadoSessao(sessao, nova=False, troca_de_canal=troca)

    async def registrar_turno(self, sessao: Sessao, intencao: Intencao) -> Sessao:
        """Incrementa contadores ANTES da avaliação de fricção (que os consome)."""
        sessao.turnos += 1
        sessao.ultima_interacao = agora()

        if intencao == sessao.intencao_atual and intencao != Intencao.OUTROS:
            sessao.turnos_mesma_intencao += 1
        else:
            sessao.intencao_atual = intencao
            sessao.turnos_mesma_intencao = 1

        await self._repo.salvar(sessao, self._s.sessao_ttl_segundos)
        return sessao

    async def salvar(self, sessao: Sessao) -> Sessao:
        await self._repo.salvar(sessao, self._s.sessao_ttl_segundos)
        return sessao

    async def registrar_resolucao(self, sessao: Sessao) -> Sessao:
        """O autoatendimento resolveu a demanda: a contagem de turnos sem
        resolução (que alimenta o detector de loop) recomeça do zero."""
        sessao.turnos = 0
        sessao.turnos_mesma_intencao = 0
        await self._repo.salvar(sessao, self._s.sessao_ttl_segundos)
        return sessao

    async def encerrar(self, cliente_id: str, protocolo: str) -> None:
        """Libera a sessão — só se ela ainda for DESTE protocolo.

        Encerrar um protocolo antigo (aba velha, clique duplo) não pode derrubar
        a conversa nova que o cliente já abriu.
        """
        sessao = await self._repo.obter(cliente_id)
        if sessao is not None and sessao.protocolo == protocolo:
            await self._repo.remover(cliente_id)
