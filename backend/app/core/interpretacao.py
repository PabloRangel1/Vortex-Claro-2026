"""Interpretação determinística de respostas curtas do cliente.

Sem IA de propósito: esta é a base que continua funcionando quando a camada de
linguagem (Fase 5) falhar ou estiver indisponível.

Olha principalmente a PRIMEIRA palavra. Numa conversa de chat, "sim, pode" e
"não, prefiro outro dia" começam pela decisão; procurar "não" em qualquer
posição transformaria "sim, não reconheço essa cobrança" em recusa.
"""

import re

from app.core.texto import contem_termo, normalizar

_CONFIRMACOES = {"sim", "s", "confirmo", "confirma", "confirmar", "confirmado", "yes"}

# Só significam "sim" numa resposta curta. "Isso mesmo" confirma; "isso é um
# absurdo, já expliquei três vezes" é frustração — e confirmava a contestação.
_CONFIRMACOES_CURTAS = {
    "pode", "ok", "okay", "isso", "fechado", "beleza", "positivo", "perfeito",
    "certo", "manda", "bora",
}
_MAX_PALAVRAS_CURTA = 3
_FRASES_CONFIRMACAO = {"ta bom", "ta certo", "pode ser", "tudo bem", "com certeza"}

_RECUSAS = {
    "nao", "n", "cancela", "cancelar", "desisto", "esquece", "negativo", "deixa",
    "nunca", "no",
}
_FRASES_RECUSA = {"melhor nao", "agora nao", "deixa pra la", "deixa para la", "mudei de ideia"}

_DIAS_POR_EXTENSO = {"cinco": 5, "dez": 10, "quinze": 15, "vinte": 20}
_NUMERO = re.compile(r"(?<!\d)(\d{1,2})(?!\d)")

# "segunda" fica de fora: colidiria com "segunda via".
_ORDINAIS = {"primeiro": 1, "primeira": 1, "segundo": 2, "terceiro": 3, "terceira": 3}


def _comeca_com(texto: str, palavras: set[str], frases: set[str]) -> bool:
    n = normalizar(texto)
    if not n:
        return False
    if any(n == f or n.startswith(f + " ") for f in frases):
        return True
    return n.split()[0] in palavras


def eh_confirmacao(texto: str) -> bool:
    if _comeca_com(texto, _CONFIRMACOES, _FRASES_CONFIRMACAO):
        return True
    palavras = normalizar(texto).split()
    return (
        bool(palavras)
        and palavras[0] in _CONFIRMACOES_CURTAS
        and len(palavras) <= _MAX_PALAVRAS_CURTA
    )


def eh_recusa(texto: str) -> bool:
    return _comeca_com(texto, _RECUSAS, _FRASES_RECUSA)


def extrair_dia(texto: str) -> int | None:
    """'dia 15', 'prefiro o 20', 'quinze' -> dia do mês. Ignora números fora de 1..31."""
    n = normalizar(texto)
    for token in n.split():
        if token in _DIAS_POR_EXTENSO:
            return _DIAS_POR_EXTENSO[token]
    for m in _NUMERO.finditer(n):
        dia = int(m.group(1))
        if 1 <= dia <= 31:
            return dia
    return None


def extrair_plano(texto: str, opcoes: list[dict]) -> str | None:
    """Identifica qual das opções oferecidas o cliente escolheu.

    Aceita o id, a franquia ("o de 150GB"), o nome, ou a posição na lista
    ("a 2", "o primeiro"). Só considera as opções efetivamente oferecidas.
    """
    if not opcoes:
        return None
    n = normalizar(texto)
    compacto = n.replace(" ", "")

    for o in opcoes:
        if o["id"] in n:
            return o["id"]
    for o in opcoes:
        franquia = normalizar(o["franquia"]).replace(" ", "")
        if franquia and franquia in compacto:
            return o["id"]
    for o in opcoes:
        if normalizar(o["nome"]) in n:
            return o["id"]
    for token in n.split():
        posicao = int(token) if token.isdigit() else _ORDINAIS.get(token)
        if posicao and 1 <= posicao <= len(opcoes):
            return opcoes[posicao - 1]["id"]
    return None


# "Era só isso, obrigado": o cliente encerra a conversa com o bot. Sem isso, um
# atendimento resolvido pelo autoatendimento nunca terminava — e a pesquisa de
# satisfação, que só aparece no encerramento, nunca chegava ao cliente.
_DESPEDIDAS = (
    "obrigado", "obrigada", "brigado", "brigada", "valeu", "vlw", "tchau",
    "so isso", "era so isso", "e so isso", "nada mais", "pode encerrar",
    "pode finalizar", "ja resolveu", "resolvido", "ate mais", "ate logo",
)
_NEGACOES_DE_RESOLUCAO = ("nao resolv", "nao ajud", "nao funcion", "nao deu certo")
_MAX_PALAVRAS_DESPEDIDA = 6


def eh_despedida(texto: str) -> bool:
    n = normalizar(texto)
    palavras = n.split()
    if not palavras or len(palavras) > _MAX_PALAVRAS_DESPEDIDA:
        return False
    if any(neg in n for neg in _NEGACOES_DE_RESOLUCAO):
        return False
    return any(contem_termo(n, d) for d in _DESPEDIDAS)


# Protocolo de atendimento (2026-1005-77301) ou de solicitação (SOL-20261005-1001).
_PROTOCOLO = re.compile(r"\b(SOL-\d{8}-\d{4}|\d{4}-\d{4}-\d{5})\b", re.IGNORECASE)


def extrair_protocolo(texto: str) -> str | None:
    m = _PROTOCOLO.search(texto)
    return m.group(1).upper() if m else None


# "Ajuda", "menu", "o que você faz?": o cliente quer saber as opções. Só vale
# quando nenhuma ação foi reconhecida ("ajuda com a internet" é diagnóstico).
_PEDIDOS_DE_AJUDA = (
    "ajuda", "menu", "opcoes", "o que voce faz", "o que voce pode", "o que da pra fazer",
    "o que posso fazer", "como funciona", "quais servicos",
)


def eh_pedido_de_ajuda(texto: str) -> bool:
    n = normalizar(texto)
    return len(n.split()) <= 8 and any(contem_termo(n, t) for t in _PEDIDOS_DE_AJUDA)
