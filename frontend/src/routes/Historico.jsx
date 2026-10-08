import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { adaptarClienteLista, adaptarHistorico } from '../api/adapters'
import {
  buscarClientesHistorico,
  buscarHistoricoCliente,
  buscarProtocolo,
} from '../api/endpoints'
import { SectionTitle } from '../components/ui/SectionTitle'
import { IconeBusca, IconeRelogio, IconeSeta, IconeUsuarios } from '../components/ui/icons'
import { PillCanal } from '../components/ui/Pill'
import { IDENTIDADE, ROTULO_STATUS, faixaDe, nivelPorScore } from '../lib/friction'

/**
 * Histórico de clientes e consulta de protocolo.
 *
 * Duas portas de entrada para a mesma informação: o atendente digita o
 * protocolo que o cliente informou (atendimento ou SOL-…) ou procura o
 * cliente pelo nome/CPF. Nos dois casos chega ao histórico completo — todos
 * os atendimentos, o que foi resolvido, o que foi transferido e por quê,
 * e as avaliações.
 */

const SEGMENTOS = [
  ['', 'Todos'],
  ['pos', 'Pós-pago'],
  ['controle', 'Controle'],
  ['fibra', 'Fibra'],
]

const TIPO_SOLICITACAO = {
  contestacao: 'Contestação',
  alteracao_vencimento: 'Alteração de vencimento',
  upgrade_plano: 'Upgrade de plano',
  reinicio_equipamento: 'Reinício do equipamento',
}
const STATUS_SOLICITACAO = { em_analise: 'Em análise', concluida: 'Concluída' }

const dataHora = (iso) =>
  iso
    ? new Date(iso).toLocaleString('pt-BR', {
        day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit',
      })
    : '—'
const data = (iso) => (iso ? new Date(`${iso.slice(0, 10)}T12:00:00`).toLocaleDateString('pt-BR') : '—')

function Campo({ rotulo, valor }) {
  return (
    <div>
      <dt className="text-txt-ghost text-rotulo font-bold tracking-[0.6px] uppercase">{rotulo}</dt>
      <dd className="text-txt-hi mt-[2px] truncate text-[12.5px] font-semibold">{valor || '—'}</dd>
    </div>
  )
}

function ItemCliente({ c, selecionado, aoSelecionar }) {
  return (
    <button
      type="button"
      onClick={() => aoSelecionar(c.clienteId)}
      className={`w-full cursor-pointer rounded-[10px] border p-[10px_12px] text-left transition ${
        selecionado ? 'bg-claro/10 border-claro/30' : 'hover:bg-claro/5 border-transparent'
      }`}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="font-display text-txt-hi truncate text-[13px] font-bold">{c.nome}</span>
        {c.emAberto && (
          <span className="bg-warn/10 text-warn border-warn/30 shrink-0 rounded-md border px-[6px] text-rotulo font-bold">
            em aberto
          </span>
        )}
      </div>
      <p className="text-txt-dim mt-[2px] truncate text-apoio">
        {c.segmentoRotulo} · {c.plano}
      </p>
      <p className="text-txt-ghost mt-[3px] flex justify-between text-rotulo">
        <span>
          {c.totalAtendimentos} {c.totalAtendimentos === 1 ? 'atendimento' : 'atendimentos'}
          {c.csatMedio != null && ` · CSAT ${c.csatMedio}`}
        </span>
        <span className="num">{c.ultimoContato ? data(c.ultimoContato) : 'sem contato'}</span>
      </p>
    </button>
  )
}

