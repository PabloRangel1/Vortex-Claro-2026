"""Contratos do painel do atendente."""

from datetime import date, datetime

from pydantic import BaseModel, Field

from app.domain.enums import (
    Canal,
    Intencao,
    NivelFriccao,
    Remetente,
    Setor,
    Segmento,
    StatusAtendimento,
)
from app.schemas.canais import FluxoOut


class ClienteOut(BaseModel):
    cliente_ref: str
    nome: str
    cpf_mascarado: str
    plano: str
    cliente_desde: str
    email: str | None = None
    cidade: str | None = None


class MensagemOut(BaseModel):
    id: str
    remetente: Remetente
    canal: Canal | None
    canal_rotulo: str | None
    conteudo: str
    intencao: Intencao | None
    confianca: int | None
    autor: str | None
    criada_em: datetime
    metadados: dict = Field(default_factory=dict)


class EventoFriccaoOut(BaseModel):
    codigo_sinal: str
    peso: int
    score_resultante: int
    descricao: str
    criado_em: datetime


class HandoffOut(BaseModel):
    acionado: bool
    em: datetime | None = None
    motivo: str | None = None


class AvaliacaoOut(BaseModel):
    nota: int | None = None
    comentario: str | None = None
    em: datetime | None = None


class ContatoAnteriorOut(BaseModel):
    protocolo: str
    aberto_em: datetime
    status: StatusAtendimento
    intencao: Intencao
    intencao_rotulo: str
    houve_handoff: bool
    nota: int | None = None


class AtendimentoDashboardOut(BaseModel):
    """GET /dashboard/atendimento/{protocolo} — payload completo do painel."""

    protocolo: str
    cliente: ClienteOut

    canal_origem: Canal
    canal_origem_rotulo: str
    canal_atual: Canal
    canal_atual_rotulo: str
    canais_utilizados: list[Canal]
    houve_troca_de_canal: bool

    status: StatusAtendimento
    # verificada_app · verificada_cpf · pendente · falhou · nao_verificada
    identidade: str = "nao_verificada"
    atendente: str | None
    setor: Setor | None = None
    setor_rotulo: str | None = None
    transferencias: int = 0
    avaliacao: AvaliacaoOut = Field(default_factory=AvaliacaoOut)
    encerrado_em: datetime | None = None

    intencao: Intencao
    intencao_rotulo: str
    confianca: int

    score_friccao: int
    score_inicial: int
    delta_score: int
    nivel: NivelFriccao
    historico_score: list[int]

    handoff: HandoffOut
    # Conversa guiada em andamento neste protocolo (None se não houver).
    fluxo: FluxoOut | None = None
    # Cliente que volta muitas vezes é sinal de fricção que nenhum turno isolado mostra.
    contatos_30_dias: int = 1
    contatos_anteriores: list[ContatoAnteriorOut] = Field(default_factory=list)
    mensagens: list[MensagemOut]
    eventos_friccao: list[EventoFriccaoOut]

    total_mensagens: int
    aberto_em: datetime
    atualizado_em: datetime
    duracao_segundos: int


class FilaItemOut(BaseModel):
    """GET /dashboard/fila — item da coluna esquerda do painel."""

    protocolo: str
    cliente_ref: str
    nome: str
    canal_atual: Canal
    canal_origem: Canal
    houve_troca_de_canal: bool
    status: StatusAtendimento
    setor: Setor | None = None
    setor_rotulo: str | None = None
    # Tipo de cliente (pelo produto) — filtro da fila.
    segmento: Segmento = Segmento.POS
    segmento_rotulo: str = "Pós-pago"
    plano: str = ""
    intencao: Intencao
    intencao_rotulo: str
    confianca: int
    score_friccao: int
    nivel: NivelFriccao
    ultima_mensagem: str
    aguardando_desde: datetime
    espera_segundos: int


class RespostaAtendenteIn(BaseModel):
    conteudo: str = Field(min_length=1, max_length=2000)
    atendente: str = Field(default="Marcos Ribeiro", max_length=120)


class TransferenciaIn(BaseModel):
    setor: Setor
    motivo: str | None = Field(default=None, max_length=280)
    por: str = Field(default="Marcos Ribeiro", max_length=120)


class AvaliacaoIn(BaseModel):
    """CSAT preenchido pelo cliente no app, após o encerramento."""

    nota: int = Field(ge=1, le=5, description="1 = muito insatisfeito, 5 = muito satisfeito")
    comentario: str | None = Field(default=None, max_length=500)


# ------------------------------------------------- histórico e protocolos


class ResumoAtendimentoOut(BaseModel):
    """Uma linha da linha do tempo de um cliente."""

    protocolo: str
    aberto_em: datetime
    encerrado_em: datetime | None = None
    canal_origem: Canal
    canais_utilizados: list[Canal]
    status: StatusAtendimento
    intencao: Intencao
    intencao_rotulo: str
    score_friccao: int
    houve_handoff: bool
    handoff_motivo: str | None = None
    identidade: str
    nota: int | None = None
    comentario: str | None = None


class SolicitacaoOut(BaseModel):
    protocolo: str
    protocolo_atendimento: str
    tipo: str
    status: str
    descricao: str
    criada_em: datetime


class ClienteListaOut(BaseModel):
    """GET /dashboard/clientes — um cliente na lista do histórico."""

    cliente_ref: str
    nome: str
    cpf_mascarado: str
    plano: str
    segmento: Segmento
    segmento_rotulo: str
    cidade: str | None = None
    total_atendimentos: int
    em_aberto: bool
    ultimo_contato: datetime | None = None
    csat_medio: float | None = None


class HistoricoClienteOut(BaseModel):
    """GET /dashboard/clientes/{id}/historico — tudo o que o cliente já viveu conosco."""

    cliente: ClienteOut
    segmento: Segmento
    segmento_rotulo: str
    data_nascimento: date | None = None
    telefone_whatsapp: str | None = None
    usuario_app: str | None = None
    atendimentos: list[ResumoAtendimentoOut]
    solicitacoes: list[SolicitacaoOut]


class ProtocoloOut(BaseModel):
    """GET /dashboard/protocolo/{p} — resolve atendimento (AAAA-MMDD-NNNNN) ou solicitação (SOL-…)."""

    protocolo_atendimento: str
    cliente_ref: str
    solicitacao: SolicitacaoOut | None = None
