import { useEffect, useMemo, useRef } from 'react'
import { Canvas } from '@react-three/fiber'
import { OrbitControls, Stats } from '@react-three/drei'
import * as THREE from 'three'
import { interpolateRdBu } from 'd3-scale-chromatic'
import type { EnergyField } from './api'

type Props = {
  field: EnergyField
  userBall?: { x: number; y: number; energy: number } | null
  trajectory?: { x: number; y: number; energy: number }[] | null
  trajectoryStep?: number
  showPoints?: boolean
  showWireframe?: boolean
  heightScale?: number
  showStats?: boolean
}

function hex2rgb(s: string): [number, number, number] {
  const m = s.match(/rgb\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)/)
  if (m) return [parseInt(m[1]), parseInt(m[2]), parseInt(m[3])]
  return [128, 128, 128]
}

function sampleField(field: EnergyField, x: number, y: number): number {
  const { grid, x_min, x_max, y_min, y_max, field: vals } = field
  const u = ((x - x_min) / (x_max - x_min)) * (grid - 1)
  const v = ((y - y_min) / (y_max - y_min)) * (grid - 1)
  const u0 = Math.max(0, Math.min(grid - 2, Math.floor(u)))
  const v0 = Math.max(0, Math.min(grid - 2, Math.floor(v)))
  const du = u - u0
  const dv = v - v0
  const e00 = vals[v0 * grid + u0]
  const e10 = vals[v0 * grid + (u0 + 1)]
  const e01 = vals[(v0 + 1) * grid + u0]
  const e11 = vals[(v0 + 1) * grid + (u0 + 1)]
  return e00 * (1 - du) * (1 - dv) + e10 * du * (1 - dv) + e01 * (1 - du) * dv + e11 * du * dv
}

/**
 * Reference-aesthetic terrain: RdBu_r (low E = blue valley, high E = red peak),
 * with soft global lighting and no harsh shadows.
 */
function useTerrainGeometry(field: EnergyField, heightScale: number) {
  return useMemo(() => {
    const { grid, x_min, x_max, y_min, y_max, field: vals, energy_min, energy_max } = field
    const xSpan = x_max - x_min
    const ySpan = y_max - y_min
    const geo = new THREE.PlaneGeometry(xSpan, ySpan, grid - 1, grid - 1)
    const range = Math.max(1e-6, energy_max - energy_min)
    const colors = new Float32Array(grid * grid * 3)
    const pos = geo.attributes.position as THREE.BufferAttribute

    for (let row = 0; row < grid; row++) {
      for (let col = 0; col < grid; col++) {
        const flippedRow = grid - 1 - row
        const fieldIdx = flippedRow * grid + col
        const v = vals[fieldIdx]
        const z = (v - energy_min) * heightScale
        const geoIdx = row * grid + col
        pos.setZ(geoIdx, z)
        // RdBu reverse: low value (cold) = blue; high value (hot) = red.
        // d3.interpolateRdBu maps 0→red, 1→blue, so we use 1 − t.
        const t = 1 - Math.max(0, Math.min(1, (v - energy_min) / range))
        const [r, g, b] = hex2rgb(interpolateRdBu(t))
        colors[geoIdx * 3 + 0] = r / 255
        colors[geoIdx * 3 + 1] = g / 255
        colors[geoIdx * 3 + 2] = b / 255
      }
    }
    geo.setAttribute('color', new THREE.BufferAttribute(colors, 3))
    geo.computeVertexNormals()
    return geo
  }, [field, heightScale])
}

function Terrain({ field, heightScale, wireframe }: { field: EnergyField; heightScale: number; wireframe: boolean }) {
  const geo = useTerrainGeometry(field, heightScale)
  return (
    <mesh
      geometry={geo}
      rotation={[-Math.PI / 2, 0, 0]}
      receiveShadow={false}
      castShadow={false}
    >
      <meshPhysicalMaterial
        vertexColors
        wireframe={wireframe}
        roughness={0.55}
        metalness={0.0}
        clearcoat={0.3}
        clearcoatRoughness={0.5}
        sheen={0.2}
        sheenRoughness={0.7}
        flatShading={false}
        side={THREE.DoubleSide}
      />
    </mesh>
  )
}

function DataPoints({ field, heightScale }: { field: EnergyField; heightScale: number }) {
  const { x_min, x_max, y_min, y_max, energy_min, points } = field
  const xMid = (x_min + x_max) / 2
  const yMid = (y_min + y_max) / 2
  const ref = useRef<THREE.InstancedMesh>(null)
  useEffect(() => {
    if (!ref.current) return
    const m = new THREE.Matrix4()
    const color = new THREE.Color()
    points.forEach((p, i) => {
      const lx = p.x - xMid
      const ly = (p.energy - energy_min) * heightScale + 0.02
      const lz = -(p.y - yMid)
      m.makeTranslation(lx, ly, lz)
      ref.current!.setMatrixAt(i, m)
      if (p.is_buggy) color.set('#ff5050')
      else if (p.status === 'fail') color.set('#cccccc')
      else color.set('#7bc4ff')
      ref.current!.setColorAt(i, color)
    })
    ref.current.instanceMatrix.needsUpdate = true
    if (ref.current.instanceColor) ref.current.instanceColor.needsUpdate = true
  }, [points, xMid, yMid, energy_min, heightScale])

  return (
    <instancedMesh ref={ref} args={[undefined, undefined, points.length]}>
      <sphereGeometry args={[0.04, 10, 10]} />
      <meshBasicMaterial vertexColors transparent opacity={0.55} />
    </instancedMesh>
  )
}

