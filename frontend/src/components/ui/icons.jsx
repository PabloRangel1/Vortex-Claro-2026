/** Ícones inline — evita dependência externa e mantém o bundle enxuto. */

const svg = (d, extras = {}) =>
  function Icone({ size = 12, className = '', ...props }) {
    return (
      <svg
        width={size}
        height={size}
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth={2}
        strokeLinecap="round"
        strokeLinejoin="round"
        className={className}
        aria-hidden="true"
        {...extras}
        {...props}
      >
        {typeof d === 'string' ? <path d={d} /> : d}
      </svg>
    )
  }

export const IconeRaio = svg('M13 2L3 14h9l-1 8 10-12h-9l1-8z')
export const IconeSeta = svg('M5 12h14m0 0l-5-5m5 5l-5 5')
export const IconeTroca = svg('M8 7h12m0 0l-4-4m4 4l-4 4M16 17H4m0 0l4 4m-4-4l4-4')
export const IconeX = svg('M6 18L18 6M6 6l12 12')
export const IconeEnviar = svg('M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z')
export const IconeRelogio = svg(
  <>
    <circle cx="12" cy="12" r="9" />
    <path d="M12 7v5l3 2" />
  </>,
)
export const IconeBusca = svg(
  <>
    <circle cx="11" cy="11" r="7" />
    <path d="M21 21l-4.3-4.3" />
  </>,
)
export const IconeUsuario = svg(
  <>
    <path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2" />
    <circle cx="12" cy="7" r="4" />
  </>,
)
export const IconeUsuarios = svg(
  'M17 20h5v-2a3 3 0 00-5.4-1.8M17 20H7m10 0v-2c0-.7-.1-1.3-.4-1.8M7 20H2v-2a3 3 0 015.4-1.8M7 20v-2c0-.7.1-1.3.4-1.8m0 0a5 5 0 019.2 0M15 7a3 3 0 11-6 0 3 3 0 016 0z',
)
export const IconeIdeia = svg(
  'M9.7 17h4.6M12 3a6 6 0 00-3.5 10.9c.3.3.5.7.5 1.1h6c0-.4.2-.8.5-1.1A6 6 0 0012 3z',
)
export const IconeChat = svg('M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z')
export const IconeAlerta = svg(
  <>
    <path d="M12 9v4M12 17h.01" />
    <path d="M10.3 3.9L1.8 18a2 2 0 001.7 3h17a2 2 0 001.7-3L13.7 3.9a2 2 0 00-3.4 0z" />
  </>,
)
export const IconeVoltar = svg('M15 18l-6-6 6-6')
export const IconeCheck = svg('M20 6L9 17l-5-5')
export const IconeCheckDuplo = svg('M2 12l5 5L18 6m-5 11l1 1L22 9')
export const IconeBrilho = svg(
  'M12 3l1.9 5.6L19.5 10.5 13.9 12.4 12 18l-1.9-5.6L4.5 10.5l5.6-1.9L12 3z',
)
export const IconeMenuLateral = svg(
  <>
    <rect x="3" y="4" width="18" height="16" rx="2" />
    <path d="M15 4v16" />
  </>,
)

// ------------------------------------------------------------- intenções
// Um ícone por intenção do NLP. Substituem emojis: emoji muda de desenho a
// cada sistema operacional e destoava do traço fino do resto da interface.

const IconeWifi = svg('M2 8.8a15 15 0 0120 0M5 12.3a10 10 0 0114 0M8.5 15.9a5 5 0 017 0M12 19.5h.01')
const IconeCartao = svg(
  <>
    <rect x="2" y="5" width="20" height="14" rx="2" />
    <path d="M2 10h20M6 15h4" />
  </>,
)
const IconeRecibo = svg(
  <>
    <path d="M5 3h14v18l-2.5-1.5L14 21l-2-1.5-2 1.5-2.5-1.5L5 21V3z" />
    <path d="M12 8v4M12 15h.01" />
  </>,
)
const IconeDocumento = svg(
  <>
    <path d="M14 3H7a2 2 0 00-2 2v14a2 2 0 002 2h10a2 2 0 002-2V8l-5-5z" />
    <path d="M14 3v5h5M9 13h6M9 17h4" />
  </>,
)
const IconeSinal = svg('M4 20v-3M9 20v-7M14 20V9M19 20V4')
const IconePorta = svg('M14 4h4a2 2 0 012 2v12a2 2 0 01-2 2h-4M3 12h11m0 0l-4-4m4 4l-4 4')
const IconeAjuda = svg(
  <>
    <circle cx="12" cy="12" r="9" />
    <path d="M9.5 9.5a2.5 2.5 0 014.6 1.3c0 1.7-2.1 2-2.1 3.4M12 17h.01" />
  </>,
)

const POR_INTENCAO = {
  suporte_tecnico: IconeWifi,
  financeiro: IconeCartao,
  contestacao_fatura: IconeRecibo,
  segunda_via: IconeDocumento,
  planos_upgrade: IconeSinal,
  cancelamento: IconePorta,
  outros: IconeAjuda,
}

export function IconeIntencao({ intencao, ...props }) {
  const Icone = POR_INTENCAO[intencao] ?? IconeAjuda
  return <Icone {...props} />
}

export const IconeReiniciar = svg('M3 12a9 9 0 0115.5-6.2L21 8M21 3v5h-5M21 12a9 9 0 01-15.5 6.2L3 16M3 21v-5h5')
