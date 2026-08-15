import { useMemo } from 'react'
import { Flag, Percent, ToggleLeft, ToggleRight } from 'lucide-react'
import { ModuleCard } from '@/components/ModuleCard'
import { Badge } from '@/components/ui/badge'
import { Stat, StatGrid } from '@/components/ui/stat'
import { DataTable } from '@/components/ui/table'
import { useModuleQuery, SLOW_INTERVAL } from '@/hooks/useModuleQuery'
import { api } from '@/lib/api'
import { count, percent } from '@/lib/utils'
import type { FlagRow, FlagsPanel } from '@/lib/types'

function FlagList({ flags, empty }: { flags: FlagRow[]; empty: string }) {
  if (flags.length === 0) {
    return <p className="py-6 text-center text-xs text-muted-foreground">{empty}</p>
  }
  return (
    <ul className="space-y-1">
      {flags.map((row) => (
        <li
          key={row.flag}
          className="flex items-center justify-between gap-3 rounded-md border border-border/70 px-2.5 py-1.5"
        >
          <span className="min-w-0 truncate font-mono text-xs">{row.flag}</span>
          <Badge variant={row.enabled ? 'allow' : 'neutral'}>{row.enabled ? 'on' : 'off'}</Badge>
        </li>
      ))}
    </ul>
  )
}

export function FlagsPage() {
  const query = useModuleQuery<FlagsPanel>('flags', (signal) => api.flags(signal), {
    refetchInterval: SLOW_INTERVAL,
  })

  const panel = query.data
  const available = panel?.available === true
  const rows = useMemo(() => panel?.flags ?? [], [panel?.flags])
  const enabledRows = useMemo(() => rows.filter((row) => row.enabled), [rows])
  const disabledRows = useMemo(() => rows.filter((row) => !row.enabled), [rows])

  const total = panel?.total ?? 0
  const enabled = panel?.enabled ?? 0
  const share = available && total > 0 ? enabled / total : null

  return (
    <div className="space-y-4">
      <StatGrid>
        <Stat
          label="Flags declared"
          value={available ? count(total) : '—'}
          hint={available ? 'runtime switches the engine reads' : panel?.reason}
          tone={available ? 'default' : 'nodata'}
          icon={<Flag className="size-3.5" aria-hidden="true" />}
        />
        <Stat
          label="Enabled"
          value={available ? count(enabled) : '—'}
          hint={available ? 'capabilities the engine may exercise' : undefined}
          tone={available ? 'allow' : 'nodata'}
          icon={<ToggleRight className="size-3.5" aria-hidden="true" />}
        />
        <Stat
          label="Disabled"
          value={available ? count(total - enabled) : '—'}
          hint={available ? 'switched off — the engine must not use these' : undefined}
          tone={available ? 'default' : 'nodata'}
          icon={<ToggleLeft className="size-3.5" aria-hidden="true" />}
        />
        <Stat
          label="Enabled share"
          value={percent(share)}
          hint={available ? `${count(enabled)} of ${count(total)}` : undefined}
          tone={share === null ? 'nodata' : 'default'}
          icon={<Percent className="size-3.5" aria-hidden="true" />}
        />
      </StatGrid>

      <ModuleCard
        title="Runtime feature flags"
        description="Flag names are code identifiers, shown verbatim as the control plane reports them"
        icon={<Flag className="size-3.5" aria-hidden="true" />}
        moduleName="Flags"
        isLoading={query.isLoading}
        error={query.isError ? query.error : undefined}
        panel={panel}
        emptyLabel="flag state is unavailable at your tier"
        actions={
          available ? (
            <Badge variant="info">
              {count(enabled)} on · {count(total - enabled)} off
            </Badge>
          ) : null
        }
        bodyClassName="p-0"
      >
        <DataTable
          rowKey={(row) => row.flag}
          rows={rows}
          maxHeight="max-h-[28rem]"
          empty={
            <p className="px-4 py-6 text-center text-xs text-muted-foreground">
              The control plane reports no flags.
            </p>
          }
          columns={[
            { key: 'flag', header: 'Flag', cell: (row: FlagRow) => row.flag, mono: true },
            {
              key: 'state',
              header: 'State',
              align: 'right',
              width: '6rem',
              cell: (row: FlagRow) => (
                <Badge variant={row.enabled ? 'allow' : 'neutral'}>
                  {row.enabled ? 'on' : 'off'}
                </Badge>
              ),
            },
          ]}
        />
      </ModuleCard>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <ModuleCard
          title="Enabled"
          description="Every capability currently switched on"
          icon={<ToggleRight className="size-3.5" aria-hidden="true" />}
          moduleName="Enabled flags"
          isLoading={query.isLoading}
          error={query.isError ? query.error : undefined}
          panel={panel}
          emptyLabel="flag state is unavailable at your tier"
        >
          <FlagList flags={enabledRows} empty="No flag is enabled." />
        </ModuleCard>

        <ModuleCard
          title="Disabled"
          description="Declared but switched off — the engine must behave as if absent"
          icon={<ToggleLeft className="size-3.5" aria-hidden="true" />}
          moduleName="Disabled flags"
          isLoading={query.isLoading}
          error={query.isError ? query.error : undefined}
          panel={panel}
          emptyLabel="flag state is unavailable at your tier"
        >
          <FlagList flags={disabledRows} empty="Every declared flag is enabled." />
        </ModuleCard>
      </div>
    </div>
  )
}
