import { useState } from 'react'

import { Dica, caminhoBarra, tetoRedondo, useLargura } from './Grafico'

const ALTURA = 210
const MARGEM = { topo: 18, baixo: 26, esquerda: 30, direita: 6 }
const GAP = 2 // respiro entre segmentos empilhados

/**
 * Colunas empilhadas (parte do todo por dia). `series` em ordem fixa de baixo
 * para cima; a cor segue a série, nunca a posição.
 */
export function ColunasEmpilhadas({ dados, series, rotuloDica }) {
  const [ref, largura] = useLargura()
  const [foco, setFoco] = useState(null)

  const teto = tetoRedondo(Math.max(...dados.map((d) => d.total), 0))
  const areaL = Math.max(largura - MARGEM.esquerda - MARGEM.direita, 0)
  const areaA = ALTURA - MARGEM.topo - MARGEM.baixo
  const faixa = dados.length ? areaL / dados.length : 0
  const barra = Math.min(24, faixa * 0.55)
  const y = (v) => MARGEM.topo + areaA - (v / teto) * areaA
  // Contagem não tem meio atendimento: só marcas inteiras no eixo.
  const ticks = Number.isInteger(teto / 2) ? [0, teto / 2, teto] : [0, teto]
  // Rótulo seletivo: só o pico e o último dia.
  const pico = dados.reduce((m, d, i) => (d.total > dados[m].total ? i : m), 0)

  return (
    <div ref={ref} className="relative" onMouseLeave={() => setFoco(null)}>
      {largura > 0 && (
        <svg width={largura} height={ALTURA} role="img" aria-label="Atendimentos por dia, por desfecho">
          {ticks.map((t) => (
            <g key={t}>
              <line
                x1={MARGEM.esquerda}
                x2={largura - MARGEM.direita}
                y1={y(t)}
                y2={y(t)}
                stroke="var(--color-border-soft)"
                strokeWidth={1}
              />
              <text x={MARGEM.esquerda - 8} y={y(t) + 4} textAnchor="end" className="num fill-txt-ghost text-rotulo">
                {t}
              </text>
            </g>
          ))}

          {dados.map((d, i) => {
            const cx = MARGEM.esquerda + faixa * i + faixa / 2
            const x = cx - barra / 2
            let acumulado = 0
            const visiveis = series.filter((s) => d.valores[s.chave] > 0)
            return (
              <g key={d.rotulo} opacity={foco == null || foco === i ? 1 : 0.45}>
                {visiveis.map((s, k) => {
                  const v = d.valores[s.chave]
                  const topo = y(acumulado + v)
                  const base = y(acumulado)
                  acumulado += v
                  const ultimo = k === visiveis.length - 1
                  const altura = Math.max(base - topo - (k > 0 ? GAP : 0), 0)
                  return ultimo ? (
                    <path key={s.chave} d={caminhoBarra(x, topo, barra, altura)} fill={s.cor} />
                  ) : (
                    <rect key={s.chave} x={x} y={topo} width={barra} height={altura} fill={s.cor} />
                  )
                })}
                {(i === pico || i === dados.length - 1) && d.total > 0 && (
                  <text x={cx} y={y(d.total) - 6} textAnchor="middle" className="num fill-txt-hi text-[11px] font-bold">
                    {d.total}
                  </text>
                )}
                <text x={cx} y={ALTURA - 8} textAnchor="middle" className="num fill-txt-ghost text-rotulo">
                  {d.rotulo}
                </text>
                {/* alvo de hover: a faixa inteira, maior que a barra */}
                <rect
                  x={MARGEM.esquerda + faixa * i}
                  y={MARGEM.topo}
                  width={faixa}
                  height={areaA}
                  fill="transparent"
                  onMouseEnter={() => setFoco(i)}
                />
              </g>
            )
          })}
        </svg>
      )}
      {foco != null && (
        <Dica
          largura={largura}
          x={MARGEM.esquerda + faixa * foco + faixa / 2}
          y={y(dados[foco].total)}
        >
          <p className="mb-1 font-bold">{rotuloDica(dados[foco])}</p>
          {series.map((s) => (
            <p key={s.chave} className="flex items-center justify-between gap-2">
              <span className="flex items-center gap-[6px]">
                <span className="size-2 rounded-sm" style={{ background: s.cor }} />
                {s.rotulo}
              </span>
              <b className="num">{dados[foco].valores[s.chave]}</b>
            </p>
          ))}
        </Dica>
      )}
    </div>
  )
}
