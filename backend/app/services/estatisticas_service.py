"""Agregações para o painel de estatísticas.

Responde à pergunta de negócio: *do que os clientes mais reclamam, e onde a
fricção se concentra?*

Nesta fase tudo é calculado em memória sobre a lista completa de atendimentos.
Na fase 2 cada bloco vira um `GROUP BY` no PostgreSQL — por isso o serviço
recebe as listas prontas do repositório em vez de iterar em dicionários: a
assinatura não muda quando a agregação descer para o banco.
"""

from collections import Counter, defaultdict
from datetime import timedelta, timezone

from app.config import Settings
from app.domain.acoes import CATALOGO, RESOLVEM_A_DEMANDA
from app.domain.enums import (
    AcaoAutoatendimento,
    Canal,
    CodigoSinal,
    Intencao,
    NivelFriccao,
    Remetente,
    StatusAcao,
    StatusAtendimento,
)
from app.domain.models import Atendimento, EventoFriccao, Mensagem, agora
from app.services.friccao_service import FriccaoService

# Descrição curta de cada sinal, para o painel não repetir a frase longa da auditoria.
ROTULO_SINAL: dict[CodigoSinal, str] = {
    CodigoSinal.PEDIDO_HUMANO: "Pediu atendente",
    CodigoSinal.REPETICAO: "Repetiu a demanda",
    CodigoSinal.TROCA_CANAL: "Trocou de canal",
    CodigoSinal.SENTIMENTO_NEGATIVO: "Insatisfação explícita",
    CodigoSinal.INTENCAO_REPETIDA: "Mesmo assunto sem solução",
    CodigoSinal.LOOP_SEM_RESOLUCAO: "Loop com o bot",
    CodigoSinal.IMPACIENCIA: "Impaciência",
    CodigoSinal.CAIXA_ALTA: "Caixa alta",
    CodigoSinal.DECAIMENTO: "Atendente assumiu",
}


# Dias contados no horário de Brasília (a virada do dia é a do cliente).
_BRASILIA = timezone(timedelta(hours=-3))
DIAS_NA_SERIE = 10

# Fricção a partir da qual o cliente é considerado "em risco" de desistir.
LIMIAR_RISCO = 40


def _media(valores: list[int | float]) -> float:
    return round(sum(valores) / len(valores), 1) if valores else 0.0


