import type { HTMLAttributes, ReactNode } from 'react'
import { cn } from '@/lib/utils'

export function Card({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        'rounded-lg border border-border bg-card text-card-foreground shadow-sm',
        className,
      )}
      {...props}
    />
  )
}

interface CardHeaderProps extends Omit<HTMLAttributes<HTMLDivElement>, 'title'> {
  title: ReactNode
  description?: ReactNode
  actions?: ReactNode
  icon?: ReactNode
}

export function CardHeader({
  title,
  description,
  actions,
  icon,
  className,
  ...props
}: CardHeaderProps) {
  return (
    <div
      className={cn('flex items-start justify-between gap-3 border-b border-border px-4 py-3', className)}
      {...props}
    >
      <div className="min-w-0">
        <div className="flex items-center gap-2">
          {icon ? <span className="text-muted-foreground">{icon}</span> : null}
          <h2 className="truncate text-sm font-semibold tracking-tight">{title}</h2>
        </div>
        {description ? (
          <p className="mt-0.5 text-xs text-muted-foreground">{description}</p>
        ) : null}
      </div>
      {actions ? <div className="shrink-0">{actions}</div> : null}
    </div>
  )
}

export function CardContent({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('p-4', className)} {...props} />
}

export function CardFooter({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn('border-t border-border px-4 py-2 text-xs text-muted-foreground', className)}
      {...props}
    />
  )
}
