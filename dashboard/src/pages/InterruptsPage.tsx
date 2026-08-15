import { useMemo, useState } from 'react'
import { AlertTriangle, CheckCircle2, Clock, Inbox } from 'lucide-react'
import { ModuleCard } from '@/components/ModuleCard'
import { Badge } from '@/components/ui/badge'
import { Stat, StatGrid } from '@/components/ui/stat'
import { useModuleQuery, SLOW_INTERVAL } from '@/hooks/useModuleQuery'
import { api } from '@/lib/api'
import { count } from '@/lib/utils'
import type { InterruptCard, InterruptsPanel } from '@/lib/types'

type Filter = 'all' | 'pending' | 'expired' | 'divergent'

const FILTERS: { id: Filter; label: string }[] = [
  { id: 'all', label: 'All' },
  { id: 'pending', label: 'Pending' },
  { id: 'expired', label: 'Expired' },
  { id: 'divergent', label: 'Off-schema' },
]

function matches(card: InterruptCard, filter: Filter): boolean {
  if (filter === 'pending') return !card.expired
  if (filter === 'expired') return Boolean(card.expired)
  if (filter === 'divergent') return !card.schema_valid
  return true
}

function CardRow({ card }: { card: InterruptCard }) {
  return (
    <article className="rounded-lg border border-border bg-card p-4">
      <header className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="font-mono text-xs text-muted-foreground">{card.id}</span>
            {card.ticket ? <Badge variant="outline">{card.ticket}</Badge> : null}
            {card.type ? <Badge variant="neutral">{card.type}</Badge> : null}
            {card.expired ? <Badge variant="deny">expired</Badge> : <Badge variant="info">open</Badge>}
            {card.schema_valid ? (
              <Badge variant="allow">schema valid</Badge>
            ) : (
              <Badge variant="warn">off-schema</Badge>
            )}
          </div>
          <h3 className="mt-1.5 text-sm font-medium">{card.question || '(no question recorded)'}</h3>
        </div>
        {card.expires ? (
          <span className="shrink-0 font-mono text-[11px] text-muted-foreground">
            expires {card.expires}
          </span>
        ) : null}
      </header>

      {card.decision ? (
        <p className="mt-2 text-xs text-muted-foreground">
          <span className="font-medium text-foreground">Decision:</span> {card.decision}
        </p>
      ) : null}

      {card.resume ? (
        <p className="mt-1.5 rounded-md bg-muted px-2 py-1.5 font-mono text-[11px] break-words">
          resume: {card.resume}
        </p>
      ) : null}

      {card.options && card.options.length > 0 ? (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {card.options.map((option) => (
            <Badge key={option} variant="outline">
              {option}
            </Badge>
          ))}
        </div>
      ) : (
        <p className="mt-2 text-[11px] text-warn">
          No options listed — this card cannot form a machine-checkable answer stub.
        </p>
      )}

      {card.conditions && card.conditions.length > 0 ? (
        <ul className="mt-2 space-y-1">
          {card.conditions.map((condition, index) => (
            <li key={index} className="flex gap-1.5 text-[11px] text-muted-foreground">
              <span aria-hidden="true">·</span>
              <span>{condition}</span>
            </li>
          ))}
        </ul>
      ) : null}

      {card.violations.length > 0 ? (
        <div className="mt-3 rounded-md border border-warn/30 bg-warn/10 px-2.5 py-2">
          <p className="flex items-center gap-1.5 text-[11px] font-medium text-warn">
            <AlertTriangle className="size-3" aria-hidden="true" />
            Diverges from board/interrupts/schema.json
          </p>
          <ul className="mt-1 space-y-0.5">
            {card.violations.map((violation, index) => (
              <li key={index} className="font-mono text-[11px] text-warn/90">
                {violation}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      <footer className="mt-3 flex flex-wrap gap-x-4 gap-y-1 border-t border-border/60 pt-2 text-[11px] text-muted-foreground">
        {card.created_by ? <span>raised by {card.created_by}</span> : null}
        {card.source ? <span>source {card.source}</span> : null}
      </footer>
    </article>
  )
}

export function InterruptsPage() {
  const [filter, setFilter] = useState<Filter>('all')
  const query = useModuleQuery<InterruptsPanel>('interrupts', (signal) => api.interrupts(signal), {
    refetchInterval: SLOW_INTERVAL,
  })

  const panel = query.data
  const cards = useMemo(
    () => (panel?.cards ?? []).filter((card) => matches(card, filter)),
    [panel?.cards, filter],
  )

  return (
    <div className="space-y-4">
      <StatGrid>
        <Stat
          label="Cards on file"
          value={count(panel?.total ?? 0)}
          icon={<Inbox className="size-3.5" />}
        />
        <Stat
          label="Answerable"
          value={count(panel?.answerable ?? 0)}
          hint="carry a legal options list"
          tone={panel?.answerable ? 'default' : 'nodata'}
          icon={<CheckCircle2 className="size-3.5" />}
        />
        <Stat
          label="Expired"
          value={count(panel?.expired ?? 0)}
          tone={panel?.expired ? 'warn' : 'default'}
          icon={<Clock className="size-3.5" />}
        />
        <Stat
          label="Off-schema"
          value={count(panel?.schema_divergent ?? 0)}
          hint="validated against schema.json"
          tone={panel?.schema_divergent ? 'deny' : 'allow'}
          icon={<AlertTriangle className="size-3.5" />}
        />
      </StatGrid>

      <ModuleCard
        title="Action console"
        description="A running agent pauses itself to ask the Founder a question. The cockpit displays them; it never answers one."
        icon={<Inbox className="size-3.5" />}
        moduleName="Action console"
        isLoading={query.isLoading}
        error={query.isError ? query.error : undefined}
        panel={panel}
        emptyLabel="no pending interrupt-cards — nothing awaits a Founder answer"
        actions={
          <div className="flex gap-1">
            {FILTERS.map((entry) => (
              <button
                key={entry.id}
                type="button"
                onClick={() => setFilter(entry.id)}
                className={
                  filter === entry.id
                    ? 'rounded-md bg-accent px-2 py-1 text-[11px] font-medium'
                    : 'rounded-md px-2 py-1 text-[11px] text-muted-foreground hover:bg-accent/60'
                }
              >
                {entry.label}
              </button>
            ))}
          </div>
        }
        bodyClassName="space-y-3"
      >
        {cards.length === 0 ? (
          <p className="py-6 text-center text-xs text-muted-foreground">
            No cards match the “{filter}” filter.
          </p>
        ) : (
          cards.map((card) => <CardRow key={card.id} card={card} />)
        )}
      </ModuleCard>
    </div>
  )
}
