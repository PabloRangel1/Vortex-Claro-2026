"""Conversa guiada: confirmação e coleta de dados em mais de uma mensagem.

Antes, cada mensagem recebia uma resposta isolada. Aqui a conversa ganha
memória curta — a ação pendente e o que já foi coletado — guardada na SESSÃO.
Como a sessão é única por cliente, a conversa atravessa canais: o cliente pode
pedir no App e confirmar no WhatsApp.

Estados (EtapaFluxo):
  nenhuma                 nada em andamento
  aguardando_parametro    falta um dado (qual dia? qual plano?)
  aguardando_confirmacao  tudo validado; falta o "sim"

Garantias:
  - só executa depois de confirmação EXPLÍCITA;
  - recusa limpa o estado sem alterar nada;
  - uma nova dúvida abandona o fluxo em curso em vez de prender o cliente;
  - depois de algumas respostas incompreendidas, desiste e libera a conversa
    (lição do bot que repetia a mesma frase sem saída).

Este serviço NÃO decide score, handoff nem status do atendimento: só sinaliza
`requer_handoff`. Quem chama é o orquestrador, a cada mensagem do cliente que
ainda está com o bot.

IA (Fase 5): as regras determinísticas vêm SEMPRE primeiro. A IA só é
consultada quando elas não entendem a mensagem — e devolve uma sugestão, que é
aplicada pelos mesmos caminhos de uma mensagem digitada. Sem IA, sem chave ou
com a API fora do ar, tudo funciona como antes.
"""

from app.config import Settings
from app.core.interpretacao import (
    eh_confirmacao,
    eh_pedido_de_ajuda,
    eh_recusa,
    extrair_dia,
    extrair_plano,
    extrair_protocolo,
)
from app.core.texto import contem_termo, normalizar
from app.domain import dialogo as txt
from app.domain.enums import AcaoAutoatendimento as A
from app.domain.enums import EtapaFluxo, Intencao, StatusAcao
from app.domain.models import ResultadoAcao, Sessao, TurnoDialogo
from app.repositories.base import SessaoRepository
from app.services.autoatendimento_service import AutoatendimentoService
from app.services.ia_service import IAService, SugestaoIA

# Ordem importa: a primeira regra que casar vence. Contestação vem antes de
# segunda via porque "minha fatura veio errada" não é pedido de boleto.
GATILHOS: list[tuple[A, tuple[str, ...]]] = [
    # Antes da contestação: "status da minha contestação" é consulta, não pedido novo.
    (A.CONSULTAR_ATENDIMENTO, (
        "protocolo", "ultimo atendimento", "atendimento anterior", "andamento",
        "acompanhar", "status da", "status do", "minha solicitacao",
    )),
    (A.ABRIR_CONTESTACAO, (
        "nao reconheco", "cobranca indevida", "indevida", "contestar", "contestacao",
        "cobrado a mais", "valor errado", "veio errada", "nao pedi",
    )),
    (A.ENCAMINHAR_HUMANO, ("cancelar", "cancelamento", "rescindir", "encerrar contrato")),
    (A.ALTERAR_VENCIMENTO, (
        "vencimento", "data de pagamento", "dia de pagamento", "mudar a data", "trocar a data",
    )),
    (A.GERAR_SEGUNDA_VIA, (
        "segunda via", "2 via", "boleto", "codigo de barras", "linha digitavel",
        # Consultas de fatura: a segunda via já traz valor, vencimento e itens.
        "quando vence", "valor da fatura", "valor da conta", "quanto esta", "quanto ficou",
        "quanto deu", "ver a fatura", "ver minha fatura", "fatura atual",
    )),
    (A.LISTAR_PLANOS, (
        "upgrade", "mudar de plano", "trocar de plano", "mudar o plano", "trocar o plano",
        "plano maior", "mais gigas", "adicionar linha", "nova linha", "outros planos",
    )),
    (A.DIAGNOSTICAR_CONEXAO, (
        "internet", "conexao", "wifi", "wi fi", "roteador", "modem", "sem sinal", "caindo",
        "caiu", "lenta", "lento", "travando", "oscilando",
    )),
]

