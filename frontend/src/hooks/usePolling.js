import { useCallback, useEffect, useRef, useState } from 'react'

/**
 * Polling com os cuidados que um setInterval cru não tem:
 *
 *  1. Guard de sobreposição — se a resposta anterior não voltou, pula o tick.
 *     Sem isso, backend lento vira pilha de requests no meio da apresentação.
 *  2. Pausa em aba oculta — document.hidden congela; retomar dispara fetch imediato.
 *  3. Backoff em erro — dobra até um teto, reseta no primeiro sucesso.
 *  4. Sem flicker — mantém os dados anteriores enquanto revalida.
 *  5. refetch() manual para uso após mutações.
 *  6. Cleanup completo: aborta a requisição em voo e limpa o timer.
 */
export function usePolling(buscar, intervalo, { habilitado = true, deps = [] } = {}) {
  const [dados, setDados] = useState(null)
  const [erro, setErro] = useState(null)
  const [carregando, setCarregando] = useState(true)

  const emVoo = useRef(false)
  const timer = useRef(null)
  const abortador = useRef(null)
  const tentativasErro = useRef(0)
  const montado = useRef(true)
  const buscarRef = useRef(buscar)

  // Mantém a função sempre atual sem reiniciar o ciclo a cada render.
  useEffect(() => {
    buscarRef.current = buscar
  })

  const executar = useCallback(async () => {
    if (emVoo.current || !habilitado) return
    emVoo.current = true

    abortador.current?.abort()
    abortador.current = new AbortController()

    try {
      const resultado = await buscarRef.current({ sinal: abortador.current.signal })
      if (!montado.current) return
      setDados(resultado)
      setErro(null)
      tentativasErro.current = 0
    } catch (e) {
      if (e.name === 'AbortError' || !montado.current) return
      setErro(e)
      tentativasErro.current += 1
      // Dados anteriores permanecem na tela — só o indicador de conexão muda.
    } finally {
      if (montado.current) setCarregando(false)
      emVoo.current = false
    }
  }, [habilitado])

  useEffect(() => {
    montado.current = true

    const agendar = () => {
      clearTimeout(timer.current)
      if (!habilitado) return
      const atraso = Math.min(intervalo * 2 ** tentativasErro.current, 30000)
      timer.current = setTimeout(async () => {
        if (!document.hidden) await executar()
        agendar()
      }, atraso)
    }

    const aoVoltar = () => {
      if (!document.hidden) {
        executar()
        agendar()
      }
    }

    if (habilitado) {
      executar()
      agendar()
    } else {
      setCarregando(false)
    }

    document.addEventListener('visibilitychange', aoVoltar)
    return () => {
      montado.current = false
      clearTimeout(timer.current)
      abortador.current?.abort()
      document.removeEventListener('visibilitychange', aoVoltar)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [habilitado, intervalo, executar, ...deps])

  return { dados, erro, carregando, refetch: executar }
}
