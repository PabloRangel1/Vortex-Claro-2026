"""Equivalente in-memory das tabelas PostgreSQL `atendimentos` e `eventos_friccao`."""

from app.domain.enums import StatusAtendimento
from app.domain.models import Atendimento, EventoFriccao
from app.repositories.base import AtendimentoRepository
from app.repositories.memory.store import MemoryStore


class MemAtendimentoRepository(AtendimentoRepository):
    def __init__(self, store: MemoryStore) -> None:
        self._store = store

    async def obter(self, protocolo: str) -> Atendimento | None:
        return self._store.atendimentos.get(protocolo)

    async def salvar(self, atendimento: Atendimento) -> Atendimento:
        self._store.atendimentos[atendimento.protocolo] = atendimento
        return atendimento

    async def listar_por_status(self, *status: StatusAtendimento) -> list[Atendimento]:
        alvos = set(status)
        return [a for a in self._store.atendimentos.values() if a.status in alvos]

    async def listar_todos(self) -> list[Atendimento]:
        return list(self._store.atendimentos.values())

    async def ultimo_do_cliente(self, cliente_id: str) -> Atendimento | None:
        do_cliente = [
            a for a in self._store.atendimentos.values() if a.cliente_id == cliente_id
        ]
        return max(do_cliente, key=lambda a: a.aberto_em) if do_cliente else None

    async def listar_do_cliente(self, cliente_id: str) -> list[Atendimento]:
        do_cliente = [a for a in self._store.atendimentos.values() if a.cliente_id == cliente_id]
        return sorted(do_cliente, key=lambda a: a.aberto_em, reverse=True)

    async def listar_todos_eventos(self) -> list[EventoFriccao]:
        return [e for lista in self._store.eventos.values() for e in lista]

    async def registrar_eventos(self, eventos: list[EventoFriccao]) -> None:
        for evento in eventos:
            self._store.eventos.setdefault(evento.protocolo, []).append(evento)

    async def listar_eventos(self, protocolo: str) -> list[EventoFriccao]:
        return list(self._store.eventos.get(protocolo, []))
