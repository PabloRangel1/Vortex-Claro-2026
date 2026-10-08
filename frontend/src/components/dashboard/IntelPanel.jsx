import { acoesDaConversa, rotuloAcao, rotuloResultado } from '../../lib/acoes'
import { horaCurta } from '../../lib/formatters'
import { IDENTIDADE, ROTULO_STATUS } from '../../lib/friction'
import { faixaDe } from '../../lib/friction'
import { FrictionGauge } from '../gauge/FrictionGauge'
import {
  IconeCheck,
  IconeIdeia,
  IconeIntencao,
  IconeRaio,
  IconeTroca,
  IconeUsuario,
} from '../ui/icons'
import { SectionTitle } from '../ui/SectionTitle'
import { corDaAcao } from './MessageList'

/** Cor do marcador da timeline conforme a natureza do evento. */
const CORES_EVENTO = {
  troca_canal: 'var(--color-claro-hi)',
  pedido_humano: 'var(--color-crit)',
  repeticao: 'var(--color-warn)',
  sentimento_negativo: 'var(--color-warn)',
  intencao_repetida: 'var(--color-warn)',
  loop_sem_resolucao: 'var(--color-warn)',
  impaciencia: 'var(--color-warn)',
  caixa_alta: 'var(--color-warn)',
  decaimento: 'var(--color-ok)',
}

function Secao({ titulo, icone, children, ultima = false }) {
  return (
    <div className={`p-4 ${ultima ? '' : 'border-border-soft border-b'}`}>
      <SectionTitle icone={icone}>{titulo}</SectionTitle>
      {children}
    </div>
  )
}

function Linha({ rotulo, valor, cor }) {
  return (
    <div className="border-border-soft flex items-center justify-between gap-[10px] py-[6.5px] not-first:border-t">
      <span className="text-txt-ghost text-[11px]">{rotulo}</span>
      <span
        className="num text-txt-hi truncate text-right text-[11.5px] font-semibold"
        style={cor ? { color: cor } : undefined}
      >
        {valor}
      </span>
    </div>
  )
}

/** Avaliação do cliente: aparece quando o atendimento termina. */
function AvaliacaoCliente({ atendimento }) {
  if (atendimento.status !== 'encerrado') return null
  const { nota, comentario } = atendimento.avaliacao
  const cor =
    nota == null ? 'var(--color-txt-dim)'
    : nota >= 4 ? 'var(--color-ok)'
    : nota === 3 ? 'var(--color-warn)'
    : 'var(--color-crit)'
  return (
    <Secao titulo="Avaliação do cliente" icone={<IconeUsuario size={12} className="text-claro" />}>
      {nota == null ? (
        <p className="text-txt-dim mt-3 text-apoio">
          Aguardando o cliente avaliar — a pesquisa já apareceu no aparelho dele.
        </p>
      ) : (
        <div className="mt-3">
          <p className="num text-[26px] leading-none font-extrabold" style={{ color: cor }}>
            {nota}
            <span className="text-txt-ghost text-[13px] font-bold"> / 5</span>
          </p>
          {comentario && (
            <p className="text-txt mt-2 text-apoio leading-[1.5]">“{comentario}”</p>
          )}
        </div>
      )}
    </Secao>
  )
}

/**
 * O que o bot já tentou. No handoff, é o que poupa o atendente de refazer
 * diagnóstico ou segunda via — e o cliente de explicar tudo de novo.
 */
