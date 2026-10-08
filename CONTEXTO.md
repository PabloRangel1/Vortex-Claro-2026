# Vortex — Briefing de Contexto

> Documento de handoff. Destina-se a quem for colaborar no projeto e precisa
> entender rapidamente o que ele é, como funciona por dentro, em que etapa está
> e aonde queremos chegar.
>
> Última atualização: 05/10/2026 · 167 testes passando (em memória e no PostgreSQL)

---

## 1. O que é

Projeto acadêmico do **Challenge FIAP + Claro 2026**, turma **4SIT-2026**.

| RM | Integrante |
|---|---|
| 551268 | Gustavo Matos dos Santos |
| 552528 | Leonardo Franco de Oliveira |
| 98342 | Heitor Novaes dos Santos |
| 551548 | Pablo Samuel Rangel Quilaqueo Aguayo |
| 552006 | Enzo Gabriel Nascimento Campos |

Fica em `C:\Users\Pablo\Downloads\Vortex`.

É uma **camada de orquestração inteligente entre canais de atendimento de uma
operadora de telecom**. O produto chama-se **Vortex** (nomeava-se OrquestraCX
até setembro/2026 — o PDF já entregue ainda usa o nome antigo).

---

## 2. O problema que resolve

Uma operadora atende o mesmo cliente por vários canais, e cada canal enxerga só
a si mesmo. O cliente tenta pelo app, não resolve, migra pro WhatsApp — e o
atendimento recomeça do zero. Ele repete o CPF, repete o problema, repete a
frustração. Quando chega num humano, já está exausto, e o atendente recebe uma
conversa sem passado.

São duas perdas simultâneas:

- o **contexto**, que se dissolve na fronteira entre canais;
- o **tempo**, porque ninguém percebe que aquele cliente já passou do ponto
  muito antes de ele escrever "quero falar com uma pessoa".

### A tese do produto

A insatisfação é observável antes de ser declarada. Repetir a pergunta,
reformular a demanda, migrar de canal, escrever em caixa alta — são sinais
mensuráveis que, somados, antecipam a ruptura. O sistema transforma isso num
número único, o **Score de Fricção**, e age quando ele cruza um limiar.

---

## 3. Como funciona de verdade

### 3.1 O fluxo central

Toda mensagem, de qualquer canal, passa pelo mesmo caso de uso
(`OrquestradorService.processar_mensagem`):

1. **Resolve identidade** — traduz o identificador do canal (telefone do
   WhatsApp, `usuario_id` do app) no `cliente_id` canônico, que é o CPF
2. **Obtém ou cria sessão** — ⭐ *aqui mora a proposta de valor*: se existe
   sessão viva pro cliente, o **protocolo é reaproveitado mesmo vindo de outro
   canal**
3. **Classifica intenção** via NLP por regras
4. **Grava a mensagem** no histórico, marcada com o canal
5. **Avalia fricção** — 9 detectores independentes
6. **Consolida o score** e grava um evento imutável por sinal detectado
7. **Decide quem responde**, nesta ordem: handoff agora (score cruzou 70, cliente
   pediu uma pessoa, ou o autoatendimento não tem solução) → fila humana (já
   transferido) → **autoatendimento** (conversa guiada executa ações do
   catálogo) → resposta comum do bot por intenção

### 3.2 O motor de fricção

Nove detectores, cada um devolvendo peso + justificativa legível em português:

| Sinal | Peso |
|---|---|
| Pedido explícito de humano | +25 |
| Repetição (literal ou reformulada) | +18 |
| Troca de canal | +16 |
| Sentimento negativo | +6 a +20 |
| Intenção repetida | +12 |
| Loop sem resolução | +8/turno (teto +24) |
| Impaciência (3 msgs em 60s) | +8 |
| Caixa alta | +5 |
| Decaimento (atendente assume) | −12 |

Score saturado em `[0, 100]`, limiar de handoff em **70**. Tudo parametrizado em
`app/config.py` — nada hardcoded nos services.

**A jornada real medida:** `0 → 18 → 54 → 82 → 100`. O handoff dispara em **82**,
no turno em que a cliente escreve *"já expliquei isso três vezes, isso é um
absurdo"* — **um turno antes** de ela pedir atendente. O sistema se antecipa.
Esse é o argumento central da apresentação.

### 3.3 O detector de repetição (o mais sutil)

Reconhece duas formas de repetir:

1. **Reenvio literal** — `SequenceMatcher` ≥ 0.75 sobre o texto inteiro.
2. **Reformulação** — o cliente reescreve a mesma demanda em outras palavras,
   geralmente mais curto. O `SequenceMatcher` perde esse caso porque pune
   diferença de comprimento, então há um segundo caminho por sobreposição de
   palavras de conteúdo (≥ 0.70, mínimo 4 palavras de cada lado).

---

## 4. Arquitetura

```
routers  →  services  →  repositories/base  →  domain
```

A dependência só aponta para dentro. **Nenhum service importa de
`repositories/memory/`** — todos falam com interfaces abstratas.

> **A regra que sustenta tudo:** todos os métodos de repositório são `async`,
> mesmo sendo dicionários hoje. É o que permite plugar `asyncpg` sem alterar
> nenhuma assinatura. A migração para o banco real troca as implementações em
> `app/dependencies.py` e nada mais.

Destino decidido no `demandas.md`: **um único PostgreSQL** (Neon). Redis e
MongoDB ficam como evolução de escala, fora do MVP.

