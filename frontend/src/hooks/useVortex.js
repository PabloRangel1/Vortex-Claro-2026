import { useCallback, useEffect, useState } from 'react'

import {
  adaptarAtendimento,
  adaptarCliente,
  adaptarEstatisticas,
  adaptarItemFila,
  adaptarRespostaCanal,
} from '../api/adapters'
import {
  avaliarAtendimento,
  buscarAtendimento,
  buscarAtendimentoAtual,
  buscarClientes,
  buscarEstatisticas,
  buscarFila,
  buscarSetores,
  encerrarAtendimento,
  enviarMensagemApp,
  enviarMensagemWhatsApp,
  responderComoAtendente,
  transferirAtendimento,
} from '../api/endpoints'
import { usePolling } from './usePolling'

const POLL_FILA = Number(import.meta.env.VITE_POLL_FILA ?? 4000)
const POLL_ATENDIMENTO = Number(import.meta.env.VITE_POLL_ATENDIMENTO ?? 3000)

/** Fila de atendimentos aguardando handoff. */
export function useFila() {
  const buscar = useCallback(
    async (opcoes) => (await buscarFila(opcoes)).map(adaptarItemFila),
    [],
  )
  const { dados, ...resto } = usePolling(buscar, POLL_FILA)
  return { fila: dados ?? [], ...resto }
}

/** Contexto consolidado de um atendimento. */
export function useAtendimento(protocolo) {
  const buscar = useCallback(
    async (opcoes) => adaptarAtendimento(await buscarAtendimento(protocolo, opcoes)),
    [protocolo],
  )
  const { dados, ...resto } = usePolling(buscar, POLL_ATENDIMENTO, {
    habilitado: Boolean(protocolo),
    deps: [protocolo],
  })
  // O polling mantém os dados anteriores para não piscar — mas ao TROCAR de
  // protocolo isso mostraria a conversa do cliente anterior enquanto a nova
  // carrega, com a resposta já indo para o novo. Só vale o que é do selecionado.
  const doSelecionado = dados?.protocolo === protocolo ? dados : null
  return {
    atendimento: doSelecionado,
    carregandoAtendimento: Boolean(protocolo) && !doSelecionado,
    ...resto,
  }
}

/** Estatísticas agregadas — do que os clientes reclamam e onde a fricção está. */
export function useEstatisticas() {
  const buscar = useCallback(async (opcoes) => adaptarEstatisticas(await buscarEstatisticas(opcoes)), [])
  const { dados, ...resto } = usePolling(buscar, POLL_FILA)
  return { estatisticas: dados, ...resto }
}

/** Setores de destino de uma transferência. Lista estática; um poll longo basta. */
export function useSetores() {
  const buscar = useCallback(async (opcoes) => await buscarSetores(opcoes), [])
  const { dados, ...resto } = usePolling(buscar, 300000)
  return { setores: dados ?? [], ...resto }
}

/** Base de clientes semeada — alimenta o seletor dos simuladores. */
export function useClientes() {
  const buscar = useCallback(
    async (opcoes) => (await buscarClientes(opcoes)).map(adaptarCliente),
    [],
  )
  // Base fixa: um poll longo basta para reagir a um /reset.
  const { dados, ...resto } = usePolling(buscar, 60000)
  return { clientes: dados ?? [], ...resto }
}

/** Envio de mensagem pelo atendente, com estado de submissão. */
export function useRespostaAtendente(protocolo, aoConcluir) {
  const [enviando, setEnviando] = useState(false)
  const [erro, setErro] = useState(null)

  // Erro de um atendimento não acompanha a troca para outro.
  useEffect(() => setErro(null), [protocolo])

  const enviar = useCallback(
    async (conteudo, atendente = 'Marcos Ribeiro') => {
      if (!protocolo || !conteudo.trim()) return
      setEnviando(true)
      setErro(null)
      try {
        await responderComoAtendente({ protocolo, conteudo: conteudo.trim(), atendente })
        await aoConcluir?.()
      } catch (e) {
        setErro(e)
        throw e // o campo de resposta devolve o texto digitado
      } finally {
        setEnviando(false)
      }
    },
    [protocolo, aoConcluir],
  )

  return { enviar, enviando, erro }
}

