"""Demonstração da Fase 1 do autoatendimento.

NÃO é teste automatizado — o demandas.md deixa testes novos fora desta etapa.
É um roteiro legível que exercita o AutoatendimentoService em processo, sem API
e sem orquestrador (que só é ligado na Fase 4), percorrendo as 8 ações do
catálogo com os 4 clientes fictícios.

    cd backend
    $env:PYTHONIOENCODING="utf-8"
    .venv\\Scripts\\python.exe demo_autoatendimento.py
"""

import asyncio
import sys

from app.config import get_settings
from app.core.protocolo import gerar_protocolo
from app.dependencies import Container
from app.domain.enums import AcaoAutoatendimento as A
from app.domain.enums import StatusAcao

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ANA, RICARDO, JULIANA, CARLOS = "52941288900", "38177100402", "44120955610", "29088413055"

MARCA = {
    StatusAcao.SUCESSO: "✔ sucesso ",
    StatusAcao.FALHA: "✖ falha   ",
    StatusAcao.AGUARDANDO_CONFIRMACAO: "… aguardando",
}


def titulo(texto: str) -> None:
    print(f"\n{'─' * 78}\n  {texto}\n{'─' * 78}")


def mostrar(rotulo: str, r) -> None:
    print(f"\n  {rotulo}")
    print(f"    {MARCA[r.status]} · {r.codigo}")
    print(f"    “{r.mensagem}”")
    if r.solicitacao:
        print(f"    solicitação {r.solicitacao.protocolo} · {r.solicitacao.status}")
    if r.requer_handoff:
        print("    ⚠ requer handoff humano")


async def main() -> None:
    c = Container(get_settings())
    svc = c.autoatendimento

    # Um protocolo de atendimento por cliente, como se cada um tivesse aberto conversa.
    protocolos = {cid: gerar_protocolo() for cid in (ANA, RICARDO, JULIANA, CARLOS)}

    async def run(cliente, acao, parametros=None, confirmado=False):
        return await svc.executar(
            protocolo=protocolos[cliente], cliente_id=cliente,
            acao=acao, parametros=parametros, confirmado=confirmado,
        )

    # ------------------------------------------------------------------ Ana
    titulo("ANA · Pós 40GB · fatura R$ 189,90 com cobrança contestável")

    mostrar("Segunda via", await run(ANA, A.GERAR_SEGUNDA_VIA))
    mostrar("Diagnóstico (Ana só tem linha móvel)", await run(ANA, A.DIAGNOSTICAR_CONEXAO))

    desc = {"descricao": "Não reconheço o serviço digital avulso de R$ 60,00"}
    mostrar("Contestação SEM confirmar", await run(ANA, A.ABRIR_CONTESTACAO, desc))
    solicitacoes = await c.operacao.listar_solicitacoes(ANA)
    print(f"    → solicitações gravadas até aqui: {len(solicitacoes)}  (esperado: 0)")

    mostrar("Contestação CONFIRMADA", await run(ANA, A.ABRIR_CONTESTACAO, desc, confirmado=True))
    mostrar("Contestação de novo (duplicada)",
            await run(ANA, A.ABRIR_CONTESTACAO, desc, confirmado=True))

    # -------------------------------------------------------------- Ricardo
    titulo("RICARDO · Fibra 500MB · roteador instável")

    mostrar("Diagnóstico", await run(RICARDO, A.DIAGNOSTICAR_CONEXAO))
    mostrar("Reinício SEM confirmar", await run(RICARDO, A.REINICIAR_EQUIPAMENTO))
    mostrar("Reinício CONFIRMADO", await run(RICARDO, A.REINICIAR_EQUIPAMENTO, confirmado=True))
    mostrar("Diagnóstico depois do reinício", await run(RICARDO, A.DIAGNOSTICAR_CONEXAO))

    # -------------------------------------------------------------- Juliana
    titulo("JULIANA · Controle 25GB · vencimento dia 5")

    mostrar("Vencimento → dia 7 (fora do permitido)",
            await run(JULIANA, A.ALTERAR_VENCIMENTO, {"dia": 7}))
    mostrar("Vencimento → dia 5 (igual ao atual)",
            await run(JULIANA, A.ALTERAR_VENCIMENTO, {"dia": 5}))
    mostrar("Vencimento → dia 15 SEM confirmar",
            await run(JULIANA, A.ALTERAR_VENCIMENTO, {"dia": 15}))
    juliana = await c.clientes.obter(JULIANA)
    print(f"    → vencimento no cadastro: dia {juliana.dia_vencimento}  (esperado: 5, nada mudou)")

    mostrar("Vencimento → dia 15 CONFIRMADO",
            await run(JULIANA, A.ALTERAR_VENCIMENTO, {"dia": 15}, confirmado=True))
    juliana = await c.clientes.obter(JULIANA)
    print(f"    → vencimento no cadastro: dia {juliana.dia_vencimento}  (esperado: 15)")

    # --------------------------------------------------------------- Carlos
    titulo("CARLOS · Pós Família 80GB · fatura já paga")

    mostrar("Segunda via (fatura paga)", await run(CARLOS, A.GERAR_SEGUNDA_VIA))

    r = await run(CARLOS, A.LISTAR_PLANOS)
    mostrar("Listar planos", r)
    for p in r.dados["opcoes"]:
        print(f"      · {p['nome']} — {p['franquia']}, {p['linhas_incluidas']} linhas")

    mostrar("Upgrade para Controle 25GB (é downgrade)",
            await run(CARLOS, A.CONFIRMAR_UPGRADE, {"plano_id": "movel_controle_25"}))
    mostrar("Upgrade para Fibra 1GB (outra categoria)",
            await run(CARLOS, A.CONFIRMAR_UPGRADE, {"plano_id": "fibra_1g"}))
    mostrar("Upgrade para Família 150GB CONFIRMADO",
            await run(CARLOS, A.CONFIRMAR_UPGRADE, {"plano_id": "movel_familia_150"},
                      confirmado=True))
    carlos = await c.clientes.obter(CARLOS)
    print(f"    → plano no cadastro: {carlos.plano}  ({carlos.plano_id})")

    # ------------------------------------------------------- falhas de catálogo
    titulo("FALHAS DE CATÁLOGO · o que não está na lista não executa")

    mostrar("Ação inexistente (ex.: sugestão inválida de uma IA)",
            await run(ANA, "cancelar_contrato"))
    mostrar("Parâmetro obrigatório ausente", await run(JULIANA, A.ALTERAR_VENCIMENTO))
    mostrar("Encaminhar para humano", await run(ANA, A.ENCAMINHAR_HUMANO,
                                                {"motivo": "cliente pediu atendente"}))

    # ------------------------------------------------------------- histórico
    titulo("HISTÓRICO DO ATENDIMENTO DA ANA · eventos tipo=\"acao\"")

    mensagens = await c.conversas.listar_mensagens(protocolos[ANA])
    acoes = [m for m in mensagens if m.metadados.get("tipo") == "acao"]
    for m in acoes:
        md = m.metadados
        print(f"  {md['status']:<8} {md['acao'] or '— fora do catálogo':<22} {md['codigo']}"
              + (f"  [{md['solicitacao']}]" if md["solicitacao"] else ""))

    print(f"\n  {len(acoes)} eventos registrados. O pedido de contestação SEM "
          "confirmação não aparece: nada aconteceu, então nada foi gravado.\n")


if __name__ == "__main__":
    asyncio.run(main())
