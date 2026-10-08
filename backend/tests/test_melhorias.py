"""Métricas de autoatendimento, regras do CSAT, reset protegido e histórico do cliente."""

import pytest
from httpx import AsyncClient

from app.config import Settings, get_settings
from app.main import app
from tests.conftest import enviar_app

# ----------------------------------------------------- métricas de autoatendimento


async def test_estatisticas_medem_resolucao_sem_humano(client: AsyncClient):
    await enviar_app(client, "me manda a segunda via da fatura")  # Ana: resolve sozinha
    await enviar_app(client, "quero falar com um atendente", usuario_id="user_ricardo")

    auto = (await client.get("/dashboard/estatisticas")).json()["autoatendimento"]

    assert auto["resolvidos_sem_humano"] == 1
    assert auto["taxa_resolucao"] == 50
    assert auto["acoes_executadas"] == 1
    assert auto["por_acao"][0]["acao"] == "gerar_segunda_via"


async def test_encaminhar_a_humano_nao_conta_como_acao_resolvida(client: AsyncClient):
    await enviar_app(client, "quero cancelar meu plano")
    auto = (await client.get("/dashboard/estatisticas")).json()["autoatendimento"]
    assert auto["acoes_executadas"] == 0
    assert auto["por_acao"] == []


async def test_resolveu_mas_depois_pediu_humano_nao_conta(client: AsyncClient):
    await enviar_app(client, "me manda a segunda via da fatura")
    await enviar_app(client, "quero falar com um atendente")

    auto = (await client.get("/dashboard/estatisticas")).json()["autoatendimento"]
    assert auto["resolvidos_sem_humano"] == 0


async def test_estatisticas_vazias_tem_bloco_de_autoatendimento(client: AsyncClient):
    auto = (await client.get("/dashboard/estatisticas")).json()["autoatendimento"]
    assert auto["taxa_resolucao"] == 0 and auto["por_acao"] == []


# ------------------------------------------------------------------------ CSAT


async def test_nao_avalia_atendimento_em_aberto(client: AsyncClient):
    p = (await enviar_app(client, "me manda a segunda via")).json()["protocolo"]
    r = await client.post(f"/dashboard/atendimento/{p}/avaliar", json={"nota": 1})
    assert r.status_code == 400


async def test_nao_avalia_duas_vezes(client: AsyncClient):
    p = (await enviar_app(client, "me manda a segunda via")).json()["protocolo"]
    await client.post(f"/dashboard/atendimento/{p}/encerrar")
    await client.post(f"/dashboard/atendimento/{p}/avaliar", json={"nota": 5})

    r = await client.post(f"/dashboard/atendimento/{p}/avaliar", json={"nota": 1})
    assert r.status_code == 400
    d = (await client.get(f"/dashboard/atendimento/{p}")).json()
    assert d["avaliacao"]["nota"] == 5


# ----------------------------------------------------------------------- reset


@pytest.fixture
def configurar():
    def aplicar(**valores):
        app.dependency_overrides[get_settings] = lambda: Settings(**valores)

    yield aplicar
    app.dependency_overrides.pop(get_settings, None)


async def test_reset_exige_token_quando_configurado(client: AsyncClient, configurar):
    configurar(admin_token="segredo")

    assert (await client.post("/reset")).status_code == 403
    assert (await client.post("/reset", headers={"X-Admin-Token": "errado"})).status_code == 403
    assert (await client.post("/reset", headers={"X-Admin-Token": "segredo"})).status_code == 200
    assert (await client.get("/health")).json()["reset_protegido"] is True


async def test_reset_fica_desligado_em_producao_sem_token(client: AsyncClient, configurar):
    configurar(ambiente="producao", admin_token=None)
    assert (await client.post("/reset")).status_code == 403


async def test_reset_aberto_em_desenvolvimento(client: AsyncClient):
    assert (await client.post("/reset")).status_code == 200
    assert (await client.get("/health")).json()["reset_protegido"] is False


# ------------------------------------------------------- histórico do cliente


async def test_painel_mostra_contatos_anteriores(client: AsyncClient):
    p1 = (await enviar_app(client, "me manda a segunda via")).json()["protocolo"]
    await client.post(f"/dashboard/atendimento/{p1}/encerrar")
    p2 = (await enviar_app(client, "quero falar com um atendente")).json()["protocolo"]

    painel = (await client.get(f"/dashboard/atendimento/{p2}")).json()

    assert painel["contatos_30_dias"] == 2
    assert [c["protocolo"] for c in painel["contatos_anteriores"]] == [p1]
    assert painel["contatos_anteriores"][0]["status"] == "encerrado"


async def test_historico_nao_mistura_clientes(client: AsyncClient):
    await enviar_app(client, "me manda a segunda via", usuario_id="user_ricardo")
    p = (await enviar_app(client, "me manda a segunda via")).json()["protocolo"]

    painel = (await client.get(f"/dashboard/atendimento/{p}")).json()
    assert painel["contatos_30_dias"] == 1
    assert painel["contatos_anteriores"] == []
