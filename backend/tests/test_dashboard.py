"""Testes de integração do painel do atendente."""

from httpx import AsyncClient

from tests.conftest import enviar_app, enviar_whatsapp


async def _cenario_handoff(client: AsyncClient) -> str:
    """Constrói um atendimento crítico que passou pelos dois canais."""
    await enviar_app(client, "minha fatura veio errada, tem cobrança que não reconheço")
    await enviar_app(client, "minha fatura veio errada, tem cobrança que não reconheço")
    await enviar_whatsapp(client, "isso é um absurdo, já expliquei três vezes")
    r = await enviar_whatsapp(client, "QUERO FALAR COM UM ATENDENTE AGORA")
    return r.json()["protocolo"]


async def test_atendimento_inexistente_retorna_404(client: AsyncClient):
    r = await client.get("/dashboard/atendimento/2026-0101-00000")
    assert r.status_code == 404


async def test_payload_do_painel_esta_completo(client: AsyncClient):
    protocolo = await _cenario_handoff(client)
    dados = (await client.get(f"/dashboard/atendimento/{protocolo}")).json()

    assert dados["protocolo"] == protocolo
    assert dados["cliente"]["nome"] == "Ana Beatriz Souza"
    assert dados["cliente"]["cpf_mascarado"].startswith("***")

    # canal de origem e histórico de troca
    assert dados["canal_origem"] == "app"
    assert dados["canal_atual"] == "whatsapp"
    assert dados["houve_troca_de_canal"] is True
    assert set(dados["canais_utilizados"]) == {"app", "whatsapp"}

    # a intenção consolidada preserva a demanda REAL, não o último turno genérico
    assert dados["intencao"] == "contestacao_fatura"
    assert dados["confianca"] > 0
    assert dados["score_friccao"] >= 70
    assert dados["nivel"] == "critico"
    assert len(dados["historico_score"]) > 1
    assert dados["delta_score"] > 0

    # handoff
    assert dados["handoff"]["acionado"] is True
    assert dados["handoff"]["motivo"]

    # histórico completo e auditoria
    assert dados["total_mensagens"] == len(dados["mensagens"])
    assert dados["eventos_friccao"]


async def test_historico_preserva_as_mensagens_dos_dois_canais(client: AsyncClient):
    protocolo = await _cenario_handoff(client)
    mensagens = (await client.get(f"/dashboard/atendimento/{protocolo}")).json()["mensagens"]

    do_cliente = [m for m in mensagens if m["remetente"] == "cliente"]
    canais = {m["canal"] for m in do_cliente}
    assert canais == {"app", "whatsapp"}
    # é isso que evita pedir para o cliente repetir
    assert any("não reconheço" in m["conteudo"] for m in do_cliente)


async def test_troca_de_canal_vira_evento_na_timeline(client: AsyncClient):
    protocolo = await _cenario_handoff(client)
    mensagens = (await client.get(f"/dashboard/atendimento/{protocolo}")).json()["mensagens"]
    tipos = {m["metadados"].get("tipo") for m in mensagens if m["remetente"] == "sistema"}
    assert "troca_canal" in tipos
    assert "handoff" in tipos


async def test_eventos_de_friccao_sao_auditaveis(client: AsyncClient):
    protocolo = await _cenario_handoff(client)
    eventos = (await client.get(f"/dashboard/atendimento/{protocolo}")).json()["eventos_friccao"]

    assert {"pedido_humano", "troca_canal"} <= {e["codigo_sinal"] for e in eventos}
    for e in eventos:
        assert e["descricao"] and e["criado_em"]


# ---------------------------------------------------------------------- fila


async def test_fila_vazia_quando_ninguem_aguarda(client: AsyncClient):
    await enviar_app(client, "quero adicionar linha no plano")
    assert (await client.get("/dashboard/fila")).json() == []


async def test_fila_lista_quem_aguarda_handoff(client: AsyncClient):
    protocolo = await _cenario_handoff(client)
    fila = (await client.get("/dashboard/fila")).json()

    assert len(fila) == 1
    item = fila[0]
    assert item["protocolo"] == protocolo
    assert item["nome"] == "Ana Beatriz Souza"
    assert item["nivel"] == "critico"
    assert item["houve_troca_de_canal"] is True
    assert item["espera_segundos"] >= 0
    assert item["ultima_mensagem"]


async def test_fila_ordena_por_score_decrescente(client: AsyncClient):
    await _cenario_handoff(client)
    # segundo cliente, também crítico mas com menos acúmulo
    for _ in range(4):
        await enviar_app(client, "QUERO UM ATENDENTE, que absurdo!", usuario_id="user_ricardo")

    fila = (await client.get("/dashboard/fila")).json()
    scores = [i["score_friccao"] for i in fila]
    assert scores == sorted(scores, reverse=True)


# ------------------------------------------------------- resposta do atendente


async def test_atendente_responde_e_reduz_friccao(client: AsyncClient):
    protocolo = await _cenario_handoff(client)
    antes = (await client.get(f"/dashboard/atendimento/{protocolo}")).json()["score_friccao"]

    r = await client.post(
        f"/dashboard/atendimento/{protocolo}/responder",
        json={"conteudo": "Olá Ana, já localizei a cobrança. Vou estornar agora.", "atendente": "Marcos Ribeiro"},
    )
    assert r.status_code == 200
    depois = r.json()

    assert depois["score_friccao"] < antes
    assert depois["status"] == "em_atendimento_humano"
    assert depois["atendente"] == "Marcos Ribeiro"
    assert depois["mensagens"][-1]["remetente"] == "atendente"


async def test_encerrar_libera_a_sessao(client: AsyncClient):
    protocolo = await _cenario_handoff(client)
    r = await client.post(f"/dashboard/atendimento/{protocolo}/encerrar")
    assert r.json()["status"] == "encerrado"

    # sessão liberada -> próximo contato abre protocolo novo
    novo = (await enviar_app(client, "oi, outra dúvida")).json()
    assert novo["protocolo"] != protocolo
    assert novo["sessao_nova"] is True


# -------------------------------------------------------------------- sistema


async def test_health(client: AsyncClient):
    assert (await client.get("/health")).json()["status"] == "ok"


async def test_config_expoe_pesos(client: AsyncClient):
    dados = (await client.get("/config")).json()
    assert dados["limiar_handoff"] == 70
    assert dados["pesos"]["pedido_humano"] > 0
