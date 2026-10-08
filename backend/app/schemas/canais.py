"""Contratos dos canais de entrada.

Cada canal tem o SEU formato — o App manda `usuario_id`/`mensagem`, o WhatsApp
simula o envelope de webhook da Meta. É justamente essa tradução que o
orquestrador faz: dois formatos externos, um único caso de uso interno.
"""

from datetime import datetime

from pydantic import BaseModel, Field

from app.domain.enums import (
    AcaoAutoatendimento,
    Canal,
    EtapaFluxo,
    Intencao,
    NivelFriccao,
    StatusAcao,
    StatusAtendimento,
)
from app.domain.models import agora


class MensagemAppIn(BaseModel):
    """POST /channels/app — payload do App Claro."""

    usuario_id: str = Field(description="Identificador de login no app", examples=["user_ana"])
    mensagem: str = Field(min_length=1, max_length=2000)
    dispositivo: str | None = Field(default=None, examples=["android-14"])
    versao_app: str | None = Field(default=None, examples=["8.32.1"])


class MensagemWhatsAppIn(BaseModel):
    """POST /channels/whatsapp — envelope simplificado de webhook."""

    telefone: str = Field(description="MSISDN do remetente", examples=["5511998877321"])
    mensagem: str = Field(min_length=1, max_length=2000)
    message_id: str | None = Field(default=None, examples=["wamid.HBgM..."])
    enviada_em: datetime = Field(default_factory=agora)


class SinalOut(BaseModel):
    codigo: str
    peso: int
    descricao: str


class AcaoOut(BaseModel):
    """Ação de autoatendimento executada (ou validada) neste turno.

    `dados` é estruturado de propósito: o simulador monta os cartões (fatura,
    diagnóstico, planos, protocolo) sem extrair nada do texto.
    """

    acao: AcaoAutoatendimento | None
    status: StatusAcao
    codigo: str
    mensagem: str
    dados: dict = Field(default_factory=dict)
    protocolo_solicitacao: str | None = None
    requer_handoff: bool = False


class OpcaoRespostaOut(BaseModel):
    rotulo: str = Field(description="O que o botão mostra")
    texto: str = Field(description="O que o botão envia como mensagem do cliente")


class FluxoOut(BaseModel):
    """Conversa guiada em andamento: o que o bot está esperando do cliente."""

    etapa: EtapaFluxo
    acao_pendente: AcaoAutoatendimento | None = None
    opcoes: list[OpcaoRespostaOut] = Field(default_factory=list)


class MensagemCanalOut(BaseModel):
    """Resposta única dos dois canais — é o que os simuladores do frontend consomem."""

    protocolo: str
    cliente_ref: str
    nome_cliente: str
    canal: Canal

    intencao: Intencao
    intencao_rotulo: str
    confianca: int
    termos_detectados: list[str]

    score_friccao: int
    score_anterior: int
    delta_score: int
    nivel: NivelFriccao
    sinais: list[SinalOut]

    status: StatusAtendimento
    handoff_acionado: bool
    troca_de_canal: bool
    sessao_nova: bool

    resposta: str
    origem_resposta: str = Field(
        description="Quem respondeu: autoatendimento, bot, handoff ou fila_humana"
    )
    acoes: list[AcaoOut] = Field(default_factory=list)
    fluxo: FluxoOut | None = None
    gerado_por_ia: bool = Field(
        default=False, description="A IA interpretou a mensagem ou escreveu a resposta"
    )

    total_mensagens: int
    processado_em: datetime = Field(default_factory=agora)
    latencia_ms: float = Field(description="Requisito não-funcional: manter < 2000ms")
