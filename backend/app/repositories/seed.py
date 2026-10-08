"""Dados fictícios de demonstração — fonte única para memória e PostgreSQL.

TODOS OS DADOS AQUI SÃO FICTÍCIOS. Nomes, CPFs, datas de nascimento, e-mails,
telefones, faturas, códigos de barras e equipamentos foram inventados para
demonstração. Os códigos de barras usam o banco 999, que não existe, os
equipamentos o prefixo EQ-FICT e os e-mails o domínio exemplo.com.br.

Os quatro primeiros clientes são os da demonstração AO VIVO e ficam sem
atendimento aberto. Os demais existem para as simulações pré-carregadas
(`services/demonstracao_service.py`) e para a fila do dashboard não abrir vazia.
"""

from datetime import date, datetime, timedelta, timezone

from app.core.relogio import agora

from app.domain.enums import CategoriaPlano, Canal, StatusConexao, StatusFatura
from app.domain.models import Cliente, Equipamento, Fatura, ItemFatura, Plano


def _cliente(cpf, nome, plano, plano_id, desde, venc, nascimento, email, cidade, app, wpp):
    return Cliente(
        cliente_id=cpf,
        nome=nome,
        cpf_mascarado=f"***.{cpf[3:6]}.{cpf[6:9]}-**",
        plano=plano,
        cliente_desde=desde,
        identificadores={Canal.APP: app, Canal.WHATSAPP: wpp},
        plano_id=plano_id,
        dia_vencimento=venc,
        data_nascimento=nascimento,
        email=email,
        cidade=cidade,
    )


# ======================================================================
# Clientes
# ======================================================================

CLIENTES_SEED = [
    # --- demonstração ao vivo -------------------------------------------
    _cliente("52941288900", "Ana Beatriz Souza", "Claro Pós 40GB + Claro tv+", "movel_pos_40",
             "Mar 2019", 5, date(1990, 3, 14), "ana.souza@exemplo.com.br", "São Paulo · SP",
             "user_ana", "5511998877321"),
    _cliente("38177100402", "Ricardo Mendes Lima", "Claro Fibra 500MB", "fibra_500",
             "Jan 2022", 10, date(1985, 11, 2), "ricardo.lima@exemplo.com.br", "Campinas · SP",
             "user_ricardo", "5511997712298"),
    _cliente("44120955610", "Juliana Ferraz", "Claro Controle 25GB", "movel_controle_25",
             "Set 2023", 5, date(1998, 7, 21), "juliana.ferraz@exemplo.com.br",
             "Rio de Janeiro · RJ", "user_juliana", "5511992095566"),
    _cliente("29088413055", "Carlos Eduardo Nunes", "Claro Pós Família 80GB", "movel_familia_80",
             "Ago 2016", 20, date(1972, 1, 30), "carlos.nunes@exemplo.com.br",
             "Belo Horizonte · MG", "user_carlos", "5511988413055"),
    # --- simulações pré-carregadas --------------------------------------
    _cliente("61835022714", "Marina Costa Alves", "Claro Controle 25GB", "movel_controle_25",
             "Fev 2021", 10, date(1994, 6, 8), "marina.alves@exemplo.com.br", "Curitiba · PR",
             "user_marina", "5511981234501"),
    _cliente("70392481166", "Paulo Henrique Rocha", "Claro Fibra 500MB", "fibra_500",
             "Out 2020", 15, date(1979, 9, 17), "paulo.rocha@exemplo.com.br", "Salvador · BA",
             "user_paulo", "5511981234502"),
    _cliente("82947150390", "Beatriz Lima Santos", "Claro Pós 40GB", "movel_pos_40",
             "Mai 2018", 5, date(1988, 12, 3), "beatriz.santos@exemplo.com.br",
             "Porto Alegre · RS", "user_beatriz", "5511981234503"),
    _cliente("93518264027", "Fernando Oliveira Dias", "Claro Pós Família 80GB", "movel_familia_80",
             "Jul 2015", 20, date(1968, 4, 25), "fernando.dias@exemplo.com.br", "Recife · PE",
             "user_fernando", "5511981234504"),
    _cliente("15029374858", "Camila Rodrigues Melo", "Claro Fibra 1GB", "fibra_1g",
             "Nov 2023", 10, date(1996, 2, 11), "camila.melo@exemplo.com.br",
             "Florianópolis · SC", "user_camila", "5511981234505"),
    _cliente("26475190832", "Lucas Martins Ferreira", "Claro Controle 25GB", "movel_controle_25",
             "Abr 2024", 5, date(2001, 10, 29), "lucas.ferreira@exemplo.com.br", "Goiânia · GO",
             "user_lucas", "5511981234506"),
    _cliente("37160482591", "Patrícia Gomes Ribeiro", "Claro Pós 40GB", "movel_pos_40",
             "Jun 2017", 15, date(1983, 8, 19), "patricia.ribeiro@exemplo.com.br",
             "Fortaleza · CE", "user_patricia", "5511981234507"),
    _cliente("48293716045", "Rafael Souza Prado", "Claro Fibra 500MB", "fibra_500",
             "Dez 2022", 20, date(1992, 5, 6), "rafael.prado@exemplo.com.br", "Brasília · DF",
             "user_rafael", "5511981234508"),
]

