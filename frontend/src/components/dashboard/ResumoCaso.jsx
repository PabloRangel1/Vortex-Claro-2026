import { useState } from 'react'

import { montarResumo } from '../../lib/resumo'
import { IconeCheck, IconeRaio, IconeSeta, IconeTroca, IconeX } from '../ui/icons'
import { PillCanal } from '../ui/Pill'

/**
 * Cartão do handoff: o caso resumido para quem assume o atendimento.
 *
 * Substitui o antigo aviso "Handoff Inteligente Ativado" — que dizia QUE houve
 * transferência, mas não O QUÊ o atendente precisa saber. Recolhível: depois
 * de lido, não deve roubar espaço da conversa.
 */

function Canais({ canalOrigem, canalAtual, canaisUtilizados, houveTroca }) {
  // A seta só aparece quando o cliente de fato migrou; "APP → APP" sugeria
  // uma troca que não houve. Ida e volta vira seta dupla entre os canais.
  if (houveTroca && canalOrigem === canalAtual) {
    return canaisUtilizados.map((c, i) => (
      <span key={c} className="flex items-center gap-[6px]">
        {i > 0 && <IconeTroca size={12} className="text-claro-hi" />}
        <PillCanal canal={c} curto />
      </span>
    ))
  }
  if (houveTroca) {
    return (
      <>
        <PillCanal canal={canalOrigem} curto />
        <IconeSeta size={13} className="text-claro-hi" />
        <PillCanal canal={canalAtual} curto />
      </>
    )
  }
  return <PillCanal canal={canalAtual} />
}

function Linha({ rotulo, children }) {
  return (
    <div className="grid grid-cols-[132px_1fr] gap-3 py-[6px] not-first:border-t not-first:border-claro/10">
      <dt className="text-txt-dim text-rotulo pt-[1px] font-bold tracking-[0.6px] uppercase">
        {rotulo}
      </dt>
      <dd className="text-txt text-[12.5px] leading-[1.5]">{children}</dd>
    </div>
  )
}

export function ResumoCaso({ atendimento }) {
  const [aberto, setAberto] = useState(true)
  const resumo = montarResumo(atendimento)

  return (
    <section
      aria-label="Resumo do caso"
      className="animate-fade-up border-claro/25 mx-5 mt-3 shrink-0 rounded-[11px] border
        bg-gradient-to-br from-[rgb(227_6_19/0.07)] to-[rgb(227_6_19/0.015)]"
    >
      <div className="flex items-center gap-[12px] px-[15px] py-[10px]">
        <div className="bg-claro/10 flex size-8 shrink-0 items-center justify-center rounded-[9px]">
          <IconeRaio size={15} className="text-claro-hi" />
        </div>
        <p className="font-display text-claro-hi flex-1 text-[12.5px] font-bold">
          Handoff · resumo do caso
        </p>
        <div className="flex shrink-0 items-center gap-[6px]">
          <Canais
            canalOrigem={atendimento.canalOrigem}
            canalAtual={atendimento.canalAtual}
            canaisUtilizados={atendimento.canaisUtilizados}
            houveTroca={atendimento.houveTroca}
          />
        </div>
        <button
          type="button"
          onClick={() => setAberto((v) => !v)}
          aria-expanded={aberto}
          className="text-claro-hi hover:bg-claro/10 cursor-pointer rounded-md px-2 py-1 text-rotulo font-bold transition"
        >
          {aberto ? 'Recolher' : 'Ver resumo'}
        </button>
      </div>

      {aberto && (
        <dl className="border-claro/15 border-t px-[15px] py-[6px]">
          <Linha rotulo="O cliente quer">
            <b className="text-txt-hi">{resumo.demanda}</b>
            {resumo.pedido && <span className="text-txt-dim"> — “{resumo.pedido}”</span>}
          </Linha>

          <Linha rotulo="O bot já fez">
            {resumo.feito.length === 0 ? (
              <span className="text-txt-dim">Nada resolvido pelo autoatendimento.</span>
            ) : (
              <span className="flex flex-wrap gap-[6px]">
                {resumo.feito.map((f) => (
                  <span
                    key={f.id}
                    className="bg-ok/8 text-ok border-ok/25 inline-flex items-center gap-1 rounded-md border px-[7px] py-[1px] text-apoio font-semibold"
                  >
                    <IconeCheck size={11} />
                    {f.rotulo}
                    {f.solicitacao && <span className="num opacity-75">· {f.solicitacao}</span>}
                  </span>
                ))}
              </span>
            )}
          </Linha>

          {resumo.falhou.length > 0 && (
            <Linha rotulo="Não deu certo">
              <span className="flex flex-wrap gap-[6px]">
                {resumo.falhou.map((f) => (
                  <span
                    key={f.id}
                    className="bg-crit/8 text-crit border-crit/25 inline-flex items-center gap-1 rounded-md border px-[7px] py-[1px] text-apoio font-semibold"
                  >
                    <IconeX size={10} />
                    {f.rotulo}
                  </span>
                ))}
              </span>
            </Linha>
          )}

          <Linha rotulo="Por que transferiu">{resumo.motivo}</Linha>

          {resumo.sinais.length > 0 && (
            <Linha rotulo="Atenção">
              <span className="text-warn font-semibold">{resumo.sinais.join(' · ')}</span>
            </Linha>
          )}
        </dl>
      )}
    </section>
  )
}
