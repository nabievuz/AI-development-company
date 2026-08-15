import { useMemo, useState } from 'react'
import { Activity, ChevronDown, ChevronRight, Layers } from 'lucide-react'
import { ModuleCard } from '@/components/ModuleCard'
import { Badge } from '@/components/ui/badge'
import { BarList } from '@/components/charts'
import { DataTable, type Column } from '@/components/ui/table'
import { useModuleQuery, LIVE_INTERVAL, SLOW_INTERVAL } from '@/hooks/useModuleQuery'
import { api } from '@/lib/api'
import { count, relativeTime } from '@/lib/utils'
import type { EventRow, EventsPanel, RunRow, RunsPanel } from '@/lib/types'

const RUN_LIMIT = 100
const EVENT_LIMIT = 120
const SUMMARY_CHARS = 120
const TIME_KEYS = new Set(['event_type', 'ts', 'created_at'])

function runId(row: RunRow): string {
  return `${row.file}::${row.run}`
}

function eventSummary(row: EventRow): string {
  const rest: Record<string, unknown> = {}
  for (const [key, value] of Object.entries(row)) {
    if (TIME_KEYS.has(key)) continue
    rest[key] = value
  }
  if (Object.keys(rest).length === 0) return '—'
  const text = JSON.stringify(rest)
  return text.length > SUMMARY_CHARS ? `${text.slice(0, SUMMARY_CHARS)}…` : text
}

export function RunsPage() {
  const [selected, setSelected] = useState<string | null>(null)

  const runsQuery = useModuleQuery<RunsPanel>('runs', (signal) => api.runs(RUN_LIMIT, signal), {
    refetchInterval: SLOW_INTERVAL,
  })
  const eventsQuery = useModuleQuery<EventsPanel>(
    'events',
    (signal) => api.events(EVENT_LIMIT, signal),
    { refetchInterval: LIVE_INTERVAL },
  )

  const runsPanel = runsQuery.data
  const eventsPanel = eventsQuery.data

  const runs = useMemo(() => runsPanel?.runs ?? [], [runsPanel?.runs])
  const selectedRun = useMemo(
    () => runs.find((row) => runId(row) === selected),
    [runs, selected],
  )

  const byType = useMemo(
    () =>
      Object.entries(eventsPanel?.by_type ?? {})
        .sort((left, right) => right[1] - left[1])
        .map(([label, value]) => ({ label, value, hint: count(value) })),
    [eventsPanel?.by_type],
  )

  const runColumns: Column<RunRow>[] = [
    { key: 'run', header: 'Run', cell: (row) => row.run, mono: true },
    { key: 'group', header: 'Group', cell: (row) => row.group },
    { key: 'file', header: 'File', cell: (row) => row.file, mono: true },
    {
      key: 'keys',
      header: 'Keys',
      align: 'right',
      cell: (row) => count(row.keys.length),
      mono: true,
    },
    {
      key: 'record',
      header: <span className="sr-only">Raw record</span>,
      align: 'right',
      width: '3rem',
      cell: (row) => {
        const id = runId(row)
        const open = id === selected
        return (
          <button
            type="button"
            aria-expanded={open}
            aria-label={open ? `Hide raw record for ${row.run}` : `Show raw record for ${row.run}`}
            onClick={() => setSelected(open ? null : id)}
            className="rounded-md p-1 text-muted-foreground hover:bg-accent hover:text-foreground"
          >
            {open ? (
              <ChevronDown className="size-3.5" aria-hidden="true" />
            ) : (
              <ChevronRight className="size-3.5" aria-hidden="true" />
            )}
          </button>
        )
      },
    },
  ]

  const eventColumns: Column<EventRow>[] = [
    {
      key: 'type',
      header: 'Event',
      cell: (row) => <Badge variant="outline">{row.event_type ?? 'untyped'}</Badge>,
    },
    {
      key: 'when',
      header: 'When',
      cell: (row) => relativeTime(row.ts ?? row.created_at),
    },
    {
      key: 'payload',
      header: 'Payload',
      cell: (row) => <span className="block truncate">{eventSummary(row)}</span>,
      mono: true,
    },
  ]

  return (
    <div className="space-y-4">
      <ModuleCard
        title="Run checkpoints"
        description="Every checkpoint the engine wrote to the run store, exactly as recorded"
        icon={<Layers className="size-3.5" aria-hidden="true" />}
        moduleName="Runs"
        isLoading={runsQuery.isLoading}
        error={runsQuery.isError ? runsQuery.error : undefined}
        panel={runsPanel}
        emptyLabel="no run checkpoints recorded yet"
        actions={
          runsPanel?.available ? (
            <Badge variant="neutral">{count(runs.length)} shown</Badge>
          ) : null
        }
        bodyClassName="space-y-3 p-4"
        footer={
          runsPanel?.available
            ? `${count(runsPanel.total)} checkpoints on file · newest ${count(runs.length)} listed`
            : undefined
        }
      >
        <DataTable
          dense
          maxHeight="max-h-96"
          rowKey={(row, index) => `${runId(row)}::${index}`}
          rows={runs}
          columns={runColumns}
          empty={
            <p className="py-6 text-center text-xs text-muted-foreground">
              The run store reports no checkpoints.
            </p>
          }
        />

        {selectedRun ? (
          <div className="rounded-md border border-border bg-muted/50 p-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="font-mono text-[11px] text-muted-foreground">
                {selectedRun.file}
              </span>
              <Badge variant="outline">{count(selectedRun.keys.length)} keys</Badge>
            </div>
            <pre className="scrollbar-thin mt-2 max-h-72 overflow-auto font-mono text-[11px] leading-relaxed break-words whitespace-pre-wrap">
              {JSON.stringify(selectedRun.record, null, 2)}
            </pre>
          </div>
        ) : (
          <p className="text-xs text-muted-foreground">
            Expand a row to read its raw checkpoint record.
          </p>
        )}
      </ModuleCard>

      <ModuleCard
        title="Event tail"
        description="The raw append-only event stream behind every computed metric"
        icon={<Activity className="size-3.5" aria-hidden="true" />}
        moduleName="Events"
        isLoading={eventsQuery.isLoading}
        error={eventsQuery.isError ? eventsQuery.error : undefined}
        panel={eventsPanel}
        emptyLabel="the event store is empty"
        actions={
          eventsPanel?.available ? (
            <Badge variant="info">{count(byType.length)} types</Badge>
          ) : null
        }
        bodyClassName="p-4"
        footer={
          eventsPanel?.available
            ? `${count(eventsPanel.total)} events on file · newest ${count(eventsPanel.events.length)} listed`
            : undefined
        }
      >
        <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
          <div className="xl:col-span-1">
            <p className="mb-2 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
              By type
            </p>
            <BarList data={byType} />
          </div>
          <div className="xl:col-span-2">
            <DataTable
              dense
              maxHeight="max-h-96"
              rowKey={(_row, index) => String(index)}
              rows={eventsPanel?.events ?? []}
              columns={eventColumns}
              empty={
                <p className="py-6 text-center text-xs text-muted-foreground">
                  No events in the current window.
                </p>
              }
            />
          </div>
        </div>
      </ModuleCard>
    </div>
  )
}
