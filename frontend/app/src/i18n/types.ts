/**
 * MachiningPro AI - Internationalization Type Definitions
 * Supports: Turkish (tr), English (en)
 */

export type Locale = 'tr' | 'en'

export interface TranslationDictionary {
  // Navigation & General
  dashboard: string
  settings: string
  help: string
  logout: string
  login: string
  home: string

  // Language Selection
  language: string
  turkish: string
  english: string

  // Landing Page
  landingHeroTitle: string
  landingHeroSubtitle: string
  landingHeroParagraph: string
  landingPrecisionMachining: string
  engineeredByPhysics: string
  determinisitcEngineeringFirst: string
  openEngineeringWorkspace: string
  exploreCapabilities: string
  cadLabel: string
  processLabel: string
  toolLabel: string
  validationLabel: string
  engineeringWorkflow: string
  determinisitcPhysics: string
  determinisitcPhysicsDesc: string
  aiAssistance: string
  aiAssistanceDesc: string
  engineeringCapabilities: string
  availableStatus: string
  foundationStatus: string

  // Login Page
  workstationTitle: string
  workstationSubtitle: string
  alphaEngineeringPreview: string
  username: string
  password: string
  signIn: string
  backToHome: string
  deterministicEngineeringWorkstation: string

  // Dashboard
  machiningEngineeringWorkspace: string
  physicsBasedValidation: string
  currentEngineeringPreview: string
  systemStatus: string
  apiStatus: string
  version: string
  database: string
  serverDate: string
  connected: string
  machiningAnalysis: string
  cuttingParameters: string
  toolLife: string
  surfaceRoughness: string
  cadImport: string
  processPlanning: string
  quickActions: string
  processSelection: string
  engineeringDomains: string
  exploreCapabilitiesByDomain: string
  useLeftNavigation: string
  ready: string

  // Process Explorer
  milling: string
  turning: string
  drilling: string
  cam: string
  validation: string
  millingOperations: string
  millingDesc: string
  turningOperations: string
  turningDesc: string
  drillingOperations: string
  drillingDesc: string
  camToolpath: string
  camDesc: string
  processValidation: string
  validationDesc: string
  foundationAvailable: string
  uiIntegrationAvailable: string
  status: string

  // Tool Life Page
  engineeringAnalysis: string
  toolLifePrediction: string
  physicsBasedToolWear: string
  uiIntegrationPending: string
  backendCapabilityAvailable: string
  frontendCalcIntegration: string
  workspaceShowsInput: string
  basicInputs: string
  process: string
  selectProcess: string
  cuttingSpeed: string
  speedUnit: string
  speedExample: string
  feed: string
  feedUnit: string
  feedExample: string
  toolMaterial: string
  selectMaterial: string
  highSpeedSteel: string
  carbide: string
  ceramic: string
  workpieceMaterial: string
  steel: string
  aluminum: string
  titanium: string
  castIron: string
  advancedParameters: string
  depthOfCut: string
  depthExample: string
  coolant: string
  selectCoolant: string
  dry: string
  flood: string
  mist: string
  toolLifeAnalysis: string
  illustrativeUiPreview: string
  toolLifeTrend: string
  chartsRender: string
  validationStatus: string
  pendingInput: string
  modelSource: string
  foundationModel: string
  engineeringNotes: string
  toolLifeUsePhysics: string
  resultsDepend: string
  analysisForGuidance: string
  configureAnalysis: string
  viewModelStatus: string
  reviewInputs: string

  // Help System
  howToUse: string
  nasılKullanılır: string

  // Module Guide Sections
  modulePurpose: string
  whatIsThisModuleFor: string
  whenToUse: string
  whenShouldItBeUsed: string
  requiredInputs: string
  workflow: string
  workflowSteps: string
  outputs: string
  howToInterpretResults: string
  assumptions: string
  limitations: string
  validationQualificationStatus: string
  commonMistakes: string
  exampleWorkflow: string
  relatedModules: string

  // Status Labels
  available: string
  foundation: string
  preview: string
  integrationPending: string
  validated: string
  notConfigured: string
  engineeringReviewRequired: string
  notQualified: string

