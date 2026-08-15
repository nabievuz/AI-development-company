import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs))
}

export function percent(value: number | null | undefined, digits = 0): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—'
  return `${(value * 100).toFixed(digits)}%`
}

export function count(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—'
  return new Intl.NumberFormat('en-US').format(value)
}

export function usd(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—'
  const digits = value !== 0 && Math.abs(value) < 0.01 ? 6 : 4
  return `$${value.toFixed(digits)}`
}

export function decimal(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—'
  return value.toFixed(digits)
}

export function bytes(value: number | null | undefined): string {
  if (!value || value < 0) return '—'
  const units = ['B', 'KB', 'MB']
  let size = value
  let unit = 0
  while (size >= 1024 && unit < units.length - 1) {
    size /= 1024
    unit += 1
  }
  return `${size.toFixed(unit === 0 ? 0 : 1)} ${units[unit]}`
}

export function shortTime(value: string | undefined | null): string {
  if (!value) return '—'
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return value
  return parsed.toISOString().replace('T', ' ').replace(/\.\d+Z$/, 'Z').replace(/Z$/, ' UTC')
}

export function relativeTime(value: string | undefined | null): string {
  if (!value) return '—'
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return value
  const seconds = Math.round((Date.now() - parsed.getTime()) / 1000)
  const table: [number, Intl.RelativeTimeFormatUnit][] = [
    [60, 'second'],
    [3600, 'minute'],
    [86400, 'hour'],
    [2592000, 'day'],
    [31536000, 'month'],
  ]
  const formatter = new Intl.RelativeTimeFormat('en', { numeric: 'auto' })
  if (seconds < 60) return formatter.format(-seconds, 'second')
  for (let index = 1; index < table.length; index += 1) {
    const [limit, unit] = table[index]
    if (seconds < limit) {
      const divisor = table[index - 1][0]
      return formatter.format(-Math.round(seconds / divisor), unit)
    }
  }
  return formatter.format(-Math.round(seconds / 31536000), 'year')
}

export function titleCase(value: string): string {
  return value
    .replace(/[-_.]/g, ' ')
    .replace(/\b\w/g, (character) => character.toUpperCase())
    .trim()
}
