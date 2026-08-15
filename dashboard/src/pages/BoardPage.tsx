import { Ban, ClipboardList, Eye, Flame, FolderGit2, Layers, ListFilter, ShieldCheck } from 'lucide-react'
import { ModuleCard } from '@/components/ModuleCard'
import { Badge, StatusBadge, type BadgeProps } from '@/components/ui/badge'
import { Stat, StatGrid } from '@/components/ui/stat'
import { BarList, type BarDatum } from '@/components/charts'
import { DataTable, type Column } from '@/components/ui/table'
import { useModuleQuery, SLOW_INTERVAL } from '@/hooks/useModuleQuery'
import { api } from '@/lib/api'
import { count, relativeTime, titleCase } from '@/lib/utils'
import type { BoardPanel, GoalBreakdown, ProjectBoard, TicketRow } from '@/lib/types'

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

const PROJECT_COLUMNS: Column<TicketRow>[] = [
  { key: 'id', header: 'Ticket', cell: (row) => row.id, mono: true, width: '12%' },
  {
    key: 'title',
    header: 'Title',
    cell: (row) => <span className="block truncate">{row.title || '—'}</span>,
  },
  {
    key: 'goal',
    header: 'Goal',
    cell: (row) => (row.goal ? <Badge variant="outline">{row.goal}</Badge> : '—'),
  },
  {
    key: 'stage',
    header: 'Gate',
    cell: (row) => (row.stage ? <Badge variant="info">{row.stage}</Badge> : <Badge variant="neutral">epic</Badge>),
  },
  { key: 'status', header: 'Status', cell: (row) => <StatusBadge status={row.status} /> },
  { key: 'assignee', header: 'Assignee', cell: (row) => row.assignee || '—', mono: true },
]

function GateRibbon({ goal }: { goal: GoalBreakdown }) {
  if (goal.stages.length === 0) return <span className="text-[11px] text-nodata">no staged tickets</span>
  return (
    <div className="flex flex-wrap gap-1">
      {goal.stages.map((stage) => (
        <span
          key={stage.gate}
          title={`${stage.gate} — ${stage.closed ? 'closed' : 'open'} (${stage.tickets.join(', ')})`}
          className={
            stage.closed
              ? 'rounded border border-transparent bg-allow/15 px-1.5 py-0.5 font-mono text-[10px] text-allow'
              : 'rounded border border-dashed border-nodata/50 px-1.5 py-0.5 font-mono text-[10px] text-nodata'
          }
        >
          {stage.gate.replace('GATE-', 'G')}
        </span>
      ))}
    </div>
  )
}

function ProjectSection({ project }: { project: ProjectBoard }) {
  return (
    <div className="space-y-4">
      <ModuleCard
        title={project.slug}
        description={`Compiled board at ${project.path} — one epic plus six AADL stage tickets per goal`}
        icon={<FolderGit2 className="size-3.5" />}
        moduleName={`Project ${project.slug}`}
        panel={{ available: true, reason: '' }}
        actions={
          <div className="flex gap-1">
            <Badge variant="outline">{count(project.total)} tickets</Badge>
            <Badge variant={project.open_gates > 0 ? 'warn' : 'allow'}>
              {count(project.open_gates)} open gates
            </Badge>
          </div>
        }
      >
        <StatGrid>
          <Stat label="Goals" value={count(project.goals.length)} hint="Founder-approved queue items" />
          <Stat
            label="Open gates"
            value={count(project.open_gates)}
            hint="each needs a Founder sign-off"
            tone={project.open_gates > 0 ? 'warn' : 'allow'}
            icon={<ShieldCheck className="size-3.5" />}
          />
          <Stat
            label="Done"
            value={count(project.done)}
            hint="stage tickets closed"
            tone={project.done > 0 ? 'allow' : 'nodata'}
          />
          <Stat
            label="Blocked"
            value={count(project.blocked)}
            hint="waiting on a dependency"
            tone={project.blocked > 0 ? 'deny' : 'default'}
            icon={<Ban className="size-3.5" />}
          />
        </StatGrid>

        <div className="mt-4 space-y-2">
          {project.goals.map((goal) => (
            <div
              key={goal.goal}
              className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-border/70 px-3 py-2"
            >
              <div className="min-w-0">
                <p className="truncate text-xs font-medium">{goal.goal}</p>
                <p className="font-mono text-[11px] text-muted-foreground">
                  {goal.epic || '—'} · {count(goal.total)} tickets
                </p>
              </div>
              <GateRibbon goal={goal} />
            </div>
          ))}
        </div>
      </ModuleCard>

      <ModuleCard
        title={`${project.slug} — tickets`}
        description="Compiled from the approved goal queue, not hand-written"
        icon={<ClipboardList className="size-3.5" />}
        moduleName={`Project tickets ${project.slug}`}
        panel={{ available: true, reason: '' }}
        bodyClassName="p-0"
        footer={`${count(project.tickets.length)} of ${count(project.total)} listed`}
      >
        <DataTable
          dense
          maxHeight="max-h-[32rem]"
          rowKey={(row, index) => row.id || String(index)}
          rows={project.tickets}
          columns={PROJECT_COLUMNS}
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

export function BoardPage() {
  const query = useModuleQuery<BoardPanel>('board', (signal) => api.board(TICKET_LIMIT, signal), {
    refetchInterval: SLOW_INTERVAL,
  })

  const panel = query.data
  const projects = query.data?.projects
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

      <ModuleCard
        title="Project boards"
        description="Tickets compiled into projects/<slug>/board-tickets — the org board above is DasLab-platform only"
        icon={<FolderGit2 className="size-3.5" />}
        moduleName="Project boards"
        isLoading={isLoading}
        error={error}
        panel={projects}
        emptyLabel="no project boards — nothing has been compiled through the WS7 gateway yet"
        actions={
          projects?.available ? (
            <Badge variant="outline">
              {count(projects.project_count ?? 0)} project · {count(projects.total ?? 0)} tickets
            </Badge>
          ) : null
        }
        bodyClassName="p-0"
      >
        <div className="space-y-4 p-4">
          {(projects?.projects ?? []).map((project) => (
            <ProjectSection key={project.slug} project={project} />
          ))}
        </div>
      </ModuleCard>
    </div>
  )
}
