"""Interfaces de repositório.

REGRA CENTRAL DO PROJETO: todos os métodos são `async`, mesmo que a
implementação atual seja um dicionário síncrono. Quando `redis.asyncio`,
`motor` e `asyncpg` entrarem na fase 2, as assinaturas já são await-áveis e
NENHUM service precisa mudar.
"""

from abc import ABC, abstractmethod

from app.domain.enums import Canal, StatusAtendimento
from app.domain.models import (
    Atendimento,
    Cliente,
    Equipamento,
    EventoFriccao,
    Fatura,
    Mensagem,
    Plano,
    Sessao,
    Solicitacao,
)


class ClienteRepository(ABC):
    """Futuro: PostgreSQL, tabela `clientes`."""

    @abstractmethod
    async def obter(self, cliente_id: str) -> Cliente | None: ...

    @abstractmethod
    async def resolver_por_identificador(self, canal: Canal, identificador: str) -> Cliente | None:
        """Traduz o identificador do canal (telefone, user_id) no cliente_id canônico."""

    @abstractmethod
    async def salvar(self, cliente: Cliente) -> Cliente: ...

    @abstractmethod
    async def listar(self) -> list[Cliente]: ...


class SessaoRepository(ABC):
    """Futuro: Redis, chave `sessao:{cliente_id}` com TTL."""

    @abstractmethod
    async def obter(self, cliente_id: str) -> Sessao | None:
        """Retorna None se ausente OU expirada (o TTL é responsabilidade daqui)."""

    @abstractmethod
    async def salvar(self, sessao: Sessao, ttl_segundos: int) -> None: ...

    @abstractmethod
    async def remover(self, cliente_id: str) -> None: ...


class ConversaRepository(ABC):
    """Futuro: MongoDB, coleção `conversas` (um documento por protocolo)."""

    @abstractmethod
    async def adicionar_mensagem(self, mensagem: Mensagem) -> Mensagem: ...

    @abstractmethod
    async def listar_mensagens(self, protocolo: str) -> list[Mensagem]: ...

    @abstractmethod
    async def ultimas_do_cliente(self, protocolo: str, limite: int) -> list[Mensagem]:
        """Últimas N mensagens do CLIENTE — entrada do detector de repetição."""

    @abstractmethod
    async def contar(self, protocolo: str) -> int: ...

    @abstractmethod
    async def listar_registros_autoatendimento(self) -> list[Mensagem]:
        """Mensagens de ação (`metadados.tipo = "acao"`) e respostas em que a IA
        participou (`metadados.ia`), de todos os protocolos. Base das métricas."""


class AtendimentoRepository(ABC):
    """Futuro: PostgreSQL, tabelas `atendimentos` e `eventos_friccao`."""

    @abstractmethod
    async def obter(self, protocolo: str) -> Atendimento | None: ...

    @abstractmethod
    async def salvar(self, atendimento: Atendimento) -> Atendimento: ...

    @abstractmethod
    async def listar_por_status(self, *status: StatusAtendimento) -> list[Atendimento]: ...

    @abstractmethod
    async def listar_todos(self) -> list[Atendimento]:
        """Base das estatísticas. Na fase 2 vira SELECT com agregação no banco."""

    @abstractmethod
    async def ultimo_do_cliente(self, cliente_id: str) -> Atendimento | None:
        """Atendimento mais recente do cliente, encerrado ou não.

        É o que permite o aparelho do cliente reabrir na conversa em curso em
        vez de numa tela vazia — e é o que faz a avaliação pós-encerramento
        chegar até ele.
        """

    @abstractmethod
    async def listar_do_cliente(self, cliente_id: str) -> list[Atendimento]:
        """Todos os atendimentos do cliente, do mais recente para o mais antigo."""

    @abstractmethod
    async def listar_todos_eventos(self) -> list[EventoFriccao]:
        """Todos os eventos de auditoria, de todos os protocolos."""

    @abstractmethod
    async def registrar_eventos(self, eventos: list[EventoFriccao]) -> None:
        """Append-only. Nunca sobrescreve — é a trilha de auditoria."""

    @abstractmethod
    async def listar_eventos(self, protocolo: str) -> list[EventoFriccao]: ...


class OperacaoRepository(ABC):
    """Dados operacionais usados pelo autoatendimento.

    Uma interface só, de propósito: representa a fronteira com os sistemas da
    operadora (faturamento, rede, catálogo comercial). Na fase de PostgreSQL
    ela se desdobra nas tabelas `faturas`, `equipamentos`, `planos` e
    `solicitacoes` sem mudar nenhuma assinatura.
    """

    @abstractmethod
    async def obter_fatura_atual(self, cliente_id: str) -> Fatura | None: ...

    @abstractmethod
    async def salvar_fatura(self, fatura: Fatura) -> Fatura: ...

    @abstractmethod
    async def obter_equipamento(self, cliente_id: str) -> Equipamento | None: ...

    @abstractmethod
    async def salvar_equipamento(self, equipamento: Equipamento) -> Equipamento: ...

    @abstractmethod
    async def listar_planos(self) -> list[Plano]: ...

    @abstractmethod
    async def obter_plano(self, plano_id: str) -> Plano | None: ...

    @abstractmethod
    async def criar_solicitacao(self, solicitacao: Solicitacao) -> Solicitacao: ...

    @abstractmethod
    async def listar_solicitacoes(self, cliente_id: str) -> list[Solicitacao]: ...

    @abstractmethod
    async def obter_solicitacao(self, protocolo: str) -> Solicitacao | None:
        """Pelo protocolo SOL-…, de qualquer cliente (consulta do atendente)."""