# Os que a simulação pré-carregada NÃO toca — reservados para a demo ao vivo.
CLIENTES_DEMO_AO_VIVO = {"52941288900", "38177100402", "44120955610", "29088413055"}


# ======================================================================
# Dados operacionais fictícios
#
# Construídos por FUNÇÕES, não constantes de módulo: o autoatendimento altera
# faturas, equipamentos e planos de clientes. Se o seed reaproveitasse os mesmos
# objetos, um POST /reset re-inseriria as versões já modificadas.
# ======================================================================


def _linha_digitavel(cliente_id: str, valor_centavos: int) -> str:
    """Linha digitável FICTÍCIA. Banco 999 não existe — não é pagável."""
    return (
        f"99990.{cliente_id[:5]} {cliente_id[5:10]}.{cliente_id[10:]}00000 "
        f"00000.000000 9 0000{valor_centavos:010d}"
    )


def planos() -> list[Plano]:
    return [
        Plano(id="movel_controle_25", nome="Claro Controle 25GB",
              categoria=CategoriaPlano.MOVEL, preco_centavos=6490,
              franquia="25GB", linhas_incluidas=1),
        Plano(id="movel_pos_40", nome="Claro Pós 40GB",
              categoria=CategoriaPlano.MOVEL, preco_centavos=12990,
              franquia="40GB", linhas_incluidas=1),
        Plano(id="movel_familia_80", nome="Claro Pós Família 80GB",
              categoria=CategoriaPlano.MOVEL, preco_centavos=21990,
              franquia="80GB", linhas_incluidas=3),
        Plano(id="movel_familia_150", nome="Claro Pós Família 150GB",
              categoria=CategoriaPlano.MOVEL, preco_centavos=29990,
              franquia="150GB", linhas_incluidas=5),
        Plano(id="fibra_500", nome="Claro Fibra 500MB",
              categoria=CategoriaPlano.FIBRA, preco_centavos=9990,
              franquia="500 Mbps", linhas_incluidas=0),
        Plano(id="fibra_1g", nome="Claro Fibra 1GB",
              categoria=CategoriaPlano.FIBRA, preco_centavos=14990,
              franquia="1 Gbps", linhas_incluidas=0),
    ]


def _proximo_vencimento(dia: int, hoje: date) -> date:
    """Próxima data com o dia de vencimento do cliente, a partir de hoje.

    As datas eram fixas (out/2026) e, com o passar dos dias, todas as faturas
    "abertas" ficavam vencidas sem ninguém perceber.
    """
    if hoje.day <= dia:
        return hoje.replace(day=dia)
    proximo_mes = (hoje.replace(day=1) + timedelta(days=32)).replace(day=1)
    return proximo_mes.replace(day=dia)


