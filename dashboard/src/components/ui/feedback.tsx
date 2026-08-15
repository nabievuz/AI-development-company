import { AlertTriangle, DatabaseZap, Lock, ShieldAlert, WifiOff } from 'lucide-react'
import type { ReactNode } from 'react'
import { ApiError } from '@/lib/api'
import type { Panel } from '@/lib/types'
import { cn } from '@/lib/utils'

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn('animate-pulse rounded-md bg-muted', className)} />
}

export function PanelSkeleton({ rows = 3 }: { rows?: number }) {
  return (
    <div className="space-y-2 p-4">
      {Array.from({ length: rows }, (_, index) => (
        <Skeleton key={index} className={cn('h-4', index === 0 ? 'w-1/3' : 'w-full')} />
      ))}
    </div>
  )
}

interface NoticeProps {
  icon: ReactNode
  title: string
  detail?: ReactNode
  tone?: 'muted' | 'warn' | 'deny'
  className?: string
}

export function Notice({ icon, title, detail, tone = 'muted', className }: NoticeProps) {
  const toneClass =
    tone === 'deny'
      ? 'border-deny/30 text-deny'
      : tone === 'warn'
        ? 'border-warn/30 text-warn'
        : 'border-dashed border-border text-muted-foreground'
  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center gap-2 rounded-md border px-4 py-8 text-center',
        toneClass,
        className,
      )}
    >
      <span aria-hidden="true">{icon}</span>
      <p className="text-sm font-medium">{title}</p>
      {detail ? <p className="max-w-prose text-xs opacity-80">{detail}</p> : null}
    </div>
  )
}

export function NoData({ reason }: { reason?: string }) {
  return (
    <Notice
      icon={<DatabaseZap className="size-5" />}
      title="No data yet"
      detail={reason || 'This surface reports nothing because the source is empty.'}
    />
  )
}

export function Forbidden({ reason }: { reason?: string }) {
  return (
    <Notice
      icon={<Lock className="size-5" />}
      title="Not available at your tier"
      detail={reason}
      tone="warn"
    />
  )
}

export function ErrorNotice({ error }: { error: unknown }) {
  if (error instanceof ApiError) {
    if (error.isForbidden) return <Forbidden reason={error.detail} />
    if (error.isUnauthorized)
      return (
        <Notice
          icon={<ShieldAlert className="size-5" />}
          title="Session rejected"
          detail="The control plane refused this token. Sign in again."
          tone="deny"
        />
      )
    if (error.isDisabled)
      return (
        <Notice
          icon={<AlertTriangle className="size-5" />}
          title="Control plane disabled"
          detail="ws_h_control_plane is OFF — the operator surface is the static read cockpit."
          tone="warn"
        />
      )
    if (error.isUnconfigured)
      return (
        <Notice
          icon={<ShieldAlert className="size-5" />}
          title="RBAC not configured"
          detail="The control plane is fail-closed until DASLAB_CP_RBAC resolves."
          tone="warn"
        />
      )
    if (error.status === 0)
      return (
        <Notice
          icon={<WifiOff className="size-5" />}
          title="Control plane unreachable"
          detail={error.detail}
          tone="deny"
        />
      )
    return (
      <Notice
        icon={<AlertTriangle className="size-5" />}
        title={`Request failed (${error.status})`}
        detail={error.detail}
        tone="deny"
      />
    )
  }
  return (
    <Notice
      icon={<AlertTriangle className="size-5" />}
      title="Unexpected error"
      detail={error instanceof Error ? error.message : String(error)}
      tone="deny"
    />
  )
}

interface PanelGuardProps {
  panel: Panel | undefined
  children: ReactNode
  emptyLabel?: string
}

export const OUT_OF_SCOPE = 'This module is not part of your effective capability set.'

export function PanelGuard({ panel, children, emptyLabel }: PanelGuardProps) {
  if (!panel) return <Forbidden reason={OUT_OF_SCOPE} />
  if (!panel.available) return <NoData reason={panel.reason || emptyLabel} />
  return <>{children}</>
}

export function DegradedBanner({ reason }: { reason?: string }) {
  if (!reason) return null
  return (
    <div className="flex items-start gap-2 rounded-md border border-warn/30 bg-warn/10 px-3 py-2 text-xs text-warn">
      <AlertTriangle className="mt-0.5 size-3.5 shrink-0" />
      <span>{reason}</span>
    </div>
  )
}
