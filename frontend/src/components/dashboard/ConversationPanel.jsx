import { useEffect, useRef, useState } from 'react'

import { iniciais } from '../../lib/formatters'
import { ROTULO_STATUS } from '../../lib/friction'
import { Button } from '../ui/Button'
import { respostasRapidas } from '../../lib/respostasAtendente'
import { IconeEnviar, IconeMenuLateral, IconeTroca, IconeX } from '../ui/icons'
import { MessageList } from './MessageList'
import { ResumoCaso } from './ResumoCaso'

function Composer({ aoEnviar, enviando, desabilitado, erro, sugestoes = [] }) {
  const [texto, setTexto] = useState('')
  const campo = useRef(null)

  // Auto-resize até um teto, sem barra de rolagem interna aparecendo cedo.
  useEffect(() => {
    const el = campo.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 110)}px`
  }, [texto])

  const submeter = async () => {
    const conteudo = texto.trim()
    if (!conteudo || enviando) return
    setTexto('')
    try {
      await aoEnviar(conteudo)
    } catch {
      setTexto(conteudo) // devolve o texto se a API falhou
    }
  }

  return (
    <div className="bg-panel border-border shrink-0 border-t p-[13px_20px]">
      {erro && (
        <p role="alert" className="text-crit mb-2 text-[12px] font-semibold">
          Não foi possível enviar{erro.offline ? ': a API está fora do ar' : ''}. Sua mensagem
          continua no campo — tente de novo.
        </p>
      )}
      {/* Um clique PREENCHE o campo, não envia: o atendente revisa antes. */}
      {!desabilitado && sugestoes.length > 0 && !texto && (
        <div className="mb-2 flex flex-wrap gap-[6px]" aria-label="Respostas rápidas">
          {sugestoes.map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => {
                setTexto(s)
                campo.current?.focus()
              }}
              title={s}
              className="bg-void border-border text-txt-dim hover:border-claro/35 hover:text-txt-hi
                max-w-[340px] cursor-pointer truncate rounded-full border px-3 py-[5px] text-apoio transition"
            >
              {s}
            </button>
          ))}
        </div>
      )}
      <div className="flex items-end gap-[9px]">
      <textarea
        aria-label="Resposta ao cliente"
        ref={campo}
        rows={1}
        value={texto}
        disabled={desabilitado}
        onChange={(e) => setTexto(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault()
            submeter()
          }
        }}
        placeholder={
          desabilitado ? 'Selecione um atendimento' : 'Digite sua resposta ao cliente...'
        }
        className="bg-input border-border text-txt focus:border-claro focus:ring-claro/10
          placeholder:text-txt-ghost max-h-[110px] flex-1 resize-none rounded-[10px] border
          px-[14px] py-[11px] text-[13px] leading-normal transition outline-none
          focus:ring-[3px] disabled:opacity-50"
      />
      <Button
        variante="primario"
        padding="px-[14px] py-[11px]"
        disabled={desabilitado || enviando || !texto.trim()}
        onClick={submeter}
        aria-label="Enviar resposta"
      >
        <IconeEnviar size={15} />
      </Button>
      </div>
    </div>
  )
}

export function ConversationPanel({
  atendimento,
  carregando,
  aoResponder,
  enviando,
  erroEnvio,
  aoEncerrar,
  aoTransferir,
  painelAberto,
  aoAlternarPainel,
}) {
  const vazio = !atendimento
  const encerrado = atendimento?.status === 'encerrado'

  return (
    <main className="bg-void flex min-w-0 flex-1 flex-col">
      <div className="bg-panel border-border flex min-h-[60px] shrink-0 items-center justify-between border-b p-[12px_20px]">
        <div className="flex min-w-0 items-center gap-3">
          <div className="font-display from-claro flex size-10 shrink-0 items-center justify-center rounded-full bg-gradient-to-br to-[#a8040e] text-[13px] font-extrabold text-white">
            {vazio ? '?' : iniciais(atendimento.cliente.nome)}
          </div>
          <div className="min-w-0">
            <p className="font-display text-txt-hi truncate text-[14.5px] font-bold">
              {vazio
                ? carregando
                  ? 'Carregando atendimento...'
                  : 'Selecione um atendimento'
                : atendimento.cliente.nome}
            </p>
            <p className="num text-txt-ghost mt-[2px] truncate text-rotulo">
              {vazio
                ? '—'
                : `${atendimento.protocolo} · ${atendimento.cliente.cpf} · ${
                    ROTULO_STATUS[atendimento.status] ?? atendimento.status
                  }`}
            </p>
          </div>
        </div>

        <div className="flex shrink-0 items-center gap-[7px]">
          {atendimento?.setorRotulo && (
            <span className="bg-claro/8 text-claro-hi border-claro/25 font-display mr-1 rounded-md border px-[9px] py-[4px] text-rotulo font-bold tracking-[0.06em] uppercase">
              {atendimento.setorRotulo}
            </span>
          )}
          <Button
            className="xl:hidden"
            onClick={aoAlternarPainel}
            aria-expanded={painelAberto}
            aria-controls="painel-inteligencia"
          >
            <IconeMenuLateral size={12} />
            Inteligência
          </Button>
          <Button disabled={vazio || encerrado} onClick={aoTransferir}>
            <IconeTroca size={12} />
            Transferir
          </Button>
          <Button variante="perigo" disabled={vazio || encerrado} onClick={aoEncerrar}>
            <IconeX size={12} />
            {encerrado ? 'Encerrado' : 'Encerrar'}
          </Button>
        </div>
      </div>

      {atendimento?.handoff.acionado && (
        // Chaves com prefixo: ResumoCaso e Composer são irmãos, e a mesma chave
        // nos dois fazia o React perder o cartão anterior e empilhar cópias.
        <ResumoCaso key={`resumo-${atendimento.protocolo}`} atendimento={atendimento} />
      )}

      <MessageList
        vazio={vazio}
        carregando={carregando}
        mensagens={atendimento?.mensagens ?? []}
        nomeCliente={atendimento?.cliente.nome}
      />

      {/* key: o rascunho não acompanha a troca de cliente — evita mandar para
          o Ricardo o que foi escrito pensando na Ana. */}
      <Composer
        key={`composer-${atendimento?.protocolo ?? 'nenhum'}`}
        aoEnviar={aoResponder}
        enviando={enviando}
        erro={erroEnvio}
        sugestoes={respostasRapidas(atendimento)}
        desabilitado={vazio || encerrado}
      />
    </main>
  )
}
