import { useEffect, useMemo, useState } from 'react'

import { segundosParaMMSS } from '../../lib/formatters'
import { ESPERA_ALERTA_SEGUNDOS, faixaDe } from '../../lib/friction'
import { IconeBusca, IconeRelogio, IconeUsuarios } from '../ui/icons'
import { PillCanal } from '../ui/Pill'
import { SectionTitle } from '../ui/SectionTitle'

/** Relógio local de 1s: a espera avança suave entre os polls de 4s. */
function useTicker() {
  const [, forcar] = useState(0)
  useEffect(() => {
    const id = setInterval(() => forcar((n) => n + 1), 1000)
    return () => clearInterval(id)
  }, [])
}

function ItemFila({ item, selecionado, aoSelecionar, atraso }) {
  const faixa = faixaDe(item.nivel)
  const espera = Math.max(
    0,
    item.esperaSegundos + Math.floor((Date.now() - item.recebidoEm) / 1000),
  )

  return (
    <button
      onClick={() => aoSelecionar(item.protocolo)}
      style={{ animationDelay: `${atraso}ms` }}
      className={`animate-fade-up relative mb-[3px] w-full cursor-pointer rounded-[10px] border
        p-[11px_12px] text-left transition-[0.15s]
        ${
          selecionado
            ? 'bg-claro/10 border-claro/25'
            : 'hover:bg-claro/5 hover:border-claro/12 border-transparent'
        }`}
    >
      {selecionado && (
        <span className="bg-claro absolute top-[11px] bottom-[11px] left-0 w-[2px] rounded-sm" />
      )}

      <div className="mb-[5px] flex items-center justify-between gap-2">
        <span className="font-display text-txt-hi truncate text-[12.5px] font-bold">
          {item.nome}
        </span>
        <PillCanal canal={item.canalAtual} curto />
      </div>
      <p className="text-txt-ghost -mt-[3px] mb-[5px] text-rotulo">{item.segmentoRotulo}</p>

      <p className="text-txt-dim mb-[7px] truncate text-[11px] leading-[1.45]">
        {item.ultimaMensagem}
      </p>

      <div className="flex items-center justify-between gap-2">
        <span
          className="num rounded-[5px] border px-[7px] py-[2px] text-rotulo font-extrabold"
          style={{ background: faixa.fundo, color: faixa.cor, borderColor: faixa.borda }}
        >
          {item.score}
        </span>
        <span
          className={`num flex items-center gap-1 text-rotulo ${
            espera >= ESPERA_ALERTA_SEGUNDOS ? 'text-warn font-bold' : 'text-txt-ghost'
          }`}
          title={
            espera >= ESPERA_ALERTA_SEGUNDOS ? 'Esperando há mais de 2 minutos' : undefined
          }
        >
          <IconeRelogio size={espera >= ESPERA_ALERTA_SEGUNDOS ? 11 : 9} />
          {segundosParaMMSS(espera)}
        </span>
      </div>
    </button>
  )
}

