"""Normalização e comparação de texto.

Tudo que o NLP e o motor de fricção comparam passa por `normalizar` primeiro:
acentos e pontuação fora, caixa baixa, espaços colapsados. Assim os dicionários
de termos podem ser escritos sem acento e ainda casar com "não reconheço".
"""

import re
import unicodedata
from difflib import SequenceMatcher

_PONTUACAO = re.compile(r"[^\w\s]", flags=re.UNICODE)
_ESPACOS = re.compile(r"\s+")


def normalizar(texto: str) -> str:
    if not texto:
        return ""
    sem_acento = unicodedata.normalize("NFKD", texto)
    sem_acento = "".join(c for c in sem_acento if not unicodedata.combining(c))
    limpo = _PONTUACAO.sub(" ", sem_acento.lower())
    return _ESPACOS.sub(" ", limpo).strip()


def similaridade(a: str, b: str) -> float:
    """Razão de similaridade entre 0 e 1 sobre os textos normalizados."""
    na, nb = normalizar(a), normalizar(b)
    if not na or not nb:
        return 0.0
    return SequenceMatcher(None, na, nb).ratio()


def tokens_relevantes(texto: str, tamanho_minimo: int = 3) -> set[str]:
    """Palavras de conteúdo. Descarta partículas curtas (de, e, um, eu) que
    inflariam qualquer medida de sobreposição."""
    return {t for t in normalizar(texto).split() if len(t) >= tamanho_minimo}


def contencao(a: str, b: str, tamanho_minimo: int = 3) -> float:
    """Fração das palavras de conteúdo da MENOR mensagem presentes na maior.

    Complementa `similaridade`: o SequenceMatcher compara os textos inteiros e
    penaliza forte a diferença de comprimento, então perde o caso clássico de
    "cliente reformula a mesma demanda de forma mais curta" — que é exatamente
    o comportamento que queremos pontuar como fricção.
    """
    ta, tb = tokens_relevantes(a, tamanho_minimo), tokens_relevantes(b, tamanho_minimo)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / min(len(ta), len(tb))


def proporcao_maiusculas(texto: str) -> float:
    letras = [c for c in texto if c.isalpha()]
    if not letras:
        return 0.0
    return sum(1 for c in letras if c.isupper()) / len(letras)


def contem_termo(texto_normalizado: str, termo: str) -> bool:
    """Casa termos de 1+ palavras respeitando fronteira de palavra."""
    return re.search(rf"(?<!\w){re.escape(termo)}(?!\w)", texto_normalizado) is not None
