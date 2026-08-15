import { useMemo } from 'react'
import type { ReactNode } from 'react'
import {
  BarChart3,
  CheckCircle2,
  PauseCircle,
  ScrollText,
  SlidersHorizontal,
  Undo2,
  XCircle,
} from 'lucide-react'
import { ModuleCard } from '@/components/ModuleCard'
import { Badge, type BadgeProps } from '@/components/ui/badge'
import { Stat, StatGrid } from '@/components/ui/stat'
import { BarList, type BarDatum } from '@/components/charts'
import { DataTable, type Column } from '@/components/ui/table'
import { useModuleQuery, SLOW_INTERVAL } from '@/hooks/useModuleQuery'
import { api } from '@/lib/api'
import { count, titleCase } from '@/lib/utils'
import type { Gate6Panel } from '@/lib/types'

type GateRecord = NonNullable<Gate6Panel['records']>[number]

type StatTone = 'default' | 'allow' | 'deny' | 'warn'

interface CountMeta {
  key: string
  hint: string
  tone: StatTone
  icon: ReactNode
}

const COUNT_META: CountMeta[] = [
  {
    key: 'applied',
    hint: 'tuning landed in the rubric',
    tone: 'allow',
    icon: <CheckCircle2 className="size-3.5" aria-hidden="true" />,
  },
  {
    key: 'reverted',
    hint: 'rolled back after landing',
    tone: 'warn',
    icon: <Undo2 className="size-3.5" aria-hidden="true" />,
  },
  {
    key: 'deferred',
    hint: 'held for a later pass',
    tone: 'default',
    icon: <PauseCircle className="size-3.5" aria-hidden="true" />,
  },
  {
    key: 'failed',
    hint: 'the gate refused the change',
    tone: 'deny',
    icon: <XCircle className="size-3.5" aria-hidden="true" />,
  },
]

const BAR_TONE: Record<string, BarDatum['tone']> = {
  applied: 'allow',
  reverted: 'warn',
  deferred: 'info',
  failed: 'deny',
}

const STATUS_VARIANT: Record<string, BadgeProps['variant']> = {
  applied: 'allow',
  reverted: 'warn',
  deferred: 'info',
  failed: 'deny',
}

const RECORD_COLUMNS: Column<GateRecord>[] = [
  { key: 'file', header: 'File', cell: (row) => row.file || '—', mono: true },
  {
    key: 'status',
    header: 'Status',
    cell: (row) => <Badge variant={STATUS_VARIANT[row.status] ?? 'neutral'}>{row.status || '—'}</Badge>,
  },
  { key: 'change_type', header: 'Change type', cell: (row) => row.change_type || '—' },
]

export function GatesPage() {
  const query = useModuleQuery<Gate6Panel>('gates', (signal) => api.gates(signal), {
    refetchInterval: SLOW_INTERVAL,
  })

  const panel = query.data
  const records = panel?.records ?? []

  const distribution = useMemo<BarDatum[]>(
    () =>
      Object.entries(panel?.counts ?? {}).map(([key, value]) => ({
        label: titleCase(key),
        value,
        hint: count(value),
        tone: BAR_TONE[key] ?? 'primary',
      })),
    [panel?.counts],
  )

  return (
    <div className="space-y-4">
      <ModuleCard
        title="GATE-6 tuning decisions"
        description="What the tuning loop did to the rubric, exactly as the gate recorded it"
        icon={<SlidersHorizontal className="size-3.5" aria-hidden="true" />}
        moduleName="Gate 6 decisions"
        isLoading={query.isLoading}
        error={query.isError ? query.error : undefined}
        panel={panel}
        emptyLabel="the tuning loop has written no GATE-6 decisions"
        bodyClassName="space-y-4 p-4"
      >
        <StatGrid>
          {COUNT_META.map((meta) => (
            <Stat
              key={meta.key}
              label={titleCase(meta.key)}
              value={count(panel?.counts?.[meta.key])}
              hint={meta.hint}
              tone={meta.tone}
              icon={meta.icon}
            />
          ))}
          <Stat
            label="Tuning events"
            value={count(panel?.tuning_events)}
            hint="proposals the loop considered"
            icon={<ScrollText className="size-3.5" aria-hidden="true" />}
          />
        </StatGrid>
      </ModuleCard>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
        <ModuleCard
          title="Decision mix"
          description="Every counter the gate reports, none inferred"
          icon={<BarChart3 className="size-3.5" aria-hidden="true" />}
          moduleName="Gate 6 mix"
          isLoading={query.isLoading}
          error={query.isError ? query.error : undefined}
          panel={panel}
          emptyLabel="no decision counters to distribute"
        >
          <BarList data={distribution} />
        </ModuleCard>

        <div className="xl:col-span-2">
          <ModuleCard
            title="Tuning records"
            description="Per-file verdicts behind the counters"
            icon={<ScrollText className="size-3.5" aria-hidden="true" />}
            moduleName="Gate 6 records"
            isLoading={query.isLoading}
            error={query.isError ? query.error : undefined}
            panel={panel}
            emptyLabel="no per-file tuning records on file"
            actions={
              panel?.available && panel.records ? (
                <Badge variant="outline">{count(records.length)} records</Badge>
              ) : null
            }
            bodyClassName="p-0"
          >
            <DataTable
              dense
              maxHeight="max-h-[28rem]"
              rowKey={(row, index) => `${row.file}::${index}`}
              rows={records}
              columns={RECORD_COLUMNS}
              empty={
                <p className="py-6 text-center text-xs text-muted-foreground">
                  The gate reported counters without per-file records.
                </p>
              }
            />
          </ModuleCard>
        </div>
      </div>
    </div>
  )
}
