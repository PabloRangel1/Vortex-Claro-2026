import { useState } from 'react'

import { dataCurta, moeda } from '../../lib/acoes'
import { IconeCheck, IconeRelogio } from '../ui/icons'

/**
 * Cartões do autoatendimento no aparelho do cliente.
 *
 * Montados a partir de `dados` — o resultado estruturado que o backend grava
 * junto de cada ação —, nunca extraindo informação do texto do bot. O texto
 * continua na bolha; o cartão é o "anexo" que torna o resultado palpável.
 */

const STATUS_CONEXAO = {
  online: { rotulo: 'Online', cor: 'var(--color-ok)' },
  instavel: { rotulo: 'Instável', cor: 'var(--color-warn)' },
  offline: { rotulo: 'Sem comunicação', cor: 'var(--color-crit)' },
}

function Moldura({ superficie, children, destaque }) {
  // A superfície vem do tema do aparelho (escuro no App e no WhatsApp).
  const base = superficie
  // shrink-0: na coluna flex da conversa, um item com overflow-hidden pode ser
  // espremido até altura zero quando a conversa passa da altura da tela.
  return (
    <div
      className={`animate-fade-in w-[86%] shrink-0 self-start overflow-hidden rounded-[13px] border ${base}`}
      style={destaque ? { borderTop: `3px solid ${destaque}` } : undefined}
    >
      {children}
    </div>
  )
}

function Rotulo({ children }) {
  return (
    <p className="text-rotulo font-bold tracking-[0.9px] uppercase opacity-55">{children}</p>
  )
}

