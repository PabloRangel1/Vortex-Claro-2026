"""Relógio da aplicação — o único lugar que diz "agora".

Em produção é só `datetime.now(UTC)`. O deslocamento existe para a simulação
pré-carregada (`services/demonstracao_service.py`): ela passa pelo MESMO
orquestrador de uma conversa real, mas "voltando no tempo", para que as
conversas de ontem e da semana passada tenham datas de ontem e da semana
passada — sem inserir linhas falsas direto no banco.
"""

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

_deslocamento = timedelta(0)


def agora() -> datetime:
    return datetime.now(timezone.utc) + _deslocamento


def avancar(segundos: float) -> None:
    """Faz o tempo simulado andar (entre uma mensagem e outra da simulação)."""
    global _deslocamento
    _deslocamento += timedelta(seconds=segundos)


@contextmanager
def no_passado(delta: timedelta):
    """Tudo dentro do bloco acontece `delta` atrás. Sempre restaura o relógio."""
    global _deslocamento
    anterior = _deslocamento
    _deslocamento = -delta
    try:
        yield
    finally:
        _deslocamento = anterior
