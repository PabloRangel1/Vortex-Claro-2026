# Demandas — evolução para Autoatendimento Funcional

## Objetivo da próxima entrega

Transformar o OrquestraCX de um orquestrador que apenas identifica a intenção e
encaminha para um atendente em um **protótipo funcional de autoatendimento**.

O cliente deve conseguir concluir demandas simples pelo App Claro e pelo
WhatsApp simulado. O handoff humano continua sendo uma saída qualificada: só
ocorre quando a demanda não pode ser resolvida automaticamente, o cliente pede
um humano ou o Score de Fricção atinge o limiar configurado.

> Regra de produto: IA conversa e interpreta; o backend executa ações
> permitidas. A IA nunca altera dados diretamente nem inventa uma solução.

---

## Escopo do MVP funcional

Implementar estes fluxos, nesta ordem:

| Prioridade | Fluxo | Resultado que o cliente vê |
|---:|---|---|
| 1 | Segunda via | Valor, vencimento e código de barras fictício da fatura atual |
| 2 | Alteração de vencimento | Datas possíveis, confirmação e nova data registrada |
| 3 | Diagnóstico de internet | Situação simulada do equipamento e resultado da reinicialização remota |
| 4 | Upgrade de plano | Opções disponíveis, confirmação e plano atualizado |
| 5 | Contestação de cobrança | Contestação criada, protocolo e status `em análise` |

Cancelamento não deve ser automatizado neste MVP. Ele deve receber orientação
e ser encaminhado ao atendimento humano com todo o contexto preservado.

---

## Fase 1 — modelar o que o sistema consegue executar

**Objetivo:** definir ações reais e controladas antes de introduzir IA.

### 1. Criar dados fictícios de operação

Adicionar ao domínio e à persistência dados coerentes para cada cliente:

- fatura atual: referência, valor, vencimento, código de barras e status;
- opções de vencimento permitidas;
- equipamento: identificador, status de conexão e data da última reinicialização;
- catálogo de planos: nome, preço, franquia e linhas incluídas;
- solicitações: tipo, protocolo, status, data e descrição.

Os dados devem ser explicitamente fictícios. Não usar CPF, telefone ou dados
reais em serviços externos de IA.

### 2. Definir o catálogo fechado de ações

Criar uma enumeração de ações de autoatendimento, por exemplo:

```text
GERAR_SEGUNDA_VIA
ALTERAR_VENCIMENTO
DIAGNOSTICAR_CONEXAO
REINICIAR_EQUIPAMENTO
LISTAR_PLANOS
CONFIRMAR_UPGRADE
ABRIR_CONTESTACAO
ENCAMINHAR_HUMANO
```

Cada ação deve ter:

- parâmetros obrigatórios;
- regra de confirmação, quando existir;
- resultado de sucesso legível ao cliente;
- resultado de falha compreensível;
- evento registrado no histórico do atendimento.

### 3. Criar `AutoatendimentoService`

Criar `backend/app/services/autoatendimento_service.py`.

Responsabilidades:

- consultar os dados operacionais do cliente;
- validar se uma ação é permitida;
- executar apenas uma ação do catálogo;
- registrar a ação e seu resultado;
- devolver um resultado estruturado para o orquestrador.

Não colocar regras HTTP, texto de interface ou chamadas de IA nesse serviço.

---

## Fase 2 — tornar a conversa orientada a etapas

**Objetivo:** permitir confirmação e execução em mais de uma mensagem.

Hoje cada mensagem recebe uma resposta isolada. Para autoatendimento, a sessão
precisa guardar um estado de fluxo, por exemplo:

```text
nenhum
aguardando_confirmacao_segunda_via
aguardando_novo_vencimento
aguardando_confirmacao_upgrade
```

### Passos

1. Adicionar à entidade `Sessao` os campos `acao_pendente` e
   `dados_pendentes`.
2. Quando uma ação exigir confirmação, salvar o estado pendente em vez de
   executar imediatamente.
3. Na mensagem seguinte, interpretar confirmação, recusa ou nova dúvida.
4. Executar a ação somente após confirmação explícita.
5. Após sucesso, limpar o estado pendente e registrar uma mensagem de sistema
   na conversa.

### Exemplo — alteração de vencimento

1. Cliente: “Quero mudar meu vencimento.”
2. Sistema: “Posso alterar para os dias 5, 10, 15 ou 20. Qual você prefere?”
3. Cliente: “Dia 15.”
4. Sistema: “Confirma a alteração para o dia 15?”
5. Cliente: “Sim.”
6. `AutoatendimentoService` atualiza o dado e devolve a confirmação final.

---

## Fase 3 — persistência PostgreSQL

**Objetivo:** os resultados sobreviverem ao reinício da API e poderem ser
demonstrados em um site público.

### Decisão recomendada

Usar um único **PostgreSQL no Neon**, no plano gratuito, durante a entrega.
Não implementar Redis e MongoDB agora. Eles permanecem como evolução de escala
documentada, não como dependência do MVP funcional.

### Passos

1. Criar conta e projeto gratuitos no Neon.
2. Copiar a string de conexão e guardá-la como `DATABASE_URL` no `.env` local.
3. Adicionar `DATABASE_URL` em `Settings`, sem expor segredo no Git.
4. Criar as tabelas:
   - `clientes`;
   - `identificadores_cliente`;
   - `sessoes`;
   - `atendimentos`;
   - `mensagens`;
   - `eventos_friccao`;
   - `faturas`;
   - `equipamentos`;
   - `planos`;
   - `solicitacoes`.
