import { useId } from 'react'
import { cn } from '@/lib/utils'

interface SparklineProps {
  values: number[]
  height?: number
  className?: string
  ariaLabel?: string
}

export function Sparkline({ values, height = 36, className, ariaLabel }: SparklineProps) {
  const gradientId = useId()
  if (values.length === 0) {
    return <div className="text-xs text-nodata">no series</div>
  }
  const width = 100
  const min = Math.min(...values)
  const max = Math.max(...values)
  const span = max - min || 1
  const step = values.length > 1 ? width / (values.length - 1) : width
  const points = values.map((value, index) => {
    const x = index * step
    const y = height - ((value - min) / span) * (height - 4) - 2
    return [x, y] as const
  })
  const line = points.map(([x, y], index) => `${index === 0 ? 'M' : 'L'}${x.toFixed(2)},${y.toFixed(2)}`).join(' ')
  const area = `${line} L${width},${height} L0,${height} Z`
  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      preserveAspectRatio="none"
      className={cn('h-9 w-full', className)}
      role="img"
      aria-label={ariaLabel ?? `sparkline of ${values.length} points`}
    >
      <defs>
        <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="var(--primary)" stopOpacity="0.35" />
          <stop offset="100%" stopColor="var(--primary)" stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={area} fill={`url(#${gradientId})`} />
      <path
        d={line}
        fill="none"
        stroke="var(--primary)"
        strokeWidth="1.5"
        vectorEffect="non-scaling-stroke"
        strokeLinejoin="round"
        strokeLinecap="round"
      />
    </svg>
  )
}

export interface BarDatum {
  label: string
  value: number
  hint?: string
  tone?: 'primary' | 'allow' | 'deny' | 'warn' | 'info'
}

const BAR_TONE: Record<NonNullable<BarDatum['tone']>, string> = {
  primary: 'bg-primary',
  allow: 'bg-allow',
  deny: 'bg-deny',
  warn: 'bg-warn',
  info: 'bg-info',
}

export function BarList({ data, max }: { data: BarDatum[]; max?: number }) {
  if (data.length === 0) return <p className="text-xs text-nodata">no distribution</p>
  const ceiling = max ?? Math.max(...data.map((datum) => datum.value), 1)
  return (
    <ul className="space-y-1.5">
      {data.map((datum) => (
        <li key={datum.label}>
          <div className="flex items-baseline justify-between gap-2 text-xs">
            <span className="truncate text-foreground">{datum.label}</span>
            <span className="shrink-0 font-mono tabular text-muted-foreground">
              {datum.hint ?? datum.value}
            </span>
          </div>
          <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-muted">
            <div
              className={cn('h-full rounded-full', BAR_TONE[datum.tone ?? 'primary'])}
              style={{ width: `${Math.max(2, (datum.value / ceiling) * 100)}%` }}
            />
          </div>
        </li>
      ))}
    </ul>
  )
}

interface MeterProps {
  value: number | null
  label?: string
  tone?: 'primary' | 'allow' | 'deny' | 'warn'
}

export function Meter({ value, label, tone = 'primary' }: MeterProps) {
  if (value === null) {
    return (
      <div className="h-1.5 w-full overflow-hidden rounded-full border border-dashed border-nodata/40" />
    )
  }
  const clamped = Math.max(0, Math.min(1, value))
  return (
    <div
      className="h-1.5 w-full overflow-hidden rounded-full bg-muted"
      role="meter"
      aria-valuenow={Math.round(clamped * 100)}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-label={label ?? 'ratio'}
    >
      <div
        className={cn('h-full rounded-full', BAR_TONE[tone])}
        style={{ width: `${clamped * 100}%` }}
      />
    </div>
  )
}

export function DeltaDot({ direction }: { direction: string }) {
  const tone =
    direction === 'improving'
      ? 'bg-allow'
      : direction === 'degrading'
        ? 'bg-deny'
        : direction === 'flat'
          ? 'bg-info'
          : 'bg-nodata'
  return <span className={cn('inline-block size-2 rounded-full', tone)} aria-hidden="true" />
}
