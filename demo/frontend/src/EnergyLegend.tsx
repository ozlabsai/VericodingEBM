/* EnergyLegend.tsx — small inferno-gradient legend chip used in both
 * the landing hero figure and the demo manifold panels. Floats over the
 * scatter at bottom-left. */

type Props = {
  range?: [number, number] | null
  className?: string
}

export default function EnergyLegend({ range, className = '' }: Props) {
  return (
    <div className={`bg-bg0/85 backdrop-blur border border-line1 rounded px-2.5 py-1.5 flex items-center gap-2 font-mono text-[10px] text-text3 ${className}`}>
      <span>low&nbsp;E</span>
      <div className="h-1.5 w-28 rounded-sm" style={{
        background: 'linear-gradient(to right, #000004, #1b0c41, #4a0c6b, #781c6d, #a52c60, #cf4446, #ed6925, #fb9b06, #f7d13d, #fcffa4)',
      }} />
      <span>high&nbsp;E</span>
      {range && (
        <span className="text-text2 tabular ml-1">{range[0].toFixed(1)} … {range[1].toFixed(1)}</span>
      )}
    </div>
  )
}
