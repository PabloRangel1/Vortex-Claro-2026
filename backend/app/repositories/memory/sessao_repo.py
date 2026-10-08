"""Equivalente in-memory do Redis.

O TTL é emulado guardando `expira_em` junto do valor e checando na leitura —
que é exatamente a semântica que o Redis dá de graça. Quando trocarmos, esta
classe some e o `SessaoService` não percebe.
"""

from datetime import datetime, timedelta, timezone

from app.domain.models import Sessao
from app.repositories.base import SessaoRepository
from app.repositories.memory.store import MemoryStore


class MemSessaoRepository(SessaoRepository):
    def __init__(self, store: MemoryStore) -> None:
        self._store = store

    async def obter(self, cliente_id: str) -> Sessao | None:
        registro = self._store.sessoes.get(cliente_id)
        if registro is None:
            return None
        sessao, expira_em = registro
        if datetime.now(timezone.utc) >= expira_em:
            del self._store.sessoes[cliente_id]  # expiração preguiçosa, como o Redis
            return None
        return sessao

    async def salvar(self, sessao: Sessao, ttl_segundos: int) -> None:
        expira_em = datetime.now(timezone.utc) + timedelta(seconds=ttl_segundos)
        self._store.sessoes[sessao.cliente_id] = (sessao, expira_em)

    async def remover(self, cliente_id: str) -> None:
        self._store.sessoes.pop(cliente_id, None)