  // Buttons
  next: string
  back: string
  skip: string
  finish: string
  close: string
  open: string

  // Error States
  pageNotFound: string
  backToHomeError: string
  invalidCredentials: string
  authenticationFailed: string
  backendUnavailable: string
  loading: string
  requiredField: string
  noMachineSelected: string
  noMaterialSelected: string
  noToolSelected: string
  noCADFileLoaded: string
  analysisNotConfigured: string

  // Onboarding
  welcome: string
  navigation: string
  contextBar: string
  basicVsAdvanced: string
  modelValidationStatus: string
  helpSystem: string

  // Glossary (selected terms)
  machining: string
  machiningDef: string
  cuttingSpeedDef: string
  feedDef: string
  toolLifeDef: string
  surfaceRoughnessDef: string
  dfmDef: string
  cadenumerator: string
  camDef: string
  cncDef: string
  validationDef: string
  verificationDef: string
  qualificationDef: string

  // Technical Drawing Intelligence - human review
  drPageTitle: string
  drPageSubtitle: string
  drReviewRequired: string
  drSessionNote: string
  drDrawing: string
  drNoDrawing: string
  drLoadSample: string
  drSampleNote: string
  drDeterministicResult: string
  drDeterministicHint: string
  drNoDeterministic: string
  drAiSuggestion: string
  drHumanConfirmed: string
  drRejected: string
  drEditedByHuman: string
  drPendingReview: string
  drAdvisory: string
  drPanelTitle: string
  drAccept: string
  drReject: string
  drEdit: string
  drSaveEdit: string
  drCancel: string
  drEditValueLabel: string
  drAiOriginalValue: string
  drHumanValue: string
  drFindingType: string
  drConfidence: string
  drNoConfidence: string
  drProvider: string
  drModel: string
  drRegion: string
  drSource: string
  drSourceRegion: string
  drSourceRegionNote: string
  drModelBoxLegacy: string
  drSelectFinding: string
  drCompared: string
  drCorroborated: string
  drConflict: string
  drAdvisoryOnly: string
  drOtherComparison: string
  drReviewHistory: string
  drReviewedBy: string
  drNotRecorded: string
  drCountPending: string
  drCountAccepted: string
  drCountEdited: string
  drCountRejected: string
  drEditBlank: string
  drEditTooLong: string
  drEditControl: string
  drEditUnchanged: string
  drNoFindings: string
  drStateIdle: string
  drStateNotConnected: string
  drStateDisabled: string
  drStateOllama: string
  drStateModel: string
  drStateTimeout: string
  drStateValidation: string
  drStateUnknown: string
  drDeterministicStillAvailable: string
  drPhasePreparing: string
  drPhaseAi: string
  drPhaseValidating: string
  drPhaseReady: string
  drSlowNote: string
  drPreviewStates: string
  drPhaseQueued: string
  drUploadDrawing: string
  drUploading: string
  drUploadFailed: string
  drAnalyze: string
  drAnalysisActive: string
  drAnalyzeAgain: string
  drReviewSaveFailed: string
  drStateInvalidDrawing: string
  drStateInvalidRegion: string
  drWholeImageNote: string
  drServerSessionNote: string
  drSampleBadge: string

  // Universal Engineering Import
  drImportInfoTitle: string
  drFileName: string
  drDetectedFormat: string
  drFormatFamily: string
  drImportStatus: string
  drEntityCount: string
  drCapabilityLevel: string
  drImportSuccess: string
  drImportPartial: string
  drImportFailed: string
  drImportUnsupported: string
  drImportUnrecognized: string
  drImportUploading: string
  drDrawingAnalysisNote: string
  drNonPdfNote: string
  drCadNote: string
  drCadStructureNote: string
  drMeshNote: string
  drNcNote: string
  drImportError: string

  // CAD Import Page
  ciPageSubtitle: string
  ciLoadAnother: string
  ciPreviewUnavailable: string
  ciPreviewUnavailableHint: string
  ciDxfPreview: string
  ciSelectPrompt: string
  ciErrFileTooLarge: string
  ciErrAuth: string
  ciErrInvalidFile: string
  ciErrImportFailed: string
  ciErrRequestFailed: string
  ciErrRenderFailed: string
  ciPdfNote: string
  ciAdapterUsed: string
  ciFidelityEvents: string

