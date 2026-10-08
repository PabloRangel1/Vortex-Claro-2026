"""Roteiro de demonstração — a jornada completa da Ana, ponta a ponta.

Rode a API primeiro:
    uvicorn app.main:app --reload

Depois:
    python demo.py
"""

import json
import sys
from urllib.request import Request, urlopen

# O console do Windows usa cp1252 por padrão e engasga com → ⇄ ⚡
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = "http://127.0.0.1:8000"


def chamar(metodo: str, rota: str, corpo: dict | None = None) -> dict:
    dados = json.dumps(corpo).encode() if corpo is not None else None
    req = Request(
        f"{BASE}{rota}", data=dados, method=metodo, headers={"Content-Type": "application/json"}
    )
    with urlopen(req) as r:
        return json.loads(r.read())


def turno(titulo: str, resposta: dict) -> None:
    print(f"\n  {titulo}")
    print(f"    intenção .......... {resposta['intencao_rotulo']} ({resposta['confianca']}%)")
    print(
        f"    score ............. {resposta['score_anterior']} → "
        f"{resposta['score_friccao']} ({resposta['delta_score']:+d}) [{resposta['nivel']}]"
    )
    for sinal in resposta["sinais"]:
        print(f"      · {sinal['codigo']} {sinal['peso']:+d} — {sinal['descricao']}")
    if resposta["troca_de_canal"]:
        print("    ⇄ TROCA DE CANAL — contexto preservado no mesmo protocolo")
    if resposta["handoff_acionado"]:
        print("    ⚡ HANDOFF ACIONADO")
    print(f"    latência .......... {resposta['latencia_ms']}ms")


def main() -> None:
    chamar("POST", "/reset")
    print("=" * 74)
    print("  VORTEX — jornada da Ana Beatriz Souza")
    print("=" * 74)

    r = chamar("POST", "/channels/app", {
        "usuario_id": "user_ana",
        "mensagem": "Minha fatura veio R$ 189,90 mas meu plano é R$ 129,90. Tem uma cobrança que eu não reconheço.",
    })
    protocolo = r["protocolo"]
    print(f"\n  Protocolo aberto: {protocolo}")
    turno("[APP CLARO] 1º contato", r)

    turno("[APP CLARO] repetindo a demanda", chamar("POST", "/channels/app", {
        "usuario_id": "user_ana",
        "mensagem": "Tem uma cobrança que eu não reconheço na minha fatura.",
    }))

    turno("[WHATSAPP] cliente troca de canal", chamar("POST", "/channels/whatsapp", {
        "telefone": "5511998877321",
        "mensagem": "Boa tarde, preciso resolver uma cobrança indevida na minha fatura.",
    }))

    turno("[WHATSAPP] insatisfação explícita", chamar("POST", "/channels/whatsapp", {
        "telefone": "5511998877321",
        "mensagem": "Já expliquei isso três vezes no aplicativo, isso é um absurdo!",
    }))

    r = chamar("POST", "/channels/whatsapp", {
        "telefone": "5511998877321",
        "mensagem": "QUERO FALAR COM UM ATENDENTE AGORA",
    })
    turno("[WHATSAPP] pedido de humano (handoff já ativo)", r)
    print(f'\n    bot → "{r["resposta"]}"')
    print(
        "\n  Note: o handoff disparou no turno ANTERIOR, pela frustração detectada.\n"
        "  O cliente não precisou pedir um atendente — o sistema se antecipou."
    )

    fila = chamar("GET", "/dashboard/fila")
    print("\n" + "=" * 74)
    print("  FILA DO ATENDENTE")
    print("=" * 74)
    for item in fila:
        print(
            f"  {item['score_friccao']:>3} [{item['nivel']:<7}] {item['nome']:<22} "
            f"{item['canal_origem']} → {item['canal_atual']:<9} {item['intencao_rotulo']}"
        )

    d = chamar("GET", f"/dashboard/atendimento/{protocolo}")
    print("\n" + "=" * 74)
    print("  PAYLOAD DO PAINEL")
    print("=" * 74)
    print(f"  Protocolo ......... {d['protocolo']}")
    print(f"  Cliente ........... {d['cliente']['nome']} · {d['cliente']['plano']}")
    print(f"  Canal origem ...... {d['canal_origem_rotulo']} → atual: {d['canal_atual_rotulo']}")
    print(f"  Intenção .......... {d['intencao_rotulo']} ({d['confianca']}%)")
    print(f"  Score ............. {d['score_inicial']} → {d['score_friccao']} [{d['nivel']}]")
    print(f"  Trajetória ........ {d['historico_score']}")
    print(f"  Handoff ........... {d['handoff']['motivo']}")
    print(f"  Mensagens ......... {d['total_mensagens']}  |  eventos: {len(d['eventos_friccao'])}")

    print("\n  Histórico consolidado (o atendente não precisa pedir nada de novo):")
    for m in d["mensagens"]:
        canal = f"[{m['canal_rotulo']}]" if m["canal_rotulo"] else "[sistema]"
        print(f"    {m['remetente']:<9} {canal:<13} {m['conteudo'][:70]}")

    r = chamar("POST", f"/dashboard/atendimento/{protocolo}/responder", {
        "conteudo": "Olá Ana! Já localizei a cobrança de R$ 60,00 e vou estornar agora.",
        "atendente": "Marcos Ribeiro",
    })
    print(f"\n  Atendente assumiu → score {d['score_friccao']} → {r['score_friccao']} "
          f"· status: {r['status']}")


if __name__ == "__main__":
    main()
