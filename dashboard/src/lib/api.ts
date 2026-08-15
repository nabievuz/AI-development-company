import type {
  AgentsPanel,
  AuditPanel,
  BoardPanel,
  CostPanel,
  EventsPanel,
  FlagsPanel,
  Gate6Panel,
  HealthResponse,
  Identity,
  InterruptsPanel,
  MemoryPanel,
  MetricsResponse,
  OrgPanel,
  QualityResponse,
  RbacPanel,
  RunsPanel,
  SummaryResponse,
  ToolsPanel,
  WavesPanel,
} from './types'

const BASE = '/api/dashboard'

export class ApiError extends Error {
  readonly status: number
  readonly detail: string

  constructor(status: number, detail: string) {
    super(detail || `request failed with status ${status}`)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }

  get isUnauthorized(): boolean {
    return this.status === 401
  }

  get isForbidden(): boolean {
    return this.status === 403
  }

  get isDisabled(): boolean {
    return this.status === 404
  }

  get isUnconfigured(): boolean {
    return this.status === 503
  }
}

type TokenReader = () => string

let readToken: TokenReader = () => ''
let onUnauthorized: () => void = () => {}

export function configureApi(reader: TokenReader, unauthorized: () => void): void {
  readToken = reader
  onUnauthorized = unauthorized
}

async function request<T>(path: string, signal?: AbortSignal): Promise<T> {
  const token = readToken()
  const headers: Record<string, string> = { Accept: 'application/json' }
  if (token) headers.Authorization = `Bearer ${token}`

  let response: Response
  try {
    response = await fetch(path, { headers, signal, cache: 'no-store', credentials: 'omit' })
  } catch (cause) {
    if (signal?.aborted) throw cause
    throw new ApiError(0, 'control plane unreachable — is it running?')
  }

  if (!response.ok) {
    let detail = ''
    try {
      const body = (await response.json()) as { detail?: unknown }
      detail = typeof body.detail === 'string' ? body.detail : ''
    } catch {
      detail = ''
    }
    if (response.status === 401) onUnauthorized()
    throw new ApiError(response.status, detail)
  }

  return (await response.json()) as T
}

function withLimit(path: string, limit?: number): string {
  return limit && limit > 0 ? `${path}?limit=${encodeURIComponent(String(limit))}` : path
}

export const api = {
  health: (signal?: AbortSignal) => request<HealthResponse>('/healthz', signal),
  me: (signal?: AbortSignal) => request<Identity>(`${BASE}/me`, signal),
  summary: (signal?: AbortSignal) => request<SummaryResponse>(`${BASE}/summary`, signal),
  org: (signal?: AbortSignal) => request<OrgPanel>(`${BASE}/org`, signal),
  board: (limit?: number, signal?: AbortSignal) =>
    request<BoardPanel>(withLimit(`${BASE}/board`, limit), signal),
  waves: (limit?: number, signal?: AbortSignal) =>
    request<WavesPanel>(withLimit(`${BASE}/waves`, limit), signal),
  runs: (limit?: number, signal?: AbortSignal) =>
    request<RunsPanel>(withLimit(`${BASE}/runs`, limit), signal),
  events: (limit?: number, signal?: AbortSignal) =>
    request<EventsPanel>(withLimit(`${BASE}/events`, limit), signal),
  agents: (signal?: AbortSignal) => request<AgentsPanel>(`${BASE}/agents`, signal),
  tools: (signal?: AbortSignal) => request<ToolsPanel>(`${BASE}/tools`, signal),
  quality: (signal?: AbortSignal) => request<QualityResponse>(`${BASE}/quality`, signal),
  metrics: (signal?: AbortSignal) => request<MetricsResponse>(`${BASE}/metrics`, signal),
  memory: (signal?: AbortSignal) => request<MemoryPanel>(`${BASE}/memory`, signal),
  cost: (signal?: AbortSignal) => request<CostPanel>(`${BASE}/cost`, signal),
  flags: (signal?: AbortSignal) => request<FlagsPanel>(`${BASE}/flags`, signal),
  audit: (limit?: number, signal?: AbortSignal) =>
    request<AuditPanel>(withLimit(`${BASE}/audit`, limit), signal),
  gates: (signal?: AbortSignal) => request<Gate6Panel>(`${BASE}/gates`, signal),
  rbac: (signal?: AbortSignal) => request<RbacPanel>(`${BASE}/rbac`, signal),
  interrupts: (signal?: AbortSignal) => request<InterruptsPanel>(`${BASE}/interrupts`, signal),
}

export const queryKeys = {
  health: ['health'] as const,
  me: ['me'] as const,
  summary: ['summary'] as const,
  module: (id: string) => ['module', id] as const,
}
