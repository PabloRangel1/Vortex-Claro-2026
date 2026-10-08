import { useEffect } from 'react'
import { NavLink, useLocation } from 'react-router-dom'

import { ReiniciarDemo } from './ReiniciarDemo'

const ABAS = [
  { para: '/', rotulo: 'Dashboard', fim: true, contexto: 'Dashboard do Atendente' },
  { para: '/estatisticas', rotulo: 'Estatísticas', contexto: 'Painel Analítico' },
  { para: '/historico', rotulo: 'Histórico', contexto: 'Clientes e protocolos' },
  { para: '/sim/app', rotulo: 'App Claro', contexto: 'Simulador de Canal' },
  { para: '/sim/whatsapp', rotulo: 'WhatsApp', contexto: 'Simulador de Canal' },
]

/** Indicador de saúde da conexão — reflete o estado real do polling. */
function StatusConexao({ erro, carregando }) {
  const estado = erro
    ? { cor: 'var(--color-crit)', texto: erro.offline ? 'API offline' : 'Erro na API' }
    : carregando
      ? { cor: 'var(--color-warn)', texto: 'Conectando' }
      : { cor: 'var(--color-ok)', texto: 'API conectada' }

  return (
    <div className="bg-void border-border flex items-center gap-[7px] rounded-full border px-3 py-[6px]">
      <span
        className={`size-[6px] rounded-full ${erro ? '' : 'animate-pulse-dot'}`}
        style={{ background: estado.cor }}
      />
      <span className="text-txt-dim text-rotulo font-semibold">{estado.texto}</span>
    </div>
  )
}

export function TopBar({ erro, carregando }) {
  const { pathname } = useLocation()
  const aba = ABAS.find((a) => (a.fim ? pathname === a.para : pathname.startsWith(a.para)))
  const contexto = aba?.contexto ?? 'Atendimento'

  // Abas do navegador distinguíveis na apresentação (dashboard x simuladores).
  useEffect(() => {
    document.title = aba ? `${aba.rotulo} · Vortex` : 'Vortex'
  }, [aba])

  return (
    <nav className="bg-panel border-claro relative flex h-14 shrink-0 items-center justify-between gap-[18px] border-b-2 px-[18px]">
      <div className="flex shrink-0 items-center gap-[11px]">
        {/* Assinatura da marca: o vermelho pleno com a palavra em negativo é o
            gesto mais reconhecível da Claro. */}
        <span className="bg-claro font-display flex h-[26px] items-center rounded-[5px] px-[9px] text-[13px] font-extrabold tracking-[0.06em] text-white">
          CLARO
        </span>
        <span className="font-display text-txt-hi text-base font-extrabold tracking-[-0.4px]">
          Vortex
        </span>
        {/* Em telas estreitas a barra prioriza as abas: o contexto sai. */}
        <span className="bg-border h-[22px] w-px max-[1280px]:hidden" />
        <span className="text-txt-ghost text-[11px] font-semibold max-[1280px]:hidden">{contexto}</span>
      </div>

      <div className="bg-void border-border flex gap-[3px] rounded-[11px] border p-[3px]">
        {ABAS.map((aba) => (
          <NavLink
            key={aba.para}
            to={aba.para}
            end={aba.fim}
            className={({ isActive }) =>
              `flex items-center gap-[7px] rounded-lg px-[15px] py-[7px] text-[12px] font-semibold whitespace-nowrap transition-[0.16s] ${
                isActive
                  ? 'bg-panel text-txt-hi shadow-[0_1px_3px_rgb(0_0_0/0.10)]'
                  : 'text-txt-dim hover:bg-black/4 hover:text-txt'
              }`
            }
          >
            {({ isActive }) => (
              <>
                <span
                  className={`size-[6px] rounded-full ${isActive ? 'bg-claro' : 'bg-txt-ghost'}`}
                />
                {aba.rotulo}
              </>
            )}
          </NavLink>
        ))}
      </div>

      <div className="flex shrink-0 items-center gap-3">
        <ReiniciarDemo />
        <StatusConexao erro={erro} carregando={carregando} />
        <div className="border-border flex items-center gap-[9px] border-l pl-3">
          {/* O atendente fica em neutro: o vermelho é reservado à marca, ao
              cliente em foco e ao estado crítico. */}
          <div
            title="Marcos Ribeiro · Atendimento N2"
            className="font-display bg-elev border-border text-txt flex size-8 items-center justify-center rounded-full border text-[11px] font-extrabold"
          >
            MR
          </div>
          <div className="max-[1200px]:hidden">
            <p className="text-txt text-[11px] font-bold">Marcos Ribeiro</p>
            <p className="text-txt-ghost text-rotulo">Atendimento N2</p>
          </div>
        </div>
      </div>
    </nav>
  )
}