function Atendimento({ a, destacado, aoAbrir }) {
  const faixa = faixaDe(nivelPorScore(a.score))
  const ident = IDENTIDADE[a.identidade] ?? IDENTIDADE.nao_verificada
  return (
    <li
      id={`atd-${a.protocolo}`}
      className={`bg-elev border-border rounded-xl border p-4 transition ${
        destacado ? 'ring-claro/60 border-claro/40 ring-2' : ''
      }`}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <span className="num text-txt-hi text-[13px] font-bold">{a.protocolo}</span>
          {a.canais.map((c) => (
            <PillCanal key={c} canal={c} curto />
          ))}
          <span className="text-txt-dim num text-rotulo">{dataHora(a.abertoEm)}</span>
        </div>
        <button
          type="button"
          onClick={() => aoAbrir(a.protocolo)}
          className="text-claro-hi inline-flex cursor-pointer items-center gap-1 text-apoio font-bold hover:underline"
        >
          Abrir no painel <IconeSeta size={12} />
        </button>
      </div>

      <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1">
        <span className="text-txt-hi text-[13px] font-semibold">{a.intencaoRotulo}</span>
        <span className="text-txt-dim text-apoio">{ROTULO_STATUS[a.status] ?? a.status}</span>
        <span className="num text-apoio font-bold" style={{ color: faixa.cor }}>
          fricção {a.score}
        </span>
        <span className="text-apoio" style={{ color: ident.cor }}>
          {ident.rotulo}
        </span>
      </div>

      {a.houveHandoff && (
        <p className="text-txt mt-2 text-apoio leading-[1.5]">
          <b className="text-txt-dim">Transferido:</b> {a.motivoHandoff}
        </p>
      )}
      {a.nota != null ? (
        <p className="text-txt mt-1 text-apoio">
          <b className="text-txt-dim">Avaliação:</b> {a.nota}/5
          {a.comentario && <span className="text-txt-dim"> — “{a.comentario}”</span>}
        </p>
      ) : a.status === 'encerrado' ? (
        <p className="text-txt-ghost mt-1 text-apoio">Sem avaliação do cliente.</p>
      ) : null}
    </li>
  )
}

