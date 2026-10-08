"""IA como camada de linguagem (Gemini).

Regra de produto: a IA conversa e interpreta; o backend executa ações
permitidas. Na prática, este serviço só faz uma coisa — transforma uma mensagem
que as regras determinísticas não entenderam numa SUGESTÃO estruturada:

    acao_sugerida   uma das ações que o chamador permitiu naquele momento
    parametros      dia de vencimento ou plano escolhido, se citados
    confirmacao     "sim" / "nao" quando há uma pergunta de confirmação aberta
    resposta_cliente  texto livre, só quando não há ação a sugerir

O que este serviço NUNCA faz: executar ação, gravar dado, decidir score,
limiar ou handoff. Quem aplica a sugestão é o `DialogoService`, que valida de
novo e chama o `AutoatendimentoService` como faria com uma mensagem digitada.

Tudo que der errado — sem chave, timeout, cota gratuita esgotada, JSON
inválido, sugestão fora do permitido — devolve `None`, e a conversa segue pelo
caminho determinístico. Depois de uma falha de rede ou de cota, a IA fica em
pausa por alguns segundos para não pagar o timeout a cada mensagem.
"""

import json
import logging
import re
import time

import httpx
from pydantic import BaseModel, Field, ValidationError

from app.config import Settings
from app.core.privacidade import anonimizar
from app.domain.acoes import CATALOGO
from app.domain.enums import AcaoAutoatendimento, EtapaFluxo, Intencao, Remetente
from app.domain.models import Sessao
from app.repositories.base import ClienteRepository, ConversaRepository

log = logging.getLogger(__name__)

URL_GEMINI = "https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent"

SEM_ACAO = "nenhuma"

INSTRUCAO = """\
Você é a camada de linguagem do assistente virtual da Claro (operadora de
telecom) em um protótipo acadêmico com dados fictícios. Você NÃO executa nada:
apenas interpreta a mensagem do cliente e devolve um JSON.

Campos:
- acao_sugerida: a ação que o cliente está pedindo, escolhida SOMENTE entre
  "acoes_permitidas". Use "nenhuma" se ele não pediu nenhuma delas.
  Reclamar de valor, cobrança estranha ou conta mais cara que o normal é
  pedido de "abrir_contestacao". Querer o boleto ou o código é
  "gerar_segunda_via". Internet ruim é "diagnosticar_conexao".
- confirmacao: só quando "etapa" = "aguardando_confirmacao".
  "sim" = o cliente quer seguir com a ação pendente. ATENÇÃO: reafirmar o
  problema que motivou a ação também é "sim". Ex.: com a contestação pendente,
  "não reconheço essa cobrança" ou "isso eu não contratei" = "sim" (o "não"
  ali nega a cobrança, não a contestação).
  "nao" = desiste da ação pendente ("deixa pra lá", "não quero mais").
  "indefinido" = qualquer outra coisa, ou fora dessa etapa.
- dia: quando "etapa" = "aguardando_parametro" e há dias em "opcoes", converta
  o que o cliente disse para um desses dias. "Meio do mês" = o dia mais
  próximo de 15; "começo do mês" = o menor; "fim do mês" = o maior. Se não
  der para escolher, null. Nunca um dia fora de "opcoes".
- plano_id: quando há planos em "opcoes", o id do plano escolhido. "O mais
  barato"/"o mais em conta" = menor preco_centavos; "o maior"/"o mais
  completo" = maior franquia. Nunca um id fora de "opcoes".
- resposta_cliente: SOMENTE quando "etapa" = "nenhuma", acao_sugerida =
  "nenhuma" e não há escolha a fazer. Uma ou duas frases curtas, cordiais, em
  português do Brasil, dizendo o que o assistente consegue fazer. Em
  qualquer outra situação, null.

Regras obrigatórias para resposta_cliente:
- Nunca invente valores, datas, prazos, protocolos, números ou políticas.
- Nunca prometa ação que não esteja em "acoes_permitidas".
- Não diga que vai transferir para atendente: isso não é decisão sua. Também
  nunca diga que não é possível falar com uma pessoa. Se o cliente perguntar,
  diga que basta escrever "quero falar com um atendente".
"""


class SugestaoIA(BaseModel):
    """Sugestão já validada contra o que era permitido no momento."""

    acao: AcaoAutoatendimento | None = None
    parametros: dict = Field(default_factory=dict)
    confirmacao: str | None = None  # "sim" | "nao" | None
    resposta_cliente: str | None = None


