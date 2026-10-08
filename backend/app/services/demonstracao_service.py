"""Conversas simuladas pré-carregadas — o dashboard nunca abre vazio.

Cada roteiro abaixo passa pelo MESMO caminho de uma conversa real: o
orquestrador (identidade, verificação, NLP, fricção, autoatendimento,
handoff), o atendente respondendo, transferindo, encerrando, e o cliente
avaliando. Nada é inserido direto no banco — por isso score, eventos de
fricção, ações e estatísticas ficam coerentes entre si.

As datas vêm do relógio deslocado (`core/relogio.no_passado`): a conversa da
semana passada fica com data da semana passada.

Os quatro clientes da demonstração ao vivo (Ana, Ricardo, Juliana, Carlos)
NÃO ganham atendimento aberto aqui — só histórico encerrado — para o roteiro
da apresentação começar do zero.
"""

from datetime import timedelta

from app.core import relogio
from app.domain.enums import Canal, Setor

APP, WPP = Canal.APP, Canal.WHATSAPP

# Identificadores dos clientes (ver repositories/seed.py)
ANA = {"app": "user_ana", "cpf": "529"}
MARINA = {"app": "user_marina", "wpp": "5511981234501", "cpf": "618"}
PAULO = {"app": "user_paulo", "wpp": "5511981234502", "cpf": "703"}
BEATRIZ = {"app": "user_beatriz", "wpp": "5511981234503", "cpf": "829"}
FERNANDO = {"app": "user_fernando", "wpp": "5511981234504", "cpf": "935"}
CAMILA = {"app": "user_camila", "wpp": "5511981234505", "cpf": "150"}
LUCAS = {"app": "user_lucas", "wpp": "5511981234506", "cpf": "264"}
PATRICIA = {"app": "user_patricia", "wpp": "5511981234507", "cpf": "371"}
RAFAEL = {"app": "user_rafael", "wpp": "5511981234508", "cpf": "482"}

ATENDENTES = ("Marcos Ribeiro", "Aline Torres", "Diego Campos")

# Respostas do modelo para as falas da simulação que SÓ a IA entende (as regras
# não reconhecem). São as mesmas que o Gemini real devolveu nos testes de 05/10;
# fixá-las mantém a simulação determinística e sem gastar cota. Passam pela
# MESMA validação da IA real (`IAService._validar`).
_RESPOSTAS_IA = {
    "minha conta desse mês veio bem mais cara que o normal": {
        "acao_sugerida": "abrir_contestacao", "confirmacao": "indefinido",
    },
    "pode ser lá pelo meio do mês": {
        "acao_sugerida": "nenhuma", "confirmacao": "indefinido", "dia": 15,
    },
}


class _IARoteirizada:
    """Faz o papel do modelo só durante a simulação; fora dela, nada muda."""

    def __init__(self, ia_real) -> None:
        self._ia = ia_real

    async def interpretar(self, *, sessao, texto, intencao, permitidas):
        bruto = _RESPOSTAS_IA.get(texto)
        return None if bruto is None else self._ia._validar(bruto, sessao, permitidas)


class _Roteiro:
    """Atalhos para escrever uma conversa como uma lista de falas."""

    def __init__(self, container) -> None:
        self.o = container.orquestrador
        self.protocolo: str | None = None

    async def cliente(self, quem: dict, canal: Canal, texto: str, pausa: float = 40) -> None:
        identificador = quem["app"] if canal == APP else quem["wpp"]
        r = await self.o.processar_mensagem(canal=canal, identificador=identificador, conteudo=texto)
        self.protocolo = r.protocolo
        relogio.avancar(pausa)

    async def atendente(self, texto: str, quem: str = ATENDENTES[0], pausa: float = 90) -> None:
        await self.o.responder_como_atendente(
            protocolo=self.protocolo, conteudo=texto, atendente=quem
        )
        relogio.avancar(pausa)

    async def transferir(self, setor: Setor, motivo: str) -> None:
        await self.o.transferir(protocolo=self.protocolo, setor=setor, motivo=motivo, por=ATENDENTES[0])
        relogio.avancar(120)

    async def encerrar(self) -> None:
        await self.o.encerrar(self.protocolo)
        relogio.avancar(30)

    async def avaliar(self, nota: int, comentario: str | None = None) -> None:
        await self.o.avaliar(protocolo=self.protocolo, nota=nota, comentario=comentario)


async def _no_passado(container, delta: timedelta, roteiro) -> None:
    with relogio.no_passado(delta):
        await roteiro(_Roteiro(container))


# ---------------------------------------------------------------- histórico


async def _ana_segunda_via(r):  # resolvido pelo bot, avaliado
    await r.cliente(ANA, APP, "Me manda a segunda via da fatura")
    await r.cliente(ANA, APP, "Era só isso, obrigado")
    await r.avaliar(5, "Rápido, nem precisei falar com ninguém")


