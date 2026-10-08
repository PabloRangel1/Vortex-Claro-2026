"""Textos da conversa guiada.

Mesma regra de `domain/acoes.py`: o texto que o cliente lê fica no domínio, não
no serviço. `acoes.py` descreve o resultado das ações; este módulo descreve as
perguntas e as transições da conversa em volta delas.
"""

from app.domain.acoes import formatar_moeda

PERGUNTAR_DIA = "Posso alterar o seu vencimento para o dia {opcoes}. Qual você prefere?"
PERGUNTAR_PLANO = "Qual você prefere? {opcoes}"

RECUSADO = "Tudo bem, não fiz nenhuma alteração. Posso ajudar em algo mais?"

REPERGUNTAR_CONFIRMACAO = "Responda sim para confirmar ou não para cancelar. {previa}"
REPERGUNTAR_DIA = "Não identifiquei o dia. As opções disponíveis são {opcoes}."
REPERGUNTAR_PLANO = "Não identifiquei o plano. Responda com o número da opção: {opcoes}"

DESISTENCIA = (
    "Vou deixar esta solicitação de lado por enquanto. Se quiser retomar, é só "
    "me dizer o que precisa."
)

CANCELAMENTO = (
    "O cancelamento não é feito pelo autoatendimento, porque envolve multa e "
    "condições do seu contrato."
)


# Respostas prontas (botões do simulador). O texto enviado é o mesmo que o
# cliente digitaria — "Sim, confirmo" começa por "sim", "Dia 15" traz o número.
OPCOES_CONFIRMACAO = (
    {"rotulo": "Sim, confirmo", "texto": "Sim, confirmo"},
    {"rotulo": "Não, obrigado", "texto": "Não, obrigado"},
)


def opcao_dia(dia: int) -> dict:
    return {"rotulo": f"Dia {dia}", "texto": f"Dia {dia}"}


def opcao_plano(plano: dict) -> dict:
    return {
        "rotulo": f"{plano['nome']} · {formatar_moeda(plano['preco_centavos'])}",
        "texto": plano["nome"],
    }


def juntar_ou(itens: list) -> str:
    """[5, 10, 15] -> '5, 10 ou 15'."""
    textos = [str(i) for i in itens]
    if len(textos) <= 1:
        return "".join(textos)
    return ", ".join(textos[:-1]) + " ou " + textos[-1]


def listar_planos(opcoes: list[dict]) -> str:
    return "; ".join(
        f"{i}) {o['nome']} — {o['franquia']}, {o['linhas_incluidas']} "
        f"{'linha' if o['linhas_incluidas'] == 1 else 'linhas'}, "
        f"{formatar_moeda(o['preco_centavos'])}/mês"
        for i, o in enumerate(opcoes, start=1)
    )


DESPEDIDA = (
    "Fico feliz em ajudar, {nome}! Vou encerrar este atendimento. Antes de ir, "
    "conta pra gente como foi — leva dois segundos."
)


# Primeira mensagem de todo atendimento novo: quem está atendendo (uma IA), o
# protocolo (informado logo no início, como é praxe no setor) e a saída humana.
BOAS_VINDAS = (
    "Olá! Aqui é a assistente virtual da Claro, com inteligência artificial. "
    "Seu protocolo de atendimento é {protocolo}. Resolvo por aqui segunda via, "
    "vencimento, internet, planos e contestações — e, se preferir falar com uma "
    "pessoa, é só pedir."
)

AJUDA = (
    "Posso resolver por aqui: segunda via e valor da fatura, mudança de vencimento, "
    "teste e reinício da internet, upgrade de plano, contestação de cobrança e "
    "consulta de protocolos anteriores. Para falar com uma pessoa, escreva "
    "\"quero falar com um atendente\"."
)