function Fatura({ dados, superficie }) {
  const [copiado, setCopiado] = useState(false)
  const copiar = async () => {
    try {
      await navigator.clipboard.writeText(dados.codigo_barras)
      setCopiado(true)
      setTimeout(() => setCopiado(false), 1800)
    } catch {
      // Sem permissão de área de transferência: o código continua visível.
    }
  }
  return (
    <Moldura superficie={superficie} destaque="var(--color-claro)">
      <div className="px-[13px] pt-[11px] pb-[9px]">
        <Rotulo>Fatura {dados.referencia} · 2ª via</Rotulo>
        <div className="mt-1 flex items-end justify-between gap-2">
          <p className="font-display num text-[21px] leading-none font-extrabold">
            {moeda(dados.valor_centavos)}
          </p>
          {dados.vencida ? (
            <p className="text-crit text-apoio font-bold">venceu {dataCurta(dados.vencimento)}</p>
          ) : (
            <p className="text-apoio opacity-70">vence {dataCurta(dados.vencimento)}</p>
          )}
        </div>
        {dados.itens?.length > 1 && (
          <ul className="mt-[9px] space-y-[3px] border-t border-current/10 pt-[7px]">
            {dados.itens.map((i) => (
              <li key={i.descricao} className="flex justify-between gap-2 text-apoio">
                <span className="opacity-75">{i.descricao}</span>
                <span className="num">{moeda(i.valor_centavos)}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
      <div className="border-t border-current/10 bg-white/[0.05] px-[13px] py-[9px]">
        <p className="num text-rotulo leading-[1.5] break-all opacity-80">{dados.codigo_barras}</p>
        <div className="mt-[7px] flex items-center justify-between">
          <span className="text-rotulo opacity-50">Código fictício · demonstração</span>
          <button
            onClick={copiar}
            aria-live="polite"
            className="text-claro-hi inline-flex min-h-8 cursor-pointer items-center gap-1 rounded-lg
              border border-current/25 px-3 text-apoio font-bold hover:bg-white/10"
          >
            {copiado ? (
              <>
                <IconeCheck size={12} /> Copiado
              </>
            ) : (
              'Copiar código'
            )}
          </button>
        </div>
      </div>
    </Moldura>
  )
}

function Metrica({ rotulo, valor }) {
  return (
    <div className="flex-1 text-center">
      <p className="num text-[13px] font-bold">{valor}</p>
      <p className="text-rotulo tracking-[0.5px] uppercase opacity-55">{rotulo}</p>
    </div>
  )
}

function Diagnostico({ dados, superficie }) {
  const st = STATUS_CONEXAO[dados.status_conexao] ?? STATUS_CONEXAO.online
  return (
    <Moldura superficie={superficie} destaque={st.cor}>
      <div className="px-[13px] pt-[11px] pb-[10px]">
        <Rotulo>Diagnóstico remoto</Rotulo>
        <div className="mt-[3px] flex items-center justify-between gap-2">
          <p className="text-[12px] font-semibold capitalize">
            {dados.tipo} {dados.modelo}
          </p>
          <span
            className="rounded-full px-2 py-[2px] text-rotulo font-bold"
            style={{ color: st.cor, background: `color-mix(in srgb, ${st.cor} 12%, transparent)` }}
          >
            {st.rotulo}
          </span>
        </div>
        <div className="mt-[10px] flex divide-x divide-current/10 rounded-lg bg-white/[0.05] py-[7px]">
          <Metrica rotulo="Sinal" valor={dados.sinal_dbm != null ? `${dados.sinal_dbm} dBm` : '—'} />
          <Metrica rotulo="Latência" valor={dados.latencia_ms != null ? `${dados.latencia_ms} ms` : '—'} />
          <Metrica rotulo="Perda" valor={`${dados.perda_pacotes_pct}%`} />
        </div>
      </div>
    </Moldura>
  )
}

function Planos({ dados, superficie }) {
  const atual = dados.plano_atual
  return (
    <Moldura superficie={superficie} destaque="var(--color-claro)">
      <div className="px-[13px] pt-[11px] pb-[10px]">
        <Rotulo>Seu plano hoje</Rotulo>
        <p className="mt-[2px] flex justify-between text-[11.5px]">
          <span className="font-semibold">{atual.nome}</span>
          <span className="num opacity-75">{moeda(atual.preco_centavos)}</span>
        </p>
        <div className="mt-[9px] space-y-[6px]">
          {dados.opcoes.map((p, i) => (
            <div key={p.id} className="rounded-[9px] border border-current/12 px-[10px] py-[7px]">
              <div className="flex items-baseline justify-between gap-2">
                <p className="text-[11.5px] font-bold">
                  <span className="num mr-1 opacity-45">{i + 1}</span>
                  {p.nome}
                </p>
                <p className="num text-[11.5px] font-bold">{moeda(p.preco_centavos)}</p>
              </div>
              <p className="mt-[1px] flex justify-between text-rotulo opacity-65">
                <span>
                  {p.franquia}
                  {p.linhas_incluidas > 0 &&
                    ` · ${p.linhas_incluidas} ${p.linhas_incluidas === 1 ? 'linha' : 'linhas'}`}
                </span>
                <span className="num">+{moeda(p.preco_centavos - atual.preco_centavos)}/mês</span>
              </p>
            </div>
          ))}
        </div>
      </div>
    </Moldura>
  )
}

/** Detalhe de uma solicitação concluída, por tipo de ação. */
function detalheConcluido(codigo, d) {
  switch (codigo) {
    case 'vencimento_alterado':
      return { titulo: 'Vencimento alterado', linha: `Dia ${d.dia_atual} → Dia ${d.dia_novo}` }
    case 'plano_atualizado':
      return {
        titulo: 'Plano atualizado',
        linha: `${d.plano_novo_nome} · ${moeda(d.preco_novo_centavos)}/mês`,
      }
    case 'equipamento_reiniciado':
      return { titulo: 'Equipamento reiniciado', linha: `${d.modelo} · conexão restabelecida` }
    case 'contestacao_aberta':
      return {
        titulo: 'Contestação aberta',
        linha: `Fatura ${d.referencia} · retorno em até 5 dias úteis`,
        emAnalise: true,
      }
    case 'contestacao_em_andamento':
      return {
        titulo: 'Contestação já em análise',
        linha: `Fatura ${d.referencia} · aguarde o retorno`,
        emAnalise: true,
      }
    default:
      return null
  }
}

function Concluido({ mensagem, superficie }) {
  const det = detalheConcluido(mensagem.codigo, mensagem.dados)
  const cor = det.emAnalise ? 'var(--color-warn)' : 'var(--color-ok)'
  const protocolo = mensagem.solicitacao ?? mensagem.dados.protocolo_solicitacao
  return (
    <Moldura superficie={superficie}>
      <div className="flex items-center gap-[10px] px-[13px] py-[10px]">
        <span
          className="flex size-[30px] shrink-0 items-center justify-center rounded-full"
          style={{ color: cor, background: `color-mix(in srgb, ${cor} 13%, transparent)` }}
        >
          {det.emAnalise ? <IconeRelogio size={15} /> : <IconeCheck size={15} />}
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-[12px] font-bold" style={{ color: cor }}>
            {det.titulo}
          </p>
          <p className="text-apoio opacity-75">{det.linha}</p>
          {protocolo && (
            <p className="num mt-[3px] text-rotulo font-semibold opacity-90">Protocolo {protocolo}</p>
          )}
        </div>
      </div>
    </Moldura>
  )
}

const POR_CODIGO = {
  segunda_via_gerada: Fatura,
  segunda_via_vencida: Fatura,
  diagnostico_online: Diagnostico,
  diagnostico_instavel: Diagnostico,
  diagnostico_offline: Diagnostico,
  planos_disponiveis: Planos,
  plano_disponivel: Planos,
}

/** Só ações que produziram algo para mostrar viram cartão; falhas ficam no texto. */
export function temCartao(m) {
  return m.tipo === 'acao' && (m.codigo in POR_CODIGO || detalheConcluido(m.codigo, m.dados) != null)
}

export function ActionCard({ mensagem, superficie }) {
  const Componente = POR_CODIGO[mensagem.codigo]
  if (Componente) return <Componente dados={mensagem.dados} superficie={superficie} />
  return <Concluido mensagem={mensagem} superficie={superficie} />
}
