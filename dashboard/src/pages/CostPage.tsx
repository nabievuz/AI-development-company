import { useMemo } from 'react'
import { AlertTriangle, Banknote, Coins, Layers, Sigma, Ticket, Users } from 'lucide-react'
import { ModuleCard } from '@/components/ModuleCard'
import { Badge } from '@/components/ui/badge'
import { Stat, StatGrid } from '@/components/ui/stat'
import { BarList } from '@/components/charts'
import { DataTable } from '@/components/ui/table'
import { DegradedBanner, NoData } from '@/components/ui/feedback'
import { useModuleQuery, SLOW_INTERVAL } from '@/hooks/useModuleQuery'
import { api } from '@/lib/api'
import { count, percent, usd } from '@/lib/utils'
import type { CostPanel, TokenGroup } from '@/lib/types'

function byCostDescending(groups: TokenGroup[] | undefined): TokenGroup[] {
  return [...(groups ?? [])].sort((left, right) => right.estimated_cost_usd - left.estimated_cost_usd)
}

function GroupBreakdown({
  groups,
  header,
  totalCost,
  emptyLabel,
}: {
  groups: TokenGroup[]
  header: string
  totalCost: number | undefined
  emptyLabel: string
}) {
  if (groups.length === 0) return <NoData reason={emptyLabel} />
  const denominator = totalCost ?? 0
  return (
    <div className="space-y-4">
      <BarList
        data={groups.map((group) => ({
          label: group.key,
          value: group.estimated_cost_usd,
          hint: usd(group.estimated_cost_usd),
        }))}
      />
      <DataTable
        dense
        rows={groups}
        rowKey={(row) => row.key}
        columns={[
          { key: 'key', header, cell: (row) => row.key, mono: true },
          {
            key: 'spans',
            header: 'Spans',
            align: 'right',
            mono: true,
            cell: (row) => count(row.span_count),
          },
          {
            key: 'input',
            header: 'Input + cached',
            align: 'right',
            mono: true,
            cell: (row) => count(row.input_tokens + row.cached_input_tokens),
          },
          {
            key: 'output',
            header: 'Output',
            align: 'right',
            mono: true,
            cell: (row) => count(row.output_tokens),
          },
          {
            key: 'cost',
            header: 'Cost',
            align: 'right',
            mono: true,
            cell: (row) => usd(row.estimated_cost_usd),
          },
          {
            key: 'share',
            header: 'Share',
            align: 'right',
            mono: true,
            cell: (row) =>
              denominator > 0 ? percent(row.estimated_cost_usd / denominator, 1) : '—',
          },
        ]}
      />
    </div>
  )
}

export function CostPage() {
  const query = useModuleQuery<CostPanel>('cost', (signal) => api.cost(signal), {
    refetchInterval: SLOW_INTERVAL,
  })

  const panel = query.data
  const totals = panel?.totals
  const unpricedTiers = panel?.unpriced_tiers ?? []
  const droppedUndated = totals?.dropped_undated ?? 0

  const tiers = useMemo(() => byCostDescending(panel?.by_tier), [panel?.by_tier])
  const agents = useMemo(() => byCostDescending(panel?.by_agent), [panel?.by_agent])
  const tickets = useMemo(() => byCostDescending(panel?.by_ticket), [panel?.by_ticket])

  const error = query.isError ? query.error : undefined

  return (
    <div className="space-y-4">
      <ModuleCard
        title="Budget burn"
        description="Estimated spend reconstructed from priced spans. Unpriced tiers contribute $0 and understate the true figure."
        icon={<Banknote className="size-3.5" />}
        moduleName="Cost totals"
        isLoading={query.isLoading}
        error={error}
        panel={panel}
        emptyLabel="cost accounting is restricted to CXO tier and above"
        bodyClassName="space-y-3"
      >
        {totals ? (
          <>
            <StatGrid>
              <Stat
                label="Estimated spend"
                value={usd(totals.estimated_cost_usd)}
                hint="priced spans only"
                icon={<Banknote className="size-3.5" />}
              />
              <Stat
                label="Priced spans"
                value={count(totals.spans)}
                icon={<Sigma className="size-3.5" />}
              />
              <Stat
                label="Input + cached tokens"
                value={count(totals.input_tokens + totals.cached_input_tokens)}
                hint={`${count(totals.cached_input_tokens)} cached`}
                icon={<Coins className="size-3.5" />}
              />
              <Stat
                label="Output tokens"
                value={count(totals.output_tokens)}
                icon={<Coins className="size-3.5" />}
              />
            </StatGrid>

            {droppedUndated > 0 ? (
              <DegradedBanner
                reason={`${count(droppedUndated)} spans carry no timestamp and are excluded from every windowed view — the totals above understate spend by that much.`}
              />
            ) : null}
          </>
        ) : (
          <NoData reason="no totals were returned for this window" />
        )}

        {unpricedTiers.length > 0 ? (
          <div className="rounded-md border border-warn/30 bg-warn/10 px-3 py-2.5">
            <p className="flex items-center gap-1.5 text-xs font-medium text-warn">
              <AlertTriangle className="size-3.5 shrink-0" aria-hidden="true" />
              {unpricedTiers.length} tier{unpricedTiers.length === 1 ? '' : 's'} have no price card —
              their spans bill at $0 and silently understate spend
            </p>
            <div className="mt-2 flex flex-wrap gap-1.5">
              {unpricedTiers.map((tier) => (
                <Badge key={tier} variant="warn">
                  {tier}
                </Badge>
              ))}
            </div>
          </div>
        ) : null}
      </ModuleCard>

      <ModuleCard
        title="Spend by tier"
        description="Which rung of the ladder consumes the budget"
        icon={<Layers className="size-3.5" />}
        moduleName="Cost by tier"
        isLoading={query.isLoading}
        error={error}
        panel={panel}
        emptyLabel="cost accounting is restricted to CXO tier and above"
      >
        <GroupBreakdown
          groups={tiers}
          header="Tier"
          totalCost={totals?.estimated_cost_usd}
          emptyLabel="no priced spans attributed to a tier"
        />
      </ModuleCard>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <ModuleCard
          title="Spend by agent"
          description="Per-role attribution of every priced span"
          icon={<Users className="size-3.5" />}
          moduleName="Cost by agent"
          isLoading={query.isLoading}
          error={error}
          panel={panel}
          emptyLabel="cost accounting is restricted to CXO tier and above"
        >
          <GroupBreakdown
            groups={agents}
            header="Agent"
            totalCost={totals?.estimated_cost_usd}
            emptyLabel="no priced spans attributed to an agent"
          />
        </ModuleCard>

        <ModuleCard
          title="Spend by ticket"
          description="What each unit of delivered work cost to produce"
          icon={<Ticket className="size-3.5" />}
          moduleName="Cost by ticket"
          isLoading={query.isLoading}
          error={error}
          panel={panel}
          emptyLabel="cost accounting is restricted to CXO tier and above"
        >
          <GroupBreakdown
            groups={tickets}
            header="Ticket"
            totalCost={totals?.estimated_cost_usd}
            emptyLabel="no priced spans attributed to a ticket"
          />
        </ModuleCard>
      </div>
    </div>
  )
}
