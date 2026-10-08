import { useEffect, useMemo, useSyncExternalStore } from 'react'
import { AnalysisController, type AnalysisApi } from '../lib/analysisController.ts'

/** Owns one controller for the page's lifetime; polling stops when the page unmounts. */
export function useAnalysisController(api: AnalysisApi) {
  const controller = useMemo(() => new AnalysisController(api), [api])
  useEffect(() => {
    controller.activate()
    return () => controller.dispose()
  }, [controller])
  const state = useSyncExternalStore(
    controller.subscribe,
    controller.getState,
    controller.getState,
  )
  return { controller, state }
}
