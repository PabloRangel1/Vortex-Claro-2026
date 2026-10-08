"""IA como camada de linguagem (Fase 5), com um modelo simulado.

Nenhum teste chama o Gemini: `_chamar_modelo` é trocado por respostas
roteirizadas — inclusive respostas ERRADAS, que o backend precisa barrar.
"""

import pytest
from httpx import AsyncClient

from app.core.privacidade import anonimizar
from app.services.ia_service import IAService
from tests.conftest import enviar_app


@pytest.fixture
def modelo(monkeypatch):
    """Liga a IA com um modelo falso. `modelo.resposta` define o que ele devolve."""

    class Falso:
        resposta: dict | None = None
        contextos: list[dict] = []

    falso = Falso()
    falso.contextos = []

    async def chamar(_self, contexto, _permitidas):
        falso.contextos.append(contexto)
        return falso.resposta

    monkeypatch.setattr(IAService, "disponivel", property(lambda _self: True))
    monkeypatch.setattr(IAService, "_chamar_modelo", chamar)
    return falso


# --------------------------------------------------------------- o que a IA faz


async def test_texto_livre_vira_acao_do_catalogo(client: AsyncClient, modelo):
    modelo.resposta = {"acao_sugerida": "abrir_contestacao", "confirmacao": "indefinido"}
    r = (await enviar_app(client, "minha conta desse mês veio bem mais cara")).json()

    assert r["gerado_por_ia"] is True
    assert [a["codigo"] for a in r["acoes"]] == ["confirmar_contestacao"]


async def test_resposta_livre_sem_acao(client: AsyncClient, modelo):
    modelo.resposta = {
        "acao_sugerida": "nenhuma",
        "confirmacao": "indefinido",
        "resposta_cliente": "Olá! Posso ajudar com fatura, internet ou planos.",
    }
    r = (await enviar_app(client, "oi, tudo bem?")).json()

    assert r["gerado_por_ia"] is True
    assert r["resposta"].startswith("Olá!")


async def test_ia_interpreta_o_dia_pedido(client: AsyncClient, modelo):
    await enviar_app(client, "quero mudar meu vencimento")
    modelo.resposta = {"acao_sugerida": "nenhuma", "confirmacao": "indefinido", "dia": 15}
    r = (await enviar_app(client, "pode ser lá pelo meio do mês")).json()

    assert [a["codigo"] for a in r["acoes"]] == ["confirmar_vencimento"]
    assert "dia 15" in r["resposta"]


async def test_ia_desempata_recusa_ambigua(client: AsyncClient, modelo):
    await enviar_app(client, "minha fatura veio errada")
    modelo.resposta = {"acao_sugerida": "nenhuma", "confirmacao": "sim"}
    r = (await enviar_app(client, "não reconheço essa cobrança de jeito nenhum")).json()

    assert [a["codigo"] for a in r["acoes"]] == ["contestacao_aberta"]


# ------------------------------------------------------------------- barreiras


async def test_ia_nao_decide_handoff(client: AsyncClient, modelo):
    modelo.resposta = {"acao_sugerida": "encaminhar_humano", "confirmacao": "indefinido"}
    r = (await enviar_app(client, "me ajuda com uma coisa estranha aqui")).json()

    assert r["handoff_acionado"] is False
    assert r["gerado_por_ia"] is False  # sugestão descartada, resposta padrão


async def test_texto_com_fato_inventado_e_descartado(client: AsyncClient, modelo):
    modelo.resposta = {
        "acao_sugerida": "nenhuma",
        "confirmacao": "indefinido",
        "resposta_cliente": "Você tem 50% de desconto, protocolo 123456!",
    }
    r = (await enviar_app(client, "e o desconto prometido?")).json()

    assert "123456" not in r["resposta"]
    assert r["gerado_por_ia"] is False


async def test_dia_fora_das_opcoes_e_ignorado(client: AsyncClient, modelo):
    await enviar_app(client, "quero mudar meu vencimento")
    modelo.resposta = {"acao_sugerida": "nenhuma", "confirmacao": "indefinido", "dia": 7}
    r = (await enviar_app(client, "um dia no começo do mês")).json()

    assert r["acoes"] == []
    assert "Não identifiquei o dia" in r["resposta"]


async def test_falha_do_modelo_cai_nas_regras(client: AsyncClient, modelo):
    modelo.resposta = None  # timeout, cota esgotada, JSON inválido...
    r = (await enviar_app(client, "oi, tudo bem?")).json()

    assert r["gerado_por_ia"] is False
    assert r["resposta"]  # o cliente nunca fica sem resposta


# ------------------------------------------------------------------ privacidade


async def test_contexto_nao_leva_dados_pessoais(client: AsyncClient, modelo):
    modelo.resposta = None
    await enviar_app(client, "meu cpf é 529.412.889-00 e o fone (11) 99887-7321, me ajuda")

    enviado = str(modelo.contextos[-1])
    for dado in ("529.412.889-00", "99887-7321", "Ana", "52941288900", "user_ana"):
        assert dado not in enviado


def test_anonimizar_preserva_valores_e_dias():
    texto = anonimizar("cobrança de R$ 60,00 no dia 15; cpf 529.412.889-00; ana@exemplo.com")
    assert "R$ 60,00" in texto and "dia 15" in texto
    assert "529.412.889-00" not in texto and "ana@exemplo.com" not in texto
