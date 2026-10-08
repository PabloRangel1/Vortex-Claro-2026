import { useEffect, useRef, useState } from 'react'

import { useCanal, useClientes } from '../../hooks/useVortex'
import { horaCurta } from '../../lib/formatters'
import { sugerirRespostas } from '../../lib/sugestoes'
import {
  IconeBrilho,
  IconeChat,
  IconeCheck,
  IconeCheckDuplo,
  IconeEnviar,
  IconeVoltar,
} from '../ui/icons'
import { ActionCard, temCartao } from './ActionCard'
import { RatingCard } from './RatingCard'

/**
 * Simulador de canal do cliente.
 *
 * UM componente para os dois canais: `variante` muda o chrome, as bolhas, o
 * identificador usado e o endpoint. Duas telas separadas divergiriam com o tempo.
 */

// Os dois aparelhos em TEMA ESCURO: texto claro sobre fundo escuro cansa menos
// e lê melhor projetado. Só o aparelho é escuro — o resto da página não muda.
const CONFIG = {
  app: {
    titulo: 'Minha Claro',
    subtitulo: 'Assistente virtual · online',
    corBarra: 'linear-gradient(120deg,#e30613,#a8040e)',
    // Escuro com viés quente, para o vermelho da marca não "encardir".
    fundo: 'bg-[#151112]',
    bolhaSaida: 'bg-gradient-to-br from-[#e30613] to-[#a8040e] text-white',
    bolhaEntrada: 'bg-[#262022] border border-white/8 text-[#f3eeee]',
    barraEntrada: 'bg-[#1c1718] border-t border-white/8',
    campo: 'bg-[#2a2325] border border-white/10 text-[#f3eeee]',
    botao: 'bg-claro hover:bg-claro-hi',
    chipSugestao: 'border-white/12 bg-white/5 text-white/75 hover:bg-white/10 hover:text-white',
    chipOpcao: 'border-[#ff4d58]/60 bg-[#e30613]/15 text-[#ff8a91] hover:bg-claro hover:text-white',
    cartao: 'bg-[#211b1d] border-white/10 text-[#f3eeee]',
    endpoint: 'POST /channels/app',
    chaveIdentificador: 'usuarioApp',
  },
  // Cores reais do modo escuro do WhatsApp — o simulador só convence se o
  // aparelho parecer o aplicativo de verdade, não uma versão Claro dele.
  whatsapp: {
    titulo: 'Claro Brasil',
    subtitulo: 'Conta comercial verificada',
    corBarra: '#202c33',
    fundo: 'bg-[#0b141a]',
    bolhaSaida: 'bg-[#005c4b] text-[#e9edef]',
    bolhaEntrada: 'bg-[#202c33] text-[#e9edef]',
    barraEntrada: 'bg-[#202c33]',
    campo: 'bg-[#2a3942] text-[#e9edef]',
    botao: 'bg-[#00a884] hover:bg-[#06cf9c]',
    chipSugestao: 'border-white/10 bg-[#202c33] text-[#aebac1] hover:text-white',
    chipOpcao: 'border-[#00a884] bg-transparent text-[#21c063] hover:bg-[#00a884]/15',
    cartao: 'bg-[#1f2c33] border-white/8 text-[#e9edef]',
    endpoint: 'POST /channels/whatsapp',
    chaveIdentificador: 'telefoneWhatsApp',
  },
}

// No escuro, as cores de status e o vermelho de texto precisam clarear para
// manter contraste. Sobrescritas só dentro da tela do aparelho.
const CORES_TELA_ESCURA = {
  '--color-ok': '#3ddc97',
  '--color-warn': '#f5b84a',
  '--color-crit': '#ff6b6b',
  '--color-claro-hi': '#ff8a91',
}