| Repositório | Hoje | Destino |
|---|---|---|
| Sessão | dict + expiração preguiçosa | PostgreSQL `sessoes` |
| Conversa | lista por protocolo | PostgreSQL `mensagens` |
| Cliente | dict + índice secundário | PostgreSQL `clientes` + `identificadores_cliente` |
| Atendimento | dict + lista de eventos | PostgreSQL `atendimentos` + `eventos_friccao` |
| Operação | dicts por cliente + catálogo | PostgreSQL `faturas`, `equipamentos`, `planos`, `solicitacoes` |

### 4.1 Stack

- **Backend:** Python 3.11+, FastAPI async, Pydantic v2 — `Vortex/backend/`
- **Frontend:** React 18, Vite, Tailwind CSS v4 — `Vortex/frontend/`
- **Persistência:** PostgreSQL no Neon (com `DATABASE_URL`); em memória sem ela

### 4.2 Endpoints

```
POST /channels/app                              mensagem do App Claro
POST /channels/whatsapp                         webhook simulado
GET  /channels/atendimento-atual                protocolo em curso do cliente
GET  /dashboard/fila                            fila ordenada por score
GET  /dashboard/atendimento/{protocolo}         contexto consolidado
GET  /dashboard/setores                         destinos de transferência
GET  /dashboard/estatisticas                    agregações do painel analítico
POST /dashboard/atendimento/{protocolo}/responder
POST /dashboard/atendimento/{protocolo}/transferir
POST /dashboard/atendimento/{protocolo}/encerrar
POST /dashboard/atendimento/{protocolo}/avaliar  CSAT do cliente
GET  /health · /config · /clientes    POST /reset
```

### 4.3 Frontend

Quatro telas: **Dashboard do atendente** (fila | conversa | painel de
inteligência com o gauge), **Estatísticas** (painel analítico), **simulador do
App Claro** e **simulador do WhatsApp**. Os dois simuladores são o mesmo
componente parametrizado (`SimulatorShell`).

Atualização por **polling** (3s no atendimento, 4s na fila), com guard de
sobreposição, pausa em aba oculta, backoff em erro e sem flicker — está em
`hooks/usePolling.js`.

---

## 5. Onde estamos agora

> **Atenção à numeração.** O roteiro atual é o do [`demandas.md`](demandas.md),
> organizado em **Fases 1 a 6** de autoatendimento. As etapas anteriores do
> projeto estão listadas abaixo como "concluídas", sem número, para não colidir.

### Etapas concluídas

```
✅ Protótipo visual                  (legado, Vortex/index.html)
✅ Backend in-memory                 85 testes passando
✅ Frontend React integrado          consumindo a API real
✅ Transferir, encerrar, CSAT        aba de estatísticas
✅ Documento de arquitetura (PDF)    entregue — ainda com o nome OrquestraCX
✅ Vídeo                             gravado
```

### Roteiro de autoatendimento (`demandas.md`)

```
✅ Fase 1  Dados fictícios, catálogo de ações, AutoatendimentoService
✅ Fase 2  Conversa orientada a etapas (estado pendente na sessão)
✅ Fase 3  PostgreSQL no Neon
✅ Fase 4  Ligar o autoatendimento ao orquestrador e à interface
✅ Fase 5  IA (Gemini) como camada de linguagem, com fallback determinístico
⬜ Fase 6  Publicação no Render
```

**Tudo que foi entregue está funcionando e verificado.** A jornada roda ponta a
ponta: cliente escreve no app, migra pro WhatsApp, o score sobe, o handoff
dispara, o atendente responde pelo dashboard e a resposta aparece no celular do
cliente.

**O autoatendimento está na interface** desde a Fase 4: o cliente resolve
segunda via, vencimento, diagnóstico/reinício, upgrade e contestação pelos
simuladores, com cartões de resultado e botões de resposta. Os scripts
`demo_autoatendimento.py`, `demo_conversa_guiada.py` e `chat.py` continuam
úteis para testar sem interface.

### 5.1 Como rodar — um comando só

O FastAPI serve o frontend compilado. Não precisa de dois servidores.

```powershell
cd C:\Users\Pablo\Downloads\Vortex\backend
.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
```

Com o `backend/.env` contendo a `DATABASE_URL`, a API sobe já ligada ao Neon
(o `GET /health` mostra `"persistencia": "postgresql"`). Sem o `.env`, roda em
memória.

Abrir **http://localhost:8000**. Swagger em `/docs`. Demo narrada:
`python demo.py`. Testes: `.venv\Scripts\python.exe -m pytest -q`.

> ⚠️ **Ao mexer em `frontend/src/`, é obrigatório rodar `npm run build`** na
> pasta `frontend` — senão a mudança não aparece, porque o backend serve o
> `dist/`.

---

## 6. Objetivo e próximos passos

**O objetivo atual** (do `demandas.md`) é transformar o Vortex de um
orquestrador que classifica e encaminha em um **protótipo funcional de
autoatendimento**: o cliente resolve demandas simples sozinho, e o handoff
humano vira saída qualificada — só quando a demanda não tem solução automática,
o cliente pede uma pessoa, ou a fricção cruza o limiar.

Regra de produto: *IA conversa e interpreta; o backend executa ações
permitidas.* A IA nunca altera dados nem inventa solução.

**Decisão de infraestrutura:** só **PostgreSQL no Neon** (plano gratuito). Redis
e MongoDB saem do MVP e ficam como evolução de escala documentada.

**Pendências e limitações conhecidas:**

1. **Fase 6 do `demandas.md`** (publicação no Render) é o próximo passo.
2. **Sem controle de concorrência.** Duas mensagens simultâneas do mesmo cliente
   podem criar duas sessões. Irrelevante para a demo.
3. **Base de clientes fixa** — identificador desconhecido retorna 404 em vez de
   criar cliente. Proposital.
