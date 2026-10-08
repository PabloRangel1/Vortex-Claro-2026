"""Entidades de domínio.

Modeladas já no formato de destino:
  Cliente / Atendimento / EventoFriccao  -> tabelas PostgreSQL
  Mensagem                               -> documentos MongoDB (embedados por protocolo)
  Sessao                                 -> hash Redis com TTL
"""

from datetime import date, datetime
from uuid import uuid4

from pydantic import BaseModel, Field

from app.domain.enums import (
    AcaoAutoatendimento,
    Canal,
    CategoriaPlano,
    CodigoSinal,
    EtapaFluxo,
    Intencao,
    NivelFriccao,
    Remetente,
    Setor,
    StatusAcao,
    StatusAtendimento,
    StatusConexao,
    StatusFatura,
    StatusSolicitacao,
    TipoSolicitacao,
)


def agora() -> datetime:
    # Delegado ao relógio central para a simulação poder "voltar no tempo".
    from app.core.relogio import agora as _agora

    return _agora()


def novo_id() -> str:
    return uuid4().hex


class Cliente(BaseModel):
    """Futuro: tabela `clientes` (PK cliente_id).

    `identificadores` é o que resolve a continuidade cross-canal: o WhatsApp
    conhece o cliente pelo telefone, o App pelo id de login. Ambos apontam
    para o mesmo cliente_id canônico.
    """

    cliente_id: str
    nome: str
    cpf_mascarado: str
    plano: str
    cliente_desde: str
    identificadores: dict[Canal, str] = Field(default_factory=dict)

    # Dados contratuais usados pelo autoatendimento. Opcionais para não quebrar
    # nada que já construa `Cliente` sem eles.
    plano_id: str | None = None
    dia_vencimento: int | None = None

    # Cadastro (fictício) consultado pelo atendente.
    data_nascimento: date | None = None
    email: str | None = None
    cidade: str | None = None


class Sessao(BaseModel):
    """Futuro: `sessao:{cliente_id}` no Redis, com TTL.

    Guarda o estado volátil do atendimento em curso — inclusive o protocolo,
    que é o que faz App e WhatsApp escreverem na MESMA conversa.
    """

    cliente_id: str
    protocolo: str
    canal_ativo: Canal
    canal_origem: Canal
    canais_utilizados: list[Canal] = Field(default_factory=list)
    iniciada_em: datetime = Field(default_factory=agora)
    ultima_interacao: datetime = Field(default_factory=agora)
    turnos: int = 0
    intencao_atual: Intencao | None = None
    turnos_mesma_intencao: int = 0

    # Conversa guiada. A sessão é única por cliente, então o estado pendente
    # atravessa canais: pergunta no App, resposta no WhatsApp.
    etapa_fluxo: EtapaFluxo = EtapaFluxo.NENHUMA
    acao_pendente: AcaoAutoatendimento | None = None
    dados_pendentes: dict = Field(default_factory=dict)
    tentativas_etapa: int = 0

    # Verificação de identidade (WhatsApp). `mensagem_pendente` guarda o pedido
    # feito antes da confirmação, para ele ser atendido logo depois dela.
    identidade_verificada: bool = False
    verificacao_pendente: bool = False
    tentativas_verificacao: int = 0
    mensagem_pendente: str | None = None
    # A expiração NÃO é calculada aqui: o TTL é responsabilidade do
    # SessaoRepository, porque no Redis ele é nativo da chave.


class Mensagem(BaseModel):
    """Futuro: item do array `mensagens` no documento MongoDB da conversa."""

    id: str = Field(default_factory=novo_id)
    protocolo: str
    remetente: Remetente
    canal: Canal | None = None
    conteudo: str
    intencao: Intencao | None = None
    confianca: int | None = None
    autor: str | None = None
    criada_em: datetime = Field(default_factory=agora)
    metadados: dict = Field(default_factory=dict)


class SinalFriccao(BaseModel):
    """Sinal detectado em um turno. Valor de retorno do motor, sem persistência própria."""

    codigo: CodigoSinal
    peso: int
    descricao: str


class EventoFriccao(BaseModel):
    """Futuro: tabela `eventos_friccao` — append-only, sustenta a auditoria."""

    id: str = Field(default_factory=novo_id)
    protocolo: str
    codigo_sinal: CodigoSinal
    peso: int
    score_resultante: int
    descricao: str
    criado_em: datetime = Field(default_factory=agora)


class AvaliacaoFriccao(BaseModel):
    """Resultado auditável de um turno — nunca um número solto."""

    score_anterior: int
    score_atual: int
    delta: int
    nivel: NivelFriccao
    sinais: list[SinalFriccao] = Field(default_factory=list)
    deve_disparar_handoff: bool = False
    motivo_handoff: str | None = None


