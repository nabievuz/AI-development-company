import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

export interface Column<T> {
  key: string
  header: ReactNode
  cell: (row: T) => ReactNode
  align?: 'left' | 'right'
  width?: string
  mono?: boolean
}

interface DataTableProps<T> {
  columns: Column<T>[]
  rows: T[]
  rowKey: (row: T, index: number) => string
  empty?: ReactNode
  dense?: boolean
  maxHeight?: string
}

export function DataTable<T>({
  columns,
  rows,
  rowKey,
  empty,
  dense = false,
  maxHeight,
}: DataTableProps<T>) {
  if (rows.length === 0 && empty) return <>{empty}</>
  return (
    <div
      className={cn('scrollbar-thin overflow-auto', maxHeight)}
      style={maxHeight ? undefined : undefined}
    >
      <table className="w-full border-collapse text-sm">
        <thead className="sticky top-0 z-10 bg-surface">
          <tr className="border-b border-border">
            {columns.map((column) => (
              <th
                key={column.key}
                scope="col"
                style={column.width ? { width: column.width } : undefined}
                className={cn(
                  'px-3 py-2 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground',
                  column.align === 'right' ? 'text-right' : 'text-left',
                )}
              >
                {column.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr
              key={rowKey(row, index)}
              className="border-b border-border/60 last:border-0 hover:bg-accent/40"
            >
              {columns.map((column) => (
                <td
                  key={column.key}
                  className={cn(
                    'px-3 align-middle',
                    dense ? 'py-1.5' : 'py-2',
                    column.align === 'right' ? 'text-right' : 'text-left',
                    column.mono ? 'font-mono text-xs tabular' : '',
                  )}
                >
                  {column.cell(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function KeyValue({ items }: { items: { label: ReactNode; value: ReactNode }[] }) {
  return (
    <dl className="grid grid-cols-1 gap-x-6 gap-y-2 sm:grid-cols-2">
      {items.map((item, index) => (
        <div key={index} className="flex items-baseline justify-between gap-3 border-b border-border/50 pb-1.5">
          <dt className="text-xs text-muted-foreground">{item.label}</dt>
          <dd className="font-mono text-xs tabular">{item.value}</dd>
        </div>
      ))}
    </dl>
  )
}
