export type ImplPoint = {
  impl_id: string
  spec_id: string
  status: string
  whole_impl_energy: number
  n_lines: number
  has_pass_sibling: boolean
  x: number
  y: number
}

export type LinePoint = {
  impl_id: string
  line_idx: number
  line_text: string
  energy: number
  is_buggy: boolean
  impl_status: string
  x: number
  y: number
}

export type ImplDetail = {
  impl: {
    impl_id: string
    spec_id: string
    status: string
    whole_impl_energy: number
    spec_text: string
    impl_text: string
  }
  lines: Array<{
    line_idx: number
    line_text: string
    energy: number
    is_buggy: boolean
    x: number
    y: number
  }>
}

export type ScoreLineResponse = {
  per_line_energies: number[]
  line_xys: [number, number][]
  whole_impl_energy: number
  whole_impl_xy: [number, number]
}

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
  field: number[]
  arrows: { x0: number; y0: number; x1: number; y1: number }[]
  points: { x: number; y: number; energy: number; is_buggy?: boolean; status?: string }[]
}

export type Trajectory = { x: number; y: number; energy: number }[]

// In STATIC mode the frontend loads precomputed JSON from ./data/*.json instead
// of hitting the FastAPI backend. Set VITE_DEMO_MODE=dynamic at build time to
// switch back to the backend (for live model scoring and gradient descent).
const STATIC_MODE = (import.meta as any).env?.VITE_DEMO_MODE !== 'dynamic'
const base = ''
// Vite serves static assets relative to BASE_URL; in dist this is './'.
const dataBase = `${(import.meta as any).env?.BASE_URL ?? '/'}data`.replace(/\/+$/, '')

let _implLinesManifest: Record<string, string> | null = null
async function _loadManifest(): Promise<Record<string, string>> {
  if (_implLinesManifest) return _implLinesManifest
  const r = await fetch(`${dataBase}/impl_lines_manifest.json`)
  if (!r.ok) throw new Error(`load manifest: ${r.status}`)
  _implLinesManifest = await r.json()
  return _implLinesManifest!
}

export async function fetchImpls(): Promise<ImplPoint[]> {
  if (STATIC_MODE) {
    const r = await fetch(`${dataBase}/impls.json`)
    if (!r.ok) throw new Error(`fetchImpls: ${r.status}`)
    return r.json()
  }
  const r = await fetch(`${base}/api/manifold/impls`)
  if (!r.ok) throw new Error(`fetchImpls: ${r.status}`)
  return r.json()
}

export async function fetchLines(): Promise<LinePoint[]> {
  if (STATIC_MODE) {
    const r = await fetch(`${dataBase}/lines.json`)
    if (!r.ok) throw new Error(`fetchLines: ${r.status}`)
    return r.json()
  }
  const r = await fetch(`${base}/api/manifold/lines`)
  if (!r.ok) throw new Error(`fetchLines: ${r.status}`)
  return r.json()
}

export async function fetchImplDetail(implId: string): Promise<ImplDetail> {
  if (STATIC_MODE) {
    const manifest = await _loadManifest()
    const fname = manifest[implId]
    if (!fname) throw new Error(`fetchImplDetail: unknown impl_id ${implId}`)
    const r = await fetch(`${dataBase}/impl_lines/${fname}`)
    if (!r.ok) throw new Error(`fetchImplDetail: ${r.status}`)
    return r.json()
  }
  const r = await fetch(`${base}/api/manifold/impl/${encodeURIComponent(implId)}/lines`)
  if (!r.ok) throw new Error(`fetchImplDetail: ${r.status}`)
  return r.json()
}

export async function scoreLine(specText: string, implText: string): Promise<ScoreLineResponse> {
  if (STATIC_MODE) {
    throw new Error(
      'Live scoring is disabled in static demo mode. ' +
      'Run the FastAPI backend (uvicorn demo.backend.app:app) to enable.',
    )
  }
  const r = await fetch(`${base}/api/score-line`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ spec_text: specText, impl_text: implText }),
  })
  if (!r.ok) throw new Error(`scoreLine: ${r.status} ${await r.text()}`)
  return r.json()
}

export async function fetchEnergyField(
  scope: 'impl' | 'line' = 'impl',
  grid = 96,
  bandwidthMul = 1.2,
): Promise<EnergyField> {
  if (STATIC_MODE) {
    // Only the default (grid=96, bandwidth_mul=1.2) is precomputed.
    if (grid !== 96 || Math.abs(bandwidthMul - 1.2) > 1e-6) {
      console.warn(`Static demo only ships grid=96, bandwidth=1.2. Requested ${grid}/${bandwidthMul} ignored.`)
    }
    const r = await fetch(`${dataBase}/energy_field_${scope}.json`)
    if (!r.ok) throw new Error(`fetchEnergyField: ${r.status}`)
    return r.json()
  }
  const r = await fetch(`${base}/api/energy-field?scope=${scope}&grid=${grid}&bandwidth_mul=${bandwidthMul}`)
  if (!r.ok) throw new Error(`fetchEnergyField: ${r.status}`)
  return r.json()
}

export async function descend(scope: 'impl' | 'line', x: number, y: number, steps = 60, lr = 0.5): Promise<{ trajectory: Trajectory }> {
  if (STATIC_MODE) {
    throw new Error(
      'Gradient descent is disabled in static demo mode. ' +
      'Run the FastAPI backend (uvicorn demo.backend.app:app) to enable.',
    )
  }
  const r = await fetch(`${base}/api/descend`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ scope, x, y, steps, lr }),
  })
  if (!r.ok) throw new Error(`descend: ${r.status} ${await r.text()}`)
  return r.json()
}

export const IS_STATIC_MODE = STATIC_MODE
