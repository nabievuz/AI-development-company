export type Tier = 'founder' | 'cxo' | 'lead' | 'ic' | 'audit' | 'orchestrator'

export type ModuleId =
  | 'overview'
  | 'org.directory'
  | 'product.board'
  | 'engineering.waves'
  | 'engineering.runs'
  | 'engineering.agents'
  | 'engineering.tools'
  | 'engineering.quality'
  | 'operations.metrics'
  | 'operations.memory'
  | 'operations.cost'
  | 'governance.flags'
  | 'governance.audit'
  | 'governance.gates'
  | 'governance.rbac'
  | 'governance.interrupts'

export type ActionId = 'goal.submit' | 'run.trigger' | 'gate.approve'

export interface Panel {
  available: boolean
  reason: string
}

export interface DeniedEntry {
  module: string
  reason: string
  stage: 'substrate' | 'org_tier' | 'department'
}

export interface CatalogueEntry {
  id: ModuleId
  title: string
  department: string
  permission: string
  min_tier: Tier
}

export interface Identity {
  user: string
  principal: string
  kind: string
  role: string
  tier: Tier
  base_tier: Tier
  department: string
  ladder: string[]
  modules: ModuleId[]
  actions: ActionId[]
  denied: DeniedEntry[]
  catalogue: CatalogueEntry[]
}

export interface DepartmentRow {
  key: string
  title: string
  manager_role: string
  headcount: number
}

export interface RoleRow {
  key: string
  title: string
  department: string
  model: string
  effort: string
  reports_to: string
  tier: Tier
  mission: string
  has_template: boolean
  tool_grants: number
  direct_reports: string[]
}

export interface OrgTotals {
  roles: number
  departments: number
  by_department: Record<string, number>
  by_tier: Record<string, number>
  by_model: Record<string, number>
  templated: number
}

export interface OrgPanel extends Panel {
  departments: DepartmentRow[]
  roles?: RoleRow[]
  totals: OrgTotals
  ladder: string[]
}

export interface TicketRow {
  id: string
  title: string
  status: string
  priority: string
  assignee: string
  updated: string
  goal?: string
  stage?: string
  parent?: string
  dept?: string
}

export interface GateStage {
  gate: string
  closed: boolean
  tickets: string[]
  status: string
}

export interface GoalBreakdown {
  goal: string
  total: number
  by_status: Record<string, number>
  stages: GateStage[]
  open_gates: number
  epic: string
}

export interface ProjectBoard {
  slug: string
  path: string
  total: number
  by_status: Record<string, number>
  by_priority: Record<string, number>
  by_assignee: Record<string, number>
  goals: GoalBreakdown[]
  open_gates: number
  blocked: number
  in_review: number
  done: number
  tickets: TicketRow[]
}

export interface ProjectsPanel extends Panel {
  projects?: ProjectBoard[]
  total?: number
  project_count?: number
}

export interface BoardPanel extends Panel {
  tickets: TicketRow[]
  total: number
  by_status: Record<string, number>
  by_priority: Record<string, number>
  blocked: number
  in_review: number
  projects?: ProjectsPanel
}

export interface WaveRow {
  start: string
  dispatched: number
  model_mix: Record<string, number>
  idle: boolean
}

export interface WavesPanel extends Panel {
  waves: WaveRow[]
  total: number
  dispatched_total: number
  idle_waves: number
}

export interface RunRow {
  file: string
  run: string
  group: string
  keys: string[]
  record: Record<string, unknown>
}

export interface RunsPanel extends Panel {
  runs: RunRow[]
  total: number
}

export interface AuditEntry {
  ts?: string
  action?: string
  principal_id?: string
  principal_kind?: string
  decision?: string
  reason?: string
  detail?: string
}

export interface AuditPanel extends Panel {
  entries: AuditEntry[]
  total: number
  by_decision: Record<string, number>
  by_action: Record<string, number>
  denials: number
}

export interface EventRow {
  event_type?: string
  ts?: string
  created_at?: string
  [key: string]: unknown
}

export interface EventsPanel extends Panel {
  events: EventRow[]
  total: number
  by_type: Record<string, number>
}

export interface FlagRow {
  flag: string
  enabled: boolean
}

export interface FlagsPanel extends Panel {
  flags: FlagRow[]
  enabled: number
  total: number
}

export interface PrincipalKindRow {
  kind: string
  human: boolean
  description: string
  grants: Record<string, string>
}

export interface RbacPanel extends Panel {
  principal_kinds: PrincipalKindRow[]
  permissions: string[]
  founder_only: string[]
  gate_approval_authority: Record<string, string>
  modules: CatalogueEntry[]
}

export interface InterruptCard {
  id: string
  readable: boolean
  ticket?: string
  question?: string
  decision?: string
  resume?: string
  options?: string[]
  conditions?: string[]
  type?: string
  created_by?: string
  source?: string
  expires?: string
  expired?: boolean
  answerable?: boolean
  schema_valid: boolean
  violations: string[]
}

export interface InterruptsPanel extends Panel {
  cards: InterruptCard[]
  total: number
  expired: number
  answerable: number
  schema_divergent: number
}

export interface HealthTrack {
  code: string
  title: string
  value: number | null
  unit: string
  available: boolean
  reason: string
  detail: Record<string, unknown>
}

export interface TracksPanel extends Panel {
  tracks: HealthTrack[]
  events: number
  waves: number
  degraded: string[]
}

export interface ThroughputPanel extends Panel {
  series: number[]
  direction: string
  slope?: number
}

export interface TokenGroup {
  key: string
  input_tokens: number
  cached_input_tokens: number
  output_tokens: number
  span_count: number
  estimated_cost_usd: number
}

export interface CostPanel extends Panel {
  totals?: {
    spans: number
    input_tokens: number
    cached_input_tokens: number
    output_tokens: number
    estimated_cost_usd: number
    dropped_undated: number
  }
  by_tier?: TokenGroup[]
  by_agent?: TokenGroup[]
  by_ticket?: TokenGroup[]
  unpriced_tiers?: string[]
}

export interface AgentRow {
  agent: string
  spans: number
  ok: number
  success_rate: number
  input_tokens: number
  output_tokens: number
  tiers: string[]
}

export interface TemplateRow {
  role: string
  bytes: number
}

export interface AgentsPanel extends Panel {
  agents?: AgentRow[]
  total?: number
  templates: Panel & { templates?: TemplateRow[]; total?: number }
}

export interface ToolsPanel extends Panel {
  tools?: { tool: string; calls: number }[]
  span_kinds?: { kind: string; count: number }[]
  unavailable?: number
}

export interface Gate6Panel extends Panel {
  counts: Record<string, number>
  records?: { file: string; status: string; change_type: string }[]
  tuning_events: number
}

export interface MemoryPanel extends Panel {
  total?: number
  recallable?: number
  health?: number
}

export interface MetricsResponse {
  tracks: TracksPanel
  throughput: ThroughputPanel
}

export interface QualityResponse {
  tracks: TracksPanel
  gate6: Gate6Panel
}

export interface SummaryResponse {
  tier: Tier
  modules: ModuleId[]
  panels: {
    org?: OrgPanel
    board?: BoardPanel
    waves?: WavesPanel
    interrupts?: InterruptsPanel
    flags?: FlagsPanel
    metrics?: TracksPanel
    cost?: CostPanel
    throughput?: ThroughputPanel
    audit?: AuditPanel
  }
}

export interface HealthResponse {
  ok: boolean
  flag: boolean
  rbac_configured: boolean
  dashboard: { router: boolean; spa: boolean; error: string }
}
