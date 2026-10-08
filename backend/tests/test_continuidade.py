"""Continuidade do atendimento em situações de borda (auditoria de 05/10/2026)."""

import pytest
from httpx import AsyncClient

from app import dependencies
from app.config import Settings
from app.dependencies import get_container
from app.main import app
from app.repositories import postgres
from tests.conftest import enviar_app

ANA = "52941288900"


async def _forcar_handoff(client: AsyncClient) -> str:
    await enviar_app(client, "minha fatura veio errada")
    return (await enviar_app(client, "QUERO FALAR COM UM ATENDENTE")).json()["protocolo"]


async def _expirar_sessao() -> None:
    # O mesmo container que a API usa — inclusive quando um override de
    # dependência o troca (ex.: rodando a suíte contra o PostgreSQL).
    container = app.dependency_overrides.get(get_container, get_container)()
    await container.sessoes_repo.remover(ANA)


# ------------------------------------------------------- sessão expirada


async def test_cliente_esperando_humano_volta_ao_mesmo_protocolo(client: AsyncClient):
    """Sessão de 30 min vence enquanto o cliente espera na fila: o histórico
    não pode se partir em dois protocolos."""
    protocolo = await _forcar_handoff(client)
    await _expirar_sessao()

    r = (await enviar_app(client, "alguém vai me atender?")).json()

    assert r["protocolo"] == protocolo
    assert r["status"] == "aguardando_handoff"
    assert r["sessao_nova"] is False
    fila = (await client.get("/dashboard/fila")).json()
    assert [f["protocolo"] for f in fila] == [protocolo]


async def test_cliente_com_atendente_volta_ao_mesmo_protocolo(client: AsyncClient):
    protocolo = await _forcar_handoff(client)
    await client.post(
        f"/dashboard/atendimento/{protocolo}/responder", json={"conteudo": "Olá, Ana!"}
    )
    await _expirar_sessao()

    r = (await enviar_app(client, "voltei")).json()
    assert r["protocolo"] == protocolo
    assert r["status"] == "em_atendimento_humano"


async def test_conversa_abandonada_com_bot_abre_protocolo_novo(client: AsyncClient):
    """Só o que está com humano é retomado; conversa com o bot que expirou acabou."""
    antigo = (await enviar_app(client, "me manda a segunda via")).json()["protocolo"]
    await _expirar_sessao()

    novo = (await enviar_app(client, "quero mudar meu vencimento")).json()
    assert novo["protocolo"] != antigo
    assert novo["sessao_nova"] is True


# --------------------------------------------------------------- encerrar


async def test_encerrar_de_novo_protocolo_antigo_nao_derruba_conversa_nova(client: AsyncClient):
    antigo = (await enviar_app(client, "me manda a segunda via")).json()["protocolo"]
    await client.post(f"/dashboard/atendimento/{antigo}/encerrar")
    novo = (await enviar_app(client, "quero mudar meu vencimento")).json()["protocolo"]

    await client.post(f"/dashboard/atendimento/{antigo}/encerrar")  # aba velha / duplo clique

    seguinte = (await enviar_app(client, "Dia 15")).json()
    assert seguinte["protocolo"] == novo
    assert seguinte["acoes"][0]["codigo"] == "confirmar_vencimento"  # o fluxo seguiu


async def test_encerrar_e_idempotente(client: AsyncClient):
    protocolo = (await enviar_app(client, "me manda a segunda via")).json()["protocolo"]
    await client.post(f"/dashboard/atendimento/{protocolo}/encerrar")
    antes = (await client.get(f"/dashboard/atendimento/{protocolo}")).json()

    r = await client.post(f"/dashboard/atendimento/{protocolo}/encerrar")
    depois = (await client.get(f"/dashboard/atendimento/{protocolo}")).json()

    assert r.status_code == 200
    assert depois["encerrado_em"] == antes["encerrado_em"]
    encerramentos = [
        m for m in depois["mensagens"] if m["metadados"].get("tipo") == "encerramento"
    ]
    assert len(encerramentos) == 1


# ------------------------------------------------------- banco na subida


@pytest.fixture
def sem_espera(monkeypatch):
    monkeypatch.setattr(dependencies, "ESPERAS_CONEXAO", (0, 0, 0))


class _PoolFalso:
    async def close(self):
        pass


async def test_subida_tenta_de_novo_ate_o_banco_responder(monkeypatch, sem_espera):
    tentativas = []

    async def criar_pool(_url):
        tentativas.append(1)
        if len(tentativas) < 3:
            raise OSError("banco acordando")
        return _PoolFalso()

    async def preparar(_pool):
        pass

    monkeypatch.setattr(postgres, "criar_pool", criar_pool)
    monkeypatch.setattr(postgres, "preparar_banco", preparar)
    monkeypatch.setattr(postgres, "semear_faltantes", preparar)

    await dependencies.iniciar_persistencia(Settings(database_url="postgresql://falso"))

    assert len(tentativas) == 3
    assert get_container().persistencia == "postgresql"


async def test_subida_desiste_depois_de_todas_as_tentativas(monkeypatch, sem_espera):
    """Desistir é melhor que cair para memória em silêncio e perder dados."""
    tentativas = []

    async def criar_pool(_url):
        tentativas.append(1)
        raise OSError("banco fora do ar")

    monkeypatch.setattr(postgres, "criar_pool", criar_pool)

    with pytest.raises(OSError):
        await dependencies.iniciar_persistencia(Settings(database_url="postgresql://falso"))
    assert len(tentativas) == 4  # 3 esperas + a última tentativa
