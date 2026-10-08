"""Testes do motor de Score de Fricção — a lógica que NÃO pode mudar na fase 2."""

from datetime import timedelta

from app.config import Settings
from app.domain.enums import Canal, CodigoSinal, Intencao, NivelFriccao, Remetente
from app.domain.models import Mensagem, Sessao, agora
from app.services.friccao_service import FriccaoService


def _sessao(**kwargs) -> Sessao:
    base = dict(
        cliente_id="52941288900",
        protocolo="2026-0816-77301",
        canal_ativo=Canal.APP,
        canal_origem=Canal.APP,
        canais_utilizados=[Canal.APP],
        turnos=1,
        turnos_mesma_intencao=1,
    )
    base.update(kwargs)
    return Sessao(**base)


def _msg(conteudo: str, segundos_atras: int = 0) -> Mensagem:
    return Mensagem(
        protocolo="2026-0816-77301",
        remetente=Remetente.CLIENTE,
        canal=Canal.APP,
        conteudo=conteudo,
        criada_em=agora() - timedelta(seconds=segundos_atras),
    )


def _avaliar(friccao: FriccaoService, texto: str, **kwargs):
    padroes = dict(
        score_atual=0,
        sessao=_sessao(),
        historico_cliente=[],
        troca_de_canal=False,
        intencao=Intencao.FINANCEIRO,
        ja_houve_handoff=False,
        canal_anterior=None,
    )
    padroes.update(kwargs)
    return friccao.avaliar(texto=texto, **padroes)


def _codigos(avaliacao) -> set:
    return {s.codigo for s in avaliacao.sinais}


# --------------------------------------------------------------- detectores


def test_pedido_humano_e_o_sinal_mais_forte(friccao: FriccaoService, settings: Settings):
    a = _avaliar(friccao, "quero falar com um atendente de verdade")
    assert CodigoSinal.PEDIDO_HUMANO in _codigos(a)
    assert a.score_atual >= settings.peso_pedido_humano


def test_detecta_repeticao_literal(friccao: FriccaoService):
    historico = [_msg("minha fatura veio com valor errado")]
    a = _avaliar(friccao, "minha fatura veio com o valor errado", historico_cliente=historico)
    assert CodigoSinal.REPETICAO in _codigos(a)


def test_detecta_demanda_reformulada_mais_curta(friccao: FriccaoService):
    """O caso que o SequenceMatcher sozinho perdia: mesma demanda, texto menor."""
    historico = [
        _msg(
            "Minha fatura veio R$ 189,90 mas meu plano é R$ 129,90. "
            "Tem uma cobrança que eu não reconheço."
        )
    ]
    a = _avaliar(
        friccao,
        "Tem uma cobrança que eu não reconheço na minha fatura.",
        historico_cliente=historico,
    )
    assert CodigoSinal.REPETICAO in _codigos(a)


def test_mensagem_diferente_nao_conta_repeticao(friccao: FriccaoService):
    historico = [_msg("minha internet está lenta")]
    a = _avaliar(friccao, "quero contratar um plano novo", historico_cliente=historico)
    assert CodigoSinal.REPETICAO not in _codigos(a)


def test_mesmo_assunto_com_demanda_nova_nao_conta_repeticao(friccao: FriccaoService):
    """Falar de fatura duas vezes não é repetir — precisa ser a MESMA demanda."""
    historico = [_msg("boa tarde, queria falar sobre a fatura deste mês")]
    a = _avaliar(
        friccao,
        "na verdade prefiro alterar a data de vencimento para o dia quinze",
        historico_cliente=historico,
    )
    assert CodigoSinal.REPETICAO not in _codigos(a)


def test_mensagens_curtas_nao_disparam_repeticao_por_acaso(friccao: FriccaoService):
    """Sem massa de texto, a sobreposição de palavras é ruído."""
    historico = [_msg("ok obrigado")]
    a = _avaliar(friccao, "ok entendi", historico_cliente=historico)
    assert CodigoSinal.REPETICAO not in _codigos(a)


def test_lexico_negativo(friccao: FriccaoService):
    a = _avaliar(friccao, "isso é um absurdo, já expliquei três vezes")
    assert CodigoSinal.SENTIMENTO_NEGATIVO in _codigos(a)


def test_sentimento_negativo_respeita_teto(friccao: FriccaoService, settings: Settings):
    a = _avaliar(friccao, "absurdo ridículo palhaçada descaso inaceitável procon processar")
    sinal = next(s for s in a.sinais if s.codigo is CodigoSinal.SENTIMENTO_NEGATIVO)
    assert sinal.peso <= settings.peso_sentimento_max


def test_caixa_alta(friccao: FriccaoService):
    a = _avaliar(friccao, "EU QUERO RESOLVER ISSO AGORA")
    assert CodigoSinal.CAIXA_ALTA in _codigos(a)


