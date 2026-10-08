"""Referência pública do cliente — o CPF nunca sai pela API.

O `cliente_id` interno é o CPF. Ele continua sendo a chave no banco, mas tudo
o que sai para o navegador usa uma referência opaca: um HMAC do CPF com uma
chave do servidor. É estável (a mesma referência sempre aponta para o mesmo
cliente) e não dá para voltar dela ao CPF sem a chave.

Em produção, defina CHAVE_REFERENCIA no ambiente.
"""

import hashlib
import hmac

from app.config import get_settings


def referencia(cliente_id: str) -> str:
    chave = get_settings().chave_referencia.encode()
    return "c_" + hmac.new(chave, cliente_id.encode(), hashlib.sha256).hexdigest()[:16]
