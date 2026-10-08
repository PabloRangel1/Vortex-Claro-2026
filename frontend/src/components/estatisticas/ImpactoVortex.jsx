import { moeda } from '../../lib/acoes'
import { faixaDe, nivelPorScore } from '../../lib/friction'
import { Grafico, useLargura } from '../charts/Grafico'
import { IconeCheck, IconeSeta, IconeUsuario } from '../ui/icons'
import { PillCanal } from '../ui/Pill'

/**
 * "O cliente que a Claro não perdeu."
 *
 * O problema que o produto ataca: o cliente troca de canal, a Claro perde o
 * fio da conversa, ele reconta tudo e desiste. Esta aba põe lado a lado o que
 * aconteceria sem continuidade (contrafactual) e o que o Vortex preservou —
 * calculado só com os atendimentos registrados, com as premissas à vista.
 */

const SEM = 'var(--color-sem-vortex)'
const COM = 'var(--color-claro)'

/** Halteres: antes -> depois por métrica, num eixo comum. */
function Halteres({ linhas }) {
  const [ref, largura] = useLargura()
  const maximo = Math.max(...linhas.flatMap((l) => [l.sem, l.com]), 1)
  const rotuloL = Math.min(260, largura * 0.42)
  const areaL = Math.max(largura - rotuloL - 40, 0)
  const x = (v) => rotuloL + (v / maximo) * areaL
  const ALTURA_LINHA = 52

  return (
    <div ref={ref}>
      {largura > 0 && (
        <svg width={largura} height={linhas.length * ALTURA_LINHA} role="img" aria-label="Sem o Vortex comparado com o Vortex">
          {linhas.map((l, i) => {
            const cy = i * ALTURA_LINHA + 26
            return (
              <g key={l.rotulo}>
                <text x={0} y={cy - 4} className="fill-txt-hi text-[12.5px] font-semibold">
                  {l.rotulo}
                </text>
                <text x={0} y={cy + 12} className="fill-txt-ghost text-rotulo">
                  {l.detalhe}
                </text>
                <line x1={rotuloL} x2={rotuloL + areaL} y1={cy} y2={cy} stroke="var(--color-border-soft)" />
                <line x1={x(l.com)} x2={x(l.sem)} y1={cy} y2={cy} stroke={SEM} strokeWidth={2} />
                <circle cx={x(l.sem)} cy={cy} r={6} fill={SEM} stroke="var(--color-panel)" strokeWidth={2} />
                <circle cx={x(l.com)} cy={cy} r={6} fill={COM} stroke="var(--color-panel)" strokeWidth={2} />
                <text x={x(l.sem) + 12} y={cy + 4} className="num fill-txt-dim text-apoio font-semibold">
                  {l.sem}
                </text>
                <text
                  x={x(l.com) - 12}
                  y={cy + 4}
                  textAnchor="end"
                  className="num fill-txt-hi text-apoio font-bold"
                >
                  {l.com}
                </text>
              </g>
            )
          })}
        </svg>
      )}
    </div>
  )
}

/** Trajetória do score numa jornada real, com os limiares. */
function Trajetoria({ historico }) {
  const [ref, largura] = useLargura()
  const A = 90
  const passo = historico.length > 1 ? (largura - 16) / (historico.length - 1) : 0
  const x = (i) => 8 + passo * i
  const y = (v) => 8 + (A - 16) * (1 - v / 100)
  const pontos = historico.map((v, i) => `${x(i)},${y(v)}`).join(' ')
  const final = historico.at(-1) ?? 0
  return (
    <div ref={ref}>
      {largura > 0 && (
        <svg width={largura} height={A} role="img" aria-label={`Fricção da jornada, de 0 a ${final}`}>
          {[40, 70].map((t) => (
            <line key={t} x1={0} x2={largura} y1={y(t)} y2={y(t)} stroke={t === 70 ? 'var(--color-crit)' : 'var(--color-warn)'} strokeOpacity={0.45} />
          ))}
          <polyline points={pontos} fill="none" stroke={faixaDe(nivelPorScore(final)).cor} strokeWidth={2} strokeLinejoin="round" />
          {historico.map((v, i) => (
            <circle key={i} cx={x(i)} cy={y(v)} r={4} fill={faixaDe(nivelPorScore(v)).cor} stroke="var(--color-panel)" strokeWidth={2} />
          ))}
        </svg>
      )}
    </div>
  )
}