# Fallback quando nenhum gatilho casou mas o NLP já reconheceu o assunto.
# FINANCEIRO fica de fora de propósito: é amplo demais para escolher uma ação.
INTENCAO_PARA_ACAO = {
    Intencao.CONTESTACAO_FATURA: A.ABRIR_CONTESTACAO,
    Intencao.CANCELAMENTO: A.ENCAMINHAR_HUMANO,
    Intencao.SEGUNDA_VIA: A.GERAR_SEGUNDA_VIA,
    Intencao.PLANOS_UPGRADE: A.LISTAR_PLANOS,
    Intencao.SUPORTE_TECNICO: A.DIAGNOSTICAR_CONEXAO,
}

# Qual parâmetro cada ação coleta ao longo da conversa.
PARAMETRO_DA_ACAO = {A.ALTERAR_VENCIMENTO: "dia", A.CONFIRMAR_UPGRADE: "plano_id"}

# Falhas em que faz sentido pedir outro valor em vez de encerrar o fluxo.
FALHAS_RECUPERAVEIS = {
    "dia_invalido", "dia_nao_permitido", "dia_igual_atual",
    "plano_inexistente", "mesmo_plano", "nao_e_upgrade", "categoria_diferente",
}

MAX_TENTATIVAS = 2

# O que pode ser INICIADO a partir de uma mensagem. Encaminhar a humano fica de
# fora de propósito: handoff nunca é decisão da IA.
INICIAVEIS = [
    A.CONSULTAR_ATENDIMENTO,
    A.GERAR_SEGUNDA_VIA,
    A.ALTERAR_VENCIMENTO,
    A.DIAGNOSTICAR_CONEXAO,
    A.LISTAR_PLANOS,
    A.ABRIR_CONTESTACAO,
]

# Com um destes, "cancelar" no meio de um fluxo é mesmo pedido de cancelamento.
OBJETOS_DE_CONTRATO = ("contrato", "plano", "linha", "assinatura", "servico", "internet")


def detectar_acao(texto: str, intencao: Intencao | None) -> A | None:
    if extrair_protocolo(texto):  # o cliente colou um número de protocolo
        return A.CONSULTAR_ATENDIMENTO
    n = normalizar(texto)
    for acao, termos in GATILHOS:
        if any(contem_termo(n, t) for t in termos):
            return acao
    return INTENCAO_PARA_ACAO.get(intencao) if intencao else None