export function QueuePanel({ fila, protocoloSelecionado, aoSelecionar }) {
  const [busca, setBusca] = useState('')
  useTicker()

  // Filtros do atendente: tipo de cliente (produto) e canal em que está agora.
  const [segmento, setSegmento] = useState('')
  const [canal, setCanal] = useState('')

  const filtrada = useMemo(() => {
    const termo = busca.trim().toLowerCase()
    return fila.filter(
      (i) =>
        (!termo || i.nome.toLowerCase().includes(termo) || i.protocolo.includes(termo)) &&
        (!segmento || i.segmento === segmento) &&
        (!canal || i.canalAtual === canal),
    )
  }, [fila, busca, segmento, canal])
  const filtrando = Boolean(segmento || canal || busca.trim())

  const criticos = fila.filter((i) => i.nivel === 'critico').length
  const esperaMedia = fila.length
    ? Math.round(fila.reduce((s, i) => s + i.esperaSegundos, 0) / fila.length)
    : 0

  return (
    <aside className="bg-panel border-border flex w-[302px] shrink-0 flex-col border-r max-[1500px]:w-[262px]">
      <div className="border-border border-b p-[15px_16px]">
        <div className="mb-3 flex items-center justify-between">
          <SectionTitle icone={<IconeUsuarios size={13} />}>Aguardando Handoff</SectionTitle>
          <span className="num bg-claro/10 text-claro-hi border-claro/25 rounded-full border px-[10px] py-[3px] text-[11px] font-extrabold">
            {fila.length}
          </span>
        </div>

        <div className="relative">
          <IconeBusca
            size={13}
            className="text-txt-ghost absolute top-1/2 left-[11px] -translate-y-1/2"
          />
          <input
            type="search"
            aria-label="Buscar cliente ou protocolo na fila"
            value={busca}
            onChange={(e) => setBusca(e.target.value)}
            placeholder="Buscar cliente ou protocolo..."
            className="bg-input border-border text-txt focus:border-claro focus:ring-claro/10
              placeholder:text-txt-ghost w-full rounded-[9px] border py-[9px] pr-3 pl-[33px]
              text-[12px] transition outline-none focus:ring-[3px]"
          />
        </div>

        <div className="mt-2 grid grid-cols-2 gap-2">
          <select
            aria-label="Filtrar por tipo de cliente"
            value={segmento}
            onChange={(e) => setSegmento(e.target.value)}
            className={`bg-input border-border focus:border-claro cursor-pointer rounded-[9px] border px-2 py-[7px] text-apoio outline-none ${
              segmento ? 'text-claro-hi border-claro/40 font-semibold' : 'text-txt-dim'
            }`}
          >
            <option value="">Todos os tipos</option>
            <option value="pos">Pós-pago</option>
            <option value="controle">Controle</option>
            <option value="fibra">Fibra</option>
          </select>
          <select
            aria-label="Filtrar por canal"
            value={canal}
            onChange={(e) => setCanal(e.target.value)}
            className={`bg-input border-border focus:border-claro cursor-pointer rounded-[9px] border px-2 py-[7px] text-apoio outline-none ${
              canal ? 'text-claro-hi border-claro/40 font-semibold' : 'text-txt-dim'
            }`}
          >
            <option value="">Todos os canais</option>
            <option value="app">App Claro</option>
            <option value="whatsapp">WhatsApp</option>
          </select>
        </div>
        {filtrando && (
          <p className="text-txt-dim mt-2 flex items-center justify-between text-rotulo">
            <span>
              Mostrando <b className="text-txt-hi">{filtrada.length}</b> de {fila.length}
            </span>
            <button
              type="button"
              onClick={() => {
                setSegmento('')
                setCanal('')
                setBusca('')
              }}
              className="text-claro-hi cursor-pointer font-semibold hover:underline"
            >
              Limpar filtros
            </button>
          </p>
        )}
      </div>

      <div className="scroll-area flex-1 p-[6px_5px]">
        {filtrada.length === 0 ? (
          <p className="text-txt-ghost p-[22px_14px] text-center text-[11.5px] leading-relaxed">
            {fila.length === 0
              ? 'Nenhum atendimento aguardando. Use os simuladores para gerar fricção.'
              : 'Nenhum atendimento com estes filtros.'}
          </p>
        ) : (
          filtrada.map((item, i) => (
            <ItemFila
              key={item.protocolo}
              item={item}
              atraso={Math.min(i * 40, 320)}
              selecionado={item.protocolo === protocoloSelecionado}
              aoSelecionar={aoSelecionar}
            />
          ))
        )}
      </div>

      <div className="border-border flex justify-between gap-[10px] border-t p-[12px_16px]">
        {[
          ['Na fila', fila.length, 'var(--color-txt)'],
          ['Espera méd.', segundosParaMMSS(esperaMedia), 'var(--color-warn)'],
          ['Crítico', criticos, 'var(--color-crit)'],
        ].map(([rotulo, valor, cor]) => (
          <div key={rotulo}>
            <p className="text-txt-ghost text-rotulo font-bold tracking-[0.6px] whitespace-nowrap uppercase">
              {rotulo}
            </p>
            <p className="num mt-[3px] text-[14px] font-extrabold" style={{ color: cor }}>
              {valor}
            </p>
          </div>
        ))}
      </div>
    </aside>
  )
}
