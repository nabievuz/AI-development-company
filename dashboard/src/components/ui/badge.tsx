import { cva, type VariantProps } from 'class-variance-authority'
import type { HTMLAttributes } from 'react'
import { cn } from '@/lib/utils'
import type { Tier } from '@/lib/types'

const badgeVariants = cva(
  'inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 text-[11px] font-medium leading-4 whitespace-nowrap',
  {
    variants: {
      variant: {
        neutral: 'border-border bg-muted text-muted-foreground',
        outline: 'border-border bg-transparent text-foreground',
        allow: 'border-transparent bg-allow/15 text-allow',
        deny: 'border-transparent bg-deny/15 text-deny',
        warn: 'border-transparent bg-warn/15 text-warn',
        info: 'border-transparent bg-info/15 text-info',
        nodata: 'border-dashed border-nodata/50 bg-transparent text-nodata',
      },
    },
    defaultVariants: { variant: 'neutral' },
  },
)

export interface BadgeProps
  extends HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

export function Badge({ className, variant, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ variant }), className)} {...props} />
}

const TIER_CLASS: Record<Tier, string> = {
  founder: 'border-transparent bg-tier-founder/15 text-tier-founder',
  cxo: 'border-transparent bg-tier-cxo/15 text-tier-cxo',
  lead: 'border-transparent bg-tier-lead/15 text-tier-lead',
  ic: 'border-transparent bg-tier-ic/15 text-tier-ic',
  audit: 'border-transparent bg-info/15 text-info',
  orchestrator: 'border-transparent bg-muted text-muted-foreground',
}

export function TierBadge({ tier, className }: { tier: Tier; className?: string }) {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-md border px-1.5 py-0.5 text-[11px] font-semibold uppercase tracking-wide',
        TIER_CLASS[tier] ?? TIER_CLASS.ic,
        className,
      )}
    >
      {tier}
    </span>
  )
}

export function DecisionBadge({ decision }: { decision: string }) {
  const normalized = decision.toLowerCase()
  if (normalized === 'allow') return <Badge variant="allow">allow</Badge>
  if (normalized === 'deny') return <Badge variant="deny">deny</Badge>
  if (normalized === 'error') return <Badge variant="warn">error</Badge>
  return <Badge variant="neutral">{decision || '—'}</Badge>
}

const STATUS_VARIANT: Record<string, BadgeProps['variant']> = {
  done: 'allow',
  in_review: 'info',
  in_progress: 'info',
  blocked: 'deny',
  interrupted: 'warn',
  todo: 'neutral',
  backlog: 'neutral',
}

export function StatusBadge({ status }: { status: string }) {
  return <Badge variant={STATUS_VARIANT[status] ?? 'neutral'}>{status || '—'}</Badge>
}