4. **Frontend sem testes automáticos.** O backend tem 167; o front foi verificado
   por capturas e cliques via Chrome headless (ver 6.7).
5. **Fases 4 e 5 cobertas por testes** desde 05/10 (`test_autoatendimento.py`,
   `test_ia.py` com modelo simulado, `test_melhorias.py`).
6. **Turnos com IA podem passar dos 2s** do requisito de latência (timeout da IA
   é 4s). Turnos resolvidos pelas regras continuam bem abaixo.

## 6.2 Autoatendimento — Fase 1 (adicionado em 17/09)

Três peças, com responsabilidades separadas de propósito:

- **`domain/acoes.py`** — o catálogo fechado. Cada ação declara parâmetros
  obrigatórios, se exige confirmação, se gera solicitação e **todos os textos**
  de sucesso e falha. Os textos vivem aqui, não no serviço: mudar a redação
  nunca toca regra de negócio.
- **`services/autoatendimento_service.py`** — decide o que aconteceu e devolve
  um `ResultadoAcao` estruturado. Sem HTTP, sem texto de interface, sem IA.
- **`OperacaoRepository`** — uma interface para faturas, equipamentos, planos e
  solicitações: a fronteira com os sistemas da operadora.

| Ação | Confirma | Gera solicitação |
|---|---|---|
| `gerar_segunda_via` | não | — |
| `alterar_vencimento` | **sim** | concluída |
| `diagnosticar_conexao` | não | — |
| `reiniciar_equipamento` | **sim** | concluída |
| `listar_planos` | não | — |
| `confirmar_upgrade` | **sim** | concluída |
| `abrir_contestacao` | **sim** | em análise |
| `encaminhar_humano` | não | — (sinaliza `requer_handoff`) |

**Pipeline de toda execução:** ação existe no catálogo → parâmetros presentes →
regra de negócio valida → se exige confirmação e não houve, devolve prévia
**sem alterar nada e sem registrar** → executa → cria solicitação → registra →
devolve. Valida *antes* de pedir confirmação, para o cliente nunca confirmar
algo que seria recusado.

**Registro:** cada sucesso ou falha vira mensagem de sistema com
`metadados.tipo = "acao"` — o mesmo padrão de troca de canal, handoff e
transferência. Na Fase 4, o orquestrador **não** deve gravar essa mensagem de
novo: o serviço já grava.

**Dados fictícios** (banco 999 no código de barras, equipamentos `EQ-FICT-…`),
coerentes com a narrativa da demo:

| Cliente | Plano | Venc. | Fatura | Equipamento |
|---|---|---|---|---|
| Ana | Pós 40GB | 5 | R$ 189,90 aberta, com item avulso de R$ 60 | — |
| Ricardo | Fibra 500MB | 10 | R$ 99,90 aberta | roteador instável |
| Juliana | Controle 25GB | 5 | R$ 64,90 aberta | — |
| Carlos | Pós Família 80GB | 20 | R$ 219,90 **paga** | — |

Os buracos são intencionais: cada ação tem pelo menos um caminho de falha
legível para demonstrar (Ana sem equipamento, Carlos sem fatura em aberto).

---

## 6.1 Operação do atendimento (adicionado em 17/09)

- **Transferir** move o atendimento para outro setor (Suporte Técnico N2,
  Financeiro, Retenção, Ouvidoria). Não encerra: o protocolo e o histórico
  seguem com o cliente, o atendente atual é liberado e o caso volta à fila com
  o setor marcado. Diálogo modal com motivo opcional.
- **Encerrar** finaliza, libera a sessão e registra o evento. O atendimento
  **permanece selecionado** na tela depois de encerrado, porque a avaliação do
  cliente ainda vai chegar nele.
- **Avaliação (CSAT)** aparece no aparelho do cliente assim que o atendimento é
  encerrado: cinco carinhas de 1 a 5 com comentário opcional. As carinhas são
  SVG desenhadas no projeto, não emoji — emoji muda de desenho por sistema
  operacional e quebra a consistência da marca.
- **Estatísticas** agrega do que os clientes reclamam (por intenção), a
  distribuição das faixas de fricção, os gatilhos mais frequentes, o canal de
  origem e o CSAT.

## 6.3 Conversa guiada — Fase 2 (adicionado em 17/09)

**`services/dialogo_service.py`** dá memória curta à conversa. O estado fica na
**sessão**, que é única por cliente — por isso o cliente pode pedir no App e
confirmar no WhatsApp.

Campos novos em `Sessao`: `etapa_fluxo` (`nenhuma` · `aguardando_parametro` ·
`aguardando_confirmacao`), `acao_pendente`, `dados_pendentes`,
`tentativas_etapa`.

`DialogoService.conduzir(sessao, texto, intencao)` devolve um `TurnoDialogo`.
Com `tratado=False` a mensagem não é de autoatendimento e quem chamou segue com
a resposta comum do bot — é esse o contrato que a Fase 4 vai usar.

**Ordem de decisão numa resposta, com fluxo em curso:**
1. valor novo ("não, prefiro o dia 20") → nova proposta
2. recusa ("não", "quero cancelar") → limpa, nada muda
3. assunto novo ("me manda a segunda via") → abandona e trata o pedido novo
4. confirmação ("sim", "pode") → **único caminho que executa**
5. nada disso → pergunta de novo; na 3ª vez desiste e libera a conversa

**Interpretação determinística** em `core/interpretacao.py`, sem IA: olha a
primeira palavra ("sim, não reconheço essa cobrança" é confirmação, não recusa)
e extrai dia e plano escolhido. É a base que continua funcionando quando a IA da
Fase 5 falhar.

