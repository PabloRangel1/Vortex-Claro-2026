import { useState } from 'react'

import { Dica, useLargura } from './Grafico'

const ALTURA = 210
const MARGEM = { topo: 14, baixo: 26, esquerda: 30, direita: 24 }

/**
 * Uma série no tempo (fricção média por dia), com as linhas de referência dos
 * limiares. Dia sem atendimento é lacuna — não vira zero.
 */
export function LinhaFriccao({ dados, referencias, cor, rotuloDica }) {
  const [ref, largura] = useLargura()
  const [foco, setFoco] = useState(null)

  const areaL = Math.max(largura - MARGEM.esquerda - MARGEM.direita, 0)
  const areaA = ALTURA - MARGEM.topo - MARGEM.baixo
  const passo = dados.length > 1 ? areaL / (dados.length - 1) : 0
  const x = (i) => MARGEM.esquerda + passo * i
  const y = (v) => MARGEM.topo + areaA - (v / 100) * areaA

  // Trechos contínuos (quebra onde o dia não tem dado).
  const trechos = []
  let atual = []
  dados.forEach((d, i) => {
    if (d.valor == null) {
      if (atual.length) trechos.push(atual)
      atual = []
    } else atual.push([x(i), y(d.valor)])
  })
  if (atual.length) trechos.push(atual)
  const ultimo = [...dados].reverse().find((d) => d.valor != null)
  const iUltimo = dados.lastIndexOf(ultimo)

  return (
    <div ref={ref} className="relative" onMouseLeave={() => setFoco(null)}>
      {largura > 0 && (
        <svg width={largura} height={ALTURA} role="img" aria-label="Fricção média por dia">
          {[0, 50, 100].map((t) => (
            <g key={t}>
              <line x1={MARGEM.esquerda} x2={largura - MARGEM.direita} y1={y(t)} y2={y(t)} stroke="var(--color-border-soft)" />
              <text x={MARGEM.esquerda - 8} y={y(t) + 4} textAnchor="end" className="num fill-txt-ghost text-rotulo">
                {t}
              </text>
            </g>
          ))}
          {referencias.map((r) => (
            <g key={r.valor}>
              <line
                x1={MARGEM.esquerda}
                x2={largura - MARGEM.direita}
                y1={y(r.valor)}
                y2={y(r.valor)}
                stroke={r.cor}
                strokeOpacity={0.55}
              />
              {/* rótulo dentro do gráfico, à esquerda: o lado direito é do valor final */}
              <text x={MARGEM.esquerda + 6} y={y(r.valor) - 5} className="fill-txt-dim text-rotulo font-semibold">
                {r.rotulo} · {r.valor}
              </text>
            </g>
          ))}
          {trechos.map((t, i) =>
            t.length > 1 ? (
              <polyline
                key={i}
                points={t.map((p) => p.join(',')).join(' ')}
                fill="none"
                stroke={cor}
                strokeWidth={2}
                strokeLinejoin="round"
                strokeLinecap="round"
              />
            ) : null,
          )}
          {dados.map((d, i) =>
            d.valor == null ? null : (
              <circle
                key={i}
                cx={x(i)}
                cy={y(d.valor)}
                r={foco === i || i === iUltimo ? 5 : 3.5}
                fill={cor}
                stroke="var(--color-panel)"
                strokeWidth={2}
              />
            ),
          )}
          {ultimo && (
            <text x={x(iUltimo)} y={y(ultimo.valor) - 10} textAnchor="middle" className="num fill-txt-hi text-[11px] font-bold">
              {Math.round(ultimo.valor)}
            </text>
          )}
          {dados.map((d, i) => (
            <g key={`h${i}`}>
              <text x={x(i)} y={ALTURA - 8} textAnchor="middle" className="num fill-txt-ghost text-rotulo">
                {d.rotulo}
              </text>
              <rect
                x={x(i) - passo / 2}
                y={MARGEM.topo}
                width={Math.max(passo, 1)}
                height={areaA}
                fill="transparent"
                onMouseEnter={() => setFoco(i)}
              />
            </g>
          ))}
          {foco != null && (
            <line x1={x(foco)} x2={x(foco)} y1={MARGEM.topo} y2={MARGEM.topo + areaA} stroke="var(--color-border)" />
          )}
        </svg>
      )}
      {foco != null && (
        <Dica largura={largura} x={x(foco)} y={dados[foco].valor == null ? MARGEM.topo + 40 : y(dados[foco].valor)}>
          {rotuloDica(dados[foco])}
        </Dica>
      )}
    </div>
  )
}