/** Discrete arrow segment with arrowhead, colored along a white→red gradient. */
function ArrowSegment({ from, to, color }: { from: [number, number, number]; to: [number, number, number]; color: string }) {
  const dir = new THREE.Vector3(to[0] - from[0], to[1] - from[1], to[2] - from[2])
  const len = dir.length()
  if (len < 1e-6) return null
  const origin = new THREE.Vector3(...from)
  const arrowHelper = useMemo(() =>
    new THREE.ArrowHelper(dir.clone().normalize(), origin, len, new THREE.Color(color).getHex(),
                          len * 0.3, len * 0.18),
    [from[0], from[1], from[2], to[0], to[1], to[2], color])
  return <primitive object={arrowHelper} />
}

function Trajectory({ field, trajectory, step, heightScale }: {
  field: EnergyField
  trajectory: { x: number; y: number; energy: number }[]
  step: number
  heightScale: number
}) {
  const { x_min, x_max, y_min, y_max, energy_min } = field
  const xMid = (x_min + x_max) / 2
  const yMid = (y_min + y_max) / 2
  const visible = trajectory.slice(0, Math.max(2, step))

  // Convert each trajectory step into a world-space (x, y, z) on the surface.
  const worldPoints = useMemo(() =>
    visible.map(p => {
      const surfaceE = sampleField(field, p.x, p.y)
      return [
        p.x - xMid,
        (surfaceE - energy_min) * heightScale + 0.05,
        -(p.y - yMid),
      ] as [number, number, number]
    }),
    [visible, field, xMid, yMid, energy_min, heightScale],
  )

  // Sample every Nth pair as a discrete arrow (cap at ~12 arrows so it stays readable).
  const arrowStride = Math.max(1, Math.floor(worldPoints.length / 12))
  const arrows: { from: [number, number, number]; to: [number, number, number]; color: string }[] = []
  for (let i = arrowStride; i < worldPoints.length; i += arrowStride) {
    const t = i / Math.max(1, worldPoints.length - 1)
    // White → red gradient along the trail (start = bright white, end = warm red).
    const r = 255
    const g = Math.round(255 * (1 - t * 0.75))
    const b = Math.round(255 * (1 - t * 0.95))
    const color = `rgb(${r}, ${g}, ${b})`
    arrows.push({ from: worldPoints[i - arrowStride], to: worldPoints[i], color })
  }

  // Ball at the head of the trajectory.
  const head = worldPoints[worldPoints.length - 1]

  return (
    <>
      {arrows.map((a, i) => (
        <ArrowSegment key={i} from={a.from} to={a.to} color={a.color} />
      ))}
      {head && (
        <mesh position={head}>
          <sphereGeometry args={[0.16, 24, 24]} />
          <meshStandardMaterial color="#ffffff" emissive="#ff6060" emissiveIntensity={0.9} />
        </mesh>
      )}
    </>
  )
}

function UserBall({ field, ball, heightScale }: {
  field: EnergyField
  ball: { x: number; y: number; energy: number }
  heightScale: number
}) {
  const { x_min, x_max, y_min, y_max, energy_min } = field
  const xMid = (x_min + x_max) / 2
  const yMid = (y_min + y_max) / 2
  const surfaceE = sampleField(field, ball.x, ball.y)
  return (
    <mesh position={[ball.x - xMid, (surfaceE - energy_min) * heightScale + 0.05, -(ball.y - yMid)]}>
      <sphereGeometry args={[0.16, 24, 24]} />
      <meshStandardMaterial color="#ffffff" emissive="#ffaa66" emissiveIntensity={0.6} />
    </mesh>
  )
}

export default function EnergyLandscape3D(props: Props) {
  const {
    field, userBall, trajectory, trajectoryStep,
    showPoints = false,         // hidden by default to match the reference
    showWireframe = false,
    heightScale = 0.5,
    showStats = false,
  } = props

  const { x_min, x_max, y_min, y_max } = field
  const span = Math.max(x_max - x_min, y_max - y_min)
  const cam = { fov: 38, position: [span * 0.05, span * 0.85, span * 1.25] as [number, number, number] }

  return (
    <Canvas
      shadows={false}                       // no harsh shadows; matches the reference
      camera={cam}
      gl={{ antialias: true, preserveDrawingBuffer: false }}
      style={{ background: 'linear-gradient(to bottom, #f5f7fa 0%, #d8e0ec 100%)' }}
    >
      {/* Soft, near-ambient lighting — the reference figure looks like soft clay,
          not strongly directional. We keep one mild key light to preserve normals. */}
      <ambientLight intensity={0.85} />
      <hemisphereLight args={['#ffffff', '#a0b0c4', 0.55]} />
      <directionalLight position={[span * 0.5, span * 1.5, span * 0.8]} intensity={0.35} />

      <Terrain field={field} heightScale={heightScale} wireframe={showWireframe} />
      {showPoints && <DataPoints field={field} heightScale={heightScale} />}
      {trajectory && trajectoryStep != null && trajectoryStep > 0 && (
        <Trajectory field={field} trajectory={trajectory} step={trajectoryStep} heightScale={heightScale} />
      )}
      {userBall && !trajectory && <UserBall field={field} ball={userBall} heightScale={heightScale} />}

      <OrbitControls
        enableDamping
        dampingFactor={0.08}
        minDistance={span * 0.3}
        maxDistance={span * 5}
        maxPolarAngle={Math.PI / 2 - 0.05}
      />
      {showStats && <Stats />}
    </Canvas>
  )
}
