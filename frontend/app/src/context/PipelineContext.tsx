import React, { createContext, useContext, useState, ReactNode } from 'react';

interface PipelineState {
  analysisSessionId: string | null;
  drawingParserSessionId: string | null;
  confirmedRequirements: Record<string, unknown> | null;
  cadSessionId: string | null;
  selectedRouteId: string | null;
  optimizedRoute: Record<string, unknown> | null;
  manufacturingPlanId: string | null;
}

interface PipelineContextType extends PipelineState {
  setAnalysisSessionId: (id: string | null) => void;
  setDrawingParserSessionId: (id: string | null) => void;
  setConfirmedRequirements: (req: Record<string, unknown> | null) => void;
  setCadSessionId: (id: string | null) => void;
  setSelectedRouteId: (id: string | null) => void;
  setOptimizedRoute: (route: Record<string, unknown> | null) => void;
  setManufacturingPlanId: (id: string | null) => void;
  clearPipeline: () => void;
}

const defaultState: PipelineState = {
  analysisSessionId: null,
  drawingParserSessionId: null,
  confirmedRequirements: null,
  cadSessionId: null,
  selectedRouteId: null,
  optimizedRoute: null,
  manufacturingPlanId: null,
};

const PipelineContext = createContext<PipelineContextType | undefined>(undefined);

export function PipelineProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<PipelineState>(defaultState);

  const setField = <K extends keyof PipelineState>(key: K, value: PipelineState[K]) =>
    setState(prev => ({ ...prev, [key]: value }));

  return (
    <PipelineContext.Provider value={{
      ...state,
      setAnalysisSessionId: id => setField('analysisSessionId', id),
      setDrawingParserSessionId: id => setField('drawingParserSessionId', id),
      setConfirmedRequirements: req => setField('confirmedRequirements', req),
      setCadSessionId: id => setField('cadSessionId', id),
      setSelectedRouteId: id => setField('selectedRouteId', id),
      setOptimizedRoute: route => setField('optimizedRoute', route),
      setManufacturingPlanId: id => setField('manufacturingPlanId', id),
      clearPipeline: () => setState(defaultState),
    }}>
      {children}
    </PipelineContext.Provider>
  );
}

export function usePipeline(): PipelineContextType {
  const ctx = useContext(PipelineContext);
  if (!ctx) throw new Error('usePipeline must be used within PipelineProvider');
  return ctx;
}
