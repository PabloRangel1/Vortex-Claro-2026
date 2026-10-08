export function EmptyState({ icone, titulo, descricao }) {
  return (
    <div className="flex h-full flex-col items-center justify-center text-center">
      <div className="bg-elev border-border mb-4 flex size-16 items-center justify-center rounded-2xl border">
        {icone}
      </div>
      <p className="font-display text-txt-dim text-[13.5px] font-semibold">{titulo}</p>
      {descricao && (
        <span className="text-txt-ghost mt-[5px] max-w-[290px] text-[11.5px] leading-relaxed">
          {descricao}
        </span>
      )}
    </div>
  )
}