**Fluxos encadeados:** diagnóstico com instabilidade já oferece o reinício;
upgrade com uma opção só vai direto para a confirmação; "mudar o vencimento
para o dia 10" já traz o dado e pula a pergunta.

**Ambiguidade resolvida:** no meio de um fluxo, "quero cancelar" cancela a
**operação**. Só vira pedido de cancelamento de contrato — e encaminhamento a
humano — se o cliente citar o que quer cancelar ("cancelar meu plano").

Textos da conversa em `domain/dialogo.py`, pelo mesmo motivo dos textos das
ações: redação não se mistura com regra.

## 6.4 PostgreSQL — Fase 3 (adicionado em 05/10)

- **Escolha automática:** `app/dependencies.py` usa os repositórios de
  `repositories/postgres/` quando há `DATABASE_URL`, e os de memória quando não
  há. O pool `asyncpg` abre no *lifespan* do FastAPI (`main.py`).
- **Esquema** em `repositories/postgres/schema.sql`, idempotente, executado a
  cada subida. Semeia os dados fictícios (`repositories/seed.py`, fonte única
  para os dois modos) só com a tabela `clientes` vazia.
- **Protocolo sem colisão:** na subida a numeração continua do maior protocolo
  gravado (`continuar_sequencia`). Vale para uma instância da API.
- **`POST /reset`** agora faz `TRUNCATE` + semeadura no banco.
- **Testes** forçam memória (`conftest.py` zera `DATABASE_URL`). A suíte também
  foi rodada inteira contra o Neon: 85/85.
- **Verificado:** API derrubada e reerguida no meio de uma alteração de
  vencimento — fila, histórico, score, eventos e o fluxo pendente voltaram, e o
  cliente concluiu a operação pelo outro canal.
- **Neon:** a URL usada é a do *pooler* (PgBouncer), por isso o asyncpg roda com
  `statement_cache_size=0`. O plano gratuito suspende o banco ocioso: a primeira
  requisição depois de um tempo parado demora ~1s.
- **Ver os dados:** HeidiSQL, tipo "PostgreSQL", com SSL marcado.
- **Segredo:** a senha mora só em `backend/.env`, protegido pelo `.gitignore`
  na raiz do projeto.

## 6.5 Autoatendimento na interface — Fase 4 (adicionado em 05/10)

**Orquestrador** (`orquestrador_service.py`): depois da fricção, decide quem
responde (ver 3.1). O `DialogoService` só roda enquanto o bot está no comando;
se o handoff dispara no meio de um fluxo, o fluxo pendente é descartado.

**Saídas qualificadas para humano**, cada uma com motivo legível em
`handoff_motivo`:
- score cruzou 70 (como antes);
- **pedido explícito de pessoa** — agora transfere na hora, sem esperar o
  limiar. O score não muda: o +25 continua sendo só um sinal;
- autoatendimento sem solução — cancelamento ou equipamento offline.

**A jornada do pitch não mudou:** `0 → 18 → 54 → 82 → 100`, handoff em 82.

**Fricção: o cálculo não mudou, o que entra nele sim.** Sem isso, o motor
punia o autoatendimento que dava certo — o segundo "Sim, confirmo" contava como
repetição e o cliente era transferido em vez de ter a contestação aberta.
- *Resposta guiada* (sim/não, o dia, o plano, em resposta a uma pergunta do
  bot) não entra na comparação de repetição nem conta como impaciência.
  Repetir a demanda em vez de responder continua contando. A mensagem fica
  marcada com `metadados.resposta_guiada`.
- *Ação que resolve* (`RESOLVEM_A_DEMANDA` em `domain/acoes.py`) zera a
  contagem de turnos sem resolução da sessão (`SessaoService.registrar_resolucao`).

**Contrato HTTP:**
- `POST /channels/*` devolve `origem_resposta`, `acoes[]` (código, status,
  `dados` estruturados, protocolo da solicitação) e `fluxo` (etapa pendente e
  `opcoes` de resposta).
- `GET /dashboard/atendimento/{p}` devolve `fluxo` quando há pergunta em
  aberto neste protocolo.

**Frontend:**
- `components/simulator/ActionCard.jsx` — cartões de fatura (com cópia do
  código), diagnóstico, planos comparados e solicitação concluída/em análise.
  Vêm das mensagens `tipo = "acao"` do histórico, então sobrevivem a recarga.
- Botões de resposta do `fluxo` substituem as sugestões enquanto o bot espera.
- Dashboard: as ações aparecem na conversa como registro compacto, e o painel
  ganhou a seção **Autoatendimento** (o que o bot tentou antes do handoff).
- `lib/acoes.js` — rótulos de ação/resultado, moeda e data.

## 6.6 IA como camada de linguagem — Fase 5 (adicionado em 05/10)

**`services/ia_service.py`** chama o Gemini por HTTP (`httpx`, sem SDK) e
devolve uma `SugestaoIA` já validada — ou `None`.

**Quando a IA entra:** só quando as regras determinísticas não entendem.
Primeiro as regras (rápidas, previsíveis, sem custo); a IA cobre o resto:
- pedido em texto livre sem gatilho ("minha conta veio mais cara") → sugere
  uma ação do catálogo;
- resposta que o fluxo não entendeu ("lá pelo meio do mês") → dia/plano/sim/não;
- conversa sem ação ("oi, tudo bem?") → resposta curta e natural;
- recusa ambígua numa confirmação ("não reconheço essa cobrança") → desempata.
  Sem IA, o bot pergunta de novo em vez de cancelar (antes cancelava).

**Barreiras (todas verificadas com um modelo simulado):**
- só ações que o chamador permitiu naquele momento; `encaminhar_humano` nunca
  é permitido — handoff, score e limiar não são decisão da IA;
