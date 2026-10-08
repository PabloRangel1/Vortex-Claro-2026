/**
 * Respostas rápidas do atendente, por assunto do atendimento.
 *
 * Um clique PREENCHE o campo — não envia. O atendente revisa e ajusta antes,
 * como num atendimento real. Os textos não citam valores nem prazos: fatos
 * vêm do sistema, não de um modelo de frase.
 */

const ABERTURA = 'Olá, {nome}! Já estou com todo o histórico da conversa, você não vai precisar repetir nada.'

const POR_INTENCAO = {
  contestacao_fatura: [
    'Vi a cobrança que você não reconhece. Vou verificar a origem dela e já te retorno por aqui.',
    'Sua contestação está registrada e vou acompanhar a análise pessoalmente.',
  ],
  segunda_via: [
    'A segunda via já está disponível aqui na conversa. Posso ajudar com mais alguma coisa na fatura?',
    'Se preferir, também consigo mudar a data de vencimento das próximas faturas.',
  ],
  financeiro: [
    'Vou verificar os detalhes da sua fatura e te explico cada item.',
    'Se ajudar, consigo mudar a data de vencimento das próximas faturas.',
  ],
  suporte_tecnico: [
    'Já vi o diagnóstico que o assistente fez no seu equipamento. Vou abrir uma verificação técnica.',
    'Pode me dizer em que horários a conexão costuma cair? Isso ajuda a equipe técnica.',
  ],
  planos_upgrade: [
    'Vi que você estava comparando planos. Posso te ajudar a escolher o que faz mais sentido.',
    'Me conta como você usa o plano hoje que eu indico a melhor opção.',
  ],
  cancelamento: [
    'Entendo que você quer cancelar. Antes, posso verificar se há alguma condição especial para você?',
    'Posso te explicar as condições do cancelamento e seguir com o pedido, se preferir.',
  ],
  outros: [
    'Como posso te ajudar hoje?',
    'Pode me contar um pouco mais sobre o que aconteceu?',
  ],
}

export function respostasRapidas(atendimento) {
  if (!atendimento) return []
  const nome = atendimento.cliente.nome.split(' ')[0]
  const especificas = POR_INTENCAO[atendimento.intencao] ?? POR_INTENCAO.outros
  // A apresentação só faz sentido enquanto o atendente ainda não falou.
  const jaFalou = atendimento.mensagens.some((m) => m.remetente === 'atendente')
  const lista = jaFalou ? especificas : [ABERTURA, ...especificas]
  return lista.map((t) => t.replace('{nome}', nome))
}
