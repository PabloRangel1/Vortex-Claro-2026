"""Testes de integração dos canais de entrada — inclui a continuidade cross-canal."""

from httpx import AsyncClient

from tests.conftest import ANA_APP, RICARDO_APP, enviar_app, enviar_whatsapp


async def test_app_aceita_mensagem_e_abre_protocolo(client: AsyncClient):
    r = await enviar_app(client, "minha internet caiu")
    assert r.status_code == 200
    dados = r.json()
    assert dados["protocolo"].startswith("20")
    assert dados["nome_cliente"] == "Ana Beatriz Souza"
    assert dados["intencao"] == "suporte_tecnico"
    assert dados["sessao_nova"] is True
    assert dados["resposta"]


async def test_whatsapp_aceita_webhook(client: AsyncClient):
    r = await enviar_whatsapp(client, "preciso da segunda via do boleto")
    assert r.status_code == 200
    assert r.json()["intencao"] == "segunda_via"


async def test_identificador_desconhecido_retorna_404(client: AsyncClient):
    r = await enviar_app(client, "oi", usuario_id="user_inexistente")
    assert r.status_code == 404
    assert r.json()["erro"] == "cliente_nao_identificado"


async def test_mensagem_vazia_e_rejeitada(client: AsyncClient):
    r = await client.post("/channels/app", json={"usuario_id": ANA_APP, "mensagem": ""})
    assert r.status_code == 422


# ---------------------------------------------------- continuidade cross-canal


async def test_mesmo_cliente_em_canais_diferentes_compartilha_protocolo(client: AsyncClient):
    """O CORAÇÃO DO PRODUTO: App e WhatsApp escrevem no mesmo atendimento."""
    no_app = (await enviar_app(client, "minha fatura veio errada")).json()
    no_wpp = (await enviar_whatsapp(client, "preciso resolver essa cobrança")).json()

    assert no_wpp["protocolo"] == no_app["protocolo"]
    assert no_wpp["troca_de_canal"] is True
    assert no_wpp["sessao_nova"] is False


async def test_clientes_distintos_nao_se_misturam(client: AsyncClient):
    ana = (await enviar_app(client, "minha internet caiu")).json()
    ricardo = (await enviar_app(client, "minha internet caiu", usuario_id=RICARDO_APP)).json()
    assert ana["protocolo"] != ricardo["protocolo"]


async def test_troca_de_canal_soma_friccao(client: AsyncClient):
    await enviar_app(client, "quero mudar meu vencimento")
    depois = (await enviar_whatsapp(client, "sobre o vencimento da fatura")).json()

    codigos = {s["codigo"] for s in depois["sinais"]}
    assert "troca_canal" in codigos
    assert depois["score_friccao"] > depois["score_anterior"]


async def test_jornada_de_ida_e_volta_mantem_um_unico_protocolo(client: AsyncClient):
    """app → whatsapp → app: três canais visitados, um só atendimento."""
    ida = (await enviar_app(client, "minha internet caiu")).json()
    meio = (await enviar_whatsapp(client, "o técnico já veio?")).json()
    volta = (await enviar_app(client, "continua sem funcionar")).json()

    assert ida["protocolo"] == meio["protocolo"] == volta["protocolo"]
    assert meio["troca_de_canal"] is True
    assert volta["troca_de_canal"] is True

    painel = (await client.get(f"/dashboard/atendimento/{ida['protocolo']}")).json()
    assert painel["canal_origem"] == "app"
    assert painel["canal_atual"] == "app"
    assert painel["houve_troca_de_canal"] is True

    # a descrição da volta aponta o canal ANTERIOR, não o de origem
    trocas = [e for e in painel["eventos_friccao"] if e["codigo_sinal"] == "troca_canal"]
    assert len(trocas) == 2
    assert "App Claro → WhatsApp" in trocas[0]["descricao"]
    assert "WhatsApp → App Claro" in trocas[1]["descricao"]


async def test_permanecer_no_mesmo_canal_nao_gera_sinal_de_troca(client: AsyncClient):
    await enviar_app(client, "quero ver meu plano")
    segunda = (await enviar_app(client, "quanto custa o upgrade?")).json()
    assert segunda["troca_de_canal"] is False


# ------------------------------------------------------------------- handoff


async def test_pedido_de_humano_com_fricção_acumulada_dispara_handoff(client: AsyncClient):
    await enviar_app(client, "minha fatura veio errada, tem cobrança que não reconheço")
    await enviar_app(client, "minha fatura veio errada, tem cobrança que não reconheço")
    await enviar_whatsapp(client, "isso é um absurdo, já expliquei três vezes")
    ultima = (await enviar_whatsapp(client, "QUERO FALAR COM UM ATENDENTE AGORA")).json()

    assert ultima["score_friccao"] >= 70
    assert ultima["nivel"] == "critico"
    assert ultima["handoff_acionado"] is True
    assert ultima["status"] == "aguardando_handoff"
    assert ultima["protocolo"] in ultima["resposta"]


async def test_conversa_tranquila_nao_dispara_handoff(client: AsyncClient):
    r = (await enviar_app(client, "gostaria de adicionar linha no meu plano")).json()
    assert r["handoff_acionado"] is False
    assert r["nivel"] == "estavel"
    assert r["status"] == "bot_ativo"


async def test_handoff_ocorre_uma_unica_vez(client: AsyncClient):
    for _ in range(6):
        r = (await enviar_app(client, "QUERO UM ATENDENTE, isso é um absurdo!")).json()
    # após o primeiro disparo, os turnos seguintes não re-acionam
    assert r["handoff_acionado"] is False
    assert r["score_friccao"] == 100


# ------------------------------------------------------- requisito não-funcional


async def test_latencia_dentro_do_orcamento(client: AsyncClient):
    r = (await enviar_app(client, "minha internet está lenta")).json()
    assert r["latencia_ms"] < 2000
