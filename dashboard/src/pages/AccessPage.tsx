import { useMemo } from 'react'
import { Bot, Crown, Gavel, KeyRound, LayoutGrid, ShieldCheck, UserRound, Users } from 'lucide-react'
import { ModuleCard } from '@/components/ModuleCard'
import { Badge, TierBadge } from '@/components/ui/badge'
import { Stat, StatGrid } from '@/components/ui/stat'
import { DataTable } from '@/components/ui/table'
import { useModuleQuery, SLOW_INTERVAL } from '@/hooks/useModuleQuery'
import { api } from '@/lib/api'
import { count } from '@/lib/utils'
import type { PrincipalKindRow, RbacPanel } from '@/lib/types'

interface AuthorityRow {
  category: string
  authority: string
}

function grantVariant(value: string): 'allow' | 'info' | 'neutral' {
  const normalized = value.toLowerCase()
  if (normalized === 'allow') return 'allow'
  if (normalized === 'own') return 'info'
  return 'neutral'
}

function KindCard({ kind }: { kind: PrincipalKindRow }) {
  const grants = Object.entries(kind.grants)
  return (
    <article className="rounded-lg border border-border bg-card p-4">
      <header className="flex flex-wrap items-start justify-between gap-2">
        <span className="font-mono text-xs font-medium">{kind.kind}</span>
        {kind.human ? (
          <Badge variant="info">
            <UserRound className="size-3" aria-hidden="true" />
            human
          </Badge>
        ) : (
          <Badge variant="neutral">
            <Bot className="size-3" aria-hidden="true" />
            machine
          </Badge>
        )}
      </header>

      {kind.description ? (
        <p className="mt-1.5 text-xs text-muted-foreground">{kind.description}</p>
      ) : null}

      <div className="mt-3 border-t border-border/60 pt-2">
        <p className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
          Grants
        </p>
        {grants.length === 0 ? (
          <p className="mt-1.5 text-[11px] text-nodata">
            No permission is granted to this kind by the resolved policy.
          </p>
        ) : (
          <ul className="mt-1.5 flex flex-wrap gap-1.5">
            {grants.map(([permission, value]) => (
              <li key={permission}>
                <Badge variant={grantVariant(value)}>
                  <span className="font-mono">{permission}</span>
                  <span className="opacity-70">{value}</span>
                </Badge>
              </li>
            ))}
          </ul>
        )}
      </div>
    </article>
  )
}

