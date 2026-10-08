"""Respostas do bot por intenção.

Deliberadamente simples: o objetivo do MVP é demonstrar a ORQUESTRAÇÃO, não
construir um chatbot. As respostas são canned e a de handoff é a única que
muda o tom — porque é o momento em que o produto entrega valor.
"""

from app.domain.enums import Intencao

RESPOSTAS: dict[Intencao, str] = {
    Intencao.SUPORTE_TECNICO: (
        "Entendi que você está com problema de conexão. Vou executar um diagnóstico "
        "remoto no seu equipamento — leva cerca de 1 minuto."
    ),
    Intencao.CONTESTACAO_FATURA: (
        "Certo, você não reconhece uma cobrança na sua fatura. Consigo abrir uma "
        "contestação para análise. Confirma que é sobre a fatura do mês atual?"
    ),
    Intencao.SEGUNDA_VIA: (
        "Posso gerar a 2ª via da sua fatura agora mesmo. Prefere receber o código "
        "de barras aqui ou por e-mail?"
    ),
    Intencao.FINANCEIRO: (
        "Sobre sua fatura: consigo consultar valores, alterar a data de vencimento "
        "ou negociar débitos em aberto. O que você precisa?"
    ),
    Intencao.PLANOS_UPGRADE: (
        "Posso te mostrar as opções de upgrade disponíveis para o seu plano atual. "
        "Você busca mais dados, mais linhas ou serviços adicionais?"
    ),
    Intencao.CANCELAMENTO: (
        "Sinto muito que você esteja pensando em cancelar. Antes disso, posso "
        "verificar se há alguma condição especial para o seu perfil?"
    ),
    Intencao.OUTROS: (
        "Desculpe, não consegui entender sua solicitação. Você pode reformular ou "
        "escolher um dos assuntos: fatura, suporte técnico, planos ou cancelamento?"
    ),
}

RESPOSTA_HANDOFF = (
    "Percebi que sua demanda não foi resolvida e peço desculpas por isso. "
    "Já estou te transferindo para um de nossos especialistas — e ele vai receber "
    "TODO o seu histórico, então você não vai precisar repetir nada. Protocolo {protocolo}."
)

RESPOSTA_EM_ATENDIMENTO = (
    "Sua mensagem foi registrada e encaminhada ao atendente responsável pelo "
    "protocolo {protocolo}. Aguarde um instante."
)


class RespostaService:
    def gerar(
        self,
        *,
        intencao: Intencao,
        protocolo: str,
        handoff_acionado: bool,
        em_atendimento_humano: bool = False,
    ) -> str:
        if handoff_acionado:
            return RESPOSTA_HANDOFF.format(protocolo=protocolo)
        if em_atendimento_humano:
            return RESPOSTA_EM_ATENDIMENTO.format(protocolo=protocolo)
        return RESPOSTAS[intencao]
