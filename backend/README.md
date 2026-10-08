# Vortex — Backend

Camada de orquestração inteligente de canais de atendimento.
**Challenge FIAP + Claro 2026.**

Recebe mensagens de múltiplos canais (App Claro, WhatsApp), classifica a intenção,
monitora o **Score de Fricção**, preserva o contexto entre canais e dispara o
**handoff** para atendimento humano levando o histórico completo — para o atendente
não precisar pedir que o cliente repita nada.

---

## Como rodar

```bash
python -m venv .venv
.venv/Scripts/activate          # Windows
pip install -e ".[dev]"

uvicorn app.main:app --reload
```

**Banco:** com `DATABASE_URL` no `.env` (modelo em `.env.example`), a API usa o
PostgreSQL do Neon — cria as tabelas e semeia os dados fictícios sozinha na
primeira subida. Sem a variável, roda em memória. `GET /health` informa qual
está ativo.

- Swagger: http://localhost:8000/docs
- Testes: `pytest -q`
- Roteiro de demonstração completo: `python demo.py` (com a API no ar)

---

## Endpoints

| Método | Rota | Descrição |
|---|---|---|
| `POST` | `/channels/app` | Mensagem vinda do App Claro |
| `POST` | `/channels/whatsapp` | Webhook simulado do WhatsApp |
| `GET` | `/dashboard/fila` | Fila de atendimentos aguardando handoff |
| `GET` | `/dashboard/atendimento/{protocolo}` | Contexto consolidado do atendimento |
| `POST` | `/dashboard/atendimento/{protocolo}/responder` | Atendente humano responde |
| `POST` | `/dashboard/atendimento/{protocolo}/encerrar` | Encerra e libera a sessão |
| `GET` | `/health` · `/config` · `/clientes` | Introspecção |
| `POST` | `/reset` | Apaga tudo e volta aos dados fictícios iniciais (apoio à demo) |

### Exemplo

```bash
curl -X POST localhost:8000/channels/app \
  -H "Content-Type: application/json" \
  -d '{"usuario_id":"user_ana","mensagem":"minha fatura veio errada"}'

curl -X POST localhost:8000/channels/whatsapp \
  -H "Content-Type: application/json" \
  -d '{"telefone":"5511998877321","mensagem":"quero falar com um atendente"}'
```

O segundo comando cai **no mesmo protocolo** do primeiro — é a continuidade de contexto.

---

## Arquitetura

```
routers  →  services  →  repositories/base  →  domain
```

A dependência só aponta para dentro. Nenhum service importa de
`repositories/memory/`; todos falam com as interfaces abstratas de
`repositories/base.py`.

**Todos os métodos de repositório são `async`**, mesmo sendo dicionários hoje.
É o que permite trocar por `redis.asyncio` / `motor` / `asyncpg` na fase 2 sem
alterar assinatura nenhuma nos services.

### Base de clientes semeada

| Cliente | `usuario_id` (App) | `telefone` (WhatsApp) |
|---|---|---|
| Ana Beatriz Souza | `user_ana` | `5511998877321` |
| Ricardo Mendes Lima | `user_ricardo` | `5511997712298` |
| Juliana Ferraz | `user_juliana` | `5511992095566` |
| Carlos Eduardo Nunes | `user_carlos` | `5511988413055` |

Os dois identificadores resolvem para o mesmo `cliente_id` canônico (CPF) — é
assim que o sistema sabe que o cliente do App e o do WhatsApp são a mesma pessoa.

---

## Motor de Score de Fricção

Cada turno passa por detectores independentes. Cada um que dispara devolve um
sinal com peso e descrição legível, gravado como evento de auditoria.

| Código | Peso | Dispara quando |
|---|---|---|
| `pedido_humano` | +25 | cliente pede atendente explicitamente |
| `repeticao` | +18 | reenvio literal (≥75% similar) **ou** demanda reformulada (≥70% das palavras de conteúdo já ditas) |
| `troca_canal` | +16 | migrou de canal mantendo a demanda |
| `sentimento_negativo` | +6 a +20 | léxico de insatisfação |
| `intencao_repetida` | +12 | 3+ turnos na mesma intenção sem resolução |
| `loop_sem_resolucao` | +8/turno (teto 24) | mais de 4 turnos com o bot |
| `impaciencia` | +8 | 3 mensagens em menos de 60s |
| `caixa_alta` | +5 | ≥60% em maiúsculas |
| `decaimento` | −12 | atendente humano assume |

