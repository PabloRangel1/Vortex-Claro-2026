"""Textos da verificação de identidade.

Mesma regra de `domain/acoes.py` e `domain/dialogo.py`: o que o cliente lê
fica no domínio; a regra fica em `services/verificacao_service.py`.
"""

PERGUNTA = (
    "Antes de continuar, preciso confirmar que estou falando com o titular da "
    "linha. Por favor, me informe os 3 primeiros dígitos do seu CPF."
)

CONFIRMADA = "Obrigado, {nome}! Identidade confirmada."
CONFIRMADA_SEM_PEDIDO = "Obrigado, {nome}! Identidade confirmada. Como posso ajudar?"

SEM_DIGITOS = (
    "Para confirmar sua identidade, preciso só dos 3 primeiros dígitos do seu CPF "
    "(apenas números)."
)

BLOQUEADA = (
    "Não consegui confirmar sua identidade. Por segurança, vou te encaminhar a "
    "um atendente, que vai te ajudar por outro caminho."
)
MOTIVO_HANDOFF = "Identidade não confirmada após {tentativas} tentativas"


def incorreta(restantes: int) -> str:
    sufixo = "tentativa restante" if restantes == 1 else "tentativas restantes"
    return f"Os dígitos não conferem com o cadastro. Tente de novo — {restantes} {sufixo}."
