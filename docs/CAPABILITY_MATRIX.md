# MachiningPro AI — Capability Matrix
Version: 0.5.0-demo

| Capability | Status | Notes |
|------------|--------|-------|
| Machine Catalog | DEMO_READY | 37 machines, 11 manufacturers |
| Cutting Tool Catalog | DEMO_READY | 40 tools, 5 manufacturers |
| Tool Holder Catalog | DEMO_READY | 17 holders, 5 manufacturers |
| Cutting Parameters | DEMO_READY | 74 REFERENCE_ONLY records |
| Tool Life (Empirical) | DEMO_READY | Taylor equation, tool wear model |
| Machine-Tool-Holder Compatibility | DEMO_READY | 3-state engine, 494 COMPATIBLE |
| Configuration Selection | DEMO_READY | RPM margin + reference criteria |
| Material Intelligence | PREVIEW | 19 materials, 6 API endpoints |
| Process Route Optimization | DEMO_READY | 5 strategies, 10-component scoring, Pareto |
| GD&T Intelligence | DEMO_READY | FCF, bonus tolerance, VC, composite FCF |
| Drawing Semantic Extraction | DEMO_READY | PDF + DXF, 6 parsers |
| CAD Feature Recognition | DEMO_READY | B-Rep engine, DXF, STEP L1 |
| Process Capability | DEMO_READY | IT table, tolerance/surface capability |
| Cycle Time Estimation | DEMO_READY | Operation-level, bounded NC parser |
| Manufacturing Plan | DEMO_READY | 12 modules, 8 tabs, approval workflow |
| Inspection Plan | DEMO_READY | 20 methods, coverage rate |
| Control Plan | DEMO_READY | Frequency, sampling, reaction plan |
| Export (JSON/CSV/HTML) | DEMO_READY | Traceability fingerprint, REFERENCE_ONLY |
| Export (XLSX) | DEFERRED | — |
| Export (NC Handoff) | DEMO_READY | Setup packages, NC_FILE_EXECUTED=False |
| STEP Level 2 B-Rep | OPTIONAL_DEPENDENCY | Requires pythonocc-core |
| VLM/OCR Analysis | OPTIONAL_DEPENDENCY | Requires Ollama + granite3.2-vision:2b |
| Database Persistence | NOT_IMPLEMENTED | In-memory only |
| Multi-user Auth | NOT_IMPLEMENTED | Single shared credential |
| PFMEA | NOT_IMPLEMENTED | Deferred |
| SPC | NOT_IMPLEMENTED | Deferred |
| MES/ERP Integration | NOT_IMPLEMENTED | Deferred |
