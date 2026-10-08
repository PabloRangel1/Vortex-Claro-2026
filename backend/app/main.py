"""Ponto de entrada da API.

    uvicorn app.main:app --reload
    http://localhost:8000/docs
"""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.dependencies import encerrar_persistencia, iniciar_persistencia
from app.domain.exceptions import (
    AtendimentoEncerrado,
    AtendimentoNaoEncontrado,
    ClienteNaoIdentificado,
    VortexError,
)
from app.routers import canais, dashboard, health

DESCRICAO = """
Camada de orquestração inteligente de canais de atendimento — **Challenge FIAP + Claro 2026**.

Recebe mensagens de múltiplos canais (App Claro, WhatsApp), classifica a intenção,
monitora o **Score de Fricção**, preserva o contexto entre canais e dispara o
**handoff** para atendimento humano levando o histórico completo.

**Persistência:** PostgreSQL quando `DATABASE_URL` está definida; em memória
caso contrário. Veja `GET /health`.
"""


@asynccontextmanager
async def lifespan(_: FastAPI):
    await iniciar_persistencia(get_settings())
    yield
    await encerrar_persistencia()


def criar_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        description=DESCRICAO,
        version=settings.versao,
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Exceções de domínio -> HTTP. Os services nunca conhecem status codes.
    @app.exception_handler(ClienteNaoIdentificado)
    async def _cliente_nao_identificado(_: Request, exc: ClienteNaoIdentificado):
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"erro": "cliente_nao_identificado", "detalhe": exc.mensagem},
        )

    @app.exception_handler(AtendimentoNaoEncontrado)
    async def _atendimento_nao_encontrado(_: Request, exc: AtendimentoNaoEncontrado):
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"erro": "atendimento_nao_encontrado", "detalhe": exc.mensagem},
        )

    @app.exception_handler(AtendimentoEncerrado)
    async def _atendimento_encerrado(_: Request, exc: AtendimentoEncerrado):
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"erro": "atendimento_encerrado", "detalhe": exc.mensagem},
        )

    @app.exception_handler(VortexError)
    async def _erro_generico(_: Request, exc: VortexError):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"erro": "erro_de_negocio", "detalhe": exc.mensagem},
        )

    app.include_router(health.router)
    app.include_router(canais.router)
    app.include_router(dashboard.router)

    montar_frontend(app)
    return app


# Vortex/backend/app/main.py -> Vortex/frontend/dist
DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"


def montar_frontend(app: FastAPI) -> None:
    """Serve o frontend compilado na mesma origem da API.

    Evita depender de um segundo servidor (Vite) e do proxy — tudo responde na
    porta 8000. Registrado DEPOIS dos routers, então as rotas da API têm
    precedência e o catch-all só recebe o que sobrou.
    """
    if not DIST.is_dir():
        return  # sem build ainda: a API funciona normalmente

    assets = DIST / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    raiz = DIST.resolve()

    @app.get("/{caminho:path}", include_in_schema=False)
    async def spa(caminho: str):
        # resolve() ANTES de comparar: `is_relative_to` é só textual, e
        # "dist/../../backend/.env" passaria por ele servindo o .env inteiro.
        arquivo = (raiz / caminho).resolve()
        # Arquivo real (favicon, etc.) é servido; qualquer outra rota devolve o
        # index.html para o React Router resolver no cliente (/sim/app, /sim/whatsapp).
        if caminho and arquivo.is_relative_to(raiz) and arquivo.is_file():
            return FileResponse(arquivo)
        return FileResponse(raiz / "index.html")


app = criar_app()
