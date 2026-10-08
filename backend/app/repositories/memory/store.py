"""O "banco de dados" desta fase: dicionários Python.

Cada atributo do MemoryStore corresponde a um destino futuro:

    clientes      -> PostgreSQL  tabela `clientes`
    atendimentos  -> PostgreSQL  tabela `atendimentos`
    eventos       -> PostgreSQL  tabela `eventos_friccao`
    conversas     -> PostgreSQL  tabela `mensagens`
    sessoes       -> PostgreSQL  tabela `sessoes` (o datetime é o expira_em)
    faturas       -> PostgreSQL  tabela `faturas`
    equipamentos  -> PostgreSQL  tabela `equipamentos`
    planos        -> PostgreSQL  tabela `planos`
    solicitacoes  -> PostgreSQL  tabela `solicitacoes`

Os dados fictícios de demonstração vivem em `app/repositories/seed.py`.
"""

from dataclasses import dataclass, field
from datetime import datetime

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
from app.repositories import seed


@dataclass
class MemoryStore:
    clientes: dict[str, Cliente] = field(default_factory=dict)
    # (canal, identificador) -> cliente_id  — índice secundário, vira UNIQUE no PG
    indice_identificadores: dict[tuple[str, str], str] = field(default_factory=dict)

    sessoes: dict[str, tuple[Sessao, datetime]] = field(default_factory=dict)
    conversas: dict[str, list[Mensagem]] = field(default_factory=dict)
    atendimentos: dict[str, Atendimento] = field(default_factory=dict)
    eventos: dict[str, list[EventoFriccao]] = field(default_factory=dict)

    # Autoatendimento — chaveados por cliente_id, exceto o catálogo de planos
    faturas: dict[str, Fatura] = field(default_factory=dict)
    equipamentos: dict[str, Equipamento] = field(default_factory=dict)
    planos: dict[str, Plano] = field(default_factory=dict)
    solicitacoes: dict[str, list[Solicitacao]] = field(default_factory=dict)

    def limpar(self) -> None:
        self.clientes.clear()
        self.indice_identificadores.clear()
        self.sessoes.clear()
        self.conversas.clear()
        self.atendimentos.clear()
        self.eventos.clear()
        # Sem estes, POST /reset devolveria dados operacionais já alterados.
        self.faturas.clear()
        self.equipamentos.clear()
        self.planos.clear()
        self.solicitacoes.clear()


def semear(store: MemoryStore) -> None:
    """Popula clientes e dados operacionais fictícios.

    Clientes entram como CÓPIAS profundas do seed: upgrade e alteração de
    vencimento mudam o `Cliente`, e mutar a constante de módulo contaminaria
    todo reset seguinte.
    """
    for base in seed.CLIENTES_SEED:
        cliente = base.model_copy(deep=True)
        store.clientes[cliente.cliente_id] = cliente
        for canal, identificador in cliente.identificadores.items():
            store.indice_identificadores[(str(canal), identificador)] = cliente.cliente_id

    for plano in seed.planos():
        store.planos[plano.id] = plano
    for fatura in seed.faturas():
        store.faturas[fatura.cliente_id] = fatura
    for equipamento in seed.equipamentos():
        store.equipamentos[equipamento.cliente_id] = equipamento
