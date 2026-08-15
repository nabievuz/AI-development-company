import { useMemo, useState } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { Building2, LogOut, Menu, RefreshCw, X } from 'lucide-react'
import { useIsFetching, useQueryClient } from '@tanstack/react-query'
import { NAV_GROUPS, navFor } from './navigation'
import { TierBadge } from '@/components/ui/badge'
import { useSession } from '@/stores/session'
import { useTabLeader } from '@/hooks/useTabLeader'
import { createCoalescedInvalidator } from '@/lib/queryClient'
import { cn } from '@/lib/utils'

function Brand() {
  return (
    <div className="flex items-center gap-2 px-3 py-3">
      <Building2 className="size-4 text-primary" aria-hidden="true" />
      <div className="min-w-0">
        <p className="truncate text-sm font-semibold tracking-tight">DasLab</p>
        <p className="truncate text-[11px] text-muted-foreground">Operator Cockpit</p>
      </div>
    </div>
  )
}

function IdentityCard() {
  const identity = useSession((state) => state.identity)
  const signOut = useSession((state) => state.signOut)
  if (!identity) return null
  return (
    <div className="border-t border-border p-3">
      <div className="flex items-center justify-between gap-2">
        <div className="min-w-0">
          <p className="truncate text-xs font-medium">{identity.user}</p>
          <p className="truncate font-mono text-[11px] text-muted-foreground">
            {identity.principal}
          </p>
        </div>
        <TierBadge tier={identity.tier} />
      </div>
      {identity.role ? (
        <p className="mt-1.5 truncate text-[11px] text-muted-foreground">
          acting as <span className="font-medium text-foreground">{identity.role}</span>
          {identity.department ? ` · ${identity.department}` : ''}
        </p>
      ) : null}
      {identity.tier !== identity.base_tier ? (
        <p className="mt-1 text-[11px] text-warn">
          downscoped from {identity.base_tier}
        </p>
      ) : null}
      <button
        type="button"
        onClick={signOut}
        className="mt-2 inline-flex w-full items-center justify-center gap-1.5 rounded-md border border-border px-2 py-1 text-[11px] font-medium hover:bg-accent"
      >
        <LogOut className="size-3" aria-hidden="true" />
        Sign out
      </button>
    </div>
  )
}

function SidebarNav({ onNavigate }: { onNavigate?: () => void }) {
  const identity = useSession((state) => state.identity)
  const items = useMemo(() => navFor(identity?.modules ?? []), [identity?.modules])
  const grouped = useMemo(
    () => NAV_GROUPS.map((group) => ({ group, items: items.filter((item) => item.group === group) })),
    [items],
  )

  return (
    <nav className="flex-1 overflow-y-auto scrollbar-thin px-2 pb-4" aria-label="Modules">
      {grouped.map(({ group, items: groupItems }) =>
        groupItems.length === 0 ? null : (
          <div key={group} className="mb-3">
            <p className="px-2 py-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
              {group}
            </p>
            <ul className="space-y-0.5">
              {groupItems.map((item) => (
                <li key={item.module}>
                  <NavLink
                    to={item.path}
                    end={item.path === '/'}
                    onClick={onNavigate}
                    className={({ isActive }) =>
                      cn(
                        'flex items-center gap-2 rounded-md px-2 py-1.5 text-[13px] transition-colors',
                        isActive
                          ? 'bg-accent font-medium text-accent-foreground'
                          : 'text-muted-foreground hover:bg-accent/60 hover:text-foreground',
                      )
                    }
                  >
                    <item.icon className="size-3.5 shrink-0" />
                    <span className="truncate">{item.label}</span>
                  </NavLink>
                </li>
              ))}
            </ul>
          </div>
        ),
      )}
    </nav>
  )
}

function Header({ onOpenMenu }: { onOpenMenu: () => void }) {
  const location = useLocation()
  const identity = useSession((state) => state.identity)
  const fetching = useIsFetching()
  const client = useQueryClient()
  const isLeader = useTabLeader()
  const refresh = useMemo(() => createCoalescedInvalidator(client), [client])
  const items = navFor(identity?.modules ?? [])
  const current = items.find((item) => item.path === location.pathname)

  return (
    <header className="sticky top-0 z-20 flex h-12 items-center gap-3 border-b border-border bg-background/95 px-4 backdrop-blur">
      <button
        type="button"
        onClick={onOpenMenu}
        className="rounded-md p-1 hover:bg-accent lg:hidden"
        aria-label="Open navigation"
      >
        <Menu className="size-4" />
      </button>
      <h1 className="flex-1 truncate text-sm font-semibold tracking-tight">
        {current?.label ?? 'Operator Cockpit'}
      </h1>
      <span
        title={isLeader ? 'This tab owns the polling lease' : 'Another tab is polling; this tab follows'}
        className={cn(
          'font-mono text-[11px] transition-opacity',
          fetching > 0 ? 'text-primary opacity-100' : 'text-muted-foreground opacity-60',
        )}
      >
        {fetching > 0 ? 'syncing…' : isLeader ? 'live' : 'follower'}
      </span>
      <button
        type="button"
        onClick={refresh}
        className="inline-flex items-center gap-1.5 rounded-md border border-border px-2 py-1 text-[11px] font-medium hover:bg-accent"
      >
        <RefreshCw className={cn('size-3', fetching > 0 && 'animate-spin')} aria-hidden="true" />
        Refresh
      </button>
    </header>
  )
}

export function AppLayout() {
  const [menuOpen, setMenuOpen] = useState(false)

  return (
    <div className="flex min-h-screen bg-background">
      <aside className="hidden w-60 shrink-0 flex-col border-r border-border bg-surface lg:flex">
        <Brand />
        <SidebarNav />
        <IdentityCard />
      </aside>

      {menuOpen ? (
        <div className="fixed inset-0 z-40 lg:hidden">
          <button
            type="button"
            aria-label="Close navigation"
            className="absolute inset-0 bg-black/50"
            onClick={() => setMenuOpen(false)}
          />
          <aside className="relative flex h-full w-64 flex-col border-r border-border bg-surface">
            <div className="flex items-center justify-between">
              <Brand />
              <button
                type="button"
                onClick={() => setMenuOpen(false)}
                className="mr-3 rounded-md p-1 hover:bg-accent"
                aria-label="Close navigation"
              >
                <X className="size-4" />
              </button>
            </div>
            <SidebarNav onNavigate={() => setMenuOpen(false)} />
            <IdentityCard />
          </aside>
        </div>
      ) : null}

      <div className="flex min-w-0 flex-1 flex-col">
        <Header onOpenMenu={() => setMenuOpen(true)} />
        <main className="flex-1 p-4">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
