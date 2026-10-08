export function SectionTitle({ icone, children }) {
  return (
    <p className="text-txt-dim flex items-center gap-[7px] text-rotulo font-bold tracking-[1.3px] uppercase">
      {icone}
      {children}
    </p>
  )
}