/**
 * Estado de um simulador de canal.
 *
 * A conversa é montada a partir do atendimento no servidor — não há histórico
 * local. É isso que faz o simulador refletir de verdade o que o backend
 * consolidou, inclusive respostas escritas pelo atendente no dashboard.
 */
export function useCanal(canal, identificador) {
  const [protocolo, setProtocolo] = useState(null)
  const [enviando, setEnviando] = useState(false)
  const [erro, setErro] = useState(null)
  const [ultimaResposta, setUltimaResposta] = useState(null)

  // Ao abrir (ou trocar de cliente), retoma o atendimento em curso. Sem isto o
  // aparelho começaria vazio mesmo havendo conversa — e a avaliação enviada
  // depois do encerramento nunca apareceria para o cliente.
  useEffect(() => {
    if (!identificador) return
    let cancelado = false
    buscarAtendimentoAtual({ canal, identificador })
      .then((r) => {
        if (!cancelado && r?.protocolo) setProtocolo(r.protocolo)
      })
      .catch(() => {})
    return () => {
      cancelado = true
    }
  }, [canal, identificador])

  const buscar = useCallback(
    async (opcoes) => adaptarAtendimento(await buscarAtendimento(protocolo, opcoes)),
    [protocolo],
  )
  const { dados, erro: erroConexao, refetch } = usePolling(buscar, POLL_ATENDIMENTO, {
    habilitado: Boolean(protocolo),
    deps: [protocolo],
  })

  const enviar = useCallback(
    async (texto) => {
      if (!identificador || !texto.trim()) return
      setEnviando(true)
      setErro(null)
      try {
        const bruto =
          canal === 'app'
            ? await enviarMensagemApp({ usuarioId: identificador, mensagem: texto.trim() })
            : await enviarMensagemWhatsApp({ telefone: identificador, mensagem: texto.trim() })

        const resposta = adaptarRespostaCanal(bruto)
        setUltimaResposta(resposta)
        // Se o protocolo mudou (sessão nova), o polling reinicia sozinho pela dep.
        if (resposta.protocolo !== protocolo) setProtocolo(resposta.protocolo)
        else await refetch()
        return resposta
      } catch (e) {
        setErro(e)
        throw e
      } finally {
        setEnviando(false)
      }
    },
    [canal, identificador, protocolo, refetch],
  )

  const avaliar = useCallback(
    async ({ nota, comentario }) => {
      if (!protocolo) return
      await avaliarAtendimento({ protocolo, nota, comentario })
      await refetch()
    },
    [protocolo, refetch],
  )

  const limparEstado = useCallback(() => {
    setProtocolo(null)
    setUltimaResposta(null)
    setErro(null)
  }, [])

  /**
   * Encerra o atendimento em curso e zera o estado local.
   *
   * Necessário porque, após o handoff, o bot deixa de responder por intenção —
   * sem uma saída explícita o simulador fica preso repetindo o aviso de
   * transferência. Encerrar libera a sessão e a próxima mensagem abre um
   * protocolo novo.
   */
  const reiniciarConversa = useCallback(async () => {
    if (protocolo) {
      try {
        await encerrarAtendimento(protocolo)
      } catch {
        // Já encerrado ou inexistente: limpar o estado local basta.
      }
    }
    limparEstado()
  }, [protocolo, limparEstado])

  return {
    // Mesmo cuidado do dashboard: ao trocar de cliente no seletor, a conversa
    // anterior não pode continuar na tela do novo.
    atendimento: dados?.protocolo === protocolo ? dados : null,
    erroConexao,
    protocolo,
    enviar,
    enviando,
    erro,
    ultimaResposta,
    avaliar,
    trocarIdentificador: limparEstado,
    reiniciarConversa,
  }
}
