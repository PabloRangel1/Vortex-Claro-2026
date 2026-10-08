import { useEffect, useState } from 'react'

import { Button } from '../ui/Button'
import { Dialog } from '../ui/Dialog'

/**
 * Confirmação de encerramento.
 *
 * Encerrar não se desfaz: o atendimento não reabre e a pesquisa de satisfação
 * vai para o aparelho do cliente. Um clique errado no meio da conversa não
 * pode bastar. O foco abre no ✕ de fechar (primeiro botão do diálogo), nunca
 * no botão destrutivo.
 */
export function EncerrarDialog({ aberto, aoFechar, atendimento, aoConfirmar }) {
  const [enviando, setEnviando] = useState(false)
  const [erro, setErro] = useState(null)

  useEffect(() => {
    if (aberto) setErro(null)
  }, [aberto])

  const confirmar = async () => {
    if (enviando) return
    setEnviando(true)
    setErro(null)
    try {
      await aoConfirmar()
      aoFechar()
    } catch (e) {
      setErro(e)
    } finally {
      setEnviando(false)
    }
  }

  return (
    <Dialog
      aberto={aberto}
      aoFechar={aoFechar}
      titulo="Encerrar este atendimento?"
      descricao={
        atendimento ? `${atendimento.cliente.nome} · ${atendimento.protocolo}` : undefined
      }
      rodape={
        <>
          <Button onClick={aoFechar} disabled={enviando}>
            Cancelar
          </Button>
          <Button variante="perigoSolido" onClick={confirmar} disabled={enviando}>
            {enviando ? 'Encerrando...' : 'Encerrar atendimento'}
          </Button>
        </>
      }
    >
      <p className="text-txt text-[13px] leading-[1.55]">
        O atendimento será finalizado e <b>não poderá ser reaberto</b>. O cliente recebe a
        pesquisa de satisfação no aparelho, e uma nova mensagem dele abrirá outro protocolo.
      </p>

      {erro && (
        <p role="alert" className="text-crit mt-3 text-[12px] font-semibold">
          Não foi possível encerrar{erro.offline ? ': a API está fora do ar' : ''}. Tente
          novamente.
        </p>
      )}
    </Dialog>
  )
}
