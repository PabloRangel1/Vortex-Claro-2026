"""Transferência entre setores, encerramento, avaliação do cliente e estatísticas."""

from httpx import AsyncClient

from tests.conftest import enviar_app, enviar_whatsapp


async def _abrir(client: AsyncClient, msg: str = "minha fatura veio errada") -> str:
    return (await enviar_app(client, msg)).json()["protocolo"]


async def _forcar_handoff(client: AsyncClient) -> str:
    await enviar_app(client, "minha fatura veio errada, tem cobrança que não reconheço")
    await enviar_app(client, "tem uma cobrança que não reconheço na minha fatura")
    await enviar_whatsapp(client, "isso é um absurdo, já expliquei três vezes")
    return (await enviar_whatsapp(client, "QUERO FALAR COM UM ATENDENTE")).json()["protocolo"]


# ------------------------------------------------------------------ transferir


async def test_setores_disponiveis(client: AsyncClient):
    setores = (await client.get("/dashboard/setores")).json()
    assert {s["valor"] for s in setores} == {
        "suporte_tecnico", "financeiro", "retencao", "ouvidoria"
    }
    assert all(s["rotulo"] for s in setores)


async def test_transferir_muda_setor_e_devolve_para_fila(client: AsyncClient):
    protocolo = await _forcar_handoff(client)
    await client.post(
        f"/dashboard/atendimento/{protocolo}/responder",
        json={"conteudo": "Oi Ana, vou verificar.", "atendente": "Marcos Ribeiro"},
    )

    r = await client.post(
        f"/dashboard/atendimento/{protocolo}/transferir",
        json={"setor": "financeiro", "motivo": "Caso de contestação", "por": "Marcos Ribeiro"},
    )
    assert r.status_code == 200
    d = r.json()

    assert d["setor"] == "financeiro"
    assert d["setor_rotulo"] == "Financeiro"
    assert d["transferencias"] == 1
    assert d["status"] == "aguardando_handoff"   # volta para a fila
    assert d["atendente"] is None                # o anterior foi liberado


async def test_transferir_preserva_protocolo_e_historico(client: AsyncClient):
    """Transferir não é encerrar: o contexto é justamente o que deve sobreviver."""
    protocolo = await _forcar_handoff(client)
    antes = (await client.get(f"/dashboard/atendimento/{protocolo}")).json()

    await client.post(
        f"/dashboard/atendimento/{protocolo}/transferir", json={"setor": "retencao"}
    )
    depois = (await client.get(f"/dashboard/atendimento/{protocolo}")).json()

    assert depois["protocolo"] == protocolo
    assert depois["total_mensagens"] > antes["total_mensagens"]  # ganhou o registro
    assert depois["score_friccao"] == antes["score_friccao"]     # transferir não pontua

    tipos = [m["metadados"].get("tipo") for m in depois["mensagens"]]
    assert "transferencia" in tipos


async def test_transferencia_aparece_na_fila_com_setor(client: AsyncClient):
    protocolo = await _forcar_handoff(client)
    await client.post(
        f"/dashboard/atendimento/{protocolo}/transferir", json={"setor": "ouvidoria"}
    )
    item = next(
        i for i in (await client.get("/dashboard/fila")).json()
        if i["protocolo"] == protocolo
    )
    assert item["setor_rotulo"] == "Ouvidoria"


async def test_transferir_atendimento_encerrado_falha(client: AsyncClient):
    protocolo = await _abrir(client)
    await client.post(f"/dashboard/atendimento/{protocolo}/encerrar")
    r = await client.post(
        f"/dashboard/atendimento/{protocolo}/transferir", json={"setor": "financeiro"}
    )
    assert r.status_code == 409


async def test_setor_invalido_e_rejeitado(client: AsyncClient):
    protocolo = await _abrir(client)
    r = await client.post(
        f"/dashboard/atendimento/{protocolo}/transferir", json={"setor": "marketing"}
    )
    assert r.status_code == 422


# ------------------------------------------------------------------- encerrar