Score saturado em `[0, 100]`. **Handoff dispara ao cruzar 70**, uma única vez por
atendimento. Todos os pesos e limiares vivem em `app/config.py` / `.env` — calibre
sem tocar em lógica.

---

## Persistência

Duas implementações para as mesmas interfaces de `app/repositories/base.py`.
Quem escolhe é `app/dependencies.py`, pela presença de `DATABASE_URL`:

| Repositório | Memória (`repositories/memory/`) | PostgreSQL (`repositories/postgres/`) |
|---|---|---|
| `ClienteRepository` | `dict` + índice secundário | `clientes` + `identificadores_cliente` |
| `SessaoRepository` | `dict` + expiração preguiçosa | `sessoes`, TTL na coluna `expira_em` |
| `ConversaRepository` | `dict[protocolo] → list` | `mensagens`, ordem pela coluna `seq` |
| `AtendimentoRepository` | `dict` + lista de eventos | `atendimentos` + `eventos_friccao` (só INSERT) |
| `OperacaoRepository` | `dict` por cliente | `faturas`, `equipamentos`, `planos`, `solicitacoes` |

- O esquema está em `repositories/postgres/schema.sql` e roda a cada subida da
  API, criando só o que falta. Os dados fictícios (`repositories/seed.py`) entram
  apenas com o banco vazio.
- A numeração de protocolo continua do maior número gravado, para não repetir
  protocolo depois de um reinício.
- Os testes rodam sempre em memória (`tests/conftest.py` anula a `DATABASE_URL`).
  A suíte inteira também passa contra o Neon, apontando o container para o pool.

---

## Detecção de repetição

O sinal mais sutil do motor, porque "repetir" tem duas formas:

1. **Literal** — o cliente reenvia praticamente o mesmo texto.
   `SequenceMatcher` sobre o texto inteiro, limiar 0.75.
2. **Reformulada** — o cliente reescreve a demanda em outras palavras, geralmente
   mais curto. O `SequenceMatcher` perde esse caso porque pune diferença de
   comprimento, então usamos a sobreposição de palavras de conteúdo (≥3 letras),
   limiar 0.70, exigindo ao menos 4 palavras de cada lado.

Exemplo real que só o segundo caminho pega:

```
turno 1  "Minha fatura veio R$ 189,90 mas meu plano é R$ 129,90.
          Tem uma cobrança que eu não reconheço."
turno 2  "Tem uma cobrança que eu não reconheço na minha fatura."
         → SequenceMatcher: 0.61  (abaixo do limiar, passaria batido)
         → contenção:       1.00  ✓ repeticao +18
```

O piso de 4 palavras existe para que "ok obrigado" / "ok entendi" não vire
repetição por acaso.

---

## Decisões que valem explicar na banca

- **A intenção consolidada não é sobrescrita por `OUTROS`.** Um turno final tipo
  "QUERO UM ATENDENTE" classifica como não-categorizado; se ele sobrescrevesse,
  apagaria "Contestação de Fatura" exatamente no payload que o atendente vai ler
  no handoff. Este bug existiu e foi pego por teste.
- **O handoff pode disparar antes do cliente pedir.** Com a detecção de repetição
  reformulada, a jornada da Ana cruza o limiar no turno de frustração
  ("isso é um absurdo"), um turno antes do "QUERO UM ATENDENTE". O sistema se
  antecipa — que é a proposta de valor do produto.
- **`troca_canal` descreve o canal ANTERIOR, não o de origem.** Numa jornada
  app → whatsapp → app, usar o canal de origem faria a volta dizer
  "App Claro → App Claro".
- **O nível de fricção só é derivado em `FriccaoService.nivel()`.** A entidade
  `Atendimento` não replica os limiares 70/40, senão haveria dois lugares para
  calibrar e um seria esquecido.

---

## Limitações conhecidas

- **Sem controle de concorrência.** Duas mensagens simultâneas do mesmo cliente
  podem intercalar entre os `await` e criar duas sessões. Irrelevante para a
  demonstração; com o banco, resolveria com `SELECT ... FOR UPDATE` na sessão.
- **Uma instância só da API.** A numeração de protocolo é retomada do banco na
  subida, mas gerada em memória; com várias instâncias, precisaria vir de uma
  `SEQUENCE` do PostgreSQL.
- **`impaciencia` dispara com 3 mensagens em 60s.** No `demo.py` (que envia em
  rajada) ele dispara sempre; com uma pessoa digitando na apresentação, quase
  nunca.
- **A base de clientes é fixa.** Um identificador desconhecido retorna 404 em vez
  de criar cliente — proposital, para deixar a resolução de identidade explícita.