function Relogio() {
  const [hora, setHora] = useState(() => horaCurta(new Date().toISOString()))
  useEffect(() => {
    const id = setInterval(() => setHora(horaCurta(new Date().toISOString())), 10000)
    return () => clearInterval(id)
  }, [])
  return <span>{hora}</span>
}

function Bolha({ mensagem, cfg }) {
  const saida = mensagem.remetente === 'cliente'
  const doAtendente = mensagem.remetente === 'atendente'

  return (
    <div
      className={`animate-fade-in max-w-[80%] rounded-[13px] px-3 py-[9px] text-[12.5px] leading-[1.55]
        ${saida ? `self-end rounded-br-[4px] ${cfg.bolhaSaida}` : `self-start rounded-bl-[4px] ${cfg.bolhaEntrada}`}
        ${doAtendente ? 'border-l-2 border-l-[#ff6b73]' : ''}`}
    >
      {doAtendente && (
        <span className="mb-[3px] block text-rotulo font-extrabold text-[#ff8a91]">
          ATENDENTE · {(mensagem.autor ?? '').toUpperCase()}
        </span>
      )}
      {mensagem.conteudo}
      <span className="num mt-1 flex items-center justify-end gap-[5px] text-rotulo opacity-60">
        {mensagem.ia && (
          <span
            title="A IA interpretou sua mensagem; a ação foi executada pelo sistema"
            className="inline-flex items-center gap-[3px] font-sans font-bold"
          >
            <IconeBrilho size={10} />
            IA ·
          </span>
        )}
        {horaCurta(mensagem.criadaEm)}
        {saida && <IconeCheckDuplo size={13} />}
      </span>
    </div>
  )
}

/**
 * Mensagens visíveis no aparelho, na ordem em que o cliente as vê.
 *
 * Mensagens de sistema são ruído para o cliente — ele não vê "handoff
 * acionado", vê o bot mudando de tom. A exceção são as ações com resultado
 * (fatura, diagnóstico...): no histórico elas vêm ANTES da resposta do bot, mas
 * na tela aparecem DEPOIS dela, como anexo do que o bot acabou de dizer.
 */
function montarItens(mensagens) {
  const itens = []
  let cartoes = []
  for (const m of mensagens) {
    if (m.remetente === 'sistema') {
      if (temCartao(m)) cartoes.push(m)
      continue
    }
    itens.push({ m, cartao: false })
    if (m.remetente === 'bot') {
      cartoes.forEach((c) => itens.push({ m: c, cartao: true }))
      cartoes = []
    }
  }
  cartoes.forEach((c) => itens.push({ m: c, cartao: true }))
  return itens
}

