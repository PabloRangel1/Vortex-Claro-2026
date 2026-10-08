"""Vocabulário fechado do domínio.

Usar StrEnum garante serialização JSON transparente (o valor é a string) e ao
mesmo tempo dá checagem estática nos services.
"""

from enum import StrEnum


class Canal(StrEnum):
    APP = "app"
    WHATSAPP = "whatsapp"

    @property
    def rotulo(self) -> str:
        return {"app": "App Claro", "whatsapp": "WhatsApp"}[self.value]


class Intencao(StrEnum):
    SUPORTE_TECNICO = "suporte_tecnico"
    FINANCEIRO = "financeiro"
    CONTESTACAO_FATURA = "contestacao_fatura"
    SEGUNDA_VIA = "segunda_via"
    PLANOS_UPGRADE = "planos_upgrade"
    CANCELAMENTO = "cancelamento"
    OUTROS = "outros"

    @property
    def rotulo(self) -> str:
        return {
            "suporte_tecnico": "Suporte Técnico",
            "financeiro": "Financeiro",
            "contestacao_fatura": "Contestação de Fatura",
            "segunda_via": "Segunda Via",
            "planos_upgrade": "Planos e Upgrade",
            "cancelamento": "Cancelamento",
            "outros": "Não Classificada",
        }[self.value]


class Remetente(StrEnum):
    CLIENTE = "cliente"
    BOT = "bot"
    ATENDENTE = "atendente"
    SISTEMA = "sistema"


class StatusAtendimento(StrEnum):
    BOT_ATIVO = "bot_ativo"
    AGUARDANDO_HANDOFF = "aguardando_handoff"
    EM_ATENDIMENTO_HUMANO = "em_atendimento_humano"
    ENCERRADO = "encerrado"


class Setor(StrEnum):
    """Destinos possíveis de uma transferência."""

    SUPORTE_TECNICO = "suporte_tecnico"
    FINANCEIRO = "financeiro"
    RETENCAO = "retencao"
    OUVIDORIA = "ouvidoria"

    @property
    def rotulo(self) -> str:
        return {
            "suporte_tecnico": "Suporte Técnico N2",
            "financeiro": "Financeiro",
            "retencao": "Retenção",
            "ouvidoria": "Ouvidoria",
        }[self.value]


class NivelFriccao(StrEnum):
    ESTAVEL = "estavel"
    ATENCAO = "atencao"
    CRITICO = "critico"


class CodigoSinal(StrEnum):
    """Cada sinal detectado vira uma linha de auditoria (futura tabela PostgreSQL)."""

    REPETICAO = "repeticao"
    INTENCAO_REPETIDA = "intencao_repetida"
    PEDIDO_HUMANO = "pedido_humano"
    TROCA_CANAL = "troca_canal"
    SENTIMENTO_NEGATIVO = "sentimento_negativo"
    CAIXA_ALTA = "caixa_alta"
    LOOP_SEM_RESOLUCAO = "loop_sem_resolucao"
    IMPACIENCIA = "impaciencia"
    DECAIMENTO = "decaimento"


# ======================================================================
# Autoatendimento — o que o sistema consegue executar sozinho
# ======================================================================


class AcaoAutoatendimento(StrEnum):
    """Catálogo FECHADO de ações. Nada fora desta lista é executado.

    É a fronteira que sustenta a regra de produto: a camada de linguagem pode
    sugerir, mas só o backend executa, e só o que estiver aqui.
    """

    GERAR_SEGUNDA_VIA = "gerar_segunda_via"
    ALTERAR_VENCIMENTO = "alterar_vencimento"
    DIAGNOSTICAR_CONEXAO = "diagnosticar_conexao"
    REINICIAR_EQUIPAMENTO = "reiniciar_equipamento"
    LISTAR_PLANOS = "listar_planos"
    CONFIRMAR_UPGRADE = "confirmar_upgrade"
    ABRIR_CONTESTACAO = "abrir_contestacao"
    ENCAMINHAR_HUMANO = "encaminhar_humano"
    # Só leitura: o cliente volta com um protocolo (ou pede o último atendimento).
    CONSULTAR_ATENDIMENTO = "consultar_atendimento"


class EtapaFluxo(StrEnum):
    """Em que ponto de uma conversa guiada o cliente está.

    Vive na sessão, que é única por cliente — por isso uma pergunta feita no
    App pode ser respondida no WhatsApp.
    """

    NENHUMA = "nenhuma"
    AGUARDANDO_PARAMETRO = "aguardando_parametro"      # ex.: qual dia de vencimento
    AGUARDANDO_CONFIRMACAO = "aguardando_confirmacao"  # ex.: confirma o dia 15?


class StatusAcao(StrEnum):
    SUCESSO = "sucesso"
    FALHA = "falha"
    # Validada e pronta, mas ainda não executada: nada foi alterado nem gravado.
    AGUARDANDO_CONFIRMACAO = "aguardando_confirmacao"


class StatusFatura(StrEnum):
    ABERTA = "aberta"
    PAGA = "paga"
    VENCIDA = "vencida"


class StatusConexao(StrEnum):
    ONLINE = "online"
    INSTAVEL = "instavel"
    OFFLINE = "offline"


class CategoriaPlano(StrEnum):
    MOVEL = "movel"
    FIBRA = "fibra"


class TipoSolicitacao(StrEnum):
    CONTESTACAO = "contestacao"
    ALTERACAO_VENCIMENTO = "alteracao_vencimento"
    UPGRADE_PLANO = "upgrade_plano"
    REINICIO_EQUIPAMENTO = "reinicio_equipamento"


class StatusSolicitacao(StrEnum):
    EM_ANALISE = "em_analise"
    CONCLUIDA = "concluida"


class Segmento(StrEnum):
    """Tipo de cliente, pelo produto que ele tem. Filtra a fila e o histórico."""

    POS = "pos"
    CONTROLE = "controle"
    FIBRA = "fibra"

    @property
    def rotulo(self) -> str:
        return {"pos": "Pós-pago", "controle": "Controle", "fibra": "Fibra"}[self.value]


def segmento_do_plano(plano_id: str | None) -> Segmento:
    if plano_id and plano_id.startswith("fibra"):
        return Segmento.FIBRA
    if plano_id and "controle" in plano_id:
        return Segmento.CONTROLE
    return Segmento.POS
