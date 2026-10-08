import { useEffect, useState } from 'react'

import { useSetores } from '../../hooks/useVortex'
import { Button } from '../ui/Button'
import { Dialog } from '../ui/Dialog'

/**
 * Transferência entre setores.
 *
 * O texto do diálogo deixa explícito que o protocolo sobrevive — é a diferença
 * entre transferir e encerrar, e o atendente precisa saber disso antes de
 * confirmar.
 */
export function TransferDialog({ aberto, aoFechar, atendimento, aoConfirmar }) {
  const { setores } = useSetores()
  const [setor, setSetor] = useState('')
  const [motivo, setMotivo] = useState('')
  const [enviando, setEnviando] = useState(false)
  const [erro, setErro] = useState(null)

  // Estado limpo a cada abertura: reaproveitar o anterior confunde.
  useEffect(() => {
    if (aberto) {
      setSetor('')
      setMotivo('')
      setErro(null)
    }
  }, [aberto])

  const disponiveis = setores.filter((s) => s.valor !== atendimento?.setor)

  const confirmar = async () => {
    if (!setor || enviando) return
    setEnviando(true)
    setErro(null)
    try {
      await aoConfirmar({ setor, motivo: motivo.trim() || null })
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
      titulo="Transferir atendimento"
      descricao={
        atendimento
          ? `${atendimento.cliente.nome} · ${atendimento.protocolo}. O protocolo e todo o histórico seguem com o cliente.`
          : undefined
      }
      rodape={
        <>
          <Button onClick={aoFechar} disabled={enviando}>
            Cancelar
          </Button>
          <Button variante="primario" onClick={confirmar} disabled={!setor || enviando}>
            {enviando ? 'Transferindo...' : 'Confirmar transferência'}
          </Button>
        </>
      }
    >
      <fieldset className="border-0 p-0">
        <legend className="text-txt-dim mb-2 text-apoio font-bold tracking-[1.1px] uppercase">
          Setor de destino
        </legend>
        <div className="flex flex-col gap-2">
          {disponiveis.length === 0 && (
            <p className="text-txt-ghost text-[12px]">Carregando setores...</p>
          )}
          {disponiveis.map((s) => (
            <label
              key={s.valor}
              className={`flex cursor-pointer items-center gap-3 rounded-xl border px-4 py-3
                text-[13px] font-semibold transition
                ${
                  setor === s.valor
                    ? 'border-claro bg-claro/6 text-txt-hi'
                    : 'border-border text-txt hover:border-claro/40 hover:bg-void'
                }`}
            >
              <input
                type="radio"
                name="setor"
                value={s.valor}
                checked={setor === s.valor}
                onChange={(e) => setSetor(e.target.value)}
                className="accent-claro size-[15px]"
              />
              {s.rotulo}
            </label>
          ))}
        </div>
      </fieldset>

      <label className="mt-5 block">
        <span className="text-txt-dim mb-2 block text-apoio font-bold tracking-[1.1px] uppercase">
          Motivo <span className="text-txt-ghost font-medium normal-case">(opcional)</span>
        </span>
        <textarea
          rows={2}
          value={motivo}
          maxLength={280}
          onChange={(e) => setMotivo(e.target.value)}
          placeholder="Ex.: caso de contestação, precisa de análise financeira"
          className="bg-input border-border text-txt focus:border-claro focus:ring-claro/10
            placeholder:text-txt-ghost w-full resize-none rounded-xl border px-3 py-2.5
            text-[13px] outline-none focus:ring-[3px]"
        />
      </label>

      {erro && (
        <p className="text-crit mt-3 text-[12px]">
          {erro.offline ? 'API indisponível.' : erro.message}
        </p>
      )}
    </Dialog>
  )
}