class Atendimento(BaseModel):
    """Futuro: tabela `atendimentos` (PK protocolo)."""

    protocolo: str
    cliente_id: str
    canal_origem: Canal
    canal_atual: Canal
    canais_utilizados: list[Canal] = Field(default_factory=list)
    status: StatusAtendimento = StatusAtendimento.BOT_ATIVO
    intencao: Intencao = Intencao.OUTROS
    confianca: int = 0
    score_friccao: int = 0
    score_inicial: int = 0
    historico_score: list[int] = Field(default_factory=list)
    total_mensagens: int = 0
    ultima_mensagem: str = ""
    aberto_em: datetime = Field(default_factory=agora)
    atualizado_em: datetime = Field(default_factory=agora)
    handoff_em: datetime | None = None
    handoff_motivo: str | None = None
    atendente: str | None = None

    # Como a identidade do cliente foi confirmada neste atendimento:
    # verificada_app · verificada_cpf · pendente · falhou · nao_verificada
    identidade: str = "nao_verificada"

    # Transferência entre setores
    setor: Setor | None = None
    transferencias: int = 0

    # Avaliação do cliente ao fim do atendimento (CSAT)
    nota: int | None = None
    comentario: str | None = None
    avaliado_em: datetime | None = None
    encerrado_em: datetime | None = None
    # O nível NÃO é derivado aqui de propósito: os limiares vivem em config e
    # `FriccaoService.nivel()` é a única fonte da verdade. Duplicar 70/40 nesta
    # entidade criaria dois lugares para calibrar — e um deles seria esquecido.


class ResultadoProcessamento(BaseModel):
    """Retorno do caso de uso principal — o que os endpoints de canal devolvem."""

    protocolo: str
    cliente: Cliente
    canal: Canal
    intencao: Intencao
    confianca: int
    termos_detectados: list[str] = Field(default_factory=list)
    avaliacao: AvaliacaoFriccao
    status: StatusAtendimento
    handoff_acionado: bool
    troca_de_canal: bool
    sessao_nova: bool
    resposta: str
    total_mensagens: int

    # Autoatendimento (Fase 4). `origem_resposta` diz quem respondeu o turno:
    # "autoatendimento", "bot" (resposta comum), "handoff" ou "fila_humana".
    origem_resposta: str = "bot"
    acoes: list["ResultadoAcao"] = Field(default_factory=list)
    etapa_fluxo: EtapaFluxo = EtapaFluxo.NENHUMA
    acao_pendente: AcaoAutoatendimento | None = None
    opcoes_resposta: list[dict] = Field(default_factory=list)
    gerado_por_ia: bool = False


# ======================================================================
# Autoatendimento — dados operacionais fictícios
#
# Futuro: tabelas PostgreSQL `faturas`, `equipamentos`, `planos` e
# `solicitacoes`. Valores monetários em centavos inteiros: dinheiro em float
# acumula erro de arredondamento.
# ======================================================================


class ItemFatura(BaseModel):
    descricao: str
    valor_centavos: int


class Fatura(BaseModel):
    """Fatura atual do cliente."""

    cliente_id: str
    referencia: str  # "09/2026"
    valor_centavos: int
    vencimento: date
    codigo_barras: str
    status: StatusFatura
    itens: list[ItemFatura] = Field(default_factory=list)


class Equipamento(BaseModel):
    """Equipamento de rede instalado na casa do cliente (roteador, modem)."""

    id: str
    cliente_id: str
    tipo: str
    modelo: str
    status_conexao: StatusConexao
    ultima_reinicializacao: datetime


class Plano(BaseModel):
    """Item do catálogo comercial — compartilhado entre clientes."""

    id: str
    nome: str
    categoria: CategoriaPlano
    preco_centavos: int
    franquia: str  # "40GB", "500 Mbps"
    linhas_incluidas: int


class Solicitacao(BaseModel):
    """Pedido formal gerado por uma ação: contestação, alteração, upgrade.

    Tem protocolo próprio, distinto do protocolo do atendimento, como um
    número de chamado que o cliente pode consultar depois.
    """

    protocolo: str
    cliente_id: str
    protocolo_atendimento: str
    tipo: TipoSolicitacao
    status: StatusSolicitacao
    descricao: str
    referencia_fatura: str | None = None
    criada_em: datetime = Field(default_factory=agora)


class ResultadoAcao(BaseModel):
    """O que o AutoatendimentoService devolve ao orquestrador.

    Estruturado de propósito: `dados` alimenta os cartões da interface na
    Fase 4 sem que o frontend precise extrair informação de texto.
    """

    acao: AcaoAutoatendimento | None
    status: StatusAcao
    codigo: str
    mensagem: str
    dados: dict = Field(default_factory=dict)
    solicitacao: Solicitacao | None = None
    requer_handoff: bool = False


class TurnoDialogo(BaseModel):
    """Resultado de um turno da conversa guiada.

    `tratado=False` significa que a mensagem não pertence a nenhum fluxo de
    autoatendimento: quem chamou segue com a resposta comum do bot.
    """

    tratado: bool
    resposta: str | None = None
    resultados: list[ResultadoAcao] = Field(default_factory=list)
    etapa: EtapaFluxo = EtapaFluxo.NENHUMA
    acao_pendente: AcaoAutoatendimento | None = None
    requer_handoff: bool = False
    # A IA participou do turno (interpretou a mensagem ou escreveu a resposta).
    ia: bool = False


# ResultadoProcessamento referencia ResultadoAcao, declarado depois dele.
ResultadoProcessamento.model_rebuild()