export function AccessPage() {
  const query = useModuleQuery<RbacPanel>('rbac', (signal) => api.rbac(signal), {
    refetchInterval: SLOW_INTERVAL,
  })

  const panel = query.data
  const error = query.isError ? query.error : undefined
  const founderOnly = useMemo(() => new Set(panel?.founder_only ?? []), [panel?.founder_only])

  const authorities = useMemo<AuthorityRow[]>(
    () =>
      Object.entries(panel?.gate_approval_authority ?? {}).map(([category, authority]) => ({
        category,
        authority,
      })),
    [panel?.gate_approval_authority],
  )

  return (
    <div className="space-y-4">
      <StatGrid>
        <Stat
          label="Principal kinds"
          value={panel?.available ? count(panel.principal_kinds.length) : '—'}
          hint="every identity the substrate can authenticate"
          tone={panel?.available ? 'default' : 'nodata'}
          icon={<Users className="size-3.5" />}
        />
        <Stat
          label="Permissions"
          value={panel?.available ? count(panel.permissions.length) : '—'}
          hint="the complete permission vocabulary"
          tone={panel?.available ? 'default' : 'nodata'}
          icon={<KeyRound className="size-3.5" />}
        />
        <Stat
          label="Founder-only"
          value={panel?.available ? count(panel.founder_only.length) : '—'}
          hint="refused to every non-founder kind"
          tone={panel?.available ? (panel.founder_only.length > 0 ? 'deny' : 'default') : 'nodata'}
          icon={<Crown className="size-3.5" />}
        />
        <Stat
          label="Governed modules"
          value={panel?.available ? count(panel.modules.length) : '—'}
          hint="each guarded by a permission and a tier floor"
          tone={panel?.available ? 'default' : 'nodata'}
          icon={<LayoutGrid className="size-3.5" />}
        />
      </StatGrid>

      <ModuleCard
        title="Principal kinds"
        description="What each authenticated identity is allowed to hold before role, tier, and department narrow it further"
        icon={<Users className="size-3.5" />}
        moduleName="Principal kinds"
        isLoading={query.isLoading}
        error={error}
        panel={panel}
        emptyLabel="the access-control catalogue is unavailable at your tier"
        bodyClassName="p-4"
      >
        {panel && panel.principal_kinds.length === 0 ? (
          <p className="py-6 text-center text-xs text-muted-foreground">
            The resolved policy declares no principal kinds.
          </p>
        ) : (
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
            {(panel?.principal_kinds ?? []).map((kind) => (
              <KindCard key={kind.kind} kind={kind} />
            ))}
          </div>
        )}
      </ModuleCard>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <ModuleCard
          title="Founder-only permissions"
          description="Reserved by the policy itself, not by convention"
          icon={<Crown className="size-3.5" />}
          moduleName="Founder-only permissions"
          isLoading={query.isLoading}
          error={error}
          panel={panel}
          emptyLabel="the access-control catalogue is unavailable at your tier"
        >
          <p className="text-xs text-muted-foreground">
            These permissions are structurally refused to every non-founder principal kind — no
            role, tier, or department grant can produce them, and a request carrying one is denied
            at the substrate stage before any module is consulted.
          </p>
          {panel && panel.founder_only.length === 0 ? (
            <p className="mt-3 text-xs text-nodata">
              The policy reserves no permission exclusively for the founder.
            </p>
          ) : (
            <ul className="mt-3 flex flex-wrap gap-1.5">
              {(panel?.founder_only ?? []).map((permission) => (
                <li key={permission}>
                  <Badge variant="deny">
                    <span className="font-mono">{permission}</span>
                  </Badge>
                </li>
              ))}
            </ul>
          )}
        </ModuleCard>

        <ModuleCard
          title="Gate approval authority"
          description="Who may sign off on each category of gate"
          icon={<Gavel className="size-3.5" />}
          moduleName="Gate approval authority"
          isLoading={query.isLoading}
          error={error}
          panel={panel}
          emptyLabel="the access-control catalogue is unavailable at your tier"
          bodyClassName="p-0"
        >
          <DataTable
            dense
            rows={authorities}
            rowKey={(row) => row.category}
            empty={
              <p className="px-4 py-6 text-center text-xs text-muted-foreground">
                The policy delegates no gate approval authority.
              </p>
            }
            columns={[
              { key: 'category', header: 'Category', cell: (row) => row.category, mono: true },
              {
                key: 'authority',
                header: 'Authority',
                align: 'right',
                cell: (row) => <Badge variant="outline">{row.authority}</Badge>,
              },
            ]}
          />
        </ModuleCard>
      </div>

      <ModuleCard
        title="Permission vocabulary"
        description="Every permission the policy can express — founder-only entries are marked"
        icon={<KeyRound className="size-3.5" />}
        moduleName="Permission vocabulary"
        isLoading={query.isLoading}
        error={error}
        panel={panel}
        emptyLabel="the access-control catalogue is unavailable at your tier"
      >
        {panel && panel.permissions.length === 0 ? (
          <p className="py-6 text-center text-xs text-muted-foreground">
            The resolved policy declares no permissions.
          </p>
        ) : (
          <ul className="flex flex-wrap gap-1.5">
            {(panel?.permissions ?? []).map((permission) => (
              <li key={permission}>
                <Badge variant={founderOnly.has(permission) ? 'deny' : 'outline'}>
                  <span className="font-mono">{permission}</span>
                </Badge>
              </li>
            ))}
          </ul>
        )}
      </ModuleCard>

      <ModuleCard
        title="Module capability matrix"
        description="The permission and tier floor each module surface demands"
        icon={<ShieldCheck className="size-3.5" />}
        moduleName="Module capability matrix"
        isLoading={query.isLoading}
        error={error}
        panel={panel}
        emptyLabel="the access-control catalogue is unavailable at your tier"
        bodyClassName="p-0"
      >
        <DataTable
          rows={panel?.modules ?? []}
          rowKey={(row) => row.id}
          empty={
            <p className="px-4 py-6 text-center text-xs text-muted-foreground">
              No module is registered in the catalogue.
            </p>
          }
          columns={[
            { key: 'id', header: 'Module', cell: (row) => row.id, mono: true },
            { key: 'title', header: 'Title', cell: (row) => row.title },
            {
              key: 'department',
              header: 'Department',
              cell: (row) => <Badge variant="outline">{row.department}</Badge>,
            },
            {
              key: 'permission',
              header: 'Required permission',
              cell: (row) => row.permission,
              mono: true,
            },
            {
              key: 'min_tier',
              header: 'Min tier',
              align: 'right',
              cell: (row) => <TierBadge tier={row.min_tier} />,
            },
          ]}
        />
      </ModuleCard>
    </div>
  )
}
