"""Execução controlada de ações de autoatendimento.

Regra de produto: a camada de linguagem conversa e interpreta; o backend
executa ações PERMITIDAS. Este serviço é essa fronteira.

Pipeline de toda execução, sempre nesta ordem:
  1. a ação existe no catálogo fechado
  2. os parâmetros obrigatórios estão presentes
  3. a regra de negócio permite (dados carregados e validados)
  4. se exige confirmação e ainda não houve, devolve a prévia SEM alterar nada
  5. executa a mutação e cria a solicitação, quando a ação gera uma
  6. registra o evento no histórico do atendimento
  7. devolve um `ResultadoAcao` estruturado

Validar ANTES de pedir confirmação é deliberado: o cliente nunca é convidado a
confirmar algo que seria recusado em seguida.

Fora deste serviço, por decisão: regras HTTP, texto de interface (vive em
`domain/acoes.py`) e qualquer chamada de IA.
"""

from datetime import date, datetime, timedelta, timezone

from app.config import Settings
from app.core.protocolo import gerar_protocolo_solicitacao
from app.domain.acoes import CATALOGO, MENSAGENS_GERAIS, DefinicaoAcao
from app.domain.enums import (
    AcaoAutoatendimento,
    Remetente,
    StatusAcao,
    StatusConexao,
    StatusFatura,
    StatusSolicitacao,
    TipoSolicitacao,
)
from app.domain.models import (
    Cliente,
    Equipamento,
    Fatura,
    Mensagem,
    Plano,
    ResultadoAcao,
    Solicitacao,
    agora,
)
from app.repositories.base import (
    AtendimentoRepository,
    ClienteRepository,
    ConversaRepository,
    OperacaoRepository,
)

# Datas mostradas ao cliente no horário de Brasília (sem horário de verão desde 2019).
_BRASILIA = timezone(timedelta(hours=-3))

# Como o CLIENTE lê a situação de um atendimento ou solicitação.
_SITUACAO_ATENDIMENTO = {
    "bot_ativo": "em andamento",
    "aguardando_handoff": "aguardando um especialista",
    "em_atendimento_humano": "em atendimento com um especialista",
    "encerrado": "encerrado",
}
_TIPO_SOLICITACAO = {
    "contestacao": "contestação",
    "alteracao_vencimento": "alteração de vencimento",
    "upgrade_plano": "upgrade de plano",
    "reinicio_equipamento": "reinício do equipamento",
}
_SITUACAO_SOLICITACAO = {"em_analise": "em análise", "concluida": "concluída"}

# Leituras simuladas do diagnóstico remoto. Determinísticas de propósito: numa
# apresentação o resultado precisa ser o mesmo toda vez.
_LEITURAS_DIAGNOSTICO = {
    StatusConexao.ONLINE: {"sinal_dbm": -48, "latencia_ms": 12, "perda_pacotes_pct": 0},
    StatusConexao.INSTAVEL: {"sinal_dbm": -71, "latencia_ms": 186, "perda_pacotes_pct": 9},
    StatusConexao.OFFLINE: {"sinal_dbm": None, "latencia_ms": None, "perda_pacotes_pct": 100},
}


def _json(valor):
    """`dados` precisa ser serializável: vai para o histórico e, depois, para a API."""
    if isinstance(valor, (date, datetime)):
        return valor.isoformat()
    return valor


def _dados_fatura(fatura: Fatura) -> dict:
    return {
        "referencia": fatura.referencia,
        "valor_centavos": fatura.valor_centavos,
        "vencimento": _json(fatura.vencimento),
        "codigo_barras": fatura.codigo_barras,
        "status_fatura": str(fatura.status),
        "itens": [
            {"descricao": i.descricao, "valor_centavos": i.valor_centavos}
            for i in fatura.itens
        ],
    }


