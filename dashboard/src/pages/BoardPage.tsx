import { Ban, ClipboardList, Eye, Flame, Layers, ListFilter } from 'lucide-react'
import { ModuleCard } from '@/components/ModuleCard'
import { Badge, StatusBadge, type BadgeProps } from '@/components/ui/badge'
import { Stat, StatGrid } from '@/components/ui/stat'
import { BarList, type BarDatum } from '@/components/charts'
import { DataTable, type Column } from '@/components/ui/table'
import { useModuleQuery, SLOW_INTERVAL } from '@/hooks/useModuleQuery'
import { api } from '@/lib/api'
import { count, relativeTime, titleCase } from '@/lib/utils'
import type { BoardPanel, TicketRow } from '@/lib/types'

const TICKET_LIMIT = 100

const PRIORITY_VARIANT: Record<string, BadgeProps['variant']> = {
  p0: 'deny',
  p1: 'warn',
  p2: 'neutral',
}

function statusTone(status: string): BarDatum['tone'] {
  if (status === 'blocked') return 'deny'
  if (status === 'in_review') return 'info'
  return 'primary'
}

function distribution(source: Record<string, number>, tone: (key: string) => BarDatum['tone']): BarDatum[] {
  return Object.entries(source)
    .map(([key, value]) => ({
      label: titleCase(key),
      value,
      hint: count(value),
      tone: tone(key),
    }))
    .sort((left, right) => right.value - left.value)
}

const COLUMNS: Column<TicketRow>[] = [
  { key: 'id', header: 'Ticket', cell: (row) => row.id, mono: true, width: '14%' },
  {
    key: 'title',
    header: 'Title',
    cell: (row) => <span className="block truncate">{row.title || '—'}</span>,
  },
  { key: 'status', header: 'Status', cell: (row) => <StatusBadge status={row.status} /> },
  {
    key: 'priority',
    header: 'Priority',
    cell: (row) => (
      <Badge variant={PRIORITY_VARIANT[row.priority] ?? 'neutral'}>{row.priority || '—'}</Badge>
    ),
  },
  { key: 'assignee', header: 'Assignee', cell: (row) => row.assignee || '—', mono: true },
  {
    key: 'updated',
    header: 'Updated',
    align: 'right',
    cell: (row) => relativeTime(row.updated),
  },
]

export function BoardPage() {
  const query = useModuleQuery<BoardPanel>('board', (signal) => api.board(TICKET_LIMIT, signal), {
    refetchInterval: SLOW_INTERVAL,
  })

  const panel = query.data
  const isLoading = query.isLoading
  const error = query.isError ? query.error : undefined

  const p0 = panel?.available ? (panel.by_priority.p0 ?? 0) : null
  const shown = panel?.available ? panel.tickets.length : 0

  return (
    <div className="space-y-4">
      <ModuleCard
        title="Board totals"
        description="Ticket counts read straight from board/tickets — nothing is inferred"
        icon={<ClipboardList className="size-3.5" />}
        moduleName="Board totals"
        isLoading={isLoading}
        error={error}
        panel={panel}
        emptyLabel="no tickets on the board yet — totals stay unmeasured until one lands"
      >
        <StatGrid>
          <Stat
            label="Tickets"
            value={panel?.available ? count(panel.total) : '—'}
            hint={panel?.available ? `${shown} of ${panel.total} listed below` : panel?.reason}
            icon={<ClipboardList className="size-3.5" />}
          />
          <Stat
            label="Blocked"
            value={panel?.available ? count(panel.blocked) : '—'}
            hint="waiting on an unmet dependency"
            tone={panel?.available && panel.blocked > 0 ? 'deny' : 'default'}
            icon={<Ban className="size-3.5" />}
          />
          <Stat
            label="In review"
            value={panel?.available ? count(panel.in_review) : '—'}
            hint="awaiting a reviewer verdict"
            tone={panel?.available && panel.in_review > 0 ? 'warn' : 'default'}
            icon={<Eye className="size-3.5" />}
          />
          <Stat
            label="P0"
            value={p0 === null ? '—' : count(p0)}
            hint="highest-priority tickets on the board"
            tone={p0 !== null && p0 > 0 ? 'deny' : 'default'}
            icon={<Flame className="size-3.5" />}
          />
        </StatGrid>
      </ModuleCard>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <ModuleCard
          title="Status distribution"
          description="Where the work actually sits right now"
          icon={<Layers className="size-3.5" />}
          moduleName="Board status"
          isLoading={isLoading}
          error={error}
          panel={panel}
          emptyLabel="no tickets on the board yet — there is no status spread to plot"
        >
          <BarList data={distribution(panel?.by_status ?? {}, statusTone)} />
        </ModuleCard>

        <ModuleCard
          title="Priority distribution"
          description="How the backlog is weighted"
          icon={<ListFilter className="size-3.5" />}
          moduleName="Board priority"
          isLoading={isLoading}
          error={error}
          panel={panel}
          emptyLabel="no tickets on the board yet — there is no priority spread to plot"
        >
          <BarList data={distribution(panel?.by_priority ?? {}, () => 'primary')} />
        </ModuleCard>
      </div>

      <ModuleCard
        title="Tickets"
        description="Most recently updated first"
        icon={<ClipboardList className="size-3.5" />}
        moduleName="Board tickets"
        isLoading={isLoading}
        error={error}
        panel={panel}
        emptyLabel="no tickets on the board yet — the queue is genuinely empty, not hidden"
        actions={
          panel?.available ? <Badge variant="outline">top {TICKET_LIMIT}</Badge> : null
        }
        bodyClassName="p-0"
        footer={
          panel?.available
            ? `Showing ${count(shown)} of ${count(panel.total)} tickets`
            : undefined
        }
      >
        <DataTable
          dense
          maxHeight="max-h-[32rem]"
          rowKey={(row, index) => row.id || String(index)}
          rows={panel?.tickets ?? []}
          columns={COLUMNS}
          empty={
            <p className="px-4 py-6 text-center text-xs text-muted-foreground">
              No tickets to list.
            </p>
          }
        />
      </ModuleCard>
    </div>
  )
}
