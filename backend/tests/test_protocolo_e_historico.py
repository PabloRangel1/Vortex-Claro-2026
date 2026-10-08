"""Abertura com IA e protocolo, consulta de protocolo, ajuda, histórico e filtros."""

from httpx import AsyncClient

from tests.conftest import enviar_app


async def _ref(client: AsyncClient, busca: str = "529") -> str:
    """Referência pública do cliente (a API não expõe o CPF)."""
    return (await client.get("/dashboard/clientes", params={"busca": busca})).json()[0]["cliente_ref"]

# ------------------------------------------------------------ abertura


async def _mensagens(client: AsyncClient, protocolo: str) -> list[dict]:
    return (await client.get(f"/dashboard/atendimento/{protocolo}")).json()["mensagens"]


async def test_atendimento_novo_abre_dizendo_que_e_ia_e_com_o_protocolo(client: AsyncClient):
    r = (await enviar_app(client, "me manda a segunda via")).json()
    bot = [m for m in await _mensagens(client, r["protocolo"]) if m["remetente"] == "bot"]

    abertura = bot[0]
    assert abertura["metadados"]["tipo"] == "boas_vindas"
    assert "inteligência artificial" in abertura["conteudo"]
    assert r["protocolo"] in abertura["conteudo"]
    assert "atendente" in abertura["conteudo"] or "pessoa" in abertura["conteudo"]


async def test_abertura_aparece_uma_vez_so(client: AsyncClient):
    p = (await enviar_app(client, "me manda a segunda via")).json()["protocolo"]
    await enviar_app(client, "quero mudar meu vencimento")
    aberturas = [m for m in await _mensagens(client, p) if m["metadados"].get("tipo") == "boas_vindas"]
    assert len(aberturas) == 1


# --------------------------------------------------- consulta de protocolo


async def _atendimento_encerrado(client: AsyncClient, usuario="user_ana") -> str:
    p = (await enviar_app(client, "não reconheço uma cobrança na fatura", usuario_id=usuario)).json()
    await enviar_app(client, "Sim, confirmo", usuario_id=usuario)
    await client.post(f"/dashboard/atendimento/{p['protocolo']}/encerrar")
    return p["protocolo"]


async def test_cliente_consulta_o_ultimo_atendimento(client: AsyncClient):
    anterior = await _atendimento_encerrado(client)
    r = (await enviar_app(client, "quero ver o andamento do meu último atendimento")).json()

    assert [a["codigo"] for a in r["acoes"]] == ["ultimo_atendimento"]
    assert anterior in r["resposta"]
    assert "Contestação de Fatura" in r["resposta"]
    assert "em análise" in r["resposta"]  # a contestação vinculada


async def test_cliente_cola_o_numero_do_protocolo(client: AsyncClient):
    anterior = await _atendimento_encerrado(client)
    r = (await enviar_app(client, anterior)).json()
    assert [a["codigo"] for a in r["acoes"]] == ["atendimento_encontrado"]


async def test_cliente_consulta_protocolo_de_solicitacao(client: AsyncClient):
    await _atendimento_encerrado(client)
    hist = (await client.get(f"/dashboard/clientes/{await _ref(client)}/historico")).json()
    sol = hist["solicitacoes"][0]["protocolo"]

    r = (await enviar_app(client, f"qual o status do {sol}?")).json()
    assert [a["codigo"] for a in r["acoes"]] == ["solicitacao_encontrada"]
    assert "em análise" in r["resposta"]


async def test_protocolo_de_outro_cliente_nao_aparece(client: AsyncClient):
    """Segurança: Ricardo não consulta o atendimento da Ana pelo número."""
    da_ana = await _atendimento_encerrado(client)
    r = (await enviar_app(client, f"protocolo {da_ana}", usuario_id="user_ricardo")).json()

    assert [a["codigo"] for a in r["acoes"]] == ["protocolo_nao_encontrado"]
    assert "Contestação" not in r["resposta"]


async def test_sem_atendimento_anterior(client: AsyncClient):
    r = (await enviar_app(client, "consultar meu último atendimento")).json()
    assert [a["codigo"] for a in r["acoes"]] == ["sem_atendimento_anterior"]


# ------------------------------------------------------- diálogos novos


async def test_pergunta_sobre_a_fatura_vira_segunda_via(client: AsyncClient):
    r = (await enviar_app(client, "quando vence minha fatura?")).json()
    assert [a["codigo"] for a in r["acoes"]] == ["segunda_via_gerada"]


async def test_menu_de_ajuda(client: AsyncClient):
    r = (await enviar_app(client, "o que você faz?")).json()
    assert r["origem_resposta"] == "autoatendimento"
    assert "segunda via" in r["resposta"] and "atendente" in r["resposta"]


async def test_ajuda_com_assunto_vai_para_o_assunto(client: AsyncClient):
    r = (await enviar_app(client, "preciso de ajuda com minha internet", usuario_id="user_ricardo")).json()
    assert "diagnostico_instavel" in [a["codigo"] for a in r["acoes"]]


# -------------------------------------------- painel: histórico e filtros


async def test_busca_por_protocolo_de_atendimento_e_de_solicitacao(client: AsyncClient):
    p = await _atendimento_encerrado(client)
    r = (await client.get(f"/dashboard/protocolo/{p}")).json()
    assert r["cliente_ref"] == await _ref(client) and r["solicitacao"] is None

    sol = (await client.get(f"/dashboard/clientes/{await _ref(client)}/historico")).json()["solicitacoes"][0]
    r = (await client.get(f"/dashboard/protocolo/{sol['protocolo'].lower()}")).json()
    assert r["protocolo_atendimento"] == p
    assert r["solicitacao"]["tipo"] == "contestacao"

    assert (await client.get("/dashboard/protocolo/2026-0101-00000")).status_code == 404


async def test_historico_do_cliente(client: AsyncClient):
    p = await _atendimento_encerrado(client)
    await enviar_app(client, "me manda a segunda via")

    h = (await client.get(f"/dashboard/clientes/{await _ref(client)}/historico")).json()
    assert h["cliente"]["nome"] == "Ana Beatriz Souza"
    assert h["segmento"] == "pos"
    assert len(h["atendimentos"]) == 2
    assert h["atendimentos"][-1]["protocolo"] == p  # mais recente primeiro
    assert h["telefone_whatsapp"] == "5511998877321"


async def test_lista_de_clientes_filtra_por_tipo_e_busca(client: AsyncClient):
    fibra = (await client.get("/dashboard/clientes", params={"segmento": "fibra"})).json()
    assert fibra and all(c["segmento"] == "fibra" for c in fibra)
    assert "Ricardo Mendes Lima" in [c["nome"] for c in fibra]

    por_nome = (await client.get("/dashboard/clientes", params={"busca": "juliana"})).json()
    assert [c["nome"] for c in por_nome] == ["Juliana Ferraz"]
    por_cpf = (await client.get("/dashboard/clientes", params={"busca": "529"})).json()
    assert [c["nome"] for c in por_cpf] == ["Ana Beatriz Souza"]


async def test_fila_informa_o_tipo_de_cliente(client: AsyncClient):
    await enviar_app(client, "quero falar com um atendente", usuario_id="user_ricardo")
    await enviar_app(client, "quero falar com um atendente", usuario_id="user_juliana")
    fila = {i["nome"]: i for i in (await client.get("/dashboard/fila")).json()}

    assert fila["Ricardo Mendes Lima"]["segmento"] == "fibra"
    assert fila["Juliana Ferraz"]["segmento"] == "controle"
    assert fila["Juliana Ferraz"]["segmento_rotulo"] == "Controle"