- dia e plano só valem se estiverem entre as opções oferecidas;
- texto livre é descartado se trouxer número longo, `R$` ou "protocolo" —
  fatos só vêm do backend;
- a sugestão é aplicada pelos mesmos caminhos de uma mensagem digitada, então
  o `AutoatendimentoService` valida tudo de novo;
- `core/privacidade.py` troca CPF, telefone, e-mail e sequências longas por
  `[número]`/`[email]`; nome e identificadores do cliente nem entram no
  contexto (só etapa, opções, ações permitidas, canal, últimas mensagens).

**Fallback:** sem chave, timeout (4s), cota (429), erro ou JSON inválido →
`None` e a conversa segue pelas regras. Depois de uma falha a IA pausa 60s,
para não pagar o timeout a cada mensagem. Testado contra a API real com chave
inválida: fallback em 0,6s e as mensagens seguintes nem tocam a rede.

**Na interface:** a bolha do bot ganha "✦ IA" quando a IA participou
(`metadados.ia` da mensagem; `gerado_por_ia` no payload do canal). No
dashboard: "Bot · interpretado por IA".

**Modelo: `gemini-3.5-flash-lite`** (padrão em `config.py`). Escolhido por
teste em 05/10/2026 com a chave real, em 5 casos (texto livre → contestação,
saudação, "meio do mês" → dia 15, recusa ambígua → sim, "o mais em conta" →
plano certo):
- `gemini-2.5-flash` e `-lite`: **indisponíveis para chaves novas** (404);
- `gemini-3.8-flash` e `gemini-3.5-flash`: sobrecarregados (503) ou acima do
  timeout de 4s;
- `gemini-3.5-flash-lite`: 15/15 em três rodadas, 0,8–1,4s por chamada.
A instrução ao modelo traz regras explícitas para os casos difíceis (o primeiro
teste, sem elas, acertou 1 de 5). Ponta a ponta com Neon + Gemini: turnos com
IA em 1,5–2,1s, sem IA em 0,7–0,9s.

**Configuração:** `GEMINI_API_KEY` e, opcionalmente, `GEMINI_MODELO` no
`backend/.env`. `GET /health` mostra o modelo ativo ou
`"desligada"`. Os testes forçam a IA desligada (`conftest.py`).

## 6.7 Melhorias de 05/10 (pós-auditoria)

**Para o atendente (dashboard):**
- **Resumo do caso** no handoff (`ResumoCaso.jsx` + `lib/resumo.js`): o que o
  cliente quer, o que o bot já fez (com protocolo), o que falhou, por que
  transferiu e sinais de atenção (repetiu, trocou de canal, contatos no mês).
  Montado só com dados registrados — nada inventado. Recolhível.
- **Respostas rápidas** (`lib/respostasAtendente.js`): por assunto; o clique
  preenche o campo, não envia.
- **Histórico do cliente**: "Nº contato em 30 dias" (alerta a partir do 3º) e
  os protocolos anteriores, clicáveis (`contatos_anteriores` no payload).
- **Fila**: contagem no título da aba ("(2) Dashboard") e espera acima de 2 min
  destacada (`ESPERA_ALERTA_SEGUNDOS`).
- **Reiniciar demo** na barra superior, com confirmação; pede o token quando
  o servidor exige.

**Estatísticas:** "Resolvido sem humano" (atendimentos com ação que resolve e
sem handoff) é o primeiro indicador; card "O que o bot resolveu sozinho" por
ação. Encaminhar a humano não conta como ação resolvida.

**Regras:**
- CSAT só em atendimento encerrado, e uma vez só.
- `POST /reset` exige `X-Admin-Token` quando `ADMIN_TOKEN` existe; fora de
  `AMBIENTE=desenvolvimento`, sem token, fica desligado. `/health` informa
  `reset_protegido`. **No Render: definir `ADMIN_TOKEN` e `AMBIENTE=producao`.**
- A IA nunca diz que não dá para falar com uma pessoa; orienta a pedir.
- **"Isso", "pode", "ok", "certo"… só confirmam em resposta de até 3 palavras.**
  Antes, "isso é um absurdo, já expliquei três vezes" — a frase de frustração
  do roteiro — confirmava a contestação oferecida pelo bot.

**Bug achado no teste por cliques:** `ResumoCaso` e `Composer` são irmãos e
tinham a mesma `key` (o protocolo). O React perdia o cartão anterior e
empilhava cópias ao trocar de atendimento. Chaves agora com prefixo.

## 6.8 Verificação, pesquisa, base e demonstração (adicionado em 05/10)

**Verificação de identidade** (`services/verificacao_service.py`, textos em
`domain/verificacao.py`): no **WhatsApp**, a primeira mensagem é respondida com
o pedido dos **3 primeiros dígitos do CPF**. O pedido original fica na sessão
(`mensagem_pendente`) e é atendido logo após a confirmação — o cliente não
repete nada. 3 erros → handoff com motivo "Identidade não confirmada". No
**App** a identidade vem do login (`verificada_app`). Quem verificou num canal
segue verificado no outro e na retomada. Canais e tentativas em `config.py`
(`verificacao_canais`, `verificacao_tentativas`). O painel mostra a situação
em "Identidade", e o resumo do caso alerta quando não foi confirmada.
Na tela do WhatsApp há uma dica para quem apresenta com os 3 dígitos.

