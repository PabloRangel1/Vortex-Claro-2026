import { useEffect, useRef } from 'react'

import { rotuloAcao, rotuloResultado } from '../../lib/acoes'
import { horaCurta, primeiroNome } from '../../lib/formatters'
import { IconeChat, IconeCheck, IconeSeta, IconeX } from '../ui/icons'
import { EmptyState } from '../ui/EmptyState'
import { Pill, PillCanal } from '../ui/Pill'

/** Divisor de troca de canal — o momento que o produto existe para resolver. */
function DivisorTroca({ de, para, hora }) {
  return (
    <div className="animate-fade-in flex items-center gap-[10px] py-2">
      <div className="from-border h-px flex-1 bg-gradient-to-l to-transparent" />
      <div className="bg-elev border-claro/25 flex items-center gap-2 rounded-full border px-[14px] py-[7px] shadow-[0_3px_16px_rgb(227_6_19/0.1)]">
        <PillCanal canal={de} />
        <IconeSeta size={13} className="text-claro-hi" />
        <PillCanal canal={para} />
        <b className="num text-txt-ghost text-rotulo font-medium">{hora}</b>
      </div>
      <div className="from-border h-px flex-1 bg-gradient-to-r to-transparent" />
    </div>
  )
}

/** Nota do sistema (handoff, encerramento...). Legível, mas claramente não é fala. */
function Sistema({ conteudo, tipo }) {
  const destaque = tipo === 'handoff'
  return (
    <div className="animate-fade-in flex justify-center">
      <div
        className={`max-w-[520px] rounded-xl border px-[16px] py-[8px] text-center text-apoio leading-relaxed ${
          destaque
            ? 'bg-claro-wash border-claro/25 text-claro-hi font-semibold'
            : 'bg-panel/80 border-border-soft text-txt-dim'
        }`}
      >
        {conteudo}
      </div>
    </div>
  )
}

/** Cor de um resultado de ação: resolvido, resolvido mas pedindo humano, falhou. */
export function corDaAcao(m) {
  if (m.status === 'falha') return 'var(--color-crit)'
  if (m.requerHandoff) return 'var(--color-warn)'
  return 'var(--color-ok)'
}

/** Registro de uma ação do autoatendimento — o que o bot FEZ, não só o que disse. */
function RegistroAcao({ mensagem }) {
  const cor = corDaAcao(mensagem)
  return (
    <div className="animate-fade-in flex justify-center" title={mensagem.conteudo}>
      <div className="bg-elev border-border flex items-center gap-[9px] rounded-full border py-[5px] pr-[14px] pl-[6px] text-apoio">
        <span
          className="flex size-[20px] items-center justify-center rounded-full"
          style={{ color: cor, background: `color-mix(in srgb, ${cor} 13%, transparent)` }}
        >
          {mensagem.status === 'falha' ? <IconeX size={11} /> : <IconeCheck size={11} />}
        </span>
        <span className="text-txt-ghost font-display text-rotulo font-extrabold tracking-[0.7px] uppercase">
          Autoatendimento
        </span>
        <span className="text-txt-hi font-semibold">{rotuloAcao(mensagem.acao)}</span>
        <span className="text-txt-dim">· {rotuloResultado(mensagem.codigo)}</span>
        {mensagem.solicitacao && (
          <span className="num text-txt-ghost text-rotulo">{mensagem.solicitacao}</span>
        )}
        <span className="num text-txt-ghost text-rotulo">{horaCurta(mensagem.criadaEm)}</span>
      </div>
    </div>
  )
}

function Balao({ mensagem, nomeCliente }) {
  const { remetente, canal, conteudo, criadaEm, autor } = mensagem
  const hora = horaCurta(criadaEm)
  const doCliente = remetente === 'cliente'

  const estilo = {
    // Cliente à esquerda com a cor do canal; bot em branco; atendente no tom da
    // marca. Antes o bot era cinza sobre fundo cinza e tudo se misturava.
    cliente: `bg-panel border-border rounded-bl-[3px] ${
      canal === 'whatsapp' ? 'border-l-[3px] border-l-wpp/60' : 'border-l-[3px] border-l-claro/60'
    }`,
    bot: 'bg-panel border-border rounded-br-[3px]',
    atendente: 'bg-claro-wash border-claro/30 rounded-br-[3px]',
  }[remetente]

  return (
    <div className={`flex ${doCliente ? 'justify-start' : 'justify-end'}`}>
      <div
        className={`${doCliente ? 'animate-fade-in' : 'animate-slide-l'} max-w-[min(540px,72%)]
          rounded-xl border px-[15px] py-[11px] shadow-[0_1px_2px_rgb(23_18_19/0.06)] ${estilo}`}
      >
        <div
          className={`mb-[6px] flex items-center gap-[6px] ${doCliente ? '' : 'justify-end'}`}
        >
          {doCliente ? (
            <>
              <PillCanal canal={canal} />
              <span className="num text-txt-ghost text-rotulo">
                {primeiroNome(autor ?? nomeCliente)} · {hora}
              </span>
            </>
          ) : (
            <>
              <span className="num text-txt-ghost text-rotulo">
                {hora} ·{' '}
                {remetente === 'bot'
                  ? mensagem.ia
                    ? 'Bot · interpretado por IA'
                    : 'Bot'
                  : (autor ?? 'Atendente')}
              </span>
              <Pill variante={remetente}>{remetente === 'bot' ? 'BOT' : 'ATENDENTE'}</Pill>
            </>
          )}
        </div>
        <p className="text-txt text-[13px] leading-[1.62]">{conteudo}</p>
      </div>
    </div>
  )
}

export function MessageList({ mensagens, nomeCliente, vazio, carregando }) {
  const fim = useRef(null)
  const quantidade = mensagens?.length ?? 0

  useEffect(() => {
    fim.current?.scrollIntoView({ block: 'end' })
  }, [quantidade])

  if (vazio) {
    return (
      <div className="scroll-area flex-1 p-[16px_20px]">
        {carregando ? (
          <EmptyState
            icone={<IconeChat size={26} className="text-txt-ghost animate-pulse" />}
            titulo="Carregando a conversa..."
            descricao="Reunindo o histórico dos canais deste atendimento."
          />
        ) : (
          <EmptyState
            icone={<IconeChat size={26} className="text-txt-ghost" />}
            titulo="Nenhum atendimento aberto"
            descricao="Escolha um cliente na fila à esquerda para ver a conversa consolidada dos canais."
          />
        )}
      </div>
    )
  }

  return (
    <div
      role="log"
      aria-label={`Conversa com ${nomeCliente ?? 'o cliente'}`}
      className="scroll-area flex flex-1 flex-col gap-[11px] p-[16px_20px]"
    >
      {mensagens.map((m) =>
        m.tipo === 'troca_canal' ? (
          <DivisorTroca key={m.id} de={m.de} para={m.para} hora={horaCurta(m.criadaEm)} />
        ) : m.tipo === 'acao' ? (
          <RegistroAcao key={m.id} mensagem={m} />
        ) : m.remetente === 'sistema' ? (
          <Sistema key={m.id} conteudo={m.conteudo} tipo={m.tipo} />
        ) : (
          <Balao key={m.id} mensagem={m} nomeCliente={nomeCliente} />
        ),
      )}
      <div ref={fim} />
    </div>
  )
}