function Autoatendimento({ atendimento }) {
  const acoes = acoesDaConversa(atendimento.mensagens)
  const { fluxo, handoff } = atendimento
  const resolvidas = acoes.filter((a) => a.status === 'sucesso' && !a.requerHandoff).length
  const antesDoHandoff = (a) => handoff.acionado && new Date(a.criadaEm) <= new Date(handoff.em)

  return (
    <Secao titulo="Autoatendimento" icone={<IconeCheck size={12} className="text-claro" />}>
      {acoes.length === 0 && !fluxo ? (
        <p className="text-txt-ghost mt-3 text-[11.5px] leading-relaxed">
          O bot ainda não executou nenhuma ação neste atendimento.
        </p>
      ) : (
        <div className="mt-[10px]">
          {acoes.length > 0 && (
            <p className="text-txt-dim mb-[8px] text-apoio">
              <b className="text-txt-hi">{acoes.length}</b> {acoes.length === 1 ? 'ação' : 'ações'} ·{' '}
              <b style={{ color: 'var(--color-ok)' }}>{resolvidas}</b> resolvida
              {resolvidas === 1 ? '' : 's'}
              {handoff.acionado && ' · tentadas antes do handoff'}
            </p>
          )}
          <div className="space-y-[6px]">
            {acoes.map((a) => (
              <div
                key={a.id}
                className={`bg-elev border-border flex items-start gap-[9px] rounded-[9px] border px-[10px] py-[7px] ${
                  handoff.acionado && !antesDoHandoff(a) ? 'opacity-60' : ''
                }`}
              >
                <span
                  className="mt-[4px] size-[8px] shrink-0 rounded-full"
                  style={{ background: corDaAcao(a) }}
                />
                <div className="min-w-0 flex-1">
                  <p className="text-txt-hi text-[11.5px] font-semibold">{rotuloAcao(a.acao)}</p>
                  <p className="text-txt-dim text-apoio">{rotuloResultado(a.codigo)}</p>
                </div>
                <div className="text-right">
                  <p className="num text-txt-ghost text-rotulo">{horaCurta(a.criadaEm)}</p>
                  {a.solicitacao && (
                    <p className="num text-txt-dim text-rotulo">{a.solicitacao}</p>
                  )}
                </div>
              </div>
            ))}
          </div>
          {fluxo && (
            <p className="border-warn/40 text-txt mt-[8px] rounded-[9px] border border-dashed px-[10px] py-[7px] text-apoio">
              Aguardando o cliente:{' '}
              <b>
                {fluxo.etapa === 'aguardando_confirmacao' ? 'confirmação' : 'escolha'} de{' '}
                {rotuloAcao(fluxo.acaoPendente).toLowerCase()}
              </b>
            </p>
          )}
        </div>
      )}
    </Secao>
  )
}

