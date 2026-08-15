import { useMemo } from 'react'
import { Bot, Coins, FileCode2, Gauge, Layers } from 'lucide-react'
import { ModuleCard } from '@/components/ModuleCard'
import { Badge, type BadgeProps } from '@/components/ui/badge'
import { Stat, StatGrid } from '@/components/ui/stat'
import { DataTable } from '@/components/ui/table'
import { NoData } from '@/components/ui/feedback'
import { useModuleQuery, SLOW_INTERVAL } from '@/hooks/useModuleQuery'
import { api } from '@/lib/api'
import { bytes, count, percent } from '@/lib/utils'
import type { AgentRow, AgentsPanel, TemplateRow } from '@/lib/types'

function rateVariant(rate: number): BadgeProps['variant'] {
  if (rate >= 0.9) return 'allow'
  if (rate >= 0.6) return 'warn'
  return 'deny'
}

function rateTone(rate: number | null): 'default' | 'allow' | 'warn' | 'deny' | 'nodata' {
  if (rate === null) return 'nodata'
  if (rate >= 0.9) return 'allow'
  if (rate >= 0.6) return 'warn'
  return 'deny'
}

export function AgentsPage() {
  const query = useModuleQuery<AgentsPanel>('agents', (signal) => api.agents(signal), {
    refetchInterval: SLOW_INTERVAL,
  })

  const panel = query.data
  const templates = panel?.templates

  const agents = useMemo<AgentRow[]>(
    () => [...(panel?.agents ?? [])].sort((left, right) => right.spans - left.spans),
    [panel?.agents],
  )

  const totals = useMemo(() => {
    const spans = agents.reduce((sum, row) => sum + row.spans, 0)
    const ok = agents.reduce((sum, row) => sum + row.ok, 0)
    return {
      spans,
      output: agents.reduce((sum, row) => sum + row.output_tokens, 0),
      successRate: spans > 0 ? ok / spans : null,
    }
  }, [agents])

  const templateRows = useMemo<TemplateRow[]>(
    () => [...(templates?.templates ?? [])].sort((left, right) => right.bytes - left.bytes),
    [templates?.templates],
  )

  return (
    <div className="space-y-4">
      <ModuleCard
        title="Agent span usage"
        description="Per-agent execution volume derived from the span store — nothing is estimated"
        icon={<Bot className="size-3.5" aria-hidden="true" />}
        moduleName="Agent usage"
        isLoading={query.isLoading}
        error={query.isError ? query.error : undefined}
        panel={panel}
        emptyLabel="per-agent usage is unavailable at your tier"
        actions={
          panel?.available && panel.total !== undefined ? (
            <Badge variant="outline">{count(panel.total)} on record</Badge>
          ) : null
        }
        bodyClassName="space-y-4 p-4"
      >
        {agents.length === 0 ? (
          <NoData reason="The span store has produced no per-agent rows yet — no agent has recorded a span." />
        ) : (
          <>
            <StatGrid>
              <Stat
                label="Agents seen"
                value={count(agents.length)}
                hint="distinct agents with at least one span"
                icon={<Bot className="size-3.5" aria-hidden="true" />}
              />
              <Stat
                label="Total spans"
                value={count(totals.spans)}
                icon={<Layers className="size-3.5" aria-hidden="true" />}
              />
              <Stat
                label="Success rate"
                value={percent(totals.successRate)}
                hint="ok spans over all spans"
                tone={rateTone(totals.successRate)}
                icon={<Gauge className="size-3.5" aria-hidden="true" />}
              />
              <Stat
                label="Output tokens"
                value={count(totals.output)}
                icon={<Coins className="size-3.5" aria-hidden="true" />}
              />
            </StatGrid>

            <DataTable
              dense
              rows={agents}
              rowKey={(row) => row.agent}
              columns={[
                { key: 'agent', header: 'Agent', cell: (row) => row.agent, mono: true },
                {
                  key: 'spans',
                  header: 'Spans',
                  align: 'right',
                  mono: true,
                  cell: (row) => count(row.spans),
                },
                {
                  key: 'success',
                  header: 'Success',
                  align: 'right',
                  cell: (row) => (
                    <Badge variant={rateVariant(row.success_rate)}>{percent(row.success_rate)}</Badge>
                  ),
                },
                {
                  key: 'input',
                  header: 'Input tokens',
                  align: 'right',
                  mono: true,
                  cell: (row) => count(row.input_tokens),
                },
                {
                  key: 'output',
                  header: 'Output tokens',
                  align: 'right',
                  mono: true,
                  cell: (row) => count(row.output_tokens),
                },
                {
                  key: 'tiers',
                  header: 'Tiers',
                  cell: (row) => (
                    <div className="flex flex-wrap gap-1">
                      {row.tiers.map((tier) => (
                        <Badge key={tier} variant="outline">
                          {tier}
                        </Badge>
                      ))}
                    </div>
                  ),
                },
              ]}
            />
          </>
        )}
      </ModuleCard>

      <ModuleCard
        title="Agent template inventory"
        description="Role prompts checked into the repository, sized on disk"
        icon={<FileCode2 className="size-3.5" aria-hidden="true" />}
        moduleName="Agent templates"
        isLoading={query.isLoading}
        error={query.isError ? query.error : undefined}
        panel={templates}
        emptyLabel="the template inventory is unavailable at your tier"
        bodyClassName="space-y-4 p-4"
      >
        <StatGrid cols={2}>
          <Stat
            label="Templates on disk"
            value={count(templates?.total ?? templateRows.length)}
            hint="one prompt file per templated role"
            icon={<FileCode2 className="size-3.5" aria-hidden="true" />}
          />
          <Stat
            label="Total size"
            value={bytes(templateRows.reduce((sum, row) => sum + row.bytes, 0))}
            hint="sum of the listed template files"
            icon={<Layers className="size-3.5" aria-hidden="true" />}
          />
        </StatGrid>

        <DataTable
          dense
          rows={templateRows}
          rowKey={(row) => row.role}
          maxHeight="max-h-96"
          empty={<NoData reason="No template files were listed for this inventory." />}
          columns={[
            { key: 'role', header: 'Role', cell: (row) => row.role, mono: true },
            {
              key: 'bytes',
              header: 'Size',
              align: 'right',
              mono: true,
              cell: (row) => bytes(row.bytes),
            },
          ]}
        />
      </ModuleCard>
    </div>
  )
}
