"""Testes do classificador de intenção."""

import pytest

from app.domain.enums import Intencao
from app.services.nlp_service import NLPService


@pytest.mark.parametrize(
    ("texto", "esperada"),
    [
        ("minha internet caiu de novo", Intencao.SUPORTE_TECNICO),
        ("o roteador está sem sinal desde ontem", Intencao.SUPORTE_TECNICO),
        ("tem uma cobrança que eu não reconheço", Intencao.CONTESTACAO_FATURA),
        ("minha fatura veio errada esse mês", Intencao.CONTESTACAO_FATURA),
        ("preciso da segunda via do boleto", Intencao.SEGUNDA_VIA),
        ("quero mudar a data de vencimento da fatura", Intencao.FINANCEIRO),
        ("gostaria de adicionar linha no meu plano", Intencao.PLANOS_UPGRADE),
        ("quero cancelar meu contrato", Intencao.CANCELAMENTO),
    ],
)
def test_classifica_intencoes(nlp: NLPService, texto: str, esperada: Intencao):
    assert nlp.classificar(texto).intencao is esperada


def test_normalizacao_ignora_acento_e_caixa(nlp: NLPService):
    com = nlp.classificar("NÃO RECONHEÇO essa cobrança!")
    sem = nlp.classificar("nao reconheco essa cobranca")
    assert com.intencao is sem.intencao is Intencao.CONTESTACAO_FATURA


def test_texto_sem_termos_cai_em_outros(nlp: NLPService):
    resultado = nlp.classificar("bom dia, tudo bem com você?")
    assert resultado.intencao is Intencao.OUTROS
    assert resultado.confianca == 0


def test_texto_vazio_nao_quebra(nlp: NLPService):
    assert nlp.classificar("").intencao is Intencao.OUTROS


def test_confianca_cresce_com_evidencia(nlp: NLPService):
    fraco = nlp.classificar("sobre a conta")
    forte = nlp.classificar("não reconheço essa cobrança indevida, quero contestar")
    assert forte.confianca > fraco.confianca


def test_expoe_termos_para_explicabilidade(nlp: NLPService):
    resultado = nlp.classificar("meu wifi está oscilando e a conexão caiu")
    assert resultado.intencao is Intencao.SUPORTE_TECNICO
    assert "wifi" in resultado.termos_detectados
