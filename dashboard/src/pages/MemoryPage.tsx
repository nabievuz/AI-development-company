import { Brain, Database, Gauge, HeartPulse, Info, ScanSearch } from 'lucide-react'
import { ModuleCard } from '@/components/ModuleCard'
import { Badge } from '@/components/ui/badge'
import { Meter } from '@/components/charts'
import { Stat, StatGrid } from '@/components/ui/stat'
import { KeyValue } from '@/components/ui/table'
import { useModuleQuery, SLOW_INTERVAL } from '@/hooks/useModuleQuery'
import { api } from '@/lib/api'
import { count, percent } from '@/lib/utils'
import type { MemoryPanel } from '@/lib/types'

type Band = 'allow' | 'warn' | 'deny'

const BAND_LABEL: Record<Band, string> = {
  allow: 'at or above 80%',
  warn: 'at or above 50%',
  deny: 'below 50%',
}

function healthBand(value: number | undefined): Band | null {
  if (value === undefined || Number.isNaN(value)) return null
  if (value >= 0.8) return 'allow'
  if (value >= 0.5) return 'warn'
  return 'deny'
}

export function MemoryPage() {
  const query = useModuleQuery<MemoryPanel>('memory', (signal) => api.memory(signal), {
    refetchInterval: SLOW_INTERVAL,
  })

  const panel = query.data
  const isLoading = query.isLoading
  const error = query.isError ? query.error : undefined

  const total = panel?.total
  const recallable = panel?.recallable
  const health = panel?.health

  const recallRate =
    total !== undefined && recallable !== undefined && total > 0 ? recallable / total : null
  const unrecallable =
    total !== undefined && recallable !== undefined ? total - recallable : undefined
  const band = healthBand(health)

  const reported: { field: string; present: boolean }[] = [
    { field: 'total', present: total !== undefined },
    { field: 'recallable', present: recallable !== undefined },
    { field: 'health', present: health !== undefined },
  ]

  return (
    <div className="space-y-4">
      <ModuleCard
        title="Memory store"
        description="What the control plane reports about the persisted memory the agents read back"
        icon={<Brain className="size-3.5" aria-hidden="true" />}
        moduleName="Memory totals"
        isLoading={isLoading}
        error={error}
        panel={panel}
        emptyLabel="no memory store is reporting yet"
      >
        <StatGrid>
          <Stat
            label="Memories on file"
            value={total === undefined ? '—' : count(total)}
            hint={total === undefined ? 'total not reported' : 'entries the store holds'}
            tone={total === undefined ? 'nodata' : 'default'}
            icon={<Database className="size-3.5" aria-hidden="true" />}
          />
          <Stat
            label="Recallable"
            value={recallable === undefined ? '—' : count(recallable)}
            hint={
              recallable === undefined
                ? 'recallable count not reported'
                : 'entries a recall query can return'
            }
            tone={recallable === undefined ? 'nodata' : 'default'}
            icon={<ScanSearch className="size-3.5" aria-hidden="true" />}
          />
          <Stat
            label="Recall rate"
            value={percent(recallRate)}
            hint={
              recallRate === null
                ? 'needs both a total and a recallable count'
                : 'recallable ÷ total'
            }
            tone={recallRate === null ? 'nodata' : 'default'}
            icon={<Gauge className="size-3.5" aria-hidden="true" />}
          />
          <Stat
            label="Store health"
            value={percent(health)}
            hint={band === null ? 'health not reported' : BAND_LABEL[band]}
            tone={band ?? 'nodata'}
            icon={<HeartPulse className="size-3.5" aria-hidden="true" />}
          />
        </StatGrid>
      </ModuleCard>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <ModuleCard
          title="Health reading"
          description="The store's own health score, banded for the operator"
          icon={<HeartPulse className="size-3.5" aria-hidden="true" />}
          moduleName="Memory health"
          isLoading={isLoading}
          error={error}
          panel={panel}
          emptyLabel="no health score is being reported"
          actions={
            <Badge variant={band ?? 'nodata'}>
              {band === null ? 'not reported' : BAND_LABEL[band]}
            </Badge>
          }
        >
          <div className="flex items-baseline justify-between gap-3">
            <span className="font-mono text-2xl font-semibold tabular">{percent(health, 1)}</span>
            <span className="font-mono text-[11px] text-muted-foreground">0% — 100%</span>
          </div>
          <div className="mt-2">
            <Meter value={health ?? null} label="memory store health" tone={band ?? 'primary'} />
          </div>
          <p className="mt-2 text-[11px] text-muted-foreground">
            Bands: 80% and above reads healthy, 50% and above reads degraded, anything lower reads
            failing.
          </p>
          <div className="mt-3">
            <KeyValue
              items={[
                { label: 'Health score', value: percent(health, 1) },
                { label: 'Recall rate', value: percent(recallRate, 1) },
                { label: 'Recallable', value: recallable === undefined ? '—' : count(recallable) },
                {
                  label: 'Not recallable',
                  value: unrecallable === undefined ? '—' : count(unrecallable),
                },
              ]}
            />
          </div>
        </ModuleCard>

        <ModuleCard
          title="Store provenance"
          description="Why these numbers look the way they do, in the control plane's own words"
          icon={<Info className="size-3.5" aria-hidden="true" />}
          moduleName="Memory provenance"
          isLoading={isLoading}
          error={error}
          panel={panel}
          emptyLabel="the control plane returned no note about the memory store"
        >
          <p className="rounded-md border border-dashed border-border px-3 py-2 text-xs text-muted-foreground">
            {panel?.reason
              ? panel.reason
              : 'The control plane returned no note alongside this panel.'}
          </p>
          <p className="mt-3 text-[11px] uppercase tracking-wide text-muted-foreground">
            Fields returned
          </p>
          <div className="mt-1.5 flex flex-wrap gap-1.5">
            {reported.map((entry) => (
              <Badge key={entry.field} variant={entry.present ? 'allow' : 'nodata'}>
                {entry.field}
              </Badge>
            ))}
          </div>
          <p className="mt-3 text-[11px] text-muted-foreground">
            Absent fields are left blank rather than shown as zero — a missing measurement is not a
            measurement of nothing.
          </p>
        </ModuleCard>
      </div>
    </div>
  )
}
