"""Painel do atendente humano."""

from datetime import timedelta

from fastapi import APIRouter, HTTPException, status

from app.dependencies import (
    AtendimentoRepoDep,
    OperacaoRepoDep,
    ClienteRepoDep,
    ConversaRepoDep,
    EstatisticasDep,
    FriccaoDep,
    OrquestradorDep,
    SessaoRepoDep,
)
from app.domain.enums import (
    Canal,
    EtapaFluxo,
    Segmento,
    Setor,
    StatusAtendimento,
    segmento_do_plano,
)
from app.core.referencia import referencia as ref_publica
from app.domain.exceptions import AtendimentoNaoEncontrado
from app.domain.models import Atendimento, agora
from app.schemas.canais import FluxoOut
from app.schemas.dashboard import (
    AtendimentoDashboardOut,
    AvaliacaoIn,
    AvaliacaoOut,
    ClienteListaOut,
    ClienteOut,
    ContatoAnteriorOut,
    HistoricoClienteOut,
    ProtocoloOut,
    ResumoAtendimentoOut,
    SolicitacaoOut,
    EventoFriccaoOut,
    FilaItemOut,
    HandoffOut,
    MensagemOut,
    RespostaAtendenteIn,
    TransferenciaIn,
)
from app.services.dialogo_service import DialogoService

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

# Janela do "quantas vezes este cliente nos procurou" no painel do atendente.
JANELA_HISTORICO_DIAS = 30


@router.get(
    "/fila",
    response_model=list[FilaItemOut],
    summary="Fila de atendimentos aguardando handoff",
)
async def listar_fila(
    atendimentos: AtendimentoRepoDep,
    clientes: ClienteRepoDep,
    friccao: FriccaoDep,
    incluir_em_atendimento: bool = True,
):
    alvos = [StatusAtendimento.AGUARDANDO_HANDOFF]
    if incluir_em_atendimento:
        alvos.append(StatusAtendimento.EM_ATENDIMENTO_HUMANO)

    registros = await atendimentos.listar_por_status(*alvos)
    agora_ts = agora()
    itens: list[FilaItemOut] = []

    for a in registros:
        cliente = await clientes.obter(a.cliente_id)
        referencia = a.handoff_em or a.aberto_em
        segmento = segmento_do_plano(cliente.plano_id if cliente else None)
        itens.append(
            FilaItemOut(
                protocolo=a.protocolo,
                cliente_ref=ref_publica(a.cliente_id),
                nome=cliente.nome if cliente else "Cliente",
                canal_atual=a.canal_atual,
                canal_origem=a.canal_origem,
                houve_troca_de_canal=len(a.canais_utilizados) > 1,
                status=a.status,
                setor=a.setor,
                setor_rotulo=a.setor.rotulo if a.setor else None,
                segmento=segmento,
                segmento_rotulo=segmento.rotulo,
                plano=cliente.plano if cliente else "",
                intencao=a.intencao,
                intencao_rotulo=a.intencao.rotulo,
                confianca=a.confianca,
                score_friccao=a.score_friccao,
                nivel=friccao.nivel(a.score_friccao),
                ultima_mensagem=a.ultima_mensagem,
                aguardando_desde=referencia,
                espera_segundos=int((agora_ts - referencia).total_seconds()),
            )
        )

    itens.sort(key=lambda i: (-i.score_friccao, -i.espera_segundos))
    return itens


