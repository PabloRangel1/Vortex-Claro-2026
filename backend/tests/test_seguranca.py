"""Regressões de segurança."""

import pytest
from httpx import AsyncClient

from app.main import DIST



@pytest.mark.skipif(not DIST.is_dir(), reason="frontend não compilado")
@pytest.mark.parametrize(
    ("rota", "trecho_do_arquivo"),
    [
        ("/..%2F..%2Fbackend%2F.env.example", "LIMIAR_HANDOFF"),
        ("/..%2F..%2Fbackend%2Fapp%2Fconfig.py", "class Settings"),
        ("/%2E%2E%2F%2E%2E%2FCONTEXTO.md", "Briefing de Contexto"),
        ("/assets%2F..%2F..%2F..%2Fbackend%2Fpyproject.toml", "[project]"),
    ],
)
async def test_nenhuma_rota_serve_arquivo_fora_do_dist(
    client: AsyncClient, rota: str, trecho_do_arquivo: str
):
    """Sem isso, o .env (senha do banco e chave da IA) saía por uma URL pública."""
    r = await client.get(rota)
    assert r.status_code in (200, 404)  # index.html da SPA, ou 404 do /assets
    assert trecho_do_arquivo not in r.text


# ------------------------------------------- dados pessoais (auditoria 05/10)

from app.core.referencia import referencia  # noqa: E402
from app.repositories.seed import CLIENTES_SEED  # noqa: E402
from app.services.ia_service import IAService  # noqa: E402
from tests.conftest import enviar_app, enviar_whatsapp  # noqa: E402

CPFS = [c.cliente_id for c in CLIENTES_SEED]


async def test_api_nunca_devolve_cpf_completo(client: AsyncClient):
    """O CPF é a chave interna; para fora só sai a referência opaca."""
    r = await enviar_app(client, "me manda a segunda via")
    p = r.json()["protocolo"]
    await enviar_app(client, "quero falar com um atendente", usuario_id="user_ricardo")
    ref = (await client.get("/clientes")).json()[0]["cliente_ref"]

    respostas = [
        r.text,
        (await client.get("/clientes")).text,
        (await client.get("/dashboard/fila")).text,
        (await client.get(f"/dashboard/atendimento/{p}")).text,
        (await client.get("/dashboard/clientes")).text,
        (await client.get(f"/dashboard/clientes/{ref}/historico")).text,
        (await client.get(f"/dashboard/protocolo/{p}")).text,
    ]
    for texto in respostas:
        for cpf in CPFS:
            assert cpf not in texto


def test_referencia_e_estavel_e_nao_revela_o_cpf():
    assert referencia("52941288900") == referencia("52941288900")
    assert referencia("52941288900") != referencia("38177100402")
    assert "529412" not in referencia("52941288900")


async def test_ia_nao_recebe_nome_nem_digitos_da_verificacao(client: AsyncClient, monkeypatch):
    """Achado da auditoria: "Obrigado, Ana!" e o "529" iam para o Gemini."""
    enviados = []

    async def modelo(_self, contexto, _permitidas):
        enviados.append(contexto)
        return None

    monkeypatch.setattr(IAService, "disponivel", property(lambda _self: True))
    monkeypatch.setattr(IAService, "_chamar_modelo", modelo)

    for m in ("oi", "529", "minha conta desse mês veio bem mais cara que o normal"):
        await enviar_whatsapp(client, m)

    contexto = str(enviados[-1])
    assert "Ana" not in contexto and "Beatriz" not in contexto and "Souza" not in contexto
    assert "529" not in contexto
    assert "[nome]" in contexto  # o cumprimento foi mantido, só sem o nome