def faturas() -> list[Fatura]:
    hoje = agora().astimezone(timezone(timedelta(hours=-3))).date()
    dias = {c.cliente_id: c.dia_vencimento for c in CLIENTES_SEED}

    def fatura(cliente_id, _venc_fixo, status, itens):
        valor = sum(i.valor_centavos for i in itens)
        venc = _proximo_vencimento(dias[cliente_id], hoje)
        return Fatura(
            cliente_id=cliente_id,
            referencia=f"{venc.month:02d}/{venc.year}",
            valor_centavos=valor,
            vencimento=venc,
            codigo_barras=_linha_digitavel(cliente_id, valor),
            status=status,
            itens=itens,
        )

    def item(descricao, centavos):
        return ItemFatura(descricao=descricao, valor_centavos=centavos)

    A, P = StatusFatura.ABERTA, StatusFatura.PAGA
    return [
        # Ana: a cobrança de R$ 60,00 que ela não reconhece — mesma narrativa da demo.
        fatura("52941288900", date(2026, 10, 5), A,
               [item("Claro Pós 40GB", 12990), item("Serviço digital avulso", 6000)]),
        fatura("38177100402", date(2026, 10, 10), A, [item("Claro Fibra 500MB", 9990)]),
        fatura("44120955610", date(2026, 10, 5), A, [item("Claro Controle 25GB", 6490)]),
        # Carlos já pagou: caminho de falha legível para a segunda via.
        fatura("29088413055", date(2026, 10, 20), P, [item("Claro Pós Família 80GB", 21990)]),
        fatura("61835022714", date(2026, 10, 10), A, [item("Claro Controle 25GB", 6490)]),
        fatura("70392481166", date(2026, 10, 15), A, [item("Claro Fibra 500MB", 9990)]),
        fatura("82947150390", date(2026, 10, 5), A,
               [item("Claro Pós 40GB", 12990), item("Assinatura de conteúdo", 3500)]),
        fatura("93518264027", date(2026, 10, 20), P, [item("Claro Pós Família 80GB", 21990)]),
        fatura("15029374858", date(2026, 10, 10), A, [item("Claro Fibra 1GB", 14990)]),
        fatura("26475190832", date(2026, 10, 5), A, [item("Claro Controle 25GB", 6490)]),
        fatura("37160482591", date(2026, 10, 15), A,
               [item("Claro Pós 40GB", 12990), item("Serviço digital avulso", 6000)]),
        fatura("48293716045", date(2026, 10, 20), A, [item("Claro Fibra 500MB", 9990)]),
    ]


def equipamentos() -> list[Equipamento]:
    # Só quem tem fibra tem equipamento. Os demais caem na falha "sem equipamento".
    def eq(id_, cliente_id, modelo, status, dia):
        return Equipamento(
            id=id_, cliente_id=cliente_id, tipo="roteador", modelo=modelo,
            status_conexao=status,
            ultima_reinicializacao=datetime(2026, 9, dia, 22, 40, tzinfo=timezone.utc),
        )

    return [
        eq("EQ-FICT-0417", "38177100402", "Wi-Fi 6 FICT-AX3000", StatusConexao.INSTAVEL, 11),
        eq("EQ-FICT-0533", "70392481166", "Wi-Fi 5 FICT-AC1200", StatusConexao.OFFLINE, 2),
        eq("EQ-FICT-0612", "15029374858", "Wi-Fi 6 FICT-AX5400", StatusConexao.ONLINE, 20),
        eq("EQ-FICT-0707", "48293716045", "Wi-Fi 6 FICT-AX3000", StatusConexao.INSTAVEL, 8),
    ]