@router.get(
    "/atendimento/{protocolo}",
    response_model=AtendimentoDashboardOut,
    summary="Contexto consolidado de um atendimento",
)
async def obter_atendimento(
    protocolo: str,
    atendimentos: AtendimentoRepoDep,
    conversas: ConversaRepoDep,
    clientes: ClienteRepoDep,
    friccao: FriccaoDep,
    sessoes: SessaoRepoDep,
):
    atendimento = await atendimentos.obter(protocolo)
    if atendimento is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=AtendimentoNaoEncontrado().mensagem
        )

    # O fluxo pendente mora na sessão, que é do cliente: só vale para este
    # protocolo se a sessão ainda for a dele e o bot ainda estiver no comando.
    fluxo = None
    sessao = await sessoes.obter(atendimento.cliente_id)
    if (
        sessao is not None
        and sessao.protocolo == protocolo
        and sessao.etapa_fluxo != EtapaFluxo.NENHUMA
        and atendimento.status == StatusAtendimento.BOT_ATIVO
    ):
        fluxo = FluxoOut(
            etapa=sessao.etapa_fluxo,
            acao_pendente=sessao.acao_pendente,
            opcoes=DialogoService.opcoes_resposta(sessao),
        )

    cliente = await clientes.obter(atendimento.cliente_id)
    if cliente is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Cliente do atendimento não encontrado"
        )

    mensagens = await conversas.listar_mensagens(protocolo)
    eventos = await atendimentos.listar_eventos(protocolo)

    limite = atendimento.aberto_em - timedelta(days=JANELA_HISTORICO_DIAS)
    recentes = [
        a for a in await atendimentos.listar_do_cliente(atendimento.cliente_id)
        if a.aberto_em >= limite and a.aberto_em <= atendimento.aberto_em
    ]
    anteriores = [a for a in recentes if a.protocolo != protocolo][:5]

    return AtendimentoDashboardOut(
        protocolo=atendimento.protocolo,
        cliente=_cliente_out(cliente),
        canal_origem=atendimento.canal_origem,
        canal_origem_rotulo=atendimento.canal_origem.rotulo,
        canal_atual=atendimento.canal_atual,
        canal_atual_rotulo=atendimento.canal_atual.rotulo,
        canais_utilizados=atendimento.canais_utilizados,
        houve_troca_de_canal=len(atendimento.canais_utilizados) > 1,
        status=atendimento.status,
        identidade=atendimento.identidade,
        atendente=atendimento.atendente,
        setor=atendimento.setor,
        setor_rotulo=atendimento.setor.rotulo if atendimento.setor else None,
        transferencias=atendimento.transferencias,
        avaliacao=AvaliacaoOut(
            nota=atendimento.nota,
            comentario=atendimento.comentario,
            em=atendimento.avaliado_em,
        ),
        encerrado_em=atendimento.encerrado_em,
        intencao=atendimento.intencao,
        intencao_rotulo=atendimento.intencao.rotulo,
        confianca=atendimento.confianca,
        score_friccao=atendimento.score_friccao,
        score_inicial=atendimento.score_inicial,
        delta_score=atendimento.score_friccao - atendimento.score_inicial,
        nivel=friccao.nivel(atendimento.score_friccao),
        historico_score=atendimento.historico_score,
        handoff=HandoffOut(
            acionado=atendimento.handoff_em is not None,
            em=atendimento.handoff_em,
            motivo=atendimento.handoff_motivo,
        ),
        fluxo=fluxo,
        contatos_30_dias=len(recentes),
        contatos_anteriores=[
            ContatoAnteriorOut(
                protocolo=a.protocolo,
                aberto_em=a.aberto_em,
                status=a.status,
                intencao=a.intencao,
                intencao_rotulo=a.intencao.rotulo,
                houve_handoff=a.handoff_em is not None,
                nota=a.nota,
            )
            for a in anteriores
        ],
        mensagens=[
            MensagemOut(
                id=m.id,
                remetente=m.remetente,
                canal=m.canal,
                canal_rotulo=m.canal.rotulo if m.canal else None,
                conteudo=m.conteudo,
                intencao=m.intencao,
                confianca=m.confianca,
                autor=m.autor,
                criada_em=m.criada_em,
                metadados=m.metadados,
            )
            for m in mensagens
        ],
        eventos_friccao=[
            EventoFriccaoOut(
                codigo_sinal=str(e.codigo_sinal),
                peso=e.peso,
                score_resultante=e.score_resultante,
                descricao=e.descricao,
                criado_em=e.criado_em,
            )
            for e in eventos
        ],
        total_mensagens=len(mensagens),
        aberto_em=atendimento.aberto_em,
        atualizado_em=atendimento.atualizado_em,
        duracao_segundos=int((agora() - atendimento.aberto_em).total_seconds()),
    )


@router.post(
    "/atendimento/{protocolo}/responder",
    response_model=AtendimentoDashboardOut,
    summary="Atendente humano responde ao cliente",
)
async def responder(
    protocolo: str,
    payload: RespostaAtendenteIn,
    orquestrador: OrquestradorDep,
    atendimentos: AtendimentoRepoDep,
    conversas: ConversaRepoDep,
    clientes: ClienteRepoDep,
    friccao: FriccaoDep,
    sessoes: SessaoRepoDep,
):
    await orquestrador.responder_como_atendente(
        protocolo=protocolo, conteudo=payload.conteudo, atendente=payload.atendente
    )
    return await obter_atendimento(protocolo, atendimentos, conversas, clientes, friccao, sessoes)