class EstatisticasService:
    def __init__(self, friccao: FriccaoService, settings: Settings) -> None:
        self._friccao = friccao
        self._s = settings

    def consolidar(
        self,
        atendimentos: list[Atendimento],
        eventos: list[EventoFriccao],
        registros: list[Mensagem] | None = None,
        precos_por_cliente: dict[str, int] | None = None,
        hoje=None,
    ) -> dict:
        if not atendimentos:
            return self._vazio()
        registros = registros or []

        scores = [a.score_friccao for a in atendimentos]
        com_handoff = [a for a in atendimentos if a.handoff_em is not None]
        encerrados = [a for a in atendimentos if a.status == StatusAtendimento.ENCERRADO]
        avaliados = [a for a in atendimentos if a.nota is not None]

        return {
            "resumo": {
                "total_atendimentos": len(atendimentos),
                "em_aberto": len(atendimentos) - len(encerrados),
                "encerrados": len(encerrados),
                "score_medio": _media(scores),
                "score_maximo": max(scores),
                "handoffs": len(com_handoff),
                "taxa_handoff": round(100 * len(com_handoff) / len(atendimentos)),
                "transferencias": sum(a.transferencias for a in atendimentos),
                "troca_de_canal": sum(1 for a in atendimentos if len(a.canais_utilizados) > 1),
            },
            "por_intencao": self._por_intencao(atendimentos),
            "por_nivel": self._por_nivel(atendimentos),
            "por_canal_origem": self._por_canal(atendimentos),
            "sinais": self._sinais(eventos),
            "csat": self._csat(avaliados),
            "autoatendimento": self._autoatendimento(atendimentos, registros),
            "por_dia": self._por_dia(atendimentos, registros, hoje),
            "impacto": self._impacto(atendimentos, eventos, registros, precos_por_cliente or {}),
        }

    # ----------------------------------------------------- série diária

    def _desfecho(self, a: Atendimento, resolveram: set[str]) -> str:
        if a.handoff_em is not None:
            return "transferido"
        if a.status == StatusAtendimento.ENCERRADO or a.protocolo in resolveram:
            return "resolvido_bot"
        return "em_andamento"

    def _por_dia(self, atendimentos, registros, hoje) -> list[dict]:
        """Atendimentos por dia (por desfecho) e fricção média — últimos 10 dias."""
        resolveram = self._protocolos_resolvidos(registros)
        # "Hoje" é o dia de hoje — não o do atendimento mais recente.
        hoje = hoje or agora().astimezone(_BRASILIA).date()
        dias = [hoje - timedelta(days=n) for n in range(DIAS_NA_SERIE - 1, -1, -1)]
        por_dia: dict = {d: [] for d in dias}
        for a in atendimentos:
            d = a.aberto_em.astimezone(_BRASILIA).date()
            if d in por_dia:
                por_dia[d].append(a)
        linhas = []
        for d in dias:
            itens = por_dia[d]
            desfechos = Counter(self._desfecho(a, resolveram) for a in itens)
            linhas.append({
                "data": d.isoformat(),
                "total": len(itens),
                "resolvido_bot": desfechos.get("resolvido_bot", 0),
                "transferido": desfechos.get("transferido", 0),
                "em_andamento": desfechos.get("em_andamento", 0),
                "score_medio": _media([a.score_friccao for a in itens]) if itens else None,
            })
        return linhas

    def _protocolos_resolvidos(self, registros: list[Mensagem]) -> set[str]:
        resolvem = {str(x) for x in RESOLVEM_A_DEMANDA}
        return {
            m.protocolo for m in registros
            if m.metadados.get("tipo") == "acao"
            and m.metadados.get("status") == StatusAcao.SUCESSO
            and m.metadados.get("acao") in resolvem
        }

    # ------------------------------------------------- impacto (simulação)

    def _impacto(self, atendimentos, eventos, registros, precos_por_cliente) -> dict:
        """O cliente que a Claro NÃO perdeu — comparação com e sem o Vortex.

        "Sem o Vortex" é contrafactual, montado só com o que foi registrado:
          - cada troca de canal abriria um protocolo novo e o cliente recontaria
            a história; cada transferência para humano sem contexto, também;
          - o cliente em risco (fricção >= 40 ou transferido) não teria alerta.
        "Receita protegida" soma a mensalidade do plano dos clientes em risco que
        saíram sem nota negativa (1 ou 2) — uma estimativa, não faturamento.
        """
        trocas = sum(max(0, len(a.canais_utilizados) - 1) for a in atendimentos)
        handoffs = sum(1 for a in atendimentos if a.handoff_em is not None)
        repeticoes = sum(1 for e in eventos if e.codigo_sinal == CodigoSinal.REPETICAO)

        em_risco = [
            a for a in atendimentos
            if a.score_friccao >= LIMIAR_RISCO or a.handoff_em is not None
        ]
        insatisfeitos = [a for a in em_risco if a.nota is not None and a.nota <= 2]
        retidos = [a for a in em_risco if a not in insatisfeitos]
        satisfeitos = [a for a in em_risco if a.nota is not None and a.nota >= 4]
        clientes_retidos = {a.cliente_id for a in retidos}

        upgrades = [
            m for m in registros
            if m.metadados.get("tipo") == "acao"
            and m.metadados.get("acao") == str(AcaoAutoatendimento.CONFIRMAR_UPGRADE)
            and m.metadados.get("status") == StatusAcao.SUCESSO
        ]
        receita_upgrades = sum(
            (u.metadados["dados"].get("plano_novo") or {}).get("preco_centavos", 0)
            - (u.metadados["dados"].get("plano_atual") or {}).get("preco_centavos", 0)
            for u in upgrades
        )

        # A jornada que conta a história: a que mais trocou de canal; no empate,
        # a de maior fricção.
        exemplo = max(
            atendimentos, key=lambda a: (len(a.canais_utilizados), a.score_friccao)
        )

        return {
            "contatos": len(atendimentos),
            "trocas_de_canal": trocas,
            "protocolos_sem_vortex": len(atendimentos) + trocas,
            "protocolos_com_vortex": len(atendimentos),
            "relatos_repetidos_sem_vortex": repeticoes + trocas + handoffs,
            "relatos_repetidos_com_vortex": repeticoes,
            "em_risco": len(em_risco),
            "em_risco_atendidos_com_contexto": handoffs,
            "em_risco_retidos": len(retidos),
            "em_risco_satisfeitos": len(satisfeitos),
            "em_risco_insatisfeitos": len(insatisfeitos),
            "receita_mensal_protegida_centavos": sum(
                precos_por_cliente.get(c, 0) for c in clientes_retidos
            ),
            "upgrades": len(upgrades),
            "receita_mensal_upgrades_centavos": receita_upgrades,
            "jornada_exemplo": {
                "protocolo": exemplo.protocolo,
                "canais": [str(c) for c in exemplo.canais_utilizados],
                "historico_score": exemplo.historico_score,
                "score_final": exemplo.score_friccao,
                "intencao_rotulo": exemplo.intencao.rotulo,
                "status": str(exemplo.status),
                "houve_handoff": exemplo.handoff_em is not None,
                "nota": exemplo.nota,
            },
        }

    # ------------------------------------------------------------------ blocos

    def _autoatendimento(self, atendimentos: list[Atendimento], registros: list[Mensagem]) -> dict:
        """O objetivo do produto em números: quanto o cliente resolveu sozinho.

        "Resolvido sem humano" = o atendimento teve ao menos uma ação que entrega
        o pedido (RESOLVEM_A_DEMANDA, com sucesso) e nunca precisou de handoff.
        """
        # Encaminhar a humano é registrado como ação, mas é o oposto de resolver.
        acoes = [
            m for m in registros
            if m.metadados.get("tipo") == "acao"
            and m.metadados.get("acao") != str(AcaoAutoatendimento.ENCAMINHAR_HUMANO)
        ]
        sucessos = [a for a in acoes if a.metadados.get("status") == StatusAcao.SUCESSO]

        resolveram = {
            a.protocolo
            for a in sucessos
            if a.metadados.get("acao") in {str(x) for x in RESOLVEM_A_DEMANDA}
        }
        sem_humano = [
            a for a in atendimentos if a.protocolo in resolveram and a.handoff_em is None
        ]

        por_acao: dict[str, Counter] = defaultdict(Counter)
        for a in acoes:
            if a.metadados.get("acao"):
                por_acao[a.metadados["acao"]][a.metadados.get("status")] += 1

        return {
            "resolvidos_sem_humano": len(sem_humano),
            "taxa_resolucao": round(100 * len(sem_humano) / len(atendimentos)),
            "acoes_executadas": len(sucessos),
            "falhas": len(acoes) - len(sucessos),
            "respostas_com_ia": sum(
                1 for m in registros if m.remetente == Remetente.BOT and m.metadados.get("ia")
            ),
            "por_acao": sorted(
                (
                    {
                        "acao": acao,
                        "rotulo": CATALOGO[AcaoAutoatendimento(acao)].descricao,
                        "total": sum(c.values()),
                        "sucesso": c.get(str(StatusAcao.SUCESSO), 0),
                    }
                    for acao, c in por_acao.items()
                ),
                key=lambda l: -l["total"],
            ),
        }

    def _por_intencao(self, atendimentos: list[Atendimento]) -> list[dict]:
        """O 'do que reclamam' — ordenado por volume."""
        agrupado: dict[Intencao, list[Atendimento]] = defaultdict(list)
        for a in atendimentos:
            agrupado[a.intencao].append(a)

        linhas = [
            {
                "intencao": str(i),
                "rotulo": i.rotulo,
                "total": len(itens),
                "score_medio": _media([x.score_friccao for x in itens]),
                "handoffs": sum(1 for x in itens if x.handoff_em is not None),
            }
            for i, itens in agrupado.items()
        ]
        linhas.sort(key=lambda l: (-l["total"], -l["score_medio"]))
        return linhas

    def _por_nivel(self, atendimentos: list[Atendimento]) -> list[dict]:
        """Distribuição pelas faixas de fricção, sempre com as três presentes."""
        contagem = Counter(self._friccao.nivel(a.score_friccao) for a in atendimentos)
        total = len(atendimentos)
        return [
            {
                "nivel": str(n),
                "total": contagem.get(n, 0),
                "percentual": round(100 * contagem.get(n, 0) / total) if total else 0,
            }
            for n in (NivelFriccao.ESTAVEL, NivelFriccao.ATENCAO, NivelFriccao.CRITICO)
        ]

    def _por_canal(self, atendimentos: list[Atendimento]) -> list[dict]:
        contagem = Counter(a.canal_origem for a in atendimentos)
        return [
            {"canal": str(c), "rotulo": c.rotulo, "total": contagem.get(c, 0)}
            for c in (Canal.APP, Canal.WHATSAPP)
        ]

    def _sinais(self, eventos: list[EventoFriccao]) -> list[dict]:
        """Quais gatilhos de fricção mais disparam — ordenado por frequência."""
        contagem: Counter[CodigoSinal] = Counter()
        peso: dict[CodigoSinal, int] = defaultdict(int)
        for e in eventos:
            contagem[e.codigo_sinal] += 1
            peso[e.codigo_sinal] += e.peso

        return [
            {
                "codigo": str(c),
                "rotulo": ROTULO_SINAL.get(c, str(c)),
                "ocorrencias": n,
                "peso_acumulado": peso[c],
            }
            for c, n in contagem.most_common()
        ]

    def _csat(self, avaliados: list[Atendimento]) -> dict:
        notas = [a.nota for a in avaliados if a.nota is not None]
        distribuicao = Counter(notas)
        # Satisfação = notas 4 e 5, convenção usual de CSAT.
        satisfeitos = sum(1 for n in notas if n >= 4)
        return {
            "media": _media(notas),
            "total_avaliacoes": len(notas),
            "percentual_satisfeitos": round(100 * satisfeitos / len(notas)) if notas else 0,
            "distribuicao": [
                {"nota": n, "total": distribuicao.get(n, 0)} for n in range(1, 6)
            ],
            "comentarios": [
                {"nota": a.nota, "comentario": a.comentario, "protocolo": a.protocolo}
                for a in avaliados
                if a.comentario
            ][-5:],
        }

    def _vazio(self) -> dict:
        return {
            "resumo": {
                "total_atendimentos": 0, "em_aberto": 0, "encerrados": 0,
                "score_medio": 0.0, "score_maximo": 0, "handoffs": 0,
                "taxa_handoff": 0, "transferencias": 0, "troca_de_canal": 0,
            },
            "por_intencao": [],
            "por_nivel": self._por_nivel([]),
            "por_canal_origem": self._por_canal([]),
            "sinais": [],
            "csat": self._csat([]),
            "autoatendimento": {
                "resolvidos_sem_humano": 0, "taxa_resolucao": 0, "acoes_executadas": 0,
                "falhas": 0, "respostas_com_ia": 0, "por_acao": [],
            },
            "por_dia": [],
            "impacto": None,
        }
