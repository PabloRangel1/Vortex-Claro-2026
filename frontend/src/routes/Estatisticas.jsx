import { useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'

import { ColunasEmpilhadas } from '../components/charts/ColunasEmpilhadas'
import { Grafico, Legenda } from '../components/charts/Grafico'
import { LinhaFriccao } from '../components/charts/LinhaFriccao'
import { ImpactoVortex } from '../components/estatisticas/ImpactoVortex'

import { useEstatisticas } from '../hooks/useVortex'
import { rotuloAcao } from '../lib/acoes'
import { faixaDe } from '../lib/friction'
import { SectionTitle } from '../components/ui/SectionTitle'
import {
  IconeCheck,
  IconeIdeia,
  IconeIntencao,
  IconeRaio,
  IconeTroca,
  IconeUsuarios,
} from '../components/ui/icons'

const ROTULO_NIVEL = { estavel: 'Estável', atencao: 'Atenção', critico: 'Crítico' }

/* ------------------------------------------------------------------ blocos */

function Cartao({ titulo, icone, children, className = '' }) {
  return (
    <section className={`bg-panel border-border rounded-2xl border shadow-[var(--shadow-cartao)] p-5 ${className}`}>
      <SectionTitle icone={icone}>{titulo}</SectionTitle>
      <div className="mt-4">{children}</div>
    </section>
  )
}

function Indicador({ rotulo, valor, sufixo, cor, apoio }) {
  return (
    <div className="bg-panel border-border rounded-2xl border shadow-[var(--shadow-cartao)] p-5">
      <p className="text-txt-ghost text-rotulo font-bold tracking-[1.2px] uppercase">
        {rotulo}
      </p>
      <p
        className="num font-display mt-2 text-[34px] leading-none font-extrabold tracking-[-0.03em]"
        style={{ color: cor ?? 'var(--color-txt-hi)' }}
      >
        {valor}
        {sufixo && <span className="ml-0.5 text-[16px] font-bold">{sufixo}</span>}
      </p>
      {apoio && <p className="text-txt-dim mt-1.5 text-[11.5px]">{apoio}</p>}
    </div>
  )
}

/** Barra horizontal — a forma certa para comparar magnitudes entre categorias. */
function BarraRanking({ itens, maximo, corDe, rotuloDe, valorDe, apoioDe }) {
  if (itens.length === 0) {
    return <p className="text-txt-ghost text-[12px]">Sem dados ainda.</p>
  }
  return (
    <div className="flex flex-col gap-3">
      {itens.map((item, i) => {
        const valor = valorDe(item)
        // Zero não desenha traço: o piso de 2% existe só para valores baixos
        // não sumirem, não para inventar presença onde não há dado.
        const largura = valor === 0 || maximo === 0 ? 0 : Math.max(2, (valor / maximo) * 100)
        return (
          <div key={i}>
            <div className="mb-1 flex items-baseline justify-between gap-3">
              <span className="text-txt truncate text-[12.5px] font-semibold">
                {rotuloDe(item)}
              </span>
              <span className="num text-txt-hi shrink-0 text-[12.5px] font-bold">
                {valor}
              </span>
            </div>
            <div className="bg-void h-[7px] w-full overflow-hidden rounded-full">
              <div
                className="h-full rounded-full"
                style={{
                  width: `${largura}%`,
                  background: corDe(item),
                  transition: 'width .8s cubic-bezier(.16,1,.3,1)',
                }}
              />
            </div>
            {apoioDe && (
              <p className="text-txt-ghost mt-1 text-apoio">{apoioDe(item)}</p>
            )}
          </div>
        )
      })}
    </div>
  )
}

/** Distribuição das faixas numa barra única — mostra a proporção, não o ranking. */
function BarraNiveis({ porNivel, total }) {
  if (total === 0) return <p className="text-txt-ghost text-[12px]">Sem dados ainda.</p>
  return (
    <>
      <div className="bg-void flex h-3 w-full overflow-hidden rounded-full">
        {porNivel.map((n) => (
          n.total > 0 && (
            <div
              key={n.nivel}
              style={{
                width: `${n.percentual}%`,
                background: faixaDe(n.nivel).cor,
                transition: 'width .8s cubic-bezier(.16,1,.3,1)',
              }}
              title={`${ROTULO_NIVEL[n.nivel]}: ${n.total}`}
            />
          )
        ))}
      </div>
      {/* Legenda obrigatória: são 3 séries, identidade nunca só por cor. */}
      <div className="mt-4 flex flex-col gap-2">
        {porNivel.map((n) => (
          <div key={n.nivel} className="flex items-center gap-2.5">
            <span
              className="size-[9px] shrink-0 rounded-sm"
              style={{ background: faixaDe(n.nivel).cor }}
            />
            <span className="text-txt flex-1 text-[12px]">{ROTULO_NIVEL[n.nivel]}</span>
            <span className="num text-txt-hi text-[12px] font-bold">{n.total}</span>
            <span className="num text-txt-ghost w-9 text-right text-[11px]">
              {n.percentual}%
            </span>
          </div>
        ))}
      </div>
    </>
  )
}

function Csat({ csat }) {
  if (csat.total === 0) {
    return (
      <p className="text-txt-ghost text-[12px] leading-relaxed">
        Nenhuma avaliação ainda. Encerre um atendimento e avalie pelo aparelho do
        cliente para alimentar este bloco.
      </p>
    )
  }
  const cor =
    csat.media >= 4 ? 'var(--color-ok)'
    : csat.media >= 3 ? 'var(--color-warn)'
    : 'var(--color-crit)'
  const maximo = Math.max(...csat.distribuicao.map((d) => d.total), 1)

  return (
    <>
      <div className="flex items-end gap-3">
        <span
          className="num font-display text-[40px] leading-none font-extrabold tracking-[-0.03em]"
          style={{ color: cor }}
        >
          {csat.media.toFixed(1)}
        </span>
        <span className="text-txt-dim pb-1 text-[12px]">
          de 5 · {csat.total} {csat.total === 1 ? 'avaliação' : 'avaliações'}
        </span>
      </div>
      <p className="text-txt-dim mt-1 text-[12px]">
        <b className="text-txt-hi num">{csat.percentualSatisfeitos}%</b> satisfeitos
        <span className="text-txt-ghost"> (notas 4 e 5)</span>
      </p>

      <div className="mt-4 flex flex-col gap-1.5">
        {[...csat.distribuicao].reverse().map((d) => (
          <div key={d.nota} className="flex items-center gap-2.5">
            <span className="num text-txt-ghost w-3 text-[11px]">{d.nota}</span>
            <div className="bg-void h-[6px] flex-1 overflow-hidden rounded-full">
              <div
                className="h-full rounded-full"
                style={{
                  width: `${(d.total / maximo) * 100}%`,
                  background: d.nota >= 4 ? 'var(--color-ok)'
                    : d.nota === 3 ? 'var(--color-warn)'
                    : 'var(--color-crit)',
                  transition: 'width .8s cubic-bezier(.16,1,.3,1)',
                }}
              />
            </div>
            <span className="num text-txt-dim w-4 text-right text-[11px]">{d.total}</span>
          </div>
        ))}
      </div>

      {csat.comentarios.length > 0 && (
        <div className="border-border mt-4 border-t pt-3">
          <p className="text-txt-ghost mb-2 text-rotulo font-bold tracking-[1.1px] uppercase">
            Últimos comentários
          </p>
          {csat.comentarios.map((c, i) => (
            <p key={i} className="text-txt mb-1.5 text-[11.5px] leading-[1.5]">
              <span className="num text-txt-ghost">{c.nota}/5</span> — “{c.comentario}”
            </p>
          ))}
        </div>
      )}
    </>
  )
}

/* ------------------------------------------------------------------- página */

const SERIES_DESFECHO = [
  { chave: 'resolvidoBot', rotulo: 'Resolvido pelo bot', cor: 'var(--color-serie-1)' },
  { chave: 'transferido', rotulo: 'Transferido com contexto', cor: 'var(--color-serie-2)' },
  { chave: 'emAndamento', rotulo: 'Em andamento', cor: 'var(--color-serie-3)' },
]

const diaMes = (iso) => `${iso.slice(8, 10)}/${iso.slice(5, 7)}`

function GraficosDoPeriodo({ porDia }) {
  if (!porDia.length) return null
  const colunas = porDia.map((d) => ({
    rotulo: diaMes(d.data),
    total: d.total,
    valores: { resolvidoBot: d.resolvidoBot, transferido: d.transferido, emAndamento: d.emAndamento },
  }))
  const totais = SERIES_DESFECHO.map((s) => ({
    ...s,
    total: colunas.reduce((soma, c) => soma + c.valores[s.chave], 0),
  }))
  return (
    <div className="mb-4 grid grid-cols-[3fr_2fr] gap-4 max-[1100px]:grid-cols-1">
      <Grafico
        titulo="Atendimentos por dia"
        subtitulo="Últimos 10 dias, por desfecho"
        legenda={<Legenda series={totais} />}
        tabela={{
          colunas: ['Dia', ...SERIES_DESFECHO.map((s) => s.rotulo), 'Total'],
          linhas: colunas.map((c) => [
            c.rotulo,
            ...SERIES_DESFECHO.map((s) => c.valores[s.chave]),
            c.total,
          ]),
        }}
      >
        <ColunasEmpilhadas
          dados={colunas}
          series={SERIES_DESFECHO}
          rotuloDica={(c) => `${c.rotulo} · ${c.total} ${c.total === 1 ? 'atendimento' : 'atendimentos'}`}
        />
      </Grafico>
      <Grafico
        titulo="Fricção média por dia"
        subtitulo="Quanto mais alto, mais perto de o cliente desistir"
        tabela={{
          colunas: ['Dia', 'Fricção média'],
          linhas: porDia.map((d) => [diaMes(d.data), d.scoreMedio ?? '—']),
        }}
      >
        <LinhaFriccao
          cor="var(--color-claro)"
          dados={porDia.map((d) => ({ rotulo: diaMes(d.data), valor: d.scoreMedio }))}
          referencias={[
            { valor: 40, rotulo: 'Atenção', cor: 'var(--color-warn)' },
            { valor: 70, rotulo: 'Especialista', cor: 'var(--color-crit)' },
          ]}
          rotuloDica={(d) =>
            d.valor == null ? `${d.rotulo} · sem atendimentos` : `${d.rotulo} · fricção média ${d.valor}`
          }
        />
      </Grafico>
    </div>
  )
}

export function Estatisticas({ aoMudarConexao }) {
  const { estatisticas, erro, carregando } = useEstatisticas()
  const [params, setParams] = useSearchParams()
  const aba = params.get('aba') === 'impacto' ? 'impacto' : 'geral'

  useEffect(() => {
    aoMudarConexao?.({ erro, carregando })
  }, [erro, carregando, aoMudarConexao])

  if (!estatisticas) {
    return (
      <div className="flex flex-1 items-center justify-center">
        <p className="text-txt-dim text-[13px]">
          {erro ? 'Não foi possível carregar as estatísticas.' : 'Carregando...'}
        </p>
      </div>
    )
  }

  const { resumo, porIntencao, porNivel, porCanal, sinais, csat, autoatendimento, porDia, impacto } =
    estatisticas
  const maxIntencao = Math.max(...porIntencao.map((i) => i.total), 1)
  const maxSinal = Math.max(...sinais.map((s) => s.ocorrencias), 1)

  return (
    <div className="scroll-area flex-1 px-6 py-6">
      <div className="mx-auto max-w-[1280px]">
        <header className="mb-6">
          <h1 className="font-display text-txt-hi text-[22px] font-extrabold tracking-[-0.02em]">
            Estatísticas de atendimento
          </h1>
          <p className="text-txt-dim mt-1 text-[13px]">
            Do que os clientes mais reclamam e onde a fricção se concentra.
            Atualiza automaticamente.
          </p>
          <div role="tablist" aria-label="Seções das estatísticas" className="border-border mt-4 flex gap-1 border-b">
            {[
              ['geral', 'Visão geral'],
              ['impacto', 'Impacto do Vortex'],
            ].map(([chave, rotulo]) => (
              <button
                key={chave}
                role="tab"
                type="button"
                aria-selected={aba === chave}
                onClick={() => setParams(chave === 'geral' ? {} : { aba: chave })}
                className={`-mb-px cursor-pointer border-b-2 px-4 py-2 text-[13px] font-semibold transition ${
                  aba === chave
                    ? 'border-claro text-txt-hi'
                    : 'text-txt-dim hover:text-txt-hi border-transparent'
                }`}
              >
                {rotulo}
              </button>
            ))}
          </div>
        </header>

        {aba === 'impacto' ? (
          <ImpactoVortex impacto={impacto} />
        ) : (
        <>

        <div className="mb-4 grid grid-cols-[repeat(auto-fit,minmax(190px,1fr))] gap-4">
          {/* O objetivo do produto vem primeiro: quanto o cliente resolveu sozinho. */}
          <Indicador
            rotulo="Resolvido sem humano"
            valor={autoatendimento.taxaResolucao}
            sufixo="%"
            cor="var(--color-ok)"
            apoio={`${autoatendimento.resolvidosSemHumano} de ${resumo.total} atendimentos · ${autoatendimento.respostasComIa} respostas com IA`}
          />
          <Indicador
            rotulo="Atendimentos"
            valor={resumo.total}
            apoio={`${resumo.emAberto} em aberto · ${resumo.encerrados} encerrados`}
          />
          <Indicador
            rotulo="Score médio"
            valor={resumo.scoreMedio}
            cor={faixaDe(
              resumo.scoreMedio >= 70 ? 'critico' : resumo.scoreMedio >= 40 ? 'atencao' : 'estavel',
            ).cor}
            apoio={`Pico de ${resumo.scoreMaximo} pontos`}
          />
          <Indicador
            rotulo="Taxa de handoff"
            valor={resumo.taxaHandoff}
            sufixo="%"
            cor={resumo.taxaHandoff >= 50 ? 'var(--color-crit)' : undefined}
            apoio={`${resumo.handoffs} para humano · ${resumo.transferencias} ${
              resumo.transferencias === 1 ? 'transferência' : 'transferências'
            } entre setores`}
          />
          <Indicador
            rotulo="Troca de canal"
            valor={resumo.trocaDeCanal}
            apoio={`${
              resumo.total ? Math.round((resumo.trocaDeCanal / resumo.total) * 100) : 0
            }% dos atendimentos passaram por mais de um canal`}
          />
        </div>

        <GraficosDoPeriodo porDia={porDia} />

        <div className="grid grid-cols-[repeat(auto-fit,minmax(320px,1fr))] gap-4">
          <Cartao
            titulo="Do que os clientes reclamam"
            icone={<IconeIdeia size={12} className="text-claro" />}
            className="lg:col-span-2"
          >
            <BarraRanking
              itens={porIntencao}
              maximo={maxIntencao}
              rotuloDe={(i) => (
                <span className="inline-flex items-center gap-2">
                  <IconeIntencao intencao={i.intencao} size={14} className="text-txt-dim" />
                  {i.rotulo}
                </span>
              )}
              valorDe={(i) => i.total}
              corDe={(i) => faixaDe(
                i.scoreMedio >= 70 ? 'critico' : i.scoreMedio >= 40 ? 'atencao' : 'estavel',
              ).cor}
              apoioDe={(i) =>
                `score médio ${i.scoreMedio}${i.handoffs ? ` · ${i.handoffs} com handoff` : ''}`
              }
            />
          </Cartao>

          <Cartao
            titulo="O que o bot resolveu sozinho"
            icone={<IconeCheck size={12} className="text-claro" />}
          >
            <BarraRanking
              itens={autoatendimento.porAcao}
              maximo={Math.max(...autoatendimento.porAcao.map((a) => a.total), 1)}
              rotuloDe={(a) => rotuloAcao(a.acao)}
              valorDe={(a) => a.total}
              corDe={(a) => (a.sucesso === a.total ? 'var(--color-ok)' : 'var(--color-warn)')}
              apoioDe={(a) =>
                a.sucesso === a.total
                  ? 'todas com sucesso'
                  : `${a.sucesso} com sucesso · ${a.total - a.sucesso} sem solução`
              }
            />
          </Cartao>

          <Cartao
            titulo="Estado de fricção"
            icone={<IconeRaio size={12} className="text-claro-hi" />}
          >
            <BarraNiveis porNivel={porNivel} total={resumo.total} />
          </Cartao>

          <Cartao
            titulo="Gatilhos mais frequentes"
            icone={<IconeTroca size={12} className="text-claro" />}
          >
            <BarraRanking
              itens={sinais}
              maximo={maxSinal}
              rotuloDe={(s) => s.rotulo}
              valorDe={(s) => s.ocorrencias}
              corDe={(s) => (s.codigo === 'decaimento' ? 'var(--color-ok)' : 'var(--color-claro)')}
              apoioDe={(s) => `${s.pesoAcumulado > 0 ? '+' : ''}${s.pesoAcumulado} pontos acumulados`}
            />
          </Cartao>

          <Cartao
            titulo="Satisfação do cliente"
            icone={<IconeUsuarios size={12} className="text-claro" />}
          >
            <Csat csat={csat} />
          </Cartao>

          <Cartao
            titulo="Canal de origem"
            icone={<IconeUsuarios size={12} className="text-claro" />}
          >
            <BarraRanking
              itens={porCanal}
              maximo={Math.max(...porCanal.map((c) => c.total), 1)}
              rotuloDe={(c) => c.rotulo}
              valorDe={(c) => c.total}
              corDe={(c) => (c.canal === 'app' ? 'var(--color-claro)' : 'var(--color-wpp)')}
            />
          </Cartao>
        </div>
        </>
        )}
      </div>
    </div>
  )
}