**Pesquisa de satisfação garantida:** antes, só aparecia quando alguém
encerrava — atendimento resolvido pelo bot nunca terminava, e o cliente nunca
avaliava. Agora "era só isso, obrigado" (`core/interpretacao.eh_despedida`)
encerra o atendimento e o aparelho mostra a pesquisa. Depois de uma ação
resolvida, o simulador sugere essa resposta. "Não resolveu, obrigado" não é
despedida; "Não, obrigado" no meio de um fluxo continua sendo recusa.
O painel do atendente mostra a nota e o comentário ("Avaliação do cliente").

**Base de clientes** (`repositories/seed.py`): 12 clientes fictícios com
nascimento, e-mail e cidade. Os 4 primeiros são da **demonstração ao vivo**
(`CLIENTES_DEMO_AO_VIVO`) e nunca ganham atendimento aberto pela simulação.

**Demonstração pré-carregada** (`services/demonstracao_service.py`): 12
conversas simuladas — 7 encerradas e avaliadas ao longo de 9 dias, e, nas
últimas 2 horas, 3 na fila humana e 1 já com atendente. Passam pelo
orquestrador real (verificação, fricção, autoatendimento, handoff, troca de
canal), então tudo fica coerente. As datas vêm de `core/relogio.py`, que
"volta no tempo" só durante a simulação.
- Carrega na subida se as conversas simuladas ainda não estiverem no banco
  (nunca apaga nada na subida), e a cada **Reiniciar demo**.
- Antes de simular, limpa sessões vivas: uma sessão de um teste recente
  capturava a conversa "de 9 dias atrás" para dentro do protocolo dela.
- Desligável com `SEMEAR_DEMONSTRACAO=false` (os testes fazem isso).

**Atualização (rodada seguinte):** a simulação tem **14** conversas — duas
delas resolvidas **com a IA** (texto livre virando contestação; "meio do mês"
virando dia 15). Durante a simulação o modelo real sai de cena e essas falas
usam respostas fixadas (as mesmas que o Gemini real deu nos testes), passando
pela mesma validação da IA (`_IARoteirizada`): determinístico e sem cota.
Cobertura dos casos: resolvidos pelo bot, fricção alta (Patrícia, 100, com
troca de canal), resolvidos com IA, falha de identidade, cancelamento,
transferência entre setores.

**Tema escuro** nos dois aparelhos (Minha Claro e WhatsApp), cartões e
pesquisa inclusos. As cores de status clareiam dentro da tela escura.

## 6.9 Abertura, protocolo, histórico e filtros (adicionado em 05/10)

**Abertura de todo atendimento novo** (`dialogo.BOAS_VINDAS`): a assistente
se apresenta como **IA**, informa o **protocolo** já no início (antes ele só
aparecia na transferência) e lembra que dá para pedir uma pessoa. É uma
mensagem do bot com `metadados.tipo = "boas_vindas"`, antes da resposta.

**Revisão da IA / diálogos novos** — só os que tiram respostas "não entendi":
- **Consulta de protocolo** (`consultar_atendimento`, só leitura): "meu último
  atendimento", "status da minha contestação", ou o número colado
  (AAAA-MMDD-NNNNN ou SOL-…). Responde assunto, data (horário de Brasília),
  canal, situação e solicitações vinculadas. **Só protocolos da própria
  conta** — de outra pessoa, recebe "não encontrado".
- **Consultas de fatura** ("quando vence?", "quanto está minha conta?") vão
  para a segunda via, que já traz valor e vencimento.
- **Ajuda/menu** ("o que você faz?"): resposta fixa com as opções; só quando
  nenhuma ação foi reconhecida ("ajuda com a internet" segue para diagnóstico).

**Aba Histórico** (`routes/Historico.jsx`): consulta por protocolo (atendimento
ou SOL-, destaca o atendimento), lista de clientes com busca por nome/CPF e
filtro por tipo, e o histórico completo — cadastro, atendimentos (assunto,
situação, fricção, identidade, motivo da transferência, avaliação) e
solicitações. "Abrir no painel" leva ao Dashboard com `?protocolo=`.
Endpoints: `GET /dashboard/clientes`, `/dashboard/clientes/{id}/historico`,
`/dashboard/protocolo/{p}`.

**Filtro por tipo de cliente** (`Segmento`: Pós-pago, Controle, Fibra, derivado
do plano) na fila do Dashboard, junto do filtro por canal, e na aba Histórico.

## 6.10 Auditoria de segurança (IA e dados), visual e Impacto (05/10)

**Achados e correções — dados pessoais:**
- **O nome do cliente ia para o Gemini** ("Obrigado, Ana!" no histórico).
  `anonimizar(texto, nomes)` agora troca o nome por `[nome]`.
- **Os dígitos do CPF da verificação iam para o Gemini** — o próprio segredo
  de identidade. A resposta à verificação é marcada (`metadados.verificacao`)
  e fica fora do contexto da IA.
- **A API devolvia o CPF completo** (`cliente_id`) na fila, no atendimento, na
  lista de clientes e no simulador. Agora sai só uma **referência opaca**
  (`cliente_ref`, HMAC do CPF com `CHAVE_REFERENCIA`); o CPF é só interno.
- **Log** de JSON inválido da IA não grava mais o conteúdo, só as chaves.
- Testado contra o Gemini real: pedidos de "repita o contexto", "qual o CPF
  do titular" e "dados de outros clientes" foram recusados — e o modelo nem
  recebe esses dados. Testes em `tests/test_seguranca.py`.

**Riscos que continuam (decisão de vocês, antes de dados reais):**
- Dashboard, histórico e estatísticas **sem login**: na URL pública, qualquer
  pessoa vê nome, e-mail, nascimento e telefone (fictícios hoje).
- **Gemini no plano gratuito**: o Google pode usar o conteúdo para melhorar
  produtos. Com dados reais, usar plano pago/Vertex com termos de tratamento.
