import { useMemo, useState } from 'react'
import { Building2, Crown, FileCode2, Layers, ListTree, Network, Search } from 'lucide-react'
import { ModuleCard } from '@/components/ModuleCard'
import { Badge, TierBadge } from '@/components/ui/badge'
import { Stat, StatGrid } from '@/components/ui/stat'
import { BarList } from '@/components/charts'
import { DataTable } from '@/components/ui/table'
import { useModuleQuery, SLOW_INTERVAL } from '@/hooks/useModuleQuery'
import { api } from '@/lib/api'
import { count, titleCase } from '@/lib/utils'
import type { OrgPanel, RoleRow } from '@/lib/types'

const ALL_DEPARTMENTS = 'all'

function distribution(source: Record<string, number>): { label: string; value: number; hint: string }[] {
  return Object.entries(source)
    .sort((left, right) => right[1] - left[1])
    .map(([key, value]) => ({ label: titleCase(key), value, hint: count(value) }))
}

export function OrgPage() {
  const [department, setDepartment] = useState<string>(ALL_DEPARTMENTS)
  const [term, setTerm] = useState('')
  const query = useModuleQuery<OrgPanel>('org.directory', (signal) => api.org(signal), {
    refetchInterval: SLOW_INTERVAL,
  })

  const panel = query.data
  const roles = panel?.roles
  const departments = panel?.departments ?? []

  const cxoRoles = useMemo(
    () => (roles ? roles.filter((role) => role.tier === 'cxo').length : null),
    [roles],
  )

  const visibleRoles = useMemo(() => {
    const needle = term.trim().toLowerCase()
    return (roles ?? []).filter((role) => {
      if (department !== ALL_DEPARTMENTS && role.department !== department) return false
      if (!needle) return true
      return role.key.toLowerCase().includes(needle) || role.title.toLowerCase().includes(needle)
    })
  }, [roles, department, term])

  const available = panel?.available === true

  return (
    <div className="space-y-4">
      <StatGrid>
        <Stat
          label="Roles"
          value={available ? count(panel.totals.roles) : '—'}
          hint={available ? 'declared in the org model' : panel?.reason}
          tone={available ? 'default' : 'nodata'}
          icon={<ListTree className="size-3.5" aria-hidden="true" />}
        />
        <Stat
          label="Departments"
          value={available ? count(panel.totals.departments) : '—'}
          hint={available ? 'each with a named manager role' : panel?.reason}
          tone={available ? 'default' : 'nodata'}
          icon={<Building2 className="size-3.5" aria-hidden="true" />}
        />
        <Stat
          label="Templated"
          value={available ? count(panel.totals.templated) : '—'}
          hint={available ? `of ${count(panel.totals.roles)} roles carry a prompt template` : panel?.reason}
          tone={available ? 'default' : 'nodata'}
          icon={<FileCode2 className="size-3.5" aria-hidden="true" />}
        />
        <Stat
          label="CXO tier"
          value={cxoRoles === null ? '—' : count(cxoRoles)}
          hint={cxoRoles === null ? 'role roster not exposed at your tier' : 'roles reporting to the founder tier'}
          tone={cxoRoles === null ? 'nodata' : 'default'}
          icon={<Crown className="size-3.5" aria-hidden="true" />}
        />
      </StatGrid>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
        <div className="xl:col-span-2">
          <ModuleCard
            title="Department headcount"
            description="Roles assigned per department, straight from the org model"
            icon={<Building2 className="size-3.5" aria-hidden="true" />}
            moduleName="Departments"
            isLoading={query.isLoading}
            error={query.isError ? query.error : undefined}
            panel={panel}
            emptyLabel="the org model is unavailable at your tier"
            footer={
              panel?.ladder && panel.ladder.length > 0
                ? `Escalation ladder: ${panel.ladder.join(' → ')}`
                : undefined
            }
          >
            <BarList
              data={departments.map((row) => ({
                label: row.title,
                value: row.headcount,
                hint: `${count(row.headcount)} · ${row.manager_role}`,
              }))}
            />
          </ModuleCard>
        </div>

        <ModuleCard
          title="Tier & model mix"
          description="Distribution recorded by the control plane"
          icon={<Layers className="size-3.5" aria-hidden="true" />}
          moduleName="Org composition"
          isLoading={query.isLoading}
          error={query.isError ? query.error : undefined}
          panel={panel}
          emptyLabel="the org model is unavailable at your tier"
          bodyClassName="space-y-4"
        >
          <div>
            <p className="mb-1.5 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
              By tier
            </p>
            <BarList data={distribution(panel?.totals.by_tier ?? {})} />
          </div>
          <div>
            <p className="mb-1.5 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
              By model
            </p>
            <BarList data={distribution(panel?.totals.by_model ?? {})} />
          </div>
        </ModuleCard>
      </div>

      <ModuleCard
        title="Role directory"
        description="Every role, its reporting line, its model, and whether a prompt template backs it"
        icon={<Network className="size-3.5" aria-hidden="true" />}
        moduleName="Role directory"
        isLoading={query.isLoading}
        error={query.isError ? query.error : undefined}
        panel={panel}
        emptyLabel="the org model is unavailable at your tier"
        actions={
          roles ? <Badge variant="outline">{count(visibleRoles.length)} shown</Badge> : null
        }
        bodyClassName="space-y-3 p-4"
      >
        {roles ? (
          <>
            <div className="flex flex-wrap items-center gap-2">
              <div className="flex flex-wrap gap-1">
                <button
                  type="button"
                  onClick={() => setDepartment(ALL_DEPARTMENTS)}
                  className={
                    department === ALL_DEPARTMENTS
                      ? 'rounded-md bg-accent px-2 py-1 text-[11px] font-medium'
                      : 'rounded-md px-2 py-1 text-[11px] text-muted-foreground hover:bg-accent/60'
                  }
                >
                  All
                </button>
                {departments.map((row) => (
                  <button
                    key={row.key}
                    type="button"
                    onClick={() => setDepartment(row.key)}
                    className={
                      department === row.key
                        ? 'rounded-md bg-accent px-2 py-1 text-[11px] font-medium'
                        : 'rounded-md px-2 py-1 text-[11px] text-muted-foreground hover:bg-accent/60'
                    }
                  >
                    {row.title}
                  </button>
                ))}
              </div>
              <div className="relative ml-auto">
                <Search
                  className="pointer-events-none absolute left-2 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground"
                  aria-hidden="true"
                />
                <input
                  type="search"
                  value={term}
                  onChange={(event) => setTerm(event.target.value)}
                  aria-label="Filter roles by key or title"
                  placeholder="Filter by key or title"
                  className="w-56 rounded-md border border-border bg-surface py-1 pl-7 pr-2 text-xs text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary"
                />
              </div>
            </div>

            <DataTable<RoleRow>
              dense
              maxHeight="max-h-[34rem]"
              rows={visibleRoles}
              rowKey={(row) => row.key}
              empty={
                <p className="py-6 text-center text-xs text-muted-foreground">
                  No role matches the current department and search filters.
                </p>
              }
              columns={[
                { key: 'key', header: 'Role key', mono: true, cell: (row) => row.key },
                {
                  key: 'title',
                  header: 'Title',
                  cell: (row) => (
                    <div className="min-w-0">
                      <p className="truncate text-xs font-medium">{row.title}</p>
                      {row.mission ? (
                        <p className="mt-0.5 max-w-md truncate text-[11px] text-muted-foreground" title={row.mission}>
                          {row.mission}
                        </p>
                      ) : null}
                    </div>
                  ),
                },
                {
                  key: 'department',
                  header: 'Department',
                  cell: (row) => <span className="text-xs">{row.department}</span>,
                },
                { key: 'tier', header: 'Tier', cell: (row) => <TierBadge tier={row.tier} /> },
                { key: 'model', header: 'Model', mono: true, cell: (row) => row.model },
                { key: 'reports_to', header: 'Reports to', mono: true, cell: (row) => row.reports_to },
                {
                  key: 'direct_reports',
                  header: 'Reports',
                  align: 'right',
                  mono: true,
                  cell: (row) => count(row.direct_reports.length),
                },
                {
                  key: 'template',
                  header: 'Template',
                  align: 'right',
                  cell: (row) =>
                    row.has_template ? (
                      <Badge variant="allow">present</Badge>
                    ) : (
                      <Badge variant="nodata">none</Badge>
                    ),
                },
              ]}
            />
          </>
        ) : (
          <p className="py-6 text-center text-xs text-muted-foreground">
            {panel?.reason || 'The role roster is not exposed at your tier.'}
          </p>
        )}
      </ModuleCard>
    </div>
  )
}