@router.post(
    "/atendimento/{protocolo}/transferir",
    response_model=AtendimentoDashboardOut,
    summary="Transfere o atendimento para outro setor",
)
async def transferir(
    protocolo: str,
    payload: TransferenciaIn,
    orquestrador: OrquestradorDep,
    atendimentos: AtendimentoRepoDep,
    conversas: ConversaRepoDep,
    clientes: ClienteRepoDep,
    friccao: FriccaoDep,
    sessoes: SessaoRepoDep,
):
    await orquestrador.transferir(
        protocolo=protocolo, setor=payload.setor, motivo=payload.motivo, por=payload.por
    )
    return await obter_atendimento(protocolo, atendimentos, conversas, clientes, friccao, sessoes)


@router.get("/setores", response_model=list[dict], summary="Setores de destino")
async def listar_setores() -> list[dict]:
    return [{"valor": str(s), "rotulo": s.rotulo} for s in Setor]


@router.post(
    "/atendimento/{protocolo}/encerrar",
    response_model=dict,
    summary="Encerra o atendimento e libera a sessão",
)
async def encerrar(protocolo: str, orquestrador: OrquestradorDep) -> dict:
    atendimento: Atendimento = await orquestrador.encerrar(protocolo)
    return {"protocolo": atendimento.protocolo, "status": atendimento.status}


@router.post(
    "/atendimento/{protocolo}/avaliar",
    response_model=dict,
    summary="Cliente avalia o atendimento encerrado (CSAT)",
)
async def avaliar(protocolo: str, payload: AvaliacaoIn, orquestrador: OrquestradorDep) -> dict:
    atendimento = await orquestrador.avaliar(
        protocolo=protocolo, nota=payload.nota, comentario=payload.comentario
    )
    return {
        "protocolo": atendimento.protocolo,
        "nota": atendimento.nota,
        "comentario": atendimento.comentario,
    }


@router.get(
    "/estatisticas",
    response_model=dict,
    summary="Agregações: do que os clientes reclamam e onde a fricção se concentra",
)
async def estatisticas(
    atendimentos: AtendimentoRepoDep,
    conversas: ConversaRepoDep,
    clientes: ClienteRepoDep,
    operacao: OperacaoRepoDep,
    estat: EstatisticasDep,
) -> dict:
    planos = {p.id: p.preco_centavos for p in await operacao.listar_planos()}
    precos = {c.cliente_id: planos.get(c.plano_id, 0) for c in await clientes.listar()}
    return estat.consolidar(
        await atendimentos.listar_todos(),
        await atendimentos.listar_todos_eventos(),
        await conversas.listar_registros_autoatendimento(),
        precos_por_cliente=precos,
    )


# ------------------------------------------------- histórico e protocolos


def _cliente_out(cliente) -> ClienteOut:
    """O cliente como sai para o navegador: referência opaca, nunca o CPF."""
    dados = cliente.model_dump(exclude={"identificadores", "cliente_id"})
    return ClienteOut(cliente_ref=ref_publica(cliente.cliente_id), **dados)


async def _por_referencia(clientes, ref: str):
    return next((c for c in await clientes.listar() if ref_publica(c.cliente_id) == ref), None)


def _resumo(a: Atendimento) -> ResumoAtendimentoOut:
    return ResumoAtendimentoOut(
        protocolo=a.protocolo,
        aberto_em=a.aberto_em,
        encerrado_em=a.encerrado_em,
        canal_origem=a.canal_origem,
        canais_utilizados=a.canais_utilizados,
        status=a.status,
        intencao=a.intencao,
        intencao_rotulo=a.intencao.rotulo,
        score_friccao=a.score_friccao,
        houve_handoff=a.handoff_em is not None,
        handoff_motivo=a.handoff_motivo,
        identidade=a.identidade,
        nota=a.nota,
        comentario=a.comentario,
    )