- O banco usa o papel **dono** (`neondb_owner`); para produção, um papel só com
  leitura/escrita nas tabelas.
- Sem limite de requisições por IP (abuso pode esgotar a cota da IA).
- A dica dos 3 dígitos no simulador é recurso de demo
  (`SIMULADOR_DICA_VERIFICACAO=false` desliga).

**Visual:** bolhas da conversa redesenhadas (bot branco, atendente no tom da
marca, cliente com a cor do canal; antes era cinza sobre cinza), notas do
sistema legíveis (handoff em destaque), profundidade discreta nos cartões
(`--shadow-cartao`).

**Estatísticas com gráficos** (`components/charts/`, SVG sem biblioteca):
atendimentos por dia em colunas empilhadas por desfecho e fricção média por
dia com os limiares, ambos com tooltip e "ver como tabela". Paleta das séries
validada para daltonismo (`--color-serie-1..3`), sem azul e sem tocar nas
cores reservadas da marca e de status. Backend: `por_dia` em
`/dashboard/estatisticas`.

**Aba "Impacto do Vortex"** (Estatísticas › Impacto): o cliente que a Claro não
perdeu — receita mensal protegida dos clientes em risco que seguiram sem nota
negativa, upgrades, "sem o Vortex × com o Vortex" (protocolos, histórias
recontadas, risco sem alerta) e uma jornada real de um protocolo só. Premissas
escritas na própria tela. Backend: bloco `impacto`.

A simulação ganhou volume de rotina (35 atendimentos em 10 dias) e um upgrade
(Marina), para os gráficos e o Impacto terem corpo.

## 6.11 Auditoria de 06/10 — reset, datas e faturas

- **"Reiniciar demo" levava ~107s no Neon** e o navegador desistia em 8s
  (erro na tela, página sem recarregar, e um 2º clique rodava outro reset em
  paralelo). Agora a simulação roda **em memória** e o resultado é gravado em
  lote numa transação (`postgres.copiar_simulacao`): **~4s**. Um reset por vez
  (`Container.resetar` espera o que estiver em curso). Na subida, sem
  simulação no banco, carrega em ~2s e **preserva o cadastro** dos clientes da
  demo ao vivo (`preservar=CLIENTES_DEMO_AO_VIVO`). O front dá 60s ao reset.
- **Espera acima de 1h** aparecia como "1854m00s"; agora "31h54m".
- **"Últimos 10 dias" terminava no último atendimento**, não hoje. Corrigido.
- **Faturas com data fixa** (out/2026) iam vencendo sem o bot notar. Agora a
  semente gera o vencimento a partir de hoje, pelo dia de cada cliente; e a
  segunda via de fatura com vencimento passado avisa que está **vencida**
  (`segunda_via_vencida`, com multa/juros), também no cartão do simulador.
- **Antes de apresentar:** a demonstração é gravada com horários relativos ao
  momento da carga. Num dia seguinte, a fila mostra esperas longas — clique em
  **Reiniciar demo** (agora leva segundos).

## 7. Convenções que importam

- **Código e comentários em português.** Nomes de domínio em português
  (`FriccaoService`, `atendimento`, `protocolo`).
- **A regra de dependência é inviolável.** Service não conhece storage.
- **Pesos e limiares só em `config.py`.**
- **Identidade visual da Claro:** tema claro, vermelho `#E30613` dominante, sem
  azul. Os neutros têm viés quente de propósito (cinza frio ao lado do vermelho
  o encardece).
- **A paleta de status é separada da marca.** Se "crítico" fosse o vermelho da
  marca, o score deixaria de comunicar. Faixas validadas: estável `#008A4E`,
  atenção `#9C6A00`, crítico `#B01020` — passam nos critérios de contraste e
  daltonismo.
- **O WhatsApp é verde de propósito** — é a marca dele, não a da Claro.
- **Texto nunca abaixo de 11px.** Use os níveis `text-rotulo` (11px: hora,
  etiqueta, título de seção) e `text-apoio` (12px: texto secundário), definidos
  em `theme.css`. A banca lê de longe, num projetor.
- **Chaves de componentes irmãos são únicas** — use prefixo (`resumo-…`,
  `composer-…`) quando a chave vier do protocolo.
- **Ícones só em SVG**, de `components/ui/icons.jsx` (intenções via
  `IconeIntencao`). Emoji muda de desenho a cada sistema operacional.
- **Ação que não se desfaz pede confirmação** e usa as variantes `perigo` /
  `perigoSolido` do `Button` (cor de status crítico, não a da marca).

---

## 8. Armadilhas que já custaram tempo

Vale saber, para não repetir:

- **Documentos vão como PDF local, nunca como artefato web.** Preferência
  explícita do Pablo.
- **O navegador dele não alcançava a porta 5173 do Vite.** Por isso o frontend é
  servido pelo FastAPI na 8000. Não reintroduza o fluxo de dois servidores sem
  necessidade.
- **Google Fonts não carrega no Chrome headless** — cai silenciosamente pra
  Arial/Times. Para gerar PDF, as fontes precisam ser embutidas como data URI.
- **Substituição por regex amplo quebra imports.** Um `client → claro`
  transformou `react-dom/client` em `react-dom/claro`. Ancore os padrões.
- **Verifique visualmente o que for renderizado.** Bugs de overflow em SVG e
  colisão de rótulos só aparecem rasterizando a página.

---

## 9. Bugs reais já corrigidos

Contexto para não regredir:

- **Path traversal servia qualquer arquivo do servidor** (achado na auditoria
  de 05/10, antes da publicação). A rota que entrega o frontend aceitava
  `/..%2F..%2Fbackend%2F.env` e devolvia o `.env` com a senha do banco e a
  chave da IA. `is_relative_to` é só textual; a correção resolve o caminho
  antes de comparar. Coberto por `tests/test_seguranca.py`.
