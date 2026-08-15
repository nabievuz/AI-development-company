import { useMemo } from 'react'
import { ClipboardCheck, FileDiff, Gauge, Lock } from 'lucide-react'
import { ModuleCard } from '@/components/ModuleCard'
import { Badge, type BadgeProps } from '@/components/ui/badge'
import { Stat, StatGrid } from '@/components/ui/stat'
import { Meter } from '@/components/charts'
import { DataTable, type Column } from '@/components/ui/table'
import { useModuleQuery, SLOW_INTERVAL } from '@/hooks/useModuleQuery'
import { api } from '@/lib/api'
import { count, decimal, percent, titleCase } from '@/lib/utils'
import type { Gate6Panel, HealthTrack, QualityResponse } from '@/lib/types'

type GateRecord = NonNullable<Gate6Panel['records']>[number]

const FOCUS_CODES = ['T6', 'T7']
const RUBRIC_CODE = 'T7'
const RUBRIC_FLAGS = ['immutable', 'hard_blocker'] as const
const COUNT_KEYS = ['applied', 'reverted', 'deferred', 'failed'] as const

const GATE_STATUS_VARIANT: Record<string, BadgeProps['variant']> = {
  applied: 'allow',
  reverted: 'warn',
  deferred: 'info',
  failed: 'deny',
}

interface RubricFlag {
  key: string
  label: string
  variant: BadgeProps['variant']
}

function trackValue(track: HealthTrack): string {
  if (!track.available) return '—'
  if (track.value === null) return 'intact'
  if (track.unit === 'ratio') return percent(track.value)
  return decimal(track.value)
}

function trackUnit(track: HealthTrack): string | undefined {
  if (!track.available || track.value === null) return undefined
  if (!track.unit || track.unit === 'ratio') return undefined
  return track.unit
}

function meterValue(track: HealthTrack): number | null {
  return track.available && track.unit === 'ratio' ? track.value : null
}

function rubricFlags(detail: Record<string, unknown>): RubricFlag[] {
  const flags: RubricFlag[] = []
  for (const key of RUBRIC_FLAGS) {
    const raw = detail[key]
    if (typeof raw === 'boolean') {
      flags.push({
        key,
        label: `${titleCase(key)}: ${raw ? 'yes' : 'no'}`,
        variant: raw ? 'info' : 'neutral',
      })
    } else if (typeof raw === 'string' && raw.length > 0) {
      flags.push({ key, label: `${titleCase(key)}: ${raw}`, variant: 'info' })
    } else if (typeof raw === 'number') {
      flags.push({ key, label: `${titleCase(key)}: ${decimal(raw)}`, variant: 'info' })
    }
  }
  return flags
}

function TrackRow({ track }: { track: HealthTrack }) {
  const focused = FOCUS_CODES.includes(track.code)
  const flags = track.code === RUBRIC_CODE ? rubricFlags(track.detail) : []
  const unit = trackUnit(track)
  return (
    <li
      className={
        focused
          ? 'rounded-md border border-primary/40 bg-primary/5 px-3 py-2'
          : 'rounded-md border border-border/70 px-3 py-2'
      }
    >
      <div className="flex items-baseline justify-between gap-3">
        <div className="min-w-0">
          <span className="font-mono text-[11px] text-muted-foreground">{track.code}</span>
          <p className="truncate text-xs">{track.title}</p>
        </div>
        <div className="flex shrink-0 items-baseline gap-1.5">
          <span
            className={
              track.available
                ? 'font-mono text-sm tabular'
                : 'font-mono text-sm tabular text-nodata'
            }
          >
            {trackValue(track)}
          </span>
          {unit ? <span className="text-[11px] text-muted-foreground">{unit}</span> : null}
        </div>
      </div>
      <div className="mt-2">
        <Meter value={meterValue(track)} label={`${track.code} ${track.title}`} />
      </div>
      {flags.length > 0 ? (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {flags.map((flag) => (
            <Badge key={flag.key} variant={flag.variant}>
              <Lock className="size-2.5" aria-hidden="true" />
              {flag.label}
            </Badge>
          ))}
        </div>
      ) : null}
      {!track.available ? <p className="mt-1.5 text-[11px] text-nodata">{track.reason}</p> : null}
    </li>
  )
}

