import { useEffect, useMemo, useRef, useState } from 'react'
import DeckGL from '@deck.gl/react'
import { ScatterplotLayer, LineLayer, BitmapLayer } from '@deck.gl/layers'
import { OrthographicView } from '@deck.gl/core'
import { interpolateMagma } from 'd3-scale-chromatic'

export type EnergyField = {
  scope: string
  grid: number
  x_min: number
  x_max: number
  y_min: number
  y_max: number
  energy_min: number
  energy_max: number
  bandwidth: number
  field: number[]            // length grid*grid, row-major (y outer, x inner)
  arrows: { x0: number; y0: number; x1: number; y1: number }[]
  points: { x: number; y: number; energy: number; is_buggy?: boolean; status?: string }[]
}

export type DescendResponse = {
  trajectory: { x: number; y: number; energy: number }[]
}

export type LandscapeExample = {
  x: number
  y: number
  whole_impl_energy: number
  category: 'model_win' | 'model_miss' | 'pass_low_energy'
  label: string
  impl_id: string
}

type Props = {
  field: EnergyField
  width: number
  height: number
  userBall?: { x: number; y: number; energy: number } | null
  trajectory?: { x: number; y: number; energy: number }[] | null
  trajectoryStep?: number  // 0..trajectory.length, how much to reveal
  onClick?: (x: number, y: number) => void
  showArrows?: boolean
  showPoints?: boolean
  examples?: LandscapeExample[]
  highlightedImplId?: string | null
  onExampleClick?: (ex: LandscapeExample) => void
}

function fieldToImageData(field: EnergyField): ImageData {
  const { grid, field: vals, energy_min, energy_max } = field
  const range = Math.max(1e-6, energy_max - energy_min)
  // deck.gl BitmapLayer expects an HTMLImage/Canvas/ImageBitmap; build via
  // an OffscreenCanvas backed ImageData. Flip Y because canvas is top-down
  // but our field is bottom-up (ys[0] is y_min, smallest y).
  const data = new Uint8ClampedArray(grid * grid * 4)
  for (let row = 0; row < grid; row++) {
    for (let col = 0; col < grid; col++) {
      const flipped = grid - 1 - row  // BitmapLayer's image-y goes top→bottom
      const v = vals[flipped * grid + col]
      const t = Math.max(0, Math.min(1, (v - energy_min) / range))
      // Magma colormap: low E = dark blue, high E = warm yellow.
      const m = interpolateMagma(t)
      const m_match = m.match(/rgb\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)/)
      const r = m_match ? parseInt(m_match[1]) : 128
      const g = m_match ? parseInt(m_match[2]) : 128
      const b = m_match ? parseInt(m_match[3]) : 128
      const idx = (row * grid + col) * 4
      data[idx] = r
      data[idx + 1] = g
      data[idx + 2] = b
      data[idx + 3] = 255
    }
  }
  return new ImageData(data, grid, grid)
}

