import { Link } from 'react-router-dom'
import {
  Activity,
  Banknote,
  ClipboardList,
  Flag,
  Inbox,
  ListTree,
  ScrollText,
  TrendingUp,
} from 'lucide-react'
import { ModuleCard } from '@/components/ModuleCard'
import { Badge, DecisionBadge, TierBadge } from '@/components/ui/badge'
import { Stat, StatGrid } from '@/components/ui/stat'
import { BarList, DeltaDot, Meter, Sparkline } from '@/components/charts'
import { DataTable } from '@/components/ui/table'
import { ErrorNotice, PanelSkeleton } from '@/components/ui/feedback'
import { useModuleQuery, SLOW_INTERVAL } from '@/hooks/useModuleQuery'
import { api } from '@/lib/api'
import { useSession } from '@/stores/session'
import { count, percent, relativeTime, usd } from '@/lib/utils'
import type { HealthTrack, InterruptCard, Panel, SummaryResponse } from '@/lib/types'

const OUT_OF_SCOPE = 'not available at your tier'

function statValue(panel: Panel | undefined, render: () => string): string {
  if (!panel) return '—'
  if (!panel.available) return '0'
  return render()
}

function statHint(panel: Panel | undefined, render: () => string): string {
  if (!panel) return OUT_OF_SCOPE
  if (!panel.available) return panel.reason
  return render()
}

function trackValue(track: HealthTrack): string {
  if (!track.available) return '—'
  if (track.value === null) return 'intact'
  if (track.unit === 'ratio') return percent(track.value)
  return track.value.toFixed(1)
}

