"""Verificação de identidade antes do autoatendimento.

No App, o cliente já entrou com login e senha: a identidade vem verificada.
No WhatsApp, o número de telefone sozinho não prova quem está escrevendo —
qualquer pessoa com o aparelho na mão veria fatura, vencimento e plano. Por
isso, na primeira mensagem o bot pede os 3 primeiros dígitos do CPF.

O pedido original do cliente NÃO se perde: fica guardado na sessão e é
atendido logo depois da confirmação — ninguém precisa repetir o que já disse.

Depois de algumas tentativas erradas, o caso vai para um atendente humano: é
o caminho seguro, e o motivo fica registrado para ele saber o que conferir.
"""

import re

from app.config import Settings
from app.domain import verificacao as txt
from app.domain.enums import Canal
from app.domain.models import Cliente, Sessao

# Valores gravados em `Atendimento.identidade`.
VERIFICADA_APP = "verificada_app"
VERIFICADA_CPF = "verificada_cpf"
PENDENTE = "pendente"
FALHOU = "falhou"
VERIFICADAS = {VERIFICADA_APP, VERIFICADA_CPF}

_NAO_DIGITO = re.compile(r"\D")


class ResultadoVerificacao:
    __slots__ = ("resposta", "confirmada", "bloqueada", "mensagem_pendente")

    def __init__(self, resposta, confirmada=False, bloqueada=False, mensagem_pendente=None):
        self.resposta = resposta
        self.confirmada = confirmada
        self.bloqueada = bloqueada
        self.mensagem_pendente = mensagem_pendente


class VerificacaoService:
    def __init__(self, settings: Settings) -> None:
        self._s = settings

    def exige(self, canal: Canal) -> bool:
        return str(canal) in self._s.verificacao_canais

    def precisa_verificar(self, sessao: Sessao, canal: Canal) -> bool:
        return not sessao.identidade_verificada and self.exige(canal)

    def marcar_verificada_por_login(self, sessao: Sessao) -> str:
        """Canal autenticado (App): a sessão nasce verificada."""
        sessao.identidade_verificada = True
        return VERIFICADA_APP

    def iniciar(self, sessao: Sessao, texto: str) -> ResultadoVerificacao:
        """Primeira mensagem sem identidade: guarda o pedido e faz a pergunta."""
        sessao.verificacao_pendente = True
        sessao.tentativas_verificacao = 0
        sessao.mensagem_pendente = texto
        return ResultadoVerificacao(txt.PERGUNTA)

    def responder(self, sessao: Sessao, cliente: Cliente, texto: str) -> ResultadoVerificacao:
        digitos = _NAO_DIGITO.sub("", texto)
        # Aceita "529", "529.412..." ou o CPF inteiro: valem os 3 primeiros.
        if len(digitos) >= 3 and digitos[:3] == cliente.cliente_id[:3]:
            pendente = sessao.mensagem_pendente
            sessao.identidade_verificada = True
            sessao.verificacao_pendente = False
            sessao.tentativas_verificacao = 0
            sessao.mensagem_pendente = None
            nome = cliente.nome.split()[0]
            modelo = txt.CONFIRMADA if pendente else txt.CONFIRMADA_SEM_PEDIDO
            return ResultadoVerificacao(
                modelo.format(nome=nome), confirmada=True, mensagem_pendente=pendente
            )

        sessao.tentativas_verificacao += 1
        restantes = self._s.verificacao_tentativas - sessao.tentativas_verificacao
        if restantes <= 0:
            sessao.verificacao_pendente = False
            sessao.mensagem_pendente = None
            return ResultadoVerificacao(txt.BLOQUEADA, bloqueada=True)
        if len(digitos) < 3:
            return ResultadoVerificacao(txt.SEM_DIGITOS)
        return ResultadoVerificacao(txt.incorreta(restantes))

    def motivo_bloqueio(self) -> str:
        return txt.MOTIVO_HANDOFF.format(tentativas=self._s.verificacao_tentativas)