export default function EnergyLandscape(props: Props) {
  const { field, width, height, userBall, trajectory, trajectoryStep, onClick,
          showArrows = true, showPoints = true,
          examples, highlightedImplId, onExampleClick } = props

  // Convert field to an ImageBitmap (deck.gl BitmapLayer accepts this).
  const [bitmap, setBitmap] = useState<ImageBitmap | null>(null)
  useEffect(() => {
    const imgData = fieldToImageData(field)
    createImageBitmap(imgData).then(setBitmap)
  }, [field])

  const heatmapLayer = useMemo(() => {
    if (!bitmap) return null
    return new BitmapLayer({
      id: 'heatmap',
      image: bitmap,
      // bounds = [west, south, east, north] in the same coord space as the points.
      bounds: [field.x_min, field.y_min, field.x_max, field.y_max],
      pickable: false,
    })
  }, [bitmap, field])

  const arrowsLayer = useMemo(() => {
    if (!showArrows) return null
    // Arrows: a LineLayer from (x0,y0)->(x1,y1), then small triangles for heads.
    return new LineLayer({
      id: 'gradient-arrows',
      data: field.arrows,
      getSourcePosition: (d: any) => [d.x0, d.y0],
      getTargetPosition: (d: any) => [d.x1, d.y1],
      getColor: [255, 255, 255, 140],
      getWidth: 1.0,
      widthUnits: 'pixels',
    })
  }, [field, showArrows])

  // Tiny arrowheads as a scatter of triangles via ScatterplotLayer (cheaper than custom geometry).
  const arrowHeadsLayer = useMemo(() => {
    if (!showArrows) return null
    return new ScatterplotLayer({
      id: 'arrow-heads',
      data: field.arrows,
      getPosition: (d: any) => [d.x1, d.y1],
      getFillColor: [255, 255, 255, 200],
      getRadius: 1.5,
      radiusUnits: 'pixels',
      pickable: false,
    })
  }, [field, showArrows])

  const pointsLayer = useMemo(() => {
    if (!showPoints) return null
    return new ScatterplotLayer({
      id: 'data-points',
      data: field.points,
      getPosition: (d: any) => [d.x, d.y],
      getFillColor: (d: any) => {
        if (d.is_buggy) return [255, 80, 80, 240]
        if (d.status === 'fail') return [220, 220, 220, 180]
        return [120, 200, 255, 180]
      },
      getRadius: (d: any) => (d.is_buggy ? 3.5 : 2.0),
      radiusUnits: 'pixels',
      pickable: true,
    })
  }, [field, showPoints])

  const trajectoryLayer = useMemo(() => {
    if (!trajectory || trajectory.length < 2) return null
    const step = trajectoryStep ?? trajectory.length
    const visible = trajectory.slice(0, Math.max(2, step))
    const segments = visible.slice(0, -1).map((p, i) => ({
      from: [p.x, p.y],
      to: [visible[i + 1].x, visible[i + 1].y],
    }))
    return new LineLayer({
      id: 'trajectory',
      data: segments,
      getSourcePosition: (d: any) => d.from,
      getTargetPosition: (d: any) => d.to,
      getColor: [120, 220, 255, 220],
      getWidth: 2.5,
      widthUnits: 'pixels',
    })
  }, [trajectory, trajectoryStep])

  // Curated-example markers (rendered above heatmap, below ball). Color by
  // category so a judge can scan win/miss/pass at a glance.
  const examplesLayer = useMemo(() => {
    if (!examples || examples.length === 0) return null
    const colorOf = (c: LandscapeExample['category']): [number, number, number, number] => {
      if (c === 'model_win') return [110, 220, 150, 240]
      if (c === 'model_miss') return [240, 110, 120, 240]
      return [120, 180, 240, 240]   // pass_low_energy
    }
    return new ScatterplotLayer({
      id: 'examples',
      data: examples,
      getPosition: (d: LandscapeExample) => [d.x, d.y],
      getFillColor: (d: LandscapeExample) => colorOf(d.category),
      getLineColor: (d: LandscapeExample) =>
        highlightedImplId === d.impl_id ? [255, 255, 255, 255] : [10, 10, 10, 200],
      getLineWidth: (d: LandscapeExample) => (highlightedImplId === d.impl_id ? 3 : 1.5),
      lineWidthUnits: 'pixels',
      stroked: true,
      filled: true,
      getRadius: (d: LandscapeExample) => (highlightedImplId === d.impl_id ? 11 : 7),
      radiusUnits: 'pixels',
      pickable: true,
      onClick: (info) => {
        if (info.object && onExampleClick) onExampleClick(info.object as LandscapeExample)
      },
    })
  }, [examples, highlightedImplId, onExampleClick])

  const ballLayer = useMemo(() => {
    // Show user's ball, OR the latest trajectory point.
    const ball = trajectory && trajectoryStep != null && trajectoryStep > 0
      ? trajectory[Math.min(trajectoryStep, trajectory.length) - 1]
      : userBall
    if (!ball) return null
    return new ScatterplotLayer({
      id: 'ball',
      data: [ball],
      getPosition: (d: any) => [d.x, d.y],
      getFillColor: [255, 80, 80, 250],
      getLineColor: [255, 255, 255, 255],
      getLineWidth: 2,
      lineWidthUnits: 'pixels',
      stroked: true,
      filled: true,
      getRadius: 8,
      radiusUnits: 'pixels',
      pickable: false,
    })
  }, [userBall, trajectory, trajectoryStep])

  const initialViewState = useMemo(() => {
    const cx = (field.x_min + field.x_max) / 2
    const cy = (field.y_min + field.y_max) / 2
    const span = Math.max(field.x_max - field.x_min, field.y_max - field.y_min) || 1
    const targetPixels = Math.min(width, height) * 0.9
    const zoom = Math.log2(targetPixels / span)
    return { target: [cx, cy, 0] as [number, number, number], zoom }
  }, [field, width, height])

  return (
    <DeckGL
      width={width}
      height={height}
      controller={true}
      views={new OrthographicView({ id: 'ortho' })}
      initialViewState={initialViewState}
      layers={[heatmapLayer, arrowsLayer, arrowHeadsLayer, pointsLayer, examplesLayer, trajectoryLayer, ballLayer].filter(Boolean)}
      onClick={(info) => {
        if (info.coordinate && onClick) onClick(info.coordinate[0], info.coordinate[1])
      }}
      getTooltip={({ object }) => {
        if (!object) return null
        const o = object as any
        // Curated-example tooltip (richer).
        if (o.label && o.category) {
          return {
            html: `<div style="background:#0d1117;color:#eee;padding:6px 8px;border:1px solid #30363d;border-radius:4px;font-size:11px;max-width:240px">
              <div style="color:#f5a25d;margin-bottom:2px">${o.label}</div>
              <div style="color:#aaa;font-size:10px">whole-impl E: ${o.whole_impl_energy.toFixed(3)}</div>
              <div style="color:#666;font-size:10px;margin-top:2px;font-family:monospace">${o.impl_id}</div>
            </div>`,
          }
        }
        if (o.energy == null) return null
        return {
          html: `<div style="background:#0d1117;color:#eee;padding:6px 8px;border:1px solid #30363d;border-radius:4px;font-size:11px">energy: <b>${o.energy.toFixed(3)}</b>${o.is_buggy ? ' • <span style="color:#f88">BUGGY</span>' : ''}</div>`,
        }
      }}
    />
  )
}
