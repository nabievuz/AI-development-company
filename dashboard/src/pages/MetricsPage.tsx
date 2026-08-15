import { useMemo } from 'react'
import type { ReactNode } from 'react'
import { Activity, AlertTriangle, Gauge, TrendingUp, Waves } from 'lucide-react'
import { ModuleCard } from '@/components/ModuleCard'
import { Badge } from '@/components/ui/badge'
import { Stat, StatGrid } from '@/components/ui/stat'
import { KeyValue } from '@/components/ui/table'
import { DegradedBanner } from '@/components/ui/feedback'
import { DeltaDot, Meter, Sparkline } from '@/components/charts'
import { useModuleQuery, SLOW_INTERVAL } from '@/hooks/useModuleQuery'
import { api } from '@/lib/api'
import { count, decimal, percent, titleCase } from '@/lib/utils'
import type { HealthTrack, MetricsResponse, TracksPanel } from '@/lib/types'

function trackValue(track: HealthTrack): string {
  if (!track.available) return '—'
  if (track.value === null) return 'intact'
  if (track.unit === 'ratio') return percent(track.value, 1)
  if (Number.isInteger(track.value)) return count(track.value)
  return decimal(track.value, 2)
}

function detailItems(detail: Record<string, unknown>): { label: ReactNode; value: ReactNode }[] {
  const items: { label: ReactNode; value: ReactNode }[] = []
  for (const [key, raw] of Object.entries(detail)) {
    const label = titleCase(key)
    if (typeof raw === 'number') {
      if (!Number.isFinite(raw)) continue
      items.push({ label, value: Number.isInteger(raw) ? count(raw) : decimal(raw, 3) })
    } else if (typeof raw === 'boolean') {
      items.push({ label, value: raw ? 'yes' : 'no' })
    } else if (typeof raw === 'string' && raw.length > 0) {
      items.push({ label, value: raw })
    }
  }
  return items
}

function degradedReason(tracks: TracksPanel): string | undefined {
  if (!tracks.available || tracks.degraded.length === 0) return undefined
  const named = tracks.degraded.map((code) => {
    const match = tracks.tracks.find((track) => track.code === code)
    return match ? `${match.code} ${match.title}` : code
  })
  return `${named.length} of ${tracks.tracks.length} tracks report no data: ${named.join(' · ')}. The console shows their reason instead of a number.`
}

function TrackCard({ track }: { track: HealthTrack }) {
  const items = detailItems(track.detail)
  return (
    <article className="rounded-lg border border-border bg-card p-3">
      <header className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <span className="font-mono text-[11px] text-muted-foreground">{track.code}</span>
          <h3 className="truncate text-xs font-medium">{track.title}</h3>
        </div>
        {track.available ? (
          <Badge variant="outline">{track.unit}</Badge>
        ) : (
          <Badge variant="nodata">no data</Badge>
        )}
      </header>

      <p
        className={
          track.available
            ? 'mt-2 font-mono text-2xl font-semibold tabular'
            : 'mt-2 font-mono text-2xl font-semibold tabular text-nodata'
        }
      >
        {trackValue(track)}
      </p>

      <div className="mt-2">
        <Meter
          value={track.available && track.unit === 'ratio' ? track.value : null}
          label={`${track.code} ${track.title}`}
        />
      </div>

      {track.available ? null : (
        <p className="mt-2 text-[11px] text-nodata">{track.reason}</p>
      )}

      {items.length > 0 ? (
        <div className="mt-3 border-t border-border/60 pt-2">
          <KeyValue items={items} />
        </div>
      ) : null}
    </article>
  )
}

export function MetricsPage() {
  const query = useModuleQuery<MetricsResponse>('metrics', (signal) => api.metrics(signal), {
    refetchInterval: SLOW_INTERVAL,
  })

  const tracks = query.data?.tracks
  const throughput = query.data?.throughput
  const banner = useMemo(() => (tracks ? degradedReason(tracks) : undefined), [tracks])
  const measured = tracks?.available
    ? tracks.tracks.filter((track) => track.available).length
    : null

  return (
    <div className="space-y-4">
      <DegradedBanner reason={banner} />

      <StatGrid>
        <Stat
          label="Events observed"
          value={tracks?.available ? count(tracks.events) : '—'}
          hint={tracks?.available ? 'rows behind every track' : tracks?.reason}
          tone={tracks?.available ? 'default' : 'nodata'}
          icon={<Activity className="size-3.5" aria-hidden="true" />}
        />
        <Stat
          label="Waves observed"
          value={tracks?.available ? count(tracks.waves) : '—'}
          hint={tracks?.available ? 'dispatch cycles in the window' : tracks?.reason}
          tone={tracks?.available ? 'default' : 'nodata'}
          icon={<Waves className="size-3.5" aria-hidden="true" />}
        />
        <Stat
          label="Tracks with data"
          value={measured === null ? '—' : count(measured)}
          hint={tracks?.available ? `of ${tracks.tracks.length} T-tracks` : 'tracks unavailable'}
          tone={measured === null ? 'nodata' : 'default'}
          icon={<Gauge className="size-3.5" aria-hidden="true" />}
        />
        <Stat
          label="Tracks degraded"
          value={tracks?.available ? count(tracks.degraded.length) : '—'}
          hint={tracks?.available ? 'no measurement, not a zero' : 'tracks unavailable'}
          tone={tracks?.available && tracks.degraded.length > 0 ? 'warn' : 'default'}
          icon={<AlertTriangle className="size-3.5" aria-hidden="true" />}
        />
      </StatGrid>

      <ModuleCard
        title="Health tracks T1–T7"
        description="Each track is computed from the live event store; a track without evidence states its reason instead of a number."
        icon={<Gauge className="size-3.5" aria-hidden="true" />}
        moduleName="Health tracks"
        isLoading={query.isLoading}
        error={query.isError ? query.error : undefined}
        panel={tracks}
        emptyLabel="track metrics are unavailable at your tier"
        actions={
          tracks?.available && tracks.degraded.length > 0 ? (
            <Badge variant="nodata">{tracks.degraded.length} without data</Badge>
          ) : null
        }
      >
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
          {(tracks?.tracks ?? []).map((track) => (
            <TrackCard key={track.code} track={track} />
          ))}
        </div>
      </ModuleCard>

      <ModuleCard
        title="Throughput trend"
        description="Direction and slope over the recorded completion series"
        icon={<TrendingUp className="size-3.5" aria-hidden="true" />}
        moduleName="Throughput"
        isLoading={query.isLoading}
        error={query.isError ? query.error : undefined}
        panel={throughput}
        emptyLabel="trend needs more completed runs"
      >
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
          <span className="flex items-center gap-2">
            <DeltaDot direction={throughput?.direction ?? ''} />
            <span className="text-xs capitalize">{throughput?.direction || '—'}</span>
          </span>
          <span className="font-mono text-xs tabular text-muted-foreground">
            slope {throughput?.slope === undefined ? '—' : decimal(throughput.slope, 3)}
          </span>
          <span className="font-mono text-xs tabular text-muted-foreground">
            {count(throughput?.series.length ?? 0)} points
          </span>
        </div>
        <div className="mt-3">
          <Sparkline values={throughput?.series ?? []} ariaLabel="throughput trend" />
        </div>
      </ModuleCard>
    </div>
  )
}