export function OverviewPage() {
  const identity = useSession((state) => state.identity)
  const query = useModuleQuery<SummaryResponse>('summary', (signal) => api.summary(signal), {
    refetchInterval: SLOW_INTERVAL,
  })

  if (query.isLoading) return <PanelSkeleton rows={6} />
  if (query.isError) return <ErrorNotice error={query.error} />

  const panels = query.data?.panels ?? {}
  const org = panels.org
  const board = panels.board
  const waves = panels.waves
  const interrupts = panels.interrupts
  const flags = panels.flags
  const metrics = panels.metrics
  const cost = panels.cost
  const throughput = panels.throughput
  const audit = panels.audit

  const pending = interrupts?.available ? interrupts.cards.filter((card) => !card.expired) : []
  const enabledFlags = flags?.available ? flags.flags.filter((flag) => flag.enabled) : []

  return (
    <div className="space-y-4">
      <section className="rounded-lg border border-border bg-surface px-4 py-3">
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
          <div className="flex items-center gap-2">
            <span className="text-xs text-muted-foreground">Acting as</span>
            {identity ? <TierBadge tier={identity.tier} /> : null}
            <span className="font-mono text-xs">{identity?.principal}</span>
          </div>
          {identity?.role ? (
            <Badge variant="outline">role: {identity.role}</Badge>
          ) : null}
          {identity?.department ? (
            <Badge variant="outline">dept: {identity.department}</Badge>
          ) : null}
          <Badge variant="info">{identity?.modules.length ?? 0} modules visible</Badge>
          {identity && identity.actions.length === 0 ? (
            <Badge variant="nodata">read-only</Badge>
          ) : (
            <Badge variant="warn">{identity?.actions.length} founder actions</Badge>
          )}
        </div>
      </section>

      <StatGrid>
        <Stat
          label="Org roles"
          value={statValue(org, () => count(org?.totals.roles))}
          hint={statHint(org, () => `${org?.totals.departments} departments`)}
          tone={org ? 'default' : 'nodata'}
          icon={<ListTree className="size-3.5" />}
        />
        <Stat
          label="Board tickets"
          value={statValue(board, () => count(board?.total))}
          hint={statHint(board, () => `${board?.blocked} blocked · ${board?.in_review} in review`)}
          tone={!board ? 'nodata' : board.available && board.blocked > 0 ? 'deny' : 'default'}
          icon={<ClipboardList className="size-3.5" />}
        />
        <Stat
          label="Pending decisions"
          value={statValue(interrupts, () => count(pending.length))}
          hint={statHint(
            interrupts,
            () => `${interrupts?.answerable} answerable · ${interrupts?.schema_divergent} off-schema`,
          )}
          tone={!interrupts ? 'nodata' : pending.length > 0 ? 'warn' : 'default'}
          icon={<Inbox className="size-3.5" />}
        />
        <Stat
          label="Waves"
          value={statValue(waves, () => count(waves?.total))}
          hint={statHint(
            waves,
            () => `${waves?.dispatched_total} dispatched · ${waves?.idle_waves} idle`,
          )}
          tone={waves ? 'default' : 'nodata'}
          icon={<Activity className="size-3.5" />}
        />
      </StatGrid>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
        <div className="xl:col-span-2">
          <ModuleCard
            title="Health tracks T1–T7"
            description="Computed from the live event store — never fabricated"
            icon={<TrendingUp className="size-3.5" />}
            moduleName="Metrics"
            panel={metrics}
            emptyLabel="metrics are unavailable at your tier"
            actions={
              metrics?.available && metrics.degraded.length > 0 ? (
                <Badge variant="nodata">{metrics.degraded.length} without data</Badge>
              ) : null
            }
          >
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              {(metrics?.tracks ?? []).map((track) => (
                <div key={track.code} className="rounded-md border border-border/70 px-3 py-2">
                  <div className="flex items-baseline justify-between gap-2">
                    <div className="min-w-0">
                      <span className="font-mono text-[11px] text-muted-foreground">
                        {track.code}
                      </span>
                      <p className="truncate text-xs">{track.title}</p>
                    </div>
                    <span
                      className={
                        track.available
                          ? 'font-mono text-sm tabular'
                          : 'font-mono text-sm tabular text-nodata'
                      }
                    >
                      {trackValue(track)}
                    </span>
                  </div>
                  <div className="mt-2">
                    <Meter
                      value={track.available && track.unit === 'ratio' ? track.value : null}
                      label={track.title}
                    />
                  </div>
                  {!track.available ? (
                    <p className="mt-1 truncate text-[11px] text-nodata">{track.reason}</p>
                  ) : null}
                </div>
              ))}
            </div>
          </ModuleCard>
        </div>

        <div className="space-y-4">
          <ModuleCard
            title="Throughput trend"
            icon={<TrendingUp className="size-3.5" />}
            moduleName="Throughput"
            panel={throughput}
            emptyLabel="trend needs more completed runs (P5 trends are trigger-gated)"
          >
            <div className="flex items-center gap-2">
              <DeltaDot direction={throughput?.direction ?? 'insufficient'} />
              <span className="text-xs capitalize">{throughput?.direction}</span>
            </div>
            <Sparkline values={throughput?.series ?? []} ariaLabel="throughput trend" />
          </ModuleCard>

          <ModuleCard
            title="Budget burn"
            icon={<Banknote className="size-3.5" />}
            moduleName="Cost"
            panel={cost}
            emptyLabel="no priced spans recorded yet"
          >
            <Stat
              label="Estimated spend"
              value={usd(cost?.totals?.estimated_cost_usd)}
              hint={`${count(cost?.totals?.spans)} spans`}
            />
            <div className="mt-3">
              <BarList
                data={(cost?.by_tier ?? []).map((group) => ({
                  label: group.key,
                  value: group.estimated_cost_usd,
                  hint: usd(group.estimated_cost_usd),
                }))}
              />
            </div>
          </ModuleCard>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <ModuleCard
          title="Action console"
          description="Interrupt cards awaiting a Founder answer"
          icon={<Inbox className="size-3.5" />}
          moduleName="Action console"
          panel={interrupts}
          emptyLabel="no pending interrupt-cards"
          actions={<Link to="/interrupts" className="text-xs text-primary hover:underline">Open</Link>}
        >
          <ul className="space-y-2">
            {pending.slice(0, 4).map((card: InterruptCard) => (
              <li key={card.id} className="rounded-md border border-border/70 px-3 py-2">
                <div className="flex items-start justify-between gap-2">
                  <p className="min-w-0 flex-1 truncate text-xs font-medium">{card.question}</p>
                  {card.schema_valid ? (
                    <Badge variant="allow">valid</Badge>
                  ) : (
                    <Badge variant="warn">off-schema</Badge>
                  )}
                </div>
                <p className="mt-1 font-mono text-[11px] text-muted-foreground">
                  {card.id}
                  {card.ticket ? ` · ${card.ticket}` : ''}
                </p>
              </li>
            ))}
          </ul>
        </ModuleCard>

        <ModuleCard
          title="Recent access decisions"
          description="Every read is attributed and audited"
          icon={<ScrollText className="size-3.5" />}
          moduleName="Audit"
          panel={audit}
          emptyLabel="no control-plane audit entries yet"
          actions={<Link to="/audit" className="text-xs text-primary hover:underline">Open</Link>}
          bodyClassName="p-0"
        >
          <DataTable
            dense
            rowKey={(_row, index) => String(index)}
            rows={(audit?.entries ?? []).slice(0, 8)}
            columns={[
              { key: 'when', header: 'When', cell: (row) => relativeTime(row.ts) },
              { key: 'action', header: 'Action', cell: (row) => row.action ?? '—', mono: true },
              {
                key: 'principal',
                header: 'Principal',
                cell: (row) => row.principal_id ?? '—',
                mono: true,
              },
              {
                key: 'decision',
                header: 'Decision',
                align: 'right',
                cell: (row) => <DecisionBadge decision={row.decision ?? ''} />,
              },
            ]}
          />
        </ModuleCard>
      </div>

      <ModuleCard
        title="Runtime posture"
        description="Feature flags decide what the engine may do"
        icon={<Flag className="size-3.5" />}
        moduleName="Flags"
        panel={flags}
        emptyLabel="flag state is unavailable at your tier"
      >
        <div className="flex flex-wrap gap-1.5">
          {(flags?.flags ?? []).map((flag) => (
            <Badge key={flag.flag} variant={flag.enabled ? 'allow' : 'neutral'}>
              {flag.flag}
            </Badge>
          ))}
        </div>
        <p className="mt-2 text-xs text-muted-foreground">
          {enabledFlags.length} of {flags?.total ?? 0} flags enabled
        </p>
      </ModuleCard>
    </div>
  )
}
