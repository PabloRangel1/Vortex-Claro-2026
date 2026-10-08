"""Motor de Score de Fricção.

Coração do produto. Cada turno do cliente é submetido a um conjunto de
detectores independentes; cada detector que dispara devolve um SinalFriccao
com peso e descrição legível. O score é a acumulação dos pesos, saturada em
[0, 100].

Nada aqui sabe onde os dados moram — recebe entidades de domínio e devolve
uma avaliação. É a parte que NÃO muda quando Redis/Mongo/Postgres entrarem.
"""

from datetime import datetime, timezone

from app.config import Settings
from app.core.texto import (
    contencao,
    normalizar,
    proporcao_maiusculas,
    similaridade,
    tokens_relevantes,
)
from app.domain.enums import Canal, CodigoSinal, Intencao, NivelFriccao
from app.domain.models import AvaliacaoFriccao, Mensagem, Sessao, SinalFriccao

# Pedido explícito de atendimento humano — o sinal mais forte que existe.
TERMOS_PEDIDO_HUMANO = (
    "atendente", "humano", "pessoa de verdade", "falar com alguem", "gerente",
    "supervisor", "nao quero robo", "sair do robo", "quero uma pessoa",
    "falar com uma pessoa", "atendimento humano",
)

# Léxico de insatisfação — peso proporcional à intensidade.
LEXICO_NEGATIVO = {
    "absurdo": 4, "ridiculo": 5, "pessimo": 4, "pessima": 4, "horrivel": 4,
    "palhacada": 5, "vergonha": 4, "vergonhoso": 4, "descaso": 5, "inaceitavel": 5,
    "nao aguento": 4, "cansado": 3, "cansada": 3, "ja falei": 4, "ja expliquei": 5,
    "ja disse": 4, "de novo": 2, "denovo": 2, "outra vez": 2, "nunca": 2,
    "tres vezes": 4, "3 vezes": 4, "varias vezes": 3, "enrolando": 4, "enrolacao": 4,
    "procon": 5, "processar": 5, "reclame aqui": 5, "nao resolve": 4,
    "nao resolveu": 4, "nao adianta": 3, "perdendo tempo": 4, "inutil": 4,
}