5. Implementar os repositórios PostgreSQL respeitando as interfaces de
   `backend/app/repositories/base.py`.
6. Semear os quatro clientes e os dados fictícios apenas quando as tabelas
   estiverem vazias.
7. Alterar o container em `backend/app/dependencies.py` para escolher
   PostgreSQL quando `DATABASE_URL` existir; manter memória como fallback local
   temporário durante o desenvolvimento.

---

## Fase 4 — atualizar o orquestrador e a interface

**Objetivo:** mostrar soluções executadas, não somente mensagens do bot.

### Backend

1. Fazer `OrquestradorService.processar_mensagem` consultar o estado pendente
   da sessão antes de gerar uma resposta comum.
2. Depois da classificação, enviar intenções solucionáveis ao
   `AutoatendimentoService`.
3. Gravar no histórico mensagens de sistema como:
   - “Segunda via gerada”; 
   - “Vencimento alterado para dia 15”; 
   - “Diagnóstico remoto concluído”; 
   - “Contestação aberta”.
4. Incluir no payload HTTP um campo estruturado opcional, como `acao_executada`
   e `dados_acao`, para o frontend não precisar extrair informação de texto.
5. Não alterar o cálculo atual de fricção: ele continua baseado em sinais
   determinísticos e auditáveis.

### Frontend

1. No simulador, exibir cartões para resultados úteis:
   - fatura/código de barras;
   - opções de vencimento;
   - resultado do diagnóstico;
   - planos comparados;
   - protocolo de contestação.
2. Exibir confirmação visual após a ação ser executada.
3. No dashboard, destacar ações já tentadas pelo bot antes do handoff.
4. Manter os dois simuladores usando o mesmo `SimulatorShell` parametrizado.
5. Depois de qualquer alteração em `frontend/src/`, executar `npm run build`
   em `frontend/`, pois o FastAPI serve `frontend/dist`.

---

## Fase 5 — integrar IA como camada de linguagem

**Objetivo:** tornar a conversa natural sem perder controle e previsibilidade.

### Escolha inicial

Usar a Gemini Developer API na camada gratuita para o protótipo, com dados
fictícios. A chave fica em `GEMINI_API_KEY`, apenas no `.env` e nas variáveis
secretas da hospedagem.

### Limites obrigatórios da IA

- Nunca enviar CPF, telefone ou dado real de cliente.
- Nunca permitir que a IA escreva diretamente no banco.
- Nunca permitir que ela execute ação fora do catálogo fechado.
- Nunca deixar a IA decidir score, limiar ou handoff.
- Sempre usar fallback determinístico se a API falhar, demorar ou atingir o
  limite gratuito.

### Implementação

1. Criar `backend/app/services/ia_service.py`.
2. Passar para a IA somente contexto mínimo: intenção, últimas mensagens,
   canal, estado de fluxo e ações permitidas naquele momento.
3. Exigir saída estruturada, com `resposta_cliente`, `acao_sugerida` e
   `parametros`; validar a resposta antes de usá-la.
4. O backend valida a ação sugerida e chama o `AutoatendimentoService`.
5. Se a resposta for inválida ou a API indisponível, usar `RespostaService` e
   manter o fluxo funcionando.
6. No simulador, identificar de forma discreta quando a resposta foi gerada
   por IA, para demonstrar a funcionalidade à banca.

---

## Fase 6 — publicar o protótipo

**Objetivo:** ter uma URL pública para a apresentação.

1. Criar repositório privado ou público no GitHub e enviar apenas o código.
2. Não enviar `.env`, chaves ou a URL do banco.
3. Criar serviço Web gratuito no Render ligado ao repositório.
4. Configurar o comando de inicialização:

```text
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

5. Configurar `DATABASE_URL` e `GEMINI_API_KEY` como variáveis de ambiente
secretas no Render.
6. Garantir que `frontend/dist` esteja disponível no deploy, pois o backend
serve a interface compilada.
7. Abrir a URL alguns minutos antes da apresentação: serviços gratuitos podem
hibernar quando ficam sem acesso.

---

## Critérios de demonstração

A entrega estará pronta para apresentar quando for possível demonstrar esta
jornada, usando somente dados fictícios:

1. Cliente pede segunda via no App e recebe dados da fatura.
2. Cliente muda para WhatsApp e o mesmo protocolo/histórico é recuperado.
3. Cliente altera o vencimento após confirmar a operação.
4. Cliente cria uma contestação ou solicita diagnóstico.
5. Cliente demonstra frustração; o score cresce de forma explicável.
6. Quando a resolução automática falha ou a fricção sobe, o sistema faz
   handoff com contexto e ações anteriores visíveis no dashboard.
7. Após reiniciar a API, o atendimento e o histórico continuam disponíveis.

---

## Fora de escopo por enquanto

- WhatsApp oficial da Meta e envio real de mensagens;
- ligação telefônica, transcrição de áudio ou voz sintetizada;
- integração com sistemas reais da Claro;
- Redis e MongoDB;
- dados pessoais reais;
- automação de cancelamento;
- autenticação e produção em escala;
