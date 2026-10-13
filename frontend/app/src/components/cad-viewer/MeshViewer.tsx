/**
 * MeshViewer — client-side 3D mesh preview for STL, OBJ, and 3MF files.
 *
 * Parses and renders the actual uploaded File object using Three.js WebGL.
 * No backend round-trip. No synthetic or placeholder geometry — the canvas
 * is blank (loading state) until the real file parses successfully.
 *
 * Controls: orbit / zoom / pan (OrbitControls), fit-to-screen, reset view.
 * Stale-preview guarantee: parent must key this component on file identity
 * so it remounts (and disposes the WebGL context) when the file changes.
 *
 * Supported: STL (ASCII + binary), OBJ, 3MF.
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import * as THREE from 'three'
import { STLLoader } from 'three/examples/jsm/loaders/STLLoader.js'
import { OBJLoader } from 'three/examples/jsm/loaders/OBJLoader.js'
import { ThreeMFLoader } from 'three/examples/jsm/loaders/3MFLoader.js'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import { LoaderCircle, Maximize2, RotateCcw } from 'lucide-react'
import { useLocale } from '../../i18n'
import type { PreviewMesh } from '../../services/engineeringImport'

// ---------------------------------------------------------------------------
// Scene constants
// ---------------------------------------------------------------------------

const BG       = 0x0f1117
const MESH_COL = 0x7a8fa8
const SPEC_COL = 0x223344
const AMB_INT  = 0.55
const DIR_INT  = 0.85

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function fitToBox(
  box: THREE.Box3,
  camera: THREE.PerspectiveCamera,
  controls: OrbitControls,
): void {
  const center = new THREE.Vector3()
  const size   = new THREE.Vector3()
  box.getCenter(center)
  box.getSize(size)
  const maxDim = Math.max(size.x, size.y, size.z)
  const fovRad = (camera.fov * Math.PI) / 180
  const dist   = (maxDim / 2 / Math.tan(fovRad / 2)) * 1.6
  camera.position.set(center.x + dist * 0.25, center.y + dist * 0.5, center.z + dist)
  camera.lookAt(center)
  controls.target.copy(center)
  controls.update()
}

function meshMaterial(): THREE.MeshPhongMaterial {
  return new THREE.MeshPhongMaterial({
    color: MESH_COL,
    specular: SPEC_COL,
    shininess: 40,
    side: THREE.DoubleSide,
  })
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

type Props =
  | { file: File; mesh?: never }
  | { mesh: PreviewMesh; file?: never }

export default function MeshViewer(props: Props) {
  const { t } = useLocale()
  const containerRef = useRef<HTMLDivElement>(null)

  // Live refs so fit/reset callbacks access current state without closures
  const cameraRef   = useRef<THREE.PerspectiveCamera | null>(null)
  const controlsRef = useRef<OrbitControls | null>(null)
  const initPosRef  = useRef(new THREE.Vector3())
  const initTgtRef  = useRef(new THREE.Vector3())
  const fitBoxRef   = useRef<THREE.Box3 | null>(null)

  const [loading,    setLoading]    = useState(true)
  const [parseError, setParseError] = useState<string | null>(null)

  // Extract props so effect deps are stable scalar/object references
  const fileSource = props.file ?? null
  const meshSource = props.mesh ?? null

  useEffect(() => {
    const container = containerRef.current
    if (!container) return

    // ── Scene ──────────────────────────────────────────────────────────────
    const scene = new THREE.Scene()
    scene.background = new THREE.Color(BG)

    // ── Camera ─────────────────────────────────────────────────────────────
    const w = container.clientWidth  || 600
    const h = container.clientHeight || 420
    const camera = new THREE.PerspectiveCamera(45, w / h, 0.001, 1e6)
    camera.position.set(0, 0, 5)
    cameraRef.current = camera

    // ── Renderer ───────────────────────────────────────────────────────────
    const renderer = new THREE.WebGLRenderer({ antialias: true })
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
    renderer.setSize(w, h)
    container.appendChild(renderer.domElement)

    // ── Lights ─────────────────────────────────────────────────────────────
    scene.add(new THREE.AmbientLight(0xffffff, AMB_INT))
    const key = new THREE.DirectionalLight(0xffffff, DIR_INT)
    key.position.set(1.5, 2, 2.5)
    scene.add(key)
    const fill = new THREE.DirectionalLight(0x8899bb, 0.3)
    fill.position.set(-2, -1, -1)
    scene.add(fill)

    // ── OrbitControls ──────────────────────────────────────────────────────
    const controls = new OrbitControls(camera, renderer.domElement)
    controls.enableDamping  = true
    controls.dampingFactor  = 0.06
    controlsRef.current = controls

    // ── Render loop ────────────────────────────────────────────────────────
    let animId = 0
    const loop = () => {
      animId = requestAnimationFrame(loop)
      controls.update()
      renderer.render(scene, camera)
    }
    loop()

    // ── ResizeObserver ─────────────────────────────────────────────────────
    const ro = new ResizeObserver(() => {
      const nw = container.clientWidth
      const nh = container.clientHeight
      if (nw === 0 || nh === 0) return
      camera.aspect = nw / nh
      camera.updateProjectionMatrix()
      renderer.setSize(nw, nh)
    })
    ro.observe(container)

    // ── Geometry disposal list ─────────────────────────────────────────────
    const toDispose: Array<THREE.BufferGeometry | THREE.Material> = []

    // ── Unmount flag ───────────────────────────────────────────────────────
    let alive = true

    const mat = meshMaterial()
    toDispose.push(mat)

    if (fileSource) {
      // ── File path: async STL / OBJ / 3MF load ─────────────────────────
      const objectUrl = URL.createObjectURL(fileSource)
      const ext = (fileSource.name.split('.').pop() ?? '').toLowerCase()

      void (async () => {
        try {
          let root: THREE.Object3D

          if (ext === 'stl') {
            const geo = await new STLLoader().loadAsync(objectUrl)
            geo.computeVertexNormals()
            toDispose.push(geo)
            root = new THREE.Mesh(geo, mat)
          } else if (ext === 'obj') {
            const group = (await new OBJLoader().loadAsync(objectUrl)) as THREE.Group
            group.traverse(child => {
              if (child instanceof THREE.Mesh) {
                toDispose.push(child.geometry as THREE.BufferGeometry)
                child.material = mat
              }
            })
            root = group
          } else {
            // 3MF
            const group = (await new ThreeMFLoader().loadAsync(objectUrl)) as THREE.Group
            group.traverse(child => {
              if (child instanceof THREE.Mesh) {
                toDispose.push(child.geometry as THREE.BufferGeometry)
                child.material = mat
              }
            })
            root = group
          }

          if (!alive) return

          scene.add(root)

          const box = new THREE.Box3().setFromObject(root)
          fitBoxRef.current = box
          fitToBox(box, camera, controls)

          initPosRef.current.copy(camera.position)
          initTgtRef.current.copy(controls.target)

          setLoading(false)
        } catch {
          if (!alive) return
          setParseError(t('ciViewerError'))
          setLoading(false)
        } finally {
          URL.revokeObjectURL(objectUrl)
        }
      })()
    } else if (meshSource) {
      // ── Mesh payload path: synchronous build from backend tessellation ──
      try {
        const geo = new THREE.BufferGeometry()
        geo.setAttribute('position', new THREE.Float32BufferAttribute(meshSource.positions, 3))
        geo.setIndex(meshSource.indices)
        geo.computeVertexNormals()
        toDispose.push(geo)
        const root = new THREE.Mesh(geo, mat)

        scene.add(root)

        const box = new THREE.Box3().setFromObject(root)
        fitBoxRef.current = box
        fitToBox(box, camera, controls)

        initPosRef.current.copy(camera.position)
        initTgtRef.current.copy(controls.target)

        setLoading(false)
      } catch {
        setParseError(t('ciViewerError'))
        setLoading(false)
      }
    }

    // ── Cleanup ────────────────────────────────────────────────────────────
    return () => {
      alive = false
      cancelAnimationFrame(animId)
      ro.disconnect()
      controls.dispose()
      for (const d of toDispose) d.dispose()
      renderer.dispose()
      if (container.contains(renderer.domElement)) {
        container.removeChild(renderer.domElement)
      }
      cameraRef.current   = null
      controlsRef.current = null
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fileSource, meshSource])

  const handleFit = useCallback(() => {
    if (!cameraRef.current || !controlsRef.current || !fitBoxRef.current) return
    fitToBox(fitBoxRef.current, cameraRef.current, controlsRef.current)
  }, [])

  const handleReset = useCallback(() => {
    if (!cameraRef.current || !controlsRef.current) return
    cameraRef.current.position.copy(initPosRef.current)
    controlsRef.current.target.copy(initTgtRef.current)
    controlsRef.current.update()
  }, [])

  return (
    <div className="relative w-full overflow-hidden rounded-md" style={{ height: '420px' }}>
      <div ref={containerRef} className="h-full w-full" />

      {loading && !parseError && (
        <div className="absolute inset-0 flex items-center justify-center bg-tp-surface/80 text-tp-text-2">
          <LoaderCircle size={20} className="animate-spin" aria-hidden="true" />
          <span className="ml-2 text-sm">{t('ciViewerLoading')}</span>
        </div>
      )}

      {parseError && (
        <div className="absolute inset-0 flex items-center justify-center bg-tp-surface">
          <p className="text-sm text-tp-error">{parseError}</p>
        </div>
      )}

      {!loading && !parseError && (
        <div className="absolute right-2 top-2 flex gap-1">
          <button
            type="button"
            onClick={handleFit}
            aria-label={t('ciViewerFit')}
            title={t('ciViewerFit')}
            className="rounded border border-tp-border bg-tp-surface/80 p-1.5 text-tp-text-2 hover:bg-tp-surface hover:text-tp-text"
          >
            <Maximize2 size={14} aria-hidden="true" />
          </button>
          <button
            type="button"
            onClick={handleReset}
            aria-label={t('ciViewerReset')}
            title={t('ciViewerReset')}
            className="rounded border border-tp-border bg-tp-surface/80 p-1.5 text-tp-text-2 hover:bg-tp-surface hover:text-tp-text"
          >
            <RotateCcw size={14} aria-hidden="true" />
          </button>
        </div>
      )}
    </div>
  )
}
