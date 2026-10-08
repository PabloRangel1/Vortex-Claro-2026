import os

# Os testes rodam SEMPRE em memória, mesmo com DATABASE_URL no .env: variável
# de ambiente tem precedência sobre o arquivo. Precisa vir antes de importar o app.
os.environ["DATABASE_URL"] = ""
# Idem para a IA: os testes nunca chamam a API do Gemini.
os.environ["GEMINI_API_KEY"] = ""
# E o /reset fica no comportamento de desenvolvimento (aberto, sem token).
os.environ["ADMIN_TOKEN"] = ""
os.environ["AMBIENTE"] = "desenvolvimento"
# Cada teste parte da base limpa, sem as conversas simuladas da demonstração.
os.environ["SEMEAR_DEMONSTRACAO"] = "false"

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.config import Settings
from app.dependencies import resetar_container
from app.main import app
from app.services.friccao_service import FriccaoService
from app.services.nlp_service import NLPService

# Identificadores da base semeada (app / whatsapp) para a mesma pessoa
ANA_APP = "user_ana"
ANA_WHATSAPP = "5511998877321"
RICARDO_APP = "user_ricardo"


@pytest.fixture(autouse=True)
def estado_limpo():
    """Cada teste começa com store e sequência de protocolo zerados."""
    resetar_container()
    yield
    resetar_container()


@pytest.fixture
def settings() -> Settings:
    return Settings()


@pytest.fixture
def nlp(settings: Settings) -> NLPService:
    return NLPService(settings)


@pytest.fixture
def friccao(settings: Settings) -> FriccaoService:
    return FriccaoService(settings)


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def enviar_app(client: AsyncClient, mensagem: str, usuario_id: str = ANA_APP):
    return await client.post("/channels/app", json={"usuario_id": usuario_id, "mensagem": mensagem})


async def enviar_whatsapp(client: AsyncClient, mensagem: str, telefone: str = ANA_WHATSAPP):
    return await client.post(
        "/channels/whatsapp", json={"telefone": telefone, "mensagem": mensagem}
    )
