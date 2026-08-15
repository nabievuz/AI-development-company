import { useMemo } from 'react'
import { Activity, AlertTriangle, Layers, Wrench } from 'lucide-react'
import { ModuleCard } from '@/components/ModuleCard'
import { BarList } from '@/components/charts'
import { Stat, StatGrid } from '@/components/ui/stat'
import { DataTable } from '@/components/ui/table'
import { useModuleQuery, SLOW_INTERVAL } from '@/hooks/useModuleQuery'
import { api } from '@/lib/api'
import { count, percent } from '@/lib/utils'
import type { ToolsPanel } from '@/lib/types'

export function ToolsPage() {
  const query = useModuleQuery<ToolsPanel>('tools', (signal) => api.tools(signal), {
    refetchInterval: SLOW_INTERVAL,
  })

  const panel = query.data
  const isLoading = query.isLoading
  const error = query.isError ? query.error : undefined

  const tools = useMemo(
    () => [...(panel?.tools ?? [])].sort((left, right) => right.calls - left.calls),
    [panel?.tools],
  )
  const spanKinds = useMemo(
    () => [...(panel?.span_kinds ?? [])].sort((left, right) => right.count - left.count),
    [panel?.span_kinds],
  )

  const totalCalls = tools.reduce((sum, entry) => sum + entry.calls, 0)
  const hasTools = panel?.tools !== undefined
  const hasSpanKinds = panel?.span_kinds !== undefined
  const unavailable = panel?.unavailable

  return (
    <div className="space-y-4">
      <ModuleCard
        title="Tool surface"
        description="Tool calls and span kinds recorded by the span store"
        icon={<Wrench className="size-3.5" aria-hidden="true" />}
        moduleName="Tool totals"
        isLoading={isLoading}
        error={error}
        panel={panel}
        emptyLabel="no tool telemetry recorded yet"
      >
        <StatGrid>
          <Stat
            label="Distinct tools"
            value={hasTools ? count(tools.length) : '—'}
            hint={hasTools ? 'named in recorded spans' : 'tool breakdown not reported'}
            tone={hasTools ? 'default' : 'nodata'}
            icon={<Wrench className="size-3.5" aria-hidden="true" />}
          />
          <Stat
            label="Tool calls"
            value={hasTools ? count(totalCalls) : '—'}
            hint={hasTools ? 'summed across every tool' : 'no call counts to sum'}
            tone={hasTools ? 'default' : 'nodata'}
            icon={<Activity className="size-3.5" aria-hidden="true" />}
          />
          <Stat
            label="Span kinds"
            value={hasSpanKinds ? count(spanKinds.length) : '—'}
            hint={hasSpanKinds ? 'distinct kinds observed' : 'span-kind breakdown not reported'}
            tone={hasSpanKinds ? 'default' : 'nodata'}
            icon={<Layers className="size-3.5" aria-hidden="true" />}
          />
          <Stat
            label="Tool unavailable"
            value={unavailable === undefined ? '—' : count(unavailable)}
            hint={
              unavailable === undefined
                ? 'not reported by the span store'
                : 'spans that could not reach a tool'
            }
            tone={unavailable === undefined ? 'nodata' : unavailable > 0 ? 'warn' : 'default'}
            icon={<AlertTriangle className="size-3.5" aria-hidden="true" />}
          />
        </StatGrid>
      </ModuleCard>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <ModuleCard
          title="Calls by tool"
          description="Ranked by recorded call count"
          icon={<Wrench className="size-3.5" aria-hidden="true" />}
          moduleName="Calls by tool"
          isLoading={isLoading}
          error={error}
          panel={panel}
          emptyLabel="no tool calls recorded yet"
        >
          <BarList
            data={tools.map((entry) => ({
              label: entry.tool,
              value: entry.calls,
              hint: count(entry.calls),
            }))}
          />
        </ModuleCard>

        <ModuleCard
          title="Span kinds"
          description="How the engine labels the work it records"
          icon={<Layers className="size-3.5" aria-hidden="true" />}
          moduleName="Span kinds"
          isLoading={isLoading}
          error={error}
          panel={panel}
          emptyLabel="no spans recorded yet"
        >
          <BarList
            data={spanKinds.map((entry) => ({
              label: entry.kind,
              value: entry.count,
              hint: count(entry.count),
              tone: 'info',
            }))}
          />
        </ModuleCard>
      </div>

      <ModuleCard
        title="Tool ledger"
        description="Every tool the span store names, with its share of all calls"
        icon={<Activity className="size-3.5" aria-hidden="true" />}
        moduleName="Tool ledger"
        isLoading={isLoading}
        error={error}
        panel={panel}
        emptyLabel="no tool telemetry recorded yet"
        bodyClassName="p-0"
        footer={
          hasTools ? `${count(tools.length)} tools · ${count(totalCalls)} calls` : undefined
        }
      >
        <DataTable
          dense
          rows={tools}
          rowKey={(row) => row.tool}
          empty={
            <p className="px-4 py-6 text-center text-xs text-muted-foreground">
              No tool calls have been recorded.
            </p>
          }
          columns={[
            { key: 'tool', header: 'Tool', cell: (row) => row.tool, mono: true },
            {
              key: 'calls',
              header: 'Calls',
              align: 'right',
              mono: true,
              cell: (row) => count(row.calls),
            },
            {
              key: 'share',
              header: 'Share',
              align: 'right',
              mono: true,
              cell: (row) => percent(totalCalls > 0 ? row.calls / totalCalls : null, 1),
            },
          ]}
        />
      </ModuleCard>
    </div>
  )
}
