"""Saúde e introspecção — úteis para a demonstração na banca."""

import secrets

from fastapi import APIRouter, Header, HTTPException, status

from app.core.referencia import referencia
from app.dependencies import ClienteRepoDep, ContainerDep, SettingsDep

router = APIRouter(tags=["Sistema"])


@router.get("/health", summary="Health check")
async def health(settings: SettingsDep, container: ContainerDep) -> dict:
    return {
        "status": "ok",
        "aplicacao": settings.app_name,
        "versao": settings.versao,
        "ambiente": settings.ambiente,
        "persistencia": container.persistencia,
        "ia": settings.gemini_modelo if container.ia.configurada else "desligada",
        "reset_protegido": bool(settings.admin_token),
    }


@router.get("/config", summary="Parâmetros ativos do motor de fricção")
async def config(settings: SettingsDep) -> dict:
    return {
        "limiar_handoff": settings.limiar_handoff,
        "limiar_atencao": settings.limiar_atencao,
        "sessao_ttl_segundos": settings.sessao_ttl_segundos,
        "pesos": {
            "repeticao": settings.peso_repeticao,
            "intencao_repetida": settings.peso_intencao_repetida,
            "pedido_humano": settings.peso_pedido_humano,
            "troca_canal": settings.peso_troca_canal,
            "sentimento_negativo_max": settings.peso_sentimento_max,
            "caixa_alta": settings.peso_caixa_alta,
            "loop_sem_resolucao": settings.peso_loop,
            "impaciencia": settings.peso_impaciencia,
            "decaimento": -settings.peso_decaimento,
        },
    }


@router.get("/clientes", summary="Base de clientes semeada (apoio aos simuladores)")
async def listar_clientes(clientes: ClienteRepoDep, settings: SettingsDep) -> list[dict]:
    """Só o que o simulador precisa para "ser" o cliente — sem CPF."""
    return [
        {
            "cliente_ref": referencia(c.cliente_id),
            "dica_verificacao": c.cliente_id[:3] if settings.simulador_dica_verificacao else None,
            "nome": c.nome,
            "plano": c.plano,
            "identificadores": {str(k): v for k, v in c.identificadores.items()},
        }
        for c in await clientes.listar()
    ]


@router.post("/reset", summary="Apaga tudo e volta aos dados fictícios iniciais (demo)")
async def reset(
    container: ContainerDep,
    settings: SettingsDep,
    x_admin_token: str | None = Header(default=None),
) -> dict:
    """Em produção, sem isso qualquer visitante da URL pública apagaria o banco."""
    if settings.admin_token:
        if not x_admin_token or not secrets.compare_digest(x_admin_token, settings.admin_token):
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Token de administração inválido")
    elif settings.ambiente != "desenvolvimento":
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, detail="Reset desligado: defina ADMIN_TOKEN para usá-lo"
        )
    await container.resetar()
    return {"status": "reiniciado", "persistencia": container.persistencia}
