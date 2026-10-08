/**
 * Sugestões de resposta do cliente, contextuais ao estado do atendimento.
 *
 * Existem para guiar a demonstração sem digitação: conforme a conversa avança,
 * elas evoluem de "abrir a demanda" para "detalhar" e depois para "escalar" —
 * que é o caminho que faz o Score de Fricção subir até o handoff.
 */

// Cada abertura cai num fluxo de autoatendimento diferente.
const ABERTURAS = {
  app: [
    'Me manda a segunda via da fatura',
    'Quero mudar a data de vencimento',
    'Consultar meu último atendimento',
  ],
  whatsapp: [
    'Minha internet está caindo',
    'Quero fazer upgrade do meu plano',
    'Não reconheço uma cobrança na fatura',
  ],
}

/** Por intenção: aprofundar a demanda (turnos iniciais). */
const DETALHAR = {
  // Cada sugestão reforça o vocabulário da própria intenção. Sem isso, uma
  // pergunta genérica ("que serviço é esse?") reclassifica o atendimento e as
  // sugestões seguintes saem do assunto.
  contestacao_fatura: [
    'Não reconheço essa cobrança de R$ 60,00 na fatura',
    'Não contratei esse serviço, quero contestar',
  ],
  suporte_tecnico: ['Cai todo dia depois das 20h', 'Já reiniciei o roteador e não adiantou'],
  segunda_via: ['Quero mudar o vencimento também', 'Não reconheço uma cobrança nessa fatura'],
  financeiro: [
    'Quero mudar o vencimento para o dia 15',
    'Isso vai gerar cobrança proporcional?',
  ],
  planos_upgrade: ['Quanto fica com mais uma linha?', 'Tem desconto para plano família?'],
  cancelamento: ['Qual é a multa de rescisão?', 'Quero cancelar mesmo assim'],
  outros: ['Pode me explicar melhor?', 'Não era isso que eu perguntei'],
}

/** Escalada — o que um cliente frustrado escreve. Alimenta os detectores de fricção. */
const ESCALAR = [
  'Já expliquei isso três vezes, isso é um absurdo!',
  'Isso não resolveu nada',
  'QUERO FALAR COM UM ATENDENTE AGORA',
]

const ENCERRAR = 'Era só isso, obrigado'

/** Depois do handoff o tom muda: o cliente aguarda uma pessoa. */
const POS_HANDOFF = [
  'Obrigado, vou aguardar',
  'Quanto tempo vai demorar?',
  'Espero não precisar repetir tudo de novo',
]

/**
 * Chave de comparação para o dedupe. Não precisa remover acentos: as sugestões
 * são comparadas com mensagens que vieram delas mesmas.
 */
const chave = (t) =>
  t
    .toLowerCase()
    .replace(/[^\p{L}\p{N}\s]/gu, '')
    .replace(/\s+/g, ' ')
    .trim()

/**
 * @param {object|null} atendimento view model vindo do adapter
 * @param {'app'|'whatsapp'} canal
 * @returns {string[]} até 3 sugestões
 */
export function sugerirRespostas(atendimento, canal) {
  if (!atendimento || atendimento.mensagens.length === 0) {
    return ABERTURAS[canal] ?? ABERTURAS.app
  }

  const doCliente = atendimento.mensagens.filter((m) => m.remetente === 'cliente')
  const jaEnviadas = new Set(doCliente.map((m) => chave(m.conteudo)))

  // O bot está pedindo os dígitos do CPF: nenhuma sugestão "entrega" a resposta.
  if (atendimento.identidade === 'pendente') return []

  // Depois de uma ação que resolveu, a saída natural é encerrar — e é ao
  // encerrar que o cliente recebe a pesquisa de satisfação.
  const resolveu = atendimento.mensagens.some(
    (m) => m.tipo === 'acao' && m.status === 'sucesso' && m.acao !== 'encaminhar_humano',
  )

  let candidatas
  if (atendimento.handoff.acionado || atendimento.status === 'em_atendimento_humano') {
    candidatas = POS_HANDOFF
  } else if (resolveu) {
    candidatas = [ENCERRAR, ...(DETALHAR[atendimento.intencao] ?? DETALHAR.outros)]
  } else {
    const detalhar = DETALHAR[atendimento.intencao] ?? DETALHAR.outros
    // A partir do 2º turno a escalada entra em cena — é ela que move o score.
    candidatas = doCliente.length >= 2 ? [...detalhar, ...ESCALAR] : detalhar
  }

  const ineditas = candidatas.filter((s) => !jaEnviadas.has(chave(s)))
  // Se o cliente já mandou tudo, a escalada continua disponível como saída.
  return (ineditas.length > 0 ? ineditas : ESCALAR).slice(0, 3)
}
