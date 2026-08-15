import type { ReactNode } from 'react'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { ErrorBoundary } from '@/components/ErrorBoundary'
import { ErrorNotice, PanelGuard, PanelSkeleton } from '@/components/ui/feedback'
import type { Panel } from '@/lib/types'

interface ModuleCardProps {
  title: ReactNode
  description?: ReactNode
  icon?: ReactNode
  actions?: ReactNode
  moduleName: string
  isLoading?: boolean
  error?: unknown
  panel?: Panel
  emptyLabel?: string
  children: ReactNode
  footer?: ReactNode
  bodyClassName?: string
}

export function ModuleCard({
  title,
  description,
  icon,
  actions,
  moduleName,
  isLoading,
  error,
  panel,
  emptyLabel,
  children,
  footer,
  bodyClassName,
}: ModuleCardProps) {
  return (
    <ErrorBoundary moduleName={moduleName}>
      <Card className="flex h-full flex-col">
        <CardHeader title={title} description={description} icon={icon} actions={actions} />
        <div className="flex-1">
          {isLoading ? (
            <PanelSkeleton />
          ) : error ? (
            <CardContent>
              <ErrorNotice error={error} />
            </CardContent>
          ) : (
            <CardContent className={bodyClassName}>
              <PanelGuard panel={panel} emptyLabel={emptyLabel}>
                {children}
              </PanelGuard>
            </CardContent>
          )}
        </div>
        {footer ? <div className="border-t border-border px-4 py-2 text-xs text-muted-foreground">{footer}</div> : null}
      </Card>
    </ErrorBoundary>
  )
}
