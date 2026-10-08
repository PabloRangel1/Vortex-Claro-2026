import { useEffect, useRef, useState } from 'react'

/**
 * Peças comuns dos gráficos (SVG à mão, sem biblioteca).
 *
 * Especificação seguida (skill dataviz): barras finas (<= 24px) com ponta
 * arredondada de 4px e base reta; 2px de respiro entre segmentos; linhas de
 * 2px; grade em hairline sólida e recessiva; texto sempre em tokens de texto
 * (nunca na cor da série); legenda para 2+ séries; tooltip no hover; e uma
 * visão em tabela — obrigatória porque uma das cores tem contraste < 3:1.
 */

/** Largura real do contêiner, para o SVG desenhar em pixels de verdade. */
export function useLargura() {
  const ref = useRef(null)
  const [largura, setLargura] = useState(0)
  useEffect(() => {
    if (!ref.current) return
    const obs = new ResizeObserver(([e]) => setLargura(Math.floor(e.contentRect.width)))
    obs.observe(ref.current)
    return () => obs.disconnect()
  }, [])
  return [ref, largura]
}

/** Teto "redondo" para o eixo: 7 -> 8, 23 -> 25, 61 -> 80. */
export function tetoRedondo(maximo) {
  if (maximo <= 0) return 1
  const passos = [1, 2, 2.5, 4, 5, 8, 10]
  const escala = 10 ** Math.floor(Math.log10(maximo))
  return passos.map((p) => p * escala).find((v) => v >= maximo) ?? 10 * escala
}

export function Legenda({ series }) {
  return (
    <ul className="flex flex-wrap gap-x-4 gap-y-1">
      {series.map((s) => (
        <li key={s.chave} className="text-txt-dim flex items-center gap-[6px] text-apoio">
          <span className="size-[10px] rounded-[3px]" style={{ background: s.cor }} />
          {s.rotulo}
          {s.total != null && <b className="num text-txt-hi">{s.total}</b>}
        </li>
      ))}
    </ul>
  )
}

/** Tooltip posicionado sobre o gráfico (coordenadas do contêiner). */
export function Dica({ x, y, largura, children }) {
  const esquerda = Math.min(Math.max(x - 90, 0), Math.max(largura - 180, 0))
  return (
    <div
      role="status"
      className="bg-txt-hi pointer-events-none absolute z-10 w-[180px] rounded-lg px-3 py-2 text-apoio text-white shadow-lg"
      style={{ left: esquerda, top: Math.max(y - 8, 0), transform: 'translateY(-100%)' }}
    >
      {children}
    </div>
  )
}

/** Moldura com título, legenda e alternância gráfico/tabela. */
export function Grafico({ titulo, subtitulo, legenda, tabela, children, acao }) {
  const [comoTabela, setComoTabela] = useState(false)
  return (
    <section className="bg-panel border-border rounded-2xl border p-5 shadow-[var(--shadow-cartao)]">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="font-display text-txt-hi text-[15px] font-bold">{titulo}</h3>
          {subtitulo && <p className="text-txt-dim mt-[2px] text-apoio">{subtitulo}</p>}
        </div>
        <div className="flex items-center gap-3">
          {acao}
          {tabela && (
            <button
              type="button"
              onClick={() => setComoTabela((v) => !v)}
              aria-pressed={comoTabela}
              className="text-claro-hi cursor-pointer text-apoio font-semibold hover:underline"
            >
              {comoTabela ? 'Ver gráfico' : 'Ver como tabela'}
            </button>
          )}
        </div>
      </div>
      {legenda && !comoTabela && <div className="mt-3">{legenda}</div>}
      <div className="mt-4">
        {comoTabela ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-apoio">
              <thead>
                <tr className="border-border text-txt-ghost border-b">
                  {tabela.colunas.map((c) => (
                    <th key={c} className="py-2 pr-4 font-semibold">
                      {c}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {tabela.linhas.map((linha, i) => (
                  <tr key={i} className="border-border-soft border-b last:border-0">
                    {linha.map((v, j) => (
                      <td key={j} className={`py-2 pr-4 ${j ? 'num text-txt-hi' : 'text-txt'}`}>
                        {v}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          children
        )}
      </div>
    </section>
  )
}

/** Caminho de barra com topo arredondado (4px) e base reta. */
export function caminhoBarra(x, y, largura, altura, raio = 4) {
  if (altura <= 0) return ''
  const r = Math.min(raio, altura, largura / 2)
  return `M${x},${y + altura} V${y + r} Q${x},${y} ${x + r},${y} H${x + largura - r} Q${x + largura},${y} ${x + largura},${y + r} V${y + altura} Z`
}
