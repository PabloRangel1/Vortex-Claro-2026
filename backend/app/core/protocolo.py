"""Gerador de protocolo no formato AAAA-MMDD-NNNNN.

A sequência é um contador em memória. Com PostgreSQL, a API o reposiciona na
inicialização a partir do maior número já gravado (`continuar_sequencia`) —
sem isso, depois de um reinício ela voltaria a 77301 e geraria um protocolo
que já existe no banco. Suficiente para uma instância só da API; com várias,
o número teria de vir de uma SEQUENCE do banco.
"""

from datetime import datetime
from itertools import count

from app.core.relogio import agora

_INICIO = 77301
_sequencia = count(_INICIO)

# Solicitações (contestação, upgrade...) têm numeração própria, como um número
# de chamado — não se confundem com o protocolo do atendimento.
_INICIO_SOLICITACAO = 1001
_sequencia_solicitacao = count(_INICIO_SOLICITACAO)


def gerar_protocolo(referencia: datetime | None = None) -> str:
    ref = referencia or agora()
    return f"{ref.year}-{ref.month:02d}{ref.day:02d}-{next(_sequencia):05d}"


def gerar_protocolo_solicitacao(referencia: datetime | None = None) -> str:
    """Formato SOL-AAAAMMDD-NNNN."""
    ref = referencia or agora()
    return (
        f"SOL-{ref.year}{ref.month:02d}{ref.day:02d}-"
        f"{next(_sequencia_solicitacao):04d}"
    )


def continuar_sequencia(ultimo_protocolo: int | None, ultima_solicitacao: int | None) -> None:
    """Retoma a numeração depois do maior número já persistido."""
    global _sequencia, _sequencia_solicitacao
    _sequencia = count(max(_INICIO, (ultimo_protocolo or 0) + 1))
    _sequencia_solicitacao = count(
        max(_INICIO_SOLICITACAO, (ultima_solicitacao or 0) + 1)
    )


def reiniciar_sequencia() -> None:
    """Usado pelos testes para tornar os protocolos determinísticos."""
    global _sequencia, _sequencia_solicitacao
    _sequencia = count(_INICIO)
    _sequencia_solicitacao = count(_INICIO_SOLICITACAO)
