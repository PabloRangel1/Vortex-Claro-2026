/**
 * Vocabulário do autoatendimento na interface.
 *
 * O backend devolve códigos estáveis (`acao`, `codigo`) e dados estruturados;
 * aqui eles viram rótulos curtos e valores formatados. O texto longo que o
 * cliente lê continua vindo pronto do backend.
 */

export const ROTULO_ACAO = {
  gerar_segunda_via: 'Segunda via',
  alterar_vencimento: 'Alteração de vencimento',
  diagnosticar_conexao: 'Diagnóstico de conexão',
  reiniciar_equipamento: 'Reinício do equipamento',
  listar_planos: 'Consulta de planos',
  confirmar_upgrade: 'Upgrade de plano',
  abrir_contestacao: 'Contestação de cobrança',
  encaminhar_humano: 'Encaminhamento humano',
}

/** Resultado em poucas palavras — para chips e para a timeline do painel. */
export const ROTULO_RESULTADO = {
  segunda_via_gerada: 'Segunda via gerada',
  segunda_via_vencida: 'Segunda via (fatura vencida)',
  fatura_ja_paga: 'Fatura já estava paga',
  sem_fatura: 'Sem fatura para a conta',
  vencimento_alterado: 'Vencimento alterado',
  dia_nao_permitido: 'Dia não permitido',
  dia_igual_atual: 'Dia igual ao atual',
  dia_invalido: 'Dia inválido',
  diagnostico_online: 'Conexão normal',
  diagnostico_instavel: 'Instabilidade detectada',
  diagnostico_offline: 'Equipamento sem comunicação',
  sem_equipamento: 'Sem equipamento vinculado',
  equipamento_reiniciado: 'Equipamento reiniciado',
  equipamento_sem_comunicacao: 'Reinício impossível (offline)',
  planos_disponiveis: 'Opções de upgrade enviadas',
  plano_disponivel: 'Opção de upgrade enviada',
  sem_upgrade_disponivel: 'Sem upgrade disponível',
  plano_atualizado: 'Plano atualizado',
  mesmo_plano: 'Já é o plano atual',
  nao_e_upgrade: 'Não é upgrade',
  categoria_diferente: 'Categoria diferente',
  plano_inexistente: 'Plano inexistente',
  plano_atual_desconhecido: 'Plano atual desconhecido',
  contestacao_aberta: 'Contestação aberta',
  contestacao_em_andamento: 'Contestação já em análise',
  encaminhado_humano: 'Encaminhado a especialista',
  parametro_ausente: 'Faltaram informações',
  acao_desconhecida: 'Ação indisponível',
  cliente_nao_encontrado: 'Conta não localizada',
}

export const rotuloAcao = (acao) => ROTULO_ACAO[acao] ?? 'Autoatendimento'
export const rotuloResultado = (codigo) => ROTULO_RESULTADO[codigo] ?? codigo

/** 18990 -> "R$ 189,90" */
export function moeda(centavos) {
  if (centavos == null) return '—'
  return (centavos / 100).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })
}

/**
 * "2026-10-05" -> "05/10/2026". Montado à mão: `new Date('2026-10-05')` é meia-noite
 * UTC, que no Brasil vira o dia anterior.
 */
export function dataCurta(iso) {
  if (!iso) return '—'
  const [a, m, d] = iso.slice(0, 10).split('-')
  return `${d}/${m}/${a}`
}

/** Mensagens de sistema que registram uma ação do bot, em ordem. */
export const acoesDaConversa = (mensagens) => (mensagens ?? []).filter((m) => m.tipo === 'acao')
