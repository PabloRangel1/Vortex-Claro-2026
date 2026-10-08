"""Verificação de identidade, encerramento com pesquisa e demonstração pré-carregada."""

from datetime import timedelta

from httpx import AsyncClient

from app.config import Settings
from app.core import relogio
from app.dependencies import Container
from app.domain.enums import Canal
from app.domain.models import agora
from app.repositories.seed import CLIENTES_DEMO_AO_VIVO
from app.services.demonstracao_service import semear_demonstracao
from tests.conftest import enviar_app, enviar_whatsapp

# ------------------------------------------------------------ verificação


async def test_whatsapp_pede_cpf_antes_de_qualquer_dado(client: AsyncClient):
    r = (await enviar_whatsapp(client, "me manda a segunda via")).json()

    assert r["origem_resposta"] == "verificacao"
    assert "3 primeiros dígitos do seu CPF" in r["resposta"]
    assert r["acoes"] == []  # nenhuma fatura antes da confirmação


async def test_pedido_feito_antes_da_verificacao_e_atendido_depois(client: AsyncClient):
    """O cliente não precisa repetir o que já pediu."""
    await enviar_whatsapp(client, "me manda a segunda via")
    r = (await enviar_whatsapp(client, "529")).json()

    assert r["resposta"].startswith("Obrigado, Ana! Identidade confirmada.")
    assert [a["codigo"] for a in r["acoes"]] == ["segunda_via_gerada"]


async def test_saudacao_antes_da_verificacao_vira_como_posso_ajudar(client: AsyncClient):
    await enviar_whatsapp(client, "oi")
    r = (await enviar_whatsapp(client, "529.412.889-00")).json()  # CPF inteiro também vale
    assert r["resposta"].endswith("Como posso ajudar?")


async def test_tres_erros_vao_para_humano_com_motivo(client: AsyncClient):
    await enviar_whatsapp(client, "me manda a segunda via")
    await enviar_whatsapp(client, "111")
    segunda = (await enviar_whatsapp(client, "222")).json()
    assert "1 tentativa restante" in segunda["resposta"]
    r = (await enviar_whatsapp(client, "333")).json()

    assert r["handoff_acionado"] is True
    painel = (await client.get(f"/dashboard/atendimento/{r['protocolo']}")).json()
    assert painel["identidade"] == "falhou"
    assert "Identidade não confirmada" in painel["handoff"]["motivo"]


async def test_respostas_da_verificacao_nao_somam_friccao(client: AsyncClient):
    await enviar_whatsapp(client, "me manda a segunda via")
    await enviar_whatsapp(client, "111")
    r = (await enviar_whatsapp(client, "111")).json()  # repetir o palpite não é "repetição"
    assert "repeticao" not in {s["codigo"] for s in r["sinais"]}


async def test_app_ja_vem_verificado_pelo_login(client: AsyncClient):
    r = (await enviar_app(client, "me manda a segunda via")).json()
    assert r["origem_resposta"] == "autoatendimento"
    painel = (await client.get(f"/dashboard/atendimento/{r['protocolo']}")).json()
    assert painel["identidade"] == "verificada_app"


async def test_quem_verificou_no_app_segue_verificado_no_whatsapp(client: AsyncClient):
    await enviar_app(client, "quero mudar meu vencimento")
    r = (await enviar_whatsapp(client, "Dia 15")).json()
    assert r["origem_resposta"] == "autoatendimento"


# ---------------------------------------------------- despedida e pesquisa


async def test_despedida_encerra_e_libera_a_pesquisa(client: AsyncClient):
    await enviar_app(client, "me manda a segunda via")
    r = (await enviar_app(client, "Era só isso, obrigado")).json()

    assert r["status"] == "encerrado"
    assert "como foi" in r["resposta"]
    avaliacao = await client.post(f"/dashboard/atendimento/{r['protocolo']}/avaliar", json={"nota": 5})
    assert avaliacao.status_code == 200


async def test_nao_resolveu_nao_e_despedida(client: AsyncClient):
    await enviar_app(client, "me manda a segunda via")
    r = (await enviar_app(client, "não resolveu, obrigado")).json()
    assert r["status"] != "encerrado"


async def test_nao_obrigado_no_meio_de_um_fluxo_e_recusa(client: AsyncClient):
    await enviar_app(client, "quero mudar meu vencimento")
    await enviar_app(client, "Dia 15")
    r = (await enviar_app(client, "Não, obrigado")).json()
    assert r["status"] == "bot_ativo"
    assert "não fiz nenhuma alteração" in r["resposta"]


# ------------------------------------------------------------ demonstração