export function SimulatorShell({ variante, aoMudarConexao }) {
  const cfg = CONFIG[variante]
  const { clientes, erro: erroClientes, carregando: carregandoClientes } = useClientes()
  const [clienteId, setClienteId] = useState(null)

  const selecionado = clientes.find((c) => c.clienteId === clienteId) ?? clientes[0] ?? null
  const identificador = selecionado?.[cfg.chaveIdentificador] ?? null

  const {
    atendimento,
    protocolo,
    enviar,
    enviando,
    erro,
    erroConexao,
    avaliar,
    trocarIdentificador,
    reiniciarConversa,
  } = useCanal(variante, identificador)

  // Sem isto o indicador da barra superior ficava em "Conectando" para sempre
  // nos simuladores — só o Dashboard e as Estatísticas o atualizavam.
  useEffect(() => {
    aoMudarConexao?.({ erro: erroConexao ?? erroClientes, carregando: carregandoClientes })
  }, [erroConexao, erroClientes, carregandoClientes, aoMudarConexao])

  // Depois do handoff o bot para de responder por intenção — é o comportamento
  // correto do produto, mas precisa ficar explícito na tela do cliente.
  const transferido =
    atendimento?.handoff.acionado || atendimento?.status === 'em_atendimento_humano'

  // Encerrado é o gatilho da avaliação: o cliente só pontua o que terminou.
  const encerrado = atendimento?.status === 'encerrado'

  const [texto, setTexto] = useState('')
  const fim = useRef(null)

  // Encerrar não se desfaz: o 1º clique arma, o 2º (em até 4s) confirma.
  const [confirmarEncerrar, setConfirmarEncerrar] = useState(false)
  useEffect(() => {
    if (!confirmarEncerrar) return
    const id = setTimeout(() => setConfirmarEncerrar(false), 4000)
    return () => clearTimeout(id)
  }, [confirmarEncerrar])
  useEffect(() => setConfirmarEncerrar(false), [protocolo])

  const aoClicarEncerrar = () => {
    // Já encerrado: não há o que perder, então começa a nova direto.
    if (!confirmarEncerrar && !encerrado) {
      setConfirmarEncerrar(true)
      return
    }
    setConfirmarEncerrar(false)
    reiniciarConversa()
  }

  // Com uma pergunta do bot em aberto ("qual dia?", "confirma?"), os botões são
  // as respostas que ele espera. Fora disso, sugestões que acompanham a
  // intenção e o estágio da conversa.
  const opcoesFluxo = !transferido ? (atendimento?.fluxo?.opcoes ?? []) : []
  const sugestoes = opcoesFluxo.length > 0 ? [] : sugerirRespostas(atendimento, variante)

  const itens = montarItens(atendimento?.mensagens ?? [])

  useEffect(() => {
    fim.current?.scrollIntoView({ block: 'end' })
  }, [itens.length])

  const submeter = async (valor) => {
    const conteudo = (valor ?? texto).trim()
    if (!conteudo || enviando) return
    setTexto('')
    try {
      await enviar(conteudo)
    } catch {
      setTexto(conteudo)
    }
  }

  return (
    <div className="relative flex flex-1 flex-col items-center justify-center gap-4 overflow-hidden bg-[radial-gradient(circle_at_50%_0%,#ffffff_0%,var(--color-void)_62%)]">
      <div
        className="pointer-events-none absolute inset-0 opacity-35"
        style={{
          backgroundImage:
            'linear-gradient(var(--color-border-soft) 1px,transparent 1px),linear-gradient(90deg,var(--color-border-soft) 1px,transparent 1px)',
          backgroundSize: '44px 44px',
          maskImage: 'radial-gradient(circle at 50% 40%,#000 0%,transparent 72%)',
        }}
      />

      {/* Seletor de cliente */}
      <div className="bg-panel border-border relative z-10 flex items-center gap-3 rounded-[11px] border px-[14px] py-[9px]">
        <label
          htmlFor={`sel-${variante}`}
          className="text-txt-ghost text-rotulo font-bold tracking-[1.1px] uppercase"
        >
          Simulando cliente
        </label>
        <select
          id={`sel-${variante}`}
          value={selecionado?.clienteId ?? ''}
          onChange={(e) => {
            setClienteId(e.target.value)
            trocarIdentificador()
          }}
          className="bg-input border-border text-txt-hi focus:border-claro cursor-pointer rounded-lg border px-[11px] py-[7px] text-[11.5px] font-semibold outline-none"
        >
          {clientes.length === 0 && <option>Carregando...</option>}
          {clientes.map((c) => (
            <option key={c.clienteId} value={c.clienteId}>
              {c.nome} · {c[cfg.chaveIdentificador]}
            </option>
          ))}
        </select>
        <span className="bg-border h-5 w-px" />

        {protocolo ? (
          <span className="num text-txt-ghost text-rotulo">
            {protocolo}
            {transferido && <span className="text-claro-hi ml-2 font-bold">· TRANSFERIDO</span>}
          </span>
        ) : (
          <span className="num text-txt-ghost text-rotulo">{cfg.endpoint}</span>
        )}

        <button
          onClick={aoClicarEncerrar}
          disabled={!protocolo}
          title="Encerra o atendimento atual — a próxima mensagem abre um protocolo novo"
          className={`cursor-pointer rounded-lg border px-[11px] py-[6px] text-rotulo font-bold
            transition disabled:cursor-not-allowed disabled:opacity-40 ${
              encerrado
                ? 'bg-elev border-border text-txt-dim hover:border-claro/30 hover:text-txt-hi'
                : confirmarEncerrar
                  ? 'bg-crit border-crit text-white'
                  : 'bg-elev border-crit/35 text-crit hover:bg-crit/8'
            }`}
        >
          {encerrado
            ? 'Nova conversa'
            : confirmarEncerrar
              ? 'Clique de novo para encerrar'
              : 'Encerrar conversa'}
        </button>
      </div>

      {/* Device */}
      <div className="relative z-10 flex h-[min(712px,76vh)] w-[400px] flex-col rounded-[34px] border border-[#332a2c] bg-[#0a0708] p-[9px] shadow-[0_22px_60px_rgb(0_0_0/0.22)]">
        <div className="absolute top-[9px] left-1/2 z-20 h-[22px] w-[112px] -translate-x-1/2 rounded-b-[14px] bg-[#0a0708]" />

        <div
          className={`flex flex-1 flex-col overflow-hidden rounded-[26px] ${cfg.fundo}`}
          style={CORES_TELA_ESCURA}
        >
          <div
            className="num flex h-[30px] shrink-0 items-end justify-between px-5 pb-[3px] text-rotulo font-bold text-white"
            style={{ background: cfg.corBarra }}
          >
            <Relogio />
            <span className="opacity-85">▮▮▮ ▰</span>
          </div>

          <div
            className="flex shrink-0 items-center gap-[11px] border-b border-white/10 px-[15px] py-[11px] text-white"
            style={{ background: cfg.corBarra }}
          >
            {variante === 'whatsapp' && <IconeVoltar size={18} />}
            <div
              className={`flex size-9 items-center justify-center bg-white/15 ${
                variante === 'app' ? 'rounded-[10px]' : 'rounded-full'
              } font-display text-[13px] font-extrabold`}
            >
              {variante === 'app' ? 'C' : <IconeChat size={17} />}
            </div>
            <div className="flex-1">
              <p className="font-display text-[14px] font-bold">{cfg.titulo}</p>
              <p className="mt-px flex items-center gap-[5px] text-rotulo opacity-75">
                {variante === 'app' ? (
                  <span className="inline-block size-[6px] rounded-full bg-[#4ade80]" />
                ) : (
                  <IconeCheck size={10} />
                )}
                {cfg.subtitulo}
              </p>
            </div>
          </div>

          <div
            role="log"
            aria-label={`Conversa no ${cfg.titulo}`}
            className="scroll-area flex flex-1 flex-col gap-[9px] p-[14px_13px]"
          >
            {itens.length === 0 ? (
              <p className="self-center rounded-[9px] bg-white/5 px-[13px] py-[6px] text-center text-rotulo leading-[1.45] text-white/60">
                {identificador
                  ? 'Nenhuma mensagem neste canal ainda. Envie a primeira.'
                  : 'Carregando base de clientes...'}
              </p>
            ) : (
              itens.map(({ m, cartao }) =>
                cartao ? (
                  <ActionCard key={m.id} mensagem={m} superficie={cfg.cartao} />
                ) : (
                  <Bolha key={m.id} mensagem={m} cfg={cfg} />
                ),
              )
            )}
            {enviando && (
              <div className={`self-start rounded-[13px] px-3 py-[11px] ${cfg.bolhaEntrada}`}>
                <span className="flex gap-1">
                  {[0, 0.15, 0.3].map((d) => (
                    <i
                      key={d}
                      className="size-[6px] rounded-full bg-current opacity-40"
                      style={{ animation: `typing-bounce 1.2s ${d}s infinite` }}
                    />
                  ))}
                </span>
              </div>
            )}
            {encerrado && (
              <RatingCard
                avaliacao={atendimento.avaliacao}
                aoAvaliar={avaliar}
                superficie={cfg.cartao}
              />
            )}
            <div ref={fim} />
          </div>

          {transferido && !encerrado && (
            <div className="animate-fade-in shrink-0 border-t border-[#e30613]/35 bg-[#e30613]/15 px-3 py-[9px] text-center">
              <p className="text-rotulo leading-[1.5] text-[#ffb3b8]">
                <b>Atendimento transferido para um humano.</b> O bot não responde mais por
                aqui — responda pelo <b>Dashboard</b>, ou clique em <b>Encerrar conversa</b> acima
                para começar do zero.
              </p>
            </div>
          )}

          {erro && (
            <p className="shrink-0 bg-[#e30613]/20 px-3 py-2 text-center text-rotulo text-[#ffb3b8]">
              {erro.offline ? 'API indisponível — o backend está rodando?' : erro.message}
            </p>
          )}

          <div className="flex shrink-0 flex-wrap gap-[6px] px-3 pb-[10px]">
            {!encerrado && opcoesFluxo.map((o) => (
              <button
                key={o.texto}
                onClick={() => submeter(o.texto)}
                disabled={enviando || !identificador}
                className={`animate-fade-in cursor-pointer rounded-[14px] border px-[12px] py-[6px] text-apoio font-bold transition disabled:opacity-40 ${cfg.chipOpcao}`}
              >
                {o.rotulo}
              </button>
            ))}
            {!encerrado && sugestoes.map((r) => (
              <button
                key={r}
                onClick={() => submeter(r)}
                disabled={enviando || !identificador}
                className={`animate-fade-in cursor-pointer rounded-[14px] border px-[11px] py-[6px] text-rotulo transition disabled:opacity-40 ${cfg.chipSugestao}`}
              >
                {r}
              </button>
            ))}
          </div>

          <div className={`flex shrink-0 items-center gap-2 p-[10px_12px] ${cfg.barraEntrada}`}>
            <input
              aria-label="Mensagem do cliente"
              value={texto}
              disabled={!identificador || encerrado}
              onChange={(e) => setTexto(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && submeter()}
              placeholder={encerrado ? 'Atendimento encerrado' : 'Mensagem...'}
              className={`flex-1 rounded-full px-[15px] py-[10px] text-[12.5px] outline-none placeholder:text-white/40 focus:ring-2 focus:ring-white/15 ${cfg.campo}`}
            />
            <button
              onClick={() => submeter()}
              disabled={enviando || encerrado || !texto.trim()}
              aria-label="Enviar mensagem"
              className={`flex size-[38px] shrink-0 cursor-pointer items-center justify-center rounded-full text-white transition disabled:opacity-40 ${cfg.botao}`}
            >
              <IconeEnviar size={16} />
            </button>
          </div>
        </div>
      </div>

      <p className="text-txt-ghost relative z-10 text-[11px]">
        {variante === 'app'
          ? 'No App o cliente já está logado — a identidade vem verificada.'
          : 'Mesmo cliente, outro canal — o Vortex costura o contexto entre os dois.'}
      </p>
      {/* Para quem apresenta: no WhatsApp o bot pede os 3 primeiros dígitos do
          CPF. Os dados são fictícios — mostrar aqui evita travar a demo. */}
      {variante === 'whatsapp' && selecionado?.dicaVerificacao && (
        <p className="bg-panel border-border text-txt-dim relative z-10 -mt-2 rounded-full border px-3 py-1 text-[11px]">
          Verificação de identidade: os 3 primeiros dígitos do CPF de{' '}
          {selecionado.nome.split(' ')[0]} são{' '}
          <b className="num text-txt-hi">{selecionado.dicaVerificacao}</b>
        </p>
      )}
    </div>
  )
}
