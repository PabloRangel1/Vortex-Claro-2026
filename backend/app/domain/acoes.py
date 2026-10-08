"""Catálogo fechado de ações de autoatendimento.

Cada ação declara, num só lugar:
  - parâmetros obrigatórios;
  - se exige confirmação explícita do cliente antes de executar;
  - se gera uma solicitação formal (e com qual tipo);
  - o texto legível de cada resultado possível, de sucesso ou de falha.

Os textos moram AQUI, e não no `AutoatendimentoService`, de propósito: o
serviço decide o que aconteceu e devolve um código; este módulo decide como
isso é dito ao cliente. Trocar a redação nunca exige mexer em regra de negócio.
"""

import re
from dataclasses import dataclass, field

from app.domain.enums import AcaoAutoatendimento, TipoSolicitacao

# ----------------------------------------------------------------- formatação

_DATA_ISO = re.compile(r"^(\d{4})-(\d{2})-(\d{2})(?:T(\d{2}):(\d{2}))?")


def formatar_moeda(centavos: int) -> str:
    """12990 -> 'R$ 129,90'."""
    inteiro = f"{centavos / 100:,.2f}"
    return "R$ " + inteiro.replace(",", "·").replace(".", ",").replace("·", ".")


def _formatar_valor(chave: str, valor):
    if valor is None:
        return ""
    if chave.endswith("_centavos") and isinstance(valor, int):
        return formatar_moeda(valor)
    if isinstance(valor, str) and (m := _DATA_ISO.match(valor)):
        ano, mes, dia, hora, minuto = m.groups()
        data = f"{dia}/{mes}/{ano}"
        return f"{data} às {hora}:{minuto}" if hora else data
    if isinstance(valor, list):
        return ", ".join(str(v) for v in valor)
    return valor


class _Contexto(dict):
    """Placeholder ausente vira vazio em vez de derrubar o atendimento."""

    def __missing__(self, chave):
        return ""


def _contexto(dados: dict) -> _Contexto:
    ctx = _Contexto()
    for chave, valor in dados.items():
        ctx[chave] = _formatar_valor(chave, valor)
        # `valor_centavos` também fica disponível como `valor`, já formatado.
        if chave.endswith("_centavos"):
            ctx[chave.removesuffix("_centavos")] = _formatar_valor(chave, valor)
    return ctx


# ------------------------------------------------------------------ definição


@dataclass(frozen=True)
class DefinicaoAcao:
    acao: AcaoAutoatendimento
    descricao: str
    parametros_obrigatorios: tuple[str, ...] = ()
    exige_confirmacao: bool = False
    tipo_solicitacao: TipoSolicitacao | None = None
    descricao_solicitacao: str | None = None
    mensagens: dict[str, str] = field(default_factory=dict)

    def renderizar(self, codigo: str, dados: dict) -> str:
        template = self.mensagens.get(codigo) or MENSAGENS_GERAIS.get(codigo, codigo)
        return template.format_map(_contexto(dados))

    def renderizar_solicitacao(self, dados: dict) -> str:
        return (self.descricao_solicitacao or self.descricao).format_map(_contexto(dados))


# Falhas que não pertencem a uma ação específica.
MENSAGENS_GERAIS: dict[str, str] = {
    "acao_desconhecida": "Esta solicitação não está disponível no autoatendimento.",
    "parametro_ausente": "Faltam informações para concluir: {parametros_faltantes}.",
    "cliente_nao_encontrado": "Não conseguimos localizar a sua conta.",
    "sem_fatura": "Não encontramos fatura para a sua conta.",
    "sem_equipamento": "Não encontramos equipamento de internet vinculado à sua conta.",
    "plano_atual_desconhecido": "Não conseguimos identificar o seu plano atual.",
}


# ------------------------------------------------------------------- catálogo