async def test_demonstracao_preenche_fila_historico_e_estatisticas():
    c = Container(Settings(semear_demonstracao=True))
    await semear_demonstracao(c)
    todos = await c.atendimentos.listar_todos()

    assert len(todos) == 35
    status = [str(a.status) for a in todos]
    assert status.count("aguardando_handoff") == 3
    assert status.count("em_atendimento_humano") == 1
    assert sum(1 for a in todos if a.nota is not None) == 30
    assert any(a.identidade == "falhou" for a in todos)
    # Datas espalhadas no passado, não todas "agora".
    assert min(a.aberto_em for a in todos) < agora() - timedelta(days=7)


async def test_demonstracao_nao_abre_atendimento_dos_clientes_ao_vivo():
    c = Container(Settings(semear_demonstracao=True))
    await semear_demonstracao(c)

    for a in await c.atendimentos.listar_todos():
        if a.cliente_id in CLIENTES_DEMO_AO_VIVO:
            assert str(a.status) == "encerrado"
    for cliente_id in CLIENTES_DEMO_AO_VIVO:
        assert await c.sessoes_repo.obter(cliente_id) is None


async def test_reset_recarrega_a_demonstracao():
    c = Container(Settings(semear_demonstracao=True))
    await c.resetar()
    await c.resetar()  # duas vezes: não duplica
    assert len(await c.atendimentos.listar_todos()) == 35


def test_relogio_volta_ao_presente_depois_da_simulacao():
    antes = agora()
    with relogio.no_passado(timedelta(days=3)):
        assert agora() < antes - timedelta(days=2)
        relogio.avancar(60)
    assert agora() >= antes


async def test_sessao_viva_nao_captura_a_simulacao():
    """Ana conversando agora não pode ter a conversa "de 9 dias atrás" da
    simulação enfiada no protocolo dela."""
    c = Container(Settings(semear_demonstracao=True))
    agora_mesmo = await c.orquestrador.processar_mensagem(
        canal=Canal.APP, identificador="user_ana", conteudo="me manda a segunda via"
    )
    await semear_demonstracao(c)

    da_ana = [a for a in await c.atendimentos.listar_todos() if a.cliente_id == "52941288900"]
    assert len(da_ana) == 2  # a de agora + a histórica da simulação
    atual = next(a for a in da_ana if a.protocolo == agora_mesmo.protocolo)
    assert str(atual.status) == "bot_ativo"  # intocada


async def test_simulacao_cobre_os_tres_tipos_de_caso():
    """Resolvidos pelo bot, fricção alta e resolvidos com ajuda da IA."""
    c = Container(Settings(semear_demonstracao=True))
    await semear_demonstracao(c)
    todos = await c.atendimentos.listar_todos()
    registros = await c.conversas.listar_registros_autoatendimento()

    resolvidos_sem_humano = [a for a in todos if a.handoff_em is None and str(a.status) == "encerrado"]
    assert len(resolvidos_sem_humano) >= 4
    assert any(a.score_friccao >= 70 for a in todos)
    respostas_ia = [m for m in registros if m.metadados.get("ia")]
    assert len(respostas_ia) >= 2
    # A IA da simulação não pode vazar para depois dela.
    assert c.dialogo._ia is c.ia


async def test_estatisticas_trazem_serie_diaria_e_impacto():
    from app.domain.models import agora as _agora
    from app.services.estatisticas_service import EstatisticasService

    c = Container(Settings(semear_demonstracao=True))
    await semear_demonstracao(c)
    planos = {p.id: p.preco_centavos for p in await c.operacao.listar_planos()}
    precos = {cl.cliente_id: planos.get(cl.plano_id, 0) for cl in await c.clientes.listar()}
    e = EstatisticasService(c.friccao, c.settings).consolidar(
        await c.atendimentos.listar_todos(),
        await c.atendimentos.listar_todos_eventos(),
        await c.conversas.listar_registros_autoatendimento(),
        precos_por_cliente=precos,
    )

    assert len(e["por_dia"]) == 10
    assert sum(d["total"] for d in e["por_dia"]) == 35
    for d in e["por_dia"]:
        assert d["resolvido_bot"] + d["transferido"] + d["em_andamento"] == d["total"]

    imp = e["impacto"]
    assert imp["protocolos_sem_vortex"] == imp["protocolos_com_vortex"] + imp["trocas_de_canal"]
    assert imp["relatos_repetidos_sem_vortex"] > imp["relatos_repetidos_com_vortex"]
    assert imp["receita_mensal_protegida_centavos"] > 0
    assert imp["upgrades"] == 1 and imp["receita_mensal_upgrades_centavos"] == 6500
    assert len(imp["jornada_exemplo"]["canais"]) == 2
