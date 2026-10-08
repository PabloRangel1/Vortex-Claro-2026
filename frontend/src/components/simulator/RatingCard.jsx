import { useState } from 'react'

/**
 * Avaliação do atendimento (CSAT), exibida no aparelho do cliente depois do
 * encerramento.
 *
 * As carinhas são SVG e não emoji: emoji muda de desenho a cada sistema
 * operacional e quebra a consistência da marca. Desenhadas aqui, a expressão
 * acompanha a cor da faixa e o conjunto fica previsível em qualquer tela.
 */

const NIVEIS = [
  { nota: 1, rotulo: 'Muito insatisfeito', cor: '#b01020', boca: 'M8 17.5q4-4 8 0', olho: 2.0 },
  { nota: 2, rotulo: 'Insatisfeito', cor: '#c4542a', boca: 'M8 16.8q4-2.2 8 0', olho: 1.9 },
  { nota: 3, rotulo: 'Neutro', cor: '#9c6a00', boca: 'M8 16h8', olho: 1.8 },
  { nota: 4, rotulo: 'Satisfeito', cor: '#4a8a3c', boca: 'M8 15.2q4 2.2 8 0', olho: 1.9 },
  { nota: 5, rotulo: 'Muito satisfeito', cor: '#008a4e', boca: 'M8 14.6q4 4 8 0', olho: 2.0 },
]

function Carinha({ nivel, ativa, size = 34 }) {
  const cor = ativa ? nivel.cor : 'currentColor'
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
      style={{ transition: 'transform .2s cubic-bezier(.16,1,.3,1)' }}
    >
      <circle
        cx="12" cy="12" r="10"
        stroke={cor}
        strokeWidth={ativa ? 1.8 : 1.4}
        fill={ativa ? cor : 'none'}
        fillOpacity={ativa ? 0.1 : 0}
      />
      <circle cx="8.6" cy="9.8" r={nivel.olho} fill={cor} />
      <circle cx="15.4" cy="9.8" r={nivel.olho} fill={cor} />
      <path
        d={nivel.boca}
        stroke={cor}
        strokeWidth="1.8"
        strokeLinecap="round"
        fill="none"
      />
    </svg>
  )
}

export function RatingCard({ avaliacao, aoAvaliar, superficie }) {
  const [nota, setNota] = useState(null)
  const [hover, setHover] = useState(null)
  const [comentario, setComentario] = useState('')
  const [enviando, setEnviando] = useState(false)
  const [erro, setErro] = useState(null)

  const jaAvaliado = avaliacao?.nota != null
  const destaque = hover ?? nota
  const nivelDestaque = NIVEIS.find((n) => n.nota === destaque)

  // A superfície vem do tema do aparelho (escuro no App e no WhatsApp).
  const base = superficie

  if (jaAvaliado) {
    const nivel = NIVEIS.find((n) => n.nota === avaliacao.nota)
    return (
      <div className={`animate-fade-in self-center rounded-2xl border p-4 text-center ${base}`}>
        <div className="flex justify-center">
          <Carinha nivel={nivel} ativa size={40} />
        </div>
        <p className="font-display mt-2 text-[13px] font-bold" style={{ color: nivel.cor }}>
          {nivel.rotulo}
        </p>
        <p className="mt-1 text-[11px] opacity-70">
          Obrigado pela avaliação. Sua opinião melhora nosso atendimento.
        </p>
      </div>
    )
  }

  const enviar = async () => {
    if (!nota || enviando) return
    setEnviando(true)
    setErro(null)
    try {
      await aoAvaliar({ nota, comentario: comentario.trim() || null })
    } catch (e) {
      setErro(e)
      setEnviando(false)
    }
  }

  return (
    <div className={`animate-fade-in self-stretch rounded-2xl border p-4 ${base}`}>
      <p className="font-display text-center text-[13px] font-bold">
        Como foi seu atendimento?
      </p>
      <p className="mt-0.5 text-center text-[11px] opacity-65">
        Sua avaliação é anônima e leva dois segundos.
      </p>

      <div
        className="mt-3 flex items-center justify-center gap-1"
        role="radiogroup"
        aria-label="Nota de 1 a 5"
        onMouseLeave={() => setHover(null)}
      >
        {NIVEIS.map((n) => {
          const ativa = destaque === n.nota
          return (
            <button
              key={n.nota}
              role="radio"
              aria-checked={nota === n.nota}
              aria-label={`${n.nota} — ${n.rotulo}`}
              onClick={() => setNota(n.nota)}
              onMouseEnter={() => setHover(n.nota)}
              onFocus={() => setHover(n.nota)}
              className="cursor-pointer rounded-full p-1.5 opacity-45 transition
                hover:opacity-100 focus-visible:opacity-100 focus-visible:outline-2
                focus-visible:outline-offset-2 aria-checked:opacity-100"
              style={{
                opacity: ativa ? 1 : undefined,
                transform: ativa ? 'scale(1.14)' : undefined,
                outlineColor: n.cor,
              }}
            >
              <Carinha nivel={n} ativa={ativa} />
            </button>
          )
        })}
      </div>

      <p
        className="mt-1.5 h-4 text-center text-[11px] font-semibold"
        style={{ color: nivelDestaque?.cor }}
      >
        {nivelDestaque?.rotulo ?? ''}
      </p>

      {nota && (
        <div className="animate-fade-in mt-3">
          <textarea
            rows={2}
            value={comentario}
            maxLength={500}
            onChange={(e) => setComentario(e.target.value)}
            placeholder="Quer contar o que aconteceu? (opcional)"
            className={`w-full resize-none rounded-xl border px-3 py-2 text-[12px] outline-none
              border-white/10 bg-white/5 placeholder:text-white/45`}
          />
          <button
            onClick={enviar}
            disabled={enviando}
            className="bg-claro hover:bg-claro-hi mt-2 w-full cursor-pointer rounded-xl py-2.5
              text-[12.5px] font-bold text-white transition disabled:opacity-50"
          >
            {enviando ? 'Enviando...' : 'Enviar avaliação'}
          </button>
        </div>
      )}

      {erro && (
        <p className="text-crit mt-2 text-center text-[11px]">
          Não foi possível enviar. Tente novamente.
        </p>
      )}
    </div>
  )
}
