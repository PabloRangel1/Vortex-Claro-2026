// Cada canal usa a cor da sua própria marca; bot e atendente ficam em neutro
// e vermelho, de modo que o vermelho sempre signifique "Claro / humano".
// No claro os chips levam texto escuro sobre lavagem clara da própria cor —
// texto pálido, que funcionava no fundo preto, aqui sumiria.
const VARIANTES = {
  app: 'bg-claro/8 text-claro-hi border-claro/30',
  whatsapp: 'bg-wpp/8 text-wpp border-wpp/35',
  bot: 'bg-bot/8 text-bot border-bot/28',
  atendente: 'bg-claro text-white border-claro',
  neutro: 'bg-void text-txt-dim border-border',
}

export function Pill({ variante = 'neutro', children, className = '' }) {
  return (
    <span
      className={`font-display inline-block rounded-[5px] border px-[7px] py-[2.5px] text-rotulo
        font-extrabold tracking-[0.7px] whitespace-nowrap uppercase ${VARIANTES[variante] ?? VARIANTES.neutro} ${className}`}
    >
      {children}
    </span>
  )
}

/** Pill de canal, resolvendo o rótulo a partir do enum da API. */
export function PillCanal({ canal, curto = false }) {
  if (!canal) return null
  const rotulo = canal === 'app' ? (curto ? 'APP' : 'APP CLARO') : curto ? 'WA' : 'WHATSAPP'
  return <Pill variante={canal}>{rotulo}</Pill>
}