function Numero({ rotulo, valor, apoio, cor }) {
  return (
    <div className="bg-panel border-border rounded-2xl border p-5 shadow-[var(--shadow-cartao)]">
      <p className="text-txt-dim text-rotulo font-bold tracking-[1px] uppercase">{rotulo}</p>
      <p className="font-display mt-2 text-[30px] leading-none font-extrabold" style={{ color: cor ?? 'var(--color-txt-hi)' }}>
        {valor}
      </p>
      {apoio && <p className="text-txt-dim mt-2 text-apoio leading-[1.45]">{apoio}</p>}
    </div>
  )
}

export function ImpactoVortex({ impacto }) {
  if (!impacto) {
    return <p className="text-txt-dim text-[13px]">Sem atendimentos registrados ainda.</p>
  }
  const i = impacto
  const ex = i.jornadaExemplo
  const linhas = [
    {
      rotulo: 'Protocolos abertos',
      detalhe: 'cada troca de canal começaria do zero',
      sem: i.protocolosSemVortex,
      com: i.protocolosComVortex,
    },
    {
      rotulo: 'Vezes que o cliente recontou a história',
      detalhe: 'a cada troca de canal e a cada transferência',
      sem: i.relatosRepetidosSemVortex,
      com: i.relatosRepetidosComVortex,
    },
    {
      rotulo: 'Clientes em risco sem alerta',
      detalhe: 'fricção alta sem ninguém perceber a tempo',
      sem: i.emRisco,
      com: Math.max(i.emRisco - i.emRiscoAtendidosComContexto, 0),
    },
  ]

  return (
    <div className="space-y-5">
      {/* --------------------------------------------- manchete */}
      <section className="from-claro relative overflow-hidden rounded-2xl bg-gradient-to-br to-[#a8040e] p-6 text-white shadow-[var(--shadow-cartao)]">
        <p className="text-rotulo font-bold tracking-[1.2px] uppercase opacity-85">
          O cliente que a Claro não perdeu
        </p>
        <div className="mt-3 flex flex-wrap items-end gap-x-10 gap-y-4">
          <div>
            <p className="font-display text-[48px] leading-none font-extrabold">
              {moeda(i.receitaMensalProtegidaCentavos)}
              <span className="text-[18px] font-bold opacity-85">/mês</span>
            </p>
            <p className="mt-2 max-w-[460px] text-[13px] leading-[1.5] opacity-90">
              de mensalidade de <b>{i.emRiscoRetidos} clientes em risco</b> que tiveram o caso
              conduzido com contexto e não saíram insatisfeitos.
            </p>
          </div>
          {i.upgrades > 0 && (
            <div className="rounded-xl bg-white/12 px-4 py-3">
              <p className="font-display text-[24px] font-extrabold">+{moeda(i.receitaMensalUpgradesCentavos)}/mês</p>
              <p className="text-apoio opacity-90">
                em {i.upgrades} {i.upgrades === 1 ? 'upgrade' : 'upgrades'} feitos no autoatendimento
              </p>
            </div>
          )}
        </div>
        <p className="mt-4 text-apoio opacity-80">
          Não estamos só retendo: o mesmo atendimento que evita a perda abre espaço para vender mais.
        </p>
      </section>

      <div className="grid grid-cols-[repeat(auto-fit,minmax(200px,1fr))] gap-4">
        <Numero
          rotulo="Protocolos que não precisaram ser reabertos"
          valor={i.protocolosSemVortex - i.protocolosComVortex}
          apoio={`${i.trocasDeCanal} trocas de canal, sempre no mesmo protocolo`}
          cor="var(--color-ok)"
        />
        <Numero
          rotulo="Histórias que o cliente não precisou recontar"
          valor={i.relatosRepetidosSemVortex - i.relatosRepetidosComVortex}
          apoio="o contexto acompanhou o cliente entre canais e até o atendente"
          cor="var(--color-ok)"
        />
        <Numero
          rotulo="Clientes em risco atendidos com contexto"
          valor={`${i.emRiscoAtendidosComContexto} de ${i.emRisco}`}
          apoio={`${i.emRiscoInsatisfeitos} saiu insatisfeito (nota 1 ou 2)`}
        />
      </div>

      {/* --------------------------------------------- comparação */}
      <Grafico
        titulo="Sem o Vortex × com o Vortex"
        subtitulo="Mesmos atendimentos, dois cenários. Quanto mais perto do zero, melhor."
        legenda={
          <ul className="flex flex-wrap gap-x-5 gap-y-1">
            <li className="text-txt-dim flex items-center gap-[6px] text-apoio">
              <span className="size-[10px] rounded-full" style={{ background: SEM }} />
              Sem continuidade entre canais (simulação)
            </li>
            <li className="text-txt-dim flex items-center gap-[6px] text-apoio">
              <span className="size-[10px] rounded-full" style={{ background: COM }} />
              Com o Vortex (registrado)
            </li>
          </ul>
        }
        tabela={{
          colunas: ['Métrica', 'Sem o Vortex', 'Com o Vortex'],
          linhas: linhas.map((l) => [l.rotulo, l.sem, l.com]),
        }}
      >
        <Halteres linhas={linhas} />
      </Grafico>

      {/* --------------------------------------------- jornada real */}
      <section className="bg-panel border-border rounded-2xl border p-5 shadow-[var(--shadow-cartao)]">
        <h3 className="font-display text-txt-hi text-[15px] font-bold">Uma jornada real, do começo ao fim</h3>
        <p className="text-txt-dim mt-[2px] text-apoio">
          O atendimento com mais trocas de canal registrado — um protocolo só, do primeiro contato ao especialista.
        </p>
        <div className="mt-4 grid grid-cols-[1fr_1fr] gap-6 max-[1100px]:grid-cols-1">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              {ex.canais.map((c, k) => (
                <span key={c} className="flex items-center gap-2">
                  {k > 0 && <IconeSeta size={13} className="text-txt-ghost" />}
                  <PillCanal canal={c} />
                </span>
              ))}
              {ex.houveHandoff && (
                <>
                  <IconeSeta size={13} className="text-txt-ghost" />
                  <span className="bg-claro inline-flex items-center gap-1 rounded-[5px] px-[7px] py-[2.5px] text-rotulo font-extrabold text-white">
                    <IconeUsuario size={10} /> ESPECIALISTA
                  </span>
                </>
              )}
            </div>
            <ul className="text-txt mt-4 space-y-2 text-apoio">
              <li className="flex items-center gap-2">
                <IconeCheck size={13} className="text-ok" /> Um único protocolo:{' '}
                <b className="num text-txt-hi">{ex.protocolo}</b>
              </li>
              <li className="flex items-center gap-2">
                <IconeCheck size={13} className="text-ok" /> Assunto preservado entre canais:{' '}
                <b className="text-txt-hi">{ex.intencaoRotulo}</b>
              </li>
              <li className="flex items-center gap-2">
                <IconeCheck size={13} className="text-ok" />
                {ex.houveHandoff
                  ? 'Transferido antes de desistir, com o histórico completo'
                  : 'Resolvido sem precisar de transferência'}
              </li>
            </ul>
          </div>
          <div>
            <p className="text-txt-dim mb-1 text-rotulo font-bold tracking-[0.8px] uppercase">
              Fricção ao longo da conversa: {ex.historicoScore.join(' → ')}
            </p>
            <Trajetoria historico={ex.historicoScore} />
            <p className="text-txt-ghost mt-1 text-rotulo">
              Linhas: 40 (atenção) e 70 (o Vortex aciona o especialista).
            </p>
          </div>
        </div>
      </section>

      <p className="text-txt-dim bg-void border-border rounded-xl border px-4 py-3 text-apoio leading-[1.6]">
        <b className="text-txt">Como esta simulação é calculada.</b> Usa só os atendimentos registrados.
        Sem continuidade entre canais, cada troca de canal abriria um protocolo novo e o cliente
        recontaria o caso — e também a cada transferência para um humano sem histórico. "Em risco" é
        quem chegou a fricção 40 ou foi transferido. A receita protegida soma a mensalidade do plano
        dos clientes em risco que não deram nota 1 ou 2: é uma estimativa, não faturamento.
      </p>
    </div>
  )
}
