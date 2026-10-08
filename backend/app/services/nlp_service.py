"""Classificação de intenção por regras ponderadas.

Não é machine learning — é um classificador léxico determinístico, que para o
escopo do Challenge tem duas vantagens sobre um modelo: roda em microssegundos
(ajuda no requisito de < 2s) e é 100% explicável, então o dashboard consegue
mostrar POR QUE a intenção foi escolhida.

Os termos são escritos SEM acento porque o texto é normalizado antes.
"""

from pydantic import BaseModel, Field

from app.config import Settings
from app.core.texto import contem_termo, normalizar
from app.domain.enums import Intencao

# termo -> peso (1 = fraco/ambíguo, 3 = altamente discriminante)
TERMOS: dict[Intencao, dict[str, int]] = {
    Intencao.SUPORTE_TECNICO: {
        "internet": 2, "sem sinal": 3, "sem internet": 3, "caiu": 2, "caindo": 2,
        "lenta": 2, "lento": 2, "roteador": 3, "modem": 3, "wifi": 3, "conexao": 2,
        "instabilidade": 3, "nao funciona": 2, "travando": 2, "oscilando": 3,
        "sinal fraco": 3, "sem rede": 3, "reparo": 2, "tecnico": 2,
    },
    Intencao.CONTESTACAO_FATURA: {
        "nao reconheco": 3, "cobranca indevida": 3, "indevida": 3, "contestar": 3,
        "contestacao": 3, "veio errada": 3, "valor errado": 3, "cobrado a mais": 3,
        "cobranca que nao": 3, "nao reconheci": 3, "nao pedi": 2, "erro na fatura": 3,
        "servico que nao": 3, "descontar": 2,
    },
    Intencao.SEGUNDA_VIA: {
        "segunda via": 3, "2 via": 3, "codigo de barras": 3, "linha digitavel": 3,
        "boleto": 2, "reenviar fatura": 3, "copia da fatura": 3,
    },
    Intencao.FINANCEIRO: {
        "fatura": 2, "pagamento": 2, "pagar": 2, "vencimento": 2, "vencer": 2,
        "debito automatico": 3, "conta": 1, "valor": 1, "cobranca": 1,
        "negociar": 2, "parcelar": 2, "atraso": 2, "desconto": 2,
    },
    Intencao.PLANOS_UPGRADE: {
        "plano": 2, "upgrade": 3, "migrar": 2, "mudar de plano": 3,
        "adicionar linha": 3, "nova linha": 3, "gigas": 2, "franquia": 2,
        "portabilidade": 3, "aumentar": 2, "pacote": 2, "contratar": 2,
    },
    Intencao.CANCELAMENTO: {
        "cancelar": 3, "cancelamento": 3, "encerrar contrato": 3, "rescindir": 3,
        "rescisao": 3, "nao quero mais": 2, "quero sair": 2, "desistir": 2,
    },
}


class ResultadoNLP(BaseModel):
    intencao: Intencao
    confianca: int
    termos_detectados: list[str] = Field(default_factory=list)
    pontuacoes: dict[str, int] = Field(default_factory=dict)


class NLPService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def classificar(self, texto: str) -> ResultadoNLP:
        normalizado = normalizar(texto)
        if not normalizado:
            return ResultadoNLP(intencao=Intencao.OUTROS, confianca=0)

        pontuacoes: dict[Intencao, int] = {}
        encontrados: dict[Intencao, list[str]] = {}

        for intencao, termos in TERMOS.items():
            achados = [t for t in termos if contem_termo(normalizado, t)]
            if achados:
                pontuacoes[intencao] = sum(termos[t] for t in achados)
                encontrados[intencao] = achados

        if not pontuacoes:
            return ResultadoNLP(intencao=Intencao.OUTROS, confianca=0)

        vencedora = max(pontuacoes, key=lambda i: pontuacoes[i])
        pontos = pontuacoes[vencedora]
        total = sum(pontuacoes.values())

        # Confiança combina DOMINÂNCIA (o quanto se destaca das concorrentes) com
        # FORÇA ABSOLUTA (o quanto casou). Só assim um único termo fraco não vira 100%.
        dominancia = pontos / total
        forca = min(1.0, pontos / 6)
        confianca = round(100 * (0.55 * dominancia + 0.45 * forca))
        confianca = max(0, min(99, confianca))

        if confianca < self._settings.confianca_minima_nlp:
            return ResultadoNLP(
                intencao=Intencao.OUTROS,
                confianca=confianca,
                termos_detectados=encontrados[vencedora],
                pontuacoes={str(k): v for k, v in pontuacoes.items()},
            )

        return ResultadoNLP(
            intencao=vencedora,
            confianca=confianca,
            termos_detectados=encontrados[vencedora],
            pontuacoes={str(k): v for k, v in pontuacoes.items()},
        )
