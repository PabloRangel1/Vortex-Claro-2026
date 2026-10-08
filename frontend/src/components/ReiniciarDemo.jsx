import { useEffect, useState } from 'react'

import { buscarSaude, resetarDemo } from '../api/endpoints'
import { Button } from './ui/Button'
import { Dialog } from './ui/Dialog'
import { IconeReiniciar } from './ui/icons'

/**
 * Volta a demonstração ao estado inicial sem abrir o /docs na frente da banca.
 *
 * Em produção o servidor exige o token de administração (ADMIN_TOKEN); o
 * diálogo só pede o campo quando o /health diz que o reset está protegido.
 */
export function ReiniciarDemo() {
  const [aberto, setAberto] = useState(false)
  const [protegido, setProtegido] = useState(false)
  const [token, setToken] = useState('')
  const [enviando, setEnviando] = useState(false)
  const [erro, setErro] = useState(null)

  useEffect(() => {
    if (!aberto) return
    setErro(null)
    setToken('')
    buscarSaude()
      .then((s) => setProtegido(Boolean(s?.reset_protegido)))
      .catch(() => setProtegido(false))
  }, [aberto])

  const confirmar = async () => {
    if (enviando || (protegido && !token.trim())) return
    setEnviando(true)
    setErro(null)
    try {
      await resetarDemo(token.trim() || null)
      // Recarregar zera de uma vez o estado local de todas as telas.
      window.location.reload()
    } catch (e) {
      setErro(e)
      setEnviando(false)
    }
  }

  return (
    <>
      <button
        type="button"
        onClick={() => setAberto(true)}
        title="Apaga os atendimentos e volta aos dados fictícios iniciais"
        className="text-txt-dim hover:text-txt-hi hover:bg-void border-border flex items-center gap-[6px]
          rounded-full border px-3 py-[6px] text-rotulo font-semibold transition"
      >
        <IconeReiniciar size={12} />
        <span className="max-[1400px]:sr-only">Reiniciar demo</span>
      </button>

      <Dialog
        aberto={aberto}
        aoFechar={() => setAberto(false)}
        titulo="Reiniciar a demonstração?"
        descricao="Todos os atendimentos, conversas e avaliações serão apagados."
        rodape={
          <>
            <Button onClick={() => setAberto(false)} disabled={enviando}>
              Cancelar
            </Button>
            <Button
              variante="perigoSolido"
              onClick={confirmar}
              disabled={enviando || (protegido && !token.trim())}
            >
              {enviando ? 'Reiniciando...' : 'Apagar e reiniciar'}
            </Button>
          </>
        }
      >
        <p className="text-txt text-[13px] leading-[1.55]">
          Os quatro clientes fictícios voltam ao estado inicial: faturas, planos e vencimentos
          originais, sem nenhum protocolo aberto.
        </p>

        {protegido && (
          <label className="mt-4 block">
            <span className="text-txt-dim mb-2 block text-rotulo font-bold tracking-[1px] uppercase">
              Token de administração
            </span>
            <input
              type="password"
              autoComplete="off"
              value={token}
              onChange={(e) => setToken(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && confirmar()}
              className="bg-input border-border text-txt focus:border-claro focus:ring-claro/10 w-full
                rounded-xl border px-3 py-2.5 text-[13px] outline-none focus:ring-[3px]"
            />
          </label>
        )}

        {erro && (
          <p role="alert" className="text-crit mt-3 text-[12px] font-semibold">
            {erro.status === 403 ? 'Token inválido.' : 'Não foi possível reiniciar. Tente de novo.'}
          </p>
        )}
      </Dialog>
    </>
  )
}
