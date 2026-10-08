/** As chamadas da API Vortex, uma função por endpoint. */

import { api } from './client'

export const enviarMensagemApp = ({ usuarioId, mensagem }, opcoes) =>
  api.post('/channels/app', { usuario_id: usuarioId, mensagem }, opcoes)

export const enviarMensagemWhatsApp = ({ telefone, mensagem }, opcoes) =>
  api.post('/channels/whatsapp', { telefone, mensagem }, opcoes)

export const buscarFila = (opcoes) => api.get('/dashboard/fila', opcoes)

export const buscarAtendimento = (protocolo, opcoes) =>
  api.get(`/dashboard/atendimento/${encodeURIComponent(protocolo)}`, opcoes)

export const responderComoAtendente = ({ protocolo, conteudo, atendente }, opcoes) =>
  api.post(
    `/dashboard/atendimento/${encodeURIComponent(protocolo)}/responder`,
    { conteudo, atendente },
    opcoes,
  )

export const encerrarAtendimento = (protocolo, opcoes) =>
  api.post(`/dashboard/atendimento/${encodeURIComponent(protocolo)}/encerrar`, undefined, opcoes)

export const transferirAtendimento = ({ protocolo, setor, motivo, por }, opcoes) =>
  api.post(
    `/dashboard/atendimento/${encodeURIComponent(protocolo)}/transferir`,
    { setor, motivo, por },
    opcoes,
  )

export const avaliarAtendimento = ({ protocolo, nota, comentario }, opcoes) =>
  api.post(
    `/dashboard/atendimento/${encodeURIComponent(protocolo)}/avaliar`,
    { nota, comentario },
    opcoes,
  )

export const buscarSetores = (opcoes) => api.get('/dashboard/setores', opcoes)

/** Protocolo em curso do cliente — usado pelo simulador ao abrir. */
export const buscarAtendimentoAtual = ({ canal, identificador }, opcoes) =>
  api.get(
    `/channels/atendimento-atual?canal=${encodeURIComponent(canal)}` +
      `&identificador=${encodeURIComponent(identificador)}`,
    opcoes,
  )

export const buscarEstatisticas = (opcoes) => api.get('/dashboard/estatisticas', opcoes)

export const buscarClientes = (opcoes) => api.get('/clientes', opcoes)

/** Histórico: lista de clientes com filtro por tipo (segmento) e busca. */
export const buscarClientesHistorico = ({ segmento, busca } = {}, opcoes) => {
  const p = new URLSearchParams()
  if (segmento) p.set('segmento', segmento)
  if (busca) p.set('busca', busca)
  const qs = p.toString()
  return api.get(`/dashboard/clientes${qs ? `?${qs}` : ''}`, opcoes)
}

export const buscarHistoricoCliente = (clienteId, opcoes) =>
  api.get(`/dashboard/clientes/${encodeURIComponent(clienteId)}/historico`, opcoes)

/** Atendimento (AAAA-MMDD-NNNNN) ou solicitação (SOL-AAAAMMDD-NNNN). */
export const buscarProtocolo = (protocolo, opcoes) =>
  api.get(`/dashboard/protocolo/${encodeURIComponent(protocolo.trim())}`, opcoes)

export const buscarSaude = (opcoes) => api.get('/health', opcoes)

/** O token só é exigido quando o servidor tem ADMIN_TOKEN (ver /health). */
export const resetarDemo = (token, opcoes) =>
  api.post('/reset', undefined, {
    ...opcoes,
    cabecalhos: token ? { 'X-Admin-Token': token } : undefined,
    timeoutMs: 60000, // recria a demonstração inteira; leva alguns segundos
  })
