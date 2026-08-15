import { Suspense, lazy, useEffect, type ReactNode } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { AppLayout } from './app/AppLayout'
import { SignIn } from './app/SignIn'
import { NAV_ITEMS } from './app/navigation'
import { ErrorBoundary } from './components/ErrorBoundary'
import { Forbidden, PanelSkeleton } from './components/ui/feedback'
import { api, queryKeys } from './lib/api'
import { shouldRetry } from './hooks/useModuleQuery'
import { useSession } from './stores/session'
import type { Identity, ModuleId } from './lib/types'
import { OverviewPage } from './pages/OverviewPage'

const OrgPage = lazy(() => import('./pages/OrgPage').then((m) => ({ default: m.OrgPage })))
const BoardPage = lazy(() => import('./pages/BoardPage').then((m) => ({ default: m.BoardPage })))
const WavesPage = lazy(() => import('./pages/WavesPage').then((m) => ({ default: m.WavesPage })))
const RunsPage = lazy(() => import('./pages/RunsPage').then((m) => ({ default: m.RunsPage })))
const AgentsPage = lazy(() => import('./pages/AgentsPage').then((m) => ({ default: m.AgentsPage })))
const ToolsPage = lazy(() => import('./pages/ToolsPage').then((m) => ({ default: m.ToolsPage })))
const QualityPage = lazy(() => import('./pages/QualityPage').then((m) => ({ default: m.QualityPage })))
const MetricsPage = lazy(() => import('./pages/MetricsPage').then((m) => ({ default: m.MetricsPage })))
const MemoryPage = lazy(() => import('./pages/MemoryPage').then((m) => ({ default: m.MemoryPage })))
const CostPage = lazy(() => import('./pages/CostPage').then((m) => ({ default: m.CostPage })))
const InterruptsPage = lazy(() =>
  import('./pages/InterruptsPage').then((m) => ({ default: m.InterruptsPage })),
)
const GatesPage = lazy(() => import('./pages/GatesPage').then((m) => ({ default: m.GatesPage })))
const AccessPage = lazy(() => import('./pages/AccessPage').then((m) => ({ default: m.AccessPage })))
const FlagsPage = lazy(() => import('./pages/FlagsPage').then((m) => ({ default: m.FlagsPage })))
const AuditPage = lazy(() => import('./pages/AuditPage').then((m) => ({ default: m.AuditPage })))

const PAGES: Record<ModuleId, ReactNode> = {
  overview: <OverviewPage />,
  'org.directory': <OrgPage />,
  'product.board': <BoardPage />,
  'engineering.waves': <WavesPage />,
  'engineering.runs': <RunsPage />,
  'engineering.agents': <AgentsPage />,
  'engineering.tools': <ToolsPage />,
  'engineering.quality': <QualityPage />,
  'operations.metrics': <MetricsPage />,
  'operations.memory': <MemoryPage />,
  'operations.cost': <CostPage />,
  'governance.interrupts': <InterruptsPage />,
  'governance.gates': <GatesPage />,
  'governance.rbac': <AccessPage />,
  'governance.flags': <FlagsPage />,
  'governance.audit': <AuditPage />,
}

function RequireModule({ module, children }: { module: ModuleId; children: ReactNode }) {
  const identity = useSession((state) => state.identity)
  if (!identity) return <PanelSkeleton rows={4} />
  if (!identity.modules.includes(module)) {
    const reason = identity.denied.find((entry) => entry.module === module)?.reason
    return <Forbidden reason={reason} />
  }
  return <>{children}</>
}

function Splash() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-background">
      <p className="font-mono text-xs text-muted-foreground">contacting control plane…</p>
    </div>
  )
}

export function App() {
  const token = useSession((state) => state.token)
  const setIdentity = useSession((state) => state.setIdentity)

  const identityQuery = useQuery<Identity, unknown>({
    queryKey: queryKeys.me,
    queryFn: ({ signal }) => api.me(signal),
    enabled: Boolean(token),
    retry: shouldRetry,
    staleTime: 60_000,
  })

  const identity = identityQuery.data ?? null

  useEffect(() => {
    setIdentity(identity)
  }, [identity, setIdentity])

  if (!token) return <SignIn />
  if (identityQuery.isError) return <SignIn error={identityQuery.error} />
  if (!identity) return <Splash />

  return (
    <Routes>
      <Route element={<AppLayout />}>
        {NAV_ITEMS.map((item) => (
          <Route
            key={item.module}
            path={item.path}
            element={
              <ErrorBoundary moduleName={item.label}>
                <RequireModule module={item.module}>
                  <Suspense fallback={<PanelSkeleton rows={5} />}>{PAGES[item.module]}</Suspense>
                </RequireModule>
              </ErrorBoundary>
            }
          />
        ))}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  )
}
