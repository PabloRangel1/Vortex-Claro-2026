"""Caso de uso central do Vortex.

Os dois endpoints de canal chamam `processar_mensagem` — muda apenas o enum
`Canal`. Toda a inteligência (identidade cross-canal, protocolo compartilhado,
NLP, fricção, autoatendimento, handoff) vive aqui, e nada disso conhece o banco.

Quem responde cada turno, em ordem de precedência:
  1. handoff disparado AGORA — por fricção, por pedido explícito de humano ou
     porque o autoatendimento não tem solução;
  2. fila humana — o atendimento já saiu do bot; só confirma o recebimento;
  3. verificação de identidade — no WhatsApp, antes de qualquer dado do cliente;
  4. despedida — "era só isso, obrigado" encerra e abre a pesquisa de satisfação;
  5. autoatendimento — a conversa guiada executa ações do catálogo;
  6. bot comum — resposta por intenção, quando nada acima se aplica.
"""

from app.config import Settings
from app.core.interpretacao import eh_despedida
from app.domain import dialogo as txt_dialogo
from app.domain.acoes import RESOLVEM_A_DEMANDA
from app.domain.enums import (
    Canal,
    CodigoSinal,
    EtapaFluxo,
    Intencao,
    Remetente,
    Setor,
    StatusAcao,
    StatusAtendimento,
)
from app.domain.exceptions import (
    AtendimentoEncerrado,
    AtendimentoNaoEncontrado,
    ClienteNaoIdentificado,
    VortexError,
)
from app.domain.models import (
    Atendimento,
    AvaliacaoFriccao,
    EventoFriccao,
    Mensagem,
    ResultadoAcao,
    ResultadoProcessamento,
    Sessao,
    agora,
)
from app.repositories.base import (
    AtendimentoRepository,
    ClienteRepository,
    ConversaRepository,
)
from app.services.dialogo_service import DialogoService
from app.services.friccao_service import FriccaoService
from app.services.nlp_service import NLPService
from app.services.resposta_service import RespostaService
from app.services.sessao_service import SessaoService
from app.services.verificacao_service import (
    FALHOU,
    PENDENTE,
    VERIFICADA_APP,
    VERIFICADA_CPF,
    VerificacaoService,
)