async def _beatriz_vencimento_por_ia(r):  # só a IA entende "meio do mês"
    await r.cliente(BEATRIZ, APP, "quero mudar meu vencimento")
    await r.cliente(BEATRIZ, APP, "pode ser lá pelo meio do mês")
    await r.cliente(BEATRIZ, APP, "Sim, confirmo")
    await r.cliente(BEATRIZ, APP, "obrigada")
    await r.avaliar(4, "Entendeu o que eu quis dizer")


async def _marina_conta_cara_por_ia(r):  # texto livre que nenhuma regra reconhece
    await r.cliente(MARINA, APP, "minha conta desse mês veio bem mais cara que o normal")
    await r.cliente(MARINA, APP, "manda ver")
    await r.cliente(MARINA, APP, "valeu")
    await r.avaliar(5, "Resolveu sem eu precisar explicar duas vezes")


async def _marina_segunda_via(r):  # segunda via + upgrade de plano
    await r.cliente(MARINA, APP, "preciso do boleto desse mês")
    await r.cliente(MARINA, APP, "quero fazer upgrade do meu plano")
    await r.cliente(MARINA, APP, "Claro Pós 40GB")
    await r.cliente(MARINA, APP, "Sim, confirmo")
    await r.cliente(MARINA, APP, "valeu!")
    await r.avaliar(5)


async def _paulo_sem_internet(r):  # equipamento offline: o bot não resolve
    await r.cliente(PAULO, WPP, "minha internet parou de funcionar")
    await r.cliente(PAULO, WPP, PAULO["cpf"])
    await r.atendente("Olá, Paulo! Vi que seu roteador está sem comunicação. Vou abrir uma visita técnica.")
    await r.cliente(PAULO, WPP, "ok, quando vem o técnico?")
    await r.atendente("A visita ficou agendada e você recebe a confirmação por SMS.")
    await r.encerrar()
    await r.avaliar(3, "Resolveram, mas demorou")


async def _beatriz_contestacao(r):
    await r.cliente(BEATRIZ, APP, "não reconheço uma cobrança de assinatura na fatura")
    await r.cliente(BEATRIZ, APP, "Sim, confirmo")
    await r.cliente(BEATRIZ, APP, "obrigada")
    await r.avaliar(4)


async def _fernando_cancelamento(r):  # cancelamento: vai para humano, e é transferido
    await r.cliente(FERNANDO, APP, "quero cancelar meu plano")
    await r.atendente("Olá, Fernando! Antes de seguir, posso verificar uma condição especial para você?", ATENDENTES[1])
    await r.cliente(FERNANDO, APP, "não, quero cancelar mesmo")
    await r.transferir(Setor.RETENCAO, "Cliente decidido a cancelar")
    await r.atendente("Fernando, aqui é da Retenção. Seu pedido de cancelamento foi registrado.", ATENDENTES[2])
    await r.encerrar()
    await r.avaliar(2, "Queria só cancelar, me fizeram esperar")


async def _camila_upgrade(r):  # já tem o maior plano; troca de canal e pede pessoa
    await r.cliente(CAMILA, APP, "quero fazer upgrade da minha internet")
    await r.cliente(CAMILA, WPP, "quero falar com um atendente")  # verificada pelo App
    await r.atendente("Oi, Camila! Você já está no plano mais rápido. Posso ver um combo com TV para você.", ATENDENTES[1])
    await r.encerrar()
    await r.avaliar(4)


async def _lucas_vencimento(r):  # WhatsApp: verificação + vencimento
    await r.cliente(LUCAS, WPP, "quero mudar a data de vencimento")
    await r.cliente(LUCAS, WPP, LUCAS["cpf"])
    await r.cliente(LUCAS, WPP, "Dia 15")
    await r.cliente(LUCAS, WPP, "Sim, confirmo")
    await r.cliente(LUCAS, WPP, "só isso, obrigado")
    await r.avaliar(5, "Muito prático pelo WhatsApp")


# ------------------------------------------------------- em curso (fila)


async def _beatriz_segunda_via_hoje(r):  # resolvido pelo bot, ainda sem despedida
    await r.cliente(BEATRIZ, APP, "me manda a segunda via")


async def _marina_em_atendimento(r):  # já com atendente
    await r.cliente(MARINA, APP, "minha fatura veio mais alta, não entendi")
    await r.cliente(MARINA, APP, "quero falar com um atendente")
    await r.atendente("Oi, Marina! Já estou olhando sua fatura, só um instante.")


async def _paulo_identidade(r):  # errou o CPF três vezes
    await r.cliente(PAULO, WPP, "preciso da segunda via")
    await r.cliente(PAULO, WPP, "123")
    await r.cliente(PAULO, WPP, "456")
    await r.cliente(PAULO, WPP, "999")


async def _patricia_frustrada(r):  # a jornada do pitch: troca de canal + repetição
    await r.cliente(PATRICIA, APP, "minha fatura veio errada, tem uma cobrança que não reconheço")
    await r.cliente(PATRICIA, APP, "tem uma cobrança na fatura que eu não reconheço", pausa=20)
    await r.cliente(PATRICIA, WPP, "boa tarde, preciso resolver uma cobrança indevida na fatura", pausa=20)
    await r.cliente(PATRICIA, WPP, "já expliquei isso três vezes no aplicativo, isso é um absurdo!", pausa=20)
    await r.cliente(PATRICIA, WPP, "QUERO FALAR COM UM ATENDENTE AGORA", pausa=20)


