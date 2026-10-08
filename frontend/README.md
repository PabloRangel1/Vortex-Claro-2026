# Vortex — Frontend

React + Vite + Tailwind v4. Consome a API FastAPI de `../backend`.

---

## Como rodar

Precisa de **dois terminais**. Backend primeiro:

```bash
cd ../backend
.venv/Scripts/python.exe -m uvicorn app.main:app --reload
```

Depois o frontend:

```bash
npm install       # só na primeira vez
npm run dev
```

Abra **http://localhost:5173**.

> Use `localhost`, não `127.0.0.1` — o Vite não escuta no IPv4 loopback por padrão.

O `vite.config.js` faz proxy de `/api/*` para `http://127.0.0.1:8000`, então **não há
CORS em desenvolvimento**. Para apontar direto ao backend, copie `.env.example` para
`.env` e ajuste `VITE_API_BASE_URL`.

---

## Telas

| Rota | Tela |
|---|---|
| `/` | Dashboard do atendente — fila, conversa, painel de inteligência |
| `/sim/app` | Simulador do App Claro |
| `/sim/whatsapp` | Simulador do WhatsApp |

### Roteiro de demonstração

1. Abra `/sim/app`, escolha **Ana Beatriz Souza**, envie "Minha fatura veio errada".
2. Repita a demanda com outras palavras — o backend detecta repetição, score sobe.
3. Vá para `/sim/whatsapp` (mesma cliente) e escreva algo — **troca de canal detectada**,
   mesmo protocolo, +16 no score.
4. Envie "Quero falar com uma pessoa" — o score cruza 70 e o **handoff dispara**.
5. Volte ao Dashboard: a cliente aparece na fila em até 4s, com o histórico dos dois
   canais costurado, o divisor de troca na timeline e o gauge animando até o valor novo.
6. Responda como atendente — o score cai 12 pontos e a resposta aparece **dentro do
   celular do cliente**, nos dois simuladores.

Para zerar entre apresentações: `curl -X POST localhost:8000/reset`.

---

## Arquitetura

```
src/
├─ api/
│  ├─ client.js      fetch wrapper: baseURL, timeout 8s, erro normalizado (ApiError)
│  ├─ endpoints.js   uma função por endpoint
│  └─ adapters.js    payload snake_case da API → view models camelCase
├─ hooks/
│  ├─ usePolling.js       polling genérico (ver abaixo)
│  └─ useVortex.js   useFila, useAtendimento, useCanal, useClientes...
├─ components/
│  ├─ ui/          Pill, Button, SectionTitle, EmptyState, icons
│  ├─ gauge/       FrictionGauge — elemento de assinatura
│  ├─ dashboard/   QueuePanel, ConversationPanel, MessageList, IntelPanel
│  └─ simulator/   SimulatorShell (um componente, duas variantes)
├─ lib/            formatters, friction (faixas de cor)
├─ routes/         Dashboard
└─ styles/         theme.css — tokens em @theme
```

**`adapters.js` é a fronteira.** Nenhum componente lê `score_friccao` ou
`canal_origem_rotulo` direto: se o backend renomear um campo, o conserto é num
arquivo só.

### `usePolling`

Não é um `setInterval`. Faz seis coisas que importam:

1. **Guard de sobreposição** — se a resposta anterior não voltou, pula o tick.
   Sem isso, backend lento vira pilha de requests no meio da apresentação.
2. **Pausa em aba oculta** — `document.hidden` congela; ao voltar, refetch imediato.
3. **Backoff exponencial em erro** — dobra o intervalo até 30s, reseta no sucesso.
4. **Sem flicker** — mantém os dados anteriores enquanto revalida; só o indicador
   de conexão na TopBar muda de cor.
5. **`refetch()`** para uso após mutações — a latência percebida cai a zero.
6. **Cleanup completo** — aborta a requisição em voo e limpa o timer no unmount.

Intervalos: fila 4s, atendimento 3s (configuráveis no `.env`).

### O gauge

`FrictionGauge` — arco de 180° em SVG, com: trilho + arco animado em
`cubic-bezier(.16,1,.3,1)`, ticks a cada 10 pontos que acendem conforme o
preenchimento, cor por faixa (verde <40 · amarelo 40–69 · vermelho ≥70),
`drop-shadow` que só liga em estado crítico, count-up do número via `requestAnimationFrame`,
badge de nível, delta desde o início e sparkline da trajetória.

Acessível: `role="meter"` com `aria-valuenow/min/max` e respeito a
`prefers-reduced-motion` (o número salta em vez de animar).

### Simuladores

`SimulatorShell` é **um** componente parametrizado por `variante` — muda chrome,
bolhas, identificador e endpoint. Duas telas separadas divergiriam com o tempo.

A conversa vem inteira do servidor, não há histórico local: é por isso que uma
resposta escrita no dashboard aparece dentro do celular do cliente em segundos.
Mensagens de sistema (`troca_canal`, `handoff`) são filtradas na visão do
cliente — ele não vê "handoff acionado", vê o bot mudando de tom.

---

## Tokens de design

Definidos em `src/styles/theme.css` via `@theme` do Tailwind v4 — viram
utilitários (`bg-panel`, `text-accent-hi`, `font-display`).

| Papel | Token | Valor |
|---|---|---|
| Fundo | `--color-void` | `#0a0e17` |
| Painéis | `--color-panel` | `#111827` |
| Cards | `--color-elev` | `#161f30` |
| Acento / crítico | `--color-accent` | `#e11d2e` |
| Cliente / neutro | `--color-client` | `#3b82f6` |
| Estável | `--color-ok` | `#22c55e` |
| Atenção | `--color-warn` | `#f59e0b` |

Tipografia: **Sora** (headers) · **DM Sans** (corpo) · **JetBrains Mono** (dados).
Todo número e identificador usa a classe `num`, que aplica mono + `tabular-nums`
— é o que dá a leitura de instrumento ao painel.

---

## Notas

- **Responsivo para projetor/notebook**, não mobile-first: as colunas laterais
  encolhem abaixo de 1500px. É ferramenta interna.
- **Sem gerenciador de estado global.** A API é a fonte da verdade e o polling
  mantém tudo sincronizado; `useState` local basta.
- **Sem biblioteca de ícones** — SVGs inline em `ui/icons.jsx`. Bundle final:
  205 kB (66 kB gzip).