CATALOGO: dict[AcaoAutoatendimento, DefinicaoAcao] = {
    AcaoAutoatendimento.GERAR_SEGUNDA_VIA: DefinicaoAcao(
        acao=AcaoAutoatendimento.GERAR_SEGUNDA_VIA,
        descricao="Gerar segunda via da fatura",
        mensagens={
            "segunda_via_gerada": (
                "Segunda via da fatura de {referencia} gerada. Valor {valor}, "
                "vencimento em {vencimento}. Código de barras: {codigo_barras}"
            ),
            "segunda_via_vencida": (
                "A fatura de {referencia} venceu em {vencimento}. Segue a segunda via: "
                "valor {valor}. Código de barras: {codigo_barras}. Pagamentos depois do "
                "vencimento podem ter multa e juros na próxima fatura."
            ),
            "fatura_ja_paga": (
                "A fatura de {referencia} já está paga, então não há segunda via "
                "a emitir."
            ),
        },
    ),
    AcaoAutoatendimento.ALTERAR_VENCIMENTO: DefinicaoAcao(
        acao=AcaoAutoatendimento.ALTERAR_VENCIMENTO,
        descricao="Alterar dia de vencimento",
        parametros_obrigatorios=("dia",),
        exige_confirmacao=True,
        tipo_solicitacao=TipoSolicitacao.ALTERACAO_VENCIMENTO,
        descricao_solicitacao="Vencimento alterado do dia {dia_atual} para o dia {dia_novo}",
        mensagens={
            "confirmar_vencimento": (
                "Confirma a alteração do vencimento do dia {dia_atual} para o dia "
                "{dia_novo}? A mudança vale a partir da próxima fatura."
            ),
            "vencimento_alterado": (
                "Vencimento alterado para o dia {dia_novo}, a partir da próxima "
                "fatura. Protocolo {protocolo_solicitacao}."
            ),
            "dia_invalido": "Informe o dia desejado como um número, por exemplo 15.",
            # {opcoes} e não {dias_permitidos}: oferecer o dia atual como
            # alternativa levaria direto à falha "dia_igual_atual".
            "dia_nao_permitido": (
                "O dia {dia_novo} não está disponível. Você pode escolher entre os "
                "dias {opcoes}."
            ),
            "dia_igual_atual": "O seu vencimento já é no dia {dia_novo}.",
        },
    ),
    AcaoAutoatendimento.DIAGNOSTICAR_CONEXAO: DefinicaoAcao(
        acao=AcaoAutoatendimento.DIAGNOSTICAR_CONEXAO,
        descricao="Diagnosticar conexão de internet",
        mensagens={
            "diagnostico_online": (
                "Diagnóstico concluído: o seu {tipo} {modelo} está online e "
                "funcionando normalmente."
            ),
            "diagnostico_instavel": (
                "Diagnóstico concluído: identificamos instabilidade no seu {tipo} "
                "{modelo}, com latência de {latencia_ms} ms e {perda_pacotes_pct}% de "
                "perda de pacotes. Uma reinicialização remota costuma resolver."
            ),
            "diagnostico_offline": (
                "Diagnóstico concluído: o seu {tipo} {modelo} está sem comunicação "
                "com a rede. Será necessário apoio técnico."
            ),
        },
    ),
    AcaoAutoatendimento.REINICIAR_EQUIPAMENTO: DefinicaoAcao(
        acao=AcaoAutoatendimento.REINICIAR_EQUIPAMENTO,
        descricao="Reiniciar equipamento remotamente",
        exige_confirmacao=True,
        tipo_solicitacao=TipoSolicitacao.REINICIO_EQUIPAMENTO,
        descricao_solicitacao="Reinicialização remota do {tipo} {equipamento_id}",
        mensagens={
            "confirmar_reinicio": (
                "Confirma a reinicialização remota do seu {tipo} {modelo}? A "
                "conexão fica indisponível por cerca de 2 minutos."
            ),
            "equipamento_reiniciado": (
                "Reinicialização concluída. O seu {tipo} está online novamente. "
                "Protocolo {protocolo_solicitacao}."
            ),
            "equipamento_sem_comunicacao": (
                "Não foi possível reiniciar: o equipamento está sem comunicação com "
                "a rede. Vamos encaminhar você ao suporte técnico."
            ),
        },
    ),
    AcaoAutoatendimento.LISTAR_PLANOS: DefinicaoAcao(
        acao=AcaoAutoatendimento.LISTAR_PLANOS,
        descricao="Listar opções de upgrade de plano",
        mensagens={
            "planos_disponiveis": (
                "Encontramos {quantidade} opções de upgrade para o seu plano "
                "atual, {plano_atual_nome}."
            ),
            "plano_disponivel": (
                "Encontramos uma opção de upgrade para o seu plano atual, "
                "{plano_atual_nome}."
            ),
            "sem_upgrade_disponivel": (
                "O {plano_atual_nome} já é o plano mais completo da categoria."
            ),
        },
    ),
    AcaoAutoatendimento.CONFIRMAR_UPGRADE: DefinicaoAcao(
        acao=AcaoAutoatendimento.CONFIRMAR_UPGRADE,
        descricao="Confirmar upgrade de plano",
        parametros_obrigatorios=("plano_id",),
        exige_confirmacao=True,
        tipo_solicitacao=TipoSolicitacao.UPGRADE_PLANO,
        descricao_solicitacao="Upgrade de {plano_atual_nome} para {plano_novo_nome}",
        mensagens={
            "confirmar_upgrade": (
                "Confirma a mudança de {plano_atual_nome} para {plano_novo_nome}, "
                "por {preco_novo} ao mês?"
            ),
            "plano_atualizado": (
                "Plano atualizado para {plano_novo_nome}. Protocolo "
                "{protocolo_solicitacao}."
            ),
            "plano_inexistente": "Não encontramos o plano informado.",
            "mesmo_plano": "Você já está no plano {plano_atual_nome}.",
            "categoria_diferente": (
                "O {plano_novo_nome} é de outra categoria e não pode substituir o "
                "{plano_atual_nome}."
            ),
            "nao_e_upgrade": (
                "O {plano_novo_nome} não é um upgrade do seu plano atual, "
                "{plano_atual_nome}."
            ),
        },
    ),
    AcaoAutoatendimento.ABRIR_CONTESTACAO: DefinicaoAcao(
        acao=AcaoAutoatendimento.ABRIR_CONTESTACAO,
        descricao="Abrir contestação de cobrança",
        parametros_obrigatorios=("descricao",),
        exige_confirmacao=True,
        tipo_solicitacao=TipoSolicitacao.CONTESTACAO,
        descricao_solicitacao="Contestação da fatura {referencia}: {descricao}",
        mensagens={
            # Cita o motivo, não o total: o cliente costuma contestar um item, e
            # "no valor de R$ 189,90" sugeriria que contesta a fatura inteira.
            "confirmar_contestacao": (
                "Confirma a abertura de contestação na fatura de {referencia}? "
                "Motivo informado: {descricao}."
            ),
            "contestacao_aberta": (
                "Contestação aberta com o protocolo {protocolo_solicitacao}. Status: "
                "em análise. O retorno acontece em até 5 dias úteis."
            ),
            "contestacao_em_andamento": (
                "Já existe uma contestação em análise para a fatura de "
                "{referencia}, com o protocolo {protocolo_solicitacao}."
            ),
        },
    ),
    AcaoAutoatendimento.CONSULTAR_ATENDIMENTO: DefinicaoAcao(
        acao=AcaoAutoatendimento.CONSULTAR_ATENDIMENTO,
        descricao="Consultar protocolo ou último atendimento",
        mensagens={
            "ultimo_atendimento": (
                "Seu último atendimento foi o protocolo {protocolo_consultado}, aberto em "
                "{aberto_em} pelo {canal}, sobre {assunto}. Situação: {situacao}."
                "{texto_solicitacoes}"
            ),
            "atendimento_encontrado": (
                "O protocolo {protocolo_consultado} foi aberto em {aberto_em} pelo {canal}, "
                "sobre {assunto}. Situação: {situacao}.{texto_solicitacoes}"
            ),
            "solicitacao_encontrada": (
                "A solicitação {protocolo_consultado} ({tipo}) foi registrada em {aberto_em}, "
                "no atendimento {protocolo_atendimento}. Situação: {situacao}."
            ),
            "protocolo_nao_encontrado": (
                "Não encontrei o protocolo {protocolo_consultado} na sua conta. Confira os "
                "números — o formato é AAAA-MMDD-NNNNN, ou SOL-AAAAMMDD-NNNN para solicitações."
            ),
            "sem_atendimento_anterior": (
                "Não encontrei atendimentos anteriores na sua conta. O protocolo deste "
                "atendimento é {protocolo_atual}."
            ),
        },
    ),
    AcaoAutoatendimento.ENCAMINHAR_HUMANO: DefinicaoAcao(
        acao=AcaoAutoatendimento.ENCAMINHAR_HUMANO,
        descricao="Encaminhar para atendimento humano",
        mensagens={
            "encaminhado_humano": (
                "Vamos transferir você para um especialista, que receberá todo o "
                "histórico deste atendimento."
            ),
        },
    ),
}


# Ações cujo sucesso ENTREGA o que o cliente pediu. Diagnóstico e listagem de
# planos são passos do caminho, não o fim dele. O orquestrador usa isto para
# zerar a contagem de "turnos sem resolução" da fricção.
RESOLVEM_A_DEMANDA = frozenset({
    AcaoAutoatendimento.GERAR_SEGUNDA_VIA,
    AcaoAutoatendimento.ALTERAR_VENCIMENTO,
    AcaoAutoatendimento.REINICIAR_EQUIPAMENTO,
    AcaoAutoatendimento.CONFIRMAR_UPGRADE,
    AcaoAutoatendimento.ABRIR_CONTESTACAO,
})
