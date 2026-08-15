import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

interface StatProps {
  label: ReactNode
  value: ReactNode
  hint?: ReactNode
  tone?: 'default' | 'allow' | 'deny' | 'warn' | 'nodata'
  icon?: ReactNode
}

const TONE: Record<NonNullable<StatProps['tone']>, string> = {
  default: 'text-foreground',
  allow: 'text-allow',
  deny: 'text-deny',
  warn: 'text-warn',
  nodata: 'text-nodata',
}

export function Stat({ label, value, hint, tone = 'default', icon }: StatProps) {
  return (
    <div className="rounded-lg border border-border bg-card px-4 py-3">
      <div className="flex items-center justify-between gap-2">
        <p className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
          {label}
        </p>
        {icon ? <span className="text-muted-foreground">{icon}</span> : null}
      </div>
      <p className={cn('mt-1 font-mono text-2xl font-semibold tabular', TONE[tone])}>{value}</p>
      {hint ? <p className="mt-0.5 text-xs text-muted-foreground">{hint}</p> : null}
    </div>
  )
}

export function StatGrid({ children, cols = 4 }: { children: ReactNode; cols?: 2 | 3 | 4 }) {
  const grid =
    cols === 2
      ? 'sm:grid-cols-2'
      : cols === 3
        ? 'sm:grid-cols-2 lg:grid-cols-3'
        : 'sm:grid-cols-2 lg:grid-cols-4'
  return <div className={cn('grid grid-cols-1 gap-3', grid)}>{children}</div>
}
