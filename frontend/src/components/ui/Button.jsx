const BASE =
  'inline-flex items-center gap-[6px] rounded-lg text-[11px] font-bold transition-[0.16s] ' +
  'cursor-pointer whitespace-nowrap disabled:opacity-40 disabled:cursor-not-allowed'

const VARIANTES = {
  primario:
    'bg-claro border border-claro text-white shadow-[0_2px_8px_rgb(227_6_19/0.22)] ' +
    'hover:enabled:bg-claro-hi hover:enabled:shadow-[0_3px_12px_rgb(227_6_19/0.32)]',
  secundario:
    'bg-elev border border-border text-txt-dim ' +
    'hover:enabled:border-claro/25 hover:enabled:text-txt-hi hover:enabled:bg-void',
  // Ação que não se desfaz (encerrar). Na cor de status "crítico", não na da
  // marca: o vermelho Claro é identidade, este é aviso.
  perigo:
    'bg-elev border border-crit/35 text-crit ' +
    'hover:enabled:bg-crit/8 hover:enabled:border-crit/60',
  perigoSolido:
    'bg-crit border border-crit text-white hover:enabled:brightness-110',
}

export function Button({
  variante = 'secundario',
  className = '',
  padding = 'px-[13px] py-[8px]',
  ...props
}) {
  return (
    <button className={`${BASE} ${VARIANTES[variante]} ${padding} ${className}`} {...props} />
  )
}
