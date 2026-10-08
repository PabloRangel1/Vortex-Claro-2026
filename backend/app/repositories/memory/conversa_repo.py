"""Equivalente in-memory da coleção MongoDB `conversas`.

O documento final terá o shape:
    {"_id": protocolo, "cliente_id": ..., "mensagens": [ {...}, {...} ]}
Aqui, `conversas[protocolo]` é exatamente esse array `mensagens`.
"""

from app.domain.enums import Remetente
from app.domain.models import Mensagem
from app.repositories.base import ConversaRepository
from app.repositories.memory.store import MemoryStore


class MemConversaRepository(ConversaRepository):
    def __init__(self, store: MemoryStore) -> None:
        self._store = store

    async def adicionar_mensagem(self, mensagem: Mensagem) -> Mensagem:
        self._store.conversas.setdefault(mensagem.protocolo, []).append(mensagem)
        return mensagem

    async def listar_mensagens(self, protocolo: str) -> list[Mensagem]:
        return list(self._store.conversas.get(protocolo, []))

    async def ultimas_do_cliente(self, protocolo: str, limite: int) -> list[Mensagem]:
        mensagens = self._store.conversas.get(protocolo, [])
        do_cliente = [m for m in mensagens if m.remetente == Remetente.CLIENTE]
        return do_cliente[-limite:] if limite > 0 else do_cliente

    async def contar(self, protocolo: str) -> int:
        return len(self._store.conversas.get(protocolo, []))

    async def listar_registros_autoatendimento(self) -> list[Mensagem]:
        return [
            m
            for lista in self._store.conversas.values()
            for m in lista
            if m.metadados.get("tipo") == "acao" or m.metadados.get("ia") is True
        ]