class OrquestradorService:
    def __init__(
        self,
        *,
        clientes: ClienteRepository,
        conversas: ConversaRepository,
        atendimentos: AtendimentoRepository,
        sessoes: SessaoService,
        nlp: NLPService,
        friccao: FriccaoService,
        respostas: RespostaService,
        dialogo: DialogoService,
        verificacao: VerificacaoService,
        settings: Settings,
    ) -> None:
        self._clientes = clientes
        self._conversas = conversas
        self._atendimentos = atendimentos
        self._sessoes = sessoes
        self._nlp = nlp
        self._friccao = friccao
        self._respostas = respostas
        self._dialogo = dialogo
        self._verificacao = verificacao
        self._s = settings

    async def processar_mensagem(
        self, *, canal: Canal, identificador: str, conteudo: str, metadados: dict | None = None
    ) -> ResultadoProcessamento:
        # 1. Identidade canônica — traduz telefone/user_id no cliente_id
        cliente = await self._clientes.resolver_por_identificador(canal, identificador)
        if cliente is None:
            raise ClienteNaoIdentificado(
                f"Identificador '{identificador}' não está vinculado a nenhum cliente "
                f"no canal {canal.rotulo}"
            )

        # 2. Sessão: se já existe, o protocolo é REAPROVEITADO mesmo em outro canal
        resultado_sessao = await self._sessoes.obter_ou_criar(
            cliente.cliente_id, canal, retomar=self._atendimento_com_humano
        )
        sessao = resultado_sessao.sessao
        protocolo = sessao.protocolo

        # O bot fez uma pergunta e esta mensagem é a resposta ("Dia 15", "sim",
        # os dígitos do CPF). Resposta a pergunta não é o cliente repetindo a demanda.
        em_verificacao = sessao.verificacao_pendente
        resposta_guiada = em_verificacao or self._dialogo.eh_resposta_a_etapa(sessao, conteudo)

        # 3. Atendimento (só criado junto com a sessão)
        atendimento = await self._atendimentos.obter(protocolo)
        if atendimento is None:
            atendimento = Atendimento(
                protocolo=protocolo,
                cliente_id=cliente.cliente_id,
                canal_origem=sessao.canal_origem,
                canal_atual=canal,
                canais_utilizados=list(sessao.canais_utilizados),
            )

        if atendimento.status == StatusAtendimento.ENCERRADO:
            raise AtendimentoEncerrado()

        # Canal autenticado (App): a identidade já vem do login.
        if not sessao.identidade_verificada and not self._verificacao.exige(canal):
            atendimento.identidade = self._verificacao.marcar_verificada_por_login(sessao)

        # 4. NLP
        nlp = self._nlp.classificar(conteudo)

        # 5. Contadores da sessão (a fricção os consome)
        sessao = await self._sessoes.registrar_turno(sessao, nlp.intencao)

        # 6. Histórico ANTES de gravar o turno atual (senão a mensagem casa consigo mesma).
        # Respostas guiadas ficam fora da comparação: dois "sim" seguidos não são
        # repetição, e tocar três botões em um minuto não é impaciência. Os
        # detectores sobre o próprio texto (sentimento, caixa alta, pedido de
        # humano) continuam valendo para elas.
        if resposta_guiada:
            historico = []
        else:
            recentes = await self._conversas.ultimas_do_cliente(
                protocolo, self._s.janela_repeticao * 3
            )
            historico = [m for m in recentes if not m.metadados.get("resposta_guiada")][
                -self._s.janela_repeticao :
            ]

        if resultado_sessao.troca_de_canal:
            await self._conversas.adicionar_mensagem(
                Mensagem(
                    protocolo=protocolo,
                    remetente=Remetente.SISTEMA,
                    conteudo=(
                        f"Cliente migrou de {atendimento.canal_atual.rotulo} para "
                        f"{canal.rotulo} — contexto preservado no protocolo {protocolo}"
                    ),
                    metadados={
                        "tipo": "troca_canal",
                        "de": str(atendimento.canal_atual),
                        "para": str(canal),
                    },
                )
            )

        await self._conversas.adicionar_mensagem(
            Mensagem(
                protocolo=protocolo,
                remetente=Remetente.CLIENTE,
                canal=canal,
                conteudo=conteudo,
                intencao=nlp.intencao,
                confianca=nlp.confianca,
                autor=cliente.nome,
                metadados={
                    **(metadados or {}),
                    **({"resposta_guiada": True} if resposta_guiada else {}),
                    # Dígitos do CPF: nunca vão para a IA (ver IAService).
                    **({"verificacao": True} if em_verificacao else {}),
                },
            )
        )

        # Atendimento novo: a primeira resposta diz quem atende (uma IA), informa
        # o protocolo e lembra que dá para pedir uma pessoa.
        if resultado_sessao.nova:
            await self._conversas.adicionar_mensagem(
                Mensagem(
                    protocolo=protocolo,
                    remetente=Remetente.BOT,
                    canal=canal,
                    conteudo=txt_dialogo.BOAS_VINDAS.format(protocolo=protocolo),
                    metadados={"tipo": "boas_vindas"},
                )
            )

        # 7. Motor de fricção
        ja_houve_handoff = atendimento.handoff_em is not None
        avaliacao = self._friccao.avaliar(
            texto=conteudo,
            score_atual=atendimento.score_friccao,
            sessao=sessao,
            historico_cliente=historico,
            troca_de_canal=resultado_sessao.troca_de_canal,
            intencao=nlp.intencao,
            ja_houve_handoff=ja_houve_handoff,
            canal_anterior=atendimento.canal_atual,
        )

        # 8. Consolidação + auditoria
        if not atendimento.historico_score:
            atendimento.score_inicial = avaliacao.score_anterior
            atendimento.historico_score = [avaliacao.score_anterior]

        atendimento.canal_atual = canal
        atendimento.canais_utilizados = list(sessao.canais_utilizados)

        # A intenção CONSOLIDADA do atendimento só é sobrescrita por uma
        # classificação com conteúdo de negócio. Sem isso, um turno final do tipo
        # "QUERO UM ATENDENTE" (que classifica como OUTROS) apagaria a demanda real
        # justamente no payload que o atendente humano vai ler no handoff.
        if nlp.intencao != Intencao.OUTROS or atendimento.intencao == Intencao.OUTROS:
            atendimento.intencao = nlp.intencao
            atendimento.confianca = nlp.confianca
        atendimento.score_friccao = avaliacao.score_atual
        atendimento.historico_score.append(avaliacao.score_atual)
        atendimento.ultima_mensagem = conteudo
        atendimento.atualizado_em = agora()

        await self._registrar_auditoria(protocolo, avaliacao)

        # 9. Quem responde este turno (ver docstring do módulo)
        fora_do_bot = atendimento.status in (
            StatusAtendimento.AGUARDANDO_HANDOFF,
            StatusAtendimento.EM_ATENDIMENTO_HUMANO,
        )
        motivo_handoff = None
        if avaliacao.deve_disparar_handoff:
            motivo_handoff = avaliacao.motivo_handoff
        elif not fora_do_bot and not ja_houve_handoff and self._pediu_humano(avaliacao):
            # Pedir uma pessoa é saída qualificada por si só — não precisa
            # esperar o score cruzar o limiar. O score continua o mesmo.
            motivo_handoff = "Cliente pediu atendimento humano explicitamente"

        acoes: list[ResultadoAcao] = []
        gerado_por_ia = False
        encerrar_ao_fim = False
        if motivo_handoff:
            origem = "handoff"
            await self._dialogo.abandonar(sessao)
            await self._acionar_handoff(atendimento, sessao, motivo_handoff, avaliacao.score_atual)
            resposta = self._respostas.gerar(
                intencao=nlp.intencao, protocolo=protocolo, handoff_acionado=True
            )
        elif fora_do_bot:
            origem = "fila_humana"
            resposta = self._respostas.gerar(
                intencao=nlp.intencao,
                protocolo=protocolo,
                handoff_acionado=False,
                em_atendimento_humano=True,
            )
        elif self._verificacao.precisa_verificar(sessao, canal):
            # 10a. Identidade antes de qualquer dado do cliente.
            origem = "verificacao"
            if not sessao.verificacao_pendente:
                resultado = self._verificacao.iniciar(sessao, conteudo)
                atendimento.identidade = PENDENTE
                resposta = resultado.resposta
                await self._sessoes.salvar(sessao)
            else:
                resultado = self._verificacao.responder(sessao, cliente, conteudo)
                resposta = resultado.resposta
                if resultado.confirmada:
                    atendimento.identidade = VERIFICADA_CPF
                    # Os turnos da verificação não contam como "sem resolução".
                    sessao = await self._sessoes.registrar_resolucao(sessao)
                    if resultado.mensagem_pendente:
                        # O pedido feito antes da confirmação é atendido agora.
                        pedido = resultado.mensagem_pendente
                        intencao_pedido = self._nlp.classificar(pedido).intencao
                        origem, extra, acoes, gerado_por_ia, motivo_handoff = (
                            await self._autoatender(
                                sessao, atendimento, pedido, intencao_pedido,
                                avaliacao.score_atual, protocolo,
                            )
                        )
                        if origem == "bot" and intencao_pedido == Intencao.OUTROS:
                            extra = "Como posso ajudar?"  # o pedido era só um "oi"
                        resposta = f"{resposta} {extra}"
                elif resultado.bloqueada:
                    atendimento.identidade = FALHOU
                    motivo_handoff = self._verificacao.motivo_bloqueio()
                    await self._acionar_handoff(
                        atendimento, sessao, motivo_handoff, avaliacao.score_atual
                    )
                    await self._sessoes.salvar(sessao)
                else:
                    await self._sessoes.salvar(sessao)
        elif (
            not resultado_sessao.nova
            and sessao.etapa_fluxo == EtapaFluxo.NENHUMA
            and eh_despedida(conteudo)
        ):
            # 10b. "Era só isso, obrigado": encerra e o aparelho mostra a pesquisa.
            origem = "encerramento"
            resposta = txt_dialogo.DESPEDIDA.format(nome=cliente.nome.split()[0])
            encerrar_ao_fim = True
        else:
            # 10c. Autoatendimento: grava no histórico, por conta própria, as
            # mensagens de sistema de cada ação executada.
            origem, resposta, acoes, gerado_por_ia, motivo_handoff = await self._autoatender(
                sessao, atendimento, conteudo, nlp.intencao, avaliacao.score_atual, protocolo
            )

        handoff_acionado = motivo_handoff is not None
        await self._conversas.adicionar_mensagem(
            Mensagem(
                protocolo=protocolo,
                remetente=Remetente.BOT,
                canal=canal,
                conteudo=resposta,
                # Marca discreta na interface: mostra à banca onde a IA entrou.
                metadados={"ia": True} if gerado_por_ia else {},
            )
        )

        atendimento.total_mensagens = await self._conversas.contar(protocolo)
        await self._atendimentos.salvar(atendimento)
        if encerrar_ao_fim:
            atendimento = await self.encerrar(protocolo)

        return ResultadoProcessamento(
            protocolo=protocolo,
            cliente=cliente,
            canal=canal,
            intencao=nlp.intencao,
            confianca=nlp.confianca,
            termos_detectados=nlp.termos_detectados,
            avaliacao=avaliacao,
            status=atendimento.status,
            handoff_acionado=handoff_acionado,
            troca_de_canal=resultado_sessao.troca_de_canal,
            sessao_nova=resultado_sessao.nova,
            resposta=resposta,
            total_mensagens=atendimento.total_mensagens,
            origem_resposta=origem,
            acoes=acoes,
            etapa_fluxo=sessao.etapa_fluxo,
            acao_pendente=sessao.acao_pendente,
            opcoes_resposta=self._dialogo.opcoes_resposta(sessao),
            gerado_por_ia=gerado_por_ia,
        )

    async def responder_como_atendente(
        self, *, protocolo: str, conteudo: str, atendente: str
    ) -> Atendimento:
        """Resposta humana no dashboard. Assume o atendimento e reduz a fricção."""
        atendimento = await self._atendimentos.obter(protocolo)
        if atendimento is None:
            raise AtendimentoNaoEncontrado()
        if atendimento.status == StatusAtendimento.ENCERRADO:
            raise AtendimentoEncerrado()

        await self._conversas.adicionar_mensagem(
            Mensagem(
                protocolo=protocolo,
                remetente=Remetente.ATENDENTE,
                canal=atendimento.canal_atual,
                conteudo=conteudo,
                autor=atendente,
            )
        )

        avaliacao = self._friccao.aplicar_decaimento(
            atendimento.score_friccao, f"Atendimento humano assumido por {atendente}"
        )
        await self._registrar_auditoria(protocolo, avaliacao)

        atendimento.status = StatusAtendimento.EM_ATENDIMENTO_HUMANO
        atendimento.atendente = atendente
        atendimento.score_friccao = avaliacao.score_atual
        atendimento.historico_score.append(avaliacao.score_atual)
        atendimento.ultima_mensagem = conteudo
        atendimento.atualizado_em = agora()
        atendimento.total_mensagens = await self._conversas.contar(protocolo)
        return await self._atendimentos.salvar(atendimento)

    async def transferir(
        self, *, protocolo: str, setor: Setor, motivo: str | None = None, por: str
    ) -> Atendimento:
        """Devolve o atendimento à fila, endereçado a outro setor.

        Transferir NÃO é encerrar: a sessão continua viva e o protocolo é o
        mesmo, então o cliente que voltar a escrever cai no mesmo histórico —
        que é justamente o que o produto promete. O atendente atual é liberado
        e o caso volta a aguardar handoff, agora com setor definido.
        """
        atendimento = await self._atendimentos.obter(protocolo)
        if atendimento is None:
            raise AtendimentoNaoEncontrado()
        if atendimento.status == StatusAtendimento.ENCERRADO:
            raise AtendimentoEncerrado()

        origem = atendimento.setor.rotulo if atendimento.setor else "Atendimento geral"
        detalhe = f" · Motivo: {motivo}" if motivo else ""

        await self._conversas.adicionar_mensagem(
            Mensagem(
                protocolo=protocolo,
                remetente=Remetente.SISTEMA,
                conteudo=(
                    f"↪ Atendimento transferido de {origem} para {setor.rotulo} "
                    f"por {por}{detalhe} · Contexto e protocolo preservados"
                ),
                metadados={
                    "tipo": "transferencia",
                    "de": origem,
                    "para": setor.rotulo,
                    "por": por,
                    "motivo": motivo,
                },
            )
        )

        atendimento.setor = setor
        atendimento.transferencias += 1
        atendimento.atendente = None
        atendimento.status = StatusAtendimento.AGUARDANDO_HANDOFF
        atendimento.ultima_mensagem = f"Transferido para {setor.rotulo}"
        atendimento.atualizado_em = agora()
        atendimento.total_mensagens = await self._conversas.contar(protocolo)
        return await self._atendimentos.salvar(atendimento)

    async def encerrar(self, protocolo: str) -> Atendimento:
        atendimento = await self._atendimentos.obter(protocolo)
        if atendimento is None:
            raise AtendimentoNaoEncontrado()

        # Idempotente: encerrar de novo não muda nada — nem a data, nem a
        # sessão, que a essa altura pode ser de uma conversa nova do cliente.
        if atendimento.status == StatusAtendimento.ENCERRADO:
            return atendimento

        # A mensagem de encerramento é o gatilho da avaliação no app do cliente.
        await self._conversas.adicionar_mensagem(
            Mensagem(
                protocolo=protocolo,
                remetente=Remetente.SISTEMA,
                conteudo="Atendimento encerrado. O cliente pode avaliar o atendimento.",
                metadados={"tipo": "encerramento"},
            )
        )

        atendimento.status = StatusAtendimento.ENCERRADO
        atendimento.encerrado_em = agora()
        atendimento.atualizado_em = agora()
        atendimento.total_mensagens = await self._conversas.contar(protocolo)
        await self._sessoes.encerrar(atendimento.cliente_id, protocolo)
        return await self._atendimentos.salvar(atendimento)

    async def avaliar(
        self, *, protocolo: str, nota: int, comentario: str | None = None
    ) -> Atendimento:
        """Avaliação do cliente (CSAT) — só faz sentido com o atendimento encerrado."""
        atendimento = await self._atendimentos.obter(protocolo)
        if atendimento is None:
            raise AtendimentoNaoEncontrado()
        if not 1 <= nota <= 5:
            raise VortexError("A nota deve estar entre 1 e 5")
        # Avaliar o que ainda está em curso distorce o CSAT; avaliar duas vezes
        # deixaria a última nota apagar a primeira.
        if atendimento.status != StatusAtendimento.ENCERRADO:
            raise VortexError("Só é possível avaliar um atendimento encerrado")
        if atendimento.nota is not None:
            raise VortexError("Este atendimento já foi avaliado")

        atendimento.nota = nota
        atendimento.comentario = (comentario or "").strip() or None
        atendimento.avaliado_em = agora()
        atendimento.atualizado_em = agora()

        await self._conversas.adicionar_mensagem(
            Mensagem(
                protocolo=protocolo,
                remetente=Remetente.SISTEMA,
                conteudo=f"Cliente avaliou o atendimento com {nota} de 5.",
                metadados={"tipo": "avaliacao", "nota": nota},
            )
        )
        atendimento.total_mensagens = await self._conversas.contar(protocolo)
        return await self._atendimentos.salvar(atendimento)

    # ------------------------------------------------------------------ interno

    async def _autoatender(self, sessao, atendimento, texto, intencao, score, protocolo):
        """Conversa guiada; se ela não tratar a mensagem, resposta comum do bot.

        Devolve (origem, resposta, ações, gerado_por_ia, motivo_handoff).
        """
        turno = await self._dialogo.conduzir(sessao=sessao, texto=texto, intencao=intencao)
        if not turno.tratado:
            resposta = self._respostas.gerar(
                intencao=intencao, protocolo=protocolo, handoff_acionado=False
            )
            return "bot", resposta, [], False, None

        acoes = turno.resultados
        if any(a.status == StatusAcao.SUCESSO and a.acao in RESOLVEM_A_DEMANDA for a in acoes):
            await self._sessoes.registrar_resolucao(sessao)
        motivo = None
        if turno.requer_handoff:
            motivo = self._motivo_autoatendimento(acoes)
            await self._acionar_handoff(atendimento, sessao, motivo, score)
        return "autoatendimento", turno.resposta or "", acoes, turno.ia, motivo

    async def _atendimento_com_humano(self, cliente_id: str) -> Atendimento | None:
        """Atendimento que deve sobreviver à expiração da sessão: o que está na
        fila humana ou com um atendente. Conversa abandonada com o bot, não."""
        ultimo = await self._atendimentos.ultimo_do_cliente(cliente_id)
        if ultimo is not None and ultimo.status in (
            StatusAtendimento.AGUARDANDO_HANDOFF,
            StatusAtendimento.EM_ATENDIMENTO_HUMANO,
        ):
            return ultimo
        return None

    @staticmethod
    def _pediu_humano(avaliacao: AvaliacaoFriccao) -> bool:
        return any(s.codigo == CodigoSinal.PEDIDO_HUMANO for s in avaliacao.sinais)

    @staticmethod
    def _motivo_autoatendimento(acoes: list[ResultadoAcao]) -> str:
        """Por que o bot desistiu, em uma frase legível para o atendente."""
        decisiva = next((a for a in reversed(acoes) if a.requer_handoff), None)
        if decisiva is None:
            return "Autoatendimento sem solução para a demanda"
        if decisiva.dados.get("motivo") == "cancelamento":
            return "Pedido de cancelamento — não é feito pelo autoatendimento"
        return f"Autoatendimento sem solução — {decisiva.mensagem}"

    async def _acionar_handoff(
        self, atendimento: Atendimento, sessao: Sessao, motivo: str, score: int
    ) -> None:
        atendimento.status = StatusAtendimento.AGUARDANDO_HANDOFF
        atendimento.handoff_em = agora()
        atendimento.handoff_motivo = motivo
        canais = ", ".join(c.rotulo for c in sessao.canais_utilizados)
        await self._conversas.adicionar_mensagem(
            Mensagem(
                protocolo=atendimento.protocolo,
                remetente=Remetente.SISTEMA,
                conteudo=(
                    f"⚡ Handoff acionado · {motivo} · Score de fricção {score} · "
                    f"Contexto consolidado dos canais {canais}"
                ),
                metadados={"tipo": "handoff", "score": score, "motivo": motivo},
            )
        )

    async def _registrar_auditoria(self, protocolo: str, avaliacao: AvaliacaoFriccao) -> None:
        if not avaliacao.sinais:
            return
        await self._atendimentos.registrar_eventos(
            [
                EventoFriccao(
                    protocolo=protocolo,
                    codigo_sinal=sinal.codigo,
                    peso=sinal.peso,
                    score_resultante=avaliacao.score_atual,
                    descricao=sinal.descricao,
                )
                for sinal in avaliacao.sinais
            ]
        )