- **Sessão expirada partia o atendimento em dois** (auditoria de 05/10). Cliente
  esperando humano por mais de 30 min, ao escrever de novo, ganhava protocolo
  novo e o antigo ficava órfão na fila. Agora a sessão é recriada no MESMO
  protocolo quando o último atendimento está na fila humana ou com atendente
  (`OrquestradorService._atendimento_com_humano`). Conversa abandonada com o
  bot continua abrindo protocolo novo.
- **Encerrar duas vezes derrubava a conversa nova** (auditoria de 05/10).
  `encerrar` agora é idempotente e só libera a sessão se ela ainda for daquele
  protocolo.
- **Banco fora do ar na subida** (auditoria de 05/10): a API tenta 6 vezes em
  ~30s antes de desistir. Desistir é de propósito — cair para memória em
  silêncio perderia dados na demo. Os três itens: `tests/test_continuidade.py`.

- **A intenção consolidada não pode ser sobrescrita por `OUTROS`.** Um turno
  final "QUERO UM ATENDENTE" classifica como não-categorizado; se sobrescrevesse,
  apagaria "Contestação de Fatura" exatamente no payload que o atendente vai ler.
  Pego por teste.
- **`troca_canal` descreve o canal anterior, não o de origem.** Numa jornada
  app → whatsapp → app, usar o de origem faria a volta dizer
  "App Claro → App Claro".
- **O limiar mora num lugar só** — a entidade `Atendimento` não replica os
  valores 40 e 70.
- **Depois do handoff o bot para de responder por intenção.** É correto, mas
  travava o simulador; foi adicionado o botão "Nova conversa" e um aviso
  explicando.

---

## 10. Base de clientes semeada

Os dois identificadores resolvem para o mesmo `cliente_id` canônico — é assim
que o sistema sabe que o cliente do App e o do WhatsApp são a mesma pessoa.

| Cliente | `usuario_id` (App) | `telefone` (WhatsApp) |
|---|---|---|
| Ana Beatriz Souza | `user_ana` | `5511998877321` |
| Ricardo Mendes Lima | `user_ricardo` | `5511997712298` |
| Juliana Ferraz | `user_juliana` | `5511992095566` |
| Carlos Eduardo Nunes | `user_carlos` | `5511988413055` |

---

## 11. Mapa de arquivos

```
Vortex/
├─ CONTEXTO.md                 este documento
├─ demandas.md                 ⭐ roteiro atual, Fases 1 a 6
├─ index.html                  protótipo visual legado (superado pelo frontend)
├─ docs/
│  ├─ arquitetura.html         fonte do documento de arquitetura
│  └─ Vortex-Arquitetura.pdf   entregável do Challenge
├─ backend/
│  ├─ README.md                documentação técnica do backend
│  ├─ demo.py                  roteiro narrado da jornada completa
│  ├─ demo_autoatendimento.py  roteiro das 8 ações da Fase 1
│  ├─ demo_conversa_guiada.py  conversa entre canais da Fase 2
│  ├─ chat.py                  chat no terminal para testar Fases 1 e 2 à mão
│  ├─ .env                     ⚠ DATABASE_URL (segredo, fora do Git)
│  ├─ app/
│  │  ├─ config.py             ⭐ pesos, limiares, TTL
│  │  ├─ dependencies.py       ⭐ ponto único de troca da persistência
│  │  ├─ main.py               app FastAPI + serve o frontend compilado
│  │  ├─ domain/               entidades, enums, exceções
│  │  │  └─ acoes.py           ⭐ catálogo fechado de ações e seus textos
│  │  ├─ schemas/              contratos HTTP
│  │  ├─ repositories/
│  │  │  ├─ base.py            ⭐ interfaces abstratas (tudo async)
│  │  │  ├─ seed.py            dados fictícios (memória e banco)
│  │  │  ├─ memory/            implementações em memória (testes)
│  │  │  └─ postgres/          ⭐ implementações PostgreSQL + schema.sql (Fase 3)
│  │  ├─ services/
│  │  │  ├─ orquestrador_service.py  ⭐ caso de uso central
│  │  │  ├─ friccao_service.py       ⭐ os 9 detectores
│  │  │  ├─ nlp_service.py           classificação por regras
│  │  │  ├─ sessao_service.py        continuidade entre canais
│  │  │  ├─ resposta_service.py      respostas do bot
│  │  │  ├─ autoatendimento_service.py  ⭐ execução das ações (Fase 1)
│  │  │  ├─ dialogo_service.py          ⭐ conversa guiada (Fase 2)
│  │  │  └─ ia_service.py               IA como camada de linguagem (Fase 5)
│  │  ├─ routers/              canais, dashboard, health
│  │  └─ core/                 protocolo, normalização de texto
│  └─ tests/                   167 testes
└─ frontend/
   └─ src/
      ├─ api/                  client, endpoints, adapters
      ├─ hooks/                usePolling, useVortex
      ├─ lib/                  friction, formatters, sugestoes, acoes
      ├─ components/
      │  ├─ dashboard/         QueuePanel, ConversationPanel, IntelPanel, MessageList
      │  ├─ gauge/             FrictionGauge (elemento de assinatura)
      │  ├─ simulator/         SimulatorShell (app e whatsapp), ActionCard, RatingCard
      │  └─ ui/                Pill, Button, icons, EmptyState, SectionTitle
      ├─ routes/Dashboard.jsx
      └─ styles/theme.css      ⭐ tokens da identidade Claro
```