def _solicitacao(s) -> SolicitacaoOut:
    return SolicitacaoOut(
        protocolo=s.protocolo,
        protocolo_atendimento=s.protocolo_atendimento,
        tipo=str(s.tipo),
        status=str(s.status),
        descricao=s.descricao,
        criada_em=s.criada_em,
    )


@router.get(
    "/clientes",
    response_model=list[ClienteListaOut],
    summary="Clientes, com filtro por tipo (segmento) e busca por nome ou CPF",
)
async def listar_clientes_historico(
    clientes: ClienteRepoDep,
    atendimentos: AtendimentoRepoDep,
    segmento: Segmento | None = None,
    busca: str | None = None,
):
    por_cliente: dict[str, list[Atendimento]] = {}
    for a in await atendimentos.listar_todos():
        por_cliente.setdefault(a.cliente_id, []).append(a)

    termo = (busca or "").strip().lower()
    digitos = "".join(ch for ch in termo if ch.isdigit())
    linhas = []
    for c in await clientes.listar():
        seg = segmento_do_plano(c.plano_id)
        if segmento and seg != segmento:
            continue
        if termo and termo not in c.nome.lower() and not (digitos and digitos in c.cliente_id):
            continue
        dele = por_cliente.get(c.cliente_id, [])
        notas = [a.nota for a in dele if a.nota is not None]
        linhas.append(
            ClienteListaOut(
                cliente_ref=ref_publica(c.cliente_id),
                nome=c.nome,
                cpf_mascarado=c.cpf_mascarado,
                plano=c.plano,
                segmento=seg,
                segmento_rotulo=seg.rotulo,
                cidade=c.cidade,
                total_atendimentos=len(dele),
                em_aberto=any(a.status != StatusAtendimento.ENCERRADO for a in dele),
                ultimo_contato=max((a.aberto_em for a in dele), default=None),
                csat_medio=round(sum(notas) / len(notas), 1) if notas else None,
            )
        )
    # Quem falou com a gente mais recentemente aparece primeiro.
    linhas.sort(key=lambda l: l.ultimo_contato.timestamp() if l.ultimo_contato else 0, reverse=True)
    return linhas


@router.get(
    "/clientes/{cliente_ref}/historico",
    response_model=HistoricoClienteOut,
    summary="Histórico completo do cliente: atendimentos, solicitações e avaliações",
)
async def historico_cliente(
    cliente_ref: str,
    clientes: ClienteRepoDep,
    atendimentos: AtendimentoRepoDep,
    operacao: OperacaoRepoDep,
):
    cliente = await _por_referencia(clientes, cliente_ref)
    if cliente is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cliente não encontrado")
    cliente_id = cliente.cliente_id
    seg = segmento_do_plano(cliente.plano_id)
    solicitacoes = await operacao.listar_solicitacoes(cliente_id)
    return HistoricoClienteOut(
        cliente=_cliente_out(cliente),
        segmento=seg,
        segmento_rotulo=seg.rotulo,
        data_nascimento=cliente.data_nascimento,
        telefone_whatsapp=cliente.identificadores.get(Canal.WHATSAPP),
        usuario_app=cliente.identificadores.get(Canal.APP),
        atendimentos=[_resumo(a) for a in await atendimentos.listar_do_cliente(cliente_id)],
        solicitacoes=[
            _solicitacao(s) for s in sorted(solicitacoes, key=lambda s: s.criada_em, reverse=True)
        ],
    )


@router.get(
    "/protocolo/{protocolo}",
    response_model=ProtocoloOut,
    summary="Localiza um protocolo de atendimento ou de solicitação (SOL-…)",
)
async def buscar_protocolo(
    protocolo: str, atendimentos: AtendimentoRepoDep, operacao: OperacaoRepoDep
):
    alvo = protocolo.strip().upper()
    if alvo.startswith("SOL-"):
        sol = await operacao.obter_solicitacao(alvo)
        if sol is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Protocolo não encontrado")
        return ProtocoloOut(
            protocolo_atendimento=sol.protocolo_atendimento,
            cliente_ref=ref_publica(sol.cliente_id),
            solicitacao=_solicitacao(sol),
        )
    atendimento = await atendimentos.obter(alvo)
    if atendimento is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Protocolo não encontrado")
    return ProtocoloOut(
        protocolo_atendimento=atendimento.protocolo, cliente_ref=ref_publica(atendimento.cliente_id)
    )
