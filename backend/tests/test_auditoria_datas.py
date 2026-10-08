"""Auditoria de 06/10: o que quebrava com a virada do dia e o reset concorrente."""

import asyncio
from datetime import date, timedelta, timezone

from httpx import AsyncClient

from app.config import Settings
from app.dependencies import Container, get_container
from app.domain.models import agora
from app.main import app
from app.repositories import seed
from app.repositories.seed import _proximo_vencimento
from tests.conftest import enviar_app

BRASILIA = timezone(timedelta(hours=-3))


def test_faturas_da_semente_nunca_nascem_vencidas():
    hoje = agora().astimezone(BRASILIA).date()
    for f in seed.faturas():
        assert f.vencimento >= hoje
        assert f.referencia == f"{f.vencimento.month:02d}/{f.vencimento.year}"


def test_proximo_vencimento_vira_o_mes_e_o_ano():
    assert _proximo_vencimento(15, date(2026, 10, 7)) == date(2026, 10, 15)
    assert _proximo_vencimento(5, date(2026, 10, 7)) == date(2026, 11, 5)
    assert _proximo_vencimento(5, date(2026, 12, 20)) == date(2027, 1, 5)
    assert _proximo_vencimento(20, date(2026, 10, 20)) == date(2026, 10, 20)


async def test_bot_avisa_quando_a_fatura_esta_vencida(client: AsyncClient):
    container = app.dependency_overrides.get(get_container, get_container)()
    fatura = await container.operacao.obter_fatura_atual("52941288900")
    fatura.vencimento = agora().astimezone(BRASILIA).date() - timedelta(days=2)
    await container.operacao.salvar_fatura(fatura)

    r = (await enviar_app(client, "me manda a segunda via")).json()
    assert [a["codigo"] for a in r["acoes"]] == ["segunda_via_vencida"]
    assert "venceu" in r["resposta"] and "multa" in r["resposta"]
    assert r["acoes"][0]["dados"]["vencida"] is True


async def test_serie_diaria_termina_hoje(client: AsyncClient):
    await enviar_app(client, "me manda a segunda via")
    por_dia = (await client.get("/dashboard/estatisticas")).json()["por_dia"]
    assert por_dia[-1]["data"] == agora().astimezone(BRASILIA).date().isoformat()


async def test_dois_resets_ao_mesmo_tempo_rodam_uma_vez(monkeypatch):
    c = Container(Settings(semear_demonstracao=False))
    rodadas = []
    original = Container._resetar

    async def contar(self):
        rodadas.append(1)
        await asyncio.sleep(0.05)
        await original(self)

    monkeypatch.setattr(Container, "_resetar", contar)
    await asyncio.gather(c.resetar(), c.resetar())
    assert len(rodadas) == 1
    await c.resetar()  # terminado o primeiro, um novo reset roda normalmente
    assert len(rodadas) == 2