export function QualityPage() {
  const query = useModuleQuery<QualityResponse>('quality', (signal) => api.quality(signal), {
    refetchInterval: SLOW_INTERVAL,
  })

  const tracksPanel = query.data?.tracks
  const gatePanel = query.data?.gate6

  const tracks = useMemo(() => tracksPanel?.tracks ?? [], [tracksPanel?.tracks])
  const focusTracks = useMemo(
    () => tracks.filter((track) => FOCUS_CODES.includes(track.code)),
    [tracks],
  )
  const extraCounts = useMemo(
    () =>
      Object.entries(gatePanel?.counts ?? {}).filter(
        ([key]) => !COUNT_KEYS.includes(key as (typeof COUNT_KEYS)[number]),
      ),
    [gatePanel?.counts],
  )

  const recordColumns: Column<GateRecord>[] = [
    { key: 'file', header: 'File', cell: (row) => row.file, mono: true },
    {
      key: 'status',
      header: 'Status',
      cell: (row) => (
        <Badge variant={GATE_STATUS_VARIANT[row.status] ?? 'neutral'}>{row.status || '—'}</Badge>
      ),
    },
    { key: 'change', header: 'Change type', cell: (row) => row.change_type || '—' },
  ]

  return (
    <div className="space-y-4">
      <ModuleCard
        title="Quality health tracks"
        description="Review efficiency and rubric enforcement, computed from the live event store"
        icon={<Gauge className="size-3.5" aria-hidden="true" />}
        moduleName="Quality tracks"
        isLoading={query.isLoading}
        error={query.isError ? query.error : undefined}
        panel={tracksPanel}
        emptyLabel="quality tracks are unavailable at your tier"
        actions={
          tracksPanel?.available && tracksPanel.degraded.length > 0 ? (
            <Badge variant="nodata">{count(tracksPanel.degraded.length)} without data</Badge>
          ) : null
        }
        bodyClassName="space-y-4 p-4"
        footer={
          tracksPanel?.available
            ? `${count(tracksPanel.events)} events · ${count(tracksPanel.waves)} waves behind these tracks`
            : undefined
        }
      >
        {focusTracks.length > 0 ? (
          <StatGrid cols={2}>
            {focusTracks.map((track) => (
              <Stat
                key={track.code}
                label={`${track.code} · ${track.title}`}
                value={trackValue(track)}
                hint={track.available ? trackUnit(track) : track.reason}
                tone={track.available ? 'default' : 'nodata'}
                icon={<ClipboardCheck className="size-3.5" aria-hidden="true" />}
              />
            ))}
          </StatGrid>
        ) : null}

        {tracks.length === 0 ? (
          <p className="py-6 text-center text-xs text-muted-foreground">
            The track computer returned no tracks.
          </p>
        ) : (
          <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            {tracks.map((track) => (
              <TrackRow key={track.code} track={track} />
            ))}
          </ul>
        )}
      </ModuleCard>

      <ModuleCard
        title="Gate 6 rubric ledger"
        description="Every rubric verdict the engine wrote, exactly as recorded"
        icon={<FileDiff className="size-3.5" aria-hidden="true" />}
        moduleName="Gate 6"
        isLoading={query.isLoading}
        error={query.isError ? query.error : undefined}
        panel={gatePanel}
        emptyLabel="no gate 6 records on file"
        bodyClassName="space-y-4 p-4"
      >
        <StatGrid>
          {COUNT_KEYS.map((key) => (
            <Stat
              key={key}
              label={titleCase(key)}
              value={count(gatePanel?.counts?.[key])}
              tone={key === 'failed' ? 'deny' : key === 'reverted' ? 'warn' : 'default'}
            />
          ))}
          <Stat
            label="Tuning events"
            value={count(gatePanel?.tuning_events)}
            hint="rubric threshold adjustments"
            icon={<Lock className="size-3.5" aria-hidden="true" />}
          />
        </StatGrid>

        {extraCounts.length > 0 ? (
          <div className="flex flex-wrap gap-1.5">
            {extraCounts.map(([key, value]) => (
              <Badge key={key} variant="outline">
                {titleCase(key)}: {count(value)}
              </Badge>
            ))}
          </div>
        ) : null}

        <DataTable
          dense
          maxHeight="max-h-96"
          rowKey={(row, index) => `${row.file}::${index}`}
          rows={gatePanel?.records ?? []}
          columns={recordColumns}
          empty={
            <p className="py-6 text-center text-xs text-muted-foreground">
              The rubric ledger lists no per-file records.
            </p>
          }
        />
      </ModuleCard>
    </div>
  )
}
