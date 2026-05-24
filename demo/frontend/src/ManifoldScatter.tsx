import { useMemo } from 'react'
import DeckGL from '@deck.gl/react'
import { ScatterplotLayer } from '@deck.gl/layers'
import { OrthographicView } from '@deck.gl/core'
import { interpolateInferno } from 'd3-scale-chromatic'
import { scaleLinear } from 'd3-scale'

export type ScatterPoint = {
  x: number
  y: number
  energy: number
  isHighlighted?: boolean   // e.g. ground-truth buggy line
  isUserPoint?: boolean     // a live-scored user-typed line
  label?: string            // shown in tooltip
  payload?: unknown         // arbitrary payload returned via onClick
}

type Props = {
  points: ScatterPoint[]
  width: number
  height: number
  onClick?: (p: ScatterPoint) => void
  onHover?: (p: ScatterPoint | null) => void
  colorBy?: 'energy' | 'status'
  energyRange?: [number, number]
  selectedKey?: string | null   // payload string-cmp; visually distinguishes selected point
}

function hex2rgb(s: string): [number, number, number] {
  // d3-scale-chromatic v3 returns "#rrggbb"; older versions returned
  // "rgb(r, g, b)". Handle both.
  if (s.charCodeAt(0) === 35) {  // '#'
    const v = parseInt(s.slice(1), 16)
    return [(v >> 16) & 0xff, (v >> 8) & 0xff, v & 0xff]
  }
  const m = s.match(/rgb\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)/)
  if (m) return [parseInt(m[1]), parseInt(m[2]), parseInt(m[3])]
  return [128, 128, 128]
}

export default function ManifoldScatter(props: Props) {
  const { points, width, height, onClick, onHover, energyRange, selectedKey } = props

  const colorScale = useMemo(() => {
    if (!energyRange) return null
    return scaleLinear<string>().domain(energyRange).range(['#00224e', '#ffd200']).clamp(true)
  }, [energyRange])

  const layer = useMemo(() => {
    return new ScatterplotLayer<ScatterPoint>({
      id: 'manifold-scatter',
      data: points,
      pickable: true,
      stroked: true,
      filled: true,
      radiusUnits: 'pixels',
      lineWidthUnits: 'pixels',
      getPosition: (d: ScatterPoint) => [d.x, d.y],
      getRadius: (d: ScatterPoint) => {
        if (d.isUserPoint) return 12
        if (d.isHighlighted) return 5
        return 3
      },
      getFillColor: (d: ScatterPoint) => {
        if (d.isUserPoint) return [255, 64, 64, 240]
        if (energyRange && colorScale) {
          // viridis-ish energy color
          const t = (d.energy - energyRange[0]) / (energyRange[1] - energyRange[0])
          const clamped = Math.max(0, Math.min(1, t))
          const rgb = hex2rgb(interpolateInferno(clamped))
          return [...rgb, d.isHighlighted ? 240 : 180] as [number, number, number, number]
        }
        return d.isHighlighted ? [204, 64, 64, 240] : [44, 95, 199, 180]
      },
      getLineColor: (d: ScatterPoint) => {
        if (selectedKey && typeof d.payload === 'string' && d.payload === selectedKey) {
          return [255, 255, 255, 255]
        }
        if (d.isHighlighted) return [255, 255, 255, 200]
        return [0, 0, 0, 0]
      },
      getLineWidth: (d: ScatterPoint) =>
        (selectedKey && typeof d.payload === 'string' && d.payload === selectedKey) ? 2 : 1,
      onClick: ({ object }) => { if (object && onClick) onClick(object as ScatterPoint) },
      onHover: ({ object }) => { if (onHover) onHover((object as ScatterPoint) ?? null) },
      updateTriggers: {
        getLineColor: [selectedKey],
        getLineWidth: [selectedKey],
        getFillColor: [energyRange],
      },
    })
  }, [points, energyRange, colorScale, selectedKey, onClick, onHover])

  // Compute view bounds for a fit-to-points initial view.
  const initialViewState = useMemo(() => {
    if (points.length === 0) {
      return { target: [0, 0, 0] as [number, number, number], zoom: 0 }
    }
    const xs = points.map(p => p.x)
    const ys = points.map(p => p.y)
    const xMin = Math.min(...xs), xMax = Math.max(...xs)
    const yMin = Math.min(...ys), yMax = Math.max(...ys)
    const cx = (xMin + xMax) / 2, cy = (yMin + yMax) / 2
    const span = Math.max(xMax - xMin, yMax - yMin) || 1
    // OrthographicView: zoom 0 means 1 unit = 1 pixel. Choose zoom such that
    // 1.1 * span ≈ min(width, height) pixels.
    const targetPixels = Math.min(width, height) * 0.85
    const zoom = Math.log2(targetPixels / span)
    return { target: [cx, cy, 0] as [number, number, number], zoom }
  }, [points, width, height])

  return (
    <DeckGL
      width={width}
      height={height}
      controller={true}
      views={new OrthographicView({ id: 'ortho' })}
      initialViewState={initialViewState}
      layers={[layer]}
      getTooltip={({ object }) => {
        if (!object) return null
        const o = object as ScatterPoint
        return {
          html: `<div style="background:#0d1117;color:#eee;padding:6px 8px;border:1px solid #30363d;border-radius:4px;font-size:11px;max-width:360px"><div>energy: <b>${o.energy.toFixed(3)}</b>${o.isHighlighted ? ' • <span style="color:#f88">BUGGY</span>' : ''}</div>${o.label ? `<div style="margin-top:4px;color:#9ca3af;white-space:pre-wrap;font-family:ui-monospace,Menlo,monospace">${o.label.slice(0, 200)}</div>` : ''}</div>`,
        }
      }}
    />
  )
}