class _SaidaModelo(BaseModel):
    """Formato bruto exigido do modelo — validado antes de qualquer uso."""

    acao_sugerida: str
    confirmacao: str = "indefinido"
    dia: int | None = None
    plano_id: str | None = None
    resposta_cliente: str | None = None


# Texto livre da IA não pode carregar fatos: números longos, valores ou
# protocolos só podem vir do backend.
_FATO_INVENTADO = re.compile(r"\d{3,}|R\$|protocolo|SOL-", re.IGNORECASE)


class IAService:
    def __init__(
        self,
        settings: Settings,
        conversas: ConversaRepository,
        clientes: ClienteRepository | None = None,
    ) -> None:
        self._s = settings
        self._conversas = conversas
        self._clientes = clientes
        self._cliente: httpx.AsyncClient | None = None
        self._pausada_ate = 0.0

    @property
    def configurada(self) -> bool:
        return bool(self._s.gemini_api_key)

    @property
    def disponivel(self) -> bool:
        return self.configurada and time.monotonic() >= self._pausada_ate

    async def fechar(self) -> None:
        if self._cliente is not None:
            await self._cliente.aclose()
            self._cliente = None

    # ================================================================ público

    async def interpretar(
        self,
        *,
        sessao: Sessao,
        texto: str,
        intencao: Intencao | None,
        permitidas: list[AcaoAutoatendimento],
    ) -> SugestaoIA | None:
        if not self.disponivel:
            return None
        contexto = await self._montar_contexto(sessao, texto, intencao, permitidas)
        bruto = await self._chamar_modelo(contexto, permitidas)
        if bruto is None:
            return None
        return self._validar(bruto, sessao, permitidas)

    # ============================================================== contexto

    async def _montar_contexto(self, sessao, texto, intencao, permitidas) -> dict:
        """Contexto MÍNIMO: sem nome, CPF, telefone ou identificador do cliente.

        Duas exclusões que a auditoria de segurança achou faltando:
          - o NOME do cliente, que o bot usa ao cumprimentar ("Obrigado, Ana!");
          - as respostas da VERIFICAÇÃO (os dígitos do CPF), que são o próprio
            segredo de identidade e não têm nada a ver com o pedido.
        """
        nomes: tuple[str, ...] = ()
        if self._clientes is not None:
            cliente = await self._clientes.obter(sessao.cliente_id)
            nomes = tuple(cliente.nome.split()) if cliente else ()
        recentes = (await self._conversas.listar_mensagens(sessao.protocolo))[-8:]
        conversa = [
            {"de": str(m.remetente), "texto": anonimizar(m.conteudo, nomes)[:400]}
            for m in recentes
            if m.remetente in (Remetente.CLIENTE, Remetente.BOT)
            and not m.metadados.get("verificacao")
        ]
        contexto = {
            "etapa": str(sessao.etapa_fluxo),
            "acao_pendente": (
                CATALOGO[sessao.acao_pendente].descricao if sessao.acao_pendente else None
            ),
            "opcoes": self._opcoes(sessao),
            "intencao_detectada": intencao.rotulo if intencao else None,
            "canal": sessao.canal_ativo.rotulo,
            "acoes_permitidas": [
                {"acao": str(a), "descricao": CATALOGO[a].descricao} for a in permitidas
            ],
            "conversa_recente": conversa,
            "mensagem_atual": anonimizar(texto, nomes)[:600],
        }
        return contexto

    @staticmethod
    def _opcoes(sessao: Sessao) -> list:
        opcoes = sessao.dados_pendentes.get("opcoes") or []
        if sessao.acao_pendente == AcaoAutoatendimento.ALTERAR_VENCIMENTO:
            return [{"dia": d} for d in opcoes]
        return [
            {"plano_id": o["id"], "nome": o["nome"], "franquia": o["franquia"],
             "preco_centavos": o.get("preco_centavos")}
            for o in opcoes
            if isinstance(o, dict)
        ]

    # ================================================================ modelo

    async def _chamar_modelo(self, contexto: dict, permitidas: list) -> dict | None:
        corpo = {
            "systemInstruction": {"parts": [{"text": INSTRUCAO}]},
            "contents": [
                {"role": "user", "parts": [{"text": json.dumps(contexto, ensure_ascii=False)}]}
            ],
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 300,
                "responseMimeType": "application/json",
                "responseSchema": self._schema(permitidas),
            },
        }
        # Raciocínio interno no mínimo: a tarefa é curta e cada segundo conta.
        if "2.5" in self._s.gemini_modelo:
            corpo["generationConfig"]["thinkingConfig"] = {"thinkingBudget": 0}
        elif self._s.gemini_modelo.startswith("gemini-3"):
            corpo["generationConfig"]["thinkingConfig"] = {"thinkingLevel": "minimal"}

        try:
            if self._cliente is None:
                self._cliente = httpx.AsyncClient(timeout=self._s.ia_timeout_segundos)
            r = await self._cliente.post(
                URL_GEMINI.format(modelo=self._s.gemini_modelo),
                headers={"x-goog-api-key": self._s.gemini_api_key},
                json=corpo,
            )
        except httpx.HTTPError as erro:
            self._pausar(f"falha de rede: {type(erro).__name__}")
            return None

        if r.status_code != 200:
            # 429 = cota gratuita; 5xx = instabilidade; 4xx = chave/modelo/pedido.
            self._pausar(f"HTTP {r.status_code}: {r.text[:200]}")
            return None
        try:
            texto = r.json()["candidates"][0]["content"]["parts"][0]["text"]
            return json.loads(texto)
        except (KeyError, IndexError, ValueError) as erro:
            log.warning("IA: resposta fora do formato (%s)", erro)
            return None

    @staticmethod
    def _schema(permitidas: list) -> dict:
        return {
            "type": "OBJECT",
            "properties": {
                "acao_sugerida": {
                    "type": "STRING",
                    "enum": [SEM_ACAO, *(str(a) for a in permitidas)],
                },
                "confirmacao": {"type": "STRING", "enum": ["sim", "nao", "indefinido"]},
                "dia": {"type": "INTEGER", "nullable": True},
                "plano_id": {"type": "STRING", "nullable": True},
                "resposta_cliente": {"type": "STRING", "nullable": True},
            },
            "required": ["acao_sugerida", "confirmacao"],
        }

    def _pausar(self, motivo: str) -> None:
        self._pausada_ate = time.monotonic() + self._s.ia_pausa_apos_erro_segundos
        log.warning(
            "IA pausada por %ss (%s) — usando fallback determinístico",
            self._s.ia_pausa_apos_erro_segundos, motivo,
        )

    # ============================================================= validação

    def _validar(self, bruto: dict, sessao: Sessao, permitidas: list) -> SugestaoIA | None:
        """Nada do modelo é usado sem passar por aqui."""
        try:
            saida = _SaidaModelo.model_validate(bruto)
        except ValidationError:
            # Só a forma, nunca o conteúdo: a saída do modelo pode ecoar o que
            # o cliente escreveu, e log não é lugar de dado de cliente.
            log.warning("IA: JSON fora do contrato (chaves: %s)", sorted(bruto)[:10])
            return None

        sugestao = SugestaoIA()

        if saida.acao_sugerida != SEM_ACAO:
            try:
                acao = AcaoAutoatendimento(saida.acao_sugerida)
            except ValueError:
                return None
            if acao not in permitidas:
                return None
            sugestao.acao = acao

        if sessao.etapa_fluxo == EtapaFluxo.AGUARDANDO_CONFIRMACAO and saida.confirmacao in (
            "sim",
            "nao",
        ):
            sugestao.confirmacao = saida.confirmacao

        # Parâmetros só valem se forem uma das opções oferecidas ao cliente.
        oferecidas = sessao.dados_pendentes.get("opcoes") or []
        if saida.dia is not None and saida.dia in oferecidas:
            sugestao.parametros["dia"] = saida.dia
        ids = {o["id"] for o in oferecidas if isinstance(o, dict)}
        if saida.plano_id and saida.plano_id in ids:
            sugestao.parametros["plano_id"] = saida.plano_id

        texto = (saida.resposta_cliente or "").strip()
        if (
            texto
            and sugestao.acao is None
            and sugestao.confirmacao is None
            and not sugestao.parametros
            and len(texto) <= 400
            and not _FATO_INVENTADO.search(texto)
        ):
            sugestao.resposta_cliente = texto

        vazia = (
            sugestao.acao is None
            and sugestao.confirmacao is None
            and not sugestao.parametros
            and sugestao.resposta_cliente is None
        )
        return None if vazia else sugestao
