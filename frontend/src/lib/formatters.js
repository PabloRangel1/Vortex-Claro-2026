/** Formatação de dados para exibição. */

export function segundosParaMMSS(total) {
  if (total == null || total < 0) return '—'
  // Acima de 1 hora, segundos viram ruído: "31h54m", não "1914m00s".
  if (total >= 3600) {
    const h = Math.floor(total / 3600)
    const m = Math.floor((total % 3600) / 60)
    return `${h}h${String(m).padStart(2, '0')}m`
  }
  const m = Math.floor(total / 60)
  const s = Math.floor(total % 60)
  return `${m}m${String(s).padStart(2, '0')}s`
}

export function horaCurta(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

export function iniciais(nome) {
  if (!nome) return '?'
  return nome
    .split(' ')
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0])
    .join('')
    .toUpperCase()
}

export function primeiroNome(nome) {
  return nome?.split(' ')[0] ?? ''
}

/** Segundos decorridos desde um instante ISO, contados no cliente. */
export function segundosDesde(iso) {
  if (!iso) return 0
  return Math.max(0, Math.floor((Date.now() - new Date(iso).getTime()) / 1000))
}
