import { useEffect, useRef } from 'react'

import { IconeX } from './icons'

/**
 * Diálogo modal sobre `<dialog>` nativo.
 *
 * O elemento nativo já entrega foco preso, fechamento por Esc e camada de topo
 * sem z-index — reimplementar isso à mão costuma sair pior.
 */
export function Dialog({ aberto, aoFechar, titulo, descricao, children, rodape }) {
  const ref = useRef(null)

  useEffect(() => {
    const el = ref.current
    if (!el) return
    if (aberto && !el.open) el.showModal()
    if (!aberto && el.open) el.close()
  }, [aberto])

  return (
    <dialog
      ref={ref}
      onClose={aoFechar}
      onClick={(e) => {
        // Clique no backdrop fecha; clique no conteúdo não.
        if (e.target === ref.current) aoFechar()
      }}
      className="bg-panel border-border text-txt m-auto w-[min(440px,92vw)] rounded-2xl border p-0
        shadow-[0_24px_64px_rgb(0_0_0/0.22)] backdrop:bg-black/40 backdrop:backdrop-blur-[2px]"
    >
      <div className="border-border relative border-b px-6 pt-5 pb-4">
        <button
          type="button"
          onClick={aoFechar}
          aria-label="Fechar"
          className="text-txt-dim hover:bg-void hover:text-txt-hi absolute top-4 right-4 flex size-8
            cursor-pointer items-center justify-center rounded-lg transition"
        >
          <IconeX size={14} />
        </button>
        <h2 className="font-display text-txt-hi pr-8 text-[17px] font-bold tracking-[-0.01em]">
          {titulo}
        </h2>
        {descricao && (
          <p className="text-txt-dim mt-1 text-[12.5px] leading-[1.5]">{descricao}</p>
        )}
      </div>

      <div className="px-6 py-5">{children}</div>

      {rodape && (
        <div className="border-border bg-void flex justify-end gap-2 rounded-b-2xl border-t px-6 py-4">
          {rodape}
        </div>
      )}
    </dialog>
  )
}