def _dados_equipamento(eq: Equipamento) -> dict:
    return {
        "equipamento_id": eq.id,
        "tipo": eq.tipo,
        "modelo": eq.modelo,
        "status_conexao": str(eq.status_conexao),
        "ultima_reinicializacao": _json(eq.ultima_reinicializacao),
    }


def _dados_plano(plano: Plano) -> dict:
    return {
        "id": plano.id,
        "nome": plano.nome,
        "categoria": str(plano.categoria),
        "preco_centavos": plano.preco_centavos,
        "franquia": plano.franquia,
        "linhas_incluidas": plano.linhas_incluidas,
    }


class AutoatendimentoService:
    def __init__(
        self,
        *,
        clientes: ClienteRepository,
        operacao: OperacaoRepository,
        conversas: ConversaRepository,
        settings: Settings,
        atendimentos: AtendimentoRepository | None = None,
    ) -> None:
        self._clientes = clientes
        self._operacao = operacao
        self._conversas = conversas
        self._atendimentos = atendimentos
        self._s = settings

        self._executores = {
            AcaoAutoatendimento.GERAR_SEGUNDA_VIA: self._segunda_via,
            AcaoAutoatendimento.ALTERAR_VENCIMENTO: self._alterar_vencimento,
            AcaoAutoatendimento.DIAGNOSTICAR_CONEXAO: self._diagnosticar,
            AcaoAutoatendimento.REINICIAR_EQUIPAMENTO: self._reiniciar,
            AcaoAutoatendimento.LISTAR_PLANOS: self._listar_planos,
            AcaoAutoatendimento.CONFIRMAR_UPGRADE: self._confirmar_upgrade,
            AcaoAutoatendimento.ABRIR_CONTESTACAO: self._abrir_contestacao,
            AcaoAutoatendimento.ENCAMINHAR_HUMANO: self._encaminhar_humano,
            AcaoAutoatendimento.CONSULTAR_ATENDIMENTO: self._consultar_atendimento,
        }

    # ================================================================ público

    def definicao(self, acao: AcaoAutoatendimento) -> DefinicaoAcao:
        return CATALOGO[acao]

    async def opcoes_vencimento(self, cliente_id: str) -> list[int]:
        """Dias que o cliente pode escolher — a regra fica aqui, não na conversa."""
        cliente = await self._clientes.obter(cliente_id)
        atual = cliente.dia_vencimento if cliente else None
        return [d for d in self._s.dias_vencimento_permitidos if d != atual]

    async def executar(
        self,
        *,
        protocolo: str,
        cliente_id: str,
        acao: AcaoAutoatendimento | str,
        parametros: dict | None = None,
        confirmado: bool = False,
    ) -> ResultadoAcao:
        parametros = parametros or {}

        # 1. Catálogo fechado
        try:
            acao = AcaoAutoatendimento(acao)
        except ValueError:
            return await self._falha_geral(
                protocolo, None, "acao_desconhecida", {"acao_solicitada": str(acao)}
            )
        definicao = CATALOGO[acao]

        # 2. Parâmetros obrigatórios
        faltantes = [
            p for p in definicao.parametros_obrigatorios if parametros.get(p) in (None, "")
        ]
        if faltantes:
            return await self._finalizar(
                protocolo, definicao, StatusAcao.FALHA, "parametro_ausente",
                {"parametros_faltantes": faltantes},
            )

        cliente = await self._clientes.obter(cliente_id)
        if cliente is None:
            return await self._finalizar(
                protocolo, definicao, StatusAcao.FALHA, "cliente_nao_encontrado", {}
            )

        # 3 a 7. Regra de negócio, confirmação, execução e registro
        return await self._executores[acao](
            protocolo, definicao, cliente, parametros, confirmado
        )

    # ============================================================= executores

    async def _segunda_via(self, protocolo, definicao, cliente, parametros, confirmado):
        fatura = await self._operacao.obter_fatura_atual(cliente.cliente_id)
        if fatura is None:
            return await self._finalizar(protocolo, definicao, StatusAcao.FALHA, "sem_fatura", {})

        dados = _dados_fatura(fatura)
        if fatura.status == StatusFatura.PAGA:
            return await self._finalizar(
                protocolo, definicao, StatusAcao.FALHA, "fatura_ja_paga", dados
            )
        # Aberta com o vencimento já passado: está vencida, e o cliente precisa saber.
        hoje = agora().astimezone(_BRASILIA).date()
        if fatura.status == StatusFatura.VENCIDA or fatura.vencimento < hoje:
            dados["vencida"] = True
            return await self._finalizar(
                protocolo, definicao, StatusAcao.SUCESSO, "segunda_via_vencida", dados
            )
        return await self._finalizar(
            protocolo, definicao, StatusAcao.SUCESSO, "segunda_via_gerada", dados
        )

    async def _alterar_vencimento(self, protocolo, definicao, cliente, parametros, confirmado):
        try:
            dia = int(parametros["dia"])
        except (TypeError, ValueError):
            return await self._finalizar(
                protocolo, definicao, StatusAcao.FALHA, "dia_invalido",
                {"valor_recebido": str(parametros.get("dia"))},
            )

        permitidos = list(self._s.dias_vencimento_permitidos)
        dados = {
            "dia_atual": cliente.dia_vencimento,
            "dia_novo": dia,
            "dias_permitidos": permitidos,
            # Já oferecido como lista de opções, pronta para virar botões na Fase 4.
            "opcoes": [d for d in permitidos if d != cliente.dia_vencimento],
        }

        if dia not in permitidos:
            return await self._finalizar(
                protocolo, definicao, StatusAcao.FALHA, "dia_nao_permitido", dados
            )
        if dia == cliente.dia_vencimento:
            return await self._finalizar(
                protocolo, definicao, StatusAcao.FALHA, "dia_igual_atual", dados
            )
        if not confirmado:
            return self._pendente(definicao, "confirmar_vencimento", dados)

        cliente.dia_vencimento = dia
        await self._clientes.salvar(cliente)

        solicitacao = await self._nova_solicitacao(
            definicao, protocolo, cliente, StatusSolicitacao.CONCLUIDA, dados
        )
        return await self._finalizar(
            protocolo, definicao, StatusAcao.SUCESSO, "vencimento_alterado", dados,
            solicitacao=solicitacao,
        )

    async def _diagnosticar(self, protocolo, definicao, cliente, parametros, confirmado):
        eq = await self._operacao.obter_equipamento(cliente.cliente_id)
        if eq is None:
            return await self._finalizar(
                protocolo, definicao, StatusAcao.FALHA, "sem_equipamento", {}
            )

        dados = {**_dados_equipamento(eq), **_LEITURAS_DIAGNOSTICO[eq.status_conexao]}
        # O diagnóstico em si deu certo; equipamento offline só não se resolve sozinho.
        return await self._finalizar(
            protocolo, definicao, StatusAcao.SUCESSO, f"diagnostico_{eq.status_conexao}",
            dados, requer_handoff=eq.status_conexao == StatusConexao.OFFLINE,
        )

    async def _reiniciar(self, protocolo, definicao, cliente, parametros, confirmado):
        eq = await self._operacao.obter_equipamento(cliente.cliente_id)
        if eq is None:
            return await self._finalizar(
                protocolo, definicao, StatusAcao.FALHA, "sem_equipamento", {}
            )

        dados = _dados_equipamento(eq)
        if eq.status_conexao == StatusConexao.OFFLINE:
            return await self._finalizar(
                protocolo, definicao, StatusAcao.FALHA, "equipamento_sem_comunicacao",
                dados, requer_handoff=True,
            )
        if not confirmado:
            return self._pendente(definicao, "confirmar_reinicio", dados)

        eq.status_conexao = StatusConexao.ONLINE
        eq.ultima_reinicializacao = agora()
        await self._operacao.salvar_equipamento(eq)

        dados = _dados_equipamento(eq)
        solicitacao = await self._nova_solicitacao(
            definicao, protocolo, cliente, StatusSolicitacao.CONCLUIDA, dados
        )
        return await self._finalizar(
            protocolo, definicao, StatusAcao.SUCESSO, "equipamento_reiniciado", dados,
            solicitacao=solicitacao,
        )

    async def _listar_planos(self, protocolo, definicao, cliente, parametros, confirmado):
        atual = await self._plano_atual(cliente)
        if atual is None:
            return await self._finalizar(
                protocolo, definicao, StatusAcao.FALHA, "plano_atual_desconhecido", {}
            )

        upgrades = sorted(
            (
                p for p in await self._operacao.listar_planos()
                if p.categoria == atual.categoria and p.preco_centavos > atual.preco_centavos
            ),
            key=lambda p: p.preco_centavos,
        )
        dados = {
            "plano_atual_nome": atual.nome,
            "plano_atual": _dados_plano(atual),
            "opcoes": [_dados_plano(p) for p in upgrades],
            "quantidade": len(upgrades),
        }
        codigo = {0: "sem_upgrade_disponivel", 1: "plano_disponivel"}.get(
            len(upgrades), "planos_disponiveis"
        )
        return await self._finalizar(protocolo, definicao, StatusAcao.SUCESSO, codigo, dados)

    async def _confirmar_upgrade(self, protocolo, definicao, cliente, parametros, confirmado):
        atual = await self._plano_atual(cliente)
        if atual is None:
            return await self._finalizar(
                protocolo, definicao, StatusAcao.FALHA, "plano_atual_desconhecido", {}
            )

        novo = await self._operacao.obter_plano(str(parametros["plano_id"]))
        if novo is None:
            return await self._finalizar(
                protocolo, definicao, StatusAcao.FALHA, "plano_inexistente",
                {"plano_id": str(parametros["plano_id"])},
            )

        dados = {
            "plano_atual_nome": atual.nome,
            "plano_novo_nome": novo.nome,
            "preco_novo_centavos": novo.preco_centavos,
            "plano_atual": _dados_plano(atual),
            "plano_novo": _dados_plano(novo),
        }

        if novo.id == atual.id:
            return await self._finalizar(
                protocolo, definicao, StatusAcao.FALHA, "mesmo_plano", dados
            )
        if novo.categoria != atual.categoria:
            return await self._finalizar(
                protocolo, definicao, StatusAcao.FALHA, "categoria_diferente", dados
            )
        if novo.preco_centavos <= atual.preco_centavos:
            return await self._finalizar(
                protocolo, definicao, StatusAcao.FALHA, "nao_e_upgrade", dados
            )
        if not confirmado:
            return self._pendente(definicao, "confirmar_upgrade", dados)

        cliente.plano_id = novo.id
        cliente.plano = novo.nome
        await self._clientes.salvar(cliente)

        solicitacao = await self._nova_solicitacao(
            definicao, protocolo, cliente, StatusSolicitacao.CONCLUIDA, dados
        )
        return await self._finalizar(
            protocolo, definicao, StatusAcao.SUCESSO, "plano_atualizado", dados,
            solicitacao=solicitacao,
        )

    async def _abrir_contestacao(self, protocolo, definicao, cliente, parametros, confirmado):
        fatura = await self._operacao.obter_fatura_atual(cliente.cliente_id)
        if fatura is None:
            return await self._finalizar(protocolo, definicao, StatusAcao.FALHA, "sem_fatura", {})

        dados = {**_dados_fatura(fatura), "descricao": str(parametros["descricao"]).strip()}

        # Uma contestação por fatura: abrir outra só geraria protocolo duplicado.
        em_andamento = next(
            (
                s for s in await self._operacao.listar_solicitacoes(cliente.cliente_id)
                if s.tipo == TipoSolicitacao.CONTESTACAO
                and s.status == StatusSolicitacao.EM_ANALISE
                and s.referencia_fatura == fatura.referencia
            ),
            None,
        )
        if em_andamento:
            return await self._finalizar(
                protocolo, definicao, StatusAcao.FALHA, "contestacao_em_andamento",
                {**dados, "protocolo_solicitacao": em_andamento.protocolo},
                solicitacao=em_andamento,
            )
        if not confirmado:
            return self._pendente(definicao, "confirmar_contestacao", dados)

        solicitacao = await self._nova_solicitacao(
            definicao, protocolo, cliente, StatusSolicitacao.EM_ANALISE, dados,
            referencia_fatura=fatura.referencia,
        )
        return await self._finalizar(
            protocolo, definicao, StatusAcao.SUCESSO, "contestacao_aberta", dados,
            solicitacao=solicitacao,
        )

    async def _consultar_atendimento(self, protocolo, definicao, cliente, parametros, confirmado):
        """Só leitura. O cliente só enxerga protocolos DA CONTA DELE: um número de
        outra pessoa recebe a mesma resposta de "não encontrado"."""
        alvo = parametros.get("protocolo")
        solicitacoes = await self._operacao.listar_solicitacoes(cliente.cliente_id)

        if alvo and alvo.startswith("SOL-"):
            sol = next((s for s in solicitacoes if s.protocolo == alvo), None)
            if sol is None:
                return await self._finalizar(
                    protocolo, definicao, StatusAcao.FALHA, "protocolo_nao_encontrado",
                    {"protocolo_consultado": alvo},
                )
            return await self._finalizar(
                protocolo, definicao, StatusAcao.SUCESSO, "solicitacao_encontrada", {
                    "protocolo_consultado": sol.protocolo,
                    "protocolo_atendimento": sol.protocolo_atendimento,
                    "tipo": _TIPO_SOLICITACAO.get(str(sol.tipo), str(sol.tipo)),
                    "aberto_em": _json(sol.criada_em.astimezone(_BRASILIA)),
                    "situacao": _SITUACAO_SOLICITACAO.get(str(sol.status), str(sol.status)),
                },
            )

        historico = await self._atendimentos.listar_do_cliente(cliente.cliente_id)
        if alvo:
            atendimento = next((a for a in historico if a.protocolo == alvo), None)
            codigo = "atendimento_encontrado"
        else:
            # O atual não conta como "último": o cliente quer o anterior.
            atendimento = next((a for a in historico if a.protocolo != protocolo), None)
            codigo = "ultimo_atendimento"
        if atendimento is None:
            return await self._finalizar(
                protocolo, definicao, StatusAcao.FALHA,
                "protocolo_nao_encontrado" if alvo else "sem_atendimento_anterior",
                {"protocolo_consultado": alvo, "protocolo_atual": protocolo},
            )

        vinculadas = [s for s in solicitacoes if s.protocolo_atendimento == atendimento.protocolo]
        texto_solicitacoes = "".join(
            f" Solicitação {s.protocolo} ({_TIPO_SOLICITACAO.get(str(s.tipo), str(s.tipo))}): "
            f"{_SITUACAO_SOLICITACAO.get(str(s.status), str(s.status))}."
            for s in vinculadas
        )
        return await self._finalizar(protocolo, definicao, StatusAcao.SUCESSO, codigo, {
            "protocolo_consultado": atendimento.protocolo,
            "aberto_em": _json(atendimento.aberto_em.astimezone(_BRASILIA)),
            "canal": atendimento.canal_origem.rotulo,
            "assunto": atendimento.intencao.rotulo,
            "situacao": _SITUACAO_ATENDIMENTO.get(str(atendimento.status), str(atendimento.status)),
            "solicitacoes": [s.protocolo for s in vinculadas],
            "texto_solicitacoes": texto_solicitacoes,
        })

    async def _encaminhar_humano(self, protocolo, definicao, cliente, parametros, confirmado):
        # Só sinaliza. Mudar o status do atendimento é decisão do orquestrador.
        return await self._finalizar(
            protocolo, definicao, StatusAcao.SUCESSO, "encaminhado_humano",
            {"motivo": parametros.get("motivo")}, requer_handoff=True,
        )

    # ================================================================ apoio

    async def _plano_atual(self, cliente: Cliente) -> Plano | None:
        if not cliente.plano_id:
            return None
        return await self._operacao.obter_plano(cliente.plano_id)

    async def _nova_solicitacao(
        self, definicao, protocolo, cliente, status, dados, *, referencia_fatura=None
    ) -> Solicitacao:
        solicitacao = Solicitacao(
            protocolo=gerar_protocolo_solicitacao(),
            cliente_id=cliente.cliente_id,
            protocolo_atendimento=protocolo,
            tipo=definicao.tipo_solicitacao,
            status=status,
            descricao=definicao.renderizar_solicitacao(dados),
            referencia_fatura=referencia_fatura,
        )
        await self._operacao.criar_solicitacao(solicitacao)
        # Disponível para o texto final ("Protocolo SOL-...").
        dados["protocolo_solicitacao"] = solicitacao.protocolo
        return solicitacao

    def _pendente(self, definicao: DefinicaoAcao, codigo: str, dados: dict) -> ResultadoAcao:
        """Prévia de uma ação válida. Não altera nada e NÃO registra no histórico:
        nada aconteceu ainda. Guardar o estado pendente é papel da sessão (Fase 2)."""
        return ResultadoAcao(
            acao=definicao.acao,
            status=StatusAcao.AGUARDANDO_CONFIRMACAO,
            codigo=codigo,
            mensagem=definicao.renderizar(codigo, dados),
            dados=dados,
        )

    async def _finalizar(
        self,
        protocolo: str,
        definicao: DefinicaoAcao,
        status: StatusAcao,
        codigo: str,
        dados: dict,
        *,
        solicitacao: Solicitacao | None = None,
        requer_handoff: bool = False,
    ) -> ResultadoAcao:
        resultado = ResultadoAcao(
            acao=definicao.acao,
            status=status,
            codigo=codigo,
            mensagem=definicao.renderizar(codigo, dados),
            dados=dados,
            solicitacao=solicitacao,
            requer_handoff=requer_handoff,
        )
        await self._registrar(protocolo, resultado)
        return resultado

    async def _falha_geral(self, protocolo, acao, codigo, dados) -> ResultadoAcao:
        """Falha anterior ao catálogo — não há definição de ação para renderizar."""
        resultado = ResultadoAcao(
            acao=acao,
            status=StatusAcao.FALHA,
            codigo=codigo,
            mensagem=MENSAGENS_GERAIS[codigo].format_map({**dados}),
            dados=dados,
        )
        await self._registrar(protocolo, resultado)
        return resultado

    async def _registrar(self, protocolo: str, resultado: ResultadoAcao) -> None:
        """Mesmo padrão dos demais eventos do atendimento (troca de canal, handoff,
        transferência): mensagem de sistema com `metadados.tipo`. Assim a ação
        aparece no histórico e o painel consegue filtrar o que o bot já tentou."""
        await self._conversas.adicionar_mensagem(
            Mensagem(
                protocolo=protocolo,
                remetente=Remetente.SISTEMA,
                conteudo=resultado.mensagem,
                metadados={
                    "tipo": "acao",
                    "acao": str(resultado.acao) if resultado.acao else None,
                    "status": str(resultado.status),
                    "codigo": resultado.codigo,
                    "dados": resultado.dados,
                    "solicitacao": resultado.solicitacao.protocolo if resultado.solicitacao else None,
                    "requer_handoff": resultado.requer_handoff,
                },
            )
        )
