"""Chat interativo para testar o autoatendimento à mão (Fases 1 e 2).

Enquanto o orquestrador não está ligado (Fase 4), este é o jeito de conversar
com o sistema digitando as próprias frases. Cada mensagem passa pela sessão
real, igual ao que a API fará depois.

    cd backend
    $env:PYTHONIOENCODING="utf-8"
    .venv\\Scripts\\python.exe chat.py

Comandos: /canal  /cliente  /estado  /dados  /reset  /ajuda  /sair
"""

import asyncio
import sys

from app.config import get_settings
from app.dependencies import Container
from app.domain.enums import Canal

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

CLIENTES = {
    "1": ("52941288900", "Ana Beatriz Souza"),
    "2": ("38177100402", "Ricardo Mendes Lima"),
    "3": ("44120955610", "Juliana Ferraz"),
    "4": ("29088413055", "Carlos Eduardo Nunes"),
}

AJUDA = """
  /canal            alterna entre App Claro e WhatsApp (a conversa continua)
  /cliente          troca de cliente
  /estado           mostra a ação pendente da sessão
  /dados            mostra fatura, plano, vencimento e solicitações do cliente
  /reset            devolve tudo ao estado inicial
  /ajuda            esta lista
  /sair             encerra

  Sugestões para experimentar:
    quero mudar meu vencimento          minha internet está caindo
    me manda a segunda via              quero fazer upgrade do meu plano
    não reconheço essa cobrança         quero cancelar meu plano
"""


class Chat:
    def __init__(self) -> None:
        self.c = Container(get_settings())
        self.cliente_id, self.nome = CLIENTES["1"]
        self.canal = Canal.APP

    @property
    def rotulo(self) -> str:
        return "App Claro" if self.canal == Canal.APP else "WhatsApp"

    async def enviar(self, texto: str) -> None:
        sessao = (await self.c.sessoes.obter_ou_criar(self.cliente_id, self.canal)).sessao
        intencao = self.c.nlp.classificar(texto).intencao
        turno = await self.c.dialogo.conduzir(sessao=sessao, texto=texto, intencao=intencao)

        if not turno.tratado:
            print("  bot: (não é autoatendimento — aqui o bot daria a resposta comum)")
            print(f"       intenção detectada: {intencao}")
        else:
            print(f"  bot: {turno.resposta}")
        if turno.acao_pendente:
            print(f"       ⏳ aguardando: {turno.etapa} · {turno.acao_pendente}")
        if turno.requer_handoff:
            print("       ⚠ este caso pediria handoff humano")

    async def estado(self) -> None:
        sessao = await self.c.sessoes_repo.obter(self.cliente_id)
        if sessao is None or not sessao.acao_pendente:
            print("  nenhuma ação pendente")
            return
        print(f"  protocolo ......: {sessao.protocolo}")
        print(f"  etapa ..........: {sessao.etapa_fluxo}")
        print(f"  ação pendente ..: {sessao.acao_pendente}")
        print(f"  dados ..........: {sessao.dados_pendentes.get('parametros', {})}")
        print(f"  tentativas .....: {sessao.tentativas_etapa}")

    async def dados(self) -> None:
        cliente = await self.c.clientes.obter(self.cliente_id)
        fatura = await self.c.operacao.obter_fatura_atual(self.cliente_id)
        equip = await self.c.operacao.obter_equipamento(self.cliente_id)
        sols = await self.c.operacao.listar_solicitacoes(self.cliente_id)

        print(f"  plano ..........: {cliente.plano}")
        print(f"  vencimento .....: dia {cliente.dia_vencimento}")
        if fatura:
            print(f"  fatura .........: {fatura.referencia} · "
                  f"R$ {fatura.valor_centavos / 100:.2f} · {fatura.status}")
        print(f"  equipamento ....: {equip.status_conexao if equip else '— não possui'}")
        print(f"  solicitações ...: {len(sols)}")
        for s in sols:
            print(f"     {s.protocolo} · {s.tipo} · {s.status}")

    def trocar_cliente(self) -> None:
        for chave, (_, nome) in CLIENTES.items():
            print(f"  {chave}) {nome}")
        escolha = input("  cliente: ").strip()
        if escolha in CLIENTES:
            self.cliente_id, self.nome = CLIENTES[escolha]
            print(f"  → agora você é {self.nome}")
        else:
            print("  opção inválida")


async def main() -> None:
    chat = Chat()
    print("\n  VORTEX · chat de autoatendimento (dados fictícios)")
    print(AJUDA)

    while True:
        try:
            texto = input(f"\n[{chat.rotulo}] {chat.nome.split()[0]}: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not texto:
            continue

        if texto == "/sair":
            break
        elif texto == "/ajuda":
            print(AJUDA)
        elif texto == "/canal":
            chat.canal = Canal.WHATSAPP if chat.canal == Canal.APP else Canal.APP
            print(f"  → agora no {chat.rotulo}. A conversa continua de onde parou.")
        elif texto == "/cliente":
            chat.trocar_cliente()
        elif texto == "/estado":
            await chat.estado()
        elif texto == "/dados":
            await chat.dados()
        elif texto == "/reset":
            await chat.c.resetar()
            print("  → tudo de volta ao estado inicial")
        else:
            await chat.enviar(texto)

    print("\n  até logo\n")


if __name__ == "__main__":
    asyncio.run(main())