export function Historico({ aoMudarConexao }) {
  const navigate = useNavigate()
  const [segmento, setSegmento] = useState('')
  const [busca, setBusca] = useState('')
  const [clientes, setClientes] = useState(null)
  const [selecionado, setSelecionado] = useState(null)
  const [historico, setHistorico] = useState(null)

  const [protocolo, setProtocolo] = useState('')
  const [destaque, setDestaque] = useState(null)
  const [solicitacaoAchada, setSolicitacaoAchada] = useState(null)
  const [aviso, setAviso] = useState(null)
  const campoProtocolo = useRef(null)

  // Lista de clientes (com uma pequena espera na digitação da busca).
  useEffect(() => {
    let cancelado = false
    const id = setTimeout(() => {
      buscarClientesHistorico({ segmento, busca: busca.trim() })
        .then((lista) => {
          if (cancelado) return
          setClientes(lista.map(adaptarClienteLista))
          aoMudarConexao?.({ erro: null, carregando: false })
        })
        .catch((e) => !cancelado && aoMudarConexao?.({ erro: e, carregando: false }))
    }, busca ? 250 : 0)
    return () => {
      cancelado = true
      clearTimeout(id)
    }
  }, [segmento, busca, aoMudarConexao])

  // Sem seleção: abre o cliente com o contato mais recente.
  useEffect(() => {
    if (!selecionado && clientes?.length) setSelecionado(clientes[0].clienteId)
  }, [clientes, selecionado])

  useEffect(() => {
    if (!selecionado) return
    let cancelado = false
    setHistorico(null)
    buscarHistoricoCliente(selecionado)
      .then((h) => !cancelado && setHistorico(adaptarHistorico(h)))
      .catch(() => {})
    return () => {
      cancelado = true
    }
  }, [selecionado])

  // Depois de achar um protocolo, rola até o atendimento destacado.
  useEffect(() => {
    if (historico && destaque) {
      document.getElementById(`atd-${destaque}`)?.scrollIntoView({ block: 'center', behavior: 'smooth' })
    }
  }, [historico, destaque])

  const consultar = async (e) => {
    e.preventDefault()
    const p = protocolo.trim()
    if (!p) return
    setAviso(null)
    try {
      const r = await buscarProtocolo(p)
      setSegmento('')
      setBusca('')
      setSelecionado(r.cliente_ref)
      setDestaque(r.protocolo_atendimento)
      setSolicitacaoAchada(r.solicitacao)
    } catch (erro) {
      setDestaque(null)
      setSolicitacaoAchada(null)
      setAviso(erro.status === 404 ? `Protocolo ${p} não encontrado.` : 'Não foi possível consultar agora.')
      campoProtocolo.current?.focus()
    }
  }

  const escolherCliente = (id) => {
    setDestaque(null)
    setSolicitacaoAchada(null)
    setSelecionado(id)
  }

  const abrirNoPainel = (p) => navigate(`/?protocolo=${encodeURIComponent(p)}`)

  return (
    <div className="scroll-area flex-1 px-6 py-6">
      <div className="mx-auto max-w-[1280px]">
        <header className="mb-5 flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="font-display text-txt-hi text-[22px] font-extrabold tracking-[-0.02em]">
              Histórico de clientes e protocolos
            </h1>
            <p className="text-txt-dim mt-1 text-[13px]">
              Consulte pelo protocolo que o cliente informou, ou procure o cliente pelo nome ou CPF.
            </p>
          </div>

          <form onSubmit={consultar} className="flex items-start gap-2">
            <div>
              <label htmlFor="protocolo" className="sr-only">
                Número do protocolo
              </label>
              <input
                id="protocolo"
                ref={campoProtocolo}
                value={protocolo}
                onChange={(e) => setProtocolo(e.target.value)}
                placeholder="2026-1005-77301 ou SOL-20261005-1001"
                className="bg-input border-border text-txt focus:border-claro focus:ring-claro/10 num w-[300px]
                  rounded-[10px] border px-3 py-[10px] text-[12.5px] outline-none focus:ring-[3px]"
              />
              {aviso && (
                <p role="alert" className="text-crit mt-1 text-apoio font-semibold">
                  {aviso}
                </p>
              )}
            </div>
            <button
              type="submit"
              className="bg-claro hover:bg-claro-hi cursor-pointer rounded-[10px] px-4 py-[10px] text-[12.5px] font-bold text-white transition"
            >
              Consultar protocolo
            </button>
          </form>
        </header>

        <div className="grid grid-cols-[320px_1fr] gap-5 max-[1100px]:grid-cols-1">
          {/* --------------------------------------------- lista de clientes */}
          <aside className="bg-panel border-border flex max-h-[calc(100vh-220px)] flex-col rounded-2xl border shadow-[var(--shadow-cartao)]">
            <div className="border-border border-b p-4">
              <SectionTitle icone={<IconeUsuarios size={13} />}>Clientes</SectionTitle>
              <div className="relative mt-3">
                <IconeBusca
                  size={13}
                  className="text-txt-ghost absolute top-1/2 left-[11px] -translate-y-1/2"
                />
                <input
                  type="search"
                  aria-label="Buscar cliente por nome ou CPF"
                  value={busca}
                  onChange={(e) => setBusca(e.target.value)}
                  placeholder="Nome ou CPF..."
                  className="bg-input border-border text-txt focus:border-claro placeholder:text-txt-ghost w-full
                    rounded-[9px] border py-[9px] pr-3 pl-[33px] text-[12px] outline-none"
                />
              </div>
              <div className="mt-2 flex flex-wrap gap-[6px]" role="group" aria-label="Tipo de cliente">
                {SEGMENTOS.map(([valor, rotulo]) => (
                  <button
                    key={valor}
                    type="button"
                    onClick={() => setSegmento(valor)}
                    aria-pressed={segmento === valor}
                    className={`cursor-pointer rounded-full border px-3 py-[4px] text-apoio font-semibold transition ${
                      segmento === valor
                        ? 'bg-claro border-claro text-white'
                        : 'border-border text-txt-dim hover:border-claro/35 hover:text-txt-hi'
                    }`}
                  >
                    {rotulo}
                  </button>
                ))}
              </div>
            </div>
            <div className="scroll-area flex-1 space-y-1 p-2">
              {clientes === null ? (
                <p className="text-txt-ghost p-4 text-center text-apoio">Carregando...</p>
              ) : clientes.length === 0 ? (
                <p className="text-txt-ghost p-4 text-center text-apoio">Nenhum cliente com estes filtros.</p>
              ) : (
                clientes.map((c) => (
                  <ItemCliente
                    key={c.clienteId}
                    c={c}
                    selecionado={c.clienteId === selecionado}
                    aoSelecionar={escolherCliente}
                  />
                ))
              )}
            </div>
          </aside>

          {/* --------------------------------------------- histórico */}
          <section className="min-w-0">
            {!historico ? (
              <p className="text-txt-dim p-6 text-[13px]">Carregando histórico...</p>
            ) : (
              <>
                <div className="bg-panel border-border rounded-2xl border shadow-[var(--shadow-cartao)] p-5">
                  <div className="flex flex-wrap items-baseline justify-between gap-2">
                    <h2 className="font-display text-txt-hi text-[18px] font-extrabold">
                      {historico.cliente.nome}
                    </h2>
                    <span className="text-txt-dim text-apoio">
                      {historico.segmentoRotulo} · cliente desde {historico.cliente.clienteDesde}
                    </span>
                  </div>
                  <dl className="mt-4 grid grid-cols-[repeat(auto-fit,minmax(170px,1fr))] gap-4">
                    <Campo rotulo="CPF" valor={historico.cliente.cpf} />
                    <Campo rotulo="Plano" valor={historico.cliente.plano} />
                    <Campo rotulo="Nascimento" valor={data(historico.dataNascimento)} />
                    <Campo rotulo="Cidade" valor={historico.cliente.cidade} />
                    <Campo rotulo="E-mail" valor={historico.cliente.email} />
                    <Campo rotulo="WhatsApp" valor={historico.whatsapp} />
                  </dl>
                </div>

                {solicitacaoAchada && (
                  <div className="bg-claro-wash border-claro/30 mt-4 rounded-xl border px-4 py-3 text-apoio">
                    <b className="text-claro-hi">Solicitação {solicitacaoAchada.protocolo}</b>{' '}
                    · {TIPO_SOLICITACAO[solicitacaoAchada.tipo] ?? solicitacaoAchada.tipo} ·{' '}
                    {STATUS_SOLICITACAO[solicitacaoAchada.status] ?? solicitacaoAchada.status} ·
                    registrada no atendimento destacado abaixo.
                  </div>
                )}

                <div className="mt-5">
                  <SectionTitle icone={<IconeRelogio size={12} />}>
                    Atendimentos ({historico.atendimentos.length})
                  </SectionTitle>
                  {historico.atendimentos.length === 0 ? (
                    <p className="text-txt-dim mt-3 text-apoio">Este cliente ainda não falou com a gente.</p>
                  ) : (
                    <ol className="mt-3 space-y-3">
                      {historico.atendimentos.map((a) => (
                        <Atendimento
                          key={a.protocolo}
                          a={a}
                          destacado={a.protocolo === destaque}
                          aoAbrir={abrirNoPainel}
                        />
                      ))}
                    </ol>
                  )}
                </div>

                {historico.solicitacoes.length > 0 && (
                  <div className="mt-6">
                    <SectionTitle>Solicitações ({historico.solicitacoes.length})</SectionTitle>
                    <ul className="bg-panel border-border mt-3 divide-y divide-[var(--color-border-soft)] rounded-xl border">
                      {historico.solicitacoes.map((s) => (
                        <li key={s.protocolo} className="flex flex-wrap items-center justify-between gap-2 px-4 py-3">
                          <span className="min-w-0">
                            <span className="num text-txt-hi text-apoio font-bold">{s.protocolo}</span>{' '}
                            <span className="text-txt text-apoio">
                              · {TIPO_SOLICITACAO[s.tipo] ?? s.tipo}
                            </span>
                            <span className="text-txt-ghost block text-rotulo">{s.descricao}</span>
                          </span>
                          <span className="text-txt-dim text-apoio">
                            {STATUS_SOLICITACAO[s.status] ?? s.status} · {dataHora(s.criadaEm)}
                          </span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </>
            )}
          </section>
        </div>
      </div>
    </div>
  )
}
