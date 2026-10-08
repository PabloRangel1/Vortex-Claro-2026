/**
 * Faixas do Score de Fricção.
 *
 * Os limiares (40 / 70) espelham os do backend em app/config.py. O nível vem
 * pronto da API — estas cores só traduzem esse nível para a interface.
 */

/**
 * Paleta de status, deliberadamente distinta das cores de marca: o verde é
 * mais azulado que o do WhatsApp e o crítico é mais carmim que o vermelho da
 * Claro, para que "estável" não se confunda com um canal nem "crítico" com a
 * identidade visual.
 */
export const FAIXAS = {
  estavel: {
    cor: '#008a4e',
    rotulo: 'ESTÁVEL',
    fundo: 'rgb(0 138 78 / 0.10)',
    borda: 'rgb(0 138 78 / 0.30)',
  },
  atencao: {
    cor: '#9c6a00',
    rotulo: 'ATENÇÃO',
    fundo: 'rgb(156 106 0 / 0.10)',
    borda: 'rgb(156 106 0 / 0.32)',
  },
  critico: {
    cor: '#b01020',
    rotulo: 'CRÍTICO',
    fundo: 'rgb(176 16 32 / 0.09)',
    borda: 'rgb(176 16 32 / 0.30)',
  },
}

export const faixaDe = (nivel) => FAIXAS[nivel] ?? FAIXAS.estavel

/** Fallback local caso o nível não venha no payload. */
export function nivelPorScore(score) {
  if (score >= 70) return 'critico'
  if (score >= 40) return 'atencao'
  return 'estavel'
}

/** Como a identidade do cliente foi confirmada — e se o atendente deve conferir. */
export const IDENTIDADE = {
  verificada_app: { rotulo: 'Verificada · login do App', cor: 'var(--color-ok)' },
  verificada_cpf: { rotulo: 'Verificada · CPF no WhatsApp', cor: 'var(--color-ok)' },
  pendente: { rotulo: 'Aguardando confirmação', cor: 'var(--color-warn)' },
  falhou: { rotulo: 'Não confirmada — confira antes', cor: 'var(--color-crit)' },
  nao_verificada: { rotulo: 'Não verificada', cor: 'var(--color-warn)' },
}

/** Acima disso, a espera na fila ganha destaque de alerta. */
export const ESPERA_ALERTA_SEGUNDOS = 120

export const ROTULO_STATUS = {
  bot_ativo: 'Bot ativo',
  aguardando_handoff: 'Aguardando handoff',
  em_atendimento_humano: 'Em atendimento',
  encerrado: 'Encerrado',
}