async def test_encerrar_marca_status_e_registra_evento(client: AsyncClient):
    protocolo = await _abrir(client)
    r = await client.post(f"/dashboard/atendimento/{protocolo}/encerrar")
    assert r.json()["status"] == "encerrado"

    d = (await client.get(f"/dashboard/atendimento/{protocolo}")).json()
    assert d["encerrado_em"] is not None
    tipos = [m["metadados"].get("tipo") for m in d["mensagens"]]
    assert "encerramento" in tipos


async def test_encerrar_libera_sessao(client: AsyncClient):
    protocolo = await _abrir(client)
    await client.post(f"/dashboard/atendimento/{protocolo}/encerrar")
    novo = (await enviar_app(client, "outra dúvida")).json()
    assert novo["protocolo"] != protocolo
    assert novo["sessao_nova"] is True


async def test_encerrar_sai_da_fila(client: AsyncClient):
    protocolo = await _forcar_handoff(client)
    assert any(i["protocolo"] == protocolo for i in (await client.get("/dashboard/fila")).json())

    await client.post(f"/dashboard/atendimento/{protocolo}/encerrar")
    assert not any(
        i["protocolo"] == protocolo for i in (await client.get("/dashboard/fila")).json()
    )


# -------------------------------------------------------------------- avaliar


async def test_cliente_avalia_atendimento(client: AsyncClient):
    protocolo = await _abrir(client)
    await client.post(f"/dashboard/atendimento/{protocolo}/encerrar")

    r = await client.post(
        f"/dashboard/atendimento/{protocolo}/avaliar",
        json={"nota": 5, "comentario": "Resolveram rápido"},
    )
    assert r.status_code == 200

    d = (await client.get(f"/dashboard/atendimento/{protocolo}")).json()
    assert d["avaliacao"]["nota"] == 5
    assert d["avaliacao"]["comentario"] == "Resolveram rápido"
    assert d["avaliacao"]["em"] is not None


async def test_avaliacao_sem_comentario(client: AsyncClient):
    protocolo = await _abrir(client)
    await client.post(f"/dashboard/atendimento/{protocolo}/encerrar")
    await client.post(f"/dashboard/atendimento/{protocolo}/avaliar", json={"nota": 3})

    d = (await client.get(f"/dashboard/atendimento/{protocolo}")).json()
    assert d["avaliacao"]["nota"] == 3
    assert d["avaliacao"]["comentario"] is None


async def test_nota_fora_da_faixa_e_rejeitada(client: AsyncClient):
    protocolo = await _abrir(client)
    for nota in (0, 6, -1):
        r = await client.post(
            f"/dashboard/atendimento/{protocolo}/avaliar", json={"nota": nota}
        )
        assert r.status_code == 422, f"nota {nota} deveria ser rejeitada"


async def test_avaliar_protocolo_inexistente(client: AsyncClient):
    r = await client.post("/dashboard/atendimento/2026-0101-00000/avaliar", json={"nota": 4})
    assert r.status_code == 404


# --------------------------------------------------------------- estatísticas


async def test_estatisticas_vazias_nao_quebram(client: AsyncClient):
    d = (await client.get("/dashboard/estatisticas")).json()
    assert d["resumo"]["total_atendimentos"] == 0
    assert d["por_intencao"] == []
    # As três faixas existem mesmo sem dados, senão o gráfico muda de forma.
    assert [n["nivel"] for n in d["por_nivel"]] == ["estavel", "atencao", "critico"]
    assert d["csat"]["total_avaliacoes"] == 0


async def test_estatisticas_agrupam_por_intencao(client: AsyncClient):
    await enviar_app(client, "minha internet caiu de novo")
    await enviar_app(client, "quero a segunda via do boleto", usuario_id="user_ricardo")
    await enviar_app(client, "minha internet está lenta", usuario_id="user_juliana")

    d = (await client.get("/dashboard/estatisticas")).json()
    assert d["resumo"]["total_atendimentos"] == 3

    por_intencao = {i["intencao"]: i for i in d["por_intencao"]}
    assert por_intencao["suporte_tecnico"]["total"] == 2
    assert por_intencao["segunda_via"]["total"] == 1
    # ordenado por volume decrescente
    assert d["por_intencao"][0]["total"] >= d["por_intencao"][-1]["total"]


