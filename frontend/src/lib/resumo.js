/**
 * Resumo do caso para o atendente, no momento do handoff.
 *
 * É a promessa do produto em três linhas — o que o cliente quer, o que o bot
 * já tentou, por que chegou aqui — para o atendente não precisar ler a
 * conversa inteira nem pedir que o cliente repita nada.
 *
 * Determinístico: monta-se só com o que o atendimento já registrou. Nada aqui
 * depende da IA nem pode inventar informação.
 */

import { acoesDaConversa, rotuloResultado } from './acoes'

const LIMITE_PEDIDO = 140

/** A frase do cliente que melhor descreve a demanda consolidada. */
function pedidoDoCliente(atendimento) {
  const doCliente = atendimento.mensagens.filter((m) => m.remetente === 'cliente')
  const sobreODemanda = doCliente.find((m) => m.intencao === atendimento.intencao)
  const texto = (sobreODemanda ?? doCliente[0])?.conteudo ?? ''
  return texto.length > LIMITE_PEDIDO ? `${texto.slice(0, LIMITE_PEDIDO - 1)}…` : texto
}

function contar(eventos, codigo) {
  return eventos.filter((e) => e.codigo === codigo).length
}

export function montarResumo(atendimento) {
  const acoes = acoesDaConversa(atendimento.mensagens)

  const sinais = []
  const repeticoes = contar(atendimento.eventos, 'repeticao')
  const trocas = contar(atendimento.eventos, 'troca_canal')
  if (repeticoes) sinais.push(`repetiu a demanda ${repeticoes}×`)
  if (trocas) sinais.push(`trocou de canal ${trocas}×`)
  if (atendimento.identidade === 'falhou') sinais.push('identidade NÃO confirmada')
  if (atendimento.identidade === 'pendente') sinais.push('identidade ainda não confirmada')
  if (atendimento.contatos30Dias > 1) {
    sinais.push(`${atendimento.contatos30Dias}º contato em 30 dias`)
  }

  return {
    demanda: atendimento.intencaoRotulo,
    pedido: pedidoDoCliente(atendimento),
    feito: acoes
      .filter((a) => a.status === 'sucesso')
      .map((a) => ({ id: a.id, rotulo: rotuloResultado(a.codigo), solicitacao: a.solicitacao })),
    falhou: acoes
      .filter((a) => a.status === 'falha')
      .map((a) => ({ id: a.id, rotulo: rotuloResultado(a.codigo) })),
    motivo: atendimento.handoff.motivo,
    sinais,
  }
}