async def _rafael_internet(r):  # diagnóstico, recusa o reinício, pede pessoa
    await r.cliente(RAFAEL, APP, "minha internet está caindo toda hora")
    await r.cliente(RAFAEL, APP, "Não, obrigado")
    await r.cliente(RAFAEL, APP, "continua lento, quero falar com um atendente")


# --------------------------------------------- volume de rotina (gráficos)
# Demandas simples ao longo dos dias, para as séries diárias terem corpo. Só
# clientes da simulação; tudo passa pelo orquestrador como as demais.

_CLIENTES_ROTINA = [MARINA, PAULO, BEATRIZ, FERNANDO, CAMILA, LUCAS, PATRICIA, RAFAEL]
_NOTAS_ROTINA = [5, 4, 5, 3, 4, 5, 2, 4]


def _rotina(quem: dict, tipo: str, nota: int, atendente: str):
    async def roteiro(r):
        if tipo == "segunda_via":
            await r.cliente(quem, APP, "me manda a segunda via")
            await r.cliente(quem, APP, "obrigado")
        elif tipo == "fatura":
            await r.cliente(quem, WPP, "quando vence minha fatura?")
            await r.cliente(quem, WPP, quem["cpf"])
            await r.cliente(quem, WPP, "valeu")
        else:  # quer falar com uma pessoa
            await r.cliente(quem, APP, "quero falar com um atendente")
            await r.atendente("Olá! Já estou com o seu histórico, vamos resolver.", atendente)
            await r.encerrar()
        await r.avaliar(nota)

    return roteiro


def _volume_rotineiro() -> list:
    tipos = ["segunda_via", "atendente", "fatura", "segunda_via", "atendente", "fatura"]
    roteiros, n = [], 0
    for dia in range(9, 0, -1):
        for hora in (9, 15) if dia % 3 else (9, 13, 17):
            quem = _CLIENTES_ROTINA[n % len(_CLIENTES_ROTINA)]
            roteiros.append((
                timedelta(days=dia, hours=24 - hora),
                _rotina(quem, tipos[n % len(tipos)], _NOTAS_ROTINA[n % 8], ATENDENTES[n % 3]),
            ))
            n += 1
    return roteiros


ROTEIROS = [
    # (quanto tempo atrás, roteiro) — em ordem cronológica, para os protocolos
    # saírem numerados na ordem das datas.
    (timedelta(days=9, hours=3), _ana_segunda_via),
    (timedelta(days=8, hours=2), _beatriz_vencimento_por_ia),
    (timedelta(days=7, hours=5), _marina_segunda_via),
    (timedelta(days=6, hours=2), _paulo_sem_internet),
    (timedelta(days=5, hours=4), _beatriz_contestacao),
    (timedelta(days=4, hours=1), _fernando_cancelamento),
    (timedelta(days=3, hours=2), _marina_conta_cara_por_ia),
    (timedelta(days=2, hours=6), _camila_upgrade),
    (timedelta(days=1, hours=3), _lucas_vencimento),
    (timedelta(hours=2, minutes=10), _beatriz_segunda_via_hoje),
    (timedelta(minutes=48), _marina_em_atendimento),
    (timedelta(minutes=31), _paulo_identidade),
    (timedelta(minutes=17), _patricia_frustrada),
    (timedelta(minutes=6), _rafael_internet),
]


async def tem_demonstracao(container) -> bool:
    """Já há conversa de algum cliente da simulação (os que não são da demo ao vivo)?"""
    from app.repositories.seed import CLIENTES_DEMO_AO_VIVO

    return any(
        a.cliente_id not in CLIENTES_DEMO_AO_VIVO
        for a in await container.atendimentos.listar_todos()
    )


async def semear_demonstracao(container) -> None:
    """Roda os roteiros. Chamado na subida (sem simulação no banco) e a cada reset."""
    # Uma sessão viva (de um teste de 10 minutos atrás) capturaria a conversa
    # "de 9 dias atrás" do mesmo cliente para dentro do protocolo dela.
    await _limpar_sessoes(container)

    # Determinística e sem gastar cota: o modelo real sai de cena durante a
    # simulação, e as falas que só a IA entende usam as respostas fixadas acima.
    ia_original = container.dialogo._ia
    container.dialogo._ia = _IARoteirizada(container.ia)
    try:
        # Em ordem cronológica: os protocolos saem numerados na ordem das datas.
        todos = sorted(ROTEIROS + _volume_rotineiro(), key=lambda item: -item[0].total_seconds())
        for delta, roteiro in todos:
            await _no_passado(container, delta, roteiro)
    finally:
        container.dialogo._ia = ia_original

    # Sessões criadas "no passado" ainda estariam vivas: limpa todas, para cada
    # cliente começar do zero (quem está na fila humana é retomado sozinho).
    await _limpar_sessoes(container)


async def _limpar_sessoes(container) -> None:
    for cliente in await container.clientes.listar():
        await container.sessoes_repo.remover(cliente.cliente_id)
