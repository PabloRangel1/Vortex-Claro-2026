"""Equivalente in-memory da tabela PostgreSQL `clientes`."""

from app.domain.enums import Canal
from app.domain.models import Cliente
from app.repositories.base import ClienteRepository
from app.repositories.memory.store import MemoryStore


class MemClienteRepository(ClienteRepository):
    def __init__(self, store: MemoryStore) -> None:
        self._store = store

    async def obter(self, cliente_id: str) -> Cliente | None:
        return self._store.clientes.get(cliente_id)

    async def resolver_por_identificador(self, canal: Canal, identificador: str) -> Cliente | None:
        cliente_id = self._store.indice_identificadores.get((str(canal), identificador))
        if cliente_id is None:
            return None
        return self._store.clientes.get(cliente_id)

    async def salvar(self, cliente: Cliente) -> Cliente:
        self._store.clientes[cliente.cliente_id] = cliente
        for canal, identificador in cliente.identificadores.items():
            self._store.indice_identificadores[(str(canal), identificador)] = cliente.cliente_id
        return cliente

    async def listar(self) -> list[Cliente]:
        return list(self._store.clientes.values())
