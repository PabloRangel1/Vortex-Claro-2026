"""Equivalente in-memory das tabelas `faturas`, `equipamentos`, `planos` e `solicitacoes`."""

from app.domain.models import Equipamento, Fatura, Plano, Solicitacao
from app.repositories.base import OperacaoRepository
from app.repositories.memory.store import MemoryStore


class MemOperacaoRepository(OperacaoRepository):
    def __init__(self, store: MemoryStore) -> None:
        self._store = store

    async def obter_fatura_atual(self, cliente_id: str) -> Fatura | None:
        return self._store.faturas.get(cliente_id)

    async def salvar_fatura(self, fatura: Fatura) -> Fatura:
        self._store.faturas[fatura.cliente_id] = fatura
        return fatura

    async def obter_equipamento(self, cliente_id: str) -> Equipamento | None:
        return self._store.equipamentos.get(cliente_id)

    async def salvar_equipamento(self, equipamento: Equipamento) -> Equipamento:
        self._store.equipamentos[equipamento.cliente_id] = equipamento
        return equipamento

    async def listar_planos(self) -> list[Plano]:
        return list(self._store.planos.values())

    async def obter_plano(self, plano_id: str) -> Plano | None:
        return self._store.planos.get(plano_id)

    async def criar_solicitacao(self, solicitacao: Solicitacao) -> Solicitacao:
        self._store.solicitacoes.setdefault(solicitacao.cliente_id, []).append(solicitacao)
        return solicitacao

    async def listar_solicitacoes(self, cliente_id: str) -> list[Solicitacao]:
        return list(self._store.solicitacoes.get(cliente_id, []))

    async def obter_solicitacao(self, protocolo: str) -> Solicitacao | None:
        return next(
            (s for lista in self._store.solicitacoes.values() for s in lista if s.protocolo == protocolo),
            None,
        )