async def test_estatisticas_contam_handoff_e_sinais(client: AsyncClient):
    await _forcar_handoff(client)
    d = (await client.get("/dashboard/estatisticas")).json()

    assert d["resumo"]["handoffs"] == 1
    assert d["resumo"]["taxa_handoff"] == 100
    assert d["resumo"]["troca_de_canal"] == 1

    codigos = {s["codigo"] for s in d["sinais"]}
    assert "troca_canal" in codigos
    assert all(s["rotulo"] and s["ocorrencias"] > 0 for s in d["sinais"])


async def test_estatisticas_distribuem_por_nivel(client: AsyncClient):
    # Clientes diferentes de propósito: o mesmo cliente cairia no mesmo
    # protocolo — que é o comportamento correto, mas daria um atendimento só.
    await enviar_app(client, "quero adicionar linha no plano", usuario_id="user_carlos")
    await _forcar_handoff(client)  # Ana, via app e whatsapp

    niveis = {n["nivel"]: n for n in (await client.get("/dashboard/estatisticas")).json()["por_nivel"]}
    assert niveis["estavel"]["total"] == 1
    assert niveis["critico"]["total"] == 1
    assert sum(n["total"] for n in niveis.values()) == 2
    assert sum(n["percentual"] for n in niveis.values()) == 100


async def test_estatisticas_consolidam_csat(client: AsyncClient):
    for usuario, nota in [("user_ana", 5), ("user_ricardo", 4), ("user_juliana", 2)]:
        r = await enviar_app(client, "minha internet caiu", usuario_id=usuario)
        p = r.json()["protocolo"]
        await client.post(f"/dashboard/atendimento/{p}/encerrar")
        await client.post(f"/dashboard/atendimento/{p}/avaliar", json={"nota": nota})

    csat = (await client.get("/dashboard/estatisticas")).json()["csat"]
    assert csat["total_avaliacoes"] == 3
    assert csat["media"] == 3.7                      # (5+4+2)/3
    assert csat["percentual_satisfeitos"] == 67      # notas 4 e 5
    assert {d["nota"] for d in csat["distribuicao"]} == {1, 2, 3, 4, 5}


async def test_estatisticas_registram_transferencia(client: AsyncClient):
    protocolo = await _forcar_handoff(client)
    await client.post(
        f"/dashboard/atendimento/{protocolo}/transferir", json={"setor": "financeiro"}
    )
    d = (await client.get("/dashboard/estatisticas")).json()
    assert d["resumo"]["transferencias"] == 1


# ------------------------------------------- retomada da conversa no aparelho


async def test_aparelho_retoma_atendimento_em_curso(client: AsyncClient):
    """Sem isto o simulador abre vazio e a avaliação nunca chega ao cliente."""
    protocolo = await _abrir(client)
    r = await client.get(
        "/channels/atendimento-atual", params={"canal": "app", "identificador": "user_ana"}
    )
    assert r.status_code == 200
    assert r.json()["protocolo"] == protocolo
    assert r.json()["status"] == "bot_ativo"


async def test_aparelho_retoma_pelo_outro_canal(client: AsyncClient):
    """Mesmo protocolo, consultado pelo telefone do WhatsApp."""
    protocolo = await _abrir(client)
    r = await client.get(
        "/channels/atendimento-atual",
        params={"canal": "whatsapp", "identificador": "5511998877321"},
    )
    assert r.json()["protocolo"] == protocolo


async def test_aparelho_retoma_atendimento_encerrado_para_avaliar(client: AsyncClient):
    protocolo = await _abrir(client)
    await client.post(f"/dashboard/atendimento/{protocolo}/encerrar")
    r = await client.get(
        "/channels/atendimento-atual", params={"canal": "app", "identificador": "user_ana"}
    )
    assert r.json()["protocolo"] == protocolo
    assert r.json()["status"] == "encerrado"


async def test_cliente_sem_atendimento_retorna_nulo(client: AsyncClient):
    r = await client.get(
        "/channels/atendimento-atual", params={"canal": "app", "identificador": "user_carlos"}
    )
    assert r.json()["protocolo"] is None


async def test_identificador_desconhecido_no_atendimento_atual(client: AsyncClient):
    r = await client.get(
        "/channels/atendimento-atual", params={"canal": "app", "identificador": "ninguem"}
    )
    assert r.status_code == 404