def test_caixa_alta_ignora_mensagem_curta(friccao: FriccaoService):
    assert CodigoSinal.CAIXA_ALTA not in _codigos(_avaliar(friccao, "OK"))


def test_troca_de_canal(friccao: FriccaoService, settings: Settings):
    sessao = _sessao(canal_ativo=Canal.WHATSAPP, canal_origem=Canal.APP)
    a = _avaliar(friccao, "boa tarde", sessao=sessao, troca_de_canal=True)
    sinal = next(s for s in a.sinais if s.codigo is CodigoSinal.TROCA_CANAL)
    assert sinal.peso == settings.peso_troca_canal
    assert "App Claro → WhatsApp" in sinal.descricao


def test_descricao_da_troca_usa_o_canal_anterior_nao_o_de_origem(friccao: FriccaoService):
    """Jornada app → whatsapp → app: a volta é 'WhatsApp → App Claro'."""
    sessao = _sessao(
        canal_ativo=Canal.APP,
        canal_origem=Canal.APP,
        canais_utilizados=[Canal.APP, Canal.WHATSAPP],
    )
    a = _avaliar(
        friccao,
        "voltei pelo aplicativo",
        sessao=sessao,
        troca_de_canal=True,
        canal_anterior=Canal.WHATSAPP,
    )
    sinal = next(s for s in a.sinais if s.codigo is CodigoSinal.TROCA_CANAL)
    assert "WhatsApp → App Claro" in sinal.descricao


def test_intencao_repetida(friccao: FriccaoService, settings: Settings):
    sessao = _sessao(turnos_mesma_intencao=settings.turnos_mesma_intencao)
    a = _avaliar(friccao, "e a minha fatura?", sessao=sessao, intencao=Intencao.FINANCEIRO)
    assert CodigoSinal.INTENCAO_REPETIDA in _codigos(a)


def test_loop_cresce_com_turnos_mas_tem_teto(friccao: FriccaoService, settings: Settings):
    muitos = _sessao(turnos=settings.turnos_para_loop + 20)
    a = _avaliar(friccao, "e aí?", sessao=muitos)
    sinal = next(s for s in a.sinais if s.codigo is CodigoSinal.LOOP_SEM_RESOLUCAO)
    assert sinal.peso == settings.peso_loop_max


def test_impaciencia_em_janela_curta(friccao: FriccaoService):
    historico = [_msg("oi", 5), _msg("alguém aí", 3)]
    a = _avaliar(friccao, "responde", historico_cliente=historico)
    assert CodigoSinal.IMPACIENCIA in _codigos(a)


def test_sem_impaciencia_em_janela_longa(friccao: FriccaoService):
    historico = [_msg("oi", 600), _msg("alguém aí", 500)]
    a = _avaliar(friccao, "responde", historico_cliente=historico)
    assert CodigoSinal.IMPACIENCIA not in _codigos(a)


# ------------------------------------------------------------- consolidação


def test_score_satura_em_100(friccao: FriccaoService):
    a = _avaliar(friccao, "QUERO UM ATENDENTE, isso é um absurdo!", score_atual=95)
    assert a.score_atual == 100


def test_score_nunca_fica_negativo(friccao: FriccaoService):
    a = friccao.aplicar_decaimento(5, "atendente assumiu")
    assert a.score_atual == 0


def test_handoff_dispara_ao_cruzar_o_limiar(friccao: FriccaoService, settings: Settings):
    a = _avaliar(friccao, "quero falar com um atendente", score_atual=settings.limiar_handoff - 5)
    assert a.deve_disparar_handoff is True
    assert a.motivo_handoff and str(settings.limiar_handoff) in a.motivo_handoff


def test_handoff_nao_redispara(friccao: FriccaoService):
    a = _avaliar(friccao, "quero falar com um atendente", score_atual=90, ja_houve_handoff=True)
    assert a.deve_disparar_handoff is False


def test_abaixo_do_limiar_nao_dispara(friccao: FriccaoService):
    a = _avaliar(friccao, "quero mudar meu vencimento", score_atual=0)
    assert a.deve_disparar_handoff is False


def test_niveis(friccao: FriccaoService):
    assert friccao.nivel(10) is NivelFriccao.ESTAVEL
    assert friccao.nivel(50) is NivelFriccao.ATENCAO
    assert friccao.nivel(85) is NivelFriccao.CRITICO


def test_avaliacao_e_auditavel(friccao: FriccaoService):
    a = _avaliar(friccao, "isso é um absurdo, quero um atendente AGORA")
    assert len(a.sinais) >= 2
    assert all(s.descricao for s in a.sinais)
    assert a.delta == a.score_atual - a.score_anterior
