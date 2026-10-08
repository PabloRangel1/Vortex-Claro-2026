"""Autoatendimento pela API (Fases 1, 2 e 4): ações, conversa guiada e handoff."""

from httpx import AsyncClient

from tests.conftest import enviar_app, enviar_whatsapp


def _codigos(resposta: dict) -> list[str]:
    return [a["codigo"] for a in resposta["acoes"]]


async def test_segunda_via_devolve_dados_estruturados(client: AsyncClient):
    r = (await enviar_app(client, "me manda a segunda via da fatura")).json()

    assert r["origem_resposta"] == "autoatendimento"
    assert _codigos(r) == ["segunda_via_gerada"]
    dados = r["acoes"][0]["dados"]
    assert dados["valor_centavos"] == 18990
    assert dados["codigo_barras"].startswith("99990")  # banco fictício


async def test_vencimento_pedido_no_app_e_confirmado_no_whatsapp(client: AsyncClient):
    """A conversa guiada vive na sessão: atravessa canais no mesmo protocolo."""
    pedido = (await enviar_app(client, "quero mudar meu vencimento")).json()
    assert pedido["fluxo"]["etapa"] == "aguardando_parametro"
    assert {o["rotulo"] for o in pedido["fluxo"]["opcoes"]} == {"Dia 10", "Dia 15", "Dia 20"}

    escolha = (await enviar_whatsapp(client, "Dia 15")).json()
    assert escolha["protocolo"] == pedido["protocolo"]
    assert _codigos(escolha) == ["confirmar_vencimento"]
    assert escolha["fluxo"]["etapa"] == "aguardando_confirmacao"

    feito = (await enviar_whatsapp(client, "Sim, confirmo")).json()
    assert _codigos(feito) == ["vencimento_alterado"]
    assert feito["acoes"][0]["protocolo_solicitacao"].startswith("SOL-")
    assert feito["fluxo"] is None


async def test_recusa_nao_altera_nada(client: AsyncClient):
    await enviar_app(client, "quero mudar meu vencimento")
    await enviar_app(client, "Dia 15")
    r = (await enviar_app(client, "Não, obrigado")).json()

    assert r["acoes"] == []
    assert "não fiz nenhuma alteração" in r["resposta"]


async def test_contestacao_abre_em_analise(client: AsyncClient):
    await enviar_app(client, "não reconheço uma cobrança na minha fatura")
    r = (await enviar_app(client, "Sim, confirmo")).json()

    assert _codigos(r) == ["contestacao_aberta"]
    assert "em análise" in r["resposta"]


async def test_fluxo_pendente_aparece_no_painel(client: AsyncClient):
    p = (await enviar_app(client, "quero mudar meu vencimento")).json()["protocolo"]
    painel = (await client.get(f"/dashboard/atendimento/{p}")).json()

    assert painel["fluxo"]["acao_pendente"] == "alterar_vencimento"
    assert len(painel["fluxo"]["opcoes"]) == 3


# ----------------------------------------------------------- saídas para humano


async def test_cancelamento_vai_para_humano_com_motivo(client: AsyncClient):
    r = (await enviar_app(client, "quero cancelar meu plano")).json()
    assert r["handoff_acionado"] is True

    painel = (await client.get(f"/dashboard/atendimento/{r['protocolo']}")).json()
    assert "cancelamento" in painel["handoff"]["motivo"].lower()


async def test_pedido_explicito_de_humano_transfere_antes_do_limiar(client: AsyncClient):
    r = (await enviar_app(client, "quero falar com um atendente")).json()

    assert r["score_friccao"] < 70
    assert r["handoff_acionado"] is True
    assert r["status"] == "aguardando_handoff"


# ------------------------------------------------------ fricção x autoatendimento


async def test_respostas_guiadas_nao_contam_como_repeticao(client: AsyncClient):
    """Dois "Sim, confirmo" em fluxos diferentes não são o cliente se repetindo."""
    await enviar_app(client, "quero mudar meu vencimento")
    await enviar_app(client, "Dia 15")
    await enviar_app(client, "Sim, confirmo")
    await enviar_app(client, "não reconheço uma cobrança na minha fatura")
    r = (await enviar_app(client, "Sim, confirmo")).json()

    assert "repeticao" not in {s["codigo"] for s in r["sinais"]}
    assert _codigos(r) == ["contestacao_aberta"]


async def test_acao_que_resolve_zera_turnos_sem_resolucao(client: AsyncClient):
    await enviar_app(client, "me manda a segunda via")
    await enviar_app(client, "quero mudar meu vencimento")
    await enviar_app(client, "Dia 15")
    await enviar_app(client, "Sim, confirmo")  # resolve: a contagem recomeça
    r = (await enviar_app(client, "e meu plano, tem upgrade?")).json()

    assert "loop_sem_resolucao" not in {s["codigo"] for s in r["sinais"]}


async def test_recusa_ambigua_sem_ia_pergunta_de_novo(client: AsyncClient):
    """'não reconheço essa cobrança' diante de 'Confirma a contestação?' reafirma
    o pedido. Sem IA para desempatar, o bot pergunta de novo em vez de cancelar."""
    await enviar_app(client, "minha fatura veio errada")
    r = (await enviar_app(client, "não reconheço essa cobrança de jeito nenhum")).json()

    assert "Responda sim" in r["resposta"]
    assert r["fluxo"]["etapa"] == "aguardando_confirmacao"


async def test_frustracao_comecando_com_isso_nao_confirma(client: AsyncClient):
    """'isso' só é 'sim' em resposta curta. A frase clássica de frustração não
    pode confirmar a contestação que o bot acabou de oferecer."""
    await enviar_app(client, "minha fatura veio errada")
    r = (await enviar_app(client, "isso é um absurdo, já expliquei três vezes")).json()

    assert "contestacao_aberta" not in _codigos(r)
    curta = (await enviar_app(client, "isso mesmo")).json()
    assert _codigos(curta) == ["contestacao_aberta"]