/** "3º contato em 30 dias" é fricção que nenhum turno isolado mostra. */
function ContatosAnteriores({ atendimento, aoAbrirProtocolo }) {
  const { contatos30Dias, contatosAnteriores } = atendimento
  const recorrente = contatos30Dias >= 3
  return (
    <div className="border-border-soft mt-[10px] border-t pt-[10px]">
      <p className="flex items-baseline justify-between gap-2">
        <span className="text-txt-ghost text-[11px]">Contatos em 30 dias</span>
        <span
          className={`num text-[11.5px] font-bold ${recorrente ? 'text-warn' : 'text-txt-hi'}`}
          title={recorrente ? 'Cliente recorrente: sinal de demanda não resolvida' : undefined}
        >
          {contatos30Dias === 1 ? '1º contato' : `${contatos30Dias}º contato`}
        </span>
      </p>
      {contatosAnteriores.length > 0 && (
        <ul className="mt-[6px] space-y-[4px]">
          {contatosAnteriores.map((c) => (
            <li key={c.protocolo}>
              <button
                type="button"
                onClick={() => aoAbrirProtocolo?.(c.protocolo)}
                className="hover:bg-void flex w-full cursor-pointer items-center justify-between gap-2 rounded-md px-[6px] py-[4px] text-left transition"
                title="Abrir este atendimento"
              >
                <span className="min-w-0">
                  <span className="text-txt block truncate text-apoio font-semibold">
                    {c.intencaoRotulo}
                  </span>
                  <span className="num text-txt-ghost text-rotulo">
                    {new Date(c.abertoEm).toLocaleDateString('pt-BR')} · {c.protocolo}
                  </span>
                </span>
                <span className="text-txt-dim shrink-0 text-rotulo">
                  {ROTULO_STATUS[c.status] ?? c.status}
                  {c.nota != null && ` · ${c.nota}/5`}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

export function IntelPanel({ atendimento, aoAbrirProtocolo }) {
  if (!atendimento) {
    return (
      <aside className="bg-panel border-border scroll-area min-h-0 w-[346px] flex-1 shrink-0 border-l max-[1500px]:w-[308px]">
        <Secao titulo="Inteligência do Atendimento" icone={<IconeRaio size={12} />} ultima>
          <p className="text-txt-ghost mt-3 text-[11.5px] leading-relaxed">
            Score de fricção, intenção detectada e histórico de canais aparecem aqui assim que
            você abrir um atendimento.
          </p>
        </Secao>
      </aside>
    )
  }

  const { cliente } = atendimento

  return (
    <aside className="bg-panel border-border scroll-area min-h-0 w-[346px] flex-1 shrink-0 border-l max-[1500px]:w-[308px]">
      <Secao titulo="Cliente" icone={<IconeUsuario size={12} className="text-claro" />}>
        <div className="mt-[10px]">
          <Linha rotulo="Protocolo" valor={atendimento.protocolo} />
          <Linha rotulo="CPF" valor={cliente.cpf} />
          <Linha
            rotulo="Identidade"
            valor={(IDENTIDADE[atendimento.identidade] ?? IDENTIDADE.nao_verificada).rotulo}
            cor={(IDENTIDADE[atendimento.identidade] ?? IDENTIDADE.nao_verificada).cor}
          />
          <Linha rotulo="Plano" valor={cliente.plano} />
          <Linha rotulo="Cliente desde" valor={cliente.clienteDesde} />
          {cliente.cidade && <Linha rotulo="Cidade" valor={cliente.cidade} />}
          {cliente.email && <Linha rotulo="E-mail" valor={cliente.email} />}
          <Linha rotulo="Canal atual" valor={atendimento.canalAtualRotulo} />
          <Linha rotulo="Canal de origem" valor={atendimento.canalOrigemRotulo} />
        </div>
        <ContatosAnteriores atendimento={atendimento} aoAbrirProtocolo={aoAbrirProtocolo} />
      </Secao>

      <Secao
        titulo="Intenção Detectada (NLP)"
        icone={<IconeIdeia size={12} className="text-claro" />}
      >
        <div className="bg-elev border-border mt-[10px] rounded-[11px] border p-[13px]">
          <div className="mb-[11px] flex items-center gap-3">
            <span className="bg-claro-wash text-claro-hi flex size-10 shrink-0 items-center justify-center rounded-[10px]">
              <IconeIntencao intencao={atendimento.intencao} size={20} />
            </span>
            <div>
              <p className="font-display text-txt-hi text-[14px] font-bold">
                {atendimento.intencaoRotulo}
              </p>
              <p className="num text-claro mt-[2px] text-rotulo font-bold">
                Confiança {atendimento.confianca}%
              </p>
            </div>
          </div>
          <div className="bg-void h-[6px] w-full overflow-hidden rounded">
            <div
              className="h-full rounded bg-gradient-to-r from-[#b3050f] to-[#e30613]"
              style={{
                width: `${atendimento.confianca}%`,
                transition: 'width .9s cubic-bezier(.16,1,.3,1)',
              }}
            />
          </div>
        </div>
      </Secao>

      <AvaliacaoCliente atendimento={atendimento} />

      <Autoatendimento atendimento={atendimento} />

      <Secao
        titulo="Score de Fricção"
        icone={<IconeRaio size={12} className="text-claro-hi" />}
      >
        <FrictionGauge
          score={atendimento.score}
          nivel={atendimento.nivel}
          delta={atendimento.deltaScore}
          historico={atendimento.historicoScore}
        />
      </Secao>

      <Secao
        titulo="Histórico de Fricção"
        icone={<IconeTroca size={12} className="text-claro" />}
        ultima
      >
        <div className="mt-3">
          {atendimento.eventos.length === 0 ? (
            <p className="text-txt-ghost text-[11.5px] leading-relaxed">
              Nenhum sinal de fricção registrado até aqui.
            </p>
          ) : (
            atendimento.eventos.map((evento, i) => {
              const cor = CORES_EVENTO[evento.codigo] ?? 'var(--color-claro)'
              const ultimo = i === atendimento.eventos.length - 1
              return (
                <div
                  key={`${evento.criadoEm}-${i}`}
                  className="animate-fade-in relative flex gap-3 pb-[14px] last:pb-0"
                  style={{ animationDelay: `${Math.min(i * 60, 400)}ms` }}
                >
                  {!ultimo && (
                    <span className="bg-border absolute top-4 bottom-0 left-[5px] w-px" />
                  )}
                  <span
                    className="border-panel z-[1] mt-[3px] size-[11px] shrink-0 rounded-full border-2"
                    style={{ background: cor, boxShadow: `0 0 0 3px ${cor}22` }}
                  />
                  <div className="flex-1">
                    <p className="num text-txt-ghost text-rotulo">
                      {horaCurta(evento.criadoEm)} ·{' '}
                      <span style={{ color: cor }}>
                        {evento.peso > 0 ? '+' : ''}
                        {evento.peso}
                      </span>{' '}
                      → {evento.scoreResultante}
                    </p>
                    <p className="text-txt mt-[2px] text-[11.5px] leading-[1.5]">
                      {evento.descricao}
                    </p>
                  </div>
                </div>
              )
            })
          )}
        </div>
      </Secao>
    </aside>
  )
}