  // 3D Mesh Viewer (CAD_3D_VIEWER_01)
  ciMeshPreview: string
  ciViewerFit: string
  ciViewerReset: string
  ciViewerLoading: string
  ciViewerError: string

  // Cutting Parameters Page (CUTTING_PARAMETERS_UI_INTEGRATION_01)
  cpPageTitle: string
  cpPageSubtitle: string
  cpSelectOperation: string
  cpSelectIsoGroup: string
  cpSelectToolMaterial: string
  cpAnyToolMaterial: string
  cpQueryButton: string
  cpMatchLevel: string
  cpMatchIsoGroup: string
  cpMatchNoMatch: string
  cpNoMatchHint: string
  cpAuthorityLabel: string
  cpEvidenceReferenceOnly: string
  cpSource: string
  cpLimitation: string
  cpVcRange: string
  cpFeedRange: string
  cpFzRange: string
  cpApRange: string
  cpMissingParam: string
  cpCalcTitle: string
  cpDiameterMm: string
  cpSelectedVc: string
  cpRpmResult: string
  cpRpmFormula: string
  cpToothCount: string
  cpFeedRateResult: string
  cpFeedFormula: string
  cpMachineLimitNote: string
  cpReferenceGuidanceNote: string
  cpScopeLabel: string
  cpOperationTurning: string
  cpOperationMilling: string
  cpOperationDrilling: string
  cpOperationReaming: string
  cpIsoP: string
  cpIsoM: string
  cpIsoK: string
  cpIsoN: string
  cpIsoS: string
  cpIsoH: string
  cpToolCarbide: string
  cpToolHss: string
  cpToolCermet: string
  cpToolCeramic: string
  cpToolCbn: string
  cpToolPcd: string
  cpCalcEnterDiameter: string
  cpCalcEnterVc: string
  cpUnitMmin: string
  cpUnitMmRev: string
  cpUnitMmTooth: string
  cpUnitMm: string
  cpUnitRpm: string
  cpUnitMmMin: string

  // Sidebar
  sidebarPinned: string
  sidebarUnpinned: string

  // Cutting Parameters — validation
  cpVcOutOfRange: string
  cpDiameterInvalid: string

  // Tool Life Explorer (TOOL_LIFE_UI_INTEGRATION_01)
  tlPageTitle: string
  tlPageSubtitle: string
  tlEvidenceStatus: string
  tlObservations: string
  tlTools: string
  tlSensorFeatures: string
  tlEolObservations: string
  tlDatasetAvailable: string
  tlEmpiricalExploration: string
  tlProductionNotValidated: string
  tlSelectTool: string
  tlToolLabel: string
  tlToolType: string
  tlTotalCycles: string
  tlAdocMm: string
  tlRdocMm: string
  tlHolderLengthMm: string
  tlHardnessMean: string
  tlEolPresent: string
  tlEolYes: string
  tlEolNo: string
  tlLifecycleChart: string
  tlSensorChart: string
  tlSelectSensorFeature: string
  tlCycleToFailureLabel: string
  tlCycleToFailureSemantics: string
  tlLeakageWarning: string
  tlLeakageWarningDetail: string
  tlLimitations: string
  tlSourceProvenance: string
  tlSourceDoi: string
  tlSourceSheet: string
  tlDatasetNotConfigured: string
  tlDatasetNotConfiguredDetail: string
  tlLoadingTools: string
  tlLoadingDetail: string
  tlObsIndex: string
  tlNormalized: string
  tlEolMarker: string
  tlFeatureIndex: string

  // Tool Life — limitation bullets (TOOL_LIFE_UI_INTEGRATION_01_DEFECT_CLOSURE_01)
  tlLimVb: string
  tlLimTaylor: string
  tlLimCtf: string
  tlLimLeakage: string
  tlLimPrediction: string
  tlLimHardness: string
  tlLimProduction: string
}
