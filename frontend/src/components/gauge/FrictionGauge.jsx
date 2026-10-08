import { useEffect, useRef, useState } from 'react'

import { faixaDe } from '../../lib/friction'

const RAIO = 84
const CX = 105
const CY = 104
const COMPRIMENTO = Math.PI * RAIO

/** Count-up suave do número central. Salta direto se o usuário pediu menos movimento. */
function useContagem(alvo, duracao = 950) {
  const [valor, setValor] = useState(alvo)
  const anterior = useRef(alvo)

  useEffect(() => {
    const reduzir = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
    if (reduzir) {
      setValor(alvo)
      anterior.current = alvo
      return
    }

    const inicio = performance.now()
    const partida = anterior.current
    let quadro

    const passo = (t) => {
      const p = Math.min((t - inicio) / duracao, 1)
      const eased = 1 - (1 - p) ** 3
      setValor(Math.round(partida + (alvo - partida) * eased))
      if (p < 1) quadro = requestAnimationFrame(passo)
      else anterior.current = alvo
    }

    quadro = requestAnimationFrame(passo)
    return () => cancelAnimationFrame(quadro)
  }, [alvo, duracao])

  return valor
}

function Ticks({ score, cor }) {
  return Array.from({ length: 11 }, (_, i) => {
    const angulo = Math.PI - (i / 10) * Math.PI
    const externo = i % 5 === 0 ? 17 : 14
    const aceso = i * 10 <= score
    return (
      <line
        key={i}
        x1={CX + Math.cos(angulo) * (RAIO + 11)}
        y1={CY - Math.sin(angulo) * (RAIO + 11)}
        x2={CX + Math.cos(angulo) * (RAIO + externo)}
        y2={CY - Math.sin(angulo) * (RAIO + externo)}
        stroke={aceso ? cor : '#ddd6d7'}
        strokeWidth={i % 5 === 0 ? 1.8 : 1.1}
        opacity={aceso ? 0.85 : 0.5}
        style={{ transition: 'stroke .5s' }}
      />
    )
  })
}

function Sparkline({ historico, cor }) {
  if (!historico || historico.length < 2) return null
  const L = 300
  const A = 30
  const pontos = historico
    .map((v, i) => `${(i / (historico.length - 1)) * L},${A - (v / 100) * A}`)
    .join(' ')
  const ultimo = historico.at(-1)

  return (
    <svg
      viewBox={`0 0 ${L} ${A}`}
      preserveAspectRatio="none"
      className="mt-[11px] block h-[34px] w-full"
      aria-label="Evolução do score ao longo do atendimento"
    >
      <polyline
        points={pontos}
        fill="none"
        stroke={cor}
        strokeWidth={1.8}
        strokeLinejoin="round"
        opacity={0.75}
      />
      <circle cx={L} cy={A - (ultimo / 100) * A} r={2.6} fill={cor} />
    </svg>
  )
}

/**
 * Gauge semicircular do Score de Fricção — elemento de assinatura do produto.
 *
 * Resume a proposta de valor num objeto só: o quanto o cliente está frustrado,
 * o quanto piorou desde o início e a trajetória que levou até ali.
 */
export function FrictionGauge({ score = 0, nivel = 'estavel', delta = 0, historico = [] }) {
  const faixa = faixaDe(nivel)
  const exibido = useContagem(score)
  const critico = nivel === 'critico'
  const offset = COMPRIMENTO - (score / 100) * COMPRIMENTO

  return (
    <div className="flex flex-col items-center pt-1">
      <div className="relative h-[118px] w-[210px]">
        <svg
          viewBox="0 0 210 118"
          className="absolute inset-0 overflow-visible"
          role="meter"
          aria-valuenow={score}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label={`Score de fricção: ${score} de 100, nível ${faixa.rotulo}`}
        >
          <defs>
            <filter id="brilho-gauge" x="-60%" y="-60%" width="220%" height="220%">
              <feGaussianBlur stdDeviation="5" result="b" />
              <feMerge>
                <feMergeNode in="b" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          </defs>

          <Ticks score={score} cor={faixa.cor} />

          <path
            d={`M ${CX - RAIO} ${CY} A ${RAIO} ${RAIO} 0 0 1 ${CX + RAIO} ${CY}`}
            fill="none"
            stroke="#e8e2e3"
            strokeWidth={13}
            strokeLinecap="round"
          />
          <path
            d={`M ${CX - RAIO} ${CY} A ${RAIO} ${RAIO} 0 0 1 ${CX + RAIO} ${CY}`}
            fill="none"
            stroke={faixa.cor}
            strokeWidth={13}
            strokeLinecap="round"
            strokeDasharray={COMPRIMENTO}
            strokeDashoffset={offset}
            filter={critico ? 'url(#brilho-gauge)' : undefined}
            style={{
              transition: 'stroke-dashoffset 1.05s cubic-bezier(.16,1,.3,1), stroke .5s',
            }}
          />
        </svg>

        <div className="pointer-events-none absolute inset-x-0 bottom-[2px] text-center">
          <span
            className="num block text-[44px] leading-none font-extrabold tracking-[-2px]"
            style={{ color: faixa.cor, transition: 'color .5s' }}
          >
            {exibido}
          </span>
          <span className="text-txt-ghost mt-[5px] block text-rotulo font-bold tracking-[1.6px] uppercase">
            de 100 pontos
          </span>
        </div>
      </div>

      <span
        className="font-display mt-[2px] rounded-full border px-[18px] py-[5px] text-rotulo font-extrabold tracking-[1.2px]"
        style={{ background: faixa.fundo, color: faixa.cor, borderColor: faixa.borda }}
      >
        {faixa.rotulo}
      </span>

      <div
        className="num mt-[9px] flex items-center gap-[5px] text-apoio font-bold"
        style={{ color: delta > 0 ? faixa.cor : 'var(--color-ok)' }}
      >
        <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.6} strokeLinecap="round" aria-hidden="true">
          <path d={delta > 0 ? 'M12 19V5m0 0l-6 6m6-6l6 6' : 'M12 5v14m0 0l6-6m-6 6l-6-6'} />
        </svg>
        {delta > 0 ? '+' : ''}
        {delta} desde o início do atendimento
      </div>

      <Sparkline historico={historico} cor={faixa.cor} />
    </div>
  )
}
