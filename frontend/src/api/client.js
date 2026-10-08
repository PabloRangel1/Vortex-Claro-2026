/**
 * Wrapper de fetch: base URL, timeout, JSON e erro normalizado.
 * Nenhum componente chama fetch diretamente.
 */

const BASE = import.meta.env.VITE_API_BASE_URL ?? '/api'
const TIMEOUT_MS = 8000

export class ApiError extends Error {
  constructor(mensagem, { status = 0, codigo = 'erro_desconhecido', detalhe = null } = {}) {
    super(mensagem)
    this.name = 'ApiError'
    this.status = status
    this.codigo = codigo
    this.detalhe = detalhe
  }

  get offline() {
    return this.status === 0
  }
}

async function requisitar(rota, { metodo = 'GET', corpo, sinal, cabecalhos, timeoutMs = TIMEOUT_MS } = {}) {
  // Combina o AbortSignal do chamador (unmount/cancelamento) com o do timeout.
  const controlador = new AbortController()
  const expirar = setTimeout(() => controlador.abort(), timeoutMs)
  if (sinal) {
    if (sinal.aborted) controlador.abort()
    else sinal.addEventListener('abort', () => controlador.abort(), { once: true })
  }

  let resposta
  try {
    resposta = await fetch(`${BASE}${rota}`, {
      method: metodo,
      headers: { ...(corpo ? { 'Content-Type': 'application/json' } : {}), ...cabecalhos },
      body: corpo ? JSON.stringify(corpo) : undefined,
      signal: controlador.signal,
    })
  } catch (erro) {
    if (erro.name === 'AbortError') throw erro // repassa: quem cancelou sabe o motivo
    throw new ApiError('Não foi possível alcançar a API', { codigo: 'offline' })
  } finally {
    clearTimeout(expirar)
  }

  if (resposta.status === 204) return null

  let dados = null
  try {
    dados = await resposta.json()
  } catch {
    dados = null
  }

  if (!resposta.ok) {
    throw new ApiError(dados?.detalhe ?? dados?.detail ?? 'Erro na requisição', {
      status: resposta.status,
      codigo: dados?.erro ?? 'erro_http',
      detalhe: dados,
    })
  }

  return dados
}

export const api = {
  get: (rota, opcoes) => requisitar(rota, { ...opcoes, metodo: 'GET' }),
  post: (rota, corpo, opcoes) => requisitar(rota, { ...opcoes, metodo: 'POST', corpo }),
}
