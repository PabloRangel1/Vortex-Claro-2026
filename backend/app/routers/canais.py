"""Canais de entrada.

Os dois endpoints são finos de propósito: adaptam o payload específico do
canal e delegam para o mesmo caso de uso. Adicionar um terceiro canal
(URA, Telegram) custa ~15 linhas aqui e zero em services.
"""

from time import perf_counter

from fastapi import APIRouter, status

from app.core.referencia import referencia
from app.dependencies import AtendimentoRepoDep, ClienteRepoDep, OrquestradorDep
from app.domain.enums import Canal
from app.domain.exceptions import ClienteNaoIdentificado
from app.domain.models import ResultadoProcessamento
from app.schemas.canais import (
    AcaoOut,
    FluxoOut,
    MensagemAppIn,
    MensagemCanalOut,
    MensagemWhatsAppIn,
    SinalOut,
)

router = APIRouter(prefix="/channels", tags=["Canais"])


@router.get(
    "/atendimento-atual",
    summary="Protocolo em curso do cliente, na visão do próprio aparelho",
)
async def atendimento_atual(
    canal: Canal,
    identificador: str,
    clientes: ClienteRepoDep,
    atendimentos: AtendimentoRepoDep,
) -> dict:
    """O aparelho do cliente usa isto ao abrir para retomar a conversa.

    Sem ele a tela começa vazia mesmo havendo atendimento em curso — e a
    avaliação pós-encerramento nunca chegaria ao cliente.
    """
    cliente = await clientes.resolver_por_identificador(canal, identificador)
    if cliente is None:
        raise ClienteNaoIdentificado(
            f"Identificador '{identificador}' não está vinculado a nenhum cliente"
        )

    atendimento = await atendimentos.ultimo_do_cliente(cliente.cliente_id)
    return {
        "protocolo": atendimento.protocolo if atendimento else None,
        "status": atendimento.status if atendimento else None,
    }


def _montar_resposta(resultado: ResultadoProcessamento, latencia_ms: float) -> MensagemCanalOut:
    a = resultado.avaliacao
    return MensagemCanalOut(
        protocolo=resultado.protocolo,
        cliente_ref=referencia(resultado.cliente.cliente_id),
        nome_cliente=resultado.cliente.nome,
        canal=resultado.canal,
        intencao=resultado.intencao,
        intencao_rotulo=resultado.intencao.rotulo,
        confianca=resultado.confianca,
        termos_detectados=resultado.termos_detectados,
        score_friccao=a.score_atual,
        score_anterior=a.score_anterior,
        delta_score=a.delta,
        nivel=a.nivel,
        sinais=[
            SinalOut(codigo=str(s.codigo), peso=s.peso, descricao=s.descricao) for s in a.sinais
        ],
        status=resultado.status,
        handoff_acionado=resultado.handoff_acionado,
        troca_de_canal=resultado.troca_de_canal,
        sessao_nova=resultado.sessao_nova,
        resposta=resultado.resposta,
        origem_resposta=resultado.origem_resposta,
        gerado_por_ia=resultado.gerado_por_ia,
        acoes=[
            AcaoOut(
                acao=r.acao,
                status=r.status,
                codigo=r.codigo,
                mensagem=r.mensagem,
                dados=r.dados,
                protocolo_solicitacao=r.solicitacao.protocolo if r.solicitacao else None,
                requer_handoff=r.requer_handoff,
            )
            for r in resultado.acoes
        ],
        fluxo=(
            FluxoOut(
                etapa=resultado.etapa_fluxo,
                acao_pendente=resultado.acao_pendente,
                opcoes=resultado.opcoes_resposta,
            )
            if resultado.acao_pendente
            else None
        ),
        total_mensagens=resultado.total_mensagens,
        latencia_ms=round(latencia_ms, 2),
    )


@router.post(
    "/app",
    response_model=MensagemCanalOut,
    status_code=status.HTTP_200_OK,
    summary="Recebe mensagem do App Claro",
)
async def receber_do_app(payload: MensagemAppIn, orquestrador: OrquestradorDep):
    inicio = perf_counter()
    resultado = await orquestrador.processar_mensagem(
        canal=Canal.APP,
        identificador=payload.usuario_id,
        conteudo=payload.mensagem,
        metadados={"dispositivo": payload.dispositivo, "versao_app": payload.versao_app},
    )
    return _montar_resposta(resultado, (perf_counter() - inicio) * 1000)


@router.post(
    "/whatsapp",
    response_model=MensagemCanalOut,
    status_code=status.HTTP_200_OK,
    summary="Recebe webhook do WhatsApp",
)
async def receber_do_whatsapp(payload: MensagemWhatsAppIn, orquestrador: OrquestradorDep):
    inicio = perf_counter()
    resultado = await orquestrador.processar_mensagem(
        canal=Canal.WHATSAPP,
        identificador=payload.telefone,
        conteudo=payload.mensagem,
        metadados={
            "message_id": payload.message_id,
            "enviada_em": payload.enviada_em.isoformat(),
        },
    )
    return _montar_resposta(resultado, (perf_counter() - inicio) * 1000)