class DialogoService:
    def __init__(
        self,
        *,
        autoatendimento: AutoatendimentoService,
        sessoes: SessaoRepository,
        settings: Settings,
        ia: IAService | None = None,
    ) -> None:
        self._auto = autoatendimento
        self._sessoes = sessoes
        self._s = settings
        self._ia = ia

    # ================================================================ público

    async def conduzir(
        self, *, sessao: Sessao, texto: str, intencao: Intencao | None = None
    ) -> TurnoDialogo:
        """Processa uma mensagem do cliente dentro da conversa guiada."""
        if sessao.etapa_fluxo != EtapaFluxo.NENHUMA:
            turno = await self._continuar(sessao, texto, intencao)
            if turno is not None:
                return turno
            # None = o cliente mudou de assunto: o fluxo anterior já foi
            # abandonado e a mensagem é tratada como pedido novo.
        return await self._iniciar(sessao, texto, intencao)

    async def abandonar(self, sessao: Sessao) -> None:
        """Descarta o fluxo em curso sem executar nada (ex.: houve handoff)."""
        if sessao.etapa_fluxo != EtapaFluxo.NENHUMA:
            await self._limpar(sessao)

    def eh_resposta_a_etapa(self, sessao: Sessao, texto: str) -> bool:
        """A mensagem responde ao que o bot perguntou (sim/não, o dia, o plano)?

        Repetir a demanda no lugar de responder NÃO é resposta — é justamente o
        sinal de fricção que o motor precisa ver.
        """
        if sessao.etapa_fluxo == EtapaFluxo.NENHUMA:
            return False
        if eh_confirmacao(texto) or eh_recusa(texto):
            return True
        return self._extrair(sessao.acao_pendente, texto, sessao.dados_pendentes) is not None

    @staticmethod
    def opcoes_resposta(sessao: Sessao) -> list[dict]:
        """Respostas prontas para a etapa em curso — viram botões no simulador.

        `texto` é o que o botão envia: precisa ser algo que a interpretação
        determinística entende, porque passa pelo mesmo caminho do digitado.
        """
        dados = sessao.dados_pendentes
        if sessao.etapa_fluxo == EtapaFluxo.AGUARDANDO_CONFIRMACAO:
            return [dict(o) for o in txt.OPCOES_CONFIRMACAO]
        if sessao.etapa_fluxo != EtapaFluxo.AGUARDANDO_PARAMETRO:
            return []
        if sessao.acao_pendente == A.ALTERAR_VENCIMENTO:
            return [txt.opcao_dia(d) for d in dados.get("opcoes", [])]
        if sessao.acao_pendente == A.CONFIRMAR_UPGRADE:
            return [txt.opcao_plano(o) for o in dados.get("opcoes", [])]
        return []

    # ============================================================== continuar

    async def _continuar(self, sessao, texto, intencao) -> TurnoDialogo | None:
        acao = sessao.acao_pendente
        dados = sessao.dados_pendentes
        parametro = PARAMETRO_DA_ACAO.get(acao)

        nova = detectar_acao(texto, intencao)
        confirmou = eh_confirmacao(texto)

        # No meio de um fluxo, "quero cancelar" quer dizer "cancela esta
        # operação". Só é pedido de cancelamento de contrato se o cliente citar
        # o que quer cancelar ("cancelar meu plano").
        cancelar_operacao = nova == A.ENCAMINHAR_HUMANO and not any(
            contem_termo(normalizar(texto), t) for t in OBJETOS_DE_CONTRATO
        )
        mudou_de_assunto = bool(
            nova
            and nova != self._acao_de_origem(acao)
            and not cancelar_operacao
            and not confirmou
        )

        # 1. Um valor novo vence recusa e confirmação: "não, prefiro o dia 20" é
        #    troca, não recusa. Mas só se o cliente não mudou de assunto — senão
        #    "minha internet caiu às 10" viraria vencimento no dia 10.
        if not mudou_de_assunto:
            valor = self._extrair(acao, texto, dados)
            if valor is not None:
                ja_proposto = dados.get("parametros", {}).get(parametro)
                if sessao.etapa_fluxo == EtapaFluxo.AGUARDANDO_PARAMETRO or valor != ja_proposto:
                    return await self._propor(sessao, acao, {parametro: valor})

        # 2. Recusa explícita. "cancelar meu plano" começa por uma palavra de
        #    recusa, mas é pedido de cancelamento — por isso a exceção.
        pede_cancelamento_de_contrato = nova == A.ENCAMINHAR_HUMANO and not cancelar_operacao
        recusou = eh_recusa(texto) and not pede_cancelamento_de_contrato
        # "não reconheço essa cobrança" diante de "Confirma a contestação?"
        # começa com "não" mas REAFIRMA o pedido. Na dúvida, não cancela:
        # a IA desempata ou o bot pergunta de novo.
        ambigua = (
            recusou
            and sessao.etapa_fluxo == EtapaFluxo.AGUARDANDO_CONFIRMACAO
            and nova is not None
            and nova == self._acao_de_origem(acao)
            and len(normalizar(texto).split()) > 2
        )
        if (recusou and not ambigua) or cancelar_operacao:
            await self._limpar(sessao)
            return self._turno(sessao, txt.RECUSADO)

        # 3. Assunto novo abandona o fluxo em curso
        if mudou_de_assunto:
            await self._limpar(sessao)
            return None

        # 4. Confirmação — o único caminho que executa uma alteração
        if sessao.etapa_fluxo == EtapaFluxo.AGUARDANDO_CONFIRMACAO and confirmou:
            resultado = await self._executar(sessao, acao, dados["parametros"], confirmado=True)
            await self._limpar(sessao)
            return self._turno(sessao, resultado.mensagem, [resultado])

        # 5. As regras não entenderam: a IA tenta interpretar; senão, pergunta
        #    de novo, com limite.
        turno = await self._continuar_pela_ia(sessao, texto, intencao)
        if turno is not None:
            return turno
        return await self._reperguntar(sessao)

    async def _continuar_pela_ia(self, sessao, texto, intencao) -> TurnoDialogo | None:
        acao = sessao.acao_pendente
        outras = [a for a in INICIAVEIS if a != self._acao_de_origem(acao)]
        sugestao = await self._sugestao(sessao, texto, intencao, outras)
        if sugestao is None:
            return None

        if sugestao.confirmacao == "sim":
            resultado = await self._executar(
                sessao, acao, sessao.dados_pendentes["parametros"], confirmado=True
            )
            await self._limpar(sessao)
            return self._turno(sessao, resultado.mensagem, [resultado], ia=True)

        if sugestao.confirmacao == "nao":
            await self._limpar(sessao)
            return self._turno(sessao, txt.RECUSADO, ia=True)

        parametro = PARAMETRO_DA_ACAO.get(acao)
        if parametro and parametro in sugestao.parametros:
            turno = await self._propor(sessao, acao, {parametro: sugestao.parametros[parametro]})
            turno.ia = True
            return turno

        if sugestao.acao is not None:
            await self._limpar(sessao)
            turno = await self._iniciar_acao(sessao, sugestao.acao, texto, sugestao.parametros)
            turno.ia = True
            return turno
        return None

    async def _reperguntar(self, sessao: Sessao) -> TurnoDialogo:
        sessao.tentativas_etapa += 1
        if sessao.tentativas_etapa > MAX_TENTATIVAS:
            await self._limpar(sessao)
            return self._turno(sessao, txt.DESISTENCIA)

        await self._salvar(sessao)
        dados = sessao.dados_pendentes
        if sessao.etapa_fluxo == EtapaFluxo.AGUARDANDO_CONFIRMACAO:
            resposta = txt.REPERGUNTAR_CONFIRMACAO.format(previa=dados.get("previa", ""))
        elif sessao.acao_pendente == A.ALTERAR_VENCIMENTO:
            resposta = txt.REPERGUNTAR_DIA.format(opcoes=txt.juntar_ou(dados.get("opcoes", [])))
        else:
            resposta = txt.REPERGUNTAR_PLANO.format(opcoes=txt.listar_planos(dados.get("opcoes", [])))
        return self._turno(sessao, resposta)

    # ================================================================ iniciar

    async def _iniciar(self, sessao, texto, intencao) -> TurnoDialogo:
        acao = detectar_acao(texto, intencao)
        if acao is not None:
            return await self._iniciar_acao(sessao, acao, texto)

        # "Ajuda", "menu": resposta fixa com as opções — mais rápida e certeira
        # que a IA para uma pergunta que tem sempre a mesma resposta.
        if eh_pedido_de_ajuda(texto):
            return self._turno(sessao, txt.AJUDA)

        # Nenhuma regra reconheceu o pedido: a IA pode identificar uma ação ou,
        # sem ação, responder com naturalidade.
        sugestao = await self._sugestao(sessao, texto, intencao, INICIAVEIS)
        if sugestao is None:
            return TurnoDialogo(tratado=False)
        if sugestao.acao is not None:
            turno = await self._iniciar_acao(sessao, sugestao.acao, texto, sugestao.parametros)
            turno.ia = True
            return turno
        if sugestao.resposta_cliente:
            return self._turno(sessao, sugestao.resposta_cliente, ia=True)
        return TurnoDialogo(tratado=False)

    async def _iniciar_acao(
        self, sessao: Sessao, acao: A, texto: str, parametros: dict | None = None
    ) -> TurnoDialogo:
        parametros = parametros or {}

        if acao == A.GERAR_SEGUNDA_VIA:
            r = await self._executar(sessao, acao, {})
            return self._turno(sessao, r.mensagem, [r])

        if acao == A.CONSULTAR_ATENDIMENTO:
            protocolo = parametros.get("protocolo") or extrair_protocolo(texto)
            r = await self._executar(sessao, acao, {"protocolo": protocolo} if protocolo else {})
            return self._turno(sessao, r.mensagem, [r])

        if acao == A.ENCAMINHAR_HUMANO:
            r = await self._executar(sessao, acao, {"motivo": "cancelamento"})
            return self._turno(sessao, f"{txt.CANCELAMENTO} {r.mensagem}", [r])

        if acao == A.ALTERAR_VENCIMENTO:
            dia = parametros.get("dia") or extrair_dia(texto)
            if dia is not None:  # "mudar o vencimento para o dia 10" já traz o dado
                return await self._propor(sessao, acao, {"dia": dia})
            opcoes = await self._auto.opcoes_vencimento(sessao.cliente_id)
            await self._aguardar_parametro(sessao, acao, {"parametro": "dia", "opcoes": opcoes})
            return self._turno(sessao, txt.PERGUNTAR_DIA.format(opcoes=txt.juntar_ou(opcoes)))

        if acao == A.DIAGNOSTICAR_CONEXAO:
            return await self._diagnosticar(sessao)

        if acao == A.LISTAR_PLANOS:
            return await self._oferecer_planos(sessao, texto)

        if acao == A.ABRIR_CONTESTACAO:
            return await self._propor(sessao, acao, {"descricao": texto})

        return TurnoDialogo(tratado=False)

    async def _diagnosticar(self, sessao: Sessao) -> TurnoDialogo:
        """Diagnóstico com instabilidade já emenda a oferta de reinício."""
        diagnostico = await self._executar(sessao, A.DIAGNOSTICAR_CONEXAO, {})
        if diagnostico.codigo != "diagnostico_instavel":
            return self._turno(sessao, diagnostico.mensagem, [diagnostico])

        previa = await self._executar(sessao, A.REINICIAR_EQUIPAMENTO, {}, confirmado=False)
        if previa.status != StatusAcao.AGUARDANDO_CONFIRMACAO:
            return self._turno(sessao, diagnostico.mensagem, [diagnostico, previa])

        await self._aguardar_confirmacao(sessao, A.REINICIAR_EQUIPAMENTO, {}, previa.mensagem)
        return self._turno(
            sessao, f"{diagnostico.mensagem} {previa.mensagem}", [diagnostico, previa]
        )

    async def _oferecer_planos(self, sessao: Sessao, texto: str) -> TurnoDialogo:
        lista = await self._executar(sessao, A.LISTAR_PLANOS, {})
        opcoes = lista.dados.get("opcoes", [])
        if lista.status == StatusAcao.FALHA or not opcoes:
            return self._turno(sessao, lista.mensagem, [lista])

        # "quero o de 150GB" já escolhe; com uma opção só, não há o que perguntar.
        escolhido = extrair_plano(texto, opcoes)
        if escolhido is None and len(opcoes) == 1:
            escolhido = opcoes[0]["id"]

        if escolhido is not None:
            sessao.dados_pendentes = {"opcoes": opcoes}
            turno = await self._propor(sessao, A.CONFIRMAR_UPGRADE, {"plano_id": escolhido})
            turno.resposta = f"{lista.mensagem} {turno.resposta}"
            turno.resultados.insert(0, lista)
            return turno

        await self._aguardar_parametro(
            sessao, A.CONFIRMAR_UPGRADE, {"parametro": "plano_id", "opcoes": opcoes}
        )
        pergunta = txt.PERGUNTAR_PLANO.format(opcoes=txt.listar_planos(opcoes))
        return self._turno(sessao, f"{lista.mensagem} {pergunta}", [lista])

    # ================================================================ propor

    async def _propor(self, sessao: Sessao, acao: A, parametros: dict) -> TurnoDialogo:
        """Valida SEM executar. Se estiver tudo certo, pede confirmação."""
        opcoes = sessao.dados_pendentes.get("opcoes")
        previa = await self._executar(sessao, acao, parametros, confirmado=False)

        if previa.status == StatusAcao.AGUARDANDO_CONFIRMACAO:
            await self._aguardar_confirmacao(sessao, acao, parametros, previa.mensagem, opcoes)
            return self._turno(sessao, previa.mensagem, [previa])

        if previa.status == StatusAcao.FALHA and previa.codigo in FALHAS_RECUPERAVEIS:
            # Valor recusado, mas a conversa continua: pede outro.
            if opcoes is None and acao == A.ALTERAR_VENCIMENTO:
                opcoes = await self._auto.opcoes_vencimento(sessao.cliente_id)
            await self._aguardar_parametro(
                sessao, acao, {"parametro": PARAMETRO_DA_ACAO[acao], "opcoes": opcoes or []},
                zerar_tentativas=False,
            )
            return self._turno(sessao, previa.mensagem, [previa])

        await self._limpar(sessao)
        return self._turno(sessao, previa.mensagem, [previa])

    # ================================================================= apoio

    def _extrair(self, acao: A | None, texto: str, dados: dict):
        if acao == A.ALTERAR_VENCIMENTO:
            return extrair_dia(texto)
        if acao == A.CONFIRMAR_UPGRADE:
            return extrair_plano(texto, dados.get("opcoes", []))
        return None

    @staticmethod
    def _acao_de_origem(acao: A | None) -> A | None:
        """O upgrade nasce de 'listar planos'; pedir planos de novo não é assunto novo."""
        if acao == A.CONFIRMAR_UPGRADE:
            return A.LISTAR_PLANOS
        return acao

    async def _sugestao(self, sessao, texto, intencao, permitidas) -> SugestaoIA | None:
        if self._ia is None:
            return None
        return await self._ia.interpretar(
            sessao=sessao, texto=texto, intencao=intencao, permitidas=permitidas
        )

    async def _executar(self, sessao, acao, parametros, confirmado=False) -> ResultadoAcao:
        return await self._auto.executar(
            protocolo=sessao.protocolo,
            cliente_id=sessao.cliente_id,
            acao=acao,
            parametros=parametros,
            confirmado=confirmado,
        )

    async def _aguardar_parametro(self, sessao, acao, dados, zerar_tentativas=True):
        sessao.etapa_fluxo = EtapaFluxo.AGUARDANDO_PARAMETRO
        sessao.acao_pendente = acao
        sessao.dados_pendentes = dados
        if zerar_tentativas:
            sessao.tentativas_etapa = 0
        await self._salvar(sessao)

    async def _aguardar_confirmacao(self, sessao, acao, parametros, previa, opcoes=None):
        sessao.etapa_fluxo = EtapaFluxo.AGUARDANDO_CONFIRMACAO
        sessao.acao_pendente = acao
        sessao.dados_pendentes = {"parametros": parametros, "previa": previa}
        if opcoes is not None:
            # Guardadas para o cliente poder trocar de plano já na confirmação.
            sessao.dados_pendentes["opcoes"] = opcoes
        sessao.tentativas_etapa = 0
        await self._salvar(sessao)

    async def _limpar(self, sessao: Sessao) -> None:
        sessao.etapa_fluxo = EtapaFluxo.NENHUMA
        sessao.acao_pendente = None
        sessao.dados_pendentes = {}
        sessao.tentativas_etapa = 0
        await self._salvar(sessao)

    async def _salvar(self, sessao: Sessao) -> None:
        await self._sessoes.salvar(sessao, self._s.sessao_ttl_segundos)

    @staticmethod
    def _turno(sessao: Sessao, resposta: str, resultados=None, ia: bool = False) -> TurnoDialogo:
        resultados = resultados or []
        return TurnoDialogo(
            tratado=True,
            resposta=resposta,
            resultados=resultados,
            etapa=sessao.etapa_fluxo,
            acao_pendente=sessao.acao_pendente,
            requer_handoff=any(r.requer_handoff for r in resultados),
            ia=ia,
        )
