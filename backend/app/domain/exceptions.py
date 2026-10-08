"""Exceções de domínio.

Os routers as traduzem em HTTP; os services nunca conhecem status codes.
"""


class VortexError(Exception):
    """Base de todas as exceções de negócio."""

    mensagem = "Erro no processamento"

    def __init__(self, mensagem: str | None = None) -> None:
        self.mensagem = mensagem or self.mensagem
        super().__init__(self.mensagem)


class ClienteNaoIdentificado(VortexError):
    mensagem = "Não foi possível identificar o cliente a partir do identificador do canal"


class AtendimentoNaoEncontrado(VortexError):
    mensagem = "Atendimento não encontrado para o protocolo informado"


class AtendimentoEncerrado(VortexError):
    mensagem = "Este atendimento já foi encerrado"
