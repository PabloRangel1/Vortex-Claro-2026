"""Demonstração da Fase 2 — conversa guiada entre canais.

NÃO é teste automatizado (fora de escopo no demandas.md). Cada mensagem passa
pela sessão real, exatamente como o orquestrador fará na Fase 4:

    SessaoService.obter_ou_criar(cliente, canal)  ->  DialogoService.conduzir(...)

Como a sessão é única por cliente, uma pergunta feita no App pode ser
respondida no WhatsApp.

    cd backend
    $env:PYTHONIOENCODING="utf-8"
    .venv\\Scripts\\python.exe demo_conversa_guiada.py
"""

import asyncio
import sys

from app.config import get_settings
from app.dependencies import Container
from app.domain.enums import Canal

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ANA, RICARDO, JULIANA, CARLOS = "52941288900", "38177100402", "44120955610", "29088413055"
ROTULO = {Canal.APP: "APP     ", Canal.WHATSAPP: "WHATSAPP"}


def titulo(texto: str) -> None:
    print(f"\n{'─' * 78}\n  {texto}\n{'─' * 78}")


async def main() -> None:
    c = Container(get_settings())

    async def falar(cliente: str, canal: Canal, texto: str):
        sessao = (await c.sessoes.obter_ou_criar(cliente, canal)).sessao
        intencao = c.nlp.classificar(texto).intencao
        turno = await c.dialogo.conduzir(sessao=sessao, texto=texto, intencao=intencao)

        print(f"\n  [{ROTULO[canal]}] cliente: {texto}")
        if not turno.tratado:
            print("             bot: (fora do autoatendimento — segue a resposta comum)")
        else:
            print(f"             bot: {turno.resposta}")
        estado = str(turno.etapa)
        if turno.acao_pendente:
            estado += f" · {turno.acao_pendente}"
        print(f"             estado: {estado}" + ("  ⚠ handoff" if turno.requer_handoff else ""))
        return turno

    # ------------------------------------------------------------ 1
    titulo("1 · JULIANA — pede no App, escolhe e confirma pelo WhatsApp")
    await falar(JULIANA, Canal.APP, "Quero mudar meu vencimento")
    await falar(JULIANA, Canal.WHATSAPP, "dia 7")
    await falar(JULIANA, Canal.WHATSAPP, "Dia 15")
    await falar(JULIANA, Canal.APP, "Sim")
    print(f"\n  → cadastro: vencimento dia {(await c.clientes.obter(JULIANA)).dia_vencimento}")

    # ------------------------------------------------------------ 2
    titulo("2 · JULIANA — dado já na primeira frase, muda de ideia, confirma")
    await falar(JULIANA, Canal.WHATSAPP, "quero trocar o vencimento para o dia 10")
    await falar(JULIANA, Canal.WHATSAPP, "não, prefiro o dia 20")
    await falar(JULIANA, Canal.APP, "confirmo")
    print(f"\n  → cadastro: vencimento dia {(await c.clientes.obter(JULIANA)).dia_vencimento}")

    # ------------------------------------------------------------ 3
    titulo("3 · RICARDO — diagnóstico no WhatsApp emenda reinício; confirma no App")
    await falar(RICARDO, Canal.WHATSAPP, "minha internet está caindo toda hora")
    await falar(RICARDO, Canal.APP, "pode sim")
    eq = await c.operacao.obter_equipamento(RICARDO)
    print(f"\n  → roteador: {eq.status_conexao}")

    # ------------------------------------------------------------ 4
    titulo("4 · CARLOS — upgrade com uma opção só; recusa no WhatsApp")
    await falar(CARLOS, Canal.APP, "quero fazer upgrade do meu plano")
    await falar(CARLOS, Canal.WHATSAPP, "não")
    print(f"\n  → cadastro: {(await c.clientes.obter(CARLOS)).plano} (nada mudou)")

    # ------------------------------------------------------------ 5
    titulo("5 · ANA — contestação, resposta confusa, muda de assunto")
    await falar(ANA, Canal.APP, "Não reconheço essa cobrança de R$ 60 na minha fatura")
    await falar(ANA, Canal.WHATSAPP, "hmm")
    await falar(ANA, Canal.WHATSAPP, "me manda a segunda via")
    abertas = await c.operacao.listar_solicitacoes(ANA)
    print(f"\n  → contestações abertas: {len(abertas)} (esperado: 0, ela não confirmou)")

    # ------------------------------------------------------------ 6
    titulo("6 · ANA — 'quero cancelar' no meio do fluxo cancela a OPERAÇÃO")
    await falar(ANA, Canal.APP, "Não reconheço essa cobrança de R$ 60")
    await falar(ANA, Canal.APP, "quero cancelar")

    # ------------------------------------------------------------ 7
    titulo("7 · ANA — limite de tentativas: não prende o cliente")
    await falar(ANA, Canal.APP, "Não reconheço essa cobrança de R$ 60")
    await falar(ANA, Canal.APP, "como assim")
    await falar(ANA, Canal.APP, "???")
    await falar(ANA, Canal.APP, "sei lá")

    # ------------------------------------------------------------ 8
    titulo("8 · ANA — agora confirma, pelo outro canal")
    await falar(ANA, Canal.WHATSAPP, "Não reconheço essa cobrança de R$ 60")
    await falar(ANA, Canal.APP, "sim, pode abrir")
    await falar(ANA, Canal.WHATSAPP, "quero cancelar meu plano")

    print()


if __name__ == "__main__":
    asyncio.run(main())