class FriccaoService:
    def __init__(self, settings: Settings) -> None:
        self._s = settings

    # ------------------------------------------------------------------ público

    def avaliar(
        self,
        *,
        texto: str,
        score_atual: int,
        sessao: Sessao,
        historico_cliente: list[Mensagem],
        troca_de_canal: bool,
        intencao: Intencao,
        ja_houve_handoff: bool,
        canal_anterior: Canal | None = None,
    ) -> AvaliacaoFriccao:
        """Roda todos os detectores sobre o turno e devolve a avaliação auditável."""
        sinais: list[SinalFriccao] = []

        for detector in (
            self._detectar_pedido_humano,
            self._detectar_repeticao,
            self._detectar_sentimento_negativo,
            self._detectar_caixa_alta,
            self._detectar_impaciencia,
        ):
            sinal = detector(texto, historico_cliente)
            if sinal:
                sinais.append(sinal)

        if troca_de_canal:
            # O canal anterior é o de ONDE veio agora — não necessariamente o de
            # origem. Numa jornada app → whatsapp → app, usar canal_origem faria
            # a descrição dizer "App Claro → App Claro".
            de = canal_anterior or sessao.canal_origem
            sinais.append(
                SinalFriccao(
                    codigo=CodigoSinal.TROCA_CANAL,
                    peso=self._s.peso_troca_canal,
                    descricao=(
                        f"Cliente migrou de canal mantendo a mesma demanda "
                        f"({de.rotulo} → {sessao.canal_ativo.rotulo})"
                    ),
                )
            )

        if sinal := self._detectar_intencao_repetida(sessao, intencao):
            sinais.append(sinal)

        if sinal := self._detectar_loop(sessao):
            sinais.append(sinal)

        return self._consolidar(score_atual, sinais, ja_houve_handoff)

    def aplicar_decaimento(self, score_atual: int, motivo: str) -> AvaliacaoFriccao:
        """Resposta humana/resolutiva reduz a fricção acumulada."""
        sinal = SinalFriccao(
            codigo=CodigoSinal.DECAIMENTO,
            peso=-self._s.peso_decaimento,
            descricao=motivo,
        )
        return self._consolidar(score_atual, [sinal], ja_houve_handoff=True)

    def nivel(self, score: int) -> NivelFriccao:
        if score >= self._s.limiar_handoff:
            return NivelFriccao.CRITICO
        if score >= self._s.limiar_atencao:
            return NivelFriccao.ATENCAO
        return NivelFriccao.ESTAVEL

    # ---------------------------------------------------------------- detectores

    def _detectar_pedido_humano(self, texto: str, _: list[Mensagem]) -> SinalFriccao | None:
        normalizado = normalizar(texto)
        achado = next((t for t in TERMOS_PEDIDO_HUMANO if t in normalizado), None)
        if not achado:
            return None
        return SinalFriccao(
            codigo=CodigoSinal.PEDIDO_HUMANO,
            peso=self._s.peso_pedido_humano,
            descricao=f'Cliente pediu atendimento humano explicitamente ("{achado}")',
        )

    def _detectar_repeticao(self, texto: str, historico: list[Mensagem]) -> SinalFriccao | None:
        """Duas formas de repetir a mesma coisa, ambas contam como fricção.

        1. LITERAL — o cliente reenvia praticamente o mesmo texto.
        2. REFORMULADA — o cliente reescreve a demanda em outras palavras (ou
           mais curto). O SequenceMatcher sozinho perde esse caso porque pune
           diferença de comprimento; a sobreposição de palavras de conteúdo pega.
        """
        janela = historico[-self._s.janela_repeticao :]
        tokens_atuais = tokens_relevantes(texto)

        for anterior in janela:
            razao = similaridade(texto, anterior.conteudo)
            if razao >= self._s.limiar_similaridade:
                return SinalFriccao(
                    codigo=CodigoSinal.REPETICAO,
                    peso=self._s.peso_repeticao,
                    descricao=(
                        f"Cliente reenviou praticamente a mesma mensagem "
                        f"({razao:.0%} de similaridade com um turno anterior)"
                    ),
                )

            # A contenção só é confiável com massa de texto suficiente: em
            # mensagens curtas ("ok", "e aí?") ela dispararia por acaso.
            anteriores = tokens_relevantes(anterior.conteudo)
            if min(len(tokens_atuais), len(anteriores)) < self._s.min_tokens_contencao:
                continue

            sobreposicao = contencao(texto, anterior.conteudo)
            if sobreposicao >= self._s.limiar_contencao:
                return SinalFriccao(
                    codigo=CodigoSinal.REPETICAO,
                    peso=self._s.peso_repeticao,
                    descricao=(
                        f"Cliente reformulou a mesma demanda "
                        f"({sobreposicao:.0%} das palavras já ditas em um turno anterior)"
                    ),
                )
        return None

    def _detectar_sentimento_negativo(self, texto: str, _: list[Mensagem]) -> SinalFriccao | None:
        normalizado = normalizar(texto)
        achados = {t: p for t, p in LEXICO_NEGATIVO.items() if t in normalizado}
        if not achados:
            return None
        bruto = self._s.peso_sentimento_base + sum(achados.values()) * 2
        peso = min(self._s.peso_sentimento_max, bruto)
        termos = ", ".join(sorted(achados)[:3])
        return SinalFriccao(
            codigo=CodigoSinal.SENTIMENTO_NEGATIVO,
            peso=peso,
            descricao=f"Linguagem de insatisfação detectada ({termos})",
        )

    def _detectar_caixa_alta(self, texto: str, _: list[Mensagem]) -> SinalFriccao | None:
        if len(texto) <= 10 or proporcao_maiusculas(texto) < 0.6:
            return None
        return SinalFriccao(
            codigo=CodigoSinal.CAIXA_ALTA,
            peso=self._s.peso_caixa_alta,
            descricao="Mensagem majoritariamente em caixa alta (indício de exaltação)",
        )

    def _detectar_impaciencia(self, _: str, historico: list[Mensagem]) -> SinalFriccao | None:
        n = self._s.mensagens_impaciencia
        if len(historico) < n - 1:
            return None
        recentes = historico[-(n - 1) :]
        agora = datetime.now(timezone.utc)
        intervalo = (agora - recentes[0].criada_em).total_seconds()
        if intervalo > self._s.janela_impaciencia_segundos:
            return None
        return SinalFriccao(
            codigo=CodigoSinal.IMPACIENCIA,
            peso=self._s.peso_impaciencia,
            descricao=f"{n} mensagens em menos de {self._s.janela_impaciencia_segundos}s",
        )

    def _detectar_intencao_repetida(
        self, sessao: Sessao, intencao: Intencao
    ) -> SinalFriccao | None:
        if intencao == Intencao.OUTROS:
            return None
        # sessao.turnos_mesma_intencao já foi incrementado pelo SessaoService
        if sessao.turnos_mesma_intencao < self._s.turnos_mesma_intencao:
            return None
        return SinalFriccao(
            codigo=CodigoSinal.INTENCAO_REPETIDA,
            peso=self._s.peso_intencao_repetida,
            descricao=(
                f'{sessao.turnos_mesma_intencao} turnos consecutivos sobre '
                f'"{intencao.rotulo}" sem resolução'
            ),
        )

    def _detectar_loop(self, sessao: Sessao) -> SinalFriccao | None:
        excedente = sessao.turnos - self._s.turnos_para_loop
        if excedente <= 0:
            return None
        peso = min(self._s.peso_loop_max, self._s.peso_loop * excedente)
        return SinalFriccao(
            codigo=CodigoSinal.LOOP_SEM_RESOLUCAO,
            peso=peso,
            descricao=f"{sessao.turnos} turnos com o bot sem resolução da demanda",
        )

    # -------------------------------------------------------------- consolidação

    def _consolidar(
        self, score_anterior: int, sinais: list[SinalFriccao], ja_houve_handoff: bool
    ) -> AvaliacaoFriccao:
        bruto = score_anterior + sum(s.peso for s in sinais)
        score_atual = max(self._s.score_minimo, min(self._s.score_maximo, bruto))

        cruzou = (
            not ja_houve_handoff
            and score_anterior < self._s.limiar_handoff
            and score_atual >= self._s.limiar_handoff
        )
        motivo = None
        if cruzou:
            principais = sorted(sinais, key=lambda s: s.peso, reverse=True)[:2]
            causa = " + ".join(s.descricao for s in principais) or "acúmulo de fricção"
            motivo = f"Score {score_atual} ultrapassou o limiar {self._s.limiar_handoff} — {causa}"

        return AvaliacaoFriccao(
            score_anterior=score_anterior,
            score_atual=score_atual,
            delta=score_atual - score_anterior,
            nivel=self.nivel(score_atual),
            sinais=sinais,
            deve_disparar_handoff=cruzou,
            motivo_handoff=motivo,
        )
