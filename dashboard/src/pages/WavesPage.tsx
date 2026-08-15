import { useMemo } from 'react'
import { Activity, Layers, Moon, TrendingUp, Waves } from 'lucide-react'
import { ModuleCard } from '@/components/ModuleCard'
import { Badge } from '@/components/ui/badge'
import { Stat, StatGrid } from '@/components/ui/stat'
import { BarList, Sparkline } from '@/components/charts'
import { DataTable } from '@/components/ui/table'
import { useModuleQuery, SLOW_INTERVAL } from '@/hooks/useModuleQuery'
import { api } from '@/lib/api'
import { count, percent, shortTime, titleCase } from '@/lib/utils'
import type { BadgeProps } from '@/components/ui/badge'
import type { WaveRow, WavesPanel } from '@/lib/types'

const WAVE_LIMIT = 60

const MODEL_VARIANT: Record<string, BadgeProps['variant']> = {
  opus: 'info',
  sonnet: 'allow',
  haiku: 'neutral',
}

function modelVariant(model: string): BadgeProps['variant'] {
  return MODEL_VARIANT[model.toLowerCase()] ?? 'outline'
}

function ModelMix({ mix }: { mix: Record<string, number> }) {
  const entries = Object.entries(mix)
  if (entries.length === 0) return <span className="text-xs text-nodata">no mix recorded</span>
  return (
    <div className="flex flex-wrap gap-1">
      {entries.map(([model, dispatched]) => (
        <Badge key={model} variant={modelVariant(model)}>
          {model} · {count(dispatched)}
        </Badge>
      ))}
    </div>
  )
}

export function WavesPage() {
  const query = useModuleQuery<WavesPanel>('waves', (signal) => api.waves(WAVE_LIMIT, signal), {
    refetchInterval: SLOW_INTERVAL,
  })

  const panel = query.data
  const waves = useMemo(() => (panel?.available ? panel.waves : []), [panel])

  const dispatchSeries = useMemo(() => waves.map((wave) => wave.dispatched), [waves])

  const modelTotals = useMemo(() => {
    const totals = new Map<string, number>()
    for (const wave of waves) {
      for (const [model, dispatched] of Object.entries(wave.model_mix)) {
        totals.set(model, (totals.get(model) ?? 0) + dispatched)
      }
    }
    return [...totals.entries()]
      .sort((left, right) => right[1] - left[1])
      .map(([model, dispatched]) => ({
        label: titleCase(model),
        value: dispatched,
        hint: count(dispatched),
      }))
  }, [waves])

  const idleRate = panel?.available && panel.total > 0 ? panel.idle_waves / panel.total : null

  return (
    <div className="space-y-4">
      <ModuleCard
        title="Wave totals"
        description="Every dispatch wave the orchestrator has recorded"
        icon={<Waves className="size-3.5" aria-hidden="true" />}
        moduleName="Wave totals"
        isLoading={query.isLoading}
        error={query.isError ? query.error : undefined}
        panel={panel}
        emptyLabel="no waves recorded"
      >
        <StatGrid>
          <Stat
            label="Waves"
            value={count(panel?.total)}
            hint={`newest ${count(waves.length)} shown below`}
            icon={<Waves className="size-3.5" aria-hidden="true" />}
          />
          <Stat
            label="Dispatched"
            value={count(panel?.dispatched_total)}
            hint="agents launched across all waves"
            icon={<Activity className="size-3.5" aria-hidden="true" />}
          />
          <Stat
            label="Idle waves"
            value={count(panel?.idle_waves)}
            hint="waves that dispatched nothing"
            tone={panel?.idle_waves ? 'warn' : 'default'}
            icon={<Moon className="size-3.5" aria-hidden="true" />}
          />
          <Stat
            label="Idle rate"
            value={percent(idleRate)}
            hint="idle waves over total waves"
            tone={idleRate === null ? 'nodata' : 'default'}
            icon={<TrendingUp className="size-3.5" aria-hidden="true" />}
          />
        </StatGrid>
      </ModuleCard>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
        <div className="xl:col-span-2">
          <ModuleCard
            title="Dispatch rhythm"
            description="Agents dispatched per wave, in the order the control plane returned them"
            icon={<Activity className="size-3.5" aria-hidden="true" />}
            moduleName="Dispatch rhythm"
            isLoading={query.isLoading}
            error={query.isError ? query.error : undefined}
            panel={panel}
            emptyLabel="no waves recorded"
          >
            <Sparkline values={dispatchSeries} ariaLabel="agents dispatched per wave" />
          </ModuleCard>
        </div>

        <ModuleCard
          title="Model mix"
          description="Summed across the waves on file"
          icon={<Layers className="size-3.5" aria-hidden="true" />}
          moduleName="Model mix"
          isLoading={query.isLoading}
          error={query.isError ? query.error : undefined}
          panel={panel}
          emptyLabel="no waves recorded"
        >
          <BarList data={modelTotals} />
        </ModuleCard>
      </div>

      <ModuleCard
        title="Wave timeline"
        description="One row per dispatch wave — an idle wave means the orchestrator woke and launched nothing"
        icon={<Waves className="size-3.5" aria-hidden="true" />}
        moduleName="Wave timeline"
        isLoading={query.isLoading}
        error={query.isError ? query.error : undefined}
        panel={panel}
        emptyLabel="no waves recorded"
        bodyClassName="p-0"
        footer={`${count(waves.length)} of ${count(panel?.total)} waves`}
      >
        <DataTable<WaveRow>
          dense
          maxHeight="max-h-[32rem]"
          rows={waves}
          rowKey={(row, index) => `${row.start}-${index}`}
          columns={[
            { key: 'start', header: 'Start', cell: (row) => shortTime(row.start), mono: true },
            {
              key: 'dispatched',
              header: 'Dispatched',
              align: 'right',
              mono: true,
              width: '7rem',
              cell: (row) => count(row.dispatched),
            },
            { key: 'mix', header: 'Model mix', cell: (row) => <ModelMix mix={row.model_mix} /> },
            {
              key: 'idle',
              header: 'State',
              align: 'right',
              width: '6rem',
              cell: (row) =>
                row.idle ? <Badge variant="nodata">idle</Badge> : <Badge variant="allow">active</Badge>,
            },
          ]}
        />
      </ModuleCard>
    </div>
  )
}
