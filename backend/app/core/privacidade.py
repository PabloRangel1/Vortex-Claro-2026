"""Remoção de dados pessoais antes de qualquer texto sair para um serviço externo.

Regra do `demandas.md`: CPF, telefone e afins nunca vão para a IA. O nome do
cliente e o `cliente_id` nem chegam a ser montados no contexto; aqui caem os
dados que o próprio cliente pode ter digitado na conversa.
"""

import re

# Sequências com 6+ dígitos, admitindo separadores (CPF, telefone, cartão,
# código de barras). Valores como "R$ 60,00" e "dia 15" ficam intactos.
_NUMERO_LONGO = re.compile(r"\+?\d(?:[\d.\-/\s()]*\d){5,}")
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")


def anonimizar(texto: str, nomes: tuple[str, ...] = ()) -> str:
    """`nomes`: partes do nome do cliente, que o bot usa ao cumprimentar
    ("Obrigado, Ana!") e que não podem seguir para fora."""
    texto = _EMAIL.sub("[email]", texto)
    texto = _NUMERO_LONGO.sub("[número]", texto)
    for nome in nomes:
        if len(nome) >= 3:
            texto = re.sub(rf"\b{re.escape(nome)}\b", "[nome]", texto, flags=re.IGNORECASE)
    return texto
