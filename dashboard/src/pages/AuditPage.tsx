import { useMemo, useState } from 'react'
import { Ban, CheckCircle2, Gavel, Layers, ListFilter, ScrollText } from 'lucide-react'
import { ModuleCard } from '@/components/ModuleCard'
import { Badge, DecisionBadge } from '@/components/ui/badge'
import { Stat, StatGrid } from '@/components/ui/stat'
import { BarList, type BarDatum } from '@/components/charts'
import { DataTable, type Column } from '@/components/ui/table'
import { useModuleQuery, LIVE_INTERVAL } from '@/hooks/useModuleQuery'
import { api } from '@/lib/api'
import { count, relativeTime, shortTime, titleCase } from '@/lib/utils'
import type { AuditEntry, AuditPanel } from '@/lib/types'

const AUDIT_LIMIT = 200

type Filter = 'all' | 'allow' | 'deny' | 'error'

const FILTERS: { id: Filter; label: string }[] = [
  { id: 'all', label: 'All' },
  { id: 'allow', label: 'Allow' },
  { id: 'deny', label: 'Deny' },
  { id: 'error', label: 'Error' },
]

function decisionOf(entry: AuditEntry): string {
  return (entry.decision ?? '').toLowerCase()
}

function matches(entry: AuditEntry, filter: Filter): boolean {
  return filter === 'all' || decisionOf(entry) === filter
}

function decisionTone(key: string): BarDatum['tone'] {
  const normalized = key.toLowerCase()
  if (normalized === 'allow') return 'allow'
  if (normalized === 'deny') return 'deny'
  if (normalized === 'error') return 'warn'
  return 'primary'
}

function distribution(
  source: Record<string, number>,
  tone: (key: string) => BarDatum['tone'],
  label: (key: string) => string,
): BarDatum[] {
  return Object.entries(source)
    .map(([key, value]) => ({ label: label(key), value, hint: count(value), tone: tone(key) }))
    .sort((left, right) => right.value - left.value)
}

const COLUMNS: Column<AuditEntry>[] = [
  {
    key: 'ts',
    header: 'When',
    width: '14%',
    cell: (row) => <span title={shortTime(row.ts)}>{relativeTime(row.ts)}</span>,
  },
  { key: 'action', header: 'Action', cell: (row) => row.action ?? '—', mono: true, width: '18%' },
  {
    key: 'principal',
    header: 'Principal',
    cell: (row) => row.principal_id ?? '—',
    mono: true,
    width: '16%',
  },
  {
    key: 'kind',
    header: 'Kind',
    cell: (row) => <Badge variant="outline">{row.principal_kind ?? '—'}</Badge>,
    width: '10%',
  },
  {
    key: 'decision',
    header: 'Decision',
    cell: (row) => <DecisionBadge decision={row.decision ?? ''} />,
    width: '10%',
  },
  {
    key: 'reason',
    header: 'Reason',
    cell: (row) => (
      <span className="block truncate text-xs text-muted-foreground" title={row.reason}>
        {row.reason || '—'}
      </span>
    ),
  },
]

export function AuditPage() {
  const [filter, setFilter] = useState<Filter>('all')
  const query = useModuleQuery<AuditPanel>('audit', (signal) => api.audit(AUDIT_LIMIT, signal), {
    refetchInterval: LIVE_INTERVAL,
  })

  const panel = query.data
  const isLoading = query.isLoading
  const error = query.isError ? query.error : undefined

  const entries = useMemo(
    () => (panel?.entries ?? []).filter((entry) => matches(entry, filter)),
    [panel?.entries, filter],
  )

  const allows = panel?.available ? (panel.by_decision.allow ?? 0) : null
  const actions = panel?.available ? Object.keys(panel.by_action).length : null

  return (
    <div className="space-y-4">
      <ModuleCard
        title="Audit totals"
        description="Every control-plane read is attributed to a principal and recorded"
        icon={<ScrollText className="size-3.5" />}
        moduleName="Audit totals"
        isLoading={isLoading}
        error={error}
        panel={panel}
        emptyLabel="no control-plane audit entries yet — the trail is genuinely empty"
      >
        <StatGrid>
          <Stat
            label="Entries"
            value={panel?.available ? count(panel.total) : '—'}
            hint={
              panel?.available
                ? `${count(panel.entries.length)} most recent held in view`
                : panel?.reason
            }
            icon={<ScrollText className="size-3.5" />}
          />
          <Stat
            label="Allows"
            value={allows === null ? '—' : count(allows)}
            hint="requests the policy admitted"
            tone={allows !== null && allows > 0 ? 'allow' : 'default'}
            icon={<CheckCircle2 className="size-3.5" />}
          />
          <Stat
            label="Denials"
            value={panel?.available ? count(panel.denials) : '—'}
            hint="requests the policy refused"
            tone={panel?.available && panel.denials > 0 ? 'deny' : 'default'}
            icon={<Ban className="size-3.5" />}
          />
          <Stat
            label="Distinct actions"
            value={actions === null ? '—' : count(actions)}
            hint="separate endpoints exercised"
            icon={<ListFilter className="size-3.5" />}
          />
        </StatGrid>
      </ModuleCard>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <ModuleCard
          title="Decision spread"
          description="How the policy engine ruled across the recorded window"
          icon={<Gavel className="size-3.5" />}
          moduleName="Audit decisions"
          isLoading={isLoading}
          error={error}
          panel={panel}
          emptyLabel="no decisions recorded yet — there is no spread to plot"
        >
          <BarList data={distribution(panel?.by_decision ?? {}, decisionTone, titleCase)} />
        </ModuleCard>

        <ModuleCard
          title="Action spread"
          description="Which surfaces principals actually reached for"
          icon={<Layers className="size-3.5" />}
          moduleName="Audit actions"
          isLoading={isLoading}
          error={error}
          panel={panel}
          emptyLabel="no actions recorded yet — there is no spread to plot"
        >
          <BarList data={distribution(panel?.by_action ?? {}, () => 'primary', (key) => key)} />
        </ModuleCard>
      </div>

      <ModuleCard
        title="Audit trail"
        description="Most recent decisions first — refreshed live"
        icon={<ScrollText className="size-3.5" />}
        moduleName="Audit trail"
        isLoading={isLoading}
        error={error}
        panel={panel}
        emptyLabel="no control-plane audit entries yet — nothing has been decided to record"
        actions={
          <div className="flex gap-1">
            {FILTERS.map((entry) => (
              <button
                key={entry.id}
                type="button"
                aria-pressed={filter === entry.id}
                onClick={() => setFilter(entry.id)}
                className={
                  filter === entry.id
                    ? 'rounded-md bg-accent px-2 py-1 text-[11px] font-medium'
                    : 'rounded-md px-2 py-1 text-[11px] text-muted-foreground hover:bg-accent/60'
                }
              >
                {entry.label}
              </button>
            ))}
          </div>
        }
        bodyClassName="p-0"
        footer={
          panel?.available
            ? `Showing ${count(entries.length)} of ${count(panel.total)} entries · top ${AUDIT_LIMIT} fetched`
            : undefined
        }
      >
        <DataTable
          dense
          maxHeight="max-h-[36rem]"
          rowKey={(row, index) => `${row.ts ?? ''}-${index}`}
          rows={entries}
          columns={COLUMNS}
          empty={
            <p className="px-4 py-6 text-center text-xs text-muted-foreground">
              No entries match the “{filter}” filter.
            </p>
          }
        />
      </ModuleCard>
    </div>
  )
}
