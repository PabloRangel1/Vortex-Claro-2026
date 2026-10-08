import { useCallback, useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'

import { ConversationPanel } from '../components/dashboard/ConversationPanel'
import { EncerrarDialog } from '../components/dashboard/EncerrarDialog'
import { IntelPanel } from '../components/dashboard/IntelPanel'
import { QueuePanel } from '../components/dashboard/QueuePanel'
import { encerrarAtendimento, transferirAtendimento } from '../api/endpoints'
import { TransferDialog } from '../components/dashboard/TransferDialog'
import { useAtendimento, useFila, useRespostaAtendente } from '../hooks/useVortex'
import { IconeX } from '../components/ui/icons'

export function Dashboard({ aoMudarConexao }) {
  // "Abrir no painel" (aba Histórico) chega aqui com ?protocolo=…
  const [params] = useSearchParams()
  const [protocolo, setProtocolo] = useState(() => params.get('protocolo'))
  const [transferindo, setTransferindo] = useState(false)
  const [confirmandoEncerrar, setConfirmandoEncerrar] = useState(false)
  // Abaixo de 1280px não cabem as três colunas: o painel de inteligência vira
  // gaveta lateral. Acima disso esta flag não tem efeito visual.
  const [painelAberto, setPainelAberto] = useState(false)

  useEffect(() => {
    if (!painelAberto) return
    const aoTeclar = (e) => e.key === 'Escape' && setPainelAberto(false)
    window.addEventListener('keydown', aoTeclar)
    return () => window.removeEventListener('keydown', aoTeclar)
  }, [painelAberto])
  const { fila, erro: erroFila, carregando, refetch: recarregarFila } = useFila()
  const { atendimento, carregandoAtendimento, refetch: recarregarAtendimento } =
    useAtendimento(protocolo)

  // Sobe o estado da conexão para o indicador na TopBar.
  useEffect(() => {
    aoMudarConexao?.({ erro: erroFila, carregando })
  }, [erroFila, carregando, aoMudarConexao])

  // Fila no título da aba: o atendente vê que chegou alguém mesmo em outra aba
  // (ex.: com o simulador do cliente em primeiro plano durante a demo).
  useEffect(() => {
    document.title = fila.length ? `(${fila.length}) Dashboard · Vortex` : 'Dashboard · Vortex'
  }, [fila.length])

  // Seleção automática do caso mais crítico ao abrir — evita tela vazia na demo.
  useEffect(() => {
    if (!protocolo && fila.length > 0) setProtocolo(fila[0].protocolo)
  }, [fila, protocolo])

  // Sair da fila NÃO tira o atendimento da tela: quem encerrou precisa ver o
  // resultado, e a avaliação do cliente ainda chega neste mesmo protocolo.
  // A troca de seleção passa a ser sempre uma ação explícita do atendente.

  const aposMutacao = useCallback(async () => {
    await Promise.all([recarregarAtendimento(), recarregarFila()])
  }, [recarregarAtendimento, recarregarFila])

  const { enviar, enviando, erro: erroEnvio } = useRespostaAtendente(protocolo, aposMutacao)

  const encerrar = useCallback(async () => {
    if (!protocolo) return
    await encerrarAtendimento(protocolo)
    // Mantém o protocolo selecionado: o atendente precisa ver que encerrou, e
    // a avaliação do cliente ainda vai chegar neste mesmo atendimento.
    await Promise.all([recarregarAtendimento(), recarregarFila()])
  }, [protocolo, recarregarAtendimento, recarregarFila])

  const transferir = useCallback(
    async ({ setor, motivo }) => {
      if (!protocolo) return
      await transferirAtendimento({ protocolo, setor, motivo, por: 'Marcos Ribeiro' })
      await Promise.all([recarregarAtendimento(), recarregarFila()])
    },
    [protocolo, recarregarAtendimento, recarregarFila],
  )

  // A fila é a fonte da verdade para o item selecionado enquanto o detalhe carrega.
  const emFila = fila.map((i) => ({ ...i, recebidoEm: i.recebidoEm ?? Date.now() }))

  return (
    <div className="flex flex-1 overflow-hidden">
      <QueuePanel fila={emFila} protocoloSelecionado={protocolo} aoSelecionar={setProtocolo} />
      <ConversationPanel
        atendimento={atendimento}
        carregando={carregandoAtendimento}
        aoResponder={enviar}
        enviando={enviando}
        erroEnvio={erroEnvio}
        aoEncerrar={() => setConfirmandoEncerrar(true)}
        painelAberto={painelAberto}
        aoAlternarPainel={() => setPainelAberto((v) => !v)}
        aoTransferir={() => setTransferindo(true)}
      />
      {painelAberto && (
        <div
          aria-hidden="true"
          onClick={() => setPainelAberto(false)}
          className="fixed inset-x-0 top-14 bottom-0 z-30 bg-black/25 xl:hidden"
        />
      )}
      <div
        id="painel-inteligencia"
        className={`flex flex-col max-xl:fixed max-xl:top-14 max-xl:right-0 max-xl:bottom-0
          max-xl:z-40 max-xl:shadow-[-12px_0_40px_rgb(0_0_0/0.16)] max-xl:transition-transform
          max-xl:duration-200 ${painelAberto ? '' : 'max-xl:invisible max-xl:translate-x-full'}`}
      >
        <div className="bg-panel border-border flex items-center justify-between border-b border-l px-4 py-2 xl:hidden">
          <span className="text-txt-dim text-rotulo font-bold tracking-[1px] uppercase">
            Inteligência do atendimento
          </span>
          <button
            type="button"
            onClick={() => setPainelAberto(false)}
            aria-label="Fechar painel de inteligência"
            className="text-txt-dim hover:bg-void hover:text-txt-hi flex size-8 cursor-pointer items-center justify-center rounded-lg transition"
          >
            <IconeX size={14} />
          </button>
        </div>
        <IntelPanel atendimento={atendimento} aoAbrirProtocolo={setProtocolo} />
      </div>

      <EncerrarDialog
        aberto={confirmandoEncerrar}
        aoFechar={() => setConfirmandoEncerrar(false)}
        atendimento={atendimento}
        aoConfirmar={encerrar}
      />

      <TransferDialog
        aberto={transferindo}
        aoFechar={() => setTransferindo(false)}
        atendimento={atendimento}
        aoConfirmar={transferir}
      />
    </div>
  )
}
